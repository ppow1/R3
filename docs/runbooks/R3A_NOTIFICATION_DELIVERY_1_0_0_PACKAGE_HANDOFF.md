<!--
R3 CONTROLLED DOCUMENT
File: docs/runbooks/R3A_NOTIFICATION_DELIVERY_1_0_0_PACKAGE_HANDOFF.md
Component: R3A-NOTIFICATION-DELIVERY
File Revision: 1.0.0
Created: 2026-11-11 UTC
Purpose: Hash-bound module release package and non-destructive install/rollback handoff.
Authority: Issue #48 Planned Step 69; no managed activation authorized.
-->
# Notification delivery provider 1.0.0 package handoff

## Immutable package

- Package: `artifacts/r3a-notification-delivery-1.0.0.tar.gz`
- SHA-256: `e3d38c9d32d4ac2ad96416cb16f3bc1d3cd8f55279fd40f6c75f3613cc312ab5`
- Sidecar: `artifacts/r3a-notification-delivery-1.0.0.tar.gz.sha256`
- Package contract: `r3a.module-release-package.v1`
- Module/provider: `r3a.notification-delivery@1.0.0`
- Operation in package: `notification.delivery.read`, effect `read`, exact required grant `notification.delivery.read`
- Store source digest: `059a1ef19c4f48e430b19a599062e5f91718fc27471af19680beeba9295c6992`
- Test command for deterministic package build and archive hash validation: `python scripts/package_notification_module.py --output artifacts/r3a-notification-delivery-1.0.0.tar.gz`

Build normalizes source line endings and fixes tar ownership, modes, timestamps, and gzip timestamp so identical source yields identical package bytes. The per-file inventory is inside `RELEASE_MANIFEST.json`. The package contains no DSN value, grant, or write-operation registration.

## Install and rollback boundary

The package regression extracts the immutable archive to an isolated temporary install root, then invokes the standard runtime configuration loader and capability registry against the extracted `manifest.read.json`. This validates staging/registration compatibility only. It does not alter a managed bootstrap or invoke CME services.

Coordinator activation requires an authorized maintenance window and must use the existing CME module install/config reload/lifecycle path, exact capability registration, provider-process DSN environment allowlist, and a separately verified exact `notification.delivery.read` grant. No grant or activation is evidenced by this package.

Before any future activation, preserve the exact prior bootstrap/config revision and module/provider version/digest. Rollback is to restore that saved configuration and immutable prior artifact, apply the existing CME config reload/lifecycle operations, then verify prior provider health and registration. Do not replace package files in place or restart Ring 0 to bypass module lifecycle.

`notification.delivery.acknowledge` and `notification.delivery.resolve` are not declared in this package. They remain blocked until #46 publishes and the Auditor reviews a generic CME-verified AP3 session-principal constraint; static people allowlists, wildcards, and Website-supplied authority remain prohibited.
