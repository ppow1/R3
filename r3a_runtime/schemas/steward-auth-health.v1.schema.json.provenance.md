<!--
R3 CONTROLLED DOCUMENT
File: r3a_runtime/schemas/steward-auth-health.v1.schema.json
Component: R3A-AP3-IDENTITY
File Revision: 1.0.0
Created: 2026-11-09T17:31:32Z
Created By: R3 Integration
Purpose: Define privacy-safe R3A identity/session readiness response shape.
Execution Model: JSON Schema validation for the unauthenticated AP3 health endpoint.
Observability: Reports ready/unavailable states without account identifiers or secrets.
Dependencies: AP3 StewardAccess identity provider and durable session store.
Authority: Steward-approved R3A Authentication Independence; AP3/R3A-010.
Changed: 2026-11-09T17:31:32Z | AP3-NATIVE-AUTH | R3 Integration | Publish native authentication health response schema.
Supersedes: None.
Contracts: r3a.steward-auth-health.v1.
Tests: tests/test_r3a_native_identity.py.
History/Predecessor: Added by Remote Access commit 16b6230d5b48bb9bd1872f687f43678faeb296d7.
-->
