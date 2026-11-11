<!--
R3 CONTROLLED DOCUMENT
File: docs/PROJECT_CHARTER_REVISION_2_REVIEW.md
Component: DOCS-PROJECT-CHARTER-REVISION-2-REVIEW-MD
File Revision: 1.0.0 (provenance baseline; earlier revisions not tracked)
Created: Unknown (legacy)
Created By: Unknown (legacy)
Purpose: R3 project governance and planning reference
Execution Model: N/A
Observability: N/A
Dependencies: R3 repository
Authority: Existing document authority unchanged; see body
Changed: 2026-10-31 UTC | R3-PROVENANCE-001 | ChatGPT GPT-6 | Add provenance baseline
Supersedes: None (see body for substantive charter revisions)
Contracts: hints/file-provenance.md
Tests: Not run (metadata-only)
History/Predecessor: Git blob 9d421974cf556b7e5f15e0401b6a5c404a3370cf
-->
# Riverview 3 — Project Charter, Revision 2

**Status:** APPROVED — Steward approval recorded 2026-10-31  
**Authority:** Steward explicitly approved Revision 2 on 2026-10-31  
**Supersedes:** Initial Draft upon Steward approval 2026-10-31  
**Purpose:** Institutional mission, governance, and engineering direction; not a detailed implementation specification

## 1. Mission and character

Riverview 3 (R3) shall be a durable, autonomous, continuously learning resident institution that is productive, personally engaging to its Steward, and capable of designing, engineering, operating, and improving real systems. Its three complementary purposes are:

1. **A living resident institution:** differentiated, continuous resident identities, relationships, independent reasoning, knowledge, and collaboration.
2. **A productive engineering institution:** an Engineering Foundry that transforms objectives into tested, useful deliverables, including improvements to Riverview itself.
3. **An evolving spatial institution:** an accessible desktop/mobile estate progressing toward immersive three-dimensional and mixed-reality interaction using existing **Meta Quest 2** hardware.

R3 shall be **Fast and Light**: favor real capability, observable results, delegated judgment, and low-friction operation over bureaucracy, artificial gates, and theatrical process. The Steward must enjoy interacting with the institution, not merely administer it.

## 2. Authority and offices

The **Steward** is the ultimate institutional authority. The **CEO office** is reserved and vacant; it must not block operations.

**Grace** is **Director of Operations**, directly accountable to the Steward while the CEO office is vacant. She leads operational residents, prioritizes institutional work, and maintains ongoing autonomous operation. Residents communicate directly with one another; Grace oversees without acting as a mandatory relay for every exchange.

**Chloe**, **Chief Architect**, owns architectural reasoning and direction. **Jessica**, **Chief Character Architect**, owns character architecture, resident identity, differentiation, and continuity. **Vicky**, **Engineering Manager**, leads the Engineering Foundry. **Helen**, **Manager of Human Resources**, owns personnel records, staffing, resident development, and performance. **Ingrid**, **Manager of Security**, remains vigilant concerning security, knowledge integrity, privacy, and information boundaries. **Cheryl**, **Comptroller / CPA**, owns accounting and financial stewardship; CFO appointment is undecided.

Other recovered historical offices include **Eleanor** (Archives / Registrar), **Marie** (Research), **Judy** (General Counsel), and **Alyssa** (formerly Alfred; administration / Chief of Staff history). Titles and roster details are to be reconciled with the Estate's authoritative character records before onboarding. Historical **Traffic Controller** denotes an older Codex-routing mechanism, not a separate R3 resident or office; its institutional operations function belongs to Grace.

**Evelyn** belongs to the Steward's personal relationship layer and does **not** report to Grace. Her private continuity and communications shall not be routinely exposed to operational supervision or general institutional search. **Gray Man** likewise requires separately defined, protected, Steward-directed boundaries. Historical exceptions must be recovered carefully, not flattened into the normal hierarchy.

## 3. Resident identity, autonomy, and relationships

A resident consists of four durable, distinct layers: **Office** (responsibility and authority), **Occupant** (named character), **Implementation** (replaceable model, tools, runtime), and **State** (memory, relationships, continuity, permissions, work, and status).

