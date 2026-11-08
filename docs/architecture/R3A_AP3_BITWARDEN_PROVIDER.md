<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_AP3_BITWARDEN_PROVIDER.md
Component: R3A-AP3-BITWARDEN-PROVIDER
File Revision: 1.0.5
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
Changed: 2026-11-07T23:52:00Z | R3A-AP3-M2-INTEGRATION-REVIEW | Codex GPT-6 | Record #49 compatibility review and coordinator integration checklist.
Changed: 2026-11-08T13:35:27Z | R3A-AP3-M2-MANAGED-INTEGRATION | Codex GPT-6 | Document verified CLI auth binding, patch release 1.1.1, activation and revocation behavior.
Changed: 2026-11-08T13:35:27Z | R3A-AP3-M2-MANAGED-INTEGRATION | Codex GPT-6 | Refresh #49 review and coordinator guidance for provider release 1.1.1.
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

The immutable patch release is `r3a.bitwarden-secrets@1.1.1`; it preserves contract `r3a.secrets.provider.v1@1.1.0`. Release 1.1.0 remains immutable at digest `464b20a0b5fd3a371bd59627407a7efea4d0cf6f0d745d2ebeb1f25f33ca23d8`. Release 1.1.1 fixes the credential environment binding; its artifact digest is pinned in `r3a_plugins/bitwarden_secrets/manifest.json`. `load_configured_provider()` verifies provider and contract versions, manifest entrypoint, artifact containment/digest, and external configuration schema before constructing the adapter.

