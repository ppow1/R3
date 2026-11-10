<!--
R3 CONTROLLED DOCUMENT
File: r3a_plugins/notification_source/manifest.activity-intake.json.provenance.md
Component: R3A-NOTIFICATION-HANDLER-MANIFEST-PROVENANCE
File Revision: 1.2.0
Created: 2026-11-10T18:53:48Z
Created By: Codex GPT-6
Purpose: Record provenance for the handler-bearing notification activity-intake manifest.
Execution Model: N/A; provenance sidecar for JSON metadata.
Observability: The manifest pins provider/module versions, artifact digest, capabilities, and handler contract.
Dependencies: r3a.module-manifest.v1@1.2.0; r3a.activity-handler.v1.1@1.1.0; r3a.activity-intake.v1@1.0.0.
Authority: Issue #48 assignment comment 6775162550; AD-024; approved Modularity Compliance Specification v1.
Changed: 2026-11-10T18:53:48Z | R3A-CORE-FREEZE-CORRECTION | Codex GPT-6 | Record source and contract provenance for the published notification handler declaration.
Changed: 2026-11-10 | STEWARD-P0-FS01 | Codex GPT-6 | Pin provider 1.2.0 and handler v1.1 result evidence/checkpoint schemas.
Changed: 2026-11-10T20:10:03Z | R3A-GENERIC-OBJECTIVE-CONTINUATION | R3A Coordinator | Pin provider/module 1.3.0 with durable objective action and disposition continuation schemas.
Supersedes: None.
Contracts: r3a.notification-activity-intake@1.3.0; r3a.notification.event-review@1.1.0; r3a.activity-handler.objective-submission@1.0.0.
Tests: tests/test_r3a_notification_source_plugin.py; tests/test_r3a_notification_handler_process.py; tests/test_r3a_activity_intake_consumer.py.
History/Predecessor: Git blob bc7ab9120213cbb4657c059998825563fc84dba1 at Notifications commit f95eeef063925ee9471553b66ab05744d7ffcbf5.
-->
# Notification activity-intake manifest provenance

The paired JSON manifest registers the read-only `notification.activity-intake.prepare` operation and declares handler `r3a.notification.event-review@1.1.0` for `notification.event.review`. Its v1.1 handler emits a source-bound generic objective-submission action, then returns only after consuming CME's durable resident result. The registered module formulates the notification review objective and owns disposition interpretation; CME retains authorization, resident execution, activity state, inference budgeting, audit, persistence, and recovery. Registration does not grant `notification.source.read`.
