<!--
R3 CONTROLLED DOCUMENT
File: r3a_modules/resident_grace/package_spec.json.provenance.md
Component: R3A-RESIDENT-GRACE-PACKAGE-SOURCE-SPEC
File Revision: 1.0.0
Created: 2026-11-11T18:20:00Z
Created By: Codex GPT-6
Purpose: Pin the source import closure and process profile used to build the immutable Grace worker package candidate
Execution Model: Source-pin input to scripts/build_grace_module_package.py and shared scripts/r3a_module_release_package.py; no runtime registration or activation
Observability: Exact source commit and SHA-256 for each packaged source file
Dependencies: Audited source candidate 29353c978ed9ea0e9991a264bc222a61fdca2f1c; AP0-M1; Step 78
Authority: Issue #61 comment 6804259280; package candidate only
Changed: 2026-11-11T18:20:00Z | R3A-MODULE-PACKAGE-V2 | Codex GPT-6 | Pin audited resident worker source closure
Supersedes: None
Contracts: r3a.module-release-package.v2@2.0.0; r3a.module-process-binding.v1@1.0.0; r3a.resident.executor@1.0.0
Tests: tests/test_r3a_generic_module_package.py
History/Predecessor: New source specification
-->
# Resident package source specification provenance

This source specification carries the package-time file inventory and process binding for candidate `resident.grace@1.2.15`. The packaged code is from the audited source commit in `source.revision`; the package version is a staging candidate and is not a statement about managed configuration or active version. Audited external requirements are Python >=3.12 and `psycopg[binary,pool] >=3.2,<4`. The shared release descriptor currently has no source-revision or external-runtime-dependency field; this candidate must not be considered dependency-complete until #46 resolves that contract gap. No credential, live binding, grant, or runtime configuration is included.
