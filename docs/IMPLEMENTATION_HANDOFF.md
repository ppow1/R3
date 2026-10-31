# R3 — Implementation Handoff and Working Decisions

**Recorded:** 2026-10-31  
**Scope:** `ppow1/R3` only. This is a continuation record, not a replacement for the approved charter.  
**Status:** First shared capability API committed; website and deployment **not yet verified**.

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
- **Website baseline:** Approved visual home, responsive navigation, charter/punch list/parking lot, gallery, R3 branch/worktree view, actual status, and diagnostic snapshot. Reuse proven *patterns* from V2 for fast navigation and snapshot rather than transplanting V2 architecture. V2 reference paths previously inspected: `src/riverview/operator/ui.py`, `vnext.py`, `vnext_projection.py`, `snapshot.py` in `ppow1/Riverview`; no R3 implementation of those patterns yet.
- **Initial host:** Camrui Ubuntu (`192.168.1.155`, user `admin1`) is the initial deployment target; dev/prod isolation and repeatable verified deployment are desired. Do not claim a running website before testing.
- **Execution preference:** **Try Riverview Comms 1.1 first** for command execution on Camrui/Windows, and Codex when appropriate. If blocked, request user intervention with one copy-paste-ready command at a time. PowerShell: begin `Clear-Host`; Bash: begin `clear`; capture output, display it, and copy it to clipboard when supported.
- **Manual bootstrap:** Steward offered to assist with the first ~10 commits or fewer until auto-deployment is working. Git commits and deployment are distinct; do not demand manual deployment for every commit. Automate deployment early.

## Verified repository state at recording

- `docs/PROJECT_CHARTER_REVISION_2_REVIEW.md`: status APPROVED by Steward on 2026-10-31.
- `assets/visual-concepts/Riverview3_Visual_Concept_Library.zip`: 53,617,898 bytes on main, confirmed via GitHub tree. User's local source/copy SHA256: `F36706A016647776589A49C37721B553317849A9D59E20A714437F7183B3248F`. User-reported push commit `62d76894ec2c9ff994fe1f33ae6c59e02fbd74a9`.
- `r3_app.py`: first FastAPI read-only capability API, committed as `ddb47699139f1623e8df867601329710a0ea0f32`. Endpoints: `/api/v1/health`, `/api/v1/engineering/branches`, `/api/v1/engineering/worktrees`, `/api/v1/artwork`, `/api/v1/artwork/file/{relative_path:path}`. Uses local Git checkout and `assets/artwork/`; requires `fastapi` and `uvicorn`. **Not deployed or runtime-tested.** No authentication, PostgreSQL, worker session registry, automated sync, frontend, or snapshot yet.
- Repository default branch is `main`. Do not create branches automatically for each new session.

## Immediate next implementation steps

1. Use **Riverview Comms 1.1** to inspect Camrui state, available R3 checkout, Python/runtime, PostgreSQL availability, and deployment constraints. No destructive changes.
2. Build a small, **real interactive R3 frontend** from the archived approved artwork, with fast navigation and explicit unavailable/unknown telemetry.
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
