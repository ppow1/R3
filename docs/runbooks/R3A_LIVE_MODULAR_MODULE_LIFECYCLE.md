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

Before install or activation, verify the effective CME authorization for the intended principal/resident, operation `infrastructure.octominer.telemetry.read`, and the smallest applicable host/source scope. This release declares `infrastructure.octominer.telemetry.read`; it does not grant it. Use the existing audited grant/revocation controls under the Coordinator's authority and confirm the authorization decision records the intended exact scope. The check below is a preflight; CME checks authorization again for each invocation. A failed authorization check blocks invocation.

```sh
r3a --config /path/to/bootstrap.json config-reload \
  --idempotency-key octominer-config-register-2.0.0
r3a --config /path/to/bootstrap.json capability-check \
  --module-id r3a.octominer-telemetry \
  --capability-id infrastructure.octominer.telemetry.read
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

Confirm the status response names `r3a.octominer-telemetry@2.0.0`, lifecycle `ACTIVE`, and healthy provider diagnostics. Then invoke the normal read-only source acceptance path with the empty input declared by the operation contract:

```sh
r3a --config /path/to/bootstrap.json activity-intake-accept \
  --operation-id infrastructure.octominer.telemetry.read \
  --operation-contract-version 1.0.0 --input-json '{}' \
  --idempotency-key octominer-telemetry-acceptance-REPLACE-WITH-UUID
```

Retain the invocation/activity ID, module version, bundle digest, CME and Website build identities, grant decision/event IDs, start/finish timestamps, provider status, source IDs, freshness, units, and output evidence digest. Missing host/config/dependency data must remain unavailable; it is not zero. The staging test uses synthetic local transport fixtures. Only the Coordinator may perform the managed-runtime invocation and confirm actual OctoMiner measurements.

## 5. Deactivate and roll back

First stop admission through the existing lifecycle and confirm the stopped state. Keep the previous package/configuration available until rollback verification completes:

```sh
r3a --config /path/to/bootstrap.json capability-module-deactivate \
  --operation-id infrastructure.octominer.telemetry.read --provider-version 2.0.0 \
  --idempotency-key octominer-deactivate-2.0.0
r3a --config /path/to/bootstrap.json capability-module-status \
  --operation-id infrastructure.octominer.telemetry.read --provider-version 2.0.0
```

Restore the prior `capability_operations` entry/configuration and apply `config.reload`; activate the retained previous provider version using its exact version. Do not replace a version's artifact or manifest in place. Recheck discovery, authorization, and the prior health state. The durable CME module transitions are the rollback evidence. The Coordinator controls live configuration and any service restart; a restart requirement must be recorded in the release evidence and no hot-plug claim made.

## Acceptance record

Track these separately:

- **Package contract:** versioned manifest, declared operation/grant/dependencies, artifact hashes, deterministic bundle SHA.
- **Staging activation:** successful local install, registry discovery, provider activation, fixture-backed functional invocation, deactivation, and reactivation or rollback.
- **Authenticated live operation:** Coordinator-provided service/build/config identities, authorization and audit events, measured source freshness, invocation IDs, operator elapsed time, and rollback readback.

Package and staging results do not imply managed live acceptance. Do not modify shared live services from an integration worktree. The managed install/config reload/activation sequence requires Coordinator approval and an Auditor review of the evidence bundle.
