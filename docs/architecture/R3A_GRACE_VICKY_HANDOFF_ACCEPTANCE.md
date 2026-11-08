<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_GRACE_VICKY_HANDOFF_ACCEPTANCE.md
Component: R3A-AP2-GRACE-DELEGATION-ACCEPTANCE
File Revision: 1.1.0
Created: 2026-11-08T13:21:02Z
Created By: Codex GPT-6
Purpose: Define a bounded, evidence-based first live Grace-to-Engineering-resident handoff acceptance case without asserting that a recipient is currently directory-bound or dispatchable.
Execution Model: N/A; acceptance plan for a future managed-runtime run.
Observability: Activity, model, directory, authorization, handoff, execution, verification, and PostgreSQL evidence listed below.
Dependencies: Authoritative directory binding; generic CME resident dispatch; registered handoff operation; configured recipient model route; recipient grants; resident-result continuation contract.
Authority: Steward directive RESUME GRACE AUTONOMY; no directory mutation, grant, activation, or runtime change authorized by this document.
Changed: 2026-11-08T13:21:02Z | R3A-AP2-GRACE-DELEGATION | Codex GPT-6 | Prepare first bounded Grace-to-Vicky handoff acceptance case and record current integration gate.
Changed: 2026-11-08T15:37:17Z | R3A-CHARACTER-CONTEXT-CONSUMER | Codex GPT-6 | Add approved character-context and revision-pinning observations to the future handoff acceptance.
Changed: 2026-11-08T17:31:16Z | R3A-CHARACTER-CONTEXT-V2 | Codex GPT-6 | Reference Character Architecture's approved v2 activity/conversation pin contract.
Changed: 2026-11-08T17:34:06Z | R3A-CHARACTER-CONTEXT-V2 | Codex GPT-6 | Record the immediate predecessor revision.
Changed: 2026-11-08T18:29:46Z | R3A-ENGINEERING-RELEASE-CONTRACT | Codex GPT-6 | Add the manifest-pinned workspace operation, invocation grant scope, bounded provider config, and explicit live handoff gates.
Supersedes: None
Contracts: r3a.resident.execution-profile@1.0.0; r3a.resident.approved-character-context@2.0.0; r3a.capability-operation.v1; r3a.capability-invocation.v1; r3a.engineering-work-order.v1; r3a.verification-result.v1; generic resident result feedback; CME durable activity lifecycle.
Tests: tests/test_r3a_engineering_provider.py; live handoff remains unperformed.
History/Predecessor: Prior revision preserved at commit 6c4f4e6d5b7f3f5c55b37fe34b0cf09b1fe47d65, blob ea0a5580f760e8d8c1b084fe4798029e34fe0cfb.
-->
# Grace to Engineering resident handoff: acceptance case

## Readiness gate

Run this case only after one authoritative directory query returns the resident principal, active office binding, office role/responsibility evidence, and directory snapshot provenance for the Engineering Manager candidate; CME resolves that same principal to an independently configured resident profile and process; a suitable generic handoff operation is registered and discoverable; and CME confirms the necessary invocation grants. A display-name or legacy HR dossier is not sufficient. The reported managed directory result at 2026-11-08 08:17 EST contained only Grace, so `r3:vicky` is **not currently verified for activation**. The current CME dispatch path is also reported as a singleton resident process. No recipient, grant, operation, or completed delegation is asserted here.

Before live inference, the governed Character Architecture provider must return `r3a.resident.approved-character-context@2.0.0` for the exact `inference_activity` boundary and activity UUID. Its durable `pin_ref` binds the approved active dossier revision/digests to verified HR identity, directory snapshot/binding and provider. Grace's parent objective remains pinned to Grace's character revision; the delegated activity is separately pinned to Vicky's revision. A refreshed authorization observation may change, but a resumed activity must reload the same pin. Do not place protected HR/relationship material in either prompt, messages, memory, or diagnostics. If the approved active dossier or identity crosswalk is missing, report that dependency; do not fill it with a draft or fixture.

## Engineering operation and authorization contract

This branch now packages the existing canonical provider at `r3a_runtime/providers/isolated_workspace.py` with `r3a_plugins/engineering_workspace/manifest.json` and an external `config.example.json`. The stable operation ID remains in the operation manifest; Grace receives its dynamically discovered human label and typed contract. The provider creates one new UTF-8 file under both the authorized work order path allowlist and configured workspace root. It refuses different existing bytes, supports identical replay, rejects path escape, and enforces the configured `maximum_file_bytes`. This is a file-creation operation; it does not edit or overwrite existing files.

For managed activation the Coordinator must install/register the manifest through the existing module/capability lifecycle, pin both the manifest adapter and provider SHA-256 values, and set `workspace_root` to a dedicated isolated workspace root with an institutionally chosen `maximum_file_bytes`. The registry operation requires the exact grant named in the manifest. CME must authorize that grant for the same durable activity before provider invocation; AP0's existing grant store supports an activity-scoped grant. The durable Engineering work order must additionally bind the selected workspace ID, repository/baseline metadata, allowed relative paths, operation reference, proposal digest, and explicit criteria. Discovery alone grants nothing. The provider's returned digest is execution evidence only; an independent verifier must re-read the bytes and evaluate the work-order criteria before CME can complete it.

