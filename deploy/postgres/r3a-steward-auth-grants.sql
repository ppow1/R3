-- Apply as the authorized R3A AP0 database owner after migration 010.
-- Configure peer-authenticated local-socket mappings separately; no password is created here.
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='r3a_steward_auth') THEN
    CREATE ROLE r3a_steward_auth LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='r3a_steward_identity_operator') THEN
    CREATE ROLE r3a_steward_identity_operator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
  END IF;
END $$;

GRANT USAGE ON SCHEMA r3a TO r3a_steward_auth, r3a_steward_identity_operator;

-- AP3 runtime: authenticate, update failed-login counters, and invoke the constrained enrollment function,
-- and create/read/revoke only Steward sessions. It cannot associate or disable identities.
GRANT SELECT (principal_id,login_name,issuer,state,password_salt,password_verifier,password_scheme,
              failed_attempts,locked_until)
  ON r3a.steward_accounts TO r3a_steward_auth;
GRANT UPDATE (failed_attempts,locked_until,updated_at)
  ON r3a.steward_accounts TO r3a_steward_auth;
GRANT SELECT (token_digest,principal_id,issuer,assertion_id,authenticated_at,factor_refs,issued_at,expires_at,revoked_at,correlation_id),
      INSERT (token_digest,principal_id,issuer,assertion_id,authenticated_at,factor_refs,issued_at,expires_at,correlation_id),
      UPDATE (revoked_at)
  ON r3a.steward_sessions TO r3a_steward_auth;
GRANT INSERT ON r3a.institution_events TO r3a_steward_auth;
GRANT EXECUTE ON FUNCTION r3a.complete_steward_enrollment(char(64),text,bytea,bytea)
  TO r3a_steward_auth;

-- Separate local operator identity for approved association, challenge issuance, and disable/revoke.
GRANT SELECT (principal_id,login_name,state,association_id,source_system,source_subject_id,source_revision,provenance),
      INSERT (principal_id,login_name,issuer,state,
  association_id,source_system,source_subject_id,source_revision,provenance,associated_at)
  ON r3a.steward_accounts TO r3a_steward_identity_operator;
GRANT SELECT (challenge_digest,principal_id,purpose,created_by,created_at,expires_at,consumed_at),
      INSERT (challenge_digest,principal_id,purpose,created_by,created_at,expires_at),
      UPDATE (consumed_at)
  ON r3a.steward_enrollment_challenges TO r3a_steward_identity_operator;
GRANT INSERT ON r3a.institution_events TO r3a_steward_identity_operator;
GRANT EXECUTE ON FUNCTION r3a.disable_steward_account(text,text,text,text)
  TO r3a_steward_identity_operator;
