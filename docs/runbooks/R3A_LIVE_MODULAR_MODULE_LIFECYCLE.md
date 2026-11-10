# R3A governed module release and rollback

This runbook packages the existing OctoMiner telemetry provider as an example of the generic provider lifecycle. The packager validates the `r3a.module-manifest.v1@1.1.0` declaration, the capability contract, configuration schema, dependency declaration, read-only effect, required grant, and every pinned source file. The bundle has its own digest and version-specific Python import path. Install does not edit CME or create a grant.

## 1. Build and verify the artifact

Run from the selected, reviewed R3A release checkout:

```sh
python3 scripts/package_octominer_module.py build \
  --output artifacts/r3a.octominer-telemetry-2.0.0.tar.gz
python3 scripts/package_octominer_module.py verify \
  artifacts/r3a.octominer-telemetry-2.0.0.tar.gz
sha256sum artifacts/r3a.octominer-telemetry-2.0.0.tar.gz
```

Store the output digest with the release record. `verify` must pass before installation. A changed file, unsupported manifest version, undeclared capability, effect change, or mismatched authorization/dependency declaration fails closed.

## 2. Install into an isolated or approved application root

For staging, point `--root` at the isolated candidate checkout root. For a shared deployment, the Coordinator selects the managed checkout and approves the activation window first.

```sh
python3 scripts/package_octominer_module.py install \
  artifacts/r3a.octominer-telemetry-2.0.0.tar.gz \
  --root /path/to/r3a-application
```

Install is versioned under `r3a_plugins/octominer_telemetry_2_0_0/`. Repeating the same install is idempotent. A different bundle cannot overwrite an installed version; publish a new module version and import path instead. The install receipt records the bundle SHA-256 and path.

## 3. Register and authorize through the existing control plane

The deployment owner adds the installed `manifest.json` and a separately protected configuration file to the existing `capability_operations` configuration list, and adds `infrastructure.octominer.telemetry.read` to the existing module's declared `module.capabilities`. Then submit the normal CME `config.reload` operation. Preserve the established telemetry configuration and host provenance. Keep SSH on pinned host keys and read-only commands; do not store credential material in the module package or repository.

This package declares `infrastructure.octominer.telemetry.read`; it creates no grant. **The module must remain disabled until the #43 executor-identity correction is independently reviewed, reconciled into the Coordinator baseline, and deployed.** On the current managed path, the directory resident ID is `resident:grace`; CME uses that ID for grant discovery and as both the invocation principal and resident. The OctoMiner manifest allows only `resident.grace`, so the current request fails its caller constraint, and a grant under either identity alone does not make the current path work.

After the reviewed #43 identity correction is active, the intended identities must remain distinct and consistent: `caller.principal_id=resident:grace`, `caller.resident_id=resident.grace`, and the grant lookup subject is the executor `resident.grace`. The narrowest available grant for a single controlled activity is then:

```json
{
  "module_id": "resident.grace",
  "capability_id": "infrastructure.octominer.telemetry.read",
  "scope": {"activity_id": "<the approved durable activity UUID>"}
}
```

The `activity_id` must be the activity used for the controlled invocation. A grant with `{}` scope is global for that executor/capability and is not acceptable for this acceptance run. The current `capability-check` CLI cannot check an activity-scoped grant; verify the grant row and its audit event through Coordinator-approved read-only database access, then verify the actual authorization decision in CME invocation evidence. Do not use `activity-intake-accept` for this operation: it invokes as CME's configured module identity, while the telemetry operation requires Grace's canonical capability path.

**Scope limitation requiring Coordinator disposition:** CME currently authorizes by resident, capability, and optional activity ID. `resource_scope` is not passed to the configured grant provider, and the OctoMiner provider currently reads its configured host without applying invocation target filters. The package config fixes the source host to `octo1`, but this is configuration containment rather than host-level authorization. Do not claim source/host-scoped authorization. Before any managed activation, the Coordinator must either explicitly accept this limitation for a one-activity read-only trial with the configured host independently verified, or block activation until target-scope enforcement is implemented and reviewed.

The Coordinator performs the authorization preflight and approves the exact activity, target configuration, and activation window. CME checks authorization again for each invocation. A failed authorization check blocks invocation.

