<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_AP3_BITWARDEN_PROVIDER.md
Component: R3A-AP3-BITWARDEN-PROVIDER
File Revision: 1.0.8
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
Changed: 2026-11-08T14:15:00Z | R3A-AP3-M2-PROVIDER-ACTIVATION | Codex GPT-6 | Record provider 1.1.2 readiness, isolated module activation, and remaining runtime boundary.
Changed: 2026-11-08T14:15:00Z | R3A-AP3-M2-PROVIDER-ACTIVATION | Codex GPT-6 | Refresh consumer alignment and activation checklist for provider release 1.1.2.
Changed: 2026-11-08T15:20:00Z | R3A-AP3-M2-PROVIDER-PACKAGING | Codex GPT-6 | Document runtime b835ed4 typed-result integration, source packaging, activation, rollback, and isolated CME verification.
Changed: 2026-11-08T18:12:00Z | R3A-AP3-M2-STEWARD-HANDOFF | Codex GPT-6 | Link the Steward setup/live acceptance checklist and define optional safe Website status integration.
Supersedes: None.
Contracts: r3a.secrets.provider.v1; r3a.machine-principal.v1; existing CME authorization/audit contracts.
Tests: tests/test_r3a_bitwarden_secrets.py; tests/test_r3a_bitwarden_consumer_integration.py; live provider acceptance requires configured real Bitwarden access.
History/Predecessor: Revision 1.0.0 at commit d07bade6dfa6e6ef498f454d82866aa592b899ba, blob 2caa7358ed0cce4d69e3e28b236935462d2c018a.
-->
# AP3 Bitwarden Secrets Provider

The Steward/operator setup, credential handling, rotation/revocation, live acceptance, and optional Website status checklist is [R3A_BITWARDEN_STEWARD_SETUP.md](../runbooks/R3A_BITWARDEN_STEWARD_SETUP.md).

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

The immutable patch release is `r3a.bitwarden-secrets@1.1.2`; it preserves contract `r3a.secrets.provider.v1@1.1.0`. Release 1.1.0 remains immutable at digest `464b20a0b5fd3a371bd59627407a7efea4d0cf6f0d745d2ebeb1f25f33ca23d8`. Release 1.1.1 fixed the credential environment binding. Release 1.1.2 adds a redacted prerequisite-readiness probe; its artifact digest is pinned in `r3a_plugins/bitwarden_secrets/manifest.json`. `load_configured_provider()` verifies provider and contract versions, manifest entrypoint, artifact containment/digest, and external configuration schema before constructing the adapter.

