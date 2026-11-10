<!-- R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_UNIVERSAL_RESIDENT_ONBOARDING_V1.md
Component: R3A-RESIDENT-ONBOARDING
File Revision: 1.0.0
Created: 2026-11-10 UTC
Created By: Codex GPT-6
Purpose: Define the reusable packet, approval boundaries, lifecycle, and owner/interface contracts for every R3A resident.
Execution Model: Data-only evidence packets plus an R3A PostgreSQL workflow projection and append-only audit events.
Observability: Packet revisions, source references, stage status, actor/approval references, idempotency, and correlation.
Dependencies: R3A directory/CME/Website, HR authority, Character Architecture, Security, Coordinator, Auditor, Steward.
Authority: Steward directives in R3 Issue #58 comments 6768560524 and 6769020176.
Changed: 2026-11-10 | R3A-UNIVERSAL-RESIDENT-ONBOARDING | Codex GPT-6 | Specify reusable resident lifecycle packet and explicit external blockers.
Supersedes: Narrow Vicky-only onboarding objective in the original Issue #58 body.
Contracts: r3a.resident.onboarding-packet.v1; resident.onboarding machine v1.
Tests: tests/test_r3a_resident_onboarding.py.
History/Predecessor: Extends transfer record R3A_HR_VICKY_TRANSFER_MATRIX_2026-11-10.md.
-->
# Universal R3A resident onboarding packet and workflow v1

## Purpose and boundary

Every current and future resident uses the same versioned packet schema and state machine. A packet records source references, authority decisions, revision pins, validation status, and blockers. It is not an identity registry and does not own appointment, directory, character, credential, capability-grant, or runtime facts. Those remain in their existing authorities.

Packets contain references and status only. They must not copy HR source payloads, credential material, protected relationship facts, or prompt content. A request label and requested role are explicitly unverified until their owning authority supplies evidence. A software transition records process progress; it never creates or implies an institutional appointment.

The R3A PostgreSQL migration adds workflow packet and immutable event tables. The repository performs atomic idempotent creation and revision compare-and-swap. Production activation requires the normal Coordinator migration/deployment lane. No HR, directory, credential, grant, character, or CME authority is written by this workflow.

## Packet contract

The canonical JSON Schema is `r3a_runtime/schemas/resident-onboarding-packet.v1.schema.json`; the reusable machine-readable blank packet is `docs/onboarding/packet-template.json`; the synthetic end-to-end request fixture is `tests/fixtures/resident-onboarding-synthetic.json`. The machine definition is `r3a_runtime/state_machines/resident_onboarding.v1.json`. Runtime validation lives in `r3a_runtime/residents/onboarding.py`; durable workflow projection and event history live in `r3a_runtime/residents/onboarding_repository.py` and migration `019_resident_onboarding.sql`.

Each packet has an opaque UUID packet ID, schema version, packet revision, create idempotency key, optional canonical HR resident ID, unverified request context, lifecycle state/checkpoint, timestamps, domain evidence blocks, and audit events. No person-specific branch or principal map is part of the implementation.

Every domain block and each field evidence item declares owner, authority source, required approval, source/evidence references, validation contract, revision pin, privacy classification where applicable, and status. A field's `value_ref` points to its authoritative source; it does not embed that source's payload. `verified` requires evidence, a revision pin, and any required approval reference. `not_applicable` requires an explicit authority reference and is permitted only for conditional/optional domains.

Universally required domains are identity, appointment, credentials, grants, runtime, communications, operational acceptance, and lifecycle. Character/canon is conditional only when the role has no resident character or continuity context; the decision and owner evidence must still be recorded. Role-specific requirements are expressed as additional evidence-field references under the same domain, not new code paths.

## Authority and interface matrix

