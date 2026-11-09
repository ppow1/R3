<!--
R3 CONTROLLED DOCUMENT
File: r3a_runtime/schemas/steward-login-request.v1.schema.json
Component: R3A-AP3-IDENTITY
File Revision: 1.0.0
Created: 2026-11-09T17:31:32Z
Created By: R3 Integration
Purpose: Define versioned login, enrollment, and credential recovery request shapes.
Execution Model: JSON Schema validation for the AP3 same-origin session endpoint.
Observability: Schema ID and version accompany source contract; request payloads are not logged.
Dependencies: `r3a.identity-provider.v1`; AP3 native Steward identity provider.
Authority: Steward-approved R3A Authentication Independence; AP3/R3A-010.
Changed: 2026-11-09T17:31:32Z | AP3-NATIVE-AUTH | R3 Integration | Publish login and governed challenge request schema.
Supersedes: None.
Contracts: r3a.steward-login-request.v1.
Tests: tests/test_r3a_native_identity.py.
History/Predecessor: Added by Remote Access commit 16b6230d5b48bb9bd1872f687f43678faeb296d7.
-->
