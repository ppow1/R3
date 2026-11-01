<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/ESTATE_SPATIAL_CANON.md
Component: R3-ESTATE-SPATIAL
File Revision: 1.0.4
Created: 2026-10-31 UTC
Created By: ChatGPT GPT-6
Purpose: Record Steward-defined Engineering and Infrastructure spatial relationships
Execution Model: Design canon; no runtime
Observability: Visual and spatial acceptance
Dependencies: Approved estate artwork; future Operations reference
Authority: Steward's 2026-10-31 annotated screenshot and description
Changed: 2026-11-01T15:42:00Z | R3-P015 | ChatGPT GPT-6 | Correct the screenshot viewport height and recalculate the doorway anchor
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
- The minimized Engineering label target is the doorway/post shown in the Steward's 2026-11-01 placement screenshot. The 2026-11-01 target screenshot places the label center at approximately (589, 229) in a 1270×751 CSS-pixel reference viewport. With the approved artwork's measured 1536×1024 intrinsic dimensions and `background-size: cover`, this maps to the image-relative anchor `{x: .464, y: .328}`. The runtime uses the loaded artwork's intrinsic dimensions when mapping this point. The Snapshot API records the actual viewport and rendered panel rectangle for acceptance.
- Distinguish surface entry points, upper offices, underground floors, and infrastructure access in future 3D/spatial navigation; they are not interchangeable.

## Pending spatial references

- Steward will supply a second picture identifying the Operations area and its relationship to the Engineering underground extent.
- Exact world coordinates, floor heights, building footprints, CME interface, access paths and interactive hit regions remain undefined. Do not invent them.
