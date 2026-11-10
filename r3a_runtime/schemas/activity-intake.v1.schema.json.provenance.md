<!--
R3 CONTROLLED DOCUMENT
File: r3a_runtime/schemas/activity-intake.v1.schema.json
Component: R3A-ACTIVITY-INTAKE-SCHEMA
File Revision: 1.0.1
Created: 2026-11-10T00:50:25Z
Created By: Codex GPT-6
Purpose: Validate the durable source-to-CME activity intake envelope.
Execution Model: JSON Schema draft 2020-12.
Observability: Validation errors identify the envelope path.
Dependencies: CME activity intake and r3a.activity-intake.v1.
Authority: AD-024; source registration and authorization remain separate from this schema.
Changed: 2026-11-10T00:50:25Z | R3A-AD024-MODULAR-DISPATCH | Codex GPT-6 | Add intake schema for generic handler activity types.
Changed: 2026-11-10T01:00:00Z | R3A-AD024-MODULAR-DISPATCH | Codex GPT-6 | Cover generic event types with typed activity lineage and durable lifecycle projection.
Supersedes: None
Contracts: r3a.activity-intake.v1; r3a.activity-handler.v1.
Tests: Schema validation is exercised by CME intake tests.
History/Predecessor: New schema; initial publication recorded in Git.
-->
