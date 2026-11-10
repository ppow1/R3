<!--
R3 CONTROLLED DOCUMENT
File: r3a_plugins/notification_source/manifest.activity-intake.json.provenance.md
Component: R3A-NOTIFICATION-HANDLER-MANIFEST-PROVENANCE
File Revision: 1.1.0
Created: 2026-11-10T18:53:48Z
Created By: Codex GPT-6
Purpose: Record provenance for the handler-bearing notification activity-intake manifest.
Execution Model: N/A; provenance sidecar for JSON metadata.
Observability: The manifest pins provider/module versions, artifact digest, capabilities, and handler contract.
Dependencies: r3a.module-manifest.v1@1.2.0; r3a.activity-handler.v1.1@1.1.0; r3a.activity-intake.v1@1.0.0.
Authority: Issue #48 assignment comment 6775162550; AD-024; approved Modularity Compliance Specification v1.
Changed: 2026-11-10T18:53:48Z | R3A-CORE-FREEZE-CORRECTION | Codex GPT-6 | Record source and contract provenance for the published notification handler declaration.
Changed: 2026-11-10 | STEWARD-P0-FS01 | Codex GPT-6 | Pin provider 1.2.0 and handler v1.1 result evidence/checkpoint schemas.
Supersedes: None.
Contracts: r3a.notification-activity-intake@1.2.0; r3a.notification.event-review@1.0.0.
Tests: tests/test_r3a_notification_source_plugin.py; tests/test_r3a_notification_handler_process.py; tests/test_r3a_activity_intake_consumer.py.
History/Predecessor: Commit bcae2fc published the initial handler-bearing manifest.
-->
# Notification activity-intake manifest provenance

The paired JSON manifest registers the read-only `notification.activity-intake.prepare` operation and declares handler `r3a.notification.event-review@1.0.0` for `notification.event.review`. Its v1.1 result carries source evidence, source-bound idempotency/correlation checkpoints, and lifecycle projection. Until CME exposes a generic Grace objective continuation over the registered action socket, the handler blocks without acknowledging or resolving the event. Registration does not grant `notification.source.read`; CME remains the authority and durable ledger owner.
