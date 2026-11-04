<!--
R3 CONTROLLED DOCUMENT
File: hints/engineering-convergence-and-grounding.md
Component: ENG-CONVERGENCE-GROUNDING
File Revision: 1.0.0
Created: 2026-11-04 UTC (date only)
Created By: ChatGPT GPT-6, at Steward request
Purpose: Executive summary of recurring AI engineering drift and candidate corrective mechanisms
Execution Model: Reference and deferred proposals; not an active enforcement mechanism
Observability: Proposed metrics and evidence, not implemented
Dependencies: AI_HINTS.md; hints/README.md; hints/engineering.md; hints/deployment.md; docs/PARKING_LOT.md
Authority: Steward conversation; proposals require separate implementation authorization
Changed: 2026-11-04 UTC | R3-ENG-CONVERGENCE | ChatGPT GPT-6 | Initial conversation executive summary
Supersedes: None
Contracts: hints/file-provenance.md
Tests: Documentation-only; no deployment or functional tests
History/Predecessor: None (new file)
-->
# Executive summary — AI engineering convergence, grounding, and Grace execution discipline
**Status:** Parking-lot analysis and recommendations. **No implementation authorized.**
**Repository:** `ppow1/R3` only. Historical repositories are reference sources, not write destinations.
**Source:** Steward discussion on November 4, 2026, including direct GitHub inspection of five predecessor/current `AI_HINTS.md` files and a reported R3 login/grants deployment failure.

## Executive finding
Across Qmap Street, CueMastery, the Estate, Riverview, Riverview 2, and now R3, ordinary feature development has repeatedly expanded into unrelated architecture, verification, deployment investigations, additional processes and unfinished delivery. The pattern begins **during ordinary feature implementation**, not merely after major integration failures. Instructions and runbooks already exist; simply adding more prose instructions has not reliably changed assistant behavior. The corrective direction is **execution-time mechanisms that preserve the original objective, reuse established knowledge, constrain discretionary scope, and require real operational acceptance**.

The Steward reported that a routine periodic administrative operation ordinarily takes 5–10 minutes, yet its attempted website implementation consumed roughly two days. A website login was initially blocked by a preexisting secure-cookie conflict, and a subsequent authority-management UI rendered buttons but returned HTTP 503. These are examples of **passing internal tests or deploying a process without proving the actual requested user workflow**. The reports are user-provided operational evidence; this document does not independently verify the root causes.

## Established rules and practices — do not reinvent
- Repository-specific `AI_HINTS.md`, linked runbooks, host/SSH knowledge, and established deployment procedures already exist; consult them before troubleshooting or modifying systems.
- Nonblocking discoveries go to the existing GitHub punch list; do not hijack the active objective.
- Record progress and evidence durably in GitHub for outside monitoring.
- Reuse established scripts, components, branches/worktrees and runtime paths; avoid gratuitous new frameworks, services, repositories and local copies.
- Relevant permanent regression tests are expected; disposable one-off tests and excessive qualification are not a substitute for delivery.
- Use the established Comms gateway when applicable; on repeated failure, switch promptly to the clipboard-first terminal fallback rather than making gateway repair a side mission.
- Default to fixing development defects in place. Roll back only when actual operational harm or recovery needs justify it; failed pre-activation tests do not require rollback.
- Preserve explicit execution authority and resident-specific configurable read/write policy; do not invent blanket read-only or additional approval restrictions.
- For current R3 work, respect the Steward's LAN-only scope unless explicitly changed.
- R3 `AI_HINTS.md` is an index; substantive reference material belongs in `hints/`, with authoritative sources linked rather than duplicated.

