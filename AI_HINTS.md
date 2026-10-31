# AI_HINTS.md — Riverview 3

Start with [the hints index](hints/README.md). Keep this root file short; put detailed guidance in `hints/` and link onward to authoritative documents.

## Essential rules

- Read the approved [R3 charter](docs/PROJECT_CHARTER_REVISION_2_REVIEW.md) before architectural changes.
- Inspect actual repository and runtime state; distinguish verified behavior from requirements and plans.
- **Engineering scope is not operational scope.** Do not impose arbitrary limits on Grace or other residents based on a narrow test.
- Preserve authorization, audit, recovery, substantive verification, and truthful UI status without unnecessary bureaucracy.
- Do not migrate Riverview 2 wholesale or modify production/backups without explicit authorization.
- Favor small, testable changes and verified outcomes.

## First-level references

- [Engineering and current handoff](hints/engineering.md)
- [Institutional architecture and durable state](hints/architecture.md)
- [Deployment and command execution](hints/deployment.md)

When asked to add material to AI_HINTS, update a focused `hints/` document and add or adjust a concise pointer here only if needed.
