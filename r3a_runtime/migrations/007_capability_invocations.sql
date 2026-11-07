-- R3 CONTROLLED SOURCE
-- File: r3a_runtime/migrations/007_capability_invocations.sql
-- Component: R3A-POSTGRES-CAPABILITY-INVOCATIONS
-- File Revision: 1.0.1
-- Created: 2026-11-07T06:45:06Z
-- Created By: Codex GPT-6
-- Purpose: Persist canonical invocation idempotency, authorization provenance, and results.
-- Execution Model: Transactional PostgreSQL migration under the existing schema migration advisory lock.
-- Observability: Invocation state is queryable by idempotency key and invocation ID; state events remain append-only.
-- Dependencies: r3a_runtime/db.py; r3a.capability-invocation.v1.
-- Authority: R3A AP2 isolated capability integration; Issues #43 and #46; no shared runtime activation.
-- Changed: 2026-11-07T13:20:00Z | R3A-AP2-CAPABILITY-INTEGRATION | Codex GPT-6 | Name authorization_evidence explicitly to avoid PostgreSQL's reserved AUTHORIZATION keyword.
-- Supersedes: Initial local draft from integration commit 742679c22ed2d0e341c1acb1233a67fa73979ff3.
-- Contracts: r3a.capability-invocation.v1.
-- Tests: Live isolated PostgreSQL migration and invocation recovery; tests/test_r3a_capability_integration_demo.py.
-- History/Predecessor: Migration introduced in commit 742679c22ed2d0e341c1acb1233a67fa73979ff3.
--
-- Durable idempotency and audit result for canonical unified capability dispatch.
CREATE TABLE IF NOT EXISTS r3a.capability_invocations (
    idempotency_key text PRIMARY KEY,
    invocation_id text NOT NULL,
    operation_id text NOT NULL,
    request_digest text NOT NULL,
    state text NOT NULL CHECK (state IN ('STARTED','SUCCEEDED','FAILED','DENIED','DEFERRED','UNKNOWN')),
    request jsonb NOT NULL,
    authorization_evidence jsonb NOT NULL,
    result jsonb,
    evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS capability_invocations_invocation_id_idx
    ON r3a.capability_invocations(invocation_id);
