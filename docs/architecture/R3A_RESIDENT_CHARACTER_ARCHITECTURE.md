<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_RESIDENT_CHARACTER_ARCHITECTURE.md
Component: R3A-RESIDENT-CHARACTER-ARCHITECTURE
File Revision: 1.0.0
Created: 2026-11-08 UTC (exact creation time not captured)
Created By: Codex GPT-6
Purpose: Define dossier, prompt, state, governance, privacy, and integration contracts for residents.
Execution Model: Architecture and implementation handoff; no production runtime changes.
Observability: Versioned dossier files, audit lineage, source inventory, and tests.
Dependencies: Approved R3 Charter Revision 2; R3A directory and execution-profile contracts.
Authority: Steward directive; does not amend the R3A master roadmap or grant operational authority.
Changed: 2026-11-08 UTC | CHARACTER-ARCHITECTURE | Codex GPT-6 | Specify and implement canonical dossier layer.
Supersedes: None
Contracts: r3a.resident.dossier.v1; r3a.resident.prompt-composition.v1; r3a.resident.runtime-binding.v1
Tests: tests/test_r3a_resident_dossiers.py
History/Predecessor: New file.
-->
# R3A Resident Character Architecture

## Identity and source findings

The dossier separates office, occupant, implementation, and durable state. The office expresses institutional responsibility; the occupant is the named resident; provider/model adapters are replaceable implementation; memory, relationships, revisions, and continuity are state. A dossier, Character Bible, prompt, or model response grants no operational authority. CME and the authoritative directory continue to own execution policy and current binding.

The source inventory is in [resident-source-inventory.md](resident-source-inventory.md). In short:

- The current R3A directory contract reads `riverview_authority.institutional_offices`, `office_bindings`, and `resident_occupants`. It does not read legacy HR SQLite. The local R3A configuration has no directory DSN, and the provider contract explicitly returns `unavailable` with empty arrays when it is absent. No live authoritative query was possible in this worktree.
- The legacy HR store is a different SQLite database (`hr_records`, one JSON payload per `resident_id`). A read-only inspection of the available local snapshot on 2026-11-08 found 13 rows, each at revision 1 and onboarding status. Two rows were protected/private and were intentionally not copied or identified in Git. The other 11 match the public roles named in the approved charter.
- A historical HR implementation summary describes the initial R3 records as Grace and Marie, not eleven. This is evidence of a different earlier snapshot/stage, not a conflict to overwrite. The locally available HR snapshot is not a current authoritative directory and no synchronization bridge is established.
- R3A execution-profile sources use IDs such as `resident.grace`, while legacy HR uses `r3:grace`. No mapping contract proves these identifiers equivalent. Dossiers retain legacy HR record keys as provisional dossier lookup IDs and mark cross-system links unresolved.

Therefore the committed 11-dossier set is a **source-grounded recovery set**, not an assertion of full authoritative roster coverage. `data/residents/index.json` declares `partial_unreconciled`; it contains no protected dossier material. The authoritative directory owner must provide a current export or read interface, including occupant lifecycle and verified crosswalk, before coverage can be certified. Chloe's identity remains explicitly unconfirmed pending that reconciliation.

## Dossier and component contract

`r3a.resident.dossier.v1` is defined in `r3a_runtime/schemas/resident-dossier.v1.schema.json` and loaded by `DossierRepository`. It includes identity/source IDs, office and lifecycle status, responsibilities, qualifications, authority boundaries, character canon, adjustable personality settings, modular prompt components, transient emotion, memory configuration, directed relationships, provider-neutral implementation preferences, governance, source provenance, and open questions.

The 11 seed dossiers carry only charter and legacy HR office facts, a minimal casual-conversation behavior supplied by the Steward directive, and epistemic boundaries. They contain no invented backstories, qualifications, personal preferences, traits, or interpersonal relationships. Their scalar dimensions use neutral global defaults; scalar values do not stand in for character identity. All character bibles are marked `not_recovered`; source discovery and Jessica/Helen review remain open.

Prompt modules have stable IDs, independent versions, owners, source references, classifications, and approval states. Composition uses a fixed public ordering, filters non-approved and protected/personnel-sensitive modules, optionally filters institutional material, and returns exact component references plus a SHA-256 digest. The result remains context only and cannot grant capabilities or alter the resident's identity. Provider-specific modules are opt-in by provider ID.

## Configuration, memory, emotion, and relationships

