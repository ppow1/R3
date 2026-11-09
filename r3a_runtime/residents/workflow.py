"""Character revision state machine; authentication remains an HR/gateway concern."""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet


STATES = ("draft", "proposed", "in_review", "approved", "published", "active", "rejected", "superseded")


@dataclass(frozen=True)
class CharacterRevision:
    resident_id: str
    revision: str
    author_id: str
    status: str
    evidence_refs: tuple[str, ...]
    durable_canon_change: bool
    target_is_author: bool = False


@dataclass(frozen=True)
class CharacterGovernance:
    independent_reviewers: FrozenSet[str]
    reviewer_policy_ref: str
    character_architects: FrozenSet[str]
    permitted_publishers: FrozenSet[str]
    permitted_activators: FrozenSet[str]


def transition_revision(revision: CharacterRevision, *, target_state: str,
                        actor_id: str, governance: CharacterGovernance) -> CharacterRevision:
    if target_state not in STATES or not actor_id:
        raise ValueError("valid target state and authenticated actor are required")
    allowed = {"draft": {"proposed", "rejected"}, "proposed": {"in_review", "rejected"},
               "in_review": {"approved", "rejected"}, "approved": {"published", "rejected"},
               "published": {"active", "superseded"}, "active": {"superseded"},
               "rejected": set(), "superseded": set()}
    if target_state not in allowed[revision.status]:
        raise ValueError("invalid character revision transition")
    if target_state == "approved":
        if not revision.evidence_refs:
            raise ValueError("character approval requires evidence or provenance")
        if revision.durable_canon_change and actor_id not in governance.character_architects:
            raise PermissionError("durable character canon approval authority denied")
        if revision.durable_canon_change and revision.target_is_author:
            if actor_id == revision.author_id or actor_id not in governance.independent_reviewers:
                raise PermissionError("self-authored durable canon requires independent configured review")
    if target_state == "published" and actor_id not in governance.permitted_publishers:
        raise PermissionError("publication authority denied")
    if target_state == "active" and actor_id not in governance.permitted_activators:
        raise PermissionError("runtime activation authority denied")
    if target_state == "approved" and revision.target_is_author and revision.durable_canon_change:
        if not governance.reviewer_policy_ref:
            raise PermissionError("independent reviewer policy is not configured")
    return CharacterRevision(revision.resident_id, revision.revision, revision.author_id,
                             target_state, revision.evidence_refs, revision.durable_canon_change,
                             revision.target_is_author)
