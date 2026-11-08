"""
R3 CONTROLLED SOURCE
File: r3a_runtime/secrets.py
Component: R3A-SECRETS-API
File Revision: 1.1.1
Created: 2026-11-07T21:36:43Z
Created By: Codex GPT-6
Purpose: Define a versioned secret reference, provider, lease, and machine-principal boundary.
Execution Model: In-process provider API; secret values remain in caller memory only.
Observability: Non-secret provider identity, revision, status, timestamp, and correlation metadata.
Dependencies: Python standard library; AP3-M2 Issue #50.
Authority: R3A AP3-M2; CME retains operation authorization and audit ownership.
Changed: 2026-11-07T21:36:43Z | R3A-AP3-M2-ISSUE-50 | Codex GPT-6 | Define private, versioned secret resolution and machine identity contracts.
Changed: 2026-11-07T22:09:29Z | R3A-AP3-M2-CONSUMER | Codex GPT-6 | Version sanitized reason codes for distinct provider availability/failure outcomes.
Changed: 2026-11-08T13:32:28Z | R3A-AP3-M2-BWS-AUTH-ENV | Codex GPT-6 | Publish Bitwarden provider patch release 1.1.1 for CLI auth environment binding.
Supersedes: None.
Contracts: r3a.secrets.provider.v1; r3a.machine-principal.v1.
Tests: tests/test_r3a_bitwarden_secrets.py.
History/Predecessor: Revision 1.0.0 at commit d07bade6dfa6e6ef498f454d82866aa592b899ba, blob e327f90f402faf70dd513bd71147ef2b78719944.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


SECRET_PROVIDER_CONTRACT_ID = "r3a.secrets.provider.v1"
MACHINE_PRINCIPAL_CONTRACT_ID = "r3a.machine-principal.v1"
SECRET_PROVIDER_CONTRACT_VERSION = "1.1.0"
MACHINE_PRINCIPAL_CONTRACT_VERSION = "1.0.0"
BITWARDEN_PROVIDER_ID = "r3a.bitwarden-secrets"
BITWARDEN_PROVIDER_VERSION = "1.1.1"
_ENVIRONMENT_VARIABLE = re.compile(r"[A-Z][A-Z0-9_]*")
_SECRET_ERROR_REASONS = frozenset({
    "provider_unavailable", "credentials_unavailable", "cli_unavailable", "request_timeout",
    "provider_start_failed", "access_denied", "reference_not_found", "provider_failure",
    "invalid_reference", "invalid_request", "response_invalid", "response_mismatch",
})


class SecretProviderError(RuntimeError):
    """A redacted secret outcome and stable reason code safe for status and diagnostics."""

    def __init__(self, outcome: str, message: str, *, reason_code: str | None = None):
        if outcome not in {"UNAVAILABLE", "DENIED", "NOT_FOUND", "FAILED"}:
            raise ValueError("unsupported secret provider outcome")
        self.outcome = outcome
        default_reason = {
            "UNAVAILABLE": "provider_unavailable",
            "DENIED": "access_denied",
            "NOT_FOUND": "reference_not_found",
            "FAILED": "provider_failure",
        }[outcome]
        if reason_code is not None and reason_code not in _SECRET_ERROR_REASONS:
            raise ValueError("secret provider reason code is invalid")
        self.reason_code = reason_code or default_reason
        super().__init__(message)


@dataclass(frozen=True)
class SecretReference:
    """Non-secret reference to one Bitwarden secret under a provider contract."""

    provider_id: str
    provider_version: str
    secret_id: str
    contract_id: str = SECRET_PROVIDER_CONTRACT_ID
    contract_version: str = SECRET_PROVIDER_CONTRACT_VERSION


@dataclass(frozen=True)
class MachinePrincipalAssertion:
    """Configured machine-principal metadata associated with an accepted fetch."""

    principal_id: str
    issuer: str
    authenticated_at: str
    correlation_id: str
    contract_id: str = MACHINE_PRINCIPAL_CONTRACT_ID
    contract_version: str = MACHINE_PRINCIPAL_CONTRACT_VERSION


@dataclass(repr=False)
class SecretLease:
    """Short-lived in-process value holder; closing overwrites its mutable buffer."""

    secret_id: str
    provider_id: str
    provider_version: str
    remote_revision: str | None
    fetched_at: str
    machine_principal: MachinePrincipalAssertion
    _value: bytearray = field(repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    def __repr__(self) -> str:
        return (f"SecretLease(secret_id={self.secret_id!r}, provider_id={self.provider_id!r}, "
                f"provider_version={self.provider_version!r}, remote_revision={self.remote_revision!r}, "
                f"fetched_at={self.fetched_at!r}, closed={self._closed})")

    @property
    def closed(self) -> bool:
        return self._closed

    def reveal(self) -> str:
        """Reveal only to the direct credential consumer; callers must close the lease."""
        if self._closed:
            raise SecretProviderError("FAILED", "secret lease is closed")
        return self._value.decode("utf-8")

    def close(self) -> None:
        """Overwrite the lease buffer and make future reveal attempts fail."""
        for index in range(len(self._value)):
            self._value[index] = 0
        self._closed = True

    def __enter__(self) -> "SecretLease":
        if self._closed:
            raise SecretProviderError("FAILED", "secret lease is closed")
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()


@runtime_checkable
class SecretProvider(Protocol):
    """Private adapter contract; implementations are deliberately not CME capabilities."""

    provider_id: str
    provider_version: str

    def resolve(self, reference: SecretReference, *, correlation_id: str) -> SecretLease:
        """Fetch current value and return a closeable, non-serializable in-process lease."""


def validate_provider_configuration(value: Any) -> dict[str, Any]:
    """Validate external provider settings, which contain references but no credential values."""
    if not isinstance(value, dict):
        raise ValueError("Bitwarden provider configuration must be an object")
    required = {"provider_id", "provider_version", "executable", "access_token_env",
                "machine_principal_id", "timeout_seconds"}
    optional = {"config_file", "profile"}
    if required - value.keys() or value.keys() - required - optional:
        raise ValueError("Bitwarden provider configuration fields are invalid")
    for name in ("provider_id", "provider_version", "executable", "machine_principal_id"):
        if not isinstance(value[name], str) or not value[name].strip():
            raise ValueError(f"Bitwarden provider configuration {name} is invalid")
    if (value["provider_id"], value["provider_version"]) != (
            BITWARDEN_PROVIDER_ID, BITWARDEN_PROVIDER_VERSION):
        raise ValueError("Bitwarden provider identity or version is unsupported")
    if not isinstance(value["access_token_env"], str) or not _ENVIRONMENT_VARIABLE.fullmatch(value["access_token_env"]):
        raise ValueError("Bitwarden access_token_env must name an uppercase environment variable")
    timeout = value["timeout_seconds"]
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 1 <= timeout <= 120:
        raise ValueError("Bitwarden timeout_seconds must be between 1 and 120 seconds")
    for name in ("config_file", "profile"):
        if name in value and (not isinstance(value[name], str) or not value[name].strip()):
            raise ValueError(f"Bitwarden provider configuration {name} is invalid")
    if "config_file" in value and not Path(value["config_file"]).is_absolute():
        raise ValueError("Bitwarden config_file must be an absolute path")
    return dict(value)


def load_provider_configuration(path: str | Path) -> dict[str, Any]:
    """Read and validate the provider's external JSON configuration without secret values."""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise ValueError("Bitwarden provider configuration is unavailable or invalid") from None
    return validate_provider_configuration(value)
