-- R3 CONTROLLED SOURCE
-- File: r3a_runtime/migrations/019_resident_onboarding.sql
-- Component: R3A-RESIDENT-ONBOARDING
-- File Revision: 1.0.0
-- Created: 2026-11-10 UTC
-- Created By: Codex GPT-6
-- Purpose: Persist resumable onboarding packet projections and immutable transition audit events.
-- Execution Model: Additive R3A PostgreSQL migration; no HR or Riverview directory authority writes.
-- Observability: Packet revisions, idempotency keys, transition actors, approvals, and evidence refs.
-- Dependencies: R3A schema_migrations; resident-onboarding-packet.v1 and resident.onboarding v1.
-- Authority: Steward directive in R3 Issue #58; production application requires Coordinator migration/deploy approval.
-- Changed: 2026-11-10 | R3A-UNIVERSAL-RESIDENT-ONBOARDING | Create separate packet and append-only event tables.
-- Supersedes: None.
-- Contracts: r3a.resident.onboarding-packet.v1; resident.onboarding v1.
-- Tests: tests/test_r3a_resident_onboarding.py; isolated database integration required before deployment.
-- History/Predecessor: New additive migration. It stores evidence references, not source personnel/credential contents.

CREATE TABLE r3a.resident_onboarding_packets (
    packet_id uuid PRIMARY KEY,
    resident_id text,
    lifecycle_state text NOT NULL CHECK (lifecycle_state IN
        ('REQUESTED','IDENTITY_PENDING','APPOINTMENT_PENDING','AUTHORIZATION_PENDING',
         'RUNTIME_PENDING','VALIDATION_PENDING','ACTIVE','BLOCKED','SUSPENDED','REVOKED','OFFBOARDED')),
    packet_revision integer NOT NULL CHECK (packet_revision > 0),
    create_idempotency_key text NOT NULL UNIQUE,
    packet jsonb NOT NULL CHECK (jsonb_typeof(packet) = 'object'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (resident_id IS NULL OR resident_id ~ '^r3:[a-z0-9_.:-]+$'),
    CHECK ((packet->>'packet_id')::uuid = packet_id),
    CHECK ((packet->>'packet_revision')::integer = packet_revision),
    CHECK (packet->>'state' = lifecycle_state)
);

CREATE UNIQUE INDEX resident_onboarding_one_open_packet_per_resident_idx
    ON r3a.resident_onboarding_packets(resident_id)
    WHERE resident_id IS NOT NULL AND lifecycle_state NOT IN ('REVOKED','OFFBOARDED');

CREATE TABLE r3a.resident_onboarding_events (
    event_id uuid PRIMARY KEY,
    packet_id uuid NOT NULL REFERENCES r3a.resident_onboarding_packets(packet_id),
    idempotency_key text NOT NULL,
    correlation_id uuid NOT NULL,
    actor_ref text NOT NULL,
    actor_role text NOT NULL CHECK (actor_role IN
        ('HR','Character Architecture','Security','Coordinator','Website','Independent Auditor','Steward')),
    action text NOT NULL,
    prior_state text,
    next_state text NOT NULL,
    expected_revision integer NOT NULL CHECK (expected_revision >= 0),
    occurred_at timestamptz NOT NULL,
    reason_ref text NOT NULL,
    approval_ref text,
    evidence_refs jsonb NOT NULL CHECK (jsonb_typeof(evidence_refs) = 'array'),
    event jsonb NOT NULL CHECK (jsonb_typeof(event) = 'object'),
    packet_snapshot jsonb NOT NULL CHECK (jsonb_typeof(packet_snapshot) = 'object'),
    UNIQUE (packet_id, idempotency_key)
);

CREATE INDEX resident_onboarding_events_packet_time_idx
    ON r3a.resident_onboarding_events(packet_id, occurred_at DESC);

CREATE FUNCTION r3a.reject_resident_onboarding_event_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'resident onboarding audit events are append-only';
END;
$$;

CREATE TRIGGER resident_onboarding_events_immutable
    BEFORE UPDATE OR DELETE ON r3a.resident_onboarding_events
    FOR EACH ROW EXECUTE FUNCTION r3a.reject_resident_onboarding_event_mutation();

-- Runtime role grants are deployment-owned. Do not grant this workflow permission to write HR,
-- resident_occupants, office_bindings, credentials, or capability grant authority tables.
