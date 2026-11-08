# R3A Engineering managed-runtime acceptance

This procedure is for the existing managed R3A development prototype after
the coordinator integrates the Engineering manifest/provider with its generic
provider lifecycle. It does not authorize this worktree to restart or activate
the shared runtime. Run it through the existing CME control and Grace inbox;
never call the provider entrypoint directly for live acceptance.

## Preconditions

- Managed CME loads `r3a_runtime/providers/isolated_workspace.manifest.json`
  through normal `capability_operations` configuration.
- External provider configuration points `workspace_root` at the already
  approved isolated Engineering workspace. Do not put that deployment path or
  credentials in the repository.
- The operation is enabled and dynamically discoverable. The coordinator's
  generic child-process lifecycle has installed and activated the digest-pinned
  provider. Its source digest matches the manifest.
- CME policy can grant the declared operation to authorized Grace for the
  specific workspace. Discovery itself is not authorization.
- Acceptance criteria designate one new artifact path under the assigned
  workspace and an independent verifier/profile supported by the work-order
  contract.

## Acceptance sequence

1. Send `capability.discover` through managed CME control without an
   `operation_id`. Record the descriptor, separate presentation (“Engineering
   Workspace Apply Patch”), contract and operation versions, effect class,
   provider identity/digest, target schema, lifecycle state, and explicit
   `authorization_evaluated: false` result.
2. Submit one bounded Engineering assignment as a normal Grace inbox objective
   with a unique idempotency key. Scope it to the configured workspace and one
   previously unused allowed artifact path. Do not grant broader paths or
   command profiles for this test.
3. Let Grace propose the operation from runtime-provided
   `available_engineering_operations`. Confirm CME resolves the discovered
   `(operation_id, contract_version)`, validates typed input/target and work
   order scope, checks the actual grant before provider execution, and persists
   invocation, authorization-decision, audit, and work-order evidence.
4. Confirm the provider runs under the generic provider child process and
   returns a contract-valid result. A provider return is not completion.
5. Run the configured independent verifier against the actual artifact. It
   must independently read the artifact, verify its digest and the work-order
   operation/workspace/path bindings, and emit a versioned `PASS` with evidence
   references. Confirm CME transitions the matching durable order to
   `COMPLETED` only after validating that PASS.
6. Repeat the same idempotent invocation and confirm recovery/replay behavior
   matches the work-order contract without duplicating or unexpectedly
   changing the artifact.
7. Submit an equivalent request under a principal without the required grant.
   Confirm CME records `DENY`, the result has
   `effect_disposition=NOT_STARTED`, and no artifact is created or changed.
8. Confirm the provider remains registered and usable after the coordinator's
   normal lifecycle activation/config reload or service restart. Record which
   lifecycle action occurred; this worktree does not restart a service.

## Evidence to attach to Issue #46

Record integrated branch/commit; CME and Ring 0 revisions; discovery descriptor
and presentation; provider module/version/digest/lifecycle state; objective,
activity, attempt, correlation, invocation and work-order IDs; scoped grant
decision and audit event; result contract-validation outcome; artifact path,
digest and independently observed contents; verifier ID/version/PASS/evidence
references; replay result; denial decision and proof the effect did not start;
and post-lifecycle discovery/invocation result. Redact secrets. Do not describe
fixture tests as live evidence.

## Current status

Prepared, not executed. Provider lifecycle activation and shared-runtime
coordination belong to the coordinator. This preparation changed or restarted
no managed service.
