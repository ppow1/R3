-- R3 CONTROLLED SOURCE
-- File: r3a_runtime/migrations/002_event_ledger_append_only.sql
-- Component: R3A-AP0-EVENT-LEDGER
-- File Revision: 1.0.0
-- Created: 2026-11-06T15:42:10Z
-- Created By: Codex GPT-6
-- Purpose: Reject ordinary update/delete operations against the durable AP0 event ledger.
-- Execution Model: Transactional PostgreSQL migration applied by CME.
-- Observability: Mutation attempts fail with an explicit database error.
-- Dependencies: PostgreSQL; r3a.institution_events from migration 001.
-- Authority: AP0-M1 implementation authorized by Steward in GitHub Issue #42; isolated R3A only.
-- Changed: 2026-11-06T15:42:10Z | R3A-AP0-M1 | Codex GPT-6 | Enforce append-only event operations.
-- Supersedes: None.
-- Contracts: AP0-004/005; AP0-M1 D2/D4; STM-003/007.
-- Tests: Migration restart and explicit update/delete rejection against isolated AP0 database.
-- History/Predecessor: New file; initial publication recorded in Git.
CREATE FUNCTION r3a.reject_institution_event_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'r3a.institution_events is append-only';
END;
$$;

CREATE TRIGGER institution_events_append_only
BEFORE UPDATE OR DELETE ON r3a.institution_events
FOR EACH ROW EXECUTE FUNCTION r3a.reject_institution_event_mutation();
