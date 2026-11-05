# R3 CONTROLLED SOURCE
# File: runtime/resident_identity.py
# Component: R3-RESIDENT-SERVICE-IDENTITY
# File Revision: 1.0.0
# Created: 2026-11-04 UTC (date precision only)
# Created By: ChatGPT GPT-6
# Purpose: Authenticate independently provisioned R3 resident service credentials.
# Execution Model: Read-only verifier against the one R3 canonical authority database.
# Observability: Caller logs outcome, never credential value; management issues/revokes in canonical audit.
# Dependencies: Python stdlib, runtime/capability_authority.py, no R2.
# Authority: Steward R3 integration, Website #16 and Grace #28 shared contract.
# Changed: 2026-11-04 UTC | R3-GRACE-ID-002 | Add fail-closed resident credential verifier.
# Supersedes: None
# Contracts: docs/r3-native-tool-contract.md
# Tests: tests/test_resident_identity.py
# History/Predecessor: New module; no credentials shipped with source.
"""Independent R3 resident credentials; browser cookies are never resident tokens."""
from __future__ import annotations
import hashlib
import hmac
import re
import sqlite3
import time

from runtime.capability_authority import R3Authority
from runtime.capabilities import AuthorityUnavailable, CapabilityDenied

ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
SECRET_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
PREFIX = "r3resident_v1"


def digest_secret(credential_id: str, token: str) -> str:
    return hashlib.sha256(
        ("R3ResidentCredential|" + credential_id + "|" + token).encode("utf-8")
    ).hexdigest()


class R3ResidentIdentity:
    def __init__(self, authority: R3Authority):
        if not isinstance(authority, R3Authority):
            raise AuthorityUnavailable("R3 canonical authority required")
        self.authority = authority

    def authenticate(self, token: str) -> str:
        if not isinstance(token, str) or len(token) > 200:
            raise CapabilityDenied("Invalid R3 resident credential")
        parts = token.split(".")
        if (len(parts) != 3 or parts[0] != PREFIX
                or not ID_PATTERN.fullmatch(parts[1])
                or not SECRET_PATTERN.fullmatch(parts[2])):
            raise CapabilityDenied("Invalid R3 resident credential")
        credential_id = parts[1]
        try:
            with self.authority._connect() as db:
                row = db.execute("""SELECT principal,secret_hash,expires_at,revoked_at
                    FROM resident_credentials WHERE credential_id=?""",
                    (credential_id,)).fetchone()
        except sqlite3.Error as exc:
            raise AuthorityUnavailable("R3 resident credential store unavailable") from exc
        if row is None or row[3] is not None or row[2] <= time.time():
            raise CapabilityDenied("R3 resident credential inactive or unknown")
        if not hmac.compare_digest(row[1], digest_secret(credential_id, token)):
            raise CapabilityDenied("R3 resident credential mismatch")
        principal = row[0]
        if not isinstance(principal, str) or not re.fullmatch(r"resident:[A-Za-z0-9_.:-]+", principal):
            raise CapabilityDenied("Invalid R3 resident principal")
        return principal
