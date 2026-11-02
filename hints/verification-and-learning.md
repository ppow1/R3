<!--
R3 CONTROLLED DOCUMENT
File: hints/verification-and-learning.md
Component: R3-VERIFICATION-LEARNING
File Revision: 1.0.0
Created: 2026-11-02 UTC (date known; exact time unverified)
Created By: ChatGPT GPT-6
Purpose: Define the proposed lightweight verification, nonconvergence escalation, and continuous-improvement contract.
Execution Model: Design guidance only; not deployed runtime behavior.
Observability: Future durable criterion reviews, correction lineage, and learning records.
Dependencies: R3 resident inbox and institution journal; future institutional knowledge base.
Authority: Steward discussion 2026-11-02; implementation subject to review.
Changed: 2026-11-02 UTC | R3-VERIFY-LEARN-001 | ChatGPT GPT-6 | Record verification and continuous improvement requirements.
Supersedes: None
Contracts: hints/engineering-test-policy.md; docs/PROJECT_CHARTER_REVISION_2_REVIEW.md
Tests: N/A — documentation-only proposal; permanent general-purpose regressions required when implemented.
History/Predecessor: New document.
-->
# Verification, nonconvergence, and institutional learning

**Status: Proposed contract; not yet implemented.** Keep R3 fast, light, self-contained, and resident-neutral. Do not import R2's verification machinery.

## Separate the records

- **Objective and proposal:** desired outcome, rationale, and possible approach; not an exact implementation template.
- **Versioned acceptance criteria:** stable criterion IDs, required outcomes, allowed tolerances or equivalences where relevant, and evidence expectations. Criteria may be qualitative or quantitative; do not force exact text matching.
- **Execution evidence:** observed result, artifacts, tests, tool results, and links to the implementing activity.
- **Independent review:** for each criterion ID, record pass, fail, or insufficient evidence; concise reason and supporting evidence. Never equate the executor's `objective_verified=true` with independent acceptance.
- **Correction lineage:** retain review ID, criterion ID, failure reason, implementation revision, correction attempted, and subsequent outcome. A second rejection of a different criterion is not inherently nonconvergence.

## Evaluation and recovery

A review asks whether the evidence materially meets the agreed criteria, not whether implementation wording exactly matches a proposal. Exact equality applies only when the criterion genuinely requires it (e.g. checksum or protocol contract).

Return actionable unmet criteria to the responsible executor. Distinguish (a) new or exposed defects, (b) persistence of the same defect, (c) regressions/oscillation across criteria, (d) reviewer disagreement, (e) missing evidence, and (f) verifier infrastructure failure. A verifier crash or uncertainty must not turn a previously completed implementation into a failure or block unrelated work. Preserve durable attempts and resume safely.

## Escalated reasoning

Escalated reasoning is an **institutional capability**, not a mandatory stage of every verification. It may be invoked for repeated nonconvergence, oscillation, contradictory interpretation, or difficult diagnosis, and for other institutional purposes outside verification. Use a compact bundle of objective, criterion versions, evidence, review reasons, and correction history. Ask for root-cause diagnosis and an actionable next step; do not let escalation invent evidence, silently change criteria, or overrule Steward authority. Avoid a hardcoded rejection-count limit; use progress patterns and externally configurable policy.

## Continuous improvement: every meaningful rejection is feedback

Record both **task-level remediation** and **process-level learning**. Determine whether a rejection stems from implementation, underspecified/ambiguous criteria, flawed proposal, inadequate evidence, verifier error, or other causes. These are hypotheses until supported; distinguish observations from inferences.

Example: if Engineering's first result failed because a proposal omitted a necessary precision or tolerance, correct the current assignment and record the omission as a candidate lesson. After sufficient evidence, improve the relevant proposal/acceptance-criteria guidance or reusable boilerplate so future work orders specify the required tolerance. Do **not** automatically rewrite institutional templates based on one potentially mistaken review.

A lightweight knowledge record should identify: source assignment/review, affected criterion(s), observed failure, causal hypothesis and confidence, correction/outcome, reusable recommendation, validation status, and any resulting template/guidance revision. Keep the original record and revision lineage. Promote supported lessons to validated guidance; allow later correction or supersession. This cycle should be shared across residents and institutional operations, not hardcoded to Grace or Engineering.

## Implementation boundary

Inspect existing R3 inbox/journal and knowledge mechanisms before introducing schema or services. Prefer minimal durable records and reusable functions over a new workflow engine. Do not add one-off tests, artificial objective/retry limits, or scenario-specific gates. Implement permanent tests for criterion identity across revisions, independent acceptance, new-vs-repeat rejection, oscillation, verifier failure recovery, and evidence-based lesson promotion when the corresponding capability is built.
