<!--
R3 CONTROLLED DOCUMENT
File: README.md
Component: README-MD
File Revision: 1.0.3
Created: Unknown (legacy)
Created By: Unknown (legacy)
Purpose: R3 repository orientation
Execution Model: N/A
Observability: N/A
Dependencies: R3 repository
Authority: Existing document authority unchanged; see body
Changed: 2026-11-01T06:38:48.481Z | R3-P012 | ChatGPT GPT-6 | Update source and runtime verification status
Changed: 2026-11-11T13:54:20Z | R3-BRIDGE-V3-STEP7 | Codex GPT-6 | Index artifact registry and Bridge v3 design
Changed: 2026-11-11T14:12:52Z | R3-BRIDGE-V3-STEP10 | Codex GPT-6 | Index modular compliance matrix
Supersedes: None (see body for substantive charter revisions)
Contracts: hints/file-provenance.md
Tests: Not run (metadata-only)
History/Predecessor: Git blob a497bc5c02b8f330265a89cc5adc9531d00d64fb
-->
# Riverview 3 (R3)

Riverview 3 is a clean architectural evolution of Riverview, built to support persistent, general-purpose resident autonomy and observable operations.

## Starting point

This repository starts with planning and architectural contracts, not an automatic migration of Riverview 2 implementation.

Read [AI_HINTS.md](AI_HINTS.md) before making changes and [docs/PROJECT_CHARTER.md](docs/PROJECT_CHARTER.md) for goals, boundaries, and acceptance principles.

## Status

**Source status:** R3 includes a read-only capability API and an API-backed estate/Engineering home. Runtime deployment and browser behavior are not yet verified; see [the implementation handoff](docs/IMPLEMENTATION_HANDOFF.md).

Riverview 2 has a preservation package, but end-to-end recovery was not certified. R3 must not depend on that backup being restorable until independently verified.

## Operational records

- [Artifact and deployment registry](docs/operations/artifact-registry.md) — authoritative paths, lifecycle states, verification evidence, and handoffs.
- [Bridge v3 design and acceptance status](docs/operations/bridge-v3-design.md) — poll, routing, delivery, persistence, and provisioning contracts; unverified items are explicit.
- [Bridge v3 modular compliance matrix](docs/operations/bridge-v3-modular-compliance.md) — maps each feature to the existing R3A contracts and records gaps.
