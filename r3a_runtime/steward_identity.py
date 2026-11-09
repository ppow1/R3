"""
R3 CONTROLLED SOURCE
File: r3a_runtime/steward_identity.py
Component: R3A-AP3-IDENTITY
File Revision: 1.0.0
Purpose: Verify independent R3A Steward credentials and implement governed identity association/enrollment.
Execution Model: Replaceable r3a.identity-provider.v1 adapter and local operator repository over AP0 PostgreSQL.
Observability: Privacy-safe institutional lifecycle events; credentials and challenge values are excluded.
Dependencies: AP3 StewardAccess; AP0 migration 010; Python hashlib.scrypt; psycopg.
Authority: Approved R3A Authentication Independence Plan; AP3/R3A-010; Issue #49.
Contracts: r3a.identity-provider.v1; r3a.steward-session.v1; r3a.steward-principal.v1.
Tests: tests/test_r3a_native_identity.py.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .steward_access import AccessUnavailable, IdentityAssertion, IDENTITY_PROVIDER_CONTRACT

IDENTITY_ISSUER = "r3a-steward"
PASSWORD_SCHEME = "scrypt-32768-8-1"
_DUMMY_SALT = bytes.fromhex("4dcf8efac6a15eea86df5fb240c0b4e7")
_LOGIN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@+-]{2,253}$")
_PRINCIPAL_RE = re.compile(r"^steward:[A-Za-z0-9-]+$")


def normalize_login(value: str) -> str:
    if not isinstance(value, str) or not _LOGIN_RE.fullmatch(value.strip()):
        raise ValueError("login_name_invalid")
    return value.strip().casefold()


def password_verifier(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**15, r=8, p=1,
                          dklen=32, maxmem=64 * 1024 * 1024)


def _credential(value: Any, *, enrollment: bool = False) -> str:
    if not isinstance(value, str) or len(value) > 1024 or "\x00" in value:
        raise PermissionError("invalid_credentials")
    if enrollment and (len(value) < 14 or len(value.encode("utf-8")) > 1024):
        raise PermissionError("credential_policy_rejected")
    if not enrollment and (len(value) < 1 or len(value.encode("utf-8")) > 1024):
        raise PermissionError("invalid_credentials")
    return value


class PostgresStewardIdentityRepository:
    """R3A-owned identity rows in AP0; no query to R3 is part of this repository."""

    def __init__(self, dsn: str, connect_timeout_seconds: float = 3):
        if not dsn:
            raise AccessUnavailable("identity_store_unavailable")
        self._dsn, self._timeout = dsn, connect_timeout_seconds

    def _connect(self):
        try:
            import psycopg
            from psycopg.rows import dict_row
            return psycopg.connect(self._dsn, connect_timeout=self._timeout,
                                   row_factory=dict_row)
        except Exception as exc:
            raise AccessUnavailable("identity_store_unavailable") from exc

    def health(self) -> str:
        try:
            with self._connect() as conn:
                conn.execute("SELECT principal_id FROM r3a.steward_accounts LIMIT 0").fetchone()
            return "ready"
        except Exception as exc:
            raise AccessUnavailable("identity_store_unavailable") from exc

    def principal_active(self, principal_id: str) -> bool:
        try:
            with self._connect() as conn:
                row = conn.execute("SELECT state FROM r3a.steward_accounts WHERE principal_id=%s",
                                   (principal_id,)).fetchone()
            return bool(row and row["state"] == "active")
        except Exception as exc:
            raise AccessUnavailable("identity_store_unavailable") from exc

    def set_account_state(self, principal_id: str, state: str, actor: str, reason: str) -> None:
        if (state not in {"disabled", "revoked"} or not actor
                or reason not in {"steward_request", "suspected_compromise", "identity_correction"}):
            raise ValueError("account_state_change_invalid")
        try:
            with self._connect() as conn, conn.transaction():
                conn.execute("SELECT r3a.disable_steward_account(%s,%s,%s,%s)",
                             (principal_id, state, actor, reason))
        except ValueError:
            raise
        except Exception as exc:
            raise AccessUnavailable("identity_store_unavailable") from exc

    def authenticate(self, login_name: str, password: str, *, now: datetime) -> dict[str, Any]:
        normalized = normalize_login(login_name)
        _credential(password)
        try:
            with self._connect() as conn, conn.transaction():
                row = conn.execute(
                    "SELECT principal_id,issuer,state,password_salt,password_verifier,password_scheme,"
                    "failed_attempts,locked_until FROM r3a.steward_accounts WHERE login_name=%s FOR UPDATE",
                    (normalized,)).fetchone()
                salt = bytes(row["password_salt"]) if row and row["password_salt"] else _DUMMY_SALT
                stored = bytes(row["password_verifier"]) if row and row["password_verifier"] else b"\x00" * 32
                candidate = password_verifier(password, salt)
                valid = bool(row and row["state"] == "active"
                             and row["password_scheme"] == PASSWORD_SCHEME
                             and (not row["locked_until"] or row["locked_until"] <= now)
                             and hmac.compare_digest(candidate, stored))
                if not row:
                    return None
                if valid:
                    conn.execute("UPDATE r3a.steward_accounts SET failed_attempts=0,locked_until=NULL,updated_at=%s WHERE principal_id=%s",
                                 (now, row["principal_id"]))
                    return {"principal_id": row["principal_id"], "issuer": row["issuer"]}
                failures = int(row["failed_attempts"]) + 1
                locked_until = now + timedelta(minutes=15) if failures >= 10 else row["locked_until"]
                conn.execute("UPDATE r3a.steward_accounts SET failed_attempts=%s,locked_until=%s,updated_at=%s WHERE principal_id=%s",
                             (failures, locked_until, now, row["principal_id"]))
                return None
        except (ValueError, PermissionError):
            raise
        except Exception as exc:
            raise AccessUnavailable("identity_store_unavailable") from exc

    def associate(self, record: dict[str, Any]) -> dict[str, str]:
        """Record one approved metadata association; the input contains references, never source credentials."""
        required = {"association_id", "principal_id", "login_name", "source_system", "source_subject_id",
                    "source_revision", "active", "verified", "steward_eligible", "approved_by",
                    "approval_reference", "hr_source", "hr_subject_reference", "hr_revision"}
        if not isinstance(record, dict) or set(record) != required:
            raise ValueError("association_record_invalid")
        if any(record[k] is not True for k in ("active", "verified", "steward_eligible")):
            raise ValueError("identity_source_not_eligible")
        for key in ("principal_id", "source_system", "source_subject_id", "source_revision", "approved_by",
                    "approval_reference", "hr_source", "hr_subject_reference", "hr_revision"):
            if not isinstance(record[key], str) or not record[key].strip() or len(record[key]) > 256:
                raise ValueError("association_record_invalid")
        if not _PRINCIPAL_RE.fullmatch(record["principal_id"]):
            raise ValueError("association_record_invalid")
        try:
            association_id = str(uuid.UUID(record["association_id"]))
        except (TypeError, ValueError) as exc:
            raise ValueError("association_record_invalid") from exc
        login = normalize_login(record["login_name"])
        provenance = {k: record[k] for k in ("source_system", "source_subject_id", "source_revision",
                       "active", "verified", "steward_eligible", "approved_by", "approval_reference", "hr_source",
                       "hr_subject_reference", "hr_revision")}
        try:
            with self._connect() as conn, conn.transaction():
                prior = conn.execute("SELECT principal_id,login_name,state,source_system,source_subject_id,source_revision,provenance "
                                     "FROM r3a.steward_accounts WHERE association_id=%s",
                                     (association_id,)).fetchone()
                if prior:
                    if (prior["principal_id"] == record["principal_id"] and prior["login_name"] == login
                            and prior["source_system"] == record["source_system"]
                            and prior["source_subject_id"] == record["source_subject_id"]
                            and prior["source_revision"] == record["source_revision"]
                            and prior["provenance"] == provenance):
                        return {"principal_id": prior["principal_id"], "state": prior["state"], "idempotent": "true"}
                    raise ValueError("association_id_conflict")
                conn.execute(
                    "INSERT INTO r3a.steward_accounts(principal_id,login_name,issuer,state,association_id,source_system,"
                    "source_subject_id,source_revision,provenance,associated_at) VALUES (%s,%s,%s,'pending_enrollment',%s,%s,%s,%s,%s::jsonb,%s)",
                    (record["principal_id"], login, IDENTITY_ISSUER, association_id, record["source_system"],
                     record["source_subject_id"], record["source_revision"], json.dumps(provenance), datetime.now(timezone.utc)))
                self._event(conn, "steward.identity.associated", record["principal_id"], record["approved_by"],
                            {"association_id": association_id, "provenance": provenance})
            return {"principal_id": record["principal_id"], "state": "pending_enrollment", "idempotent": "false"}
        except ValueError:
            raise
        except Exception as exc:
            if "UniqueViolation" in type(exc).__name__:
                raise ValueError("identity_association_conflict") from None
            raise AccessUnavailable("identity_store_unavailable") from exc

    def issue_challenge(self, principal_id: str, actor: str, purpose: str = "initial_enrollment",
                        lifetime_minutes: int = 30) -> str:
        if purpose not in {"initial_enrollment", "credential_recovery"} or not actor or lifetime_minutes < 1 or lifetime_minutes > 60:
            raise ValueError("challenge_request_invalid")
        now = datetime.now(timezone.utc)
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode()).hexdigest()
        try:
            with self._connect() as conn, conn.transaction():
                account = conn.execute("SELECT state FROM r3a.steward_accounts WHERE principal_id=%s",
                                       (principal_id,)).fetchone()
                required_state = "pending_enrollment" if purpose == "initial_enrollment" else "active"
                if not account or account["state"] != required_state:
                    raise ValueError("account_state_not_eligible")
                conn.execute("UPDATE r3a.steward_enrollment_challenges SET consumed_at=%s WHERE principal_id=%s AND consumed_at IS NULL",
                             (now, principal_id))
                conn.execute("INSERT INTO r3a.steward_enrollment_challenges(challenge_digest,principal_id,purpose,created_by,created_at,expires_at) VALUES (%s,%s,%s,%s,%s,%s)",
                             (digest, principal_id, purpose, actor, now, now + timedelta(minutes=lifetime_minutes)))
                self._event(conn, "steward.identity.challenge_issued", principal_id, actor,
                            {"purpose": purpose, "expires_at": (now + timedelta(minutes=lifetime_minutes)).isoformat()})
            return token
        except ValueError:
            raise
        except Exception as exc:
            raise AccessUnavailable("identity_store_unavailable") from exc

    def complete_enrollment(self, challenge: str, login_name: str, password: str) -> dict[str, str]:
        normalized, new_password = normalize_login(login_name), _credential(password, enrollment=True)
        digest = hashlib.sha256(challenge.encode()).hexdigest()
        salt = secrets.token_bytes(16)
        verifier = password_verifier(new_password, salt)
        try:
            with self._connect() as conn, conn.transaction():
                row = conn.execute("SELECT principal_id,issuer FROM r3a.complete_steward_enrollment(%s,%s,%s,%s)",
                                   (digest, normalized, salt, verifier)).fetchone()
                return {"principal_id": row["principal_id"], "issuer": row["issuer"]}
        except (ValueError, PermissionError):
            raise
        except Exception as exc:
            if getattr(exc, "sqlstate", None) == "28000":
                raise PermissionError("enrollment_challenge_invalid") from None
            raise AccessUnavailable("identity_store_unavailable") from exc

    @staticmethod
    def _event(conn, event_type: str, principal_id: str, actor: str, evidence: dict[str, Any]) -> None:
        conn.execute("INSERT INTO r3a.institution_events(event_id,event_type,schema_version,subject_type,subject_id,occurred_at,actor,correlation_id,reason,outcome,implementation_revision,evidence) VALUES (%s,%s,1,'steward_principal',%s,%s,%s,%s,%s,'accepted','ap3-m1',%s::jsonb)",
                     (uuid.uuid4(), event_type, principal_id, datetime.now(timezone.utc), actor, uuid.uuid4(),
                      event_type.replace(".", " "), json.dumps(evidence, sort_keys=True)))


class R3aNativeIdentityProvider:
    """Password adapter for an explicitly associated R3A account; never calls R3."""
    contract_id = IDENTITY_PROVIDER_CONTRACT
    contract_version = "1.0.0"
    provider_id = "r3a.native-identity"
    requires_credentials = True

    def __init__(self, config: dict[str, Any], repository: PostgresStewardIdentityRepository):
        self.config, self.repository = config, repository
        self._kdf_slots = threading.BoundedSemaphore(4)

    def health(self) -> str:
        return self.repository.health()

    def principal_active(self, principal_id: str) -> bool:
        return self.repository.principal_active(principal_id)

    def authenticate(self, request, *, correlation_id: str) -> IdentityAssertion:
        if not self._kdf_slots.acquire(timeout=0.1):
            raise AccessUnavailable("identity_provider_busy")
        try:
            return self._authenticate_request(request)
        finally:
            self._kdf_slots.release()

    def _authenticate_request(self, request) -> IdentityAssertion:
        payload = getattr(request.state, "r3a_identity_payload", None)
        if not isinstance(payload, dict):
            raise PermissionError("invalid_credentials")
        if payload.get("intent") in {"enroll", "recover"}:
            challenge = payload.get("challenge")
            if not isinstance(challenge, str) or not 32 <= len(challenge) <= 128:
                raise PermissionError("enrollment_challenge_invalid")
            try:
                identity = self.repository.complete_enrollment(challenge, payload.get("login_name"),
                                                               payload.get("password"))
            except ValueError:
                raise PermissionError("invalid_credentials") from None
            factors = ("password", "governed-enrollment")
        else:
            if payload.get("intent") not in {None, "login"}:
                raise PermissionError("invalid_credentials")
            try:
                identity = self.repository.authenticate(payload.get("login_name"), payload.get("password"),
                                                        now=datetime.now(timezone.utc))
            except ValueError:
                identity = None
            if not identity:
                raise PermissionError("invalid_credentials")
            factors = ("password",)
        return IdentityAssertion(identity["issuer"], identity["principal_id"], str(uuid.uuid4()),
                                 int(time.time()), datetime.now(timezone.utc), factors,
                                 {"identity_provider_id": self.provider_id,
                                  "identity_provider_contract_id": self.contract_id,
                                  "identity_provider_contract_version": self.contract_version,
                                  "credential_scheme": PASSWORD_SCHEME})
