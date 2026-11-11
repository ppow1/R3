<!--
R3 CONTROLLED HANDOFF
File: docs/handoffs/R3A_WEBSITE_RELEASE_HANDOFF_20261111_6e5f3a6.md
Component: R3A-AP3-WEBSITE
Purpose: Record exact Step 89 source/package evidence for independent Auditor review.
Authority: Issue #61 comment 6804626987; governing Issues #51 and #56.
Security: Candidate only; no production activation, shared service restart, grant, or secret delivery.
-->

# R3A Website Step 89 rework — exact candidate evidence

## Immutable source and package

- Repository: `ppow1/R3`
- Branch: `engineering/r3a-ap3-website-20261107`
- Exact package source commit: `6e5f3a6ceea723d0217367c57afd20d9b4c437bd`
- Package: [`artifacts/releases/r3a-website-6e5f3a6.tar.gz`](../../artifacts/releases/r3a-website-6e5f3a6.tar.gz)
- SHA-256: `85322406cc44c1796af211176d7b6bd2d2abc17a92d3f511a1c85e534480914e`
- In-archive manifest: `WEBSITE_PACKAGE_MANIFEST.json`, contract `r3a.website-release-package.v1`, source commit above, **422** tracked file entries with per-file byte lengths and SHA-256. The package verifier passed against the exact expected archive digest.
- The package carries the required background image (`3,605,170` bytes; SHA-256 `7d6c2eb3d3c5016f30add672baec7276e8a9a0cb0f1bfb8a04a70d02c2d7756f`) with provenance and excludes the 53 MB source concept archive. The 20-wheel hash-pinned runtime dependency lock is preserved; Step 89 changed no dependency pin.
- The previous source/archive pair `32077703603fba2a4595348d81b7d1b0ee2472e9` / `a23d6c1b961ff976bccbb168e077f31096b999388e64e1510a4b5e0bfcfd18da` was reviewed FAIL and omitted a runtime image; the intermediate `5227dd2` package predates this Step 89 rework. Neither is the current candidate.

## Auditor findings corrected

1. Removed the disabled **“Assign work to Grace”** message-toolbar item. The conversation interface has no generic registered work capability in its contract, so the Website does not imply one. The mounted chat regression selects non-Grace resident Vicky, renders her real-shaped resident message, and asserts her rendered message and toolbar contain no Grace-specific work label or route. This is covered in `tests/test_steward_workspace_api.mjs`.
2. Preserved truthful package health: the extracted archive has no `.git`, so `/api/v1/health` returns `repository_present:false`. `scripts/deployment/verify_candidate_runtime.py` now accepts either Boolean repository state. It identifies a Git candidate by `git rev-parse`; for an extracted package it requires a valid `r3a.website-release-package.v1` manifest with a full 40-character source SHA. It fails closed if neither identity source exists. Permanent cases are in `tests/test_deployment_candidate_runtime.py`.

## Verification evidence

- Exact source focused regressions: **84 Python passed**, **31 Node passed**. The Python command included Website API, package integrity, AP3 access, Bitwarden integration, resident conversations, and candidate runtime verifier tests.
- The same **84 Python + 31 Node tests passed from the extracted exact package**.
- Exact archive package verifier: `verified:true`, 422 manifest entries, expected package SHA-256 matched.
- The candidate runtime verifier ran against the exact extracted archive in isolated staging with `repository_present:false`: `RUNTIME_VERIFICATION_PASS=TRUE`, health HTTP 200, homepage HTTP 200, manifest source commit exactly `6e5f3a6ceea723d0217367c57afd20d9b4c437bd`, candidate server stopped, activation `NOT_RUN`.
- A separate process launched from that exact extracted source returned `/api/v1/visual/background` HTTP 200, `image/png`, 3,605,170 bytes and the exact expected PNG SHA. `/api/v1/health` returned `running` and `repository_present:false`. `_base_snapshot()` image dimensions pass in the extracted Python suite. An unauthenticated HTTP `/api/v1/snapshot` request returned 503 because this isolated process had no shared AP3 session provider; authenticated snapshot/CME diagnostics acceptance is not claimed.
- `git diff --check`, Python compile checks, and JavaScript syntax checks passed before packaging.
- Broad source regression: **421 tests ran; 3 failures, 2 errors, 5 skipped**. Exact unrelated failures: `tests.test_r3a_institutional_directory.InstitutionalDirectoryProviderTests.test_dynamic_grace_tool_receives_directory_output_and_distinct_evidence` (missing CME resident execution adapter); `tests.test_r3a_institutional_knowledge.InstitutionalKnowledgeProviderTests.test_registered_operation_is_the_existing_grace_capability_and_carries_provenance` (same missing execution adapter); `tests.test_r3a_institutional_knowledge.InstitutionalKnowledgeProviderTests.test_denied_retrieval_never_loads_or_returns_source_content` (expected grant denial but same missing adapter occurs first); `tests.test_r3a_notification_service.NotificationServicePresentationTests.test_versioned_service_manifest_pins_runtime_artifacts_and_categories` (expected artifact SHA `107ea3…`, actual `41cd92…`, Notifications #48); and `tests.test_r3a_telemetry_inbox_demo.TelemetryInboxDemo.test_grace_discovers_authorized_plugin_and_invokes_from_queued_objective` (fixture has zero tools). These are not Website-owned fixes; do not report broad suite green.

## Review and release boundary

- Request independent exact-source/package re-audit on Issue #56 for source `6e5f3a6ceea723d0217367c57afd20d9b4c437bd` and package SHA `85322406cc44c1796af211176d7b6bd2d2abc17a92d3f511a1c85e534480914e`. Auditor must confirm the resident identity correction, extracted-package verifier behavior, archive manifest/digest, dependency lock, and exact focused/runtime evidence above.
- This remains a candidate pending that re-audit. No Coordinator release/rollback handoff is made until the exact re-audit returns PASS. No live deployment, shared service restart, authorization grant, identity binding or CME/Ring0 change was made.
- Remaining Website acceptance includes authenticated Steward browser interaction, real multi-resident and Grace persistence, authenticated snapshot/CME projection, notification/workstream/settings interfaces, and completion of the full Class I backlog documented in the acceptance matrix.