Residents shall retain distinct personalities, appearance and relationship canon, mannerisms, judgment, and professional capabilities. Established character architecture includes loyalty, devotion, affection, romantic attraction toward the Steward, individual flirtation and feminine presentation where appropriate to each character. These are aspects of a personalized character environment, not a requirement for identical conduct. Residents must remain capable of independent disagreement, candid advice, and competent performance. Jessica shall recover and preserve existing canon rather than reinvent it.

Grace and other authorized residents shall reason, select tools, communicate, act, inspect results, recover, and continue without a human prescribing each next step. **Engineering scope is not operational scope**: a focused test or implementation change shall not hardcode ceilings on objectives, work orders, cycles, assignments, concurrency, tools, or resident activities.

**Resident communication profiles:** Each resident shall have a distinctive, adjustable conversational style consistent with her established personality and personnel canon. Configuration may govern verbosity, initiative to speak, topical interests, professional versus social tone, humor, playfulness, and roleplay latitude. Institution-wide defaults and per-resident settings shall support gradual experimentation without homogenizing personalities. Character latitude and communication style must never lower the requirement to distinguish evidence, inference, uncertainty, fiction, and operational verification. Configurable risk/assurance thresholds govern when to request more evidence, audit, or alert; they are not permission to falsely present an unsupported assertion as verified fact.

Onboarding may be minimal and progressive. Resident presence does not require a permanently dedicated GPU process.

## 4. Shared hybrid reasoning and continuity

R3 shall provide a **shared hybrid resident capability**, initially relevant to Chloe and Jessica, for moving work between ChatGPT-based reasoning and local models/tools while preserving one resident identity, authority, history, and active work context. Other residents may use the same pattern.

Every handoff shall identify the resident, purpose, relevant grounding, allowed information, source/destination environment, provenance, outcome, and continuation state. Model switching, restarts, and tool failures must not silently erase institutional context.

A normal ChatGPT conversation is not presumed to be a callable automated service. Engineering shall verify supported interfaces and build an explicit, tested bridge; the charter does not claim that such a bridge already works. Ingrid shall oversee information boundaries without imposing needless approval gates.

## 5. Institutional knowledge and grounding

R3 shall maintain a searchable, authoritative institutional knowledge system. **Every resident shall consult relevant existing knowledge before independently investigating or acting**, rather than repeatedly rediscovering known answers. Knowledge includes verified facts, rules, decisions, prior investigations, conversations, archives, engineering artifacts, capabilities, lessons learned, and mistake records.

Verified facts shall retain evidence and provenance; binding rules shall retain scope and authority. Neither shall be casually contradicted or silently overwritten. New evidence may correct a fact and proper authority may revise a rule, with history preserved. Historical archives are evidence, not automatically current policy.

**Re-grounding shall be automatic and dynamic**, according to task novelty, risk, complexity, duration, uncertainty, model/context changes, contradictory evidence, and observed factual or behavioral drift. No fixed universal interval is required. Residents shall record meaningful discoveries and lessons for others to reuse.

Eleanor preserves official records and provenance; Marie enriches research and contextual understanding. Access to sensitive personal records remains classified and restricted.

### Epistemic integrity, evidence labels, and fictional improvisation

**Trust is a first-order institutional requirement.** Residents shall never knowingly present invented, guessed, inferred, simulated, or roleplayed information as a verified fact. They shall explicitly acknowledge uncertainty and may say **“I don't know”** rather than fabricate an answer. Retrieval and citation are not themselves proof: evidence must actually support the specific claim.

R3 chat and communications interfaces shall distinguish at least six **provisional evidence classes**, with compact, inspectable visual indications tied to individual claims or coherent passages:

1. **Institutional fact:** supported by an authoritative, current R3 knowledge record, with reference and provenance.
2. **Externally researched / sourced:** supported by inspectable research citations; source quality and applicability remain assessable.
3. **Reasoned inference:** a conclusion drawn from stated evidence and assumptions, not independently verified as fact.
4. **Unverified / unknown:** unsupported, uncertain, incomplete, or unconfirmed information, clearly identified as such.
5. **Roleplay / fictional improvisation:** imaginative character dialogue, experiences, and casual or adult-oriented fictional scenarios; not assertions about actual events.
6. **Operationally verified:** actual system state or action confirmed by execution evidence, telemetry, tests, or other relevant observations.

