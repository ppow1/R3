-- R3 CONTROLLED SOURCE
-- File: r3a_runtime/migrations/016_character_revision_retirement.sql
-- Component: R3A-RESIDENT-DOSSIERS
-- File Revision: 1.0.0
-- Created: 2026-11-08 UTC
-- Purpose: Add governed retirement/deactivation of an active character revision.
-- Execution Model: Additive PostgreSQL migration; existing revision/event history is retained.
-- Observability: Append-only retired event and reversible current-pointer removal.
-- Dependencies: Migration 009 resident dossier revisions/events.
-- Authority: Character Architecture approved lifecycle; production use remains integration-owner governed.
-- Changed: None
-- Supersedes: None
-- Contracts: resident dossier lifecycle @1.1
-- Tests: tests.test_r3a_postgres_character_workflow
-- History/Predecessor: New migration.

ALTER TABLE r3a.resident_dossier_revisions
    DROP CONSTRAINT resident_dossier_revisions_approval_status_check;
ALTER TABLE r3a.resident_dossier_revisions
    ADD CONSTRAINT resident_dossier_revisions_approval_status_check
    CHECK (approval_status IN ('proposed','in_review','approved','published','active','superseded','rejected','retired'));

ALTER TABLE r3a.resident_dossier_events
    DROP CONSTRAINT resident_dossier_events_event_type_check;
ALTER TABLE r3a.resident_dossier_events
    ADD CONSTRAINT resident_dossier_events_event_type_check
    CHECK (event_type IN ('created','proposed','submitted_for_review','approved','rejected','published','activated','superseded','rollback','retired'));
