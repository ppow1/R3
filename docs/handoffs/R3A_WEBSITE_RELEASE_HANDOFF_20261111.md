<!--
R3 CONTROLLED HANDOFF
File: docs/handoffs/R3A_WEBSITE_RELEASE_HANDOFF_20261111.md
Component: R3A-AP3-WEBSITE
Revision: 1.0.0
Purpose: Transfer the exact Website source bundle and candidate verification evidence to Coordinator/Auditor.
Authority: Issue #61 comment 6803610860; governed by Issue #51.
Security: Candidate only; no production activation, service restart, grant, or secret delivery.
-->

# R3A Website release candidate handoff — 2026-11-11

## Immutable source package

- Repository: `ppow1/R3`
- Branch: `engineering/r3a-ap3-website-20261107`
- Exact source SHA: `32077703603fba2a4595348d81b7d1b0ee2472e9`
- Package: [`artifacts/releases/r3a-website-32077703603fba2a4595348d81b7d1b0ee2472e9.tar.gz`](../../artifacts/releases/r3a-website-32077703603fba2a4595348d81b7d1b0ee2472e9.tar.gz)
- Package archive SHA-256: `a23d6c1b961ff976bccbb168e077f31096b999388e64e1510a4b5e0bfcfd18da`
- Sidecar: [`artifacts/releases/r3a-website-32077703603fba2a4595348d81b7d1b0ee2472e9.tar.gz.sha256`](../../artifacts/releases/r3a-website-32077703603fba2a4595348d81b7d1b0ee2472e9.tar.gz.sha256)
- In-archive manifest: `WEBSITE_PACKAGE_MANIFEST.json`; contract `r3a.website-release-package.v1`; 414 file entries and per-file SHA-256/byte length. Archive size: 912 KB. Only `assets/visual-concepts/Riverview3_Visual_Concept_Library.zip` is excluded, because it is an unused design reference; that exclusion and reason are recorded in the manifest.
- Runtime dependency lock: 20 exact Linux CPython 3.12 wheel pins including generated hashes for `psycopg`, `psycopg-binary`, and `psycopg-pool`. Hashes were generated from downloaded wheel bytes using the existing candidate lock generator after candidate installation proved the old omission.
- Configuration: package contains only `r3a_plugins/steward_access.r3a-native.config.example.json`, with placeholder origin/environment references and no credential/token/DSN value. Real AP3 config remains operator-owned, external, and mode 0600.
- Install/rollback: use the existing exact-SHA candidate builder and loopback verifier plus [R3A LAN deployment runbook](../runbooks/R3A_LAN_HTTPS_DEPLOYMENT.md). Coordinator controls staging, active working-directory/config changes, Website-only service restart, and restoration of the prior exact source/config revision. This handoff is not deployment authorization.

## Independent verification

- Package builder and verifier both completed for the exact source SHA. Re-running `verify --sha256 a23d6c…18da` reports `verified: true`, 414 entries, and source commit `320777…2472e9`.
- Isolated dependency installation from the new hash-locked file completed (`BUILD_PASS=TRUE`, 20 pinned packages); active checkout and shared service environment were untouched.
- In the fresh isolated candidate venv, Website Python/API and package tests: **26 passed**. Website client/operations/roadmap suites: **28 passed**.
- Extracted the exact `.tar.gz` bundle into a disposable directory and repeated **26 Python + 28 Node tests** against extracted files. A process launched from the extracted package on ephemeral loopback returned `/api/v1/health` with status `running` and `/` HTTP 200 (98,493-byte response); the process was terminated after probes.
- Existing `verify_candidate_runtime.py` on the isolated commit candidate: `RUNTIME_VERIFICATION_PASS=TRUE`, health HTTP 200, homepage HTTP 200, exact candidate commit confirmed, candidate server stopped, activation `NOT_RUN`.
- **Full-repository regression is not green:** the repository candidate script's broad discovery requires test-only `pytest` not in production lock and fails before completion in the fresh runtime venv. With the existing provisioned R3A test environment, 414 tests ran: **3 failures, 2 errors, 5 skipped**. Exact failures are `test_r3a_institutional_directory.InstitutionalDirectoryProviderTests.test_dynamic_grace_tool_receives_directory_output_and_distinct_evidence` (error), `test_r3a_institutional_knowledge.InstitutionalKnowledgeProviderTests.test_registered_operation_is_the_existing_grace_capability_and_carries_provenance` (error), `test_r3a_institutional_knowledge.InstitutionalKnowledgeProviderTests.test_denied_retrieval_never_loads_or_returns_source_content` (assertion after the same missing execution-adapter condition), `test_r3a_notification_service.NotificationServicePresentationTests.test_versioned_service_manifest_pins_runtime_artifacts_and_categories` (stale artifact digest), and `test_r3a_telemetry_inbox_demo.TelemetryInboxDemo.test_grace_discovers_authorized_plugin_and_invokes_from_queued_objective` (fixture registers zero tools). They are not modified in this Website candidate. Coordinator/CME, Knowledge, Notifications, and telemetry owners must reconcile these before declaring the integrated repository suite green. Website-focused suites and packaged runtime are independently passing.
- No authenticated Steward browser credentials/session were available. No real Grace response, authenticated reload persistence, mobile/accessibility acceptance, notification inbox, or private GitHub retrieval is claimed.

## Audit and Coordinator requests

1. Auditor: review exact source SHA `32077703603fba2a4595348d81b7d1b0ee2472e9` and package digest `a23d6c1b961ff976bccbb168e077f31096b999388e64e1510a4b5e0bfcfd18da`; confirm manifest/digest integrity, configuration/secrets boundary, packaging dependencies, and architecture compliance. Report exact disposition against this package, not a later moving branch head.
2. Coordinator: review candidate with source commit `320777…2472e9`, confirm integration target/source compatibility, and plan controlled Website-owned activation/rollback only after review and current deployment authorization. Do not touch shared services as part of source review.
3. Keep the full feature backlog and external API/runtime dependencies in [the acceptance matrix](../architecture/R3A_WEBSITE_ACCEPTANCE_MATRIX_2026-11-11.md). The live Grace response failure remains owned by Coordinator/CME/Autonomy; notifications, Engineering repository access, model readiness, conversation lifecycle and genuine streaming require their approved interface owners.
