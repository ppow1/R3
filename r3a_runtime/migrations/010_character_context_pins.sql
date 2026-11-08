-- R3A resident character context: immutable activation-bound execution pins.
-- Stores provenance references and exact revisions only; never prompt/context content.

CREATE TABLE r3a.resident_character_context_pins (
    pin_id uuid PRIMARY KEY,
    resident_id text NOT NULL,
    dossier_revision text NOT NULL,
    dossier_sha256 char(64) NOT NULL CHECK (dossier_sha256 ~ '^[a-f0-9]{64}$'),
    execution_kind text NOT NULL CHECK (execution_kind IN ('inference_activity','conversation_boundary')),
    execution_ref text NOT NULL,
    identity_revision text NOT NULL,
    directory_resident_id text NOT NULL,
    binding_revision bigint NOT NULL CHECK (binding_revision > 0),
    provider_id text NOT NULL,
    principal_ref text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (resident_id, execution_kind, execution_ref),
    FOREIGN KEY (resident_id, dossier_revision)
        REFERENCES r3a.resident_dossier_revisions(resident_id, dossier_revision)
);

CREATE FUNCTION r3a.reject_resident_context_pin_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'resident character context pins are immutable';
END;
$$;

CREATE TRIGGER resident_character_context_pins_immutable
    BEFORE UPDATE OR DELETE ON r3a.resident_character_context_pins
    FOR EACH ROW EXECUTE FUNCTION r3a.reject_resident_context_pin_mutation();

COMMENT ON TABLE r3a.resident_character_context_pins IS
    'Pins approved character revision, identity binding and provider to one inference or conversation execution boundary; stores no prompt text.';
