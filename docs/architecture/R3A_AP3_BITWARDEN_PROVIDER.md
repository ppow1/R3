<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_AP3_BITWARDEN_PROVIDER.md
Component: R3A-AP3-BITWARDEN-PROVIDER
File Revision: 1.0.2
Created: 2026-11-07T21:36:43Z
Created By: Codex GPT-6
Purpose: Specify the Bitwarden Secrets Manager provider and its shared AP3 identity boundary.
Execution Model: Versioned in-process secret adapter backed by Bitwarden Secrets Manager CLI.
Observability: Redacted status, provider/revision metadata, correlation ID and fetch timestamp.
Dependencies: R3A AP3-M2 Issue #50; AP3-M1 Issue #49; AP1/CME Issue #43; R3A secret-reference configuration.
Authority: Approved R3A Master Roadmap Baseline 1.0; R3A-010/R3A-013; no roadmap exception.
Changed: 2026-11-07T21:36:43Z | R3A-AP3-M2-ISSUE-50 | Codex GPT-6 | Record provider interface, machine identity, and operational limitations.
Changed: 2026-11-07T21:59:02Z | R3A-AP3-M2-CONSUMER | Codex GPT-6 | Document the authorized reasoning-service consumer, lease lifecycle, and disclosure controls.
Changed: 2026-11-07T22:09:29Z | R3A-AP3-M2-CONSUMER | Codex GPT-6 | Version reason-code observability and describe the provider 1.1 contract.
Changed: 2026-11-07T23:40:56Z | R3A-AP3-M2-TEST-HANDOFF | Codex GPT-6 | Publish exact provider fields, failure mapping, and safe #49 consumer guidance.
Supersedes: None.
Contracts: r3a.secrets.provider.v1; r3a.machine-principal.v1; existing CME authorization/audit contracts.
Tests: tests/test_r3a_bitwarden_secrets.py; tests/test_r3a_bitwarden_consumer_integration.py; live provider acceptance requires configured real Bitwarden access.
History/Predecessor: Revision 1.0.0 at commit d07bade6dfa6e6ef498f454d82866aa592b899ba, blob 2caa7358ed0cce4d69e3e28b236935462d2c018a.
-->
# AP3 Bitwarden Secrets Provider

## Authority and scope

This is the AP3-M2 implementation contract under approved R3A Master Roadmap Baseline 1.0, requirements R3A-010 and R3A-013, Issue #50. The approved exception is `None`. Steward authentication/session ownership remains AP3-M1 Issue #49; AP1/CME Issue #43 retains capability authorization, event-ledger audit, and activity dispatch. Secret resolution does not grant an operation.

The adapter is intentionally outside `CapabilityRegistry`: secret values must not become a normal CME invocation result, durable activity event, diagnostic, or resident/model input. A trusted authentication or credential adapter may request a secret lease and consume the value directly in process.

## Versioned interfaces

`r3a.secrets.provider.v1` version `1.1.0` defines this Python interface:

```python
@dataclass(frozen=True)
class SecretReference:
    provider_id: str
    provider_version: str
    secret_id: str
    contract_id: str = "r3a.secrets.provider.v1"
    contract_version: str = "1.1.0"

class SecretProvider(Protocol):
    provider_id: str
    provider_version: str
    def resolve(self, reference: SecretReference, *, correlation_id: str) -> SecretLease: ...
```

`SecretLease` exposes `secret_id`, `provider_id`, `provider_version`, optional `remote_revision`, `fetched_at`, `machine_principal`, `closed`, `reveal() -> str`, `close() -> None`, and context-manager methods. The value is held in a mutable in-process buffer, excluded from repr, and overwritten on close. Do not serialize the dataclass, call `dataclasses.asdict`, log the lease, or retain the string returned by `reveal()` beyond direct verification/credential use. Python immutable string copies cannot be reliably zeroed; keep them short-lived and never persist, emit, notify, or place them in a prompt.

`SecretProviderError` exposes `outcome` and finite, safe `reason_code` only. The supported mapping is:

| Outcome | Reason codes |
| --- | --- |
| `UNAVAILABLE` | `provider_unavailable`, `credentials_unavailable`, `cli_unavailable`, `request_timeout` |
| `DENIED` | `access_denied` |
| `NOT_FOUND` | `reference_not_found` |
| `FAILED` | `provider_start_failed`, `provider_failure`, `invalid_reference`, `invalid_request`, `response_invalid`, `response_mismatch` |

The provider emits `credentials_unavailable` when the configured environment variable has no token, `cli_unavailable` when the executable is absent, and `request_timeout` when the CLI times out. Authentication/authorization diagnostics collapse to `DENIED/access_denied`; missing-item diagnostics collapse to `NOT_FOUND/reference_not_found`. CLI stderr/stdout are never placed in the exception. Consumers should branch only on these finite fields, not parse exception messages. `provider_unavailable` is the default reason for a generic `UNAVAILABLE` error created by a provider implementation.

`r3a.machine-principal.v1` remains version `1.0.0` and exposes `contract_id`, `contract_version`, `issuer`, externally configured `principal_id`, `authenticated_at`, and `correlation_id`. The assertion is emitted only after a successful authenticated secret retrieval. The CLI response confirms that the configured machine token retrieved the requested secret; it does not independently query the machine-account ID. This metadata is provenance for the machine credential, not the requesting human and not an authorization grant. AP3-M1 owns human principal/session lifecycle; CME remains the grant and audit authority.

## Bitwarden adapter and external configuration

