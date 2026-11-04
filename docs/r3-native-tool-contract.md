# R3 Native Tool Contract

Phase 2 defines R3-owned tool discovery and invocation, independent of R2 and Comms5. A descriptor includes a tool name, an OpenAI-compatible function definition, and a read-only flag. Invocation takes a tool name and JSON arguments and returns a structured outcome. The R3 server must independently authorize execution and audit each invocation. Uncertain outcomes must not be automatically replayed. Configurable transport settings belong in external configuration. No total task-duration cap.