Bitwarden documents native CLI support for Windows, macOS, and Linux distributions and an official container image; the managed runtime here is Linux x86_64, but `bws` is not installed or available on its PATH. The adapter invokes `bws secret get <secret-id> --output json --color no` as a child process. Bitwarden's CLI reads `BWS_ACCESS_TOKEN`. The adapter reads the configured `access_token_env`, binds its value to `BWS_ACCESS_TOKEN` only in the child environment, and removes the custom source variable from that child environment. The value never enters argv. Bitwarden machine accounts scope access to assigned projects/secrets; configure only read permission for the required secret. References identify a provider ID/version and secret ID; they contain no value. See Bitwarden's [CLI installation and authentication instructions](https://bitwarden.com/help/secrets-manager-cli/) and [machine-account permissions](https://bitwarden.com/help/machine-accounts/).

The provider JSON in `r3a_plugins/bitwarden_secrets/config.example.json` is the exact external configuration shape: `provider_id`, provider `provider_version` 1.1.1, `executable`, `access_token_env`, externally assigned `machine_principal_id`, `timeout_seconds` (1–120), and optional `config_file` / `profile`. The secret token itself is absent from JSON. The service supervisor must inject the named environment variable into the provider consumer process. `config_file` and `profile` select an externally provisioned Bitwarden server profile; the provider does not select or hardcode a server. For strict revocation response, configure the selected `bws` config's `state_opt_out` to `true` or `1`; Bitwarden documents that otherwise encrypted CLI state can be reused. The deployed provider manifest and `provider.py` must be staged together at the manifest-relative artifact path with a matching digest.

### Runtime activation and authorization

Bitwarden remains a private provider dependency; it is not independently registered as a CME capability and secret resolution does not grant access to any R3 operation. Provider activation means staging the pinned provider artifact/manifest and external JSON at the paths supplied to the authorized consumer, then loading them through `load_configured_provider()`. The #49 Steward adapter binds this during configured service setup and resolves only after origin and trusted ingress identity checks. The reasoning consumer loads the provider on its first CME-authorized `reasoning.model.invoke`; CME performs grants, reservation, dispatch, and audit before provider resolution. Machine-principal metadata is credential-source provenance only.

For the #49 consumer, set `R3A_STEWARD_ACCESS_CONFIG` to its protected external config; its `secret_provider_manifest` and `secret_provider_config` are absolute paths. Set `identity.assertion_secret_ref` to `{provider_id: "r3a.bitwarden-secrets", provider_version: "1.1.1", secret_id: "<assigned-id>"}` and ensure the referenced external provider JSON also has provider version 1.1.1. The config's `session_dsn_env` must name a separately provisioned session database credential; the Bitwarden token remains the provider's separately configured `access_token_env`. Remote-access session authentication and CME grants remain separate authorities.

Every `resolve` launches a fresh CLI retrieval and does not cache the secret value. Its `revisionDate` is returned as `remote_revision`, so secret rotation is observed by the next successful resolve. The provider re-reads the configured source environment variable each call; updating it in the running process takes effect on the next call, while deployment secret managers may require an authorized reload/restart to update that process environment.

Token revocation has a CLI-specific caveat: Bitwarden documents that a CLI session already authenticated may continue retrieving/decrypting for up to one hour after access-token revocation. For immediate reauthentication, configure the selected CLI config's `state_opt_out` to `true`/`1` or delete that token's state file through the approved service operator procedure. The provider's JSON `config_file` points to the CLI server/profile config, not to a secret value. A coordinated revoked-token smoke check must verify the deployed state policy; do not claim immediate revocation from provider behavior alone. See Bitwarden's [CLI state settings](https://bitwarden.com/help/secrets-manager-cli/#config) and [access-token revocation behavior](https://bitwarden.com/help/access-tokens/).

No credentials are present in the repository example. A missing token or executable, timeout, denied access, missing reference, and malformed/provider failure have explicit `UNAVAILABLE`, `DENIED`, `NOT_FOUND`, or `FAILED` outcomes with generic redacted messages. CLI stdout/stderr are captured privately; neither response bodies nor diagnostics are included in exceptions or events.

## Configuration and status

Use the external JSON shape from `r3a_plugins/bitwarden_secrets/config.example.json`, with a real externally assigned machine-account ID and a protected environment variable name. `timeout_seconds` is configurable because network latency and deployment behavior vary; the validator accepts 1–120 seconds and the example uses 30 seconds. Optional `config_file` must be an absolute external path; `profile` selects the corresponding externally provisioned server profile.

The provider is `BLOCKED/UNAVAILABLE` for real Bitwarden retrieval until deployment provides the CLI in the consumer process environment, an authorized machine-account access token, a configured server/profile if required, protected external config paths, and a permitted secret reference. Unit tests with synthetic CLI responses verify the adapter contract only; they do not establish live Bitwarden authentication or operational acceptance. No live Bitwarden credentials were available in this work environment.

## Coordination and integration

The existing CME-authorized `reasoning.model.invoke` provider is the representative AP3-M2 service consumer. It accepts optional external `secret_reference` configuration containing provider ID/version, secret ID, and absolute provider manifest/configuration paths. Only after CME dispatch does the provider resolve that reference; the resulting value is used only in the outbound HTTP `Authorization` header. It is rejected if it appears in the serialized request body. The provider closes the lease after every send outcome, redacts exact value echoes in response content/metadata, and emits generic HTTP/provider errors without response bodies. The durable invocation evidence preserves only non-secret credential-source metadata (provider/secret reference, remote revision, fetch time, and machine-principal assertion). `api_key_env` remains supported for existing configuration; setting both credential sources is rejected.

AP3-M1 may consume the same lease as a private authentication/credential adapter dependency. Steward identity assertions and session records remain AP3-M1-owned; machine identity is separate. CME continues to authorize and audit the model operation; no authorization system or secret registry is added. The secret reference is external provider configuration, not part of invocation input, event data, or Grace model messages. Integration changes remain on the isolated AP3-M2 branch for coordinator review through Issue #43; no shared runtime or production service is restarted by these source changes.

### Issue #49 consumer integration guidance

Use `SecretReference` and the provider already selected by the external manifest/configuration. Do not import Bitwarden CLI behavior into the auth adapter or create another token/configuration registry. Set the configured reference's `provider_id` to `r3a.bitwarden-secrets`, `provider_version` to `1.1.1`, `contract_id` to `r3a.secrets.provider.v1`, and `contract_version` to `1.1.0`; keep the secret ID and provider manifest/config paths in protected external configuration. The auth adapter must resolve only after its ingress/origin checks, verify the signed assertion while the lease is open, and close the lease on every path:

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
            "contract_id": SECRET_PROVIDER_CONTRACT_ID,
            "contract_version": SECRET_PROVIDER_CONTRACT_VERSION,
            "provider_id": lease.provider_id,
            "provider_version": lease.provider_version,
            "secret_id": lease.secret_id,
            "remote_revision": lease.remote_revision,
            "fetched_at": lease.fetched_at,
            "machine_principal": {
                "contract_id": lease.machine_principal.contract_id,
                "contract_version": lease.machine_principal.contract_version,
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

### Coordinator integration checklist

1. **Provider registration:** deploy `r3a.bitwarden-secrets@1.1.1` and its pinned artifact together; its contract remains `r3a.secrets.provider.v1@1.1.0`. The previous provider 1.1.0 digest remains valid only for that immutable release.
2. **External configuration:** install a supported `bws` binary in the consumer process environment and provide protected provider/service JSON paths. Inject the configured machine-account token into the service environment; the adapter maps it to `BWS_ACCESS_TOKEN` for `bws`. Grant only read access to the required secret/project.
3. **Consumer binding:** the #49 branch at `9e77d74913bece16d46d1aba164d912ce2e88203` corrected the previous handoff gaps: its config reference uses provider 1.1.0, it preserves `reason_code`, closes leases, and records provider/machine-principal contract provenance. Before activating this 1.1.1 provider patch, update the #49 reference and external provider config to provider version 1.1.1.
4. **Authorization:** verify allowed origin and trusted ingress assertion before resolving its verification-key reference. Close the lease on success and failure. Keep Steward principal/session authority in #49 and protected capability grants/audit in CME; machine-principal provenance grants neither.
5. **Live smoke:** only after an authorized machine account, CLI, external config, secret reference, and coordinated service window are available, perform one narrow reference resolution and one authenticated consumer/session check. Record provider/revision, configured machine-principal metadata, correlation ID, and success/failure reason only. Confirm lease closure and ensure no secret value appears in stdout/stderr, logs, events, HTTP bodies, notifications, or model context. Revoke/rotate only an authorized test token under the operator's plan, verify the selected CLI state policy, and do not restart or activate the shared runtime outside the coordinator's window.
