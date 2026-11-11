<!--
R3 CONTROLLED DOCUMENT
File: docs/IMPLEMENTATION_HANDOFF.md
Component: IMPLEMENTATION-HANDOFF
File Revision: 1.0.1
Created: Unknown (legacy; initial commit can establish earliest publication)
Created By: Unknown (legacy)
Purpose: R3 engineering reference and continuation guidance
Execution Model: N/A
Observability: N/A
Dependencies: R3 docs and hints index
Authority: R3 engineering guidance; approved charter prevails
Changed: 2026-11-01T06:38:48.481Z | R3-P012 | ChatGPT GPT-6 | Record initial API-backed estate home source state
Supersedes: None
Contracts: hints/file-provenance.md
Tests: Not run; frontend source state recorded without runtime verification
History/Predecessor: Git blob dd20520c94c80b236e5d7817ecb2376a5d016fca
-->
# R3 — Implementation Handoff and Working Decisions

**Recorded:** 2026-10-31  
**Scope:** `ppow1/R3` only. This is a continuation record, not a replacement for the approved charter.  
**Status:** Initial API-backed estate home and read-only capability API committed; runtime and deployment **not yet verified**.

## Read order for a new session

1. `AI_HINTS.md`
2. `docs/PROJECT_CHARTER_REVISION_2_REVIEW.md` (Steward-approved Revision 2)
3. `docs/PROJECT_CHARTER.md`, `docs/PUNCH_LIST.md`, `docs/PARKING_LOT.md`
4. This handoff
5. `r3_app.py` and `assets/visual-concepts/Riverview3_Visual_Concept_Library.zip`

## Architectural decisions confirmed in conversation

- **Capability-first institution:** The website is one interface, not the system. Operational features must be backed by reusable, permission-controlled APIs/tools consumable by the 2D site, Grace, authorized residents, engineering services, and eventually 3D/spatial Meta Quest interfaces. Presentation widgets themselves need not be standalone tools.
- **Institution-wide durability:** Continuity is for the institution as a whole, not only residents. R3 needs a **separate R3 PostgreSQL database/schema design** for authoritative durable state, historian, messages, engineering activity, permissions, and recovery. Dynamic state should not be hardcoded in the UI. Database implementation is still pending.
- **Fast and light:** Prioritize a working baseline website now, with minimal bureaucracy, responsive navigation, actual state or explicit unknown, and independently verifiable behavior. Do not import R2 wholesale.
- **Approved artwork is the visual baseline:** Preserve the selected modern estate dashboard design; do not substitute generic generated landscapes or a static document viewer. The ZIP contains `backgrounds/R3_modern_dashboard_as_is.png` (preferred UI concept), `backgrounds/R3_modern_estate_clean_concept.png` (newly generated companion, not pixel-perfect), originals, cropped overlay references, and README. Flattened raster overlays must become independent, functional components. Design includes estate landscape, clickable districts, left navigation, status indicators, resident hover/tap cards, collapsible resource/activity panels, and CME as institution-wide. Status indicators in concept art are illustrative, **not telemetry**.
- **R3-specific engineering visibility:** GitHub management initially covers **only `ppow1/R3`**. Show parallel branches, worktrees, commits, worker/session ownership, active vs idle/unknown, baseline SHA, ahead/behind, file overlap, and merge readiness. Branch existence or commit recency alone does not establish active work.
- **Avoid artificial integration work:** New Codex window does **not** imply new branch. Continue an existing worktree for the same assignment when practical. Know the starting commit, coordinate overlapping edits before work, integrate small verified changes promptly. A branch behind main is not automatically in conflict. Avoid gratuitous worktree/branch proliferation.
- **Folder-driven artwork library:** A Git-synchronized local Camrui directory is preferred for fast private-repo serving. Index image files dynamically by directory; no hardcoded image filenames. The archived ZIP is preserved intact, and images should be extracted into a separately tracked folder for gallery use. Sync and indexing status must be observable. Gallery APIs must be reusable by residents and spatial views.
- **Website baseline:** Approved visual home, responsive navigation, charter/punch list/parking lot, gallery, R3 branch/worktree view, actual status, and diagnostic snapshot. Reuse proven *patterns* from V2 for fast navigation and snapshot rather than transplanting V2 architecture. V2 reference paths previously inspected: `src/riverview/operator/ui.py`, `vnext.py`, `vnext_projection.py`, `snapshot.py` in `ppow1/Riverview`; responsive navigation and snapshot are still pending in R3.
- **Initial host:** Camrui Ubuntu (`192.168.1.155`, user `admin1`) is the initial deployment target; dev/prod isolation and repeatable verified deployment are desired. Do not claim a running website before testing.
- **Execution preference:** **Try Riverview Comms 1.1 first** for command execution on Camrui/Windows, and Codex when appropriate. If blocked, request user intervention with one copy-paste-ready command at a time. PowerShell: begin `Clear-Host`; Bash: begin `clear`; capture output, display it, and copy it to clipboard when supported.
- **Manual bootstrap:** Steward offered to assist with the first ~10 commits or fewer until auto-deployment is working. Git commits and deployment are distinct; do not demand manual deployment for every commit. Automate deployment early.

