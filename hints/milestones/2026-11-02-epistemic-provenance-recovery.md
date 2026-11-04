# R3 — Epistemic provenance recovery and future integration checkpoint
Date: 2026-11-02
Status: HISTORICAL ARCHITECTURE RECOVERED; R3 IMPLEMENTATION NOT AUTHORIZED BY THIS RECORD
Scope: Resident-neutral epistemic accountability, provenance, knowledge catalog, configurable verification.
Priority: Preserve architectural compatibility while completing Grace's existing autonomous runtime qualification. No separate campaign.

## Purpose and hard boundaries
Recover and preserve existing Riverview/Estate decisions; do not redesign or reimplement historical systems prematurely. Keep R3 fast/light, resident-neutral, externally configurable, and proportional to task cost/risk. Classifying a resident's claim is NOT verifying that claim. Display colors are presentation, not epistemic authority. The knowledge catalog is not an authorization mechanism. Preserve Steward authority and independent Engineering acceptance.

## Recovered historical artifacts
1. Historical 2026-10-03 snapshot `Riverview-Full-System-Review-20261003-161150.txt` (ChatGPT Library; source excerpt inspected): `src/riverview/reasoning/epistemic.py` defined provider-neutral bitmasks VERIFIED=1, CANON=2, REASONED=4, GENERAL=8, CREATIVE=16, UNKNOWN=32; `ProvenanceRecord` with source_class, evidence_ref, observed_at, freshness, capability, source_refs. Source classes included institutional, live_telemetry, postgresql, river, local_artifact, repository, steward, canon, external_authoritative, web_research, cross_validation.
2. Same snapshot: `resident-epistemic-v1` provided optional per-span epistemic metadata, badges, and source drill-down; historical repair avoided a second provider inference solely to fix malformed provenance display metadata. Current deployment and exact white/green/purple palette remain unverified. Jessica REASONED / Grace repair attribution requires further historical reconciliation.
3. https://github.com/ppow1/Riverview-/issues/161 — OPEN punch-list: claim-level grounding, provenance, uncertainty, source freshness/conflicts, factual vs creative/personality distinction; cites historical `ResidentConversationGateway.from_evidence()`, RV-014.1, RV-018.6, provenance/classification/certainty. Records actual false citations to nonexistent contract paths. Historical gateway implementation not yet independently inspected.
4. https://github.com/ppow1/Riverview-/issues/159 — OPEN/PARKED: `AI_HINTS.md` should be a small catalog to authoritative knowledge, runbooks, resource indexes, host/IP/SSH records and verified experience. Do not duplicate dynamic facts into root hints; preserve correction history and source authority; do not claim persistence without receipt. No knowledge-store refactor authorized.
5. `ppow1/theestate`: `src/estate/core/readiness_evidence_projection.py`, `docs/architecture/campaign_0681_readiness_evidence_projection.md`, `collaboration/work_packages/pending/WP-0698_READINESS_VALIDATION_AND_EVIDENCE_SIGNAL_UNIFICATION.md`. Read-only operational evidence projection handles source precedence, identity, freshness, supersession, contradictions and protected acceptance; it is NOT a conversational epistemic verifier or action authority.
6. November 2 discussion: possible verification modes are self-review, independent review, selective combined review. Configurability across institution defaults and resident overrides is required; final mode names/default/triggers/cost thresholds NOT decided.

## Current R3 seams (inspected GitHub branch engineering/institution-runtime-v1-20261101)
- `runtime/resident_inference.py`: `Inbox` durable `resident_inbox` and `resident_turns` (ASSISTANT, TOOL_INTENT, TOOL_RESULT); `ResidentInference.__call__` performs tool reasoning, JSON activity decisions, and durable continuation via `Inbox.continue_activity`.
- `runtime/configuration.py`: `load_configuration` reads external runtime/resident JSON and validates resident settings.
- `runtime/serve.py`: constructs generic resident handlers from configuration.
- `config/residents/grace.json`: resident-specific external settings.
- `tests/test_activity_continuation.py`: permanent synthetic regression for cross-activation continuation, ordinary responses, invalid decision, blocked state.
- No R3 epistemic processor, inheritance contract, claim-to-source validation, or independent reviewer has been verified. Do not claim otherwise.

## Live Grace evidence and qualification gap
2026-11-02 Camrui SQLite journal events 5, 6, 7: all COMPLETED, each independently called `r3.status` and `r3.host.uptime`, recorded actual tool outputs, separated observed vs inferred text, and chose complete. This verifies within-event tool reasoning and journal, NOT global Riverview health or truth of broad stability claims. Events 6 and 7 explicitly requested a two-stage separate activation; both instead called both tools and completed in ONE activation. No `continuation_event_id` for 5–7. Therefore live cross-activation continuation remains UNVERIFIED despite permanent tests. Do not mark passed.

## Near-term integration boundary — NOT implementation authorization
1. First qualify genuine live cross-activation continuation without weakening Grace's general-purpose autonomy or adding disposable tests.
2. At a convenient point in existing runtime work, inspect response finalization/configuration for a minimal OPTIONAL resident-neutral epistemic processor hook; reuse historical classification/provenance contracts rather than inventing new ontology.
3. Preserve existing journal evidence references; avoid second evidence store, second scheduler, new service, and mandatory extra model pass.
4. Support persistent institution-wide defaults with resident-specific overrides; future processor selection and review policy must remain externally configurable, not hardcoded in Grace.
5. Ensure ordinary resident activities still complete if advanced verification is disabled; metadata is not a certification of truth.
6. Add permanent regression tests when actual integration is authorized. No deployment or implementation is implied by this milestone.

## Future work / unresolved decisions
- Reconcile exact historical implementation, tests, October 3 Grace/Jessica repairs, and Estate gateway/RV-014.1/RV-018.6 contracts.
- Determine claim-level classification and evidence-reference schema, verification authority, freshness/conflict handling, uncertainty calibration and false positive/negative evaluation.
- Decide self-review vs independent vs selective combined review; per-resident policy inheritance, escalation triggers, cost/risk budgets, and handling review failures.
- Link established institutional experience (IPs, SSH aliases, corrections, verified procedures) to canonical source records through existing catalog without copying dynamic state.
- Reuse optional span-level UI and provenance explanations; confirm historic color mapping (white facts, green reasoning, purple unknowns) and accessibility.
- Keep conversational epistemic labels distinct from operational readiness/acceptance, permission/approval, and Engineering verification.

## Existing tracking
- R3 controlling roadmap: `hints/milestones/2026-11-02-r3-six-phase-roadmap-phase1.md`.
- Riverview punch list: https://github.com/ppow1/Riverview-/issues/161 and https://github.com/ppow1/Riverview-/issues/159.
- This checkpoint is a preservation/reference document, not a new project, new work order, or approval to interrupt the autonomy milestone.
