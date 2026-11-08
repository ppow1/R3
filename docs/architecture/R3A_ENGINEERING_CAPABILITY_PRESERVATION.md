# R3A Engineering capability preservation record

## Baselines

The modular workstream branch
`engineering/r3a-modular-plugins-20261106` was at
`ca2d29e47336dfb3d6a0e633c20bd31e1a200978`. The accepted unified branch
`integration/r3a-capability-unified-20261107` at
`f70b43da24e14014d31f1c2350a396dfb48fc006` is a descendant of that commit.
The modular branch worktree was fast-forwarded to the accepted descendant
before further edits. Its original remote ref remains unchanged until the
resulting preservation/conformance commit is pushed.

`git diff --name-status ca2d29e47336dfb3d6a0e633c20bd31e1a200978 f70b43da24e14014d31f1c2350a396dfb48fc006`
reports 33 changed paths, 4,098 insertions and 100 deletions. The 100
deletions are edits within shared files; there are no Engineering source files
deleted by the accepted unified baseline.

## Engineering preservation inventory

| Area | Preserved paths | Role |
|---|---|---|
| Work-order contracts and state | `r3a_runtime/engineering.py`; `r3a_runtime/state_machines/engineering_work_order.json`; `r3a_runtime/state_machines/engineering_work_order.json.provenance.md` | Typed assignment, proposal, work order, operation reference, verification result, lifecycle transitions and state-machine provenance. |
| Existing provider and independent verifier | `r3a_runtime/providers/isolated_workspace.py`; `r3a_runtime/engineering_verifier.py` | Idempotent, work-order-scoped isolated file writes and independent artifact verification. |
| Durable invocation and recovery storage | `r3a_runtime/migrations/005_event_history_persisted_at_idx.concurrent.sql`; `006_activity_created_at_idx.concurrent.sql`; `007_capability_invocations.sql`; shared `r3a_runtime/db.py` updates | Invocation idempotency/evidence storage, efficient event/activity recovery and Engineering persistence. |
| Common authorization, dispatch and contracts | Shared updates in `r3a_runtime/authorization.py`, `capability_contracts.py`, `cme.py`, `contracts.py`, `diagnostics.py`, and `grace_module.py` | The single CME dispatcher, invocation/grant enforcement, durable Engineering handoff and gated completion, diagnostic/resource projection, and Grace proposal/assessment path. |
| Direct and autonomous regression coverage | `tests/test_r3a_engineering.py`; `tests/test_r3a_engineering_autonomy.py`; `tests/test_r3a_capability_integration_demo.py`; shared updates to `tests/test_r3a_ap1.py`, `tests/test_r3a_capability_contracts.py`, and `tests/test_r3a_modular_autonomy.py` | Provider path safety, independent verification, interruption/idempotency recovery, authorization order, CME completion gate, Grace operations discovery and autonomy compatibility. |

The same diff also preserves the existing OctoMiner operation/provider and
contract fixtures, and adds the Riverview-only directory provider. Those are
modular workstream changes, not Engineering replacements. Exact changed paths
can be reproduced with the command above; the integration commit is the
preservation source and remains separately available for review.

## Generic operation registration

The Engineering operation is now described by
`r3a_runtime/providers/isolated_workspace.manifest.json` and its external
configuration example. The manifest pins the existing provider artifact and
declares typed inputs/outputs, `isolated_write`, caller and target scope,
required grant, evidence obligations, work-order idempotency, retry behavior,
and lifecycle state. It registers through the existing
`capability_operations` loader and `CapabilityRegistry`; it adds no
operation-specific CME branch or parallel registry. The workspace root is an
external provider-configuration value; the checked-in example uses only a
generic placeholder path.

The existing target contract discovers the workspace identity as a typed
target. The existing generic read-only diagnostics status projection discovers
the resource registry, including the workspace resource, health and metadata.
`lifecycle.desired_state=disabled` is excluded from normal discovery and
`CapabilityRegistry.resolve` rejects invocation of the disabled operation.
These semantics are covered by `tests/test_r3a_modular_capability_registration.py`.

The stable machine identity is `engineering.workspace.apply_patch` with
operation revision and contract version `1.0.0`; the shorthand
`engineering.workspace.apply_patch@1.0.0` denotes that identity/version pair.
The manifest presents it separately as “Engineering Workspace Apply Patch.”
Grace obtains isolated-write descriptors dynamically from
`CapabilityRegistry.discover()` and constrains the proposal schema to that
runtime-provided list. Consumers resolve the returned identity/version pair;
they need not embed the historical identifier. No alias is added because the
canonical operation contract has no alias field and dynamic discovery already
provides compatibility.

No generic operation resource-reference extension is needed for this provider:
the typed target and durable Engineering work order bind a workspace for each
invocation, while the existing resource registry supplies generic resource
discovery and health. The coordinator's AP0 module binding already has a
`resource_refs` field; the Engineering child process can leave it empty because
its workspace association is invocation-scoped, not a static provider
dependency. No new schema or registry is needed. If a future module must map a
typed target field to an authoritative resource identity, the smallest
versioned operation-contract proposal is optional
`resource_bindings: [{"resource_type": string, "target_json_pointer": string}]`
in a new operation-contract version; it should be resolved against the existing
resource registry at invocation time. That extension is not required or
implemented for Engineering.

The managed-runtime invocation and independent-verification acceptance
procedure is prepared in
`docs/architecture/R3A_ENGINEERING_MANAGED_RUNTIME_ACCEPTANCE.md`; it remains
unexecuted until the coordinator integrates the provider lifecycle.

The coordinator was asked whether the generic child-process lifecycle consumes
module `resource_refs` semantically or treats it as descriptive metadata. This
branch does not introduce descriptor fields or registry infrastructure.
