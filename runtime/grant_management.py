# R3 CONTROLLED SOURCE
# File: runtime/grant_management.py
# Component: R3-CANONICAL-GRANT-MANAGEMENT
# File Revision: 1.1.2
# Created: 2026-11-04 UTC (date precision only)
# Created By: ChatGPT GPT-6
# Purpose: Typed request/approval/revoke/delegation service against ONE R3 authority database.
# Execution Model: Synchronous SQLite transactions; invoked only behind authenticated Website/Resident API.
# Observability: Atomic append-only capability_management_audit; stable request/grant IDs.
# Dependencies: Python stdlib; runtime/capability_authority.py.
# Authority: Steward directive, Website #16 and Grace #28 agreed shared authority contract.
# Changed: 2026-11-04 UTC | R3-GRACE-AUTH-012 | Add fail-closed management service, no default grants.
# Changed: 2026-11-04 UTC | R3-GRACE-AUTH-014 | Harden idempotency and expiry, retain delegation reason.
# Changed: 2026-11-04 UTC | R3-GRACE-ID-004 | Add Steward-issued and revoked resident credentials.
# Changed: 2026-11-04 UTC | R3-GRACE-RECOVERY-001 | Reject stale or revoked idempotent delegation retries.
# Changed: 2026-11-04 UTC | R3-GRACE-RECOVERY-003 | Revalidate delegation ancestor chain on idempotent retry.
# Supersedes: None
# Contracts: docs/r3-native-tool-contract.md; #16 comment 6632391220.
# Tests: tests/test_grant_management.py
# History/Predecessor: New module; no R2 application dependency.
"""R3 canonical authority management. Website authenticates humans and exposes API.

The Website's trusted session verifier must be injected; no user-supplied
principal or HTTP header is accepted as authority. This service has NO routes
and never creates default grants on startup.
"""
from __future__ import annotations

import json
import math
import secrets
import sqlite3
import time
import uuid
from typing import Callable

from runtime.capability_authority import R3Authority
from runtime.capabilities import AuthorityUnavailable, CapabilityDenied
from runtime.resident_identity import PREFIX, digest_secret