```sh
r3a --config /path/to/bootstrap.json config-reload \
  --idempotency-key octominer-config-register-2.0.0
r3a --config /path/to/bootstrap.json capability-module-install \
  --operation-id infrastructure.octominer.telemetry.read \
  --provider-version 2.0.0 --idempotency-key octominer-install-2.0.0
r3a --config /path/to/bootstrap.json capability-module-status \
  --operation-id infrastructure.octominer.telemetry.read --provider-version 2.0.0
r3a --config /path/to/bootstrap.json capability-module-activate \
  --operation-id infrastructure.octominer.telemetry.read \
  --provider-version 2.0.0 --idempotency-key octominer-activate-2.0.0
```

`capability-module-install`, `capability-module-activate`, and the durable module registry are the existing CME lifecycle. CME owns authorization and scheduling; registration and discovery do not authorize calls. Grace retains its decision authority and uses the canonical capability operation interface.

## 4. Verify discovery, health, and one operation

First collect status output and confirm it names `r3a.octominer-telemetry@2.0.0`, lifecycle `ACTIVE`, a healthy process/provider heartbeat newer than the activation time, and the installed artifact digest. A healthy process check does not prove the SSH source is reachable. Confirm the separately protected runtime configuration resolves to host ID `octo1`, a pinned `known_hosts` entry, and a read-only identity; do not print credentials or secret values into the evidence record.

For functional acceptance, an authenticated Steward asks Grace to perform one bounded, read-only OctoMiner telemetry check in the approved durable activity. Grace must select the registered canonical operation through its normal tool interface; CME performs authorization and scheduling. Do not invoke the provider directly or substitute the staging CLI path. Capture the request/activity ID before activation so the read-only grant can be scoped to that activity.

Retain the authenticated request reference, activity ID, invocation ID, module version, bundle and provider digests, CME/Website source build identities (not stale self-reported release labels), config revision, scoped grant row/audit event, authorization decision/audit event, start/finish times, provider health before/after, source IDs, collection timestamps, freshness, units, and output evidence digest. Missing host/config/dependency data must remain unavailable; it is not zero. The staging test uses synthetic local transport fixtures. Only the Coordinator may perform the managed-runtime invocation and confirm actual OctoMiner measurements.

## 5. Deactivate and roll back

First stop admission through the existing lifecycle and confirm the stopped state. Keep the previous package/configuration available until rollback verification completes. Record deactivation start/finish times and capture status before changing configuration:

```sh
r3a --config /path/to/bootstrap.json capability-module-deactivate \
  --operation-id infrastructure.octominer.telemetry.read --provider-version 2.0.0 \
  --idempotency-key octominer-deactivate-2.0.0
r3a --config /path/to/bootstrap.json capability-module-status \
  --operation-id infrastructure.octominer.telemetry.read --provider-version 2.0.0
```

Restore the prior `capability_operations` entry/configuration and apply `config.reload`; activate the retained previous provider version using its exact version. Do not replace a version's artifact or manifest in place. Recheck discovery, authorization, and prior provider health. Verify the new version is `STOPPED`, the previous version is `ACTIVE` with its original digest, and a read-only status request still succeeds. Record transition/event references, config revision, timestamps, and any restart. The Coordinator controls live configuration and any service restart; a restart requirement must be recorded in the release evidence and no hot-plug claim made.

## Acceptance record

Track these separately:

- **Package contract:** versioned manifest, declared operation/grant/dependencies, artifact hashes, deterministic bundle SHA.
- **Staging activation:** successful local install, registry discovery, provider activation, fixture-backed functional invocation, deactivation, and reactivation or rollback.
- **Authenticated live operation:** Coordinator-provided service/build/config identities, authorization and audit events, measured source freshness, invocation IDs, operator elapsed time, and rollback readback.

Measure installation separately from package construction and verification. From the reviewed checkout, run `python3 scripts/measure_octominer_module_install.py`; it builds and verifies the deterministic archive, installs into a fresh temporary root, and prints per-phase and total elapsed seconds. This is a repeatable local baseline. For the managed window, time the install command and record start/end timestamps separately from config reload, activation, provider health, invocation, and rollback; do not report local staging time as managed integration time.

Package and staging results do not imply managed live acceptance. Do not modify shared live services from an integration worktree. The managed install/config reload/activation sequence requires Coordinator approval and an Auditor review of the evidence bundle.
