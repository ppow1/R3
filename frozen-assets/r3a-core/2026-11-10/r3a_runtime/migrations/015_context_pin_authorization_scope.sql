-- R3 CONTROLLED SOURCE
-- File: r3a_runtime/migrations/015_context_pin_authorization_scope.sql
-- Component: R3A-RESIDENT-CONTEXT-MIGRATION
-- File Revision: 1.0.0
-- Created: 2026-11-08 UTC
-- Created By: Codex GPT-6
-- Purpose: Persist classification authorization scope for immutable context pins.
-- Execution Model: Additive PostgreSQL migration through r3a_runtime.db.Store.migrate().
-- Observability: Schema version/checksum and migration history.
-- Dependencies: Migrations 009–012; PostgreSQL arrays and CHECK constraints.
-- Authority: Steward-approved Character Architecture; no managed database mutation here.
-- Changed: 2026-11-08 UTC | CA-03 | Codex GPT-6 | Add immutable boundary classification scope.
-- Supersedes: None
-- Contracts: r3a.resident.approved-character-context@2.0.0
-- Tests: Fresh and idempotent isolated PostgreSQL migration; PostgreSQL workflow regression.
-- History/Predecessor: New file.
--
-- Preserve the exact classification grant used when a conversation/activity context
-- is first pinned. A later grant change must not widen or silently change that context.
-- Legacy pins remain NULL and are rejected by the v2 provider until a new boundary.

ALTER TABLE r3a.resident_character_context_pins
    ADD COLUMN authorized_classifications text[];

ALTER TABLE r3a.resident_character_context_pins
    ADD CONSTRAINT resident_context_pin_classification_scope_check
        CHECK (authorized_classifications IS NULL OR
               (cardinality(authorized_classifications) > 0 AND
                authorized_classifications <@ ARRAY['public','institutional']::text[]));
