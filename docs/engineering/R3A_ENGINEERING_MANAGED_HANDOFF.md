# R3A Engineering managed integration handoff

Status date: 2026-11-08  
Owner: Engineering integration  
Verified isolated package: `r3a.isolated_workspace` 1.0.0  
Operation: `engineering.workspace.apply_patch` 1.0.0

## Boundary and ownership

Engineering owns the versioned module manifest, bounded workspace provider, work-order contracts, and independent verifier. CME owns activity scheduling, activity-scoped authorization, invocation, durable evidence, and the verification completion gate. Grace owns proposal selection and post-execution assessment. The #46 generic provider runtime owns module activation, health, deactivation, and recovery. The managed CME remains Coordinator-owned; this handoff does not activate or restart it.

The prior Engineering grant implementation rejected every effectful capability. The generic contract correction is the existing activity-scope rule: an effectful grant must include a canonical durable activity UUID, and authorization matches either a global read-only grant or the exact activity UUID. No Engineering-specific authorization bypass is required. The current Coordinator live-modular branch already contains this generic contract. The Engineering branch carries the same schema/API behavior for the isolated verification. The pending coordination comments on #43 and #46 document this boundary.

## Module package and lifecycle

Install the repository package in the managed CME's existing Python environment. The versioned manifest is `r3a_plugins/engineering_workspace/manifest.json`; its provider artifact SHA-256 is `0b92d126ed33c972ddee65d67b94c57794bcf64122ebe304c8a0e1ffeb064126`. It declares the operation input/output schema, `isolated_write` effect, required grant, target workspace schema, replay/idempotency contract, 30 second execution bound, and verification obligation `r3a.engineering-work-order-verification.v1`. The independent verifier contract is `r3a_plugins/engineering_workspace/verification_contract.json`.

Add an operation entry to the managed bootstrap's existing `capability_operations` array:

```json
{
  "manifest": "/path/to/R3/r3a_plugins/engineering_workspace/manifest.json",
  "configuration": "/etc/r3a/engineering-workspace.json"
}
```

The referenced JSON must point only at an isolated, disposable workspace owned by the Engineering service account:

```json
{"workspace_root":"/var/lib/r3a/engineering-workspaces/authorized-disposable-root"}
```

Add `engineering.workspace.apply_patch` to the existing `module.capabilities` list for the Grace resident. Keep existing entries. Do not make the operation a resident tool shortcut: CME presents it to Grace as a discovered Engineering operation only when a typed Engineering assignment is submitted. Grace returns the typed proposal; CME checks its operation, workspace, allowed paths, activity-scoped grant, and input schema before invoking the provider.

The operation catalog is loaded from bootstrap at CME startup; adding/removing `capability_operations` or changing Grace's capability discovery list therefore needs the Coordinator's approved CME configuration activation/restart window. The ordinary operation lifecycle below does not restart CME:

1. `capability-module-install --operation-id engineering.workspace.apply_patch --provider-version 1.0.0`
2. `capability-module-activate --operation-id engineering.workspace.apply_patch --provider-version 1.0.0`
3. `capability-module-status --operation-id engineering.workspace.apply_patch --provider-version 1.0.0`
4. For rollback, deactivate the operation, remove its operation entry and Grace discovery capability from the next approved bootstrap revision, then use the Coordinator's normal config activation procedure. Reinstall/reactivate with the same controls to recover.

The provider is stateless. Its version is immutable: a changed provider artifact needs a new provider version and manifest digest. A stale or unhealthy worker is restarted by the existing provider runtime. No CME restart is needed for ordinary provider lifecycle operations. Bootstrap operation/discovery-list changes follow the Coordinator's established config activation procedure.

## Authorization and invocation procedure

Create a UUID for the requested durable activity before submitting the Engineering assignment. Grant the canonical operation only to that exact activity:

```sh
r3a --config /path/to/managed-bootstrap.json capability-grant \
  --module-id resident.grace \
  --capability-id engineering.workspace.apply_patch \
  --reason "Approved bounded Engineering work order <change reference>" \
  --activity-id <activity-uuid>
```

Then submit through normal durable Grace objective intake, supplying the same `--requested-activity-id` and a validated `--engineering-assignment-json`:

```sh
r3a --config /path/to/managed-bootstrap.json grace-objective-submit \
  --objective "<bounded Engineering request>" \
  --requested-activity-id <activity-uuid> \
  --engineering-assignment-json "$(cat /path/to/engineering-assignment.json)" \
  --idempotency-key <unique-intake-key>
```

The assignment must identify the repository and baseline, one workspace ID, `allowed_paths`, bounded command profiles, criteria, verifier ID/version, and policy revision. CME persists the activity, then Grace chooses among the registry's discovered Engineering operations. Do not call the provider directly.

Activity scope prevents the grant from authorizing another activity. Current runtime has no generic grant-revocation CLI; rollback deactivates/removes discovery, while any remaining scoped grant is inert for other activity IDs. Coordinator should add a generic revoke operation before treating grant revocation as part of operational rollback.

## Isolated live verification

On 2026-11-08, an isolated CME was started against private PostgreSQL database `r3a_eng_ready` (port 55973) and disposable workspace `/tmp/r3a-eng-acceptance-final/workspace-grace`. No managed Coordinator CME or worktree was modified.

- Activity: `14e12d61-05ac-432a-810b-5659852ed80c`, state `COMPLETED`, one attempt.
- Work order: `6973c722-bdfe-5a1b-b0e6-479f2b931db0`, version 1, state `COMPLETED`.
- Grace selected `engineering.workspace.apply_patch` through the configured registry after real inference via the configured OpenAI-compatible 80B route. Model refs and digests are in `engineering_live_execution_evidence.json`.
- Scoped authorization: decision `d5b0f497-b49c-57bd-8d28-37f7f171faa3`; audit event `d9cf489f-0fae-47e7-811d-4850157939fd`.
- Provider invocation: `d5b0f497-b49c-57bd-8d28-37f7f171faa3`, `SUCCEEDED`, committed; wrote 301 bytes to `artifacts/engineering_result.json`, digest `7ab245366de8c977921f7af6dcec127659de8cbeb7439f4554a82c147d66e26a`.
- Independent verifier: `engineering.independent-workspace-verifier` 1.0.0, PASS on all three operation/scope bindings. Verification `680eadee-4052-4e6c-a088-4ebdbf253391`.
- Grace returned structured `ready_for_verification` feedback citing the invocation, inspected workspace artifact, and verifier. CME alone advanced the work order after verifier PASS.
- Module lifecycle was exercised on this isolated instance: installed, activated/healthy, deactivated/stopped, reactivated/healthy.
- The authorization, invocation, work order, activity result, and verifier result are durably stored in the isolated PostgreSQL database. A concise evidence export is committed alongside this handoff.

This run uses live Grace model inference, not synthetic/scripted resident reasoning. It does not establish managed Coordinator activation or live Grace selection in the managed runtime.

## Managed dependencies remaining

Coordinator must approve a disposable workspace root and activation window, install this package in the managed provider environment, add the operation/configuration and Grace discovery capability to the managed bootstrap, run migration 008 if its current database does not already carry activity-scoped grants, and issue an exact activity-scoped grant before the first work order. Autonomy must confirm the managed Grace route/runtime is compatible with `propose_engineering` and `engineering_assess`; Grace's model route must have sufficient timeout and request budget. #46 must continue to own provider protocol/lifecycle compatibility. Do not restart managed CME for this handoff.
