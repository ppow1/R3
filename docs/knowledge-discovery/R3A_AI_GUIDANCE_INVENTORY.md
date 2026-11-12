<!--
R3 CONTROLLED DOCUMENT
File: docs/knowledge-discovery/R3A_AI_GUIDANCE_INVENTORY.md
Component: R3A-KNOWLEDGE-DISCOVERY-INVENTORY
File Revision: 1.0.0
Created: 2026-11-08 UTC (exact time recorded in Git commit)
Created By: Codex GPT-6
Purpose: Record inspected AI guidance sources and distinguish R3A authority from references.
Execution Model: N/A
Observability: Source revisions, Git object IDs, content digests where available, review dispositions.
Dependencies: Accessible ppow1 GitHub repositories and R3 local worktrees.
Authority: Discovery record only; does not establish institutional authority or approve ingestion.
Changed: 2026-11-08 | R3A-KNOWLEDGE-DISCOVERY | Codex GPT-6 | Initial reviewed-source inventory.
Supersedes: None
Contracts: Steward-directed institutional knowledge discovery assignment.
Tests: Inventory structure and proposal provenance verified by tests/test_knowledge_review_batches.py.
History/Predecessor: None; new file.
-->
# R3A AI guidance source inventory

**Snapshot date:** 2026-11-08. This is a reviewed sample of sources actually available through the local R3 checkout and connected GitHub repositories, not a claim that every Riverview development estate archive has been exhaustively crawled. Repository names and source contents are recorded as found; R1/R2 lineage is not inferred from names.

## Discovery scope and counts

- Reviewed **13 distinct AI guidance file paths** across five repositories/projects, including **15 distinct content revisions** after counting the R3 worktree variants; plus **3 historical revisions** of the `ppow1/Riverview-/AI_HINTS.md` file.
- Also reviewed **7 local R3 governance/architecture references** used to assess current R3A scope and candidate knowledge; these are not counted as AI guidance documents.
- Found **8 local worktree copies** of R3 `AI_HINTS.md`, but they represent only **3 unique content revisions** (1.0.8, 1.0.9, 1.1.0) and are not counted as separate institutional sources. Revisions 1.0.8 are byte-identical (SHA-256 `67b51a8269a49e86718023a37ffa79190ee6ab433df26a56f980adea994268b7`); 1.0.9 and 1.1.0 are separate branch guidance and must not be combined as one authority.
- The literal repositories `ppow1/R1` and `ppow1/R2` were not available to this connected account (repository lookup returned 404). `ppow1/Riverview` and `ppow1/Riverview-` were inspected under their actual names; their lineage is not assumed.
- Counts by proposal assessment: **3 current R3/R3A candidates**, **2 useful external-reference/adaptation candidates**, **1 conflicting legacy candidate**, **1 project-specific candidate recommended for rejection**, and **8 reviewed AI guidance documents with no transferable knowledge candidate**. Candidate totals overlap with source documents; the underlying proposal set is 7 entries.

## Inspected AI guidance documents