## Candidate workstream A — deterministic, reusable deployment
**Goal:** Adapt the existing website deployment script and runbook for Grace and other R3 services, **not** build a parallel release framework.
**Proposed input:** exact repository, revision, target service and feature-specific acceptance criterion.
**Proposed flow:** confirm target/revision → build/compile → relevant existing permanent regression suite → deploy/activate via authorized existing process → verify running revision and health → test actual intended operation on the deployed LAN target.
**Distinct outcomes:** `BUILD_PASS`, `REGRESSION_PASS`, `DEPLOY_PASS`, `ACCEPTANCE_PASS`; never equate one with another. Report exact defect, running revision and evidence on failure. Preserve active production on predeployment failure; recovery on post-activation failure should be proportionate and based on actual service impact.
**Acceptance for this mechanism:** A repeatable command yields a trustworthy pass/fail result, with real-boundary evidence, without multi-hour discretionary investigation. First step is to obtain and inspect the **existing website script**, not invent a replacement.
**Status:** Proposed; existing script not inspected in this conversation.

## Candidate workstream B — automatic re-grounding for ChatGPT engineering conversations
**Problem:** Assistant behavior drifts after several turns despite earlier instructions, and the Steward must repeatedly send the model back to the repository rules.
**Proposed checkpoint:** initially every **five assistant responses** (tune to 10–15 based on evidence), and immediately after context compaction, handoff, change of objective, or material environment confusion.
**Checkpoint content:** reload active objective and original acceptance criteria; 4–5 prevailing constraints; exact repository/branch/revision and current verified state; `AI_HINTS.md` and task-relevant runbook; latest result and single next necessary action. Compare proposed action against scope before execution. Keep it short, avoid a new ritual that blocks work.
**Limitation:** a conversational instruction alone cannot guarantee automatic five-turn execution. A wrapper, controller or browser-side assistant may count turns and inject/retrieve the checkpoint. A manual `Read AI_HINTS.md and re-ground` instruction remains a fallback, not the final solution.
**Status:** Proposed; no automated checkpoint installed.

## Candidate workstream C — Chrome grounding monitor (parking-lot idea)
A browser extension could count assistant replies and approximate output growth, pin the current objective, five goals and four prevailing rules, and **notify or prepare a re-grounding message** after a configurable threshold (initially 5 responses; secondary character threshold approximately 10k–50k, not 1,000 characters). Consider conversation-specific state, explicit user review before insertion, no secret capture, and graceful handling of UI changes. The extension cannot force internal model attention or guarantee compliance. Prefer an integrated session wrapper if available; do not make this a prerequisite for Grace deployment.
**Status:** Idea only; no implementation authorization.

## Candidate workstream D — knowledge-first behavior for Grace and Riverview residents
Grace already has a database-driven durable state and event-driven/autonomic continuation design. These are significant protections against context loss and idle stalling, but **do not by themselves prevent incorrect task selection, unnecessary investigation or architecture expansion**.
Proposed execution-time behavior, ideally at the task dispatcher/policy or resident prompt/tool-selection boundary:
1. Bind every work step to a durable objective ID, original acceptance criterion, authorized scope and current state.
2. Before investigating a known operational problem, retrieve the relevant R3 knowledge-base entry, `AI_HINTS.md` pointer and canonical runbook; do not rediscover known host/procedure facts.
3. Compare each proposed action with the objective and existing implementation. Prefer the smallest proven change; require explicit justification/authorization for new permanent architectural layers or expanded scope.
4. Classify a finding as a genuine blocker or nonblocker; defer nonblockers to the existing punch list.
5. Persist progress, evidence, next action and blockers; use existing event-driven continuation instead of adding new autonomous loops or stages.
6. Preserve resident HR/profile-specific configurable tool access, including authorized read/write operations; do not hard-code read-only.
7. Mark completion only after the actual objective's acceptance evidence is obtained and independently verified where required.
8. Record when a policy prevented an action or when knowledge was missing, so the rule can be tested rather than merely asserted.
**Caution:** The Steward has described an existing ~33-step autonomic state machine and substantial anti-stall mechanisms. Inspect the actual implemented workflow before adding anything. Do **not** add a 34th process or duplicate memory, orchestration, governance, or approval machinery without demonstrated necessity.
**Status:** Behavioral design proposal, not a claim that Grace currently enforces these rules.

