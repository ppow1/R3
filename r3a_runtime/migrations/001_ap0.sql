-- R3 CONTROLLED SOURCE
-- File: r3a_runtime/migrations/001_ap0.sql
-- Component: R3A-AP0-DATABASE
-- File Revision: 1.0.0
-- Created: 2026-11-06T15:04:00Z
-- Created By: Codex GPT-6
-- Purpose: Create the isolated AP0 state, event, registry, configuration, and activity schema.
-- Execution Model: Transactional PostgreSQL migration applied by CME.
-- Observability: schema_migrations ledger and durable event table.
-- Dependencies: PostgreSQL; AP0-004/005/008/009.
-- Authority: Steward authorized AP0-M1 in GitHub Issue #42; R3A database only.
-- Changed: 2026-11-06T15:04:00Z | R3A-AP0-M1 | Codex GPT-6 | Create initial AP0 schema.
-- Supersedes: None.
-- Contracts: AP0-M1 D2/D4/D6/D7; STM-001–STM-007.
-- Tests: Targeted disposable PostgreSQL migration/recovery checks.
-- History/Predecessor: New file; initial publication recorded in Git.
CREATE SCHEMA IF NOT EXISTS r3a AUTHORIZATION r3a_runtime;
CREATE TABLE IF NOT EXISTS r3a.schema_migrations (
    version text PRIMARY KEY,
    checksum char(64) NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE r3a.config_revisions (
    revision_id char(64) PRIMARY KEY,
    schema_version integer NOT NULL,
    config jsonb NOT NULL,
    source_path text NOT NULL,
    source_digest char(64) NOT NULL,
    activated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    actor text NOT NULL
);
CREATE TABLE r3a.config_current (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    revision_id char(64) NOT NULL REFERENCES r3a.config_revisions(revision_id),
    changed_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE r3a.state_machine_definitions (
    machine_id text NOT NULL,
    machine_version integer NOT NULL,
    definition jsonb NOT NULL,
    digest char(64) NOT NULL,
    installed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (machine_id, machine_version),
    UNIQUE (machine_id, digest)
);
CREATE TABLE r3a.runtime_entities (
    entity_type text NOT NULL,
    entity_id text NOT NULL,
    machine_id text NOT NULL,
    machine_version integer NOT NULL,
    state text NOT NULL,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    config_revision char(64) REFERENCES r3a.config_revisions(revision_id),
    version bigint NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (entity_type, entity_id),
    FOREIGN KEY (machine_id, machine_version)
        REFERENCES r3a.state_machine_definitions(machine_id, machine_version)
);
CREATE TABLE r3a.institution_events (
    event_id uuid PRIMARY KEY,
    event_type text NOT NULL,
    schema_version integer NOT NULL,
    subject_type text NOT NULL,
    subject_id text NOT NULL,
    machine_id text,
    machine_version integer,
    prior_state text,
    next_state text,
    occurred_at timestamptz NOT NULL,
    persisted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    actor text NOT NULL,
    correlation_id uuid NOT NULL,
    causation_id uuid,
    reason text NOT NULL,
    outcome text NOT NULL,
    config_revision char(64) REFERENCES r3a.config_revisions(revision_id),
    implementation_revision text NOT NULL,
    evidence jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX institution_events_subject_time_idx
    ON r3a.institution_events(subject_type, subject_id, occurred_at DESC);

CREATE TABLE r3a.process_observations (
    component_id text PRIMARY KEY,
    pid integer NOT NULL,
    state text NOT NULL,
    health text NOT NULL,
    heartbeat_at timestamptz NOT NULL,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    config_revision char(64) REFERENCES r3a.config_revisions(revision_id),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE r3a.activities (
    activity_id uuid PRIMARY KEY,
    activity_type text NOT NULL,
    idempotency_key text NOT NULL UNIQUE,
    machine_id text NOT NULL,
    machine_version integer NOT NULL,
    state text NOT NULL,
    available_at timestamptz NOT NULL,
    attempt_id uuid,
    attempt_count integer NOT NULL DEFAULT 0,
    lease_owner text,
    lease_until timestamptz,
    progress jsonb NOT NULL DEFAULT '{}'::jsonb,
    checkpoint jsonb NOT NULL DEFAULT '{}'::jsonb,
    recovery_policy text NOT NULL,
    config_revision char(64) REFERENCES r3a.config_revisions(revision_id),
    latest_event_id uuid,
    exception jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (machine_id, machine_version)
        REFERENCES r3a.state_machine_definitions(machine_id, machine_version)
);
CREATE INDEX activities_due_idx ON r3a.activities(state, available_at, created_at);
CREATE INDEX activities_lease_idx ON r3a.activities(lease_until) WHERE state = 'RUNNING';

CREATE TABLE r3a.module_registry (
    module_id text NOT NULL,
    module_version text NOT NULL,
    contract_id text NOT NULL,
    protocol_major integer NOT NULL,
    protocol_minor integer NOT NULL,
    artifact_ref text NOT NULL,
    artifact_digest char(64) NOT NULL,
    manifest jsonb NOT NULL,
    lifecycle_state text NOT NULL,
    health text NOT NULL,
    observed_at timestamptz,
    diagnostic jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (module_id, module_version)
);
CREATE TABLE r3a.capability_registry (
    capability_id text PRIMARY KEY,
    contract_version text NOT NULL,
    owner text NOT NULL,
    access_mode text NOT NULL CHECK (access_mode IN ('read_only', 'read_write')),
    health text NOT NULL,
    observed_at timestamptz NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE r3a.resource_registry (
    resource_id text PRIMARY KEY,
    contract_version text NOT NULL,
    owner text NOT NULL,
    capacity integer NOT NULL CHECK (capacity > 0),
    allocated integer NOT NULL DEFAULT 0 CHECK (allocated >= 0),
    health text NOT NULL,
    observed_at timestamptz NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (allocated <= capacity)
);
CREATE TABLE r3a.resource_leases (
    lease_id uuid PRIMARY KEY,
    resource_id text NOT NULL REFERENCES r3a.resource_registry(resource_id),
    activity_id uuid NOT NULL REFERENCES r3a.activities(activity_id),
    units integer NOT NULL CHECK (units > 0),
    lease_until timestamptz NOT NULL,
    released_at timestamptz
);
CREATE UNIQUE INDEX resource_leases_one_active_idx
    ON r3a.resource_leases(activity_id, resource_id) WHERE released_at IS NULL;
CREATE TABLE r3a.capability_grants (
    grant_id uuid PRIMARY KEY,
    module_id text NOT NULL,
    capability_id text NOT NULL REFERENCES r3a.capability_registry(capability_id),
    granted_by text NOT NULL,
    reason text NOT NULL,
    granted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    revoked_at timestamptz,
    UNIQUE (module_id, capability_id, granted_at)
);
CREATE INDEX capability_grants_active_idx
    ON r3a.capability_grants(module_id, capability_id) WHERE revoked_at IS NULL;
CREATE UNIQUE INDEX capability_grants_one_active_idx
    ON r3a.capability_grants(module_id, capability_id) WHERE revoked_at IS NULL;

CREATE TABLE r3a.diagnostic_observations (
    observation_id uuid PRIMARY KEY,
    observed_at timestamptz NOT NULL,
    source_id text NOT NULL,
    health text NOT NULL,
    freshness text NOT NULL,
    details jsonb NOT NULL,
    config_revision char(64) REFERENCES r3a.config_revisions(revision_id),
    evidence_event_id uuid REFERENCES r3a.institution_events(event_id)
);
