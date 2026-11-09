-- R3 CONTROLLED MIGRATION
-- File: r3a_runtime/migrations/018_steward_identity.sql
-- Component: R3A-AP3-IDENTITY
-- File Revision: 1.0.0
-- Created: 2026-11-09T17:31:32Z
-- Created By: R3 Integration
-- Purpose: Store independently associated R3A Steward identities, password verifiers, and single-use enrollment/recovery challenges.
-- Execution Model: Ordered after the current R3A migration baseline through the checksum-verified AP0 migration runner; schema depends on migrations 001 and 009.
-- Observability: Checksummed schema_migrations record and append-only identity lifecycle events.
-- Dependencies: r3a schema, institution_events, and steward_sessions from migrations 001 and 009.
-- Authority: Approved R3A Authentication Independence Plan, AP3/R3A-010, Issue #49.
-- Security: No R3 account secret/session data; opaque challenge digests only; no default Steward row.
-- Changed: 2026-11-09T17:31:32Z | AP3-NATIVE-AUTH | R3 Integration | Add independently owned R3A account, challenge, and revocation schema.
-- Supersedes: None.
-- Contracts: R3A native Steward identity lifecycle v1.
-- Tests: PostgreSQL 16 isolated migration/role integration reported by Remote Access; managed migration pending.
-- History/Predecessor: Added by Remote Access commit 16b6230d5b48bb9bd1872f687f43678faeb296d7.

CREATE TABLE r3a.steward_accounts (
    principal_id text PRIMARY KEY,
    login_name text NOT NULL UNIQUE,
    issuer text NOT NULL,
    state text NOT NULL CHECK (state IN ('pending_enrollment','active','disabled','revoked')),
    password_salt bytea,
    password_verifier bytea,
    password_scheme text,
    failed_attempts integer NOT NULL DEFAULT 0 CHECK (failed_attempts >= 0),
    locked_until timestamptz,
    association_id uuid NOT NULL UNIQUE,
    source_system text NOT NULL,
    source_subject_id text NOT NULL,
    source_revision text NOT NULL,
    provenance jsonb NOT NULL,
    associated_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (principal_id ~ '^steward:[A-Za-z0-9-]+$'),
    CHECK (login_name = lower(login_name) AND login_name ~ '^[A-Za-z0-9][A-Za-z0-9._@+-]{2,253}$'),
    CHECK (issuer = 'r3a-steward'),
    CHECK (length(source_system) > 0 AND length(source_subject_id) > 0 AND length(source_revision) > 0),
    CHECK ((password_salt IS NULL AND password_verifier IS NULL AND password_scheme IS NULL)
        OR (password_salt IS NOT NULL AND password_verifier IS NOT NULL AND password_scheme = 'scrypt-32768-8-1')),
    CHECK (state <> 'active' OR password_verifier IS NOT NULL)
);
CREATE UNIQUE INDEX steward_accounts_source_identity_uq
    ON r3a.steward_accounts(source_system, source_subject_id);

CREATE TABLE r3a.steward_enrollment_challenges (
    challenge_digest char(64) PRIMARY KEY CHECK (challenge_digest ~ '^[a-f0-9]{64}$'),
    principal_id text NOT NULL REFERENCES r3a.steward_accounts(principal_id),
    purpose text NOT NULL CHECK (purpose IN ('initial_enrollment','credential_recovery')),
    created_by text NOT NULL,
    created_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz,
    CHECK (expires_at > created_at)
);
CREATE INDEX steward_enrollment_challenges_live_idx
    ON r3a.steward_enrollment_challenges(principal_id, expires_at)
    WHERE consumed_at IS NULL;

CREATE INDEX steward_accounts_active_idx ON r3a.steward_accounts(principal_id)
    WHERE state = 'active';

