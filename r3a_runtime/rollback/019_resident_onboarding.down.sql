-- R3 CONTROLLED SOURCE
-- File: r3a_runtime/rollback/019_resident_onboarding.down.sql
-- Component: R3A-RESIDENT-ONBOARDING
-- File Revision: 1.0.0
-- Created: 2026-11-10 UTC
-- Created By: Codex GPT-6
-- Purpose: Guarded rollback for migration 019 in an approved R3A maintenance window.
-- Execution Model: Transactional PostgreSQL rollback; refuses to discard packet or audit evidence.
-- Observability: Removes migration ledger row only after empty workflow tables are removed.
-- Dependencies: Coordinator backup/restore, approval, and database-role procedure.
-- Authority: R3A migration rollback procedure; never run against shared/production data without explicit authorization.
-- Changed: 2026-11-10 | R3A-UNIVERSAL-RESIDENT-ONBOARDING | Add data-preserving rollback guard.
-- Supersedes: None.
-- Contracts: r3a resident onboarding packet/event schema v1.
-- Tests: tests/test_r3a_resident_onboarding_postgres.py (disposable database only).
-- History/Predecessor: Migration 019 is additive; this file is deliberately outside migrations/*.sql.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM r3a.resident_onboarding_events)
       OR EXISTS (SELECT 1 FROM r3a.resident_onboarding_packets) THEN
        RAISE EXCEPTION 'migration 019 rollback refused while onboarding evidence exists'
            USING ERRCODE = '55000';
    END IF;

    DROP TRIGGER resident_onboarding_events_immutable
        ON r3a.resident_onboarding_events;
    DROP FUNCTION r3a.reject_resident_onboarding_event_mutation();
    DROP TABLE r3a.resident_onboarding_events;
    DROP TABLE r3a.resident_onboarding_packets;
    DELETE FROM r3a.schema_migrations WHERE version = '019_resident_onboarding.sql';
END;
$$;
