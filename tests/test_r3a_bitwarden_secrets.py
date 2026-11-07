"""Contract and failure-path tests for the private Bitwarden secret provider."""
# R3 CONTROLLED SOURCE
# File: tests/test_r3a_bitwarden_secrets.py
# Component: R3A-AP3-BITWARDEN-TESTS
# File Revision: 1.0.0
# Created: 2026-11-07T21:36:43Z
# Created By: Codex GPT-6
# Purpose: Verify versioning, machine identity metadata, failure outcomes, rotation and secret redaction.
# Execution Model: Standard-library unittest with synthetic subprocess responses.
# Observability: Assertions over invocation contract and redacted outcomes; fixture values are synthetic.
# Dependencies: r3a_runtime.secrets; r3a_plugins.bitwarden_secrets.provider.
# Authority: R3A AP3-M2 Issue #50; isolated unit tests only.
# Changed: 2026-11-07T21:36:43Z | R3A-AP3-M2-ISSUE-50 | Codex GPT-6 | Add independent provider contract tests.
# Supersedes: None.
# Contracts: r3a.secrets.provider.v1; r3a.machine-principal.v1.
# Tests: python3 -m unittest tests.test_r3a_bitwarden_secrets.
# History/Predecessor: New file; initial publication recorded in Git.

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from r3a_plugins.bitwarden_secrets.provider import (BitwardenSecretsProvider, create_provider,
                                                   load_configured_provider)