## Candidate workstream E — operational acceptance and truthful completion
The failure mode is **false completion**: tests pass and a process starts, while the requested browser workflow remains broken. Require a feature-specific **real-boundary acceptance test** against the actual deployed target, not only isolated unit tests, mock services or UI rendering. For login, a real browser session must log in, access a protected sitewide resource and log out. For any other feature, define the equivalent primary user workflow. A service HTTP 503, wrong running revision or unverified session must prevent `ACCEPTANCE_PASS`.
Keep testing proportional: the right end-to-end test, not another huge framework. Clearly distinguish verified facts, hypotheses and untested claims.
**Status:** Proposed reinforcement of existing testing policy; not a new claim that R3 lacks tests.

## Additional engineering guardrails discussed
- **Implementation-first authority:** ordinary feature requests authorize focused changes within the existing architecture, not independent redesign. New services, frameworks, identity systems or approval machinery require a demonstrated technical need and explicit authority.
- **No scope ratchet:** when a defect appears, first identify the smallest path back to the objective. Do not automatically escalate into rollback, log expansion, simulation and additional tooling.
- **Environment identity:** verify which process, revision and endpoint are actually serving the intended feature; deployment of a related institutional service does not prove website deployment.
- **Progress evidence:** report objective, verified state, blocker, next action and acceptance evidence; avoid lengthy activity reports mistaken for outcomes.
- **One objective at a time:** current Website Development priority is **unblocking Grace autonomy integration**. This process-improvement parking lot must not redirect that team into unrelated work.
- **Steward-intervention metric:** count scope corrections, time to actual acceptance, unnecessary rollbacks, repeated rediscovery, and features reported complete without operational evidence.

## Direct GitHub evidence examined
| Repository | Current AI_HINTS.md lines | Commit-history entries touching file | Earliest/latest entry |
|---|---:|---:|---|
| [CueMastery](https://github.com/ppow1/CueMastery/blob/main/AI_HINTS.md) | 75 | 12 | May 23–Jun 11, 2026 |
| [The Estate](https://github.com/ppow1/theestate/blob/main/AI_HINTS.md) | 96 | 11 | Jun 30–Aug 26, 2026 |
| [Riverview](https://github.com/ppow1/Riverview/blob/main/AI_HINTS.md) | 708 | 34 | Aug 14–Oct 17, 2026 |
| [Riverview 2](https://github.com/ppow1/Riverview-/blob/main/AI_HINTS.md) | 81 | 8 | Oct 9–Oct 22, 2026 |
| [R3](https://github.com/ppow1/R3/blob/main/AI_HINTS.md) | 52 | 8 | Oct 30–Nov 4, 2026 |

The five current default-branch files total **1,012 lines and 73 file-touching Git commits**. These counts do not mean 73 independent failures. The files already address re-grounding, recovery, no rediscovery, execution-first engineering, established runbooks, and provenance. The pattern shows repeated attempts to preserve hard-won knowledge, not proof that another instruction document will fix model behavior.

## Prioritization and non-authorization
1. **Immediate practical candidate:** inspect and adapt the existing deployment runner for Grace; do not block current Grace autonomy integration on this parking-lot work.
2. **Near-term experiment:** a short, measurable grounding checkpoint, initially every five assistant responses; verify whether intervention count falls.
3. **After Grace is operational:** inspect existing Grace dispatcher/policy and knowledge retrieval boundaries for a minimal enforcement change; preserve durable/event-driven architecture.
4. **Deferred:** Chrome extension or session wrapper prototype only if simpler mechanisms prove insufficient.
5. **Across all releases:** distinguish test/build/deploy success from objective-level operational acceptance.

**No implementation, deployment, repository restructuring, external-network work, or unrelated development is authorized by this document.** Preserve this summary in R3 only.