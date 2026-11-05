# R3 CONTROLLED SOURCE
# File: r3_native_sessions.py
# Component: R3-NATIVE-STEWARD-AUTH
# File Revision: 1.0.0
# Created: 2026-11-04 UTC | ChatGPT GPT-6
# Purpose: Independent R3 human authentication and sessions.
# Authority: Steward; Website Development issue #16.
# Supersedes: None
# Tests: tests/test_r3_native_sessions.py

"""R3-owned human sessions. Never authorizes resident execution."""

import hashlib
import hmac
import secrets
import sqlite3
import time
from pathlib import Path


class AuthenticationDenied(Exception):
    pass


class NativeSessions:
    def __init__(self, database):
        self.database = str(database)
        if not Path(database).is_file():
            raise AuthenticationDenied("R3 session database unavailable")
        with self._connect() as db:
            db.execute("SELECT id FROM accounts LIMIT 0")
            db.execute("SELECT token_hash FROM sessions LIMIT 0")

    def _connect(self):
        return sqlite3.connect(
            "file:" + str(Path(self.database).resolve()) + "?mode=rw",
            uri=True,
            timeout=5,
        )

    @staticmethod
    def _hash_password(password, salt):
        return hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt),
            n=16384,
            r=8,
            p=1,
            dklen=32,
        ).hex()

    @staticmethod
    def _token_hash(token):
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_password(password):
        if not isinstance(password, str) or len(password) < 12:
            raise ValueError("Password must contain at least 12 characters")
        if len(password.encode("utf-8")) > 1024:
            raise ValueError("Password too long")

    def bootstrap_steward(self, email, password):
        """Explicit first-account provisioning; never runs automatically."""
        self._validate_password(password)
        if not isinstance(email, str) or "@" not in email:
            raise ValueError("Invalid email")

        email = email.strip().lower()
        salt = secrets.token_hex(16)
        digest = self._hash_password(password, salt)

        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]:
                raise AuthenticationDenied("Bootstrap already completed")
            db.execute(
                """INSERT INTO accounts
                   (id,email,salt,password_hash,role,enabled)
                   VALUES (?,?,?,?,?,1)""",
                (secrets.token_hex(16), email, salt, digest, "steward"),
            )

    def login(self, email, password, lifetime=28800):
        if not isinstance(email, str) or not isinstance(password, str):
            raise AuthenticationDenied("Invalid credentials")

        if not 0 < lifetime <= 86400:
            raise ValueError("Invalid session lifetime")

        with self._connect() as db:
            row = db.execute(
                """SELECT id,salt,password_hash,enabled,role
                   FROM accounts WHERE email=?""",
                (email.strip().lower(),),
            ).fetchone()

            if row is None:
                raise AuthenticationDenied("Invalid credentials")

            account_id, salt, expected, enabled, role = row
            actual = self._hash_password(password, salt)

            if not enabled or not hmac.compare_digest(actual, expected):
                raise AuthenticationDenied("Invalid credentials")

            token = secrets.token_urlsafe(48)
            csrf = secrets.token_urlsafe(32)

            db.execute(
                """INSERT INTO sessions
                   (token_hash,account_id,csrf_hash,expires_at,revoked)
                   VALUES (?,?,?,?,0)""",
                (
                    self._token_hash(token),
                    account_id,
                    self._token_hash(csrf),
                    time.time() + lifetime,
                ),
            )

            return {
                "token": token,
                "csrf": csrf,
                "role": role,
                "expires_in": lifetime,
            }

    def authenticate(self, token, csrf=None, mutation=False):
        if not isinstance(token, str) or not token:
            raise AuthenticationDenied("Missing session")

        with self._connect() as db:
            row = db.execute(
                """SELECT a.id,a.email,a.role,a.enabled,
                          s.csrf_hash,s.expires_at,s.revoked
                   FROM sessions s
                   JOIN accounts a ON a.id=s.account_id
                   WHERE s.token_hash=?""",
                (self._token_hash(token),),
            ).fetchone()

        if row is None:
            raise AuthenticationDenied("Invalid session")

        account_id, email, role, enabled, csrf_hash, expiry, revoked = row

        if not enabled or revoked or expiry <= time.time():
            raise AuthenticationDenied("Session expired or revoked")

        if mutation:
            if not isinstance(csrf, str) or not hmac.compare_digest(
                self._token_hash(csrf), csrf_hash
            ):
                raise AuthenticationDenied("Invalid CSRF token")

        return {
            "principal": "human:steward:" + account_id,
            "email": email,
            "role": role,
        }

    def logout(self, token):
        if not isinstance(token, str) or not token:
            raise AuthenticationDenied("Missing session")

        with self._connect() as db:
            db.execute(
                "UPDATE sessions SET revoked=1 WHERE token_hash=?",
                (self._token_hash(token),),
            )


def initialize_empty_schema(database):
    """Create an empty R3 account store. No default users or grants."""
    path = Path(database)
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(path)) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                enabled INTEGER NOT NULL CHECK(enabled IN (0,1))
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                account_id TEXT NOT NULL REFERENCES accounts(id),
                csrf_hash TEXT NOT NULL,
                expires_at REAL NOT NULL,
                revoked INTEGER NOT NULL CHECK(revoked IN (0,1))
            )
        """)