| Repository / path | Purpose and scope | Source revision / content identity | Modification | Authority assessment and relationships |
|---|---|---|---|---|
| `ppow1/R3` `AI_HINTS.md` | R3 engineering index and source-governance guidance. | File 1.0.8; SHA-256 `67b51a8269a49e86718023a37ffa79190ee6ab433df26a56f980adea994268b7`; Git blob `a076a5ad0a13433a4e4ad1ccf7b8f029a5c6d06d`. | Commit `0636704f9b9f1dfba346dfcdd24a70c0f35b62f7`, 2026-11-06T05:05:20Z. | Current R3 navigation guidance subordinate to approved charter. Directs new R3 runbooks to `ppow1/R3`, treats `Riverview-` as reference, and rejects wholesale migration. It points to R3 charter/roadmap. |
| `ppow1/R3` local guidance copies (8 worktrees) | Separate workstream checkout copies. | Three contents: 1.0.8 SHA-256 `67b51a8269a49e86718023a37ffa79190ee6ab433df26a56f980adea994268b7`; 1.0.9 SHA-256 `2b56c8e611ed7821327ccfe0b0ab3dd607421fb9edb093734f1e49737a1251c5`; 1.1.0 SHA-256 `8ebedda3e71e17b89cc1e24bdf4de7e0a7c9d74f1c134c6f8c60ee3d4d601185`. | 1.0.8 last file commit `0636704f9b9f1dfba346dfcdd24a70c0f35b62f7` (2026-11-06); 1.0.9 `0e2af25e3b2003dd78c48c93b055416598047032` (2026-11-07); 1.1.0 copies `4d3cee6e6be87dfa7f4f65e48d6c304f0a2019b6` and `1623fd6e672c57083cbf31d2d37158d7f9f8ae20` (2026-11-07). | 1.0.8 copies are duplicates. The 1.0.9 variant adds resident character architecture pointers; 1.1.0 adds Steward access/session pointers. These worktree commits are branch-specific snapshots; none independently supersedes the common R3 mainline. |
| `ppow1/Riverview` `AI_HINTS.md` | Large legacy Riverview project guide and task instructions. | Git blob `77c966d641ccf508177f0828b49a8b85dcfa67b3`; source commit `4590f2fb5e6813d409b3faf8e37a151778aea1f6`. | Default tree snapshot; per-file last modification was not reliably retrieved in this pass. | Legacy project-local operational guidance. Contains useful durable-knowledge practices but also execution-first wording that conflicts with this assignment's explicit approval requirement; do not import wholesale. |
| `ppow1/Riverview-` `AI_HINTS.md` | Repository-scoped recovery and Steward approval guidance. | Revision 1.0.7; blob `16771b9df9b00f1758f45ca277bd675c217fc4ca`; source commit `2a861dabc6549aaf130139dfb6915b45fa3f1700`. | 2026-10-22T19:09:10Z. | Historical/reference project guidance. Says proposal drafts are not execution authority, and approval and promotion are separate; useful candidate subject to R3A review, not R3A authority. Revisions 1.0.6 and 1.0.0 were also read; 1.0.7 includes later scope and proposal distinctions. |
| `ppow1/theestate` `AI_HINTS.md` | Estate AI reading index. | Blob `e313c02b946b431cde883fd7b92f839d31b05e09`. | 2026-08-26T12:42Z; source snapshot commit `6f8c620225bc757eaf11b0b090c9c56bd13bb110`. | Estate-scoped pointer; directs readers to project-local records. Not R3A authority. |
| `ppow1/theestate` `AI_COMMUNICATION_HINTS.md` | Estate communications/repository pointers. | Exact Git blob SHA was not captured; fetched and read at snapshot commit `6f8c620225bc757eaf11b0b090c9c56bd13bb110`. | Source snapshot commit above; file timestamp unavailable. | Estate-only workflow context; not used as a proposal source. |
| `ppow1/theestate` `AI_REFLECTION_HINTS.md` | Estate reflection and evaluation pointers. | Blob `c3d8f49f2eed8080e9974c46b272cf0ea540e1fc`. | Source snapshot commit above; file timestamp unavailable. | Distinguishes evaluation from directive and warns historical examples do not override current process; useful reference. |
| `ppow1/theestate` `AI_SOFTWARE_DEVELOPMENT_HINTS.md` | Estate software-development instructions. | Blob `b1cea1f39cc6ec828699b5bed62e4a922fff084b`. | Commit `50b8b69b7d828a9afd45f01dad9248271652abf2`, 2026-08-11T21:19:57Z. | Estate scoped. Its proposal/classification without silent promotion is an adaptation candidate consistent with the current task; its authority remains external. |
| `ppow1/theestate` `AI_START_HERE.md` | Estate current entrypoint and reading order. | Blob `f43cfae1370252da2c96f89de227e37419e0d1c7`. | Source snapshot commit above; file timestamp unavailable. | Current Estate navigation pointer; no R3A rule proposed. |
| `ppow1/theestate` `docs/onboarding/AI_START_HERE.md` | Earlier onboarding entrypoint. | Blob `85ca729f77980303f7734d14bba01556a11d7bad`. | Source snapshot commit above; file timestamp unavailable. | Historical onboarding document; appears superseded by root `AI_START_HERE.md`, not promoted. |
| `ppow1/theestate` `collaboration/workstreams/WP-0210/proposed/ai_services_model_controls.md` | Proposed controls for AI services. | Blob `89e3578fd7792e03c888aa87bae21fa7d1fa7671`. | Source snapshot commit above; proposal timestamp in document only. | Explicitly staged/proposed, not installed. Separating proposals from approvals is a useful reference; no present authority. |
| `ppow1/CueMastery` `AI_HINTS.md` | CueMastery / Ionoge quick recovery pointer. | Blob `f6cecd550aace5b67d09e1fe21c70469649fb264`. | Commit `1f03e77da9fbbdb131d923f7b616feb5b9415b27`, 2026-06-11T00:40:35Z. | Project-specific. Comms authority belongs to Ionoge Comms7 in that project; not transferable to R3A. |
| `ppow1/CueMastery` `AGENTS.md` | CueMastery repository agent instructions. | Blob `301e78fc52288156ef74d3abbe97345924a1fede`. | Commit `2b3614d06771a355a77d548c1971b8494a5784cb`, 2026-06-03T13:27:17Z. | Project-specific execution conventions, no R3A candidate. |
| `ppow1/CueMastery` `docs/ai_start_here.md` | CueMastery-only reading index. | Blob `6c760940523fd764a0eaddef6dc8f455e42f8ad7`. | Commit `f42df5cefdc99aa511238ac1776a24b51386a310`, 2026-06-17T00:41:36Z. | Project-specific navigation; no R3A candidate. |

