<!--
R3 CONTROLLED DOCUMENT
File: r3a_plugins/notification_service/manifest.json.provenance.md
Component: R3A-NOTIFICATION-SERVICE-MANIFEST-PROVENANCE
File Revision: 1.0.1
Created: 2026-11-10T18:53:48Z
Created By: Codex GPT-6
Purpose: Record provenance for the notification service manifest and its supporting artifact pins.
Execution Model: N/A; provenance sidecar for JSON metadata.
Observability: Manifest digest pins are verified by the service manifest regression.
Dependencies: Notification service v1.2.1; source adapter; capability contract runtime.
Authority: Issue #48; Independent Auditor finding 6774873463; core matrix 4e5b2c2.
Changed: 2026-11-10T18:53:48Z | R3A-CORE-FREEZE-CORRECTION | Codex GPT-6 | Reconcile manifest pins to canonical package artifacts and the reviewed shared contract source.
Changed: 2026-11-10 | R3A-COORDINATOR-FS01 | Coordinator | Pin the exact integrated capability_contracts.py content digest for this candidate.
Supersedes: None.
Contracts: r3a.notifications@1.2.1; r3a.capability-operation.v1.
Tests: tests/test_r3a_notification_service.py::NotificationServicePresentationTests.test_versioned_service_manifest_pins_runtime_artifacts_and_categories.
History/Predecessor: Commit bcae2fc; pins were corrected to current canonical source digests.
-->
# Notification service manifest provenance

The v1.2.1 service manifest's supporting-artifact pin for `r3a_runtime/capability_contracts.py` is `4526128a338af6c106d48b6ad8cdf23e2990414886478804cf090127bc5bd2bc`, matching the exact integrated Coordinator source at candidate construction. The notification source manifest and adapter pins are refreshed to their current canonical content. The JSON manifest remains the authoritative package declaration.
