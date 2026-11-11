<!--
R3 CONTROLLED DOCUMENT
File: r3a_plugins/notification_service/capability.config.example.json
Component: R3A-NOTIFICATION-DELIVERY-CONFIG
File Revision: 1.0.0
Created: 2026-11-11 UTC (ported from reviewed provider candidate)
Created By: Codex GPT-6
Purpose: Supply non-secret defaults for provider registry staging.
Execution Model: CME capability configuration example.
Observability: Configuration schema validation.
Dependencies: manifest.read.json configuration_schema.
Authority: Issue #48, Planned Step 128; no credentials or grant authority.
Changed: 2026-11-11 | STEP-128 | Codex GPT-6 | Preserve the reviewed non-secret read configuration.
Supersedes: None.
Contracts: r3a.notification-delivery.config.v1.
Tests: tests/test_r3a_notification_package.py.
History/Predecessor: a3f82a0203b706dd75a831331004ffa294e984ba.
-->
# Notification provider configuration provenance

The example contains only an environment-variable name for the external database DSN and a presentation timezone. It contains no DSN value, recipient identity, grant, or credential.