| Packet field or operation | Authoritative owner | Existing source/API in the verified R3A baseline | Required approval | Validation and evidence | Current interface status |
|---|---|---|---|---|---|
| Canonical HR resident ID, unique identity, HR revision, privacy classification | HR; Helen's HR management authority is represented by configured HR policy, never a hardcoded name check | Existing host-injected `HRCapability.read`; R3A `HRPrincipalAssociationAdapter`; no deployed R3A personnel-record API was found | HR identity decision; authenticated exact `r3:hr` / `hr.write` grant for association | Revisioned source reference, exact principal association, provenance, audit event, privacy classification | Read/write host integration unavailable; association operation `associate_authority_principal_with_provenance` is absent and adapter fails closed |
| Active resident occupant and office binding, office role, reporting relationships | Riverview institutional directory/HR authority | CME `institutional.directory.discover`; provider reads `riverview_authority.institutional_offices`, `resident_occupants`, `office_bindings`; read only | HR appointment and authorized directory-owner binding approval | Authenticated current snapshot digest/time, canonical principal, office status/revision and source refs | Read path exists; no R3A occupant/binding writer exists |
| Appointment, title, responsibilities, authority, reporting line, dates/status | HR | No authenticated R3A appointment API identified; do not infer from dossier or directory display | HR-authorized appointment approver | Approved active appointment ref, effective interval, source revision, office assignment | External authority contract/owner action required |
| Character identity, canon, revision, continuity/memory refs, protected relationship policy | Character Architecture; Jessica's approval role is enforced through configured policy and separate reviewer checks | R3A `CharacterWorkflowService`, dossier revision repository, approved context provider; no Vicky activation link | Character Architecture proposal/review/publish and independent review where required | Approved artifact refs, immutable revision, source/evidence refs, protected-scope validation | Source workflow exists; Vicky's dossier is provisional and not identity or activation evidence |
| Credential owner, issue/expiry, authentication verification | Security | AP3/Steward session components are not resident credential provisioning; no resident credential API found | Security issuance and rotation approval | Reference only, owner, expiry, authenticated check evidence; never store secret/token | Missing resident credential authority/interface |
| Capability grants, exact scope, renewal and revocation | Security / canonical R3 authority policy | CME exact grant checks/revocation and R3A grant adapter; module grant persistence in R3A Store | Separate Security grant approval; role assignment alone is insufficient | Exact resource/action/operation/scope, grant ref, authorization audit, expiry/revocation evidence | Enforcement exists; Vicky grants and resident onboarding grant issuance are not evidenced |
| Module registration, model/inference route, dependencies, capability interface, CME registration/config | Coordinator | CME module registry, manifest contract, configured execution profiles/routes | Coordinator review and controlled deployment | Artifact/config digest, registration/health, route ID, dependency/interface tests | Generic registration exists; Vicky-specific registration/route is unverified |
| Authenticated directory roster, display/title/status, resident chat and persistence | Coordinator owns CME/Website integration; Website endpoint is session protected | `GET /api/v1/steward/residents` → authenticated AP3 principal → CME `steward.residents.discover` → `institutional.directory.discover`; conversation persistence in CME | Coordinator integration; authenticated session; HR source supplies title/status | Fresh authenticated roster snapshot, canonical principal, display mapping, chat route and persisted turn refs | Read interface exists; latest snapshot at 2026-11-10 12:49:05Z returned Grace only |
| Operational acceptance and lifecycle transitions | Steward owns the acceptance packet; Independent Auditor owns its independent-review evidence field; HR/Security/Coordinator own their rollback actions | Packet workflow plus owner APIs above | Auditor review and explicit Steward acceptance, with each domain approval kept separate | Revision-pinned acceptance evidence, denied/expired grant checks, tool/inference/CME persistence evidence, audit | Workflow source implemented; no production packet migration or full resident acceptance run |

No role title alone provisions a credential, grant, model route, or chat capability. The packet workflow's own R3A database permission covers only packet/current projection and its event history. Database grants for the new tables are deployment-owned and must not permit writes to authority schemas.

## Lifecycle machine

The exact machine is immutable `resident.onboarding` v1. Ordinary advancement is:

| From → to | Responsible authority | Gate |
|---|---|---|
| REQUESTED → IDENTITY_PENDING | HR | Authenticated onboarding request and stable request key |
| IDENTITY_PENDING → APPOINTMENT_PENDING | HR | Verified unique HR identity, provenance association, canonical principal, and active office-binding evidence |
| APPOINTMENT_PENDING → AUTHORIZATION_PENDING | HR | Approved active appointment, title/responsibilities, office/reporting assignment, authority, and effective dates |
| AUTHORIZATION_PENDING → RUNTIME_PENDING | Security | Independently verified credential and exact approved grants/scopes |
| RUNTIME_PENDING → VALIDATION_PENDING | Coordinator | Module, route, dependencies, capability interface, configuration, and CME registration evidence |
| VALIDATION_PENDING → ACTIVE | Steward | All mandatory domains verified; applicable character domain resolved; Auditor review and Steward approval refs present |

Any in-progress owner may move its own stage to BLOCKED with a reason/evidence reference; the packet preserves the exact resume checkpoint. The same owner resumes only to that checkpoint after updating the blocker evidence. ACTIVE must first be SUSPENDED before revocation/offboarding. Security/HR revoke credentials and grants as source operations, record those owner attestations, then an authorized role moves SUSPENDED to REVOKED. SUSPENDED resumes at its saved checkpoint; resuming to ACTIVE requires fresh Steward approval and every activation gate still valid. REVOKED may only become OFFBOARDED. OFFBOARDED is terminal.

Transition requests require a trusted actor and role resolved by the server, exact external `authorize` decision, packet revision, stable idempotency/correlation IDs, reason/evidence refs, and approval ref when the transition requires one. Repository updates use a row lock and compare-and-swap; packet state and immutable event snapshot commit in one transaction. Reusing a key with the same request returns the current prior result; conflicting reuse and stale revisions fail. Domain evidence revisions are owner-scoped, references only, and equally audited. Partial failure leaves the prior packet and event intact so the owner can resume. When identity evidence validates, its source adapter returns the canonical HR resident ID and the repository enforces one open packet per identity.

### Rollback and lifecycle operations

- **Renewal/reassignment:** HR issues a successor appointment/binding revision; HR and Coordinator revalidate the packet's pinned facts before resume/activation.
- **Suspension/reactivation:** Security, HR, or Steward suspends with approval and reason. Required grants are reevaluated. Reactivation re-enters the saved checkpoint and cannot bypass acceptance.
- **Credential rotation/grant revocation:** Security records successor references and revoked/predecessor refs. Secrets never enter the packet.
- **Offboarding:** HR/Coordinator/Steward request; credentials and all grants must first be recorded revoked; Coordinator records module/chat disablement and rollback refs; HR records appointment closure; final event remains append-only.
- **Rollback/recovery:** restore a prior verified packet/domain snapshot only through a new revision and owner approval. Never delete audit events or reanimate a revoked/offboarded identity; a new appointment requires a new packet after terminal closure.

## Vicky first packet and second-resident reuse

`docs/onboarding/vicky.packet.json` is an evidence-grounded, unpersisted packet example. It uses only the Steward request label and cited records. The latest authenticated R3A directory evidence in Issue #58 comment 6768796862 is timestamped 2026-11-10T12:49:05Z, returned Grace only, and states that the result cannot distinguish absent/retired occupant from absent active binding. The Vicky dossier uses `r3:vicky` as a provisional legacy key, says onboarding is not active assignment, and has no approved Character Bible. Vicky's `resident_id` therefore remains null. Every unavailable section is pending or blocked with its owner and evidence pointer. The packet is not a persisted HR identity and does not activate Vicky.

The synthetic Analyst fixture and tests create two different packets through the exact same schema, service, store protocol, and transition definitions. Resident IDs, names, titles, field requirements, and capability scopes are data/evidence; no resident-named code branches are used.

## Deployment and acceptance boundary

Source tests do not authorize or prove migration application, live HR reads/writes, directory writes, resident credentials, effective grants, module activation, Website chat, or live inference. Coordinator must review the additive migration/role grants and compose the service with authenticated R3A principal and authorization resolvers. HR must publish its personnel/appointment and resident-binding procedures plus the provenance writer. Security must identify resident credential/grant provisioning. Jessica/Character Architecture must provide its authoritative approval refs. Auditor review and Steward activation follow only after those evidence sources are available.