The provider ships as `r3a_plugins.bitwarden_secrets` in the R3A runtime distribution. The root package metadata includes the provider manifest and safe config example as package data; the module source, manifest, and config schema remain versioned separately from CME capability authorization. Bitwarden documents native CLI support for Windows, macOS, and Linux distributions and an official container image. `bws` is not installed or available anywhere in the approved development paths checked for this milestone. The adapter invokes `bws secret get <secret-id> --output json --color no` as a child process. Bitwarden's CLI reads `BWS_ACCESS_TOKEN`. The adapter reads the configured `access_token_env`, binds its value to `BWS_ACCESS_TOKEN` only in the child environment, and removes the custom source variable from that child environment. The value never enters argv. Bitwarden machine accounts scope access to assigned projects/secrets; configure only read permission for the required secret. References identify a provider ID/version and secret ID; they contain no value. See Bitwarden's [CLI installation and authentication instructions](https://bitwarden.com/help/secrets-manager-cli/) and [machine-account permissions](https://bitwarden.com/help/machine-accounts/).

The provider JSON in `r3a_plugins/bitwarden_secrets/config.example.json` is the exact external configuration shape: `provider_id`, provider `provider_version` 1.1.2, `executable`, `access_token_env`, externally assigned `machine_principal_id`, `timeout_seconds` (1–120), and optional `config_file` / `profile`. The secret token itself is absent from JSON. The service supervisor must inject the named environment variable into the provider consumer process. `config_file` and `profile` select an externally provisioned Bitwarden server profile; the provider does not select or hardcode a server. For strict revocation response, configure the selected `bws` config's `state_opt_out` to `true` or `1`; Bitwarden documents that otherwise encrypted CLI state can be reused. The deployed provider manifest and `provider.py` must be staged together at the manifest-relative artifact path with a matching digest.

### Runtime activation and authorization

Bitwarden remains a private provider dependency; it is not independently registered as a CME capability and secret resolution does not grant access to any R3 operation. Provider activation means staging the pinned provider artifact/manifest and external JSON at the paths supplied to the authorized consumer, then loading them through `load_configured_provider()`. The #49 Steward adapter binds this during configured service setup and resolves only after origin and trusted ingress identity checks. The reasoning consumer loads the provider on its first CME-authorized `reasoning.model.invoke`; CME performs grants, reservation, dispatch, and audit before provider resolution. Machine-principal metadata is credential-source provenance only.

For the #49 HMAC-ingress consumer, set `R3A_STEWARD_ACCESS_CONFIG` to its protected external config; its `secret_provider_manifest` and `secret_provider_config` are absolute paths. If that adapter is enabled, set `identity.assertion_secret_ref` to `{provider_id: "r3a.bitwarden-secrets", provider_version: "1.1.2", secret_id: "<assigned-id>"}` and ensure the referenced external provider JSON also has provider version 1.1.2. The current #49 default R3 account-session identity adapter does not need a Bitwarden reference. The config's `session_dsn_env` must name a separately provisioned session database credential; the Bitwarden token remains the provider's separately configured `access_token_env`. Remote-access session authentication and CME grants remain separate authorities.

Every `resolve` launches a fresh CLI retrieval and does not cache the secret value. Its `revisionDate` is returned as `remote_revision`, so secret rotation is observed by the next successful resolve. The provider re-reads the configured source environment variable each call; updating it in the running process takes effect on the next call, while deployment secret managers may require an authorized reload/restart to update that process environment.

Token revocation has a CLI-specific caveat: Bitwarden documents that a CLI session already authenticated may continue retrieving/decrypting for up to one hour after access-token revocation. For immediate reauthentication, configure the selected CLI config's `state_opt_out` to `true`/`1` or delete that token's state file through the approved service operator procedure. The provider's JSON `config_file` points to the CLI server/profile config, not to a secret value. A coordinated revoked-token smoke check must verify the deployed state policy; do not claim immediate revocation from provider behavior alone. See Bitwarden's [CLI state settings](https://bitwarden.com/help/secrets-manager-cli/#config) and [access-token revocation behavior](https://bitwarden.com/help/access-tokens/).

No credentials are present in the repository example. A missing token or executable, timeout, denied access, missing reference, and malformed/provider failure have explicit `UNAVAILABLE`, `DENIED`, `NOT_FOUND`, or `FAILED` outcomes with generic redacted messages. CLI stdout/stderr are captured privately; neither response bodies nor diagnostics are included in exceptions or events.

## Isolated lifecycle verification

The reasoning consumer manifest declares `r3a.reasoning-inference@1.1.2` as the managed capability module and keeps Bitwarden as a private in-process dependency. Managed runtime release `b835ed4` already implements `r3a.capability-provider-result.v1@1.0.0`: the worker serializes separate JSON-safe `output` and `evidence`, and the manager restores `CapabilityProviderResult` for CME normalization. No duplicate transport was added. I executed the current provider and consumer in a disposable copy of that release with a synthetic CLI fixture and local model endpoint. Through CME with a synthetic allowed grant, resolution succeeded; echoed synthetic secret text was redacted from result/output/evidence, the request body contained no secret, and the process-boundary result was typed output/evidence. A second call denied by the synthetic grant made no CLI request. The module then stopped cleanly. This verifies integration and disclosure behavior only with synthetic credentials; it is not live Bitwarden evidence.

The test harness recorded only Boolean checks for CLI invocation and token placement: the fake CLI received `BWS_ACCESS_TOKEN`, not the configured source variable, and no credential was in argv. The existing 34 focused unit tests separately verify lease buffer cleanup, error mapping, authorization-before-resolution, and config/manifest failures. No secret value was printed or stored as test output.

### Install, activate, and roll back

1. Install the R3A source distribution or runtime wheel built from the exact provider commit into the isolated R3A virtual environment. Keep `r3a_plugins/bitwarden_secrets/provider.py`, `manifest.json`, and `config.example.json` together; the provider artifact digest in the manifest must equal the installed `provider.py` digest. Stage immutable versions under a release directory such as `/opt/r3a/providers/bitwarden/1.1.2/`; do not overwrite a prior version.
2. Put the service-specific provider JSON in a protected external config directory. Set file ownership to the consumer service/operator and restrict it to the minimum required read access. It contains only provider settings and the token environment-variable name, never the token. Inject the actual machine-account token through the approved process environment mechanism.
3. Point the authorized consumer's manifest/config paths and `SecretReference` at the matching 1.1.2 release. Check readiness as the consumer service identity with `load_configured_provider(manifest_path, configuration_path).assert_available()`. This checks token presence and CLI availability without resolving a secret. Then activate through the consumer's normal lifecycle: the reasoning consumer is registered under its module manifest and first resolves only after CME authorization; the optional #49 HMAC adapter resolves only after its ingress checks. Do not register the secret provider as a CME capability.
4. For rollback, retain the previous immutable runtime release and matching provider manifest/config/reference. Restore that complete code-and-config set as one release, then use the owning service's authorized reload/module replacement procedure. Provider 1.1.2 rejects a reference or config with a different provider version; do not roll back by changing only the version string or by mixing artifacts. The provider is stateless and requires no data migration. Any CME lifecycle activation/deactivation or shared service reload remains under Coordinator's integration window.

The AP3 package was source-distribution built in a temporary tree and inspected: provider source, manifest, config example, reasoning manifest, and consumer example were included. Wheel construction could not be verified in this environment because the available build environments lack the `wheel` build command; `pyproject.toml` declares the same package data for wheel builds. This packaging-tool limitation does not affect the isolated managed-release lifecycle test.

## Configuration and status

Use the external JSON shape from `r3a_plugins/bitwarden_secrets/config.example.json`, with a real externally assigned machine-account ID and a protected environment variable name. `timeout_seconds` is configurable because network latency and deployment behavior vary; the validator accepts 1–120 seconds and the example uses 30 seconds. Optional `config_file` must be an absolute external path; `profile` selects the corresponding externally provisioned server profile.

The provider and reasoning consumer lifecycle are isolated-tested against managed release `b835ed4`; real Bitwarden retrieval remains unavailable until deployment provides the CLI in the consumer process environment, an authorized machine-account access token, a configured server/profile if required, protected external config paths, and a permitted secret reference. The approved-path inventory found no `bws` binary, machine-token variable in this process/configuration files, external provider config files, or enumerable R3A systemd units in this development environment. If #49 enables its HMAC ingress adapter, its reference and external provider JSON must use provider 1.1.2; its default R3 account-session adapter does not use Bitwarden. Synthetic lifecycle and regression evidence do not establish live authentication/retrieval. No real Bitwarden credentials were available in this work environment.

## Coordination and integration

The existing CME-authorized `reasoning.model.invoke` provider is the representative AP3-M2 service consumer. It accepts optional external `secret_reference` configuration containing provider ID/version, secret ID, and absolute provider manifest/configuration paths. Only after CME dispatch does the provider resolve that reference; the resulting value is used only in the outbound HTTP `Authorization` header. It is rejected if it appears in the serialized request body. The provider closes the lease after every send outcome, redacts exact value echoes in response content/metadata, and emits generic HTTP/provider errors without response bodies. The durable invocation evidence preserves only non-secret credential-source metadata (provider/secret reference, remote revision, fetch time, and machine-principal assertion). `api_key_env` remains supported for existing configuration; setting both credential sources is rejected.

AP3-M1 may consume the same lease as a private authentication/credential adapter dependency. Steward identity assertions and session records remain AP3-M1-owned; machine identity is separate. CME continues to authorize and audit the model operation; no authorization system or secret registry is added. The secret reference is external provider configuration, not part of invocation input, event data, or Grace model messages. Integration changes remain on the isolated AP3-M2 branch for coordinator review through Issue #43; no shared runtime or production service is restarted by these source changes.

### Issue #49 consumer integration guidance

Use `SecretReference` and the provider already selected by the external manifest/configuration. Do not import Bitwarden CLI behavior into the auth adapter or create another token/configuration registry. Set the configured reference's `provider_id` to `r3a.bitwarden-secrets`, `provider_version` to `1.1.2`, `contract_id` to `r3a.secrets.provider.v1`, and `contract_version` to `1.1.0`; keep the secret ID and provider manifest/config paths in protected external configuration. The auth adapter must resolve only after its ingress/origin checks, verify the signed assertion while the lease is open, and close the lease on every path:

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

1. **Provider registration:** deploy `r3a.bitwarden-secrets@1.1.2` and its pinned artifact together; its contract remains `r3a.secrets.provider.v1@1.1.0`. The previous provider 1.1.0 digest remains valid only for that immutable release.
2. **External configuration:** install a supported `bws` binary in the consumer process environment and provide protected provider/service JSON paths. Inject the configured machine-account token into the service environment; the adapter maps it to `BWS_ACCESS_TOKEN` for `bws`. Grant only read access to the required secret/project.
3. **Consumer binding:** #49 is currently at `engineering/r3a-ap3-remote-20261107` / `12a30f9`. Its default R3 account-session identity adapter does not use Bitwarden. If the HMAC-ingress adapter is enabled, its example reference and external provider JSON must both be set to provider version 1.1.2; the provider contract remains 1.1.0. The HMAC adapter preserves `reason_code`, closes leases, and records provider/machine-principal contract provenance.
4. **Authorization:** verify allowed origin and trusted ingress assertion before resolving its verification-key reference. Close the lease on success and failure. Keep Steward principal/session authority in #49 and protected capability grants/audit in CME; machine-principal provenance grants neither.
5. **Live smoke:** only after an authorized machine account, CLI, external config, secret reference, and coordinated service window are available, perform one narrow reference resolution and one authenticated consumer/session check. Record provider/revision, configured machine-principal metadata, correlation ID, and success/failure reason only. Confirm lease closure and ensure no secret value appears in stdout/stderr, logs, events, HTTP bodies, notifications, or model context. Revoke/rotate only an authorized test token under the operator's plan, verify the selected CLI state policy, and do not restart or activate the shared runtime outside the coordinator's window.
