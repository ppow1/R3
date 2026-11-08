<!--
R3 CONTROLLED DOCUMENT
File: r3a_runtime/schemas/grace-objective-submission.v1.schema.json
Component: R3A-GRACE-OBJECTIVE-SUBMISSION
File Revision: 1.0.0
Created: 2026-11-07 UTC
Created By: Codex GPT-6
Purpose: Specify the versioned Steward-to-CME Grace objective submission request and accepted result.
Execution Model: JSON Schema Draft 2020-12 contract used by the website adapter and API tests.
Observability: Requires idempotency identity, durable activity identity, and CME correlation.
Dependencies: Existing CME `grace.objective.submit` control operation; #49 shared Steward session.
Authority: R3A Class I website work, Issue #51.
Changed: 2026-11-07 | R3A-007/R3A-010/R3A-019 | Define versioned objective submission envelope.
Supersedes: None.
Contracts: r3a.grace-objective-submission.v1@1.0.0.
Tests: tests.test_r3a_website validates route forwarding; live CME roundtrip pending coordinated service access.
History/Predecessor: New contract; initial publication recorded in Git.
-->
The service response includes only the contract fields guaranteed by this schema plus additional CME result fields. A successful 202 response means CME durably accepted an activity, not that Grace completed the requested work.
