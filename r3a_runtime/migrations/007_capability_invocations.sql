-- Durable idempotency and audit result for canonical unified capability dispatch.
CREATE TABLE IF NOT EXISTS r3a.capability_invocations (
    idempotency_key text PRIMARY KEY,
    invocation_id text NOT NULL,
    operation_id text NOT NULL,
    request_digest text NOT NULL,
    state text NOT NULL CHECK (state IN ('STARTED','SUCCEEDED','FAILED','DENIED','DEFERRED','UNKNOWN')),
    request jsonb NOT NULL,
    authorization jsonb NOT NULL,
    result jsonb,
    evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS capability_invocations_invocation_id_idx
    ON r3a.capability_invocations(invocation_id);
