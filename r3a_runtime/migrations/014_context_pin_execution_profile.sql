-- Bind approved character context to the exact verified resident execution profile.
-- The profile's resident ID must be supplied by a trusted directory/profile resolver;
-- this migration stores references only and creates no profile or identity mapping.

ALTER TABLE r3a.resident_character_context_pins
    ADD COLUMN execution_profile_id text,
    ADD COLUMN execution_profile_revision text,
    ADD COLUMN execution_profile_resident_id text,
    ADD COLUMN execution_route_id text,
    ADD COLUMN execution_profile_source_ref text;

ALTER TABLE r3a.resident_character_context_pins
    ADD CONSTRAINT resident_context_pin_profile_provenance_complete_check
        CHECK (
            (execution_profile_id IS NULL AND execution_profile_revision IS NULL
             AND execution_profile_resident_id IS NULL AND execution_route_id IS NULL
             AND execution_profile_source_ref IS NULL)
            OR
            (execution_profile_id IS NOT NULL AND execution_profile_revision IS NOT NULL
             AND execution_profile_resident_id IS NOT NULL AND execution_route_id IS NOT NULL
             AND execution_profile_source_ref IS NOT NULL)
        );
