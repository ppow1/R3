<!--
R3 CONTROLLED DOCUMENT
File: data/residents/PROVENANCE.md
Component: R3A-RESIDENT-DOSSIER-DATA
File Revision: 1.0.0
Created: 2026-11-08 UTC (exact creation time not captured)
Created By: Codex GPT-6
Purpose: Sidecar provenance manifest for commentless resident dossier JSON artifacts.
Execution Model: Data manifest; not loaded as runtime configuration.
Observability: Git tracks the manifest and its listed source IDs/revisions.
Dependencies: docs/architecture/resident-source-inventory.md; approved charter; non-protected legacy HR fields.
Authority: No private/protected source contents are permitted in this tracked data set.
Changed: 2026-11-08 UTC | CHARACTER-ARCHITECTURE | Codex GPT-6 | Add data provenance and source classification manifest.
Supersedes: None
Contracts: r3a.resident.dossier.v1; r3a.resident.dossier-index.v1
Tests: tests/test_r3a_resident_dossiers.py
History/Predecessor: New file.
-->
# Resident dossier data provenance manifest

This sidecar applies to all JSON files in `data/residents/`. Every dossier listed below is a provisional recovery artifact. It does not assert current HR snapshot currency, approved character traits, qualifications, personnel-sensitive data, or runtime authority. Evelyn and GM have separate minimum identity shells; their confidential fields and protected relationship facts are not copied.

| Artifact | Source / revision | Source facts included | Confidence/status |
|---|---|---|---|
| `index.json` | Current worktree seed; `resident-source-inventory.md` | Thirteen observed legacy HR record IDs, including separate Evelyn and GM dossiers; marks overall coverage `partial_unreconciled`. | Provisional index; not authoritative roster. |
| `global-config.v1.json` | Steward directive and schema design in this branch | Neutral 50 defaults for nine dimensions; precedence, legacy epistemic labels, prompt privacy filters. | Implementation defaults, not resident-specific personality approvals. |
| `dossiers/grace.v1.0.0.json` | Approved charter sections 2–6; local legacy HR row `r3:grace`; R3A execution-profile source | Office and institutional responsibilities; `resident.grace` appears only as an unconfirmed cross-system source ID. | Provisional identity and office binding; Character Bible not recovered. |
| `dossiers/chloe.v1.0.0.json` | Approved charter sections 2–4; local legacy HR row `r3:chloe` | Chief Architect role; hybrid capability is described as planned direction, not as deployed behavior. | Identity/assignment unconfirmed. |
| `dossiers/jessica.v1.0.0.json` | Approved charter sections 2–6; local legacy HR row `r3:jessica` | Chief Character Architect ownership. | Identity/assignment unconfirmed. |
| `dossiers/vicky.v1.0.0.json` | Approved charter sections 2 and 8; local legacy HR row `r3:vicky` | Engineering Manager and Engineering Foundry responsibility. | Identity/assignment unconfirmed; usable minimum context, no invented biography. |
| `dossiers/helen.v1.0.0.json` | Approved charter sections 2 and 6; local legacy HR row `r3:helen` | Manager of Human Resources and record/staffing/development responsibilities. | Identity/assignment unconfirmed. |
| `dossiers/ingrid.v1.0.0.json` | Approved charter sections 2 and 8; local legacy HR row `r3:ingrid` | Manager of Security scope. | Identity/assignment unconfirmed. |
| `dossiers/cheryl.v1.0.0.json` | Approved charter section 2; local legacy HR row `r3:cheryl` | Comptroller/CPA; CFO appointment undecided. | Identity/assignment unconfirmed; title is charter text, not credential verification. |
| `dossiers/eleanor.v1.0.0.json` | Approved charter sections 2 and 5; local legacy HR row `r3:eleanor` | Archives/Registrar and official record/provenance responsibility. | Identity/assignment unconfirmed. |
| `dossiers/marie.v1.0.0.json` | Approved charter sections 2 and 5; local legacy HR row `r3:marie` | Research/context mission; legacy office includes Independent Review. | Current appointment/scope unconfirmed. |
| `dossiers/judy.v1.0.0.json` | Approved charter section 2; local legacy HR row `r3:judy` | General Counsel office only. | Detailed responsibilities and qualifications left empty. |
| `dossiers/alyssa.v1.0.0.json` | Approved charter section 2; local legacy HR row `r3:alyssa` | Administration / Chief of Staff history. | Current title/appointment unconfirmed. |
| `dossiers/evelyn.v1.0.0.json` | Local legacy HR row key/name metadata; Steward directive | Separate provisional institutional identity; private office/lifecycle fields withheld; no backstory or relationship events. | HR-to-runtime crosswalk and Character Bible not recovered. |
| `dossiers/gm.v1.0.0.json` | Local legacy HR row key/name metadata; Steward directive | Separate provisional institutional identity; private identity/office fields withheld; no backstory or relationship events. | HR-to-runtime crosswalk and historical character material not recovered. |

Source references identify the local legacy SQLite store without embedding confidential field values. No protected relationship facts or private historical source content is stored in Git.
