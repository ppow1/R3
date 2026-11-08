<!--
R3 CONTROLLED DOCUMENT
File: r3a_plugins/institutional_knowledge/manifest.provenance.md
Component: R3A-INSTITUTIONAL-KNOWLEDGE-MANIFEST-PROVENANCE
File Revision: 1.0.0
Created: 2026-11-07T22:04:07Z
Created By: Codex GPT-6
Purpose: Track provenance for the adjacent JSON capability manifest, whose format cannot carry comments.
Execution Model: N/A; metadata sidecar.
Observability: Git revision and manifest artifact/provider/operation versions.
Dependencies: r3a_plugins/institutional_knowledge/manifest.json; hints/file-provenance.md.
Authority: AP1-K2 / R3A-019; preserves the existing knowledge operation identity and CME authority path.
Changed: 2026-11-07T22:04:07Z | AP1-K2 | Codex GPT-6 | Record the compatible knowledge provider revision and manifest predecessor.
Supersedes: None.
Contracts: institution.knowledge.read@1.1.0; r3a.capability-operation.v1.
Tests: tests.test_r3a_institutional_knowledge; tests.test_r3a_capability_contracts; tests.test_r3a_ap1.
History/Predecessor: New sidecar; manifest predecessor blob c2a4d928bc1fb2ae14b0a9536faf388259476c75 at commit 4fe86ba4158e0f1f4b134114af276c942456c77c.
-->
# Institutional knowledge manifest provenance

`manifest.json` advances plugin, provider, and operation revision from 1.0.1
to 1.1.0. The change identifies improved Markdown source-path citations that
include heading context and source line ranges. Operation ID, configuration
schema, invocation input/output shape, required grant, and CME dispatch are
unchanged. The manifest's `artifact_sha256` continues to pin the provider
entrypoint `plugin.py`; the R3A implementation revision identifies the full
runtime source tree used by an activated service.
