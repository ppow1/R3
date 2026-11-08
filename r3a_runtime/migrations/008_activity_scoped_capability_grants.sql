-- R3 CONTROLLED SOURCE
-- File: r3a_runtime/migrations/008_activity_scoped_capability_grants.sql
-- Component: R3A-POSTGRES-AUTHORIZATION
-- File Revision: 1.0.0
-- Created: 2026-11-07 UTC
-- Created By: Codex GPT-6
-- Purpose: Add optional durable-activity scope to the existing generic capability-grant mechanism.
-- Execution Model: Additive PostgreSQL migration under the existing schema migration lock.
-- Observability: Grant scope remains visible in the grant row and grant/revoke events.
-- Dependencies: r3a.capability_grants; canonical CME authorization provider.
-- Authority: R3A AP2 implementation; managed-integration reconciliation for Issues #43 and #46.
-- Changed: 2026-11-08 | R3A-ENG-MANAGED-INTEGRATION | Codex GPT-6 | Port the existing shared activity-scoped grant contract.
-- Supersedes: None.
-- Contracts: r3a.authorization-provider.v1.
-- Tests: tests/test_r3a_modular_autonomy.py; isolated live Engineering acceptance.
-- History/Predecessor: Port of the existing Coordinator authorization migration.

ALTER TABLE r3a.capability_grants
    ADD COLUMN IF NOT EXISTS scope jsonb NOT NULL DEFAULT '{}'::jsonb;

DROP INDEX IF EXISTS r3a.capability_grants_one_active_idx;
CREATE UNIQUE INDEX IF NOT EXISTS capability_grants_one_active_scope_idx
    ON r3a.capability_grants(module_id, capability_id, scope)
    WHERE revoked_at IS NULL;

CREATE INDEX IF NOT EXISTS capability_grants_activity_scope_idx
    ON r3a.capability_grants(module_id, capability_id, (scope->>'activity_id'))
    WHERE revoked_at IS NULL;
