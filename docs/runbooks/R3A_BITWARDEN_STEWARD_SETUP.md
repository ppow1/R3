<!--
R3 CONTROLLED DOCUMENT
File: docs/runbooks/R3A_BITWARDEN_STEWARD_SETUP.md
Component: R3A-AP3-BITWARDEN-OPERATIONS
File Revision: 1.0.0
Created: 2026-11-08T18:06:44Z
Created By: Codex GPT-6
Purpose: Give the Steward and deployment operator an exact safe setup and acceptance checklist for the Bitwarden provider.
Execution Model: Human-operated Bitwarden configuration and consumer-side deployment/testing.
Observability: Safe provider metadata, reason codes, correlation references, and Bitwarden machine-account audit records only.
Dependencies: r3a.bitwarden-secrets@1.1.2; R3A AP3-M2 Issue #50; optional #49 HMAC identity consumer; Website #51 status interface.
Authority: Approved R3A Master Roadmap Baseline 1.0, AP3 R3A-010/R3A-013; Issue #50; no roadmap exception.
Changed: 2026-11-08T18:06:44Z | R3A-AP3-BITWARDEN-STEWARD-SETUP | Codex GPT-6 | Publish host setup, Bitwarden least-privilege, live test, rotation, revocation, audit, and Website safety checklist.
Supersedes: None.
Contracts: r3a.secrets.provider.v1@1.1.0; r3a.machine-principal.v1@1.0.0; r3a.bitwarden-secrets@1.1.2.
Tests: Documentation review against current provider manifest/config and #49/#51 integration contracts; no real credentials used.
History/Predecessor: New file; initial publication recorded in Git.
-->
# Bitwarden setup and acceptance checklist

This runbook separates Steward-side Bitwarden setup, protected host configuration, synthetic regression, and live acceptance. The live steps require Steward/operator participation. Never paste an access token, secret value, signing key, or browser cookie into ChatGPT, Grace, GitHub, a website form, a shell command line, test output, or an ordinary log.

## 1. Configure Bitwarden (Steward or Bitwarden administrator)

- [ ] Confirm the organization has Bitwarden Secrets Manager enabled and choose a dedicated machine account for the R3A consumer. Do not reuse a person's access token.
- [ ] Create or select a project containing only the test secret needed for the authorized consumer. Assign the machine account **Can read** for that project; do not grant write permission or other project access.
- [ ] Create a synthetic test secret in that project. Use a unique test value with no production meaning. Record its **secret ID** for protected consumer configuration; the ID is a reference, not the value.
- [ ] Create a machine-account access token with a chosen expiry. Bitwarden shows the token once. Save it directly into the approved host secret-delivery channel; do not transmit it to this assistant or put it in a command, ticket, or browser field.
- [ ] Confirm the machine-account Events view is available to the operator. It should record secret access by identifier; R3A records only sanitized outcome/provenance and correlation metadata.

Bitwarden's native CLI supports Linux/macOS/Windows and authenticates from `BWS_ACCESS_TOKEN`. Install a pinned native `bws` release through the approved host package procedure, verify `bws --version`, and record that version in deployment evidence. See the official [CLI install/authentication and state documentation](https://bitwarden.com/help/secrets-manager-cli/) and [machine-account permission guide](https://bitwarden.com/help/machine-accounts/).

## 2. Configure the R3A host (deployment operator)

- [ ] Install the versioned provider package from the authorized R3A commit. Stage `provider.py` beside its matching `manifest.json`; the manifest pins provider `r3a.bitwarden-secrets@1.1.2` and artifact digest `85516d46a839057ddadccefb6716585f9d0da695c56142644e59431da5072378`.
- [ ] Store provider configuration outside Git and the web root, for example `/etc/r3a/providers/bitwarden/provider.json`, with service/operator ownership and restrictive file permissions. Start from `r3a_plugins/bitwarden_secrets/config.example.json`; set the externally assigned `machine_principal_id`, executable path/name, timeout, and optional CLI `config_file`/`profile`.
- [ ] Set `access_token_env` to the protected variable supplied by the approved service manager. The example uses `R3A_BITWARDEN_ACCESS_TOKEN`; the provider copies its value to `BWS_ACCESS_TOKEN` only in the `bws` child environment and removes the custom source variable from that child. The token never appears in argv. If using the canonical environment name directly, set `access_token_env` to `BWS_ACCESS_TOKEN` in the external config.
- [ ] Put the test **secret ID** in the authorized consumer's protected reference configuration (`secret_reference.secret_id` for reasoning or `identity.assertion_secret_ref.secret_id` only when #49 HMAC ingress is deliberately selected). Do not put the secret value in either file.
- [ ] Set `state_opt_out` to `true` or `1` in the selected BWS CLI config when the acceptance requires revocation to force reauthentication. Otherwise Bitwarden documents that cached CLI session state may continue until it expires.
- [ ] As the consumer service identity, validate configuration and local readiness with the provider loader and `assert_available()`. This verifies manifest/configuration, token-variable presence, and CLI availability; it does **not** contact Bitwarden or prove the token can retrieve the reference.