def _required(value: str, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 1024:
        raise ValueError(label + " required")
    return value


def _expiry(effective_at, expires_at):
    now = time.time()
    if effective_at is not None and (
            not isinstance(effective_at, (int, float)) or isinstance(effective_at, bool) or not math.isfinite(effective_at)):
        raise ValueError("Invalid effective timestamp")
    if expires_at is not None and (
            not isinstance(expires_at, (int, float)) or isinstance(expires_at, bool) or not math.isfinite(expires_at)):
        raise ValueError("Invalid expiry timestamp")
    if expires_at is not None and expires_at <= (effective_at or now):
        raise ValueError("Grant expiry must be future and after effective time")


def _audit(db, *, actor, event, request_id=None, grant_id=None, detail=None):
    db.execute("""INSERT INTO capability_management_audit
                  (at,actor,event,request_id,grant_id,detail)
                  VALUES (?,?,?,?,?,?)""",
               (time.time(), actor, event, request_id, grant_id,
                json.dumps(detail or {}, sort_keys=True)))


def _as_dict(cursor):
    names = [entry[0] for entry in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


class R3GrantManagement:
    """Mutation service with a separately injected authenticating Steward verifier.

    `authenticate_steward(opaque_context)` must validate an R3-owned human
    session, CSRF and Origin at the Website request boundary before mutation.
    `authenticate_delegator(opaque_credential)` is an OPTIONAL independent
    resident-credential verifier; no browser session is a resident token.
    """

    def __init__(self, authority: R3Authority,
                 authenticate_steward: Callable[[object], str],
                 authenticate_delegator: Callable[[object], str] | None = None):
        if not isinstance(authority, R3Authority) or not callable(authenticate_steward):
            raise AuthorityUnavailable("Canonical authority and trusted Steward verifier required")
        self.authority = authority
        self.authenticate_steward = authenticate_steward
        self.authenticate_delegator = authenticate_delegator

    def _steward(self, context: object) -> str:
        principal = self.authenticate_steward(context)
        if (not isinstance(principal, str)
                or not principal.startswith("human:steward:")
                or principal == "human:steward:"):
            raise CapabilityDenied("R3 Steward authentication required")
        return principal

    def _resident_delegator(self, credential: object) -> str:
        if self.authenticate_delegator is None:
            raise CapabilityDenied("Delegation identity verifier not configured")
        principal = self.authenticate_delegator(credential)
        if (not isinstance(principal, str)
                or not principal.startswith("resident:")
                or principal == "resident:"):
            raise CapabilityDenied("Independent resident delegation identity required")
        return principal

    def request(self, *, steward_context: object, target_principal: str,
                resource_ref: str, action: str, operation: str, scope_ref: str,
                reason: str, idempotency_key: str,
                effective_at: float | None = None,
                expires_at: float | None = None,
                delegable: bool = False) -> dict:
        steward = self._steward(steward_context)
        for label, value in (("target principal", target_principal),
                             ("resource", resource_ref), ("action", action),
                             ("scope", scope_ref), ("reason", reason),
                             ("idempotency key", idempotency_key)):
            _required(value, label)
        if not target_principal.startswith(("resident:", "human:")):
            raise ValueError("Unknown principal namespace")
        if operation not in ("read", "write") or not isinstance(delegable, bool):
            raise ValueError("Invalid read/write operation or delegation flag")
        _expiry(effective_at, expires_at)
        with self.authority._connect() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT * FROM capability_requests WHERE idempotency_key=?",
                    (idempotency_key,)).fetchone()
                if row is not None:
                    # Never mistake a reused key with differing parameters as authorization.
                    fields = (target_principal, resource_ref, action, operation, scope_ref,
                              reason, effective_at, expires_at, int(delegable))
                    if row[1] != steward or tuple(row[i] for i in (2,3,4,5,6,11,8,9,10)) != fields:
                        raise CapabilityDenied("Idempotency key reused with different request")
                    return {"request_id": row[0], "status": row[12]}
                request_id = "r3-request:" + uuid.uuid4().hex
                db.execute("""INSERT INTO capability_requests
                   (request_id,requester,principal,resource_ref,action,operation,scope_ref,
                    requested_at,effective_at,expires_at,delegable,reason,status,idempotency_key)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                   (request_id, steward, target_principal, resource_ref,
                    action, operation, scope_ref, time.time(), effective_at,
                    expires_at, int(delegable), reason, "PENDING", idempotency_key))
                _audit(db, actor=steward, event="REQUESTED",
                       request_id=request_id, detail={"operation": operation,
                       "resource_ref": resource_ref, "target": target_principal})
                return {"request_id": request_id, "status": "PENDING"}
            except sqlite3.Error as exc:
                raise AuthorityUnavailable("R3 grant request persistence unavailable") from exc

    def decide(self, *, steward_context: object, request_id: str,
               approve: bool, reason: str) -> dict:
        steward = self._steward(steward_context)
        _required(request_id, "request ID")
        _required(reason, "decision reason")
        if not isinstance(approve, bool):
            raise ValueError("Approval decision must be boolean")
        with self.authority._connect() as db:
            try:
                db.row_factory = sqlite3.Row
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT * FROM capability_requests WHERE request_id=?",
                    (request_id,)).fetchone()
                if row is None:
                    raise CapabilityDenied("Unknown grant request")
                target_state = "APPROVED" if approve else "REJECTED"
                if row["status"] != "PENDING":
                    if row["status"] == target_state:
                        return {"request_id": request_id, "status": target_state,
                                "grant_id": row["grant_id"]}
                    raise CapabilityDenied("Request already decided differently")
                grant_id = None
                if approve:
                    # Never create overlapping active exact grants that could be ambiguous.
                    active = db.execute("""SELECT grant_id FROM capability_grants
                        WHERE principal=? AND resource_ref=? AND action=?
                          AND operation=? AND scope_ref=? AND active=1
                          AND revoked_at IS NULL""",
                        (row["principal"], row["resource_ref"], row["action"],
                         row["operation"], row["scope_ref"])).fetchone()
                    if active is not None:
                        raise CapabilityDenied("Active exact grant already exists")
                    grant_id = "r3-grant:" + uuid.uuid4().hex
                    db.execute("""INSERT INTO capability_grants
                       (grant_id,principal,resource_ref,action,operation,scope_ref,active,
                        effective_at,expires_at,issued_by,approved_by,parent_grant_id,
                        created_at,revoked_at,reason,delegable)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (grant_id, row["principal"], row["resource_ref"], row["action"],
                         row["operation"], row["scope_ref"], 1, row["effective_at"],
                         row["expires_at"], steward, steward, None, time.time(),
                         None, reason, row["delegable"]))
                db.execute("""UPDATE capability_requests
                    SET status=?,decided_by=?,decision_at=?,grant_id=?
                    WHERE request_id=?""",
                    (target_state, steward, time.time(), grant_id, request_id))
                _audit(db, actor=steward, event=target_state,
                       request_id=request_id, grant_id=grant_id,
                       detail={"reason": reason})
                return {"request_id": request_id, "status": target_state,
                        "grant_id": grant_id}
            except sqlite3.Error as exc:
                raise AuthorityUnavailable("R3 grant decision persistence unavailable") from exc

    def revoke(self, *, steward_context: object, grant_id: str,
               reason: str) -> dict:
        steward = self._steward(steward_context)
        _required(grant_id, "grant ID")
        _required(reason, "revocation reason")
        with self.authority._connect() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                old = db.execute("SELECT active FROM capability_grants WHERE grant_id=?",
                                 (grant_id,)).fetchone()
                if old is None:
                    raise CapabilityDenied("Unknown grant")
                if old[0] != 1:
                    return {"grant_id": grant_id, "status": "REVOKED"}
                db.execute("""UPDATE capability_grants
                    SET active=0,revoked_at=?,reason=? WHERE grant_id=?""",
                           (time.time(), reason, grant_id))
                _audit(db, actor=steward, event="REVOKED",
                       grant_id=grant_id, detail={"reason": reason})
                return {"grant_id": grant_id, "status": "REVOKED"}
            except sqlite3.Error as exc:
                raise AuthorityUnavailable("R3 revocation persistence unavailable") from exc

    def delegate(self, *, resident_credential: object, parent_grant_id: str,
                 target_principal: str, expires_at: float | None,
                 reason: str, idempotency_key: str) -> dict:
        issuer = self._resident_delegator(resident_credential)
        _required(parent_grant_id, "parent grant")
        _required(target_principal, "target principal")
        _required(reason, "delegation reason")
        _required(idempotency_key, "idempotency key")
        if not target_principal.startswith("resident:"):
            raise CapabilityDenied("Only resident-to-resident delegation supported")
        with self.authority._connect() as db:
            try:
                db.row_factory = sqlite3.Row
                db.execute("BEGIN IMMEDIATE")
                existing = db.execute(
                    """SELECT grant_id,principal,parent_grant_id,expires_at,reason FROM capability_grants
                       WHERE idempotency_key=? AND issued_by=? AND parent_grant_id=?""",
                    (idempotency_key, issuer, parent_grant_id)).fetchone()
                if existing:
                    if (existing["principal"] != target_principal
                            or existing["expires_at"] != expires_at or existing["reason"] != reason):
                        raise CapabilityDenied("Delegation key reused with different target")
                    # Idempotent retries must never turn a revoked/expired
                    # historical delegation into a claim of active authority.
                    now = time.time()
                    active = db.execute("""SELECT active,revoked_at FROM capability_grants
                                           WHERE grant_id=?""",
                                        (existing["grant_id"],)).fetchone()
                    if (not active or active["active"] != 1 or active["revoked_at"] is not None
                            or (existing["expires_at"] is not None and existing["expires_at"] <= now)):
                        raise CapabilityDenied("Delegation is no longer active")
                    # An active-looking child cannot outlive a revoked ancestor.
                    # Consult the canonical verifier's exact chain check before
                    # answering an idempotent request as ACTIVE.
                    delegated = db.execute(
                        "SELECT * FROM capability_grants WHERE grant_id=?",
                        (existing["grant_id"],)).fetchone()
                    self.authority._verify_parent_chain(db, delegated, now)
                    return {"grant_id": existing["grant_id"], "status": "ACTIVE"}
                parent = db.execute(
                    "SELECT * FROM capability_grants WHERE grant_id=?", (parent_grant_id,)).fetchone()
                now = time.time()
                if (not parent or parent["principal"] != issuer or parent["delegable"] != 1
                    or parent["active"] != 1 or parent["revoked_at"] is not None
                    or (parent["expires_at"] is not None and parent["expires_at"] <= now)
                    or (parent["effective_at"] is not None and parent["effective_at"] > now)
                    or not isinstance(parent["approved_by"], str)
                    or not parent["approved_by"].startswith("human:steward:")):
                    raise CapabilityDenied("Delegation parent not effective, owned or delegable")
                if (expires_at is not None and (
                        not isinstance(expires_at, (int, float)) or expires_at <= now)):
                    raise CapabilityDenied("Invalid delegated expiry")
                if parent["expires_at"] is not None and (
                        expires_at is None or expires_at > parent["expires_at"]):
                    raise CapabilityDenied("Delegated expiry exceeds parent")
                for column in ("resource_ref", "action", "operation", "scope_ref"):
                    if not parent[column]:
                        raise CapabilityDenied("Untyped legacy grant cannot delegate")
                duplicate = db.execute("""SELECT grant_id FROM capability_grants
                    WHERE principal=? AND resource_ref=? AND action=? AND operation=?
                      AND scope_ref=? AND active=1 AND revoked_at IS NULL""",
                    (target_principal, parent["resource_ref"], parent["action"],
                     parent["operation"], parent["scope_ref"])).fetchone()
                if duplicate:
                    raise CapabilityDenied("Exact grantee already has effective grant")
                grant_id = "r3-grant:" + uuid.uuid4().hex
                db.execute("""INSERT INTO capability_grants
                    (grant_id,principal,resource_ref,action,operation,scope_ref,active,
                     effective_at,expires_at,issued_by,approved_by,parent_grant_id,
                     created_at,revoked_at,reason,delegable,idempotency_key)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (grant_id, target_principal, parent["resource_ref"], parent["action"],
                     parent["operation"], parent["scope_ref"], 1,
                     parent["effective_at"], expires_at, issuer, parent["approved_by"],
                     parent_grant_id, now, None, reason, 0, idempotency_key))
                _audit(db, actor=issuer, event="DELEGATED", grant_id=grant_id,
                       detail={"parent_grant_id": parent_grant_id,
                               "target_principal": target_principal, "reason": reason})
                return {"grant_id": grant_id, "status": "ACTIVE"}
            except sqlite3.Error as exc:
                raise AuthorityUnavailable("R3 delegation persistence unavailable") from exc

    def issue_resident_credential(self, *, steward_context: object,
                                  resident_principal: str, expires_at: float,
                                  reason: str, idempotency_key: str) -> dict:
        """Issue one high-entropy resident credential; token returned ONCE, never logged."""
        steward = self._steward(steward_context)
        _required(resident_principal, "resident principal")
        _required(reason, "credential issuance reason")
        _required(idempotency_key, "idempotency key")
        if (not resident_principal.startswith("resident:")
                or resident_principal == "resident:"):
            raise CapabilityDenied("Only independent resident identities may be provisioned")
        _expiry(None, expires_at)
        if expires_at is None:
            raise ValueError("Resident credential must expire")
        with self.authority._connect() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                existing = db.execute(
                    """SELECT credential_id,principal,expires_at
                       FROM resident_credentials WHERE idempotency_key=?""",
                    (idempotency_key,)).fetchone()
                if existing is not None:
                    if existing[1] != resident_principal or existing[2] != expires_at:
                        raise CapabilityDenied("Credential key reused with different intent")
                    return {"credential_id": existing[0], "status": "ALREADY_ISSUED"}
                credential_id = uuid.uuid4().hex
                token = PREFIX + "." + credential_id + "." + secrets.token_urlsafe(32)
                db.execute("""INSERT INTO resident_credentials
                    (credential_id,principal,secret_hash,created_at,
                     expires_at,revoked_at,issued_by,idempotency_key)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (credential_id, resident_principal,
                     digest_secret(credential_id, token),
                     time.time(), expires_at, None, steward, idempotency_key))
                _audit(db, actor=steward, event="RESIDENT_CREDENTIAL_ISSUED",
                       detail={"credential_id": credential_id,
                               "principal": resident_principal, "reason": reason})
                return {"credential_id": credential_id, "credential": token,
                        "status": "ISSUED"}
            except sqlite3.Error as exc:
                raise AuthorityUnavailable("R3 resident credential issuance unavailable") from exc

    def revoke_resident_credential(self, *, steward_context: object,
                                   credential_id: str, reason: str) -> dict:
        steward = self._steward(steward_context)
        _required(credential_id, "credential ID")
        _required(reason, "revocation reason")
        with self.authority._connect() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT revoked_at FROM resident_credentials WHERE credential_id=?",
                    (credential_id,)).fetchone()
                if row is None:
                    raise CapabilityDenied("Resident credential not found")
                if row[0] is None:
                    db.execute(
                        "UPDATE resident_credentials SET revoked_at=? WHERE credential_id=?",
                        (time.time(), credential_id))
                    _audit(db, actor=steward, event="RESIDENT_CREDENTIAL_REVOKED",
                           detail={"credential_id": credential_id, "reason": reason})
                return {"credential_id": credential_id, "status": "REVOKED"}
            except sqlite3.Error as exc:
                raise AuthorityUnavailable("R3 credential revocation unavailable") from exc

    def list_grants(self, *, steward_context: object, active_only: bool = False) -> list[dict]:
        self._steward(steward_context)
        with self.authority._connect() as db:
            sql = "SELECT * FROM capability_grants"
            if active_only:
                sql += """ WHERE active=1 AND revoked_at IS NULL
                    AND (effective_at IS NULL OR effective_at <= ?)
                    AND (expires_at IS NULL OR expires_at > ?)"""
                now = time.time()
                return _as_dict(db.execute(
                    sql + " ORDER BY created_at DESC, grant_id", (now, now)))
            return _as_dict(db.execute(sql + " ORDER BY created_at DESC, grant_id"))

    def list_requests(self, *, steward_context: object,
                      status: str | None = None) -> list[dict]:
        self._steward(steward_context)
        with self.authority._connect() as db:
            if status is not None:
                return _as_dict(db.execute(
                    "SELECT * FROM capability_requests WHERE status=? ORDER BY requested_at DESC",
                    (status,)))
            return _as_dict(db.execute(
                "SELECT * FROM capability_requests ORDER BY requested_at DESC"))

    def history(self, *, steward_context: object) -> list[dict]:
        self._steward(steward_context)
        with self.authority._connect() as db:
            return _as_dict(db.execute(
                "SELECT * FROM capability_management_audit ORDER BY id"))
