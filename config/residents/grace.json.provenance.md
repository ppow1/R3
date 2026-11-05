<!--
R3 CONTROLLED DOCUMENT
File: config/residents/grace.json.provenance.md
Component: R3-GRACE-CONFIGURATION
File Revision: 1.0.0
Created: 2026-11-03T02:24:45.188Z
Created By: Codex
Purpose: Record provenance for Grace's resident runtime configuration.
Execution Model: Loaded by runtime.configuration at service startup.
Observability: Git revision and deployed release configuration.
Dependencies: runtime/configuration.py; config/residents/prompts/grace.md
Authority: R3 Steward-approved resident role and assignment continuity.
Changed: 2026-11-03T02:24:45.188Z | R3-VERIFY-FEEDBACK-LOOP-001 | Codex | Configure Grace to resume durable independent-review feedback.
Supersedes: None
Contracts: hints/file-provenance.md; hints/engineering-test-policy.md
Tests: tests/test_resident_continuity.py; tests/test_configuration.py
History/Predecessor: Git blob 1cbf46a21131b9563c3de24e5c4471cff341e727
-->
# Grace configuration provenance

The configuration enables `REVIEW_FEEDBACK` as a durable continuation event while preserving the existing R3-native read-only tool allowlist.
