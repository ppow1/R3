<!--
R3 CONTROLLED DOCUMENT
File: docs/runbooks/R3A_NOTIFICATION_DELIVERY_1_2_2_PACKAGE_HANDOFF.md
Component: R3A-NOTIFICATION-DELIVERY
File Revision: 1.0.1
Created: 2026-11-11 UTC
Created By: Codex GPT-6
Purpose: Record the immutable read-only notification package and safe future registration/restore steps.
Execution Model: Release handoff; no deployment execution.
Observability: In-band file inventory and outer SHA-256 sidecar.
Dependencies: r3a.module-release-package.v1; existing CME capability registry and lifecycle.
Authority: Issue #48 Planned Step 128; no grant or activation authorization.
Changed: 2026-11-11 | STEP-128 | Codex GPT-6 | Bind the rebuild to exact committed package source d09066d.
Supersedes: R3A_NOTIFICATION_DELIVERY_1_0_0_PACKAGE_HANDOFF.md from prior package branch.
Contracts: notification.delivery.read; exact grant notification.delivery.read.
Tests: tests/test_r3a_notification_package.py; tests/test_r3a_notification_capability.py.
History/Predecessor: Active baseline 651014cdab52e679e9adb3076ad4bbd0561cd15c; provider source a3f82a0203b706dd75a831331004ffa294e984ba; package source d09066d30102ec8a154644fdf8395b9f71a5b4eb.
-->
# Notification delivery read provider 1.2.2

## Immutable package

- Archive: `artifacts/r3a-notification-delivery-1.2.2.tar.gz`
- SHA-256: `4af1939e30b51ec18c59e9512eba08a13e71259e1f30d144d68f44ee472916e8`
- Sidecar: adjacent `.sha256`
- Package contract: `r3a.module-release-package.v1`
- Module/provider: `r3a.notification-delivery@1.2.2`
- Registered operation: `notification.delivery.read`, effect `read`, exact grant `notification.delivery.read`
- Write operations: not registered
- Exact package source: `d09066d30102ec8a154644fdf8395b9f71a5b4eb`, directly based on active integration correction `651014cdab52e679e9adb3076ad4bbd0561cd15c`.
- Provider implementation provenance: retained read-only provider source from previously reviewed candidate `a3f82a0203b706dd75a831331004ffa294e984ba`; this exact provider source is part of package source commit `d09066d` and archive inventory.

The in-band `RELEASE_MANIFEST.json` inventories all four payload files and pins each digest. The package verifier checks the sidecar, archive paths, inventory closure, provider pins, operation version and exact read-only grant. Builds normalize source bytes and fix archive timestamps, ownership and modes.

Build and verify:

```powershell
python scripts/package_notification_module.py --output artifacts/r3a-notification-delivery-1.2.2.tar.gz
python -c "from pathlib import Path; from scripts.package_notification_module import verify_package; verify_package(Path('artifacts/r3a-notification-delivery-1.2.2.tar.gz'))"
python -m pytest -q tests/test_r3a_notification_capability.py tests/test_r3a_notification_package.py
```

## Managed registration/configuration handoff (not executed)

The Coordinator must choose the existing managed bootstrap and versioned install root; neither path is assumed here. Before any future change, preserve the current bootstrap/configuration bytes and SHA-256 in the controlled change record. Extract the archive only to a new versioned staging directory under the approved existing application root, verify the in-band inventory and sidecar, and retain the prior provider package unchanged.

Add only the package's `manifest.read.json` and a separately protected configuration file to the existing `capability_operations` array. The configuration shape is:

```json
{
  "dsn_env": "R3A_NOTIFICATION_DATABASE_DSN",
  "presentation_timezone": "UTC"
}
```

The actual DSN must come from the managed secret environment; it is not included in the archive or repository. Add only `notification.delivery.read` to the host module's declared capabilities. Do not register acknowledge/resolve operations, add a grant, or infer that an existing grant is present. A separately authorized Coordinator may then use the existing configuration reload and module install/lifecycle operations from the approved host runbook; packaging itself performs none of these operations.

## Restore path

For any future managed registration, first stop admission and deactivate this exact provider version through the existing CME lifecycle. Restore the saved bootstrap/configuration bytes and verify their recorded digest, apply the normal configuration reload, and confirm the prior provider version and digest are restored to their previous lifecycle state. Keep both immutable packages; do not overwrite a version directory. No install, configuration reload, grant, activation, service restart, or production change was performed for this handoff.
