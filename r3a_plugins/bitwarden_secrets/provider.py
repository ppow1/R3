"""
R3 CONTROLLED SOURCE
File: r3a_plugins/bitwarden_secrets/provider.py
Component: R3A-PLUG-BITWARDEN
File Revision: 1.1.2
Created: 2026-11-07T21:36:43Z
Created By: Codex GPT-6
Purpose: Resolve versioned secret references through the Bitwarden Secrets Manager CLI.
Execution Model: Synchronous external CLI adapter using a machine-account access token from process environment.
Observability: Redacted status, correlation ID, provider identity, and remote revision only.
Dependencies: r3a_runtime.secrets; externally installed/configured Bitwarden `bws` CLI.
Authority: AP3-M2 Issue #50; returned values are private adapter data, never CME capabilities or model context.
Changed: 2026-11-07T21:36:43Z | R3A-AP3-M2-ISSUE-50 | Codex GPT-6 | Implement configurable Bitwarden machine-account secret resolution.
Changed: 2026-11-07T22:09:29Z | R3A-AP3-M2-CONSUMER | Codex GPT-6 | Return distinct non-secret reason codes for credential, CLI, timeout, and provider failures.
Changed: 2026-11-08T13:32:28Z | R3A-AP3-M2-BWS-AUTH-ENV | Codex GPT-6 | Map configured credential source into Bitwarden CLI BWS_ACCESS_TOKEN without argv exposure.
Changed: 2026-11-08T13:35:27Z | R3A-AP3-M2-LIFECYCLE | Codex GPT-6 | Expose non-secret runtime readiness for provider lifecycle activation.
Changed: 2026-11-08T14:15:00Z | R3A-AP3-M2-PROVIDER-ACTIVATION | Codex GPT-6 | Publish readiness probe as provider patch 1.1.2.
Supersedes: None.
Contracts: r3a.secrets.provider.v1; r3a.machine-principal.v1.
Tests: tests/test_r3a_bitwarden_secrets.py.
History/Predecessor: Revision 1.0.0 at commit d07bade6dfa6e6ef498f454d82866aa592b899ba, blob 3f7ce8d489869bb28c58bffdd2263716441e78ce.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from r3a_runtime.secrets import (
    BITWARDEN_PROVIDER_ID,
    BITWARDEN_PROVIDER_VERSION,
    MACHINE_PRINCIPAL_CONTRACT_ID,
    MACHINE_PRINCIPAL_CONTRACT_VERSION,
    SECRET_PROVIDER_CONTRACT_ID,
    SECRET_PROVIDER_CONTRACT_VERSION,
    MachinePrincipalAssertion,
    SecretLease,
    SecretProviderError,
    SecretReference,
    load_provider_configuration,
    validate_provider_configuration,
)


class BitwardenSecretsProvider:
    """Retrieve one current Bitwarden secret without exposing CLI diagnostics."""

    def __init__(self, configuration: dict[str, Any], *, run: Any = subprocess.run,
                 environment: Any = os.environ, executable_lookup: Any = shutil.which):
        self.configuration = dict(configuration)
        self.provider_id = self.configuration["provider_id"]
        self.provider_version = self.configuration["provider_version"]
        self.access_token_env = self.configuration["access_token_env"]
        self._run = run
        self._environment = environment
        self._executable_lookup = executable_lookup

    def assert_available(self) -> None:
        """Check activation prerequisites without resolving or returning a secret."""
        token = self._environment.get(self.access_token_env)
        if not isinstance(token, str) or not token:
            raise SecretProviderError("UNAVAILABLE", "Bitwarden machine-account credential is unavailable",
                                      reason_code="credentials_unavailable")
        if not self._executable_lookup(self.configuration["executable"]):
            raise SecretProviderError("UNAVAILABLE", "Bitwarden Secrets Manager CLI is unavailable",
                                      reason_code="cli_unavailable")

    def resolve(self, reference: SecretReference, *, correlation_id: str) -> SecretLease:
        if (reference.contract_id != SECRET_PROVIDER_CONTRACT_ID
                or reference.contract_version != SECRET_PROVIDER_CONTRACT_VERSION
                or reference.provider_id != self.provider_id
                or reference.provider_version != self.provider_version
                or not isinstance(reference.secret_id, str) or not reference.secret_id.strip()):
            raise SecretProviderError("FAILED", "secret reference does not match the configured provider contract",
                                      reason_code="invalid_reference")
        if not isinstance(correlation_id, str) or not correlation_id.strip():
            raise SecretProviderError("FAILED", "secret resolution requires a correlation identifier",
                                      reason_code="invalid_request")

        token_variable = self.access_token_env
        token = self._environment.get(token_variable)
        if not isinstance(token, str) or not token:
            raise SecretProviderError("UNAVAILABLE", "Bitwarden machine-account credential is unavailable",
                                      reason_code="credentials_unavailable")

        executable = self.configuration["executable"]
        if not self._executable_lookup(executable):
            raise SecretProviderError("UNAVAILABLE", "Bitwarden Secrets Manager CLI is unavailable",
                                      reason_code="cli_unavailable")

        command = [executable, "secret", "get", reference.secret_id, "--output", "json", "--color", "no"]
        if "config_file" in self.configuration:
            command.extend(["--config-file", self.configuration["config_file"]])
        if "profile" in self.configuration:
            command.extend(["--profile", self.configuration["profile"]])
        environment = dict(self._environment)
        if token_variable != "BWS_ACCESS_TOKEN":
            environment.pop(token_variable, None)
        environment["BWS_ACCESS_TOKEN"] = token
        try:
            result = self._run(command, check=False, capture_output=True, text=True,
                               timeout=float(self.configuration["timeout_seconds"]), env=environment)
        except FileNotFoundError:
            raise SecretProviderError("UNAVAILABLE", "Bitwarden Secrets Manager CLI is unavailable",
                                      reason_code="cli_unavailable") from None
        except subprocess.TimeoutExpired:
            raise SecretProviderError("UNAVAILABLE", "Bitwarden secret request timed out",
                                      reason_code="request_timeout") from None
        except OSError:
            raise SecretProviderError("FAILED", "Bitwarden secret request could not be started",
                                      reason_code="provider_start_failed") from None

        if result.returncode != 0:
            diagnostic = (result.stderr or "").lower()
            if any(term in diagnostic for term in ("unauthorized", "unauthenticated", "forbidden",
                                                    "permission denied", "not authorized", "access denied",
                                                    "invalid token", "authentication failed")):
                raise SecretProviderError("DENIED", "Bitwarden denied machine-account access to the secret")
            if any(term in diagnostic for term in ("not found", "does not exist", "no secret")):
                raise SecretProviderError("NOT_FOUND", "Bitwarden secret reference was not found")
            raise SecretProviderError("FAILED", "Bitwarden secret request failed")

        try:
            payload = json.loads(result.stdout)
        except (TypeError, json.JSONDecodeError):
            raise SecretProviderError("FAILED", "Bitwarden returned an invalid secret response",
                                      reason_code="response_invalid") from None
        if (not isinstance(payload, dict) or payload.get("id") != reference.secret_id
                or not isinstance(payload.get("value"), str)):
            raise SecretProviderError("FAILED", "Bitwarden returned a mismatched or incomplete secret response",
                                      reason_code="response_mismatch")

        principal = MachinePrincipalAssertion(
            principal_id=self.configuration["machine_principal_id"],
            issuer="bitwarden-secrets-manager",
            authenticated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            correlation_id=correlation_id,
            contract_id=MACHINE_PRINCIPAL_CONTRACT_ID,
            contract_version=MACHINE_PRINCIPAL_CONTRACT_VERSION,
        )
        revision = payload.get("revisionDate")
        return SecretLease(
            secret_id=reference.secret_id,
            provider_id=self.provider_id,
            provider_version=self.provider_version,
            remote_revision=revision if isinstance(revision, str) else None,
            fetched_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            machine_principal=principal,
            _value=bytearray(payload["value"].encode("utf-8")),
        )


def create_provider(configuration: dict[str, Any]) -> BitwardenSecretsProvider:
    """Provider factory for external configuration loaders."""
    checked = validate_provider_configuration(configuration)
    if (checked["provider_id"], checked["provider_version"]) != (
            BITWARDEN_PROVIDER_ID, BITWARDEN_PROVIDER_VERSION):
        raise ValueError("Bitwarden provider identity or version is unsupported")
    return BitwardenSecretsProvider(checked)


def load_configured_provider(manifest_path: str | Path,
                             configuration_path: str | Path) -> BitwardenSecretsProvider:
    """Load the externally configured provider through its versioned pinned manifest."""
    manifest_file = Path(manifest_path).resolve()
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise ValueError("Bitwarden provider manifest is unavailable or invalid") from None
    if (not isinstance(manifest, dict)
            or manifest.get("provider_id") != BITWARDEN_PROVIDER_ID
            or manifest.get("provider_version") != BITWARDEN_PROVIDER_VERSION
            or manifest.get("contract_id") != SECRET_PROVIDER_CONTRACT_ID
            or manifest.get("contract_version") != SECRET_PROVIDER_CONTRACT_VERSION
            or manifest.get("entrypoint") != "r3a_plugins.bitwarden_secrets.provider:create_provider"
            or manifest.get("artifact_ref") != "provider.py"):
        raise ValueError("Bitwarden provider manifest contract is unsupported")
    artifact = (manifest_file.parent / manifest["artifact_ref"]).resolve()
    expected_digest = manifest.get("artifact_sha256")
    if (not artifact.is_relative_to(manifest_file.parent.resolve()) or not artifact.is_file()
            or not isinstance(expected_digest, str)
            or hashlib.sha256(artifact.read_bytes()).hexdigest() != expected_digest):
        raise ValueError("Bitwarden provider artifact does not match its manifest digest")
    try:
        from r3a_runtime.capability_contracts import validate_json
        configuration = load_provider_configuration(configuration_path)
        validate_json(configuration, manifest["configuration_schema"], path="$.configuration")
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith("Bitwarden provider configuration"):
            raise
        raise ValueError("Bitwarden provider configuration does not match its manifest") from None
    return create_provider(configuration)
