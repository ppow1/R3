<!--
R3 CONTROLLED DOCUMENT
File: r3a_runtime/schemas/PROVENANCE.md
Component: R3A-RESIDENT-SCHEMA-MANIFEST
File Revision: 1.0.0
Created: 2026-11-08 UTC (exact time not independently captured)
Created By: Codex GPT-6
Purpose: Sidecar provenance manifest for the commentless resident JSON Schema files.
Execution Model: Metadata only; not imported by runtime.
Observability: Git tracks schema revisions and their source contracts.
Dependencies: Approved R3 Charter Revision 2; Steward resident architecture directive.
Authority: Schema membership does not establish data authority or runtime permissions.
Changed: 2026-11-08 UTC | CHARACTER-ARCHITECTURE | Codex GPT-6 | Record schema provenance.
Supersedes: None
Contracts: JSON Schema Draft 2020-12; dossier, epistemic, institutional identity, protected relationship, and runtime character context v1 contracts.
Tests: JSON parsing and dossier instance validation in 2026-11-08 test run; external JSON Schema validator is not installed.
History/Predecessor: New file.
-->
# Resident schema provenance

| File | Purpose and source | Authority / status |
|---|---|---|
| `resident-dossier.v1.schema.json` | Versioned provider-neutral dossier interchange schema derived from the Steward directive and approved role/authority boundaries in R3 Charter Revision 2. | Proposed R3A resident dossier contract v1; does not replace institutional directory or HR identity authority. |
| `epistemic-span.v1.schema.json` | Passage-level legacy epistemic classes and provenance spans. Class names are supplied by the Steward directive; span/audit provenance requirements follow Charter Revision 2. | Proposed R3A epistemic span contract v1; a class label is not evidence. |
| `institutional-identity.v1.schema.json` | Resident and special Steward identity classification fields. `STEWARD` is separate from ordinary resident lifecycle and requires Steward-governed identity writes. | Contract only; no canonical Steward ID or HR record was provisioned in this environment. |
| `protected-relationship.v1.schema.json` | Separate relationship record with parties, classification, reader/editor ACL, disclosure scopes, provenance, revision and sourced facts. | Contract only; no Evelyn–GM relationship facts were recovered or stored in this Git repository. |
| `runtime-character-context.v1.schema.json` | Approved, identity-bound, digest-checked provider-neutral character context passed to a resident inference module. | Optional inference input; an upstream governed HR service must authenticate and filter before issuing it. |

Schemas contain no resident roster, personal history, credential, or provider secret. Dossier profiles live separately in `data/residents`; the source inventory records gaps in historical material.
