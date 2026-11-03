# R3 CONTROLLED SOURCE
# File: runtime/assignment_intake.py
# Component: R3-STEWARD-ASSIGNMENT-INTAKE
# File Revision: 1.0.1
# Created: 2026-11-03 UTC (exact time unverified)
# Created By: ChatGPT GPT-6 via GitHub API
# Purpose: Authenticated loopback API for durable resident assignment submission and status.
# Execution Model: Threaded HTTP server hosted by runtime.serve when explicitly configured.
# Observability: Durable assignment identity, idempotency, inbox event lineage, and review status.
# Dependencies: Python standard library; runtime.resident_inference; runtime.verification.
# Authority: Steward-approved R3 charter; loopback-only and bearer-token protected.
# Changed: 2026-11-03 UTC | R3-ASSIGNMENT-INTAKE-001 | ChatGPT GPT-6 | Add opt-in durable assignment API.
# Changed: 2026-11-03 UTC | R3-SHUTDOWN-ADMISSION-001 | Gate assignment writes before runtime shutdown.
# Supersedes: None
# Contracts: docs/r3-assignment-intake-contract.md; hints/engineering-test-policy.md
# Tests: tests/test_assignment_intake.py
# History/Predecessor: New file.
"""Authenticated, loopback-only assignment ingress for the R3 resident runtime."""
from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from contextlib import closing
import json
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import time
from urllib.parse import unquote

from runtime.admission import AdmissionGate
from runtime.resident_inference import Inbox
from runtime.verification import VerificationLedger


