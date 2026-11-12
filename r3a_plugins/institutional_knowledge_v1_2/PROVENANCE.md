<!--
R3 CONTROLLED DOCUMENT
File: r3a_plugins/institutional_knowledge/manifest.provenance.md
Component: R3A-INSTITUTIONAL-KNOWLEDGE-MANIFEST-PROVENANCE
File Revision: 1.1.0
Created: 2026-11-07T22:04:07Z
Created By: Codex GPT-6
Purpose: Track provenance for the versioned Knowledge provider and operation manifests, whose JSON format cannot carry comments.
Execution Model: N/A; metadata sidecar.
Observability: Git revision, manifest artifact/provider/operation versions, and supporting artifact digest.
Dependencies: adjacent operation manifests; hints/file-provenance.md.
Authority: Steward governed ingestion directive for Issues #43/#46/#47/#51.
Changed: 2026-11-08 | AP1-K1 | Codex GPT-6 | Add list/decision manifests, pin review_store.py, and preserve the existing Grace read operation.
Supersedes: 1.0.0.
Contracts: institution.knowledge.read@1.1.0; Knowledge proposal operations; capability-operation/invocation v1.1.0 Steward effects.
Tests: tests/test_governed_knowledge_contracts.py; tests/test_r3a_institutional_knowledge.py; scripts/knowledge_ingestion_acceptance.py.
History/Predecessor: New sidecar; manifest predecessor blob c2a4d928bc1fb2ae14b0a9536faf388259476c75 at commit 4fe86ba4158e0f1f4b134114af276c942456c77c.
-->
# Institutional knowledge manifest provenance

`manifest.json` remains the compatibility alias for the read operation. The
three versioned operation manifests share provider `r3a.institutional-knowledge`
at 1.2.0 and pin both `plugin.py` and `review_store.py`. The established Grace
read operation remains contract 1.0.0, operation revision 1.1.0, and its
existing resident grant. The two new Steward review operations use generic
capability contract 1.1.0. Their manifests declare the exact allowed Steward
principal and external database environment-variable name. Module registration
does not create authorization grants.