CREATE FUNCTION r3a.disable_steward_account(p_principal_id text, p_state text,
                                             p_actor text, p_reason text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = r3a, pg_temp
AS $$
DECLARE
    event_time timestamptz := clock_timestamp();
BEGIN
    IF p_state NOT IN ('disabled','revoked') OR COALESCE(p_actor,'') = ''
       OR p_reason NOT IN ('steward_request','suspected_compromise','identity_correction') THEN
        RAISE EXCEPTION 'account_state_change_invalid';
    END IF;
    UPDATE steward_accounts SET state=p_state,updated_at=event_time
      WHERE principal_id=p_principal_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'principal_not_found'; END IF;
    UPDATE steward_sessions SET revoked_at=event_time
      WHERE principal_id=p_principal_id AND revoked_at IS NULL;
    INSERT INTO institution_events(event_id,event_type,schema_version,subject_type,subject_id,
        occurred_at,actor,correlation_id,reason,outcome,implementation_revision,evidence)
      VALUES (gen_random_uuid(),'steward.identity.account_state_changed',1,'steward_principal',
        p_principal_id,event_time,p_actor,gen_random_uuid(),'steward identity state changed',
        'accepted','ap3-m1',jsonb_build_object('state',p_state,'reason',p_reason,
        'active_sessions_revoked',true));
END;
$$;
REVOKE ALL ON FUNCTION r3a.disable_steward_account(text,text,text,text) FROM PUBLIC;

CREATE FUNCTION r3a.complete_steward_enrollment(p_challenge_digest char(64), p_login_name text,
    p_password_salt bytea, p_password_verifier bytea)
RETURNS TABLE(principal_id text, issuer text, purpose text, created_by text)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = r3a, pg_temp
AS $$
DECLARE
    identity_row record;
    event_time timestamptz := clock_timestamp();
BEGIN
    SELECT c.principal_id,c.purpose,c.expires_at,c.consumed_at,c.created_by,
           a.state,a.login_name,a.issuer
      INTO identity_row
      FROM steward_enrollment_challenges c
      JOIN steward_accounts a USING(principal_id)
     WHERE c.challenge_digest=p_challenge_digest
     FOR UPDATE OF c,a;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE='28000', MESSAGE='enrollment_challenge_invalid';
    END IF;
    IF identity_row.consumed_at IS NOT NULL OR identity_row.expires_at <= event_time
       OR identity_row.login_name IS DISTINCT FROM p_login_name
       OR (identity_row.purpose='initial_enrollment' AND identity_row.state <> 'pending_enrollment')
       OR (identity_row.purpose='credential_recovery' AND identity_row.state <> 'active') THEN
        RAISE EXCEPTION USING ERRCODE='28000', MESSAGE='enrollment_challenge_invalid';
    END IF;
    IF p_password_salt IS NULL OR p_password_verifier IS NULL
       OR octet_length(p_password_salt) <> 16 OR octet_length(p_password_verifier) <> 32 THEN
        RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='credential_verifier_invalid';
    END IF;
    UPDATE steward_accounts SET password_salt=p_password_salt,password_verifier=p_password_verifier,
        password_scheme='scrypt-32768-8-1',state='active',failed_attempts=0,locked_until=NULL,
        updated_at=event_time WHERE steward_accounts.principal_id=identity_row.principal_id;
    UPDATE steward_enrollment_challenges SET consumed_at=event_time
      WHERE challenge_digest=p_challenge_digest;
    INSERT INTO institution_events(event_id,event_type,schema_version,subject_type,subject_id,
        occurred_at,actor,correlation_id,reason,outcome,implementation_revision,evidence)
      VALUES (gen_random_uuid(),'steward.identity.credential_enrolled',1,'steward_principal',
        identity_row.principal_id,event_time,identity_row.created_by,gen_random_uuid(),
        'steward credential enrolled','accepted','ap3-m1',
        jsonb_build_object('purpose',identity_row.purpose,'credential_scheme','scrypt-32768-8-1'));
    RETURN QUERY SELECT identity_row.principal_id,identity_row.issuer,identity_row.purpose,identity_row.created_by;
END;
$$;
REVOKE ALL ON FUNCTION r3a.complete_steward_enrollment(char(64),text,bytea,bytea) FROM PUBLIC;

-- Existing AP0 role remains migration owner; runtime grant is provisioned separately and narrowly.