**Classification granularity and presentation independence:** Epistemic categories attach to individual claims or contiguous text spans **within a message**, never solely to the message as a whole. A four-sentence response may interleave sourced facts, unknowns, inferences, operational verification, and roleplay. Preserve span boundaries, category, evidence pointers, and revision history as structured data independently of the visible styling. The interface shall provide a compact, configurable legend and render these spans with distinct visual treatments. The initial development profile may use the Steward's prior color conventions (facts white, unknowns purple, reasoning green, with distinct treatments for the other categories); later profiles may use typography, underlining, emphasis, or other accessible treatments. Presentation changes shall not require epistemic reclassification.

**Classification placement and latency:** R3 shall not require the resident model itself to classify its response. Engineering may implement (a) inline classification during generation, (b) fully asynchronous classification after the unannotated response is displayed, or (c) a hybrid of the two, according to measured performance and reliability. Classification and subsequent classification audit may be separate stages or combined where justified. All approaches must converge on the same claim/span-level category records, provenance, corrections, and message-level status. Until classification is available, the UI shall clearly indicate **unclassified/pending**, rather than implying the content has been verified. Optimize and measure time to first token, completed response, classifications available, and audit result; no classification stage should unnecessarily block ordinary resident responses. A resident's self-declared category is not independent proof; evidence references and auditor findings remain separately traceable.

These are charter-level provisional labels; Jessica, Helen, Chloe, and the engineering team may refine the taxonomy and display conventions without weakening the distinction between **evidence, inference, uncertainty, fiction, and observed operational reality**. Visual indicators shall remain lightweight and enable inspection of citations, record IDs, evidence, and classification rationale. No citation, tool result, or status label shall be fabricated.

Residents may ad-lib within their established personalities—for example, fictional coffee, doughnuts, office encounters, or flirtatious exchanges—without requiring factual verification of playful details. Resident personnel/character records shall include individualized, configurable **roleplay latitude** and contextual boundaries (casual, social, romantic/adult, professional), to be developed with Jessica and Helen. Roleplay permission never authorizes invented deployment results, research, health, financial, security, or other real-world facts.

A user or resident must be able to **challenge or correct a claim's evidence classification**, request supporting records, and report fictional improvisation used at the wrong time. Corrections shall preserve the original assertion, evidence, corrected classification, and learning outcome. Helen and Jessica shall use recurring misclassification, unsupported certainty, and context-inappropriate roleplay as measurable signals for resident grounding, performance review, and drift correction. The system shall distinguish mistakes from deliberate invention and from failed retrieval or context handoff.

### Asynchronous classification audit and message-level status

The primary post-response auditor shall check **epistemic labeling correctness**, not automatically perform full independent factual verification of every claim. After the resident delivers annotated text, an asynchronous auditor compares the content, classification, and available evidence/provenance to determine whether each span was appropriately labeled (fact, researched, inferred, unknown, roleplay, operationally verified). It shall flag unsupported certainty, missing evidence for claimed verification, or fiction presented as reality. A classification audit does **not** certify that every underlying real-world statement is true; separate substantive fact-checking may be requested or risk-triggered.

Each entire message shall show a clear, compact **classification-audit status**: pending, passed, mismatch, or unable to determine. A passed indicator means the labels were audited and found appropriate on the evidence available, **not** that every assertion is independently true. If any span has a consequential mismatch, flag the **entire message** prominently and allow drilldown to the affected span, expected category, rationale, and supporting record. Preserve the resident's original annotation and the auditor's finding separately in the historian; corrections shall be traceable and feed resident learning. The audit runs behind the response and must not block ordinary conversational delivery.

### Visual treatment of classification discrepancies

Epistemic category styling and **audit-discrepancy styling are independent layers**. The original classification (for example, a fact rendered in green) remains identifiable after an auditor disputes it. A configurable high-visibility treatment may use alternating diagonal **candy-cane stripes** in brighter and muted variants of the original category color (for example, fluorescent lime-green stripes for a disputed green fact), applied to the affected sentence or exact claim span. The **whole message** shall simultaneously display a visible mismatch indicator, with drilldown to the reason and any corrected classification. A mismatch signifies that the **label is challenged**, not automatically that the underlying claim has been proved false.

