-- Strengthen context pins with the evidence references for the resolved HR/directory edge.
-- Existing pre-contract test pins remain explicitly incomplete (NULL) and cannot be served
-- by ApprovedCharacterContextProvider, which requires these values on every lookup.

ALTER TABLE r3a.resident_character_context_pins
    ADD COLUMN directory_snapshot_sha256 char(64),
    ADD COLUMN directory_source_ref text,
    ADD COLUMN hr_source_ref text,
    ADD COLUMN hr_principal_association_ref text,
    ADD COLUMN office_id text,
    ADD COLUMN office_role text;

ALTER TABLE r3a.resident_character_context_pins
    ADD CONSTRAINT resident_context_pin_directory_digest_check
        CHECK (directory_snapshot_sha256 IS NULL OR directory_snapshot_sha256 ~ '^[a-f0-9]{64}$'),
    ADD CONSTRAINT resident_context_pin_provenance_complete_check
        CHECK (
            (directory_snapshot_sha256 IS NULL AND directory_source_ref IS NULL
             AND hr_source_ref IS NULL AND hr_principal_association_ref IS NULL
             AND office_id IS NULL AND office_role IS NULL)
            OR
            (directory_snapshot_sha256 IS NOT NULL AND directory_source_ref IS NOT NULL
             AND hr_source_ref IS NOT NULL AND hr_principal_association_ref IS NOT NULL
             AND office_id IS NOT NULL AND office_role IS NOT NULL)
        );