class IntakeError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class AssignmentIntake:
    def __init__(self, database: Path, token: str, residents: set[str],
                 continuation_residents: set[str]):
        if len(token) < 32:
            raise ValueError("Assignment intake token must contain at least 32 characters")
        self.database = Path(database)
        self.token = token
        self.residents = frozenset(residents)
        self.continuation_residents = frozenset(continuation_residents)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        db = self._connect()
        try:
            db.execute("""CREATE TABLE IF NOT EXISTS assignment_intake_assignments (
                assignment_id TEXT PRIMARY KEY,
                request_sha256 TEXT NOT NULL,
                event_id INTEGER NOT NULL UNIQUE,
                resident TEXT NOT NULL,
                created_at REAL NOT NULL
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS assignment_intake_keys (
                idempotency_key TEXT PRIMARY KEY,
                request_sha256 TEXT NOT NULL,
                event_id INTEGER NOT NULL,
                created_at REAL NOT NULL
            )""")
            db.commit()
        finally:
            db.close()

    def _connect(self):
        return sqlite3.connect(str(self.database), timeout=10)

    def authorized(self, header: str | None) -> bool:
        if not isinstance(header, str) or not header.startswith("Bearer "):
            return False
        supplied = header[7:]
        return bool(supplied) and secrets.compare_digest(supplied, self.token)

    @staticmethod
    def _validate(payload, idempotency_key: str):
        if not isinstance(payload, dict):
            raise IntakeError(400, "Request body must be an object")
        allowed = {"resident", "assignment_id", "objective", "acceptance_criteria",
                   "next_step", "correlation_id"}
        if set(payload) - allowed:
            raise IntakeError(400, "Request contains unsupported fields")
        for field in ("resident", "assignment_id", "objective"):
            value = payload.get(field)
            if not isinstance(value, str) or not value.strip():
                raise IntakeError(400, f"{field} must be nonempty text")
        if not isinstance(idempotency_key, str) or not re.fullmatch(r"[A-Za-z0-9._:-]+", idempotency_key):
            raise IntakeError(400, "A valid Idempotency-Key header is required")
        criteria = payload.get("acceptance_criteria")
        if not isinstance(criteria, list) or not criteria:
            raise IntakeError(400, "acceptance_criteria must be a nonempty list")
        seen = set()
        for item in criteria:
            if not isinstance(item, dict) or set(item) - {"id", "version", "description"}:
                raise IntakeError(400, "Each acceptance criterion must contain id, version, and description")
            for field in ("id", "version", "description"):
                if not isinstance(item.get(field), str) or not item[field].strip():
                    raise IntakeError(400, f"Acceptance criterion {field} must be nonempty text")
            if item["id"] in seen:
                raise IntakeError(400, "Acceptance criterion identifiers must be unique")
            seen.add(item["id"])
        for field in ("next_step", "correlation_id"):
            if field in payload and (not isinstance(payload[field], str) or not payload[field].strip()):
                raise IntakeError(400, f"{field} must be nonempty text when supplied")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return payload, hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def submit(self, payload, idempotency_key: str):
        payload, digest = self._validate(payload, idempotency_key)
        resident = payload["resident"]
        if resident not in self.residents:
            raise IntakeError(404, "Resident is not registered")
        if resident not in self.continuation_residents:
            raise IntakeError(409, "Resident is not configured for durable assignment activities")

        db = self._connect()
        try:
            Inbox(db)
            db.execute("BEGIN IMMEDIATE")
            prior_key = db.execute(
                "SELECT request_sha256,event_id FROM assignment_intake_keys WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if prior_key:
                if prior_key[0] != digest:
                    raise IntakeError(409, "Idempotency key was already used for different content")
                db.commit()
                return {"event_id": int(prior_key[1]), "status": "DUPLICATE"}
            prior_assignment = db.execute(
                "SELECT request_sha256,event_id FROM assignment_intake_assignments WHERE assignment_id=?",
                (payload["assignment_id"],),
            ).fetchone()
            if prior_assignment:
                if prior_assignment[0] != digest:
                    raise IntakeError(409, "Assignment identifier was already used for different content")
                db.execute(
                    "INSERT INTO assignment_intake_keys(idempotency_key,request_sha256,event_id,created_at) VALUES (?,?,?,?)",
                    (idempotency_key, digest, prior_assignment[1], time.time()),
                )
                db.commit()
                return {"event_id": int(prior_assignment[1]), "status": "DUPLICATE"}

            event_payload = {
                "assignment_id": payload["assignment_id"],
                "objective": payload["objective"],
                "acceptance_criteria": payload["acceptance_criteria"],
                "intake": {"channel": "r3-assignment-intake", "request_sha256": digest,
                           "received_at": time.time()},
            }
            if "next_step" in payload:
                event_payload["next_step"] = payload["next_step"]
            if "correlation_id" in payload:
                event_payload["correlation_id"] = payload["correlation_id"]
            now = time.time()
            cursor = db.execute(
                "INSERT INTO resident_inbox(resident,event_type,payload,created_at,updated_at) VALUES (?,?,?,?,?)",
                (resident, "RESIDENT_ACTIVITY", json.dumps(event_payload), now, now),
            )
            event_id = int(cursor.lastrowid)
            db.execute(
                "INSERT INTO assignment_intake_assignments(assignment_id,request_sha256,event_id,resident,created_at) VALUES (?,?,?,?,?)",
                (payload["assignment_id"], digest, event_id, resident, now),
            )
            db.execute(
                "INSERT INTO assignment_intake_keys(idempotency_key,request_sha256,event_id,created_at) VALUES (?,?,?,?)",
                (idempotency_key, digest, event_id, now),
            )
            db.commit()
            return {"event_id": event_id, "status": "PENDING"}
        except IntakeError:
            db.rollback()
            raise
        except sqlite3.Error:
            db.rollback()
            raise IntakeError(503, "Assignment store unavailable") from None
        finally:
            db.close()

    def status(self, root_event_id: int):
        with closing(self._connect()) as db:
            assignment = db.execute(
                "SELECT assignment_id,resident FROM assignment_intake_assignments WHERE event_id=?",
                (root_event_id,),
            ).fetchone()
            if assignment is None:
                raise IntakeError(404, "Assignment not found")
            assignment_id, resident = assignment
            events = []
            current_id = root_event_id
            visited = set()
            while current_id not in visited:
                visited.add(current_id)
                row = db.execute(
                    "SELECT id,event_type,status,result FROM resident_inbox WHERE id=?",
                    (current_id,),
                ).fetchone()
                if row is None:
                    break
                result = json.loads(row[3]) if row[3] else None
                events.append({"event_id": row[0], "event_type": row[1],
                               "status": row[2], "result": result})
                next_id = result.get("continuation_event_id") if isinstance(result, dict) else None
                if not isinstance(next_id, int):
                    break
                current_id = next_id
            review = VerificationLedger(db).assignment_review_status(assignment_id)
            return {"assignment_id": assignment_id, "resident": resident,
                    "root_event_id": root_event_id, "events": events,
                    "verification": review}


def create_server(database: Path, token_file: Path, residents: set[str],
                  continuation_residents: set[str], *, host: str = "127.0.0.1",
                  port: int, admission_gate: AdmissionGate | None = None):
    if host != "127.0.0.1":
        raise ValueError("Assignment intake must bind to 127.0.0.1")
    if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
        raise ValueError("Invalid assignment intake port")
    token_path = Path(token_file)
    metadata = token_path.stat()
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        raise ValueError("Assignment intake token file must not be group- or world-accessible")
    token = token_path.read_text(encoding="utf-8").strip()
    app = AssignmentIntake(database, token, residents, continuation_residents)
    gate = admission_gate or AdmissionGate()

    class Handler(BaseHTTPRequestHandler):
        def _respond(self, code, payload):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self):
            if app.authorized(self.headers.get("Authorization")):
                return True
            self._respond(401, {"error": "Unauthorized"})
            return False

        def do_POST(self):
            if self.path != "/v1/assignments":
                self._respond(404, {"error": "Not found"})
                return
            if not self._authorized():
                return
            try:
                size = int(self.headers.get("Content-Length", "-1"))
                if size < 0 or size > 1_048_576:
                    self._respond(413, {"error": "Invalid request size"})
                    return
                payload = json.loads(self.rfile.read(size))
                with gate.enter() as admitted:
                    if not admitted:
                        self._respond(503, {"error": "service_shutting_down"})
                        return
                    result = app.submit(payload, self.headers.get("Idempotency-Key"))
                self._respond(200 if result["status"] == "DUPLICATE" else 202, result)
            except IntakeError as exc:
                self._respond(exc.status, {"error": str(exc)})
            except (ValueError, UnicodeError):
                self._respond(400, {"error": "Invalid JSON request"})

        def do_GET(self):
            if not self.path.startswith("/v1/assignments/"):
                self._respond(404, {"error": "Not found"})
                return
            if not self._authorized():
                return
            suffix = unquote(self.path.removeprefix("/v1/assignments/"))
            if not suffix.isdigit():
                self._respond(400, {"error": "Assignment event id must be numeric"})
                return
            try:
                self._respond(200, app.status(int(suffix)))
            except IntakeError as exc:
                self._respond(exc.status, {"error": str(exc)})

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server
