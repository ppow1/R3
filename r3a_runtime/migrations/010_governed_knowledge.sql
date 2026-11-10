-- R3 CONTROLLED SOURCE
-- File: r3a_runtime/migrations/010_governed_knowledge.sql
-- Component: R3A-GOVERNED-KNOWLEDGE
-- File Revision: 1.0.1
-- Created: 2026-11-08 UTC
-- Created By: Codex GPT-6
-- Purpose: Persist source-grounded proposals, individual Steward decisions, and approved knowledge in the existing institutional store.
-- Execution Model: Transactional PostgreSQL migration under the existing schema migration lock.
-- Observability: Durable per-item review, provenance, and supersession records plus existing institution event ledger.
-- Dependencies: PostgreSQL; r3a.capability-invocation.v1; institutional knowledge provider.
-- Authority: R3A Knowledge governed ingestion directive, GitHub Issue #47; capability effects coordinated via #43/#46.
-- Changed: 2026-11-08 | AP1-K2 | Correct migration filename provenance; schema unchanged.
-- Supersedes: None.
-- Contracts: r3a.knowledge-review-api.v1@1.0.0; r3a.capability-operation.v1@1.1.0.
-- Tests: tests/test_governed_knowledge.py and isolated PostgreSQL acceptance.
-- History/Predecessor: Original migration at 8944f4f0a20f966256813bd1c126ead57174ded4, Git blob 0328893928d9014f978988b9c852ea009c5b4b8e.

ALTER TABLE r3a.capability_registry DROP CONSTRAINT IF EXISTS capability_registry_access_mode_check;
ALTER TABLE r3a.capability_registry ADD CONSTRAINT capability_registry_access_mode_check
    CHECK (access_mode IN ('read_only', 'read_write', 'steward_read', 'steward_write'));

CREATE TABLE IF NOT EXISTS r3a.knowledge_proposals (
    proposal_id text PRIMARY KEY,
    batch_id text NOT NULL,
    proposal_revision integer NOT NULL CHECK (proposal_revision > 0),
    source_digest char(64) NOT NULL,
    content jsonb NOT NULL,
    state text NOT NULL DEFAULT 'pending' CHECK (state IN ('pending','approved','rejected','deferred')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS r3a.knowledge_review_batches (
    batch_id text PRIMARY KEY,
    source_digest char(64) NOT NULL,
    content jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS knowledge_proposals_batch_state_idx
    ON r3a.knowledge_proposals(batch_id,state,proposal_id);

CREATE TABLE IF NOT EXISTS r3a.knowledge_review_decisions (
    decision_id bigserial PRIMARY KEY,
    idempotency_key text NOT NULL UNIQUE,
    proposal_id text NOT NULL REFERENCES r3a.knowledge_proposals(proposal_id),
    proposal_revision integer NOT NULL,
    decision text NOT NULL CHECK (decision IN ('approve','reject','defer')),
    reviewer_principal text NOT NULL,
    authorization_ref jsonb NOT NULL,
    invocation_id text NOT NULL,
    correlation_id uuid NOT NULL,
    batch_id text NOT NULL,
    rationale text,
    source_digest char(64) NOT NULL,
    decided_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    knowledge_item_id text
);
CREATE INDEX IF NOT EXISTS knowledge_review_decisions_proposal_idx
    ON r3a.knowledge_review_decisions(proposal_id,decision_id);

CREATE FUNCTION r3a.reject_knowledge_decision_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'r3a.knowledge_review_decisions is append-only';
END;
$$;
CREATE TRIGGER knowledge_review_decisions_append_only
BEFORE UPDATE OR DELETE ON r3a.knowledge_review_decisions
FOR EACH ROW EXECUTE FUNCTION r3a.reject_knowledge_decision_mutation();

CREATE TABLE IF NOT EXISTS r3a.institutional_knowledge_items (
    knowledge_item_id text PRIMARY KEY,
    proposal_id text NOT NULL REFERENCES r3a.knowledge_proposals(proposal_id),
    proposal_revision integer NOT NULL,
    title text NOT NULL,
    category text NOT NULL,
    content text NOT NULL,
    content_sha256 char(64) NOT NULL,
    source_digest char(64) NOT NULL,
    source_references jsonb NOT NULL,
    approval_decision_id bigint NOT NULL REFERENCES r3a.knowledge_review_decisions(decision_id),
    reviewer_principal text NOT NULL,
    approved_at timestamptz NOT NULL,
    supersedes_item_id text REFERENCES r3a.institutional_knowledge_items(knowledge_item_id),
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(proposal_id,proposal_revision)
);
CREATE INDEX IF NOT EXISTS institutional_knowledge_active_idx
    ON r3a.institutional_knowledge_items(active,category);
