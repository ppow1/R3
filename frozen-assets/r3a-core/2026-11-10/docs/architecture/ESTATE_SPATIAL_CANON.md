<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/ESTATE_SPATIAL_CANON.md
Component: R3-ESTATE-SPATIAL
File Revision: 1.0.6
Created: 2026-10-31 UTC
Created By: ChatGPT GPT-6
Purpose: Record Steward-defined Engineering and Infrastructure spatial relationships
Execution Model: Design canon; no runtime
Observability: Visual and spatial acceptance
Dependencies: Approved estate artwork; future Operations reference
Authority: Steward's 2026-10-31 annotated screenshot and description
Changed: 2026-11-01 UTC | R3-PANEL-INTERACTION-002 | ChatGPT GPT-6 | Recalibrate Engineering anchor from newer placement screenshot; record draggable Infrastructure marker
Supersedes: None
Superseded By: None
Contracts: docs/IMPLEMENTATION_HANDOFF.md
Tests: Screenshot reference recorded; full-viewport runtime acceptance pending deployment
History/Predecessor: Git blob 13e759448d7d8e7948c41d5951d043c5728c8a71
-->
# Estate spatial canon — Engineering and Infrastructure

## Steward-established geography

- **Engineering entrance:** The lower-left entrance accessed from the walkway beside the Engineering Foundry minimized label in the 2026-10-31 screenshot. This is the label's home position and an entry point, not the full extent of Engineering.
- **Engineering offices:** The row of windows and upper walkway one level above the entrance.
- **Engineering complex:** Subterranean beneath the Great Courtyard, **at least six floors deep**, extending toward the estate's **Operations** area. Exact extents and floor geometry remain to be established.
- **CME relationship:** Engineering is intentionally close to CME.
- **Infrastructure building/entrance:** Between Engineering's entrance and the waterwheel, rising from the waterwheel base to approximately the level of the Engineering offices.
- **Infrastructure access points:** The top of the infrastructure tower and the walkway crossing in front of the waterwheel are intended interactive entry points to a detailed real-time under-the-hood infrastructure view.

## UI behavior contract

- Minimized Engineering Foundry becomes a compact, minimally distracting label at the Engineering entrance; use the panel's **45%** opacity slider minimum.
- On restore, return the window to its prior expanded position and opacity.
- The entrance anchor is image-relative and must account for background cover cropping/resizing; do not fix it to arbitrary viewport coordinates.
- The minimized Engineering label target is the doorway/post shown in the Steward's 2026-11-01 placement screenshot. The subsequent Steward-supplied placement references correct the earlier mapping: the prior point `{x: .464, y: .328}` places the label over the main hall and is superseded. The newer target screenshot (969×733 CSS-pixel viewport, marker center approximately (349, 479)) maps through the approved 1536×1024 artwork with `background-size: cover` to approximately `{x: .377, y: .653}`. The implementation uses this image-relative point and accounts for cover cropping. Confirm with a fresh browser snapshot; any further correction remains Steward-directed. The runtime uses loaded artwork dimensions and accounts for `background-size: cover`. The Snapshot API records the actual viewport and rendered panel rectangle for acceptance.
- Distinguish surface entry points, upper offices, underground floors, and infrastructure access in future 3D/spatial navigation; they are not interchangeable.

## Pending spatial references

- Steward will supply a second picture identifying the Operations area and its relationship to the Engineering underground extent.
- The Infrastructure minimized marker begins immediately to the right of Engineering and is draggable so the Steward can indicate the intended point. Its dragged browser-local position is recorded by Snapshot; final artwork position remains Steward-directed.
- Exact world coordinates, floor heights, building footprints, CME interface, access paths and interactive hit regions remain undefined. Do not invent them.
