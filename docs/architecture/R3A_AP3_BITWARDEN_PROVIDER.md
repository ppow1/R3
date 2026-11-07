<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_AP3_BITWARDEN_PROVIDER.md
Component: R3A-AP3-BITWARDEN-PROVIDER
File Revision: 1.0.0
Created: 2026-11-07T21:36:43Z
Created By: Codex GPT-6
Purpose: Specify the Bitwarden Secrets Manager provider and its shared AP3 identity boundary.
Execution Model: Versioned in-process secret adapter backed by Bitwarden Secrets Manager CLI.
Observability: Redacted status, provider/revision metadata, correlation ID and fetch timestamp.
Dependencies: R3A AP3-M2 Issue #50; AP3-M1 Issue #49; AP1/CME Issue #43; R3A secret-reference configuration.
Authority: Approved R3A Master Roadmap Baseline 1.0; R3A-010/R3A-013; no roadmap exception.
Changed: 2026-11-07T21:36:43Z | R3A-AP3-M2-ISSUE-50 | Codex GPT-6 | Record provider interface, machine identity, and operational limitations.
Supersedes: None.
Contracts: r3a.secrets.provider.v1; r3a.machine-principal.v1; existing CME authorization/audit contracts.
Tests: tests/test_r3a_bitwarden_secrets.py; live provider acceptance requires configured real Bitwarden access.
History/Predecessor: New document; initial publication recorded in Git.
-->
# AP3 Bitwarden Secrets Provider

## Authority and scope

This is the AP3-M2 implementation contract under approved R3A Master Roadmap Baseline 1.0, requirements R3A-010 and R3A-013, Issue #50. The approved exception is `None`. Steward authentication/session ownership remains AP3-M1 Issue #49; AP1/CME Issue #43 retains capability authorization, event-ledger audit, and activity dispatch. Secret resolution does not grant an operation.

The adapter is intentionally outside `CapabilityRegistry`: secret values must not become a normal CME invocation result, durable activity event, diagnostic, or resident/model input. A trusted authentication or credential adapter may request a secret lease and consume the value directly in process.

## Versioned interfaces

`r3a.secrets.provider.v1` version `1.0.0` defines `SecretReference` with `provider_id`, `provider_version`, and Bitwarden `secret_id`, plus contract ID/version. `SecretProvider.resolve(reference, correlation_id)` returns a `SecretLease` with secret value held in a mutable in-process buffer, remote `revisionDate`, fetch time, and machine-principal metadata. Callers consume it through `reveal()` and must use the lease as a context manager or call `close()`; close overwrites the mutable lease buffer. The value is excluded from the lease representation. Python callers may create transient immutable copies when consuming the value, so the adapter must keep its own handling short-lived and must never serialize, log, emit, or place the value into a prompt.

`r3a.machine-principal.v1` version `1.0.0` carries `issuer`, stable configured `principal_id`, `authenticated_at`, and `correlation_id`. The assertion is emitted only after a successful authenticated secret retrieval. `principal_id` is the externally configured Bitwarden machine-account identity; the CLI response confirms that its token could retrieve the requested secret but does not return an independently queried machine-account ID. This metadata is a credential-source identity, not the authenticated Steward principal, and must not be accepted as a caller-supplied authorization claim. AP3-M1 owns human principal/session lifecycle; CME remains the grant and audit authority.

## Bitwarden adapter and external configuration

The versioned manifest pins the provider artifact digest and declares its configuration schema; `load_configured_provider()` validates the manifest, source digest, and external JSON before constructing the adapter. The provider invokes `bws secret get <secret-id> --output json --color no`. The machine-account access token is read from the externally named environment variable. It is passed only in the subprocess environment, never as a command-line argument. Bitwarden documents machine-account access tokens and the `BWS_ACCESS_TOKEN` environment variable for CLI authentication ([Secrets Manager CLI](https://bitwarden.com/help/secrets-manager-cli/), [Machine Accounts](https://bitwarden.com/help/machine-accounts/)). `executable`, `access_token_env`, `machine_principal_id`, timeout, optional CLI config file, and profile are external configuration in `r3a_plugins/bitwarden_secrets/config.example.json`; server endpoints remain in the Bitwarden CLI's externally provisioned config/profile. The provider does not select or hardcode a Bitwarden server.

Every `resolve` performs a fresh CLI fetch rather than caching a value. The returned Bitwarden `revisionDate` identifies the retrieved version; a rotated value is observed by the next resolution. Updating the access-token environment value takes effect on the next resolution in a process that has received the updated environment; service managers commonly require an authorized process restart or configuration reload to supply a new environment. Configure the external CLI profile's encrypted state behavior according to the deployment's revocation policy. Bitwarden documents that cached CLI session state may continue to work after token revocation until that session expires ([CLI state configuration](https://bitwarden.com/help/secrets-manager-cli/#config)).

No credentials are present in the repository example. A missing token or executable, timeout, denied access, missing reference, and malformed/provider failure have explicit `UNAVAILABLE`, `DENIED`, `NOT_FOUND`, or `FAILED` outcomes with generic redacted messages. CLI stdout/stderr are captured privately; neither response bodies nor diagnostics are included in exceptions or events.

## Configuration and status

Use the external JSON shape from `r3a_plugins/bitwarden_secrets/config.example.json`, with a real externally assigned machine-account ID and a protected environment variable name. `timeout_seconds` is configurable because network latency and deployment behavior vary; the validator accepts 1–120 seconds and the example uses 30 seconds. Optional `config_file` must be an absolute external path; `profile` selects the corresponding externally provisioned server profile.

The provider is `BLOCKED/UNAVAILABLE` for real Bitwarden retrieval until deployment provides the Bitwarden CLI, an authorized machine-account access token, a configured server profile, and an accessible secret reference. Unit tests with synthetic CLI responses verify the adapter contract only; they do not establish live Bitwarden authentication or operational acceptance. No live Bitwarden credentials were available in the development environment inspected for Issue #50.

## Coordination and integration

AP3-M1 may consume the lease as a private authentication/credential adapter dependency. Steward identity assertions and session records remain AP3-M1-owned; machine identity is separate. AP3 capability invocation, CME authorization, and audit schemas are unchanged, and the provider is not added as a Grace tool. Integration is coordinated through Issue #43 after review of the versioned interfaces; this implementation branch does not modify a shared runtime or production service.
