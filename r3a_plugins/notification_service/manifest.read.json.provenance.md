<!--
R3 CONTROLLED DOCUMENT
File: r3a_plugins/notification_service/manifest.read.json
Component: R3A-NOTIFICATION-DELIVERY-MANIFEST
File Revision: 1.1.0
Created: 2026-11-11 UTC (ported from reviewed provider candidate)
Created By: Codex GPT-6
Purpose: Declare the notification delivery read provider and exact CME grant.
Execution Model: CME capability registry input.
Observability: Manifest and pinned provider/support artifact digests.
Dependencies: R3A module manifest v1; capability provider v1.
Authority: Issue #48, Planned Step 128; read only, no activation.
Changed: 2026-11-11 | STEP-128 | Codex GPT-6 | Version provider package to 1.2.2.
Supersedes: Provider manifest revision 1.0.0 for the same read-only operation.
Contracts: r3a.module-manifest.v1; r3a.capability-operation.v1.
Tests: tests/test_r3a_notification_capability.py; tests/test_r3a_notification_package.py.
History/Predecessor: a3f82a0203b706dd75a831331004ffa294e984ba.
-->
# Notification read manifest provenance

This JSON manifest declares only `notification.delivery.read` with effect `read` and exact required grant `notification.delivery.read`. Provider/package version is 1.2.2. The provider source code is unchanged from the independently reviewed read-only candidate; the versioned manifest and archive bind the active-baseline package release.