No live grant, workspace, provider registration, Vicky profile, or managed activation is asserted by this package. Exact deployment roots and the institutional grant owner/value are deployment-specific configuration and must be reported from the active managed registry/configuration, not inferred from this example.

## Bounded objective to submit after the gate passes

> In an isolated R3A engineering workspace, improve the evidence inventory presentation so each returned record retains its source identifier, content/source digest, observation freshness, and provider/invocation provenance. Add a focused regression that demonstrates a relevant source supports its claim while unrelated or unavailable records remain visible as provenance but are not represented as support. Do not change CME verification rules or production data. Return the patch, exact focused command/output, and artifact digest for independent review.

This is a limited source-and-test assignment with no external side effects. Grace must receive the objective without a prescribed recipient or operation. She should inspect directory evidence, determine whether its returned office/resident/capability information justifies handoff, and select only a currently discovered handoff contract if present. CME—not Grace—resolves the directory principal to the configured recipient process and enforces grants. If directory, registration, profile, route, or grants are absent, Grace should report the specific missing dependency and the activity should remain truthfully blocked or waiting according to CME's existing lifecycle.

## Required observation trace

| Stage | Evidence to capture | Authority |
|---|---|---|
| Objective intake | Durable activity UUID, objective and acceptance criteria, parent/correlation lineage, initial state and timestamp | CME/store |
| Grace planning | Actual primary-model route/model, request/result references and digests, model-selected action, rationale, evidence refs, approved context revision/digest and classification scope | Grace inference provenance |
| Directory discovery | Capability invocation ID, authorization decision/audit ID, returned office/resident/binding/capability data, source snapshot digest/time | CME + directory provider |
| Delegation | Grace's actual selected handoff contract/typed arguments; CME's recipient resolution and grant decision; durable handoff/child activity ID and lineage | Grace decision; CME enforcement/persistence |
| Recipient execution | Recipient identity/profile revision, its own approved character-context revision/digest, and model route; independent model request/result refs; provider invocation and idempotency key; artifact path and digest | CME + recipient + canonical provider |
| Independent verification | Verifier ID/version, each acceptance criterion result, inspected artifact digest, PASS/FAIL and failure evidence | Independent verifier |
| Grace continuation | Exact returned result envelope and evidence; Grace's actual decision to finish, revise, gather evidence, or block | CME result delivery; Grace inference |
| Closure | Durable final state, transition/event IDs and timestamps; no completion unless independent verification passes | CME only |

## Expected durable records

Record the actual table/schema names from the integrated database before querying it; do not assume schema names from a fixture. At minimum, inspect the persisted representations of:

- Parent activity intake, claim/lease, attempts, checkpoints, transitions, terminal or waiting state, and correlation lineage.
- Model request/result provenance for Grace and the recipient, including configured role/model route and config revision.
- The pinned character-context contract/version, pin reference, verified resident binding, identity and dossier revisions/digests, context/prompt digest, classification scope, provider, and durable activity boundary. Full prompt text, personality values, authorization references, and HR/directory source references must not be copied into inference diagnostics; the governed pin store retains those references.
- Capability invocations, idempotency key, authorization decision/audit, provider identity, result, and evidence references.
- Directory snapshot/evidence and the selected directory-bound recipient identity and binding revision.
- Durable handoff/child activity and result correlation to the parent.
- Engineering artifact manifest/digest and independent verifier decision/criterion results.
- Any returned verification feedback and Grace's follow-up decision/evidence.

The acceptance query must demonstrate one lineage across parent and delegated work, one effective side effect per idempotency key, the recipient identity from the directory (not from task text), and completion only after verifier PASS. Preserve all records; this acceptance case performs no direct database state changes.

## Current status

- **Grace-side profile/action logic:** implemented and fixture-tested in the Grace branch; not loaded by the managed service.
- **Evidence handling:** full provenance inventory is delivered to inference; this branch now makes the distinction between claim-support references and required evidence-coverage references explicit and prohibits treating unrelated/unavailable items as support.
- **Managed integration:** coordinator reported the managed Ring0/CME baseline at `c1818d5`; multi-resident dispatch and durable handoff remain incomplete.
- **Character context:** the Grace consumer is fixture-tested against v2; no approved active Grace dossier/context has been delivered to inference in a managed run. The authoritative Grace HR-to-directory crosswalk remains unverified, so this document makes no operational character-continuity claim.
- **Canonical target identity:** not verified in the managed directory snapshot reported to #56; the report contained only Grace. Do not activate a Vicky profile or infer `r3:vicky` from another source.
- **Live Grace-to-recipient execution:** not performed. This document is preparation, not runtime evidence.
- **Engineering provider package:** implemented and isolated-tested in this branch; manifest and provider artifacts are digest-pinned; managed registration, workspace configuration, activity-scoped grant, and live invocation are not verified.
