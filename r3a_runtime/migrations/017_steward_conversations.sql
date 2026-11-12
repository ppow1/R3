-- R3 CONTROLLED MIGRATION
-- Contract: r3a.steward-conversation.v1
-- Purpose: Persist authenticated Steward conversations in the authoritative CME database.
-- Owner: R3A CME; conversation turns reference the existing durable activity ledger.

CREATE TABLE r3a.steward_conversations (
    conversation_id uuid PRIMARY KEY,
    owner_principal_id text NOT NULL,
    resident_id text NOT NULL,
    resident_display_name text NOT NULL,
    directory_snapshot_sha256 char(64) NOT NULL CHECK (directory_snapshot_sha256 ~ '^[a-f0-9]{64}$'),
    directory_invocation_id text NOT NULL,
    client_conversation_id uuid NOT NULL,
    title text NOT NULL DEFAULT 'Conversation',
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (owner_principal_id, client_conversation_id)
);
CREATE INDEX steward_conversations_owner_updated_idx
    ON r3a.steward_conversations(owner_principal_id, updated_at DESC);

CREATE TABLE r3a.steward_conversation_messages (
    message_id uuid PRIMARY KEY,
    conversation_id uuid NOT NULL REFERENCES r3a.steward_conversations(conversation_id),
    sequence_no bigint GENERATED ALWAYS AS IDENTITY,
    sender_kind text NOT NULL CHECK (sender_kind IN ('steward', 'resident')),
    sender_id text NOT NULL,
    body text NOT NULL,
    delivery_state text NOT NULL CHECK (delivery_state IN ('accepted', 'processing', 'completed', 'blocked')),
    activity_id uuid REFERENCES r3a.activities(activity_id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (conversation_id, sequence_no),
    UNIQUE (conversation_id, message_id)
);
CREATE INDEX steward_conversation_messages_history_idx
    ON r3a.steward_conversation_messages(conversation_id, sequence_no);
CREATE UNIQUE INDEX steward_conversation_one_turn_activity_idx
    ON r3a.steward_conversation_messages(activity_id)
    WHERE activity_id IS NOT NULL AND sender_kind='steward';