**Metadata note:** The exact Git blob ID for `AI_COMMUNICATION_HINTS.md` was not retained. It is explicitly not an ingestion citation. Re-fetch its exact blob before any candidate is approved. The proposal set does not cite it.

## R3 source references used to classify authority

These actual local sources are not part of the AI guidance count, but bound applicability:

| Source | Revision and digest | Assessment |
|---|---|---|
| `ppow1/R3/AI_HINTS.md` | 1.0.8; SHA-256 above. | Current source/repository boundaries; says R3 charter and approved roadmap govern. |
| `docs/PROJECT_CHARTER_REVISION_2_REVIEW.md` | 1.0.0 provenance baseline; SHA-256 `89c5e72d48dea8770bc8a9b15f2992073f1d9e450f6b4c50980ad509376a75e5`; approved 2026-10-31. | Approved R3 charter. Current authority for institutional knowledge, evidence/provenance, privacy, Grace and office boundaries. |
| `docs/architecture/R3A_MASTER_ROADMAP_AP0_AP6.md` | 1.0.3; SHA-256 `3d18d59506075b7eebadca1898ab67d50091af3947bbcf6e75b69117ba57c1ab`; Baseline 1.0 approved 2026-11-06. | Governing R3A development roadmap within approved scope. |
| `docs/architecture/R3A_INSTITUTIONAL_KNOWLEDGE_CAPABILITY.md` | 1.2.0; SHA-256 `6ddb9e77a8cc34d6cc7d9cee97cfb0c8bd04f6d298728f586e82509adbfdfa67`. | Existing knowledge read contract; preserves read-only retrieval and states retrieval has no institutional decision authority. |
| `hints/development-governance.md` | 1.0.4; Git blob `512eb84d3611099dbe78ae51fba7fe368f9fe231` (current file predecessor metadata). | Explicitly says historic R2 standards are references, not wholesale R3 policy; R3A milestones/authority governed by approved roadmap. |
| `hints/file-provenance.md` | 1.0.0; new-source requirements for exact origin, revision, and predecessor. | R3 source-creation conventions. |
| `r3a_plugins/institutional_knowledge/manifest.json` | Provider/operation 1.1.0, operation contract 1.0.0; plugin artifact SHA-256 `1af091cd41ace4cc9fa94d4a8d8d378163a08ea794611975b36849b6f2394054`. | Current read-only operation; provides no item review, approval, or ingestion route. |

## Classification summary

- **Current authoritative R3/R3A:** R3 charter, approved R3A roadmap, and the current R3 source boundaries as identified by the R3 index. These constrain candidate knowledge, even if a legacy source disagrees.
- **Current useful reference:** Estate software guidance on inspect-before-creating and no silent promotion; Riverview- proposal/approval separation. These remain external project references pending R3A decision.
- **Historical:** Riverview and Riverview- records with repository-local scope; old Estate onboarding pointer; older Riverview- AI_HINTS revisions.
- **Potential adaptation:** granular proposal review, explicit separation of draft, approval, and promotion; only if R3A owners accept the applicable rule.
- **Conflict/supersession:** Riverview's execution-first directions cannot override the active Steward directive requiring approval. CueMastery/Ionoge authority is project-specific. The Estate onboarding file is superseded as an entrypoint by root `AI_START_HERE.md`.
- **Unavailable/unverified:** literal R1/R2 repository identities; exact historical per-file modification times where Git metadata did not establish them; the exact Git object for TheEstate communications hints. None is treated as ingestion-ready.

## Review proposal set

Seven granular proposals are in [`knowledge_review_proposals.v1.json`](knowledge_review_proposals.v1.json). They retain source URL, repository path, commit, Git blob or SHA-256, excerpt location, category, scope assessment, known conflict and a **recommendation only**. No item is approved by its document or batch. Three current R3/R3A items are individually eligible for Steward review; adaptation, uncertain, conflicting, and project-specific items are flagged for individual disposition.