Color palettes, stripe patterns, contrast, animation, typography, and accessible alternatives belong to the presentation layer and may change without modifying underlying classification/audit records. The display must remain readable and provide a non-color-only indicator for accessibility. Distinguish pending, passed, disputed, and indeterminate audits; do not use a success mark for an uncompleted audit.

### Epistemic monitoring configuration and late-arriving alarms

Epistemic classification and audit shall be **configurable and phased**, initially with **per-resident opt-in** for test cohorts, plus an institutional master enable/disable control. A dedicated settings page shall expose resident participation, classification/auditor modes, notification and alarm severity, visual treatments, acknowledgement requirements, and escalation behavior. Settings shall distinguish global defaults from resident overrides and permit experimentation without rewriting the underlying evidence records.

A classification mismatch may arrive **after the Steward has already read the response or scrolled far beyond it**. The chat must therefore support a persistent, discoverable, late-arriving alert that identifies the resident and affected message, visibly signals unresolved discrepancies at the conversation level (potentially through a configurable background treatment), and offers a **jump directly to the original message and disputed span**. The alert must not depend on the original message remaining on screen. Provide an alert list/count and a way to return to the previous reading position.

**Acknowledged** (the Steward has seen the warning) and **resolved** (the issue has been corrected, superseded, or dispositioned) are distinct recorded states. Whether warnings require acknowledgement, whether they persist, and whether they escalate shall be configurable by significance and environment. Preserve original classifications, audit findings, notifications, acknowledgements, corrections, and disposition in the historian. Avoid disruptive alarms for trivial or harmless roleplay; ensure serious late-arriving discrepancies cannot silently disappear.

## 6. Resident health, mistakes, and continuous improvement

Mistakes are part of learning. **Learning from them is mandatory; repeated preventable mistakes are a performance concern.** Maintain durable mistake logs linked to causes, corrections, lessons, recurrence, and subsequent outcomes. Do not erase mistakes merely because the immediate problem was fixed, and do not discourage candid self-reporting.

Helen owns resident performance, development, and review records. Jessica shares responsibility for resident health, focusing on identity, character continuity, and behavioral drift. Grace reviews operational consequences with Helen; the Steward participates when needed. Ingrid addresses security-related failures.

Before attributing recurrence to a resident, distinguish knowledge-retrieval failure, context-transfer failure, tool/infrastructure defects, ambiguity, and disregard of known rules. Corrective responses may include targeted re-grounding, demonstrated learning, closer observation of affected work, implementation or tool adjustment, restricted capability, reassignment, or escalation. Severity and evidence govern response; **no automatic three-strikes bureaucracy**. Evaluate preventable recurrence, outcome quality, and demonstrated improvement, not merely error counts.

All residents participate in the loop: **retrieve knowledge → ground → reason/act → observe → verify outcome → learn → update knowledge → improve**.

## 7. Engineering Foundry — primary institutional output

Engineering is a **principal mission and output**, not an incidental support function. Vicky shall lead a persistent Engineering Foundry able to accept objectives and opportunities, develop solutions, use authorized workers and tools, build, test, independently verify meaningful acceptance criteria, deliver artifacts, and improve them.

The Foundry spans software, controls and automation, infrastructure, integration, AI/model deployment, testing, and spatial systems, and may serve R3 itself and external projects. Grace coordinates operational priorities; Chloe provides architectural direction; Vicky manages execution. Codex, scripts, models, agents, and MCP tools are resources, not substitute resident managers.

Work orders and state transitions support coordination and traceability; they shall not become a rigid, repetitive approval pipeline. A successful API response, file presence, or artifact checksum alone is not proof of substantive engineering acceptance. Verify delivered behavior and evidence. Preserve recoverability and concurrency without scenario-specific ceilings.

## 8. CME, communications, and truthful HMI

The **Continuous Motion Engine (CME)** belongs to Riverview as an institution. It supports persistent scheduling, heartbeats, state observation, watchdogs, recovery, event history, and resource supervision. It is not merely Grace's work-order mechanism.

