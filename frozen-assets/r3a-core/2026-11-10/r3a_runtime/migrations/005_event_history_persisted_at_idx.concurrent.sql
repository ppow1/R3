-- R3 CONTROLLED SOURCE
-- File: r3a_runtime/migrations/005_event_history_persisted_at_idx.concurrent.sql
-- Component: R3A-POSTGRES-EVENT-HISTORY-INDEX
-- File Revision: 1.0.0
-- Created: 2026-11-07T04:36:29Z
-- Created By: Codex GPT-6
-- Purpose: Support bounded newest-event diagnostics without scanning and sorting the append-only event history.
-- Execution Model: Autocommit PostgreSQL CREATE INDEX CONCURRENTLY; migration ledger entry commits after index validity is verified.
-- Observability: r3a.schema_migrations and pg_index.indisvalid.
-- Dependencies: PostgreSQL; r3a.institution_events.persisted_at.
-- Authority: Steward Directive — R3A SQL Diagnostics Optimization, Issue #43; isolated R3A only.
-- Changed: 2026-11-07T04:36:29Z | R3A-AP1-M1-DIAGNOSTICS | Codex GPT-6 | Add an online index for newest-first bounded event queries.
-- Supersedes: None.
-- Contracts: AP0-003 durable event history; AP0-010 truthful diagnostics.
-- Tests: Applied to isolated R3A using PostgreSQL concurrent index build; query plan and live CLI verified.
-- History/Predecessor: New migration; source revision recorded in Git.

CREATE INDEX CONCURRENTLY institution_events_persisted_at_idx
    ON r3a.institution_events (persisted_at DESC);
