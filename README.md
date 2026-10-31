<!--
R3 CONTROLLED DOCUMENT
File: README.md
Component: README-MD
File Revision: 1.0.0 (provenance baseline; earlier revisions not tracked)
Created: Unknown (legacy)
Created By: Unknown (legacy)
Purpose: R3 repository orientation
Execution Model: N/A
Observability: N/A
Dependencies: R3 repository
Authority: Existing document authority unchanged; see body
Changed: 2026-10-31 UTC | R3-PROVENANCE-001 | ChatGPT GPT-6 | Add provenance baseline
Supersedes: None (see body for substantive charter revisions)
Contracts: hints/file-provenance.md
Tests: Not run (metadata-only)
History/Predecessor: Git blob 92c1f2cf57093834e89dfa26b1e5dc6415c2e486
-->
# Riverview 3 (R3)

Riverview 3 is a clean architectural evolution of Riverview, built to support persistent, general-purpose resident autonomy and observable operations.

## Starting point

This repository starts with planning and architectural contracts, not an automatic migration of Riverview 2 implementation.

Read [AI_HINTS.md](AI_HINTS.md) before making changes and [docs/PROJECT_CHARTER.md](docs/PROJECT_CHARTER.md) for goals, boundaries, and acceptance principles.

## Status

**Charter stage.** No Riverview 3 runtime is claimed to exist yet.

Riverview 2 has a preservation package, but end-to-end recovery was not certified. R3 must not depend on that backup being restorable until independently verified.
