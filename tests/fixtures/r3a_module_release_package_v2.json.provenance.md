<!--
R3 CONTROLLED DOCUMENT
File: tests/fixtures/r3a_module_release_package_v2.json.provenance.md
Component: FIXTURE-R3A-MODULE-RELEASE-V2
File Revision: 1.0.0
Created: 2026-11-11T19:00:20Z
Created By: Codex GPT-6
Purpose: Publish a shared release descriptor fixture for Autonomy CME package/launcher integration.
Execution Model: N/A; interoperability fixture sidecar.
Observability: Exact package descriptor and runtime artifact digest are asserted by permanent tests.
Dependencies: module-release-package.v2.schema.json; matching manifest and worker fixtures.
Authority: AD-024; Step 70/84; no live module, identity, grant or deployment.
Changed: 2026-11-11T19:00:20Z | R3A-MODULAR-PLUGINS-STEP-70 | Codex GPT-6 | Publish generic executor release descriptor fixture.
Supersedes: None.
Contracts: r3a.module-release-package.v2@2.0.0; r3a.module-process-binding.v1@1.0.0.
Tests: tests/test_r3a_module_release_v2.py.
History/Predecessor: New shared contract fixture.
-->
# Module package v2 fixture provenance

The fixture uses the synthetic module `executor.orbit` and can be consumed by CME implementation tests without introducing a Grace-specific contract.
