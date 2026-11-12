-- R3 CONTROLLED SOURCE
-- File: r3a_runtime/migrations/006_activity_created_at_idx.concurrent.sql
-- Component: R3A-POSTGRES-ACTIVITY-DIAGNOSTICS-INDEX
-- File Revision: 1.0.0
-- Created: 2026-11-07T04:41:59Z
-- Created By: Codex GPT-6
-- Purpose: Support bounded newest-activity diagnostics without sorting the complete current-state relation.
-- Execution Model: Autocommit PostgreSQL CREATE INDEX CONCURRENTLY; migration ledger entry commits after index validity is verified.
-- Observability: r3a.schema_migrations and pg_index.indisvalid.
-- Dependencies: PostgreSQL; r3a.activities.created_at.
-- Authority: Steward Directive — R3A SQL Diagnostics Optimization, Issue #43; isolated R3A only.
-- Changed: 2026-11-07T04:41:59Z | R3A-AP1-M1-DIAGNOSTICS | Codex GPT-6 | Add an online index for newest-first bounded activity queries.
-- Supersedes: None.
-- Contracts: AP0-003 durable activity state; AP0-010 truthful diagnostics.
-- Tests: Applied to isolated R3A using PostgreSQL concurrent index build; query plan and live CLI verified.
-- History/Predecessor: New migration; source revision recorded in Git.

CREATE INDEX CONCURRENTLY activities_created_at_idx
    ON r3a.activities (created_at DESC);
