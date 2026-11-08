-- R3 CONTROLLED SOURCE
-- File: r3a_runtime/migrations/009_resident_dossiers.sql
-- Component: R3A-RESIDENT-DOSSIERS
-- File Revision: 1.0.0
-- Created: 2026-11-08 UTC (exact creation time not captured)
-- Created By: Codex GPT-6
-- Purpose: Add immutable dossier revisions, current pointers, and append-only governance events.
-- Execution Model: Transactional PostgreSQL migration; R3A database only.
-- Observability: Revision and approval/rollback events persist with source/evidence references.
-- Dependencies: AP0 migration 001; PostgreSQL JSONB; future approved least-privilege role grants.
-- Authority: Steward Character Architecture directive; no production migration authorized.
-- Changed: 2026-11-08 UTC | CHARACTER-ARCHITECTURE | Codex GPT-6 | Add additive dossier persistence schema.
-- Supersedes: None
-- Contracts: r3a.resident.dossier.v1; r3a.resident.dossier-event.v1
-- Tests: SQL static review; live migration not run.
-- History/Predecessor: New file.

CREATE TABLE r3a.resident_dossier_revisions (
    resident_id text NOT NULL,
    dossier_revision text NOT NULL,
    schema_version integer NOT NULL CHECK (schema_version > 0),
    dossier jsonb NOT NULL,
    dossier_sha256 char(64) NOT NULL CHECK (dossier_sha256 ~ '^[a-f0-9]{64}$'),
    approval_status text NOT NULL CHECK (approval_status IN ('proposed','in_review','approved','superseded','rejected')),
    source_refs jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(source_refs) = 'array'),
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    supersedes_revision text,
    PRIMARY KEY (resident_id, dossier_revision),
    FOREIGN KEY (resident_id, supersedes_revision)
        REFERENCES r3a.resident_dossier_revisions(resident_id, dossier_revision)
        DEFERRABLE INITIALLY DEFERRED,
    CHECK (jsonb_typeof(dossier) = 'object')
);

CREATE TABLE r3a.resident_dossier_current (
    resident_id text PRIMARY KEY,
    dossier_revision text NOT NULL,
    changed_by text NOT NULL,
    changed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (resident_id, dossier_revision)
        REFERENCES r3a.resident_dossier_revisions(resident_id, dossier_revision)
);

CREATE TABLE r3a.resident_dossier_events (
    event_id uuid PRIMARY KEY,
    resident_id text NOT NULL,
    event_type text NOT NULL CHECK (event_type IN ('created','proposed','approved','rejected','superseded','rollback')),
    dossier_revision text NOT NULL,
    prior_revision text,
    actor_ref text NOT NULL,
    owner_domain text NOT NULL CHECK (owner_domain IN ('hr','character_architecture','engineering','steward')),
    occurred_at timestamptz NOT NULL,
    reason text NOT NULL,
    source_refs jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(source_refs) = 'array'),
    evidence jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(evidence) = 'object'),
    FOREIGN KEY (resident_id, dossier_revision)
        REFERENCES r3a.resident_dossier_revisions(resident_id, dossier_revision),
    FOREIGN KEY (resident_id, prior_revision)
        REFERENCES r3a.resident_dossier_revisions(resident_id, dossier_revision)
);

CREATE INDEX resident_dossier_event_subject_time_idx
    ON r3a.resident_dossier_events(resident_id, occurred_at DESC);

-- Role grants are intentionally deployment-owned. Runtime must not receive UPDATE/DELETE
-- on revision or event tables; a separate narrowly scoped transaction will move current pointers.
-- HR personnel-sensitive fields and protected character sources require a distinct store/access
-- projection and must not be bulk-copied into dossier JSON or prompts by this migration.
