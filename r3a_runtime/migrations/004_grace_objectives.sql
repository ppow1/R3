-- R3 CONTROLLED SOURCE
-- File: r3a_runtime/migrations/004_grace_objectives.sql
-- Component: R3A-AP1-GRACE-OBJECTIVES
-- File Revision: 1.0.0
-- Created: 2026-11-06 UTC
-- Created By: Codex GPT-6
-- Purpose: Persist Grace objective inputs and independently verifiable results on AP0 activity lineage.
-- Execution Model: Transactional PostgreSQL migration applied by CME.
-- Observability: Objective input, request/result digests, and activity references remain durable.
-- Dependencies: AP0 r3a.activities and append-only r3a.institution_events.
-- Authority: AP1-M1 authorized by Steward in GitHub Issue #43; isolated R3A only.
-- Changed: 2026-11-06 | AP1-M1 | Codex GPT-6 | Add durable Grace objective payload and result.
-- Supersedes: None.
-- Contracts: R3A-019; AP1-M1 Issue #43 acceptance.
-- Tests: Migration restart and live objective/recovery evidence.
-- History/Predecessor: New AP1-M1 migration.
ALTER TABLE r3a.activities
    ADD COLUMN input jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN result jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX activities_grace_due_idx
    ON r3a.activities(available_at, created_at)
    WHERE activity_type = 'grace.objective';