The Website's default `r3.account-session` identity path remains the default and has no Bitwarden dependency. Do not set `identity.provider` to `hmac-ingress` merely to make Bitwarden appear configured. If that optional mode is explicitly selected, the reference and external provider config must both pin provider version 1.1.2.

## 3. Synthetic tests (no Steward credential needed)

- [ ] Run the focused provider, consumer, reasoning-provider, and capability-contract suites with synthetic token/secret values.
- [ ] Verify successful retrieval; reference/version mismatch; missing credentials; missing CLI; timeout; denied access; missing secret; malformed response; rotation; and lease closure.
- [ ] Verify an authorization denial occurs before provider resolution and does not call the model service or CLI.
- [ ] Verify secret echoes are redacted from output, evidence, request bodies, test logs, audit fixtures, and exception diagnostics.
- [ ] Verify `SecretLease.__repr__` excludes the value and `close()` overwrites its buffer; no lease/value is serialized across the CME JSON boundary.
- [ ] Verify configured source token is mapped to `BWS_ACCESS_TOKEN`, not argv, and is absent from the child environment under its custom source name.

These tests establish implementation behavior only. They do not establish real Bitwarden authentication or retrieval.

## 4. Live acceptance (requires Steward/operator participation)

Use only the synthetic test secret and a coordinated isolated consumer. No shared CME restart is part of this checklist.

- [ ] **Authorized retrieval:** invoke the existing authorized consumer using the test reference. Confirm success, machine-account event for the referenced secret ID, correlation/audit metadata, lease closure, and no value in model input, website response, CME output/evidence, durable events, or logs.
- [ ] **Denied retrieval:** use a separate test machine account without access to the test project (or temporarily remove only that test account's assignment). Confirm `DENIED/access_denied`, no secret returned, and safe correlated diagnostics. Restore the test account's intended permission afterward.
- [ ] **Rotation:** create a replacement expiring token; update it only through the protected service-manager channel; reload the owning consumer process/module using its approved procedure; confirm retrieval succeeds using the replacement token; then revoke the superseded test token.
- [ ] **Revocation:** with `state_opt_out` enabled, revoke the replacement test token in Bitwarden and repeat the authorized consumer request. Confirm it fails closed as `DENIED/access_denied`, with no model request/secret value and only sanitized audit evidence. If state opt-out is not enabled, do not claim immediate rejection: Bitwarden says an already-authenticated cached CLI session may continue until expiry.
- [ ] **Recovery:** provision a fresh authorized test token through the same secure channel and confirm the next authorized request recovers without code/config changes that expose the value.

The Steward/operator must supply the Bitwarden-side account, project, test reference, permission changes, token rotation/revocation actions, and the coordinated live-test window. Actual token/secret values remain exclusively in Bitwarden and the approved host injection channel. If no live token is provisioned, report these as pending rather than simulated.

## 5. Safe Website interface contract for #51

The following is a proposed versioned, read-only projection for the Website settings/status panel; #51 owns implementation and may bind it to its existing authorized configuration/status route. It does not add an identity provider, secret registry, CME capability, or settings-write capability.

**Default behavior:** the current R3 account-session adapter continues unchanged. Bitwarden status is optional and must not be fetched as a prerequisite for Website startup, login, or normal portal-session use. If Bitwarden is unconfigured, return/display `not_configured` while the default portal session remains functional.

**Status view:** expose only provider version, mode (`not_required` or `optional_hmac`), configuration state, local readiness (`ready`/`unavailable`), finite reason code, observation time, and—only when available from an existing authoritative audit source—the last remote outcome/time/correlation reference. A readiness check is local-only; label it “CLI and configured token variable present; remote authorization not tested.” A remote check must be the result of the existing authorized consumer, not a browser-triggered secret fetch.

**Never return to the browser:** token values, retrieved secret values, request/response bodies, signatures, CLI stdout/stderr, arbitrary external file paths, environment variable values, secret IDs by default, or unfiltered exception text. A boolean that a credential variable is present is sufficient; do not expose the variable's value. Provider failure responses use the finite `reason_code` vocabulary only.

**Configuration controls:** show that the provider is controlled by protected external configuration. Do not provide a token/password textbox or store a secret in browser state/local storage. Do not let browser input select an arbitrary executable, manifest path, environment variable, or secret ID. Until an existing authorized configuration-write capability owns this setting, the panel is read-only and links to this Steward/operator checklist; do not invent a new Website write route. If a future authorized setting operation is published, it may update non-secret references/configuration metadata, but the credential value remains externally provisioned and is never returned after write.

**Candidate response shape** (only if #51 adopts a dedicated projection; route/mount remain Website-owned):

```json
{
  "contract_id": "r3a.website.bitwarden-status.v1",
  "contract_version": "1.0.0",
  "mode": "not_required",
  "state": "not_configured",
  "local_readiness": "not_checked",
  "reason_code": null,
  "last_remote_outcome": null,
  "observed_at": "<UTC timestamp>"
}
```

If the optional HMAC mode is enabled, the Website must continue to use #49's existing opaque AP3 session and CME authorization/audit path. Anonymous requests remain denied. The default portal identity provider must not import or load Bitwarden unless HMAC mode is explicitly selected.
