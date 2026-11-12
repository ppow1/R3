-- R3 CONTROLLED SOURCE
-- File: r3a_runtime/migrations/008_activity_scoped_capability_grants.sql
-- Component: R3A-POSTGRES-AUTHORIZATION
-- File Revision: 1.0.0
-- Created: 2026-11-07 UTC
-- Created By: Codex GPT-6
-- Purpose: Add optional activity scope to the existing capability-grant mechanism.
-- Execution Model: Additive PostgreSQL migration under the existing schema migration lock.
-- Observability: Grant scope remains visible in the grant row and capability grant/revoke events.
-- Dependencies: r3a.capability_grants; canonical CME authorization provider.
-- Authority: R3 Alpha autonomy Task B, GitHub Issues #43 and #46.
-- Changed: 2026-11-07 | AP2-ESCALATED-REASONING | Codex GPT-6 | Support bounded activity-scoped grants.
-- Supersedes: None.
-- Contracts: r3a.authorization-provider.v1; r3a.activity-budget-reservation.v1.
-- Tests: scoped grant authorization and isolated PostgreSQL reservation tests.
-- History/Predecessor: New file; initial revision recorded in Git.

ALTER TABLE r3a.capability_grants
    ADD COLUMN IF NOT EXISTS scope jsonb NOT NULL DEFAULT '{}'::jsonb;

DROP INDEX IF EXISTS r3a.capability_grants_one_active_idx;
CREATE UNIQUE INDEX IF NOT EXISTS capability_grants_one_active_scope_idx
    ON r3a.capability_grants(module_id, capability_id, scope)
    WHERE revoked_at IS NULL;

CREATE INDEX IF NOT EXISTS capability_grants_activity_scope_idx
    ON r3a.capability_grants(module_id, capability_id, (scope->>'activity_id'))
    WHERE revoked_at IS NULL;