The versioned `global-config.v1.json` declares the nine personality dimensions, integer range 0–100, and precedence `institution_default < resident < approved_experiment`. Only approved active overrides apply. A provider binding carries the same dossier resident ID and continuity reference across provider replacement; authority and capabilities are empty until supplied through their separate contracts.

Memory supports episodic, professional, institutional, personal, and relationship categories. Each future entry must carry source references, occurrence/record timestamps, access classification, and retention rule reference. Corrections append a successor and retain the original; supersession is explicit. No memory content or retention period is invented in the seed data. Temporary emotional state is represented separately from durable traits and requires a source, capture time, and optional expiry. Relationships are directed; trust, respect, professional rapport, and affinity require experience/source references. Empty seed relationships do not imply affinity.

## Epistemic contract

Passage-level spans preserve the legacy classifications `VERIFIED`, `CANON`, `REASONED`, `GENERAL`, `CREATIVE`, and `UNKNOWN`, with source/locator, timestamp, classification actor, audit state, and supersession reference. `VERIFIED` and institutional `CANON` fail validation without source references. A classification is not independent evidence. The contracts add no mandatory multipass inference; ordinary conversation can be delivered without an added classifier pass. Asynchronous classification/audit and UI presentation remain Coordinator/Autonomy integration work.

## Ownership and approval workflows

- **Helen / HR:** maintain personnel identity, office and lifecycle assignments, onboarding, professional qualifications, performance history, and development records. Personnel revisions carry source evidence and use expected-revision concurrency. Sensitive fields remain in the governed HR store and only an authorized projection may enter a runtime context.
- **Jessica / Character Architecture:** recover canon, maintain Character Bibles and modular character components, review differentiation and drift, and propose changes to durable traits or personality settings. Existing canon is recovered before proposed additions are approved.
- **Joint readiness:** validate an HR identity and office binding, assemble the character package, validate schemas/provenance/privacy, obtain domain-specific approval, bind an implementation adapter without changing identity, and report activation readiness. CME independently checks capability and execution policy.

Repository code records separate HR and Character Architecture owner decisions in immutable revisions. Neither owner can approve the other's domain. The dossier's overall approval remains `in_review` until both decisions are approved and authoritative occupant identity is resolved; any rejection records a rejected revision. Repository actor names are claims only: they cannot authenticate Helen or Jessica. The SQL migration intentionally defines no grants. Before any write interface is activated, an identity-bound HR/Character Architecture service must attest the caller and scope; the local JSON store is development/test storage only.

## Runtime and compatibility

The dossier package is independent of resident count. Lookup is by dossier ID or a source ID whose crosswalk is explicitly confirmed; unresolved aliases fail closed. No Python resident map or provider-specific identity table exists. The R3A directory remains the authority for resident binding. Existing `r3a.resident.execution-profile@1.0.0` stays unchanged; a future adapter may join its verified ID/office evidence to the dossier store after the directory supplies a crosswalk. The schema migration adds version/current/event tables but has not been applied to any database.

Coordinator and Autonomy can integrate through these versioned surfaces:

- `DossierRepository.get(resident_id, revision=None)` and `.list_ids()` for storage access; call only after resolving authoritative identity.
- `compose_prompt(dossier, provider_id=...)` for deterministic prompt text and lineage.
- `resolve_personality(defaults, resident_settings, overrides)` for settings precedence.
- `runtime_binding(dossier, provider_id, configuration_revision)` for identity-preserving adapter configuration. CME must continue deriving grants independently.
- `validate_epistemic_span`, `validate_memory_entry`, `validate_relationship`, and `validate_emotional_state` for data admission.

Database integration should validate dossiers before insertion, store immutable revisions, append governance events, and move the current pointer transactionally. Migrate only public/approved data with source lineage. Do not import protected HR rows or private character sources into this Git repository or runtime prompt path. Rollback means pointer/event reversal to a retained revision; it never deletes history.

## Status and prerequisites

Implemented locally: schema contracts, repository adapter, composition/configuration helpers, 11 provisional public dossiers, source inventory, migration draft, ownership and handoff contracts, and unit tests. Not operational: authoritative roster access/crosswalk, DB migration application, authenticated HR/character write workflows, provider dispatch, persistent memory/relationship services, live Grace compatibility, Vicky activation readiness, or production deployment.

Before Coordinator/Autonomy integration, obtain the authoritative roster source/crosswalk, preserve their current branch state, agree the dossier profile adapter boundary, and provision isolated integration DB permissions. No production deployment or runtime mutation occurred in this workstream.
