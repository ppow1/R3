# R3 CONTROLLED SOURCE
# File: runtime/conversations.py
# Component: R3-DURABLE-CONVERSATIONS
# File Revision: 1.0.1
# Purpose: Durable resident conversations backed by the institutional SQLite database.
# Execution Model: Loopback HTTP ingress plus the existing resident scheduler.
# Authority: Website backend authenticates Steward; this service validates its trusted
#            backend principal assertion and confines each conversation to its owner.
"""Durable conversation storage and loopback HTTP API for resident chat."""
from __future__ import annotations

from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import time
import uuid
from urllib.parse import parse_qs, unquote, urlsplit

from runtime.admission import AdmissionGate
from runtime.resident_inference import Inbox

# A JSON-escaped Unicode code point can occupy up to 12 bytes (a surrogate pair).
# Keep the HTTP body ceiling large enough for the 100,000-character API contract.
MAX_MESSAGE_CHARACTERS = 100_000
MAX_REQUEST_BODY_BYTES = MAX_MESSAGE_CHARACTERS * 12 + 512


class ConversationError(Exception):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status = status
        self.code = code


class ConversationStore:
    """SQLite conversation records; each store instance owns its connection."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        Inbox(db)
        db.execute("""CREATE TABLE IF NOT EXISTS r3_conversations (
            conversation_id TEXT PRIMARY KEY,
            resident TEXT NOT NULL,
            owner_principal TEXT NOT NULL,
            title TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'OPEN',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS r3_conversation_messages (
            message_id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL REFERENCES r3_conversations(conversation_id),
            sequence INTEGER NOT NULL,
            sender_type TEXT NOT NULL,
            sender_id TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at REAL NOT NULL,
            delivery_status TEXT NOT NULL,
            client_message_id TEXT,
            inbox_event_id INTEGER,
            error_code TEXT,
            UNIQUE(conversation_id, sequence),
            UNIQUE(conversation_id, sender_id, client_message_id)
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS r3_conversation_owner ON r3_conversations(owner_principal,resident,state,updated_at)")
        db.execute("CREATE INDEX IF NOT EXISTS r3_conversation_message_order ON r3_conversation_messages(conversation_id,sequence)")
        db.commit()

    @staticmethod
    def _now() -> float:
        return time.time()

    def _owned(self, conversation_id: str, principal: str):
        row = self.db.execute(
            "SELECT conversation_id,resident,title,state,created_at,updated_at "
            "FROM r3_conversations WHERE conversation_id=? AND owner_principal=?",
            (conversation_id, principal),
        ).fetchone()
        if row is None:
            raise ConversationError(404, "conversation_not_found")
        return row

    def list_conversations(self, principal: str, resident: str):
        rows = self.db.execute(
            "SELECT conversation_id,resident,title,state,created_at,updated_at "
            "FROM r3_conversations WHERE owner_principal=? AND resident=? "
            "ORDER BY updated_at DESC,conversation_id",
            (principal, resident),
        ).fetchall()
        return [self._conversation_dict(row) for row in rows]

    @staticmethod
    def _conversation_dict(row):
        return {
            "conversation_id": row[0], "resident": row[1], "title": row[2],
            "state": row[3], "created_at": row[4], "updated_at": row[5],
        }

    def create_conversation(self, principal: str, resident: str, title: str):
        now = self._now()
        conversation_id = str(uuid.uuid4())
        with self.db:
            self.db.execute(
                "INSERT INTO r3_conversations(conversation_id,resident,owner_principal,title,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?)",
                (conversation_id, resident, principal, title, now, now),
            )
        return self._conversation_dict(
            (conversation_id, resident, title, "OPEN", now, now)
        )

    def _reconcile(self, conversation_id: str):
        rows = self.db.execute(
            "SELECT m.inbox_event_id,i.status,i.result,i.resident FROM r3_conversation_messages m "
            "JOIN resident_inbox i ON i.id=m.inbox_event_id "
            "WHERE m.conversation_id=? AND m.sender_type='STEWARD' AND m.inbox_event_id IS NOT NULL",
            (conversation_id,),
        ).fetchall()
        for event_id, status, encoded, resident in rows:
            if status == "FAILED":
                self.fail_event(event_id, "resident_inference_failed")
            elif status == "COMPLETED":
                result = json.loads(encoded) if encoded else {}
                message = result.get("message") if isinstance(result, dict) else None
                content = message.get("content") if isinstance(message, dict) else ""
                self.complete_event(event_id, resident, str(content or ""))

    def messages(self, principal: str, conversation_id: str, *, after: int, limit: int):
        self._owned(conversation_id, principal)
        self._reconcile(conversation_id)
        rows = self.db.execute(
            "SELECT message_id,conversation_id,sequence,sender_type,sender_id,content,"
            "created_at,delivery_status,client_message_id,error_code "
            "FROM r3_conversation_messages WHERE conversation_id=? AND sequence>? "
            "ORDER BY sequence LIMIT ?",
            (conversation_id, after, limit),
        ).fetchall()
        items = [{
            "message_id": r[0], "conversation_id": r[1], "sequence": r[2],
            "sender_type": r[3], "sender_id": r[4], "content": r[5],
            "created_at": r[6], "delivery_status": r[7],
            "client_message_id": r[8], "error_code": r[9],
        } for r in rows]
        return {"messages": items, "next_after": items[-1]["sequence"] if items else after}

    def send_message(self, principal: str, conversation_id: str, content: str,
                     client_message_id: str):
        row = self._owned(conversation_id, principal)
        if row[3] != "OPEN":
            raise ConversationError(409, "conversation_not_open")
        prior = self.db.execute(
            "SELECT message_id,sequence,delivery_status,inbox_event_id,content "
            "FROM r3_conversation_messages WHERE conversation_id=? AND sender_id=? AND client_message_id=?",
            (conversation_id, principal, client_message_id),
        ).fetchone()
        if prior:
            if prior[4] != content:
                raise ConversationError(409, "idempotency_key_conflict")
            return {
                "message_id": prior[0], "sequence": prior[1],
                "delivery_status": prior[2], "event_id": prior[3], "duplicate": True,
            }
        now = self._now()
        message_id = str(uuid.uuid4())
        event_payload = {
            "conversation_id": conversation_id,
            "message_id": message_id,
        }
        try:
            self.db.execute("BEGIN IMMEDIATE")
            sequence = int(self.db.execute(
                "SELECT COALESCE(MAX(sequence),0)+1 FROM r3_conversation_messages WHERE conversation_id=?",
                (conversation_id,),
            ).fetchone()[0])
            cursor = self.db.execute(
                "INSERT INTO resident_inbox(resident,event_type,payload,created_at,updated_at) "
                "VALUES (?, 'CONVERSATION_MESSAGE', ?, ?, ?)",
                (row[1], json.dumps(event_payload), now, now),
            )
            event_id = int(cursor.lastrowid)
            self.db.execute(
                "INSERT INTO r3_conversation_messages(message_id,conversation_id,sequence,sender_type,sender_id,"
                "content,created_at,delivery_status,client_message_id,inbox_event_id) "
                "VALUES (?,?,?,'STEWARD',?,?,?,'QUEUED',?,?)",
                (message_id, conversation_id, sequence, principal, content, now, client_message_id, event_id),
            )
            self.db.execute(
                "UPDATE r3_conversations SET updated_at=? WHERE conversation_id=?",
                (now, conversation_id),
            )
            self.db.commit()
        except sqlite3.IntegrityError:
            self.db.rollback()
            prior = self.db.execute(
                "SELECT message_id,sequence,delivery_status,inbox_event_id,content "
                "FROM r3_conversation_messages WHERE conversation_id=? AND sender_id=? AND client_message_id=?",
                (conversation_id, principal, client_message_id),
            ).fetchone()
            if prior:
                if prior[4] != content:
                    raise ConversationError(409, "idempotency_key_conflict")
                return {
                    "message_id": prior[0], "sequence": prior[1],
                    "delivery_status": prior[2], "event_id": prior[3], "duplicate": True,
                }
            raise ConversationError(409, "message_conflict") from None
        except sqlite3.Error:
            self.db.rollback()
            raise ConversationError(503, "conversation_store_unavailable") from None
        return {
            "message_id": message_id, "sequence": sequence,
            "delivery_status": "QUEUED", "event_id": event_id, "duplicate": False,
        }

    def prompt_history(self, conversation_id: str, current_message_id: str):
        self._reconcile(conversation_id)
        current = self.db.execute(
            "SELECT sequence FROM r3_conversation_messages WHERE message_id=? AND conversation_id=?",
            (current_message_id, conversation_id),
        ).fetchone()
        if current is None:
            raise RuntimeError("Conversation message is missing")
        self.db.execute(
            "UPDATE r3_conversation_messages SET delivery_status='PROCESSING' "
            "WHERE message_id=? AND delivery_status='QUEUED'",
            (current_message_id,),
        )
        self.db.commit()
        rows = self.db.execute(
            "SELECT sender_type,content FROM r3_conversation_messages "
            "WHERE conversation_id=? AND sequence<? AND delivery_status='DELIVERED' ORDER BY sequence",
            (conversation_id, current[0]),
        ).fetchall()
        history = []
        for sender_type, content in rows:
            history.append({"role": "assistant" if sender_type == "RESIDENT" else "user", "content": content})
        message = self.db.execute(
            "SELECT content FROM r3_conversation_messages WHERE message_id=?",
            (current_message_id,),
        ).fetchone()
        history.append({"role": "user", "content": message[0]})
        return history

    def complete_event(self, event_id: int, resident: str, content: str):
        now = self._now()
        with self.db:
            row = self.db.execute(
                "SELECT message_id,conversation_id FROM r3_conversation_messages WHERE inbox_event_id=?",
                (event_id,),
            ).fetchone()
            if row is None:
                return
            user_message_id, conversation_id = row
            self.db.execute(
                "UPDATE r3_conversation_messages SET delivery_status='DELIVERED' WHERE message_id=?",
                (user_message_id,),
            )
            exists = self.db.execute(
                "SELECT 1 FROM r3_conversation_messages WHERE inbox_event_id=? AND sender_type='RESIDENT'",
                (event_id,),
            ).fetchone()
            if not exists:
                sequence = int(self.db.execute(
                    "SELECT COALESCE(MAX(sequence),0)+1 FROM r3_conversation_messages WHERE conversation_id=?",
                    (conversation_id,),
                ).fetchone()[0])
                self.db.execute(
                    "INSERT INTO r3_conversation_messages(message_id,conversation_id,sequence,sender_type,sender_id,"
                    "content,created_at,delivery_status,inbox_event_id) "
                    "VALUES (?,?,?,'RESIDENT',?,?,?,'DELIVERED',?)",
                    (str(uuid.uuid4()), conversation_id, sequence, resident, content, now, event_id),
                )
                self.db.execute(
                    "UPDATE r3_conversations SET updated_at=? WHERE conversation_id=?",
                    (now, conversation_id),
                )

    def fail_event(self, event_id: int, error_code: str):
        with self.db:
            self.db.execute(
                "UPDATE r3_conversation_messages SET delivery_status='FAILED',error_code=? "
                "WHERE inbox_event_id=? AND sender_type='STEWARD'",
                (error_code[:80], event_id),
            )


def create_server(database: Path, token_file: Path, residents: set[str],
                  resident_actions: dict[str, list[str]], *, port: int,
                  admission_gate: AdmissionGate | None = None):
    """Build a localhost-only API; principal is asserted by the trusted website backend."""
    token_path = Path(token_file)
    metadata = token_path.stat()
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        raise ValueError("Conversation token file must not be group- or world-accessible")
    token = token_path.read_text(encoding="utf-8").strip()
    if len(token) < 32:
        raise ValueError("Conversation token must contain at least 32 characters")
    database = Path(database)
    gate = admission_gate or AdmissionGate()

    class Handler(BaseHTTPRequestHandler):
        def _reply(self, code, value):
            body = json.dumps(value, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _identity(self):
            auth = self.headers.get("Authorization", "")
            principal = self.headers.get("X-R3-Principal", "")
            if not auth.startswith("Bearer ") or not secrets.compare_digest(auth[7:], token):
                self._reply(401, {"error": "unauthorized"})
                return None
            if not re.fullmatch(r"[A-Za-z0-9._:@-]{1,160}", principal):
                self._reply(401, {"error": "trusted_principal_required"})
                return None
            return principal

        def _store(self):
            db = sqlite3.connect(str(database), timeout=10)
            db.execute("PRAGMA busy_timeout=10000")
            return db, ConversationStore(db)

        def _body(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > MAX_REQUEST_BODY_BYTES:
                    raise ValueError
                value = json.loads(self.rfile.read(length))
            except (ValueError, json.JSONDecodeError):
                raise ConversationError(400, "invalid_json") from None
            if not isinstance(value, dict):
                raise ConversationError(400, "object_required")
            return value

        def do_GET(self):
            principal = self._identity()
            if principal is None:
                return
            parts = [unquote(p) for p in urlsplit(self.path).path.split("/") if p]
            query = parse_qs(urlsplit(self.path).query)
            try:
                db, store = self._store()
                try:
                    if len(parts) == 4 and parts[:2] == ["v1", "residents"] and parts[3] == "conversations":
                        resident = parts[2]
                        if resident not in residents:
                            raise ConversationError(404, "resident_not_found")
                        self._reply(200, {"conversations": store.list_conversations(principal, resident)})
                        return
                    if len(parts) == 4 and parts[:2] == ["v1", "residents"] and parts[3] == "capabilities":
                        resident = parts[2]
                        if resident not in residents:
                            raise ConversationError(404, "resident_not_found")
                        self._reply(200, {
                            "resident": resident,
                            "message_actions": ["send_text"],
                            "resident_tools": resident_actions.get(resident, []),
                        })
                        return
                    if len(parts) == 4 and parts[0:2] == ["v1", "conversations"] and parts[3] == "messages":
                        after = int(query.get("after", ["0"])[0])
                        limit = min(max(int(query.get("limit", ["100"])[0]), 1), 200)
                        self._reply(200, store.messages(principal, parts[2], after=after, limit=limit))
                        return
                    raise ConversationError(404, "route_not_found")
                finally:
                    db.close()
            except ConversationError as exc:
                self._reply(exc.status, {"error": exc.code})
            except (ValueError, TypeError):
                self._reply(400, {"error": "invalid_query"})
            except sqlite3.Error:
                self._reply(503, {"error": "conversation_store_unavailable"})

        def do_POST(self):
            principal = self._identity()
            if principal is None:
                return
            parts = [unquote(p) for p in urlsplit(self.path).path.split("/") if p]
            try:
                body = self._body()
                db, store = self._store()
                try:
                    if len(parts) == 4 and parts[:2] == ["v1", "residents"] and parts[3] == "conversations":
                        resident = parts[2]
                        if resident not in residents:
                            raise ConversationError(404, "resident_not_found")
                        title = body.get("title", "")
                        if not isinstance(title, str) or len(title) > 200:
                            raise ConversationError(400, "invalid_title")
                        with gate.enter() as admitted:
                            if not admitted:
                                raise ConversationError(503, "service_shutting_down")
                            created = store.create_conversation(principal, resident, title)
                        self._reply(201, {"conversation": created})
                        return
                    if len(parts) == 4 and parts[0:2] == ["v1", "conversations"] and parts[3] == "messages":
                        content = body.get("content")
                        client_id = body.get("client_message_id")
                        if not isinstance(content, str) or not content.strip() or len(content) > MAX_MESSAGE_CHARACTERS:
                            raise ConversationError(400, "invalid_content")
                        if not isinstance(client_id, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,160}", client_id):
                            raise ConversationError(400, "client_message_id_required")
                        with gate.enter() as admitted:
                            if not admitted:
                                raise ConversationError(503, "service_shutting_down")
                            result = store.send_message(principal, parts[2], content, client_id)
                        self._reply(200 if result["duplicate"] else 202, result)
                        return
                    raise ConversationError(404, "route_not_found")
                finally:
                    db.close()
            except ConversationError as exc:
                self._reply(exc.status, {"error": exc.code})
            except sqlite3.Error:
                self._reply(503, {"error": "conversation_store_unavailable"})

        def log_message(self, fmt, *args):
            return

    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("Invalid conversation API port")
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server
