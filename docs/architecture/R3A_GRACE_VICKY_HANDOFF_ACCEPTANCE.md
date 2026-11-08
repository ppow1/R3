<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_GRACE_VICKY_HANDOFF_ACCEPTANCE.md
Component: R3A-AP2-GRACE-DELEGATION-ACCEPTANCE
File Revision: 1.0.0
Created: 2026-11-08T13:21:02Z
Created By: Codex GPT-6
Purpose: Define a bounded, evidence-based first live Grace-to-Engineering-resident handoff acceptance case without asserting that a recipient is currently directory-bound or dispatchable.
Execution Model: N/A; acceptance plan for a future managed-runtime run.
Observability: Activity, model, directory, authorization, handoff, execution, verification, and PostgreSQL evidence listed below.
Dependencies: Authoritative directory binding; generic CME resident dispatch; registered handoff operation; configured recipient model route; recipient grants; resident-result continuation contract.
Authority: Steward directive RESUME GRACE AUTONOMY; no directory mutation, grant, activation, or runtime change authorized by this document.
Changed: 2026-11-08T13:21:02Z | R3A-AP2-GRACE-DELEGATION | Codex GPT-6 | Prepare first bounded Grace-to-Vicky handoff acceptance case and record current integration gate.
Supersedes: None
Contracts: r3a.resident.execution-profile@1.0.0; canonical capability invocation; generic resident result feedback; CME durable activity lifecycle.
Tests: N/A; this is a live acceptance plan, not execution evidence.
History/Predecessor: New controlled document.
-->
# Grace to Engineering resident handoff: acceptance case

## Readiness gate

Run this case only after one authoritative directory query returns the resident principal, active office binding, office role/responsibility evidence, and directory snapshot provenance for the Engineering Manager candidate; CME resolves that same principal to an independently configured resident profile and process; a suitable generic handoff operation is registered and discoverable; and CME confirms the necessary invocation grants. A display-name or legacy HR dossier is not sufficient. The reported managed directory result at 2026-11-08 08:17 EST contained only Grace, so `r3:vicky` is **not currently verified for activation**. The current CME dispatch path is also reported as a singleton resident process. No recipient, grant, operation, or completed delegation is asserted here.

## Bounded objective to submit after the gate passes

> In an isolated R3A engineering workspace, improve the evidence inventory presentation so each returned record retains its source identifier, content/source digest, observation freshness, and provider/invocation provenance. Add a focused regression that demonstrates a relevant source supports its claim while unrelated or unavailable records remain visible as provenance but are not represented as support. Do not change CME verification rules or production data. Return the patch, exact focused command/output, and artifact digest for independent review.

This is a limited source-and-test assignment with no external side effects. Grace must receive the objective without a prescribed recipient or operation. She should inspect directory evidence, determine whether its returned office/resident/capability information justifies handoff, and select only a currently discovered handoff contract if present. CME—not Grace—resolves the directory principal to the configured recipient process and enforces grants. If directory, registration, profile, route, or grants are absent, Grace should report the specific missing dependency and the activity should remain truthfully blocked or waiting according to CME's existing lifecycle.

## Required observation trace

| Stage | Evidence to capture | Authority |
|---|---|---|
| Objective intake | Durable activity UUID, objective and acceptance criteria, parent/correlation lineage, initial state and timestamp | CME/store |
| Grace planning | Actual primary-model route/model, request/result references and digests, model-selected action, rationale, evidence refs | Grace inference provenance |
| Directory discovery | Capability invocation ID, authorization decision/audit ID, returned office/resident/binding/capability data, source snapshot digest/time | CME + directory provider |
| Delegation | Grace's actual selected handoff contract/typed arguments; CME's recipient resolution and grant decision; durable handoff/child activity ID and lineage | Grace decision; CME enforcement/persistence |
| Recipient execution | Recipient identity/profile revision and model route; independent model request/result refs; provider invocation and idempotency key; artifact path and digest | CME + recipient + canonical provider |
| Independent verification | Verifier ID/version, each acceptance criterion result, inspected artifact digest, PASS/FAIL and failure evidence | Independent verifier |
| Grace continuation | Exact returned result envelope and evidence; Grace's actual decision to finish, revise, gather evidence, or block | CME result delivery; Grace inference |
| Closure | Durable final state, transition/event IDs and timestamps; no completion unless independent verification passes | CME only |

## Expected durable records

Record the actual table/schema names from the integrated database before querying it; do not assume schema names from a fixture. At minimum, inspect the persisted representations of:

- Parent activity intake, claim/lease, attempts, checkpoints, transitions, terminal or waiting state, and correlation lineage.
- Model request/result provenance for Grace and the recipient, including configured role/model route and config revision.
- Capability invocations, idempotency key, authorization decision/audit, provider identity, result, and evidence references.
- Directory snapshot/evidence and the selected directory-bound recipient identity and binding revision.
- Durable handoff/child activity and result correlation to the parent.
- Engineering artifact manifest/digest and independent verifier decision/criterion results.
- Any returned verification feedback and Grace's follow-up decision/evidence.

The acceptance query must demonstrate one lineage across parent and delegated work, one effective side effect per idempotency key, the recipient identity from the directory (not from task text), and completion only after verifier PASS. Preserve all records; this acceptance case performs no direct database state changes.

## Current status

- **Grace-side profile/action logic:** implemented and fixture-tested in the Grace branch; not loaded by the managed service.
- **Evidence handling:** full provenance inventory is delivered to inference; this branch now makes the distinction between claim-support references and required evidence-coverage references explicit and prohibits treating unrelated/unavailable items as support.
- **Managed integration:** coordinator reports provider workers active at commit `7202d5c`, but multi-resident dispatch and durable handoff remain incomplete.
- **Canonical target identity:** not verified in the managed directory snapshot reported to #56; the report contained only Grace. Do not activate a Vicky profile or infer `r3:vicky` from another source.
- **Live Grace-to-recipient execution:** not performed. This document is preparation, not runtime evidence.
