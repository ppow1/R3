"""Deterministic, inspectable prompt composition from dossier components."""

# R3 CONTROLLED SOURCE
# File: r3a_runtime/residents/prompts.py
# Component: R3A-RESIDENT-DOSSIERS
# File Revision: 1.0.0
# Created: 2026-11-08 UTC (exact time not independently captured)
# Created By: Codex GPT-6
# Purpose: Compose provider-neutral prompt modules from approved, active, classification-safe components.
# Execution Model: Pure deterministic projection; returned digest identifies exact composition.
# Observability: Component IDs, versions, source refs, approval states and SHA-256 are inspectable.
# Dependencies: Python standard library; resident dossier contract.
# Authority: Dossier prompts do not grant tools, capabilities, or operational authority.
# Changed: 2026-11-08 UTC (exact time not independently captured) | CHARACTER-ARCHITECTURE | Codex GPT-6 | Add deterministic prompt composer.
# Supersedes: None
# Contracts: r3a.resident.dossier.v1; r3a.resident.prompt-composition.v1
# Tests: tests/test_r3a_resident_dossiers.py
# History/Predecessor: New file.

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .validation import validate_dossier


_ORDER = (
    "identity", "professional_responsibilities", "conversational_personality",
    "behavioral_boundaries", "emotional_expression", "relationships_memory",
    "situational_context", "epistemic_expression", "model_adaptation",
)
_CLASSIFICATION_RANK = {"public": 0, "institutional": 1}


@dataclass(frozen=True)
class PromptComposition:
    text: str
    component_refs: tuple[tuple[str, str], ...]
    source_refs: tuple[str, ...]
    sha256: str
    provisional: bool


def compose_prompt(dossier: dict[str, Any], *, include_institutional: bool = True,
                   provider_id: str | None = None) -> PromptComposition:
    """Compose approved and safe prompt modules in a stable order."""
    validate_dossier(dossier)
    dossier_status = dossier["governance"]["approval_status"]
    parts: list[tuple[str, str, str]] = []
    for component in dossier.get("prompt_components", []):
        if component["approval_status"] not in {"approved", "active"}:
            continue
        classification = component["classification"]
        if classification not in _CLASSIFICATION_RANK or (classification == "institutional" and not include_institutional):
            continue
        if component.get("provider_id") not in (None, provider_id):
            continue
        parts.append((component.get("kind", "situational_context"), component["component_id"], component["version"]))
    order = {kind: index for index, kind in enumerate(_ORDER)}
    components = {
        (x["component_id"], x["version"]): x for x in dossier.get("prompt_components", [])
    }
    parts.sort(key=lambda x: (order.get(x[0], len(order)), x[1], x[2]))
    blocks = []
    sources: list[str] = []
    for _, component_id, version in parts:
        item = components[(component_id, version)]
        blocks.append(f"[{component_id}@{version}]\n{item['text'].strip()}")
        sources.extend(source["source_id"] for source in item.get("sources", [])
                       if isinstance(source, dict) and isinstance(source.get("source_id"), str))
    preamble = "This is the current dossier-backed resident context. It conveys no operational authority."
    if dossier_status not in {"approved", "active"}:
        preamble += " Character material is provisional and must not be represented as settled canon."
    rendered = preamble + ("\n\n" + "\n\n".join(blocks) if blocks else "")
    digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    return PromptComposition(rendered, tuple((x[1], x[2]) for x in parts),
                             tuple(sorted(set(sources))), digest,
                             dossier_status not in {"approved", "active"})
