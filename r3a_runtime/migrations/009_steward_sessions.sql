--
-- R3 CONTROLLED MIGRATION
-- File: r3a_runtime/migrations/009_steward_sessions.sql
-- Component: R3A-AP3-STEWARD-ACCESS
-- File Revision: 1.0.1
-- Created: 2026-11-07T21:37:42Z
-- Created By: Codex GPT-6
-- Purpose: Persist opaque Steward session digests and assertion replay identifiers.
-- Execution Model: Applied once by the existing ordered PostgreSQL migration runner.
-- Observability: Session rows are revocable; lifecycle and operation records use the append-only institutional event ledger.
-- Dependencies: AP0 r3a.institution_events; AP3-M1 Issue #49.
-- Authority: R3A AP3-M1, R3A-010/R3A-013; no roadmap exception.
-- Changed: 2026-11-07T21:37:42Z | AP3-M1 | Codex GPT-6 | Add durable opaque sessions and replay-safe ingress assertions.
-- Changed: 2026-11-07T21:44:36Z | AP3-M1 | Codex GPT-6 | Store authenticated-at time and factor references for future factor adapters.
-- Supersedes: None.
-- Contracts: r3a.steward-session.v1; r3a.steward-identity.v1.
-- Tests: tests/test_r3a_steward_access.py.
-- History/Predecessor: New migration; initial publication recorded in Git.
--

CREATE TABLE r3a.steward_sessions (
    token_digest char(64) PRIMARY KEY CHECK (token_digest ~ '^[a-f0-9]{64}$'),
    principal_id text NOT NULL,
    issuer text NOT NULL,
    assertion_id text NOT NULL UNIQUE,
    authenticated_at timestamptz NOT NULL,
    factor_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    issued_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    correlation_id uuid NOT NULL,
    CHECK (expires_at > issued_at)
);
CREATE INDEX steward_sessions_active_idx
    ON r3a.steward_sessions(principal_id, expires_at)
    WHERE revoked_at IS NULL;