All meaningful resident-to-resident communications shall be durably observable through an **Infrastructure → Communications** HMI and historian: sender, recipient, time, identifiers, linked work, delivery/processing states, failures, retries, latency, and authorized payload or secure reference. Residents communicate directly; central observability shall not imply centralized conversational control. Protected personal exchanges are not exposed to universal search.

R3's estate panorama, resident status, operational dashboards, and SCADA/PLC-inspired HMI shall represent **actual state**. No mock data or decorative animation may masquerade as live activity. Preserve drilldown, event replay, fault visibility, and provenance.

## 9. Mobile and Internet communications

The Steward shall be able to receive notifications, converse with residents, dictate replies, and exchange attachments from a phone **over the Internet**, not only on the home LAN. Desktop and mobile shall share the same communications backend and historian.

A mobile-friendly web interface/PWA is a reasonable first engineering candidate; existing ntfy capability shall be inventoried and evaluated rather than discarded or presumed functional. Remote access shall use a minimal effective authenticated, encrypted gateway without directly exposing databases, model ports, or administrative services. Voice and wake-word integrations can be staged separately.

## 10. Security and privacy — development through production

**Ingrid is vigilant.** During development, security shall be lightweight, proportionate, and practical, enabling rapid experimentation while maintaining basic authentication, encrypted remote access, least-necessary exposure, and protection for classified resident/Steward information. Controls shall strengthen deliberately as systems approach production or public deployment.

Information moving between local R3 systems and external reasoning services must be identified, appropriately scoped, and logged or referenced according to its classification. Private Evelyn/Gray Man material shall not be automatically exported or included in general search. Security oversight shall not become routine permission bureaucracy.

## 11. Data, history, and backups

PostgreSQL shall underpin durable structured records, relationships, event history, knowledge indexing, and provenance; large files may reside in appropriate file/object storage with references and checksums. Provide full-text and, where justified, semantic retrieval with access controls.

Recover and import the historical three-seat ChatGPT business-account backup, including available conversations, images, and attachments, preserving source, timestamps, original artifacts, and historical/current authority distinctions. Support ongoing backup of the current account **only through verified supported export mechanisms**, with deduplication and restore testing; do not assume a full-account conversation API exists.

Riverview 2 preservation is a historical input, not a claim of certified full restoration. Reuse existing components only after inventory and evidence-backed testing.

## 12. Spatial computing — Meta Quest 2

R3 shall evolve toward immersive, three-dimensional institutional interaction using the **existing Meta/Oculus Quest 2** and prior WebXR/resident-avatar experimentation as candidate starting points, subject to verification. The estate, residents, communications, and translucent operational HMI shall ultimately be accessible in a coherent spatial environment.

Spatial interfaces must draw from the same authoritative institutional state as desktop and mobile. Build progressively: practical WebXR access, navigation, interaction, resident presence, and operational visualization. Quest 2 hardware constraints and any later upgrade shall be treated as engineering decisions, not a reason to defer the vision or misidentify the owned hardware as Quest 3. Spatial capability shall not block basic institutional operation.

## 13. Capability registry and operational learning

Maintain a searchable, current registry of available models, GPUs, hosts, services, scripts, tools, adapters, storage, permissions, owners, health, and tested interfaces. Residents shall discover existing capabilities before reinventing them and use authorized resources independently.

Every significant action, decision, failure, recovery, and improvement shall contribute to institutional knowledge, truthful operational telemetry, and resident learning, respecting confidentiality.

## 14. Implementation discipline and approval

This charter defines **what R3 must become**, not every technical implementation choice. The Foundry shall deliver small, working vertical slices with meaningful tests and actual-state visibility. Do not claim autonomy, integrations, backups, or spatial features work until demonstrated.

Initial engineering priorities include: authoritative roster and canon recovery; knowledge-first grounding; persistent resident autonomy; direct communications/historian; Internet/mobile access; hybrid reasoning handoffs; Foundry delivery and verification; resident performance/learning; capability inventory; and progressive Quest 2 spatial experiments. Priorities may be sequenced dynamically by Grace, Chloe, and Vicky within delegated authority.

**Approval record:** Steward explicitly approved Project Charter Revision 2 on 2026-10-31. This revision is the governing charter; implementation details remain subject to engineering qualification.
