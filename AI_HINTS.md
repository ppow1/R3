# AI_HINTS.md — Riverview 3

## First-read instructions

1. Read `README.md` and `docs/PROJECT_CHARTER.md` before proposing or editing architecture.
2. Inspect existing code and current deployment state before claiming a capability works. Separate observed facts, hypotheses, and plans.
3. Do not import or rewrite Riverview 2 wholesale. Migration requires an explicit inventory, interface contracts, tests, and approval.
4. **Engineering scope is not operational scope.** Keep each change focused; never implement arbitrary limits on Grace's objectives, reasoning cycles, assignments, work orders, concurrency, or tool types merely because a test uses one scenario.
5. Grace is an ongoing Operations Manager and reasoning agent, **not** merely a work-order dispatcher. Tool choice, continuation, error recovery, and autonomous reasoning are core requirements.
6. Preserve meaningful authorization and audit boundaries while avoiding unnecessary approval bureaucracy and state-machine complexity.
7. Record observable state transitions, branch/sequence IDs, tool actions, outcomes, failures, and recovery evidence. The UI must show current actual state, not a fabricated success.
8. Fail closed on verification: an artifact existing is not proof its acceptance criteria were met. Require substantive evidence, commit/reference when relevant, and independent checks.
9. Keep changes reversible and testable; protect production systems and Riverview 2 backups. No destructive commands or deployments without explicit authorization.
10. Before implementation, propose the smallest vertical slice that demonstrates a persistent autonomous reasoning-and-tool loop with verifiable outcomes.

## Architecture anchors

- Grace: persistent general-purpose Operations Manager
- CME: continuous operational motion rather than a one-shot workflow
- Residents: differentiated reasoning/tool-capable participants with continuity
- Model tiers: lightweight autonomic routing, vision, and higher-capacity reasoning; deployment choices are replaceable
- Historian / SCADA-HMI: accurate live state, durable events, recovery, and operator visibility
- Tests: behavior and substantive verification, not just successful API responses

## Work discipline

Provide concise evidence and exact repository paths/functions. Avoid speculative large refactors and repeated diagnostic loops. Treat all earlier Riverview 2 observations as historical context until verified against R3.
