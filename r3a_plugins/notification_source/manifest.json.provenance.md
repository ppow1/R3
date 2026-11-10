<!--
R3 CONTROLLED DOCUMENT
File: r3a_plugins/notification_source/manifest.json.provenance.md
Component: R3A-NOTIFICATION-SOURCE-MANIFEST-PROVENANCE
File Revision: 1.0.0
Created: 2026-11-10T18:53:48Z
Created By: Codex GPT-6
Purpose: Record provenance for the legacy N1 notification source operation manifest.
Execution Model: N/A; provenance sidecar for JSON metadata.
Observability: The manifest pins the source provider artifact, operation, and required grant.
Dependencies: r3a.notification-intake.v1; r3a.capability-operation.v1.
Authority: Issue #48; existing N1 compatibility contract.
Changed: 2026-11-10T18:53:48Z | R3A-CORE-FREEZE-CORRECTION | Codex GPT-6 | Refresh the source provider artifact pin while preserving the N1 contract.
Supersedes: None.
Contracts: notification.source.read@1.0.0; notification.source.read grant.
Tests: tests/test_r3a_notification_source_plugin.py.
History/Predecessor: Commit bcae2fc; legacy operation remains available beside the generic adapter.
-->
# Notification source manifest provenance

This manifest continues to expose the N1 `notification.source.read@1.0.0` operation. Its artifact digest reflects the controlled source adapter bytes. The separately registered activity-intake manifest adds the generic handler role; it does not replace this N1 operation during rollout.