The versioned manifest pins the provider artifact digest and declares its configuration schema; `load_configured_provider()` validates the manifest, source digest, and external JSON before constructing the adapter. The provider invokes `bws secret get <secret-id> --output json --color no`. The machine-account access token is read from the externally named environment variable. It is passed only in the subprocess environment, never as a command-line argument. Bitwarden documents machine-account access tokens and the `BWS_ACCESS_TOKEN` environment variable for CLI authentication ([Secrets Manager CLI](https://bitwarden.com/help/secrets-manager-cli/), [Machine Accounts](https://bitwarden.com/help/machine-accounts/)). `executable`, `access_token_env`, `machine_principal_id`, timeout, optional CLI config file, and profile are external configuration in `r3a_plugins/bitwarden_secrets/config.example.json`; server endpoints remain in the Bitwarden CLI's externally provisioned config/profile. The provider does not select or hardcode a Bitwarden server.

Every `resolve` performs a fresh CLI fetch rather than caching a value. The returned Bitwarden `revisionDate` identifies the retrieved version; a rotated value is observed by the next resolution. Updating the access-token environment value takes effect on the next resolution in a process that has received the updated environment; service managers commonly require an authorized process restart or configuration reload to supply a new environment. Configure the external CLI profile's encrypted state behavior according to the deployment's revocation policy. Bitwarden documents that cached CLI session state may continue to work after token revocation until that session expires ([CLI state configuration](https://bitwarden.com/help/secrets-manager-cli/#config)).

No credentials are present in the repository example. A missing token or executable, timeout, denied access, missing reference, and malformed/provider failure have explicit `UNAVAILABLE`, `DENIED`, `NOT_FOUND`, or `FAILED` outcomes with generic redacted messages. CLI stdout/stderr are captured privately; neither response bodies nor diagnostics are included in exceptions or events.

## Configuration and status

Use the external JSON shape from `r3a_plugins/bitwarden_secrets/config.example.json`, with a real externally assigned machine-account ID and a protected environment variable name. `timeout_seconds` is configurable because network latency and deployment behavior vary; the validator accepts 1–120 seconds and the example uses 30 seconds. Optional `config_file` must be an absolute external path; `profile` selects the corresponding externally provisioned server profile.

The provider is `BLOCKED/UNAVAILABLE` for real Bitwarden retrieval until deployment provides the Bitwarden CLI, an authorized machine-account access token, a configured server profile, and an accessible secret reference. Unit tests with synthetic CLI responses verify the adapter contract only; they do not establish live Bitwarden authentication or operational acceptance. No live Bitwarden credentials were available in the development environment inspected for Issue #50.

## Coordination and integration

The existing CME-authorized `reasoning.model.invoke` provider is the representative AP3-M2 service consumer. It accepts optional external `secret_reference` configuration containing provider ID/version, secret ID, and absolute provider manifest/configuration paths. Only after CME dispatch does the provider resolve that reference; the resulting value is used only in the outbound HTTP `Authorization` header. It is rejected if it appears in the serialized request body. The provider closes the lease after every send outcome, redacts exact value echoes in response content/metadata, and emits generic HTTP/provider errors without response bodies. The durable invocation evidence preserves only non-secret credential-source metadata (provider/secret reference, remote revision, fetch time, and machine-principal assertion). `api_key_env` remains supported for existing configuration; setting both credential sources is rejected.

AP3-M1 may consume the same lease as a private authentication/credential adapter dependency. Steward identity assertions and session records remain AP3-M1-owned; machine identity is separate. CME continues to authorize and audit the model operation; no authorization system or secret registry is added. The secret reference is external provider configuration, not part of invocation input, event data, or Grace model messages. Integration changes remain on the isolated AP3-M2 branch for coordinator review through Issue #43; no shared runtime or production service is restarted by these source changes.

### Issue #49 consumer integration guidance

Use `SecretReference` and the provider already selected by the external manifest/configuration. Do not import Bitwarden CLI behavior into the auth adapter or create another token/configuration registry. Set the configured reference's `provider_id` to `r3a.bitwarden-secrets`, `provider_version` to `1.1.0`, `contract_id` to `r3a.secrets.provider.v1`, and `contract_version` to `1.1.0`; keep the secret ID and provider manifest/config paths in protected external configuration. The auth adapter must resolve only after its ingress/origin checks, verify the signed assertion while the lease is open, and close the lease on every path:

```python
try:
    lease = secret_provider.resolve(reference, correlation_id=correlation_id)
except SecretProviderError as exc:
    # AccessUnavailable should retain this finite reason_code as structured status.
    raise AccessUnavailable("identity_secret_unavailable", reason_code=exc.reason_code) from None

try:
    with lease:
        assertion_key = lease.reveal()
        verify_assertion_with_key(assertion, assertion_key)
        provenance = {
            "provider_id": lease.provider_id,
            "provider_version": lease.provider_version,
            "remote_revision": lease.remote_revision,
            "fetched_at": lease.fetched_at,
            "machine_principal": {
                "issuer": lease.machine_principal.issuer,
                "principal_id": lease.machine_principal.principal_id,
                "authenticated_at": lease.machine_principal.authenticated_at,
                "correlation_id": lease.machine_principal.correlation_id,
            },
        }
finally:
    assertion_key = None
```

The adapter should translate `AccessUnavailable.reason_code` into the established unavailable response/audit reason while keeping the HTTP response generic. Preserve distinctions among missing machine credentials, missing CLI, access denial, missing secret reference, and provider failure. Persist only the non-secret provenance fields shown above; never persist the assertion key, CLI output, exception text from unrelated failures, signature, or request secret. CME remains the authority for protected capabilities; the machine-principal assertion must not be substituted for the Steward identity assertion or CME grant decision.
