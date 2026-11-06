<!--
R3 CONTROLLED DOCUMENT
File: docs/r3-assignment-intake-contract.md
Component: R3-STEWARD-ASSIGNMENT-INTAKE
File Revision: 1.3.0
Created: 2026-11-06T02:45:00Z
Created By: Codex GPT-6, acting on Steward instruction
Purpose: Define durable activity intake, status, and exact-grant blocked-resumption boundaries.
Execution Model: Loopback-only authenticated HTTP API hosted by runtime.serve.
Observability: Assignment event lineage plus canonical resident capability audit on resumption.
Dependencies: runtime.assignment_intake; runtime.resident_identity; runtime.capability_authority.
Authority: R3 assignment intake contract; resumption requires a resident credential and exact Steward-approved grant.
Contracts: runtime/assignment_intake.py; runtime/resident_inference.py::Inbox.resume_blocked
Tests: tests/test_assignment_resume_api.py
History/Predecessor: New file; no predecessor.
-->
# R3 Assignment Intake Contract

The API binds only to `127.0.0.1`. Every route requires the private assignment-intake bearer configured for the runtime.

## Submit and inspect

- `POST /v1/assignments` creates one durable `RESIDENT_ACTIVITY`, keyed by `Idempotency-Key`. The existing assignment schema and behavior are unchanged.
- `GET /v1/assignments/{root_event_id}` returns the durable continuation chain and independent verification projection for that assignment.

## Resume a blocked activity

`POST /v1/assignments/{root_event_id}/resume` requires both the assignment-intake bearer and an `X-R3-Resident-Credential` issued by the canonical R3 identity service. The body contains only `resolution_evidence` (1–2000 characters). The server derives the exact principal from the credential; it does not accept a principal in the body or headers.

The runtime must be explicitly configured with the same canonical `authority_database` used by R3 identity and grants. The resumption operation requires a current exact write grant for resource/scope `assignment:{assignment_id}` and action `resident.activity.resume`. It audits that authorization, preserves the original `BLOCKED` event and evidence, and enqueues at most one successor for matching principal and resolution evidence. Repeating the same request returns the same event ID; changed evidence conflicts.

The route does not create grants or credentials. Missing resident authentication returns 401, missing/inactive/ambiguous authority returns 403, a conflicting resumption returns 409, and unavailable canonical authority returns 503. When `authority_database` is not configured, the resumption route fails closed with 503; assignment submission and status continue to work.

Configure `assignment_intake.authority_database` in `config/runtime.json` or pass `--assignment-intake-authority-db` to `runtime.serve`. Deployment configuration must point to the pre-existing canonical authority database and must be separately verified; no production configuration or grant is changed by the development branch.