from r3a_runtime.secrets import (
    MACHINE_PRINCIPAL_CONTRACT_ID,
    SECRET_PROVIDER_CONTRACT_ID,
    SecretProviderError,
    SecretReference,
    load_provider_configuration,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_TOKEN = "synthetic-machine-token-for-unit-test"
FIXTURE_TOKEN_ROTATED = "synthetic-machine-token-rotated-for-unit-test"
FIXTURE_VALUE_A = "synthetic-value-alpha"
FIXTURE_VALUE_B = "synthetic-value-bravo"
SECRET_ID = "fixture-secret-id"


def configuration(**overrides):
    value = {
        "provider_id": "r3a.bitwarden-secrets",
        "provider_version": "1.1.0",
        "executable": "bws",
        "access_token_env": "FIXTURE_BWS_TOKEN",
        "machine_principal_id": "fixture-machine-account",
        "timeout_seconds": 5,
    }
    value.update(overrides)
    return value


def reference(**overrides):
    value = {"provider_id": "r3a.bitwarden-secrets", "provider_version": "1.1.0",
             "secret_id": SECRET_ID}
    value.update(overrides)
    return SecretReference(**value)


def completed(value, revision="2026-11-07T20:00:00Z", *, secret_id=SECRET_ID):
    return subprocess.CompletedProcess(
        args=["bws"], returncode=0,
        stdout=json.dumps({"id": secret_id, "value": value, "revisionDate": revision}), stderr="")


class BitwardenSecretsProviderTests(unittest.TestCase):
    def provider(self, run, *, environment=None, executable_lookup=lambda _path: "/usr/bin/bws", **options):
        return BitwardenSecretsProvider(configuration(**options), run=run,
                                        environment=environment or {},
                                        executable_lookup=executable_lookup)

    def test_versioned_private_resolution_and_machine_principal_contract(self):
        calls = []

        def run(command, **kwargs):
            calls.append((command, kwargs))
            return completed(FIXTURE_VALUE_A)

        provider = self.provider(run, environment={"FIXTURE_BWS_TOKEN": FIXTURE_TOKEN},
                                 config_file="/etc/r3a/bws.json", profile="r3a")
        lease = provider.resolve(reference(), correlation_id="corr-50-1")
        self.assertEqual(SECRET_PROVIDER_CONTRACT_ID, reference().contract_id)
        self.assertEqual(FIXTURE_VALUE_A, lease.reveal())
        self.assertEqual("2026-11-07T20:00:00Z", lease.remote_revision)
        self.assertEqual(MACHINE_PRINCIPAL_CONTRACT_ID, lease.machine_principal.contract_id)
        self.assertEqual("fixture-machine-account", lease.machine_principal.principal_id)
        self.assertEqual("bitwarden-secrets-manager", lease.machine_principal.issuer)
        self.assertEqual("corr-50-1", lease.machine_principal.correlation_id)

        command, options = calls[0]
        self.assertEqual(["bws", "secret", "get", SECRET_ID, "--output", "json", "--color", "no",
                          "--config-file", "/etc/r3a/bws.json", "--profile", "r3a"], command)
        self.assertNotIn(FIXTURE_TOKEN, command)
        self.assertEqual(FIXTURE_TOKEN, options["env"]["FIXTURE_BWS_TOKEN"])
        self.assertNotIn(FIXTURE_VALUE_A, repr(lease))
        lease.close()
        self.assertTrue(lease.closed)
        self.assertEqual(bytes(len(FIXTURE_VALUE_A)), bytes(lease._value))
        with self.assertRaises(SecretProviderError):
            lease.reveal()

    def test_rotation_is_observed_on_each_resolution_without_cache(self):
        responses = iter([completed(FIXTURE_VALUE_A, "revision-a"), completed(FIXTURE_VALUE_B, "revision-b")])
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            return next(responses)

        provider = self.provider(run, environment={"FIXTURE_BWS_TOKEN": FIXTURE_TOKEN})
        first = provider.resolve(reference(), correlation_id="rotation-1")
        second = provider.resolve(reference(), correlation_id="rotation-2")
        with first, second:
            self.assertEqual(FIXTURE_VALUE_A, first.reveal())
            self.assertEqual(FIXTURE_VALUE_B, second.reveal())
            self.assertEqual("revision-b", second.remote_revision)
        self.assertEqual(2, len(calls))

    def test_rotated_environment_credential_is_used_on_next_resolution(self):
        environment = {"FIXTURE_BWS_TOKEN": FIXTURE_TOKEN}
        observed_tokens = []

        def run(command, **kwargs):
            observed_tokens.append(kwargs["env"]["FIXTURE_BWS_TOKEN"])
            return completed(FIXTURE_VALUE_A)

        provider = self.provider(run, environment=environment)
        first = provider.resolve(reference(), correlation_id="credential-before")
        first.close()
        environment["FIXTURE_BWS_TOKEN"] = FIXTURE_TOKEN_ROTATED
        second = provider.resolve(reference(), correlation_id="credential-after")
        second.close()
        self.assertEqual([FIXTURE_TOKEN, FIXTURE_TOKEN_ROTATED], observed_tokens)

    def test_denial_recovery_fetches_again_and_succeeds(self):
        responses = iter([
            subprocess.CompletedProcess(args=["bws"], returncode=1, stdout="", stderr="forbidden"),
            completed(FIXTURE_VALUE_A, "recovered-revision"),
        ])
        provider = self.provider(lambda *args, **kwargs: next(responses),
                                 environment={"FIXTURE_BWS_TOKEN": FIXTURE_TOKEN})
        with self.assertRaises(SecretProviderError) as caught:
            provider.resolve(reference(), correlation_id="denied-first")
        self.assertEqual("DENIED", caught.exception.outcome)
        lease = provider.resolve(reference(), correlation_id="recovered-second")
        with lease:
            self.assertEqual(FIXTURE_VALUE_A, lease.reveal())
            self.assertEqual("recovered-revision", lease.remote_revision)

    def test_missing_credential_and_cli_are_unavailable(self):
        invoked = []
        provider = self.provider(lambda *args, **kwargs: invoked.append(args), environment={})
        with self.assertRaises(SecretProviderError) as caught:
            provider.resolve(reference(), correlation_id="missing-token")
        self.assertEqual("UNAVAILABLE", caught.exception.outcome)
        self.assertEqual("credentials_unavailable", caught.exception.reason_code)
        self.assertEqual([], invoked)

        provider = self.provider(lambda *args, **kwargs: completed(FIXTURE_VALUE_A),
                                 environment={"FIXTURE_BWS_TOKEN": FIXTURE_TOKEN},
                                 executable_lookup=lambda _path: None)
        with self.assertRaises(SecretProviderError) as caught:
            provider.resolve(reference(), correlation_id="missing-cli")
        self.assertEqual("UNAVAILABLE", caught.exception.outcome)
        self.assertEqual("cli_unavailable", caught.exception.reason_code)

    def test_authorization_denial_is_explicit_and_cli_text_is_redacted(self):
        sensitive_cli_text = f"forbidden value={FIXTURE_VALUE_A} token={FIXTURE_TOKEN}"
        failure = subprocess.CompletedProcess(args=["bws"], returncode=1, stdout="", stderr=sensitive_cli_text)
        provider = self.provider(lambda *args, **kwargs: failure,
                                 environment={"FIXTURE_BWS_TOKEN": FIXTURE_TOKEN})
        with self.assertRaises(SecretProviderError) as caught:
            provider.resolve(reference(), correlation_id="denied")
        self.assertEqual("DENIED", caught.exception.outcome)
        self.assertNotIn(FIXTURE_VALUE_A, str(caught.exception))
        self.assertNotIn(FIXTURE_TOKEN, str(caught.exception))

    def test_not_found_timeout_malformed_and_mismatched_response_are_fail_closed(self):
        denied_env = {"FIXTURE_BWS_TOKEN": FIXTURE_TOKEN}
        cases = [
            (subprocess.CompletedProcess(args=["bws"], returncode=1, stdout="", stderr="secret not found"), "NOT_FOUND"),
            (subprocess.CompletedProcess(args=["bws"], returncode=0, stdout="{", stderr=""), "FAILED"),
            (completed(FIXTURE_VALUE_A, secret_id="another-secret"), "FAILED"),
            (subprocess.TimeoutExpired("bws", 5), "UNAVAILABLE"),
        ]
        for result, expected in cases:
            with self.subTest(expected=expected):
                def run(*args, _result=result, **kwargs):
                    if isinstance(_result, Exception):
                        raise _result
                    return _result
                provider = self.provider(run, environment=denied_env)
                with self.assertRaises(SecretProviderError) as caught:
                    provider.resolve(reference(), correlation_id="failure")
                self.assertEqual(expected, caught.exception.outcome)
                if expected == "UNAVAILABLE":
                    self.assertEqual("request_timeout", caught.exception.reason_code)

    def test_reference_and_configuration_versions_are_validated(self):
        provider = self.provider(lambda *args, **kwargs: completed(FIXTURE_VALUE_A),
                                 environment={"FIXTURE_BWS_TOKEN": FIXTURE_TOKEN})
        with self.assertRaises(SecretProviderError) as caught:
            provider.resolve(reference(provider_version="2.0.0"), correlation_id="wrong-version")
        self.assertEqual("FAILED", caught.exception.outcome)

        with self.assertRaises(ValueError):
            create_provider(configuration(access_token_env="not-valid"))
        with self.assertRaises(ValueError):
            create_provider(configuration(timeout_seconds=0))
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "provider.json"
            config_path.write_text(json.dumps(configuration()), encoding="utf-8")
            self.assertEqual("r3a.bitwarden-secrets", load_provider_configuration(config_path)["provider_id"])
            config_path.write_text(json.dumps({**configuration(), "unexpected": True}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_provider_configuration(config_path)

    def test_versioned_manifest_pins_provider_artifact_and_loads_external_config(self):
        manifest_path = ROOT / "r3a_plugins/bitwarden_secrets/manifest.json"
        config_path = ROOT / "r3a_plugins/bitwarden_secrets/config.example.json"
        provider = load_configured_provider(manifest_path, config_path)
        self.assertIsInstance(provider, BitwardenSecretsProvider)
        self.assertEqual("r3a.bitwarden-secrets", provider.provider_id)
        self.assertEqual("1.1.0", provider.provider_version)


if __name__ == "__main__":
    unittest.main()