## Verified repository state at recording

- `docs/PROJECT_CHARTER_REVISION_2_REVIEW.md`: status APPROVED by Steward on 2026-10-31.
- `assets/visual-concepts/Riverview3_Visual_Concept_Library.zip`: 53,617,898 bytes on main, confirmed via GitHub tree. User's local source/copy SHA256: `F36706A016647776589A49C37721B553317849A9D59E20A714437F7183B3248F`. User-reported push commit `62d76894ec2c9ff994fe1f33ae6c59e02fbd74a9`.
- `r3_app.py`: read-only capability API, initially committed as `ddb47699139f1623e8df867601329710a0ea0f32`. Endpoints: `/api/v1/health`, `/api/v1/engineering/branches`, `/api/v1/engineering/worktrees`, `/api/v1/artwork`, `/api/v1/artwork/file/{relative_path:path}`, and the approved visual background. `web/index.html` now provides a full-bleed estate home with an initially minimized Engineering marker at the Steward's screenshot-derived doorway anchor and 45% opacity. Centering expands the panel; minimizing restores its saved expanded position and opacity. The Engineering panel reads health, branches, and worktrees from the same-origin APIs and labels unavailable data as unknown. **These frontend changes are source-only; deployment and browser acceptance remain unverified.** Responsive navigation, charter/punch-list/parking-lot views, dynamic gallery, diagnostic snapshot, authentication, PostgreSQL, worker session registry, and automated sync remain pending.
- Repository default branch is `main`. Do not create branches automatically for each new session.

## Immediate next implementation steps

1. Use **Riverview Comms 1.1** to inspect Camrui state, available R3 checkout, Python/runtime, PostgreSQL availability, and deployment constraints. No destructive changes.
2. Expand and visually accept the initial **interactive R3 frontend** from the approved artwork, adding fast responsive navigation and explicit unavailable/unknown telemetry.
3. Extract selected artwork into a browsable `assets/artwork/` folder, implement dynamic gallery with safe path handling, and make Git sync status observable.
4. Add R3 engineering activity projection: branches, worktrees, main baseline, ahead/behind, session ownership when verified, not invented activity.
5. Establish separate R3 PostgreSQL persistence and migration process for institution-wide state; don't block the first visible website on the entire data model.
6. Implement a useful diagnostic snapshot (manifest, runtime/version, projection freshness, redacted diagnostics), then test it.
7. Establish repeatable Camrui deployment, health check, and eventual auto-deploy. Verify browser access and real API behavior.

## Guardrails and unresolved details

- Do not conflate concept art with live hardware, network, model, weather, or service status.
- Never expose private GitHub tokens or sensitive server paths through public browser endpoints; secure operational APIs before exposing the site beyond trusted access.
- GitHub sync direction, authorization policy, PostgreSQL DB credentials, Camrui deployment paths, and production domain are **not yet verified**.
- Historical R2 services and performance are not assumed operational in R3.
- Record substantive acceptance evidence and exact commit/deployment SHAs. Do not mark implementation complete from a successful commit alone.
