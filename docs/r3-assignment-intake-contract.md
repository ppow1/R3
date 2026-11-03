<!--
R3 CONTROLLED DOCUMENT
File: docs/r3-assignment-intake-contract.md
Component: R3-ASSIGNMENT-INTAKE-CONTRACT
File Revision: 1.0.0
Created: 2026-11-03 UTC (exact time unverified)
Created By: ChatGPT GPT-6 via GitHub API
Purpose: Define the R3-owned assignment ingress contract for the resident runtime.
Execution Model: Local HTTP API hosted by runtime.serve when explicitly enabled.
Observability: Assignment event IDs, idempotency records, inbox status, continuation lineage, and independent review state.
Dependencies: runtime/assignment_intake.py; runtime/serve.py; SQLite institution database.
Authority: R3 Steward authority; no R2 workflow fallback.
Changed: 2026-11-03 UTC | R3-ASSIGNMENT-INTAKE-001 | ChatGPT GPT-6 | Define authenticated backend assignment intake.
Supersedes: None
Contracts: docs/PROJECT_CHARTER_REVISION_2_REVIEW.md; hints/engineering-test-policy.md
Tests: tests/test_assignment_intake.py
History/Predecessor: New file.
-->
# R3 resident assignment intake

## Purpose

This API is the backend seam for a Steward-authenticated Riverview interface to submit assignments into the existing R3 resident inbox. It does not create or approve an objective, and does not call Riverview 2 Comms5 workflows.

The API is disabled unless runtime.serve receives both --assignment-intake-port and --assignment-intake-token-file. It binds only to 127.0.0.1. The token file must be readable by the service and have no group/world permissions; the token must contain at least 32 characters.

## Submit an assignment

POST /v1/assignments

Headers:

- Authorization: Bearer <server-side integration token>
- Idempotency-Key: <stable retry key>
- Content-Type: application/json

JSON body:

    {
      "resident": "Grace",
      "assignment_id": "steward-issued-stable-id",
      "objective": "The assignment objective",
      "acceptance_criteria": [
        {
          "id": "criterion-id",
          "version": "1",
          "description": "A checkable acceptance condition"
        }
      ],
      "next_step": "Optional initial direction",
      "correlation_id": "Optional Riverview correlation"
    }

A new assignment returns HTTP 202 with its durable inbox event ID. An identical retry returns HTTP 200 and the same event ID. Reusing either the idempotency key or assignment ID with changed content returns HTTP 409. The event is inserted atomically with the idempotency records and is processed by the ordinary resident scheduler.

The endpoint accepts only residents configured for RESIDENT_ACTIVITY continuation. Acceptance criteria remain attached to the event and are used by the existing independent-review flow when Grace reports completion.

## Read assignment status

GET /v1/assignments/{root_event_id} returns the durable event/continuation lineage and the independent verification status. COMPLETED inbox events remain distinct from independent assignment acceptance.

## Integration security

The website backend must authenticate the Steward before calling the loopback API. It must keep the token on the server and must never place it in browser JavaScript, HTML, URLs, or client-visible logs. Do not expose the intake listener on LAN or Internet interfaces. If an authenticated R3-native Comms service becomes available, it can call this same API through the same narrowly scoped integration credential; this endpoint does not establish that such a Comms service already exists.
