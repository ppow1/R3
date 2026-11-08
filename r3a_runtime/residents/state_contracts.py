"""Validation helpers for resident memory, emotional state, and relationships."""

# R3 CONTROLLED SOURCE
# File: r3a_runtime/residents/state_contracts.py
# Component: R3A-RESIDENT-DOSSIERS
# File Revision: 1.0.0
# Created: 2026-11-08 UTC (exact creation time not captured)
# Created By: Codex GPT-6
# Purpose: Define provenance-bearing memory/relationship records separate from character traits.
# Execution Model: Pure contract validation; persistence belongs to institutional state services.
# Observability: Raises stable validation errors; records retain source/time/classification metadata.
# Dependencies: Python standard library.
# Authority: No relationship, emotion, or memory is canonical without its source and approval rules.
# Changed: 2026-11-08 UTC | CHARACTER-ARCHITECTURE | Codex GPT-6 | Add memory and relationship contract validators.
# Supersedes: None
# Contracts: r3a.resident.memory-entry.v1; r3a.resident.relationship.v1; r3a.resident.emotion-state.v1
# Tests: tests/test_r3a_resident_dossiers.py
# History/Predecessor: New file.

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any


MEMORY_CATEGORIES = {"episodic", "professional", "institutional", "personal", "relationship"}
CLASSIFICATIONS = {"public", "institutional", "personnel_sensitive", "protected"}


def validate_memory_entry(entry: dict[str, Any]) -> None:
    required = {"memory_id", "category", "content_ref", "source_refs", "occurred_at",
                "recorded_at", "classification", "retention_rule_ref", "status"}
    if not isinstance(entry, dict) or not required <= entry.keys():
        raise ValueError("memory entry is missing required provenance fields")
    if entry["category"] not in MEMORY_CATEGORIES or entry["classification"] not in CLASSIFICATIONS:
        raise ValueError("memory category or classification is invalid")
    if (not entry["source_refs"] or not all(isinstance(ref, str) and ref for ref in entry["source_refs"])
            or not isinstance(entry["retention_rule_ref"], str) or not entry["retention_rule_ref"]):
        raise ValueError("memory requires source references")
    for name in ("occurred_at", "recorded_at"):
        datetime.fromisoformat(entry[name].replace("Z", "+00:00"))


def validate_relationship(relationship: dict[str, Any]) -> None:
    required = {"relationship_id", "from_resident_id", "to_resident_id", "affinity",
                "trust", "respect", "professional_rapport", "basis_refs", "history"}
    if not isinstance(relationship, dict) or not required <= relationship.keys():
        raise ValueError("relationship is missing directional state fields")
    if relationship["from_resident_id"] == relationship["to_resident_id"]:
        raise ValueError("interpersonal relationship must be directional between distinct residents")
    if not relationship["basis_refs"]:
        raise ValueError("relationship ratings require experience/source references")
    if isinstance(relationship["affinity"], bool) or not -1.0 <= float(relationship["affinity"]) <= 1.0:
        raise ValueError("affinity must be between -1 and 1")
    for field in ("trust", "respect", "professional_rapport"):
        value = relationship[field]
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 100:
            raise ValueError(f"{field} must be an integer from 0 through 100")


def validate_emotional_state(state: dict[str, Any]) -> None:
    required = {"state_id", "resident_id", "captured_at", "expires_at", "source_ref", "values"}
    if not isinstance(state, dict) or not required <= state.keys():
        raise ValueError("emotional state is missing required transient-state fields")
    if not state["source_ref"]:
        raise ValueError("emotional state requires a source reference")
    if set(state["values"]) - {"valence", "arousal", "dominant_emotion", "intensity"}:
        raise ValueError("unsupported emotional dimension")
    if "intensity" in state["values"] and not 0 <= int(state["values"]["intensity"]) <= 100:
        raise ValueError("emotional intensity must be between 0 and 100")
    datetime.fromisoformat(state["captured_at"].replace("Z", "+00:00"))
    if state["expires_at"] is not None:
        datetime.fromisoformat(state["expires_at"].replace("Z", "+00:00"))


def append_memory_correction(prior: dict[str, Any], successor: dict[str, Any]) -> dict[str, Any]:
    """Return a correction successor while leaving the prior memory immutable."""
    validate_memory_entry(prior)
    corrected = deepcopy(successor)
    corrected["supersedes_memory_id"] = prior["memory_id"]
    if corrected.get("category") != prior["category"]:
        raise ValueError("a memory correction must preserve its category")
    validate_memory_entry(corrected)
    return corrected


def evolve_relationship(current: dict[str, Any], *, affinity: float, trust: int,
                       respect: int, professional_rapport: int,
                       experience_ref: str, occurred_at: str) -> dict[str, Any]:
    """Create a sourced relationship successor and retain its prior rating snapshot."""
    validate_relationship(current)
    if not experience_ref:
        raise ValueError("relationship growth requires an experience reference")
    updated = deepcopy(current)
    updated.setdefault("history", []).append({
        "recorded_at": occurred_at,
        "basis_refs": list(current["basis_refs"]),
        "affinity": current["affinity"],
        "trust": current["trust"],
        "respect": current["respect"],
        "professional_rapport": current["professional_rapport"],
    })
    updated["affinity"] = affinity
    updated["trust"] = trust
    updated["respect"] = respect
    updated["professional_rapport"] = professional_rapport
    updated["basis_refs"] = list(dict.fromkeys([*current["basis_refs"], experience_ref]))
    validate_relationship(updated)
    return updated


def transition_emotional_state(previous: dict[str, Any], successor: dict[str, Any]) -> dict[str, Any]:
    """Link a newer transient emotion state to its predecessor without changing traits."""
    validate_emotional_state(previous)
    transitioned = deepcopy(successor)
    validate_emotional_state(transitioned)
    if transitioned["resident_id"] != previous["resident_id"]:
        raise ValueError("emotional transition must preserve resident identity")
    old_time = datetime.fromisoformat(previous["captured_at"].replace("Z", "+00:00"))
    new_time = datetime.fromisoformat(transitioned["captured_at"].replace("Z", "+00:00"))
    if new_time <= old_time:
        raise ValueError("emotional transition must have a later capture time")
    transitioned["supersedes_state_id"] = previous["state_id"]
    return transitioned
