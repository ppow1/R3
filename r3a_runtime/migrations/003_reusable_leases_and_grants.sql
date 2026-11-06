-- R3 CONTROLLED SOURCE
-- File: r3a_runtime/migrations/003_reusable_leases_and_grants.sql
-- Component: R3A-AP0-LEASE-CONSTRAINTS
-- File Revision: 1.0.0
-- Created: 2026-11-06T15:42:30Z
-- Created By: Codex GPT-6
-- Purpose: Preserve released lease history while permitting safe retries and prevent duplicate active grants.
-- Execution Model: Transactional PostgreSQL migration applied by CME.
-- Observability: Active-lease and active-grant uniqueness enforced by partial indexes.
-- Dependencies: PostgreSQL; resource_leases and capability_grants from migration 001.
-- Authority: AP0-M1 implementation authorized by Steward in GitHub Issue #42; isolated R3A only.
-- Changed: 2026-11-06T15:42:30Z | R3A-AP0-M1 | Codex GPT-6 | Add retry-safe active resource/grant constraints.
-- Supersedes: None.
-- Contracts: AP0-005/006/008; AP0-M1 D3/D4/D6.
-- Tests: Isolated claim/recovery retry and grant idempotency operations.
-- History/Predecessor: New file; initial publication recorded in Git.
ALTER TABLE r3a.resource_leases
    DROP CONSTRAINT IF EXISTS resource_leases_activity_id_resource_id_key;
CREATE UNIQUE INDEX IF NOT EXISTS resource_leases_one_active_idx
    ON r3a.resource_leases(activity_id, resource_id) WHERE released_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS capability_grants_one_active_idx
    ON r3a.capability_grants(module_id, capability_id) WHERE revoked_at IS NULL;
