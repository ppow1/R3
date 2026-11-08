<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_RESIDENT_VERIFICATION_FEEDBACK.md
Component: R3A-AP2-RESIDENT-FEEDBACK
File Revision: 1.0.0
Created: 2026-11-08T00:02:00Z
Created By: Codex GPT-6
Purpose: Record the current CME verification-feedback boundary and propose the smallest generic result envelope for resident continuation.
Execution Model: N/A
Observability: Source references, versioned payload example, and fixture acceptance cases.
Dependencies: r3a_runtime/cme.py; r3a_runtime/grace_module.py; tests/test_r3a_ap1.py; Issue #43 coordinator agreement.
Authority: Steward directive R3A AP2 verification feedback; Grace cannot override verifier or CME completion authority.
Changed: 2026-11-08T00:02:00Z | R3A-AP2-VERIFICATION-FEEDBACK | Codex GPT-6 | Document the verification short-circuit and generic resident-result proposal.
Supersedes: None
Contracts: Proposed r3a.resident.result@1.0.0 inner payload; existing r3a.resident.execution.v1 remains unchanged.
Tests: Fixture-level coverage in tests/test_r3a_ap1.py; not live runtime acceptance.
History/Predecessor: New controlled document; no predecessor.
-->
# Grace verification feedback boundary

## Current CME path

The current path is `CME._run_activity` → `CME._run_engineering_activity` in `r3a_runtime/cme.py`.

1. CME invokes the authorized capability and persists `engineering.execution.succeeded` with the invocation result (currently around lines 1417–1420).
2. CME invokes `verify_workspace_artifact`, assembles the independent verifier output with artifact observations, and checkpoints `engineering.artifact.inspected` (lines 1431–1454).
3. CME calls Grace with that execution/artifact/verifier bundle for `engineering_assess` (lines 1455–1475). Thus Grace does receive the verifier output in this pre-verification assessment request. The boundary defect is that this request is explicitly about execution readiness, before CME's final verification checkpoint and completion gate; it is not a post-verification continuation request.
4. After Grace's assessment, CME checkpoints the verifier result and transitions the work order to `VERIFYING` (lines 1498–1506).
5. On any verifier outcome other than `PASS`, CME transitions the work order to `BLOCKED`, calls `store.block_activity(...)`, and returns (lines 1507–1517). It makes no resident call after this authoritative verification result is durably recorded, so Grace cannot choose a follow-up from the final result as a continuation decision.
6. Only a `PASS` proceeds to `complete_engineering_work_order(...)` and `finish_activity(...)` (lines 1518–1523).

Thus verifier authority is preserved, but failed verification currently terminates the activity before Grace receives the post-verification result as a continuation input. The verifier details happened to be included in Grace's earlier assessment payload; however, the requested assessment is not a continuation response to the authoritative verification gate, and CME does not permit a corrective decision/retry after that gate fails. Grace's pre-verification assessment is not a substitute for a post-verification decision.

## Proposed generic result envelope

This is an additive inner payload for the existing resident execution call; it does not create another RPC envelope, dispatcher, registry, authorization path, or lifecycle. The coordinator/CME owner must agree the final field names and arrange delivery before it can be used in the managed workflow.

```json
{
  "contract_id": "r3a.resident.result",
  "contract_version": "1.0.0",
  "activity_id": "activity UUID",
  "attempt_id": "attempt UUID",
  "correlation_id": "correlation UUID",
  "resident_id": "requesting resident",
  "config_revision": "resident configuration revision",
  "issued_at": "RFC3339 timestamp",
  "issuer": {"component_id": "verifier or institutional component", "decision_ref": "durable result reference"},
  "outcome": "PASS | FAIL | INCONCLUSIVE | REJECTED | RETURNED | UNAVAILABLE",
  "evidence": [{"evidence_ref": "durable evidence reference", "kind": "evidence type", "content": {}}],
  "failure_reasons": [{"code": "stable reason code", "message": "explanation", "evidence_refs": ["reference"]}],
  "completion_authority": false
}
```

All fields are required. Activity, attempt, resident, and configuration lineage must match the current resident execution. A non-PASS outcome must have at least one failure reason. `completion_authority` must be false: the result informs resident reasoning but confers neither capability authority nor acceptance authority. A result is evidence, not an instruction to trust arbitrary claims in its `content`.

Grace may respond through its existing action vocabulary: choose a currently offered capability, propose work where the existing generic proposal contract permits it, request an already authorized escalation, or return a truthful blocked decision. CME remains responsible for authorization, durable state transitions, retry/idempotency, verification gating, and completion. A Grace response cannot change verifier outcome or make a non-PASS result acceptable.

## Grace-side implementation in this branch

`GraceResident.handle("execute", payload)` validates an optional `resident_result` against contract version, identity lineage, timestamp, issuer provenance, outcome, evidence, and failure reasons before inference. It includes the validated result in the actual model request and retains it in the resident response provenance. A model response claiming `healthy` while the supplied result is non-PASS is rejected. Existing capability and proposal actions remain constrained to the manifest/assignment supplied by CME.

This branch does not change the CME caller, activity state machine, database records, or shared runtime. No claim is made that the managed runtime currently delivers this payload.

## Integration acceptance case

Using the existing managed contracts and isolated Engineering assignment:

1. Grace delegates/plans an objective; CME validates, authorizes, and dispatches it.
2. Engineering executes and persists invocation/artifact evidence.
3. The independent verifier records FAIL with criterion evidence.
4. CME persists a generic result envelope and supplies it to Grace on the same activity lineage before deciding whether the activity is blocked or can continue; CME must retain the no-completion-on-FAIL invariant.
5. Live 80B inference receives the exact verifier evidence. Grace chooses an offered authorized corrective action (or truthfully blocks if none is available); the action is not scripted by the harness.
6. CME persists the resident decision, invocation, continuation, and each verification result with the same objective lineage and idempotency protection.
7. A subsequent independent verification determines acceptance. Only CME may complete after verifier PASS; if it fails, the result is again returned for a resident decision or the activity is truthfully blocked.

Current tests in this branch are fixture/code-level checks of Grace payload validation and action selection. They do not establish CME integration, durable PostgreSQL history, actual 80B reasoning, or managed-runtime behavior.
