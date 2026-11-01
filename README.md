<!--
R3 CONTROLLED DOCUMENT
File: README.md
Component: README-MD
File Revision: 1.0.1
Created: Unknown (legacy)
Created By: Unknown (legacy)
Purpose: R3 repository orientation
Execution Model: N/A
Observability: N/A
Dependencies: R3 repository
Authority: Existing document authority unchanged; see body
Changed: 2026-11-01T06:38:48.481Z | R3-P012 | ChatGPT GPT-6 | Update source and runtime verification status
Supersedes: None (see body for substantive charter revisions)
Contracts: hints/file-provenance.md
Tests: Not run (metadata-only)
History/Predecessor: Git blob 8303754b13de16a4ed23f8b61e7c9488ffefabb5
-->
# Riverview 3 (R3)

Riverview 3 is a clean architectural evolution of Riverview, built to support persistent, general-purpose resident autonomy and observable operations.

## Starting point

This repository starts with planning and architectural contracts, not an automatic migration of Riverview 2 implementation.

Read [AI_HINTS.md](AI_HINTS.md) before making changes and [docs/PROJECT_CHARTER.md](docs/PROJECT_CHARTER.md) for goals, boundaries, and acceptance principles.

## Status

**Source status:** R3 includes a read-only capability API and an API-backed estate/Engineering home. Runtime deployment and browser behavior are not yet verified; see [the implementation handoff](docs/IMPLEMENTATION_HANDOFF.md).

Riverview 2 has a preservation package, but end-to-end recovery was not certified. R3 must not depend on that backup being restorable until independently verified.
