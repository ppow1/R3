"""
R3 CONTROLLED SOURCE
File: r3a_runtime/knowledge.py
Component: R3A-KNOWLEDGE-RETRIEVAL
File Revision: 1.0.5
Created: 2026-11-06 UTC (exact time not independently captured)
Created By: Codex GPT-6
Purpose: Retrieve relevant evidence from explicitly configured knowledge sources and preserve its source digest.
Execution Model: Deterministic, in-process retrieval; no external service.
Observability: Source IDs, excerpt paths/text, source and excerpt SHA-256 digests, and match terms.
Dependencies: Python standard library; allowlisted files supplied by R3A configuration.
Authority: AP1 / R3A-019 authorized by Steward; read-only institutional knowledge use.
Changed: 2026-11-06T18:02:08Z | R3A-019 | Codex GPT-6 | Add source-aware retrieval for durable Grace activities.
Changed: 2026-11-06T18:26:37Z | R3A-019 | Codex GPT-6 | Match source-state phrases despite preceding articles or unrelated "from" phrases.
Changed: 2026-11-06T18:54:42Z | R3A-019 | Codex GPT-6 | Keep each transition set together as one answerable, source-traceable knowledge fact.
Changed: 2026-11-06T19:01:13Z | R3A-019 | Codex GPT-6 | Treat after/following a state as an explicit source-state transition query.
Supersedes: None.
Contracts: R3A-019 knowledge grounding and retrieval; AP1 activity evidence lineage.
Tests: tests/test_r3a_ap1.py retrieval and digest checks.
History/Predecessor: Git blob 6cde0e7501aab0d945b6103425bcfbcb23ee7792 at commit 81d33d631daaf35fa50091219ea0326a5373851f.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


_WORD = re.compile(r"[a-z0-9_]+", re.IGNORECASE)


def _json_facts(value: Any, prefix: str = "") -> list[tuple[str, str]]:
    facts: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if key == "transitions" and isinstance(child, dict):
                for source, targets in child.items():
                    if isinstance(targets, list):
                        destinations = ", ".join(str(target) for target in targets)
                        facts.append((f"{path}.{source}",
                                      f"Transitions from {source}: {destinations}"))
                continue
            facts.extend(_json_facts(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            facts.extend(_json_facts(child, f"{prefix}[{index}]"))
    else:
        facts.append((prefix, f"{prefix}: {json.dumps(value, ensure_ascii=False)}"))
    return facts


def _chunks(text: str) -> list[tuple[str, str]]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return [(f"paragraph.{index + 1}", part.strip())
                for index, part in enumerate(re.split(r"\n\s*\n", text)) if part.strip()]
    return _json_facts(value)


def retrieve(path: Path, source_id: str, query: str) -> list[dict[str, Any]]:
    """Return all matching source facts in relevance order, preserving precise source lineage."""
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    query_terms = set(_WORD.findall(query.casefold()))
    if not query_terms:
        return []
    facts = _chunks(text)
    transition_sources = {match.group(1).casefold() for source_path, _ in facts
                          if (match := re.match(r"transitions\.([a-z0-9_-]+)(?:\[|$)",
                                                source_path.casefold()))}
    transition_source = next((state for state in transition_sources
                              if re.search(rf"\b(?:from|after|following)\s+(?:the\s+)?{re.escape(state)}\b",
                                           query.casefold())), None)
    ranked = []
    for source_path, excerpt in facts:
        terms = set(_WORD.findall(excerpt.casefold()))
        matched = sorted(query_terms & terms)
        if matched:
            score = len(matched)
            if transition_source:
                relation = re.match(r"transitions\.([a-z0-9_-]+)(?:\[|$)", source_path.casefold())
                if relation and relation.group(1) == transition_source:
                    score += len(query_terms)
            ranked.append((score, source_path, excerpt, matched))
    if not ranked:
        return []
    best_score = max(item[0] for item in ranked)
    # Preserve all equally relevant facts, while excluding weaker incidental word overlap.
    # This is relevance ranking rather than a fixed result-count/context cap.
    ranked = [item for item in ranked if item[0] == best_score]
    ranked.sort(key=lambda item: item[1])
    source_hash = hashlib.sha256(raw).hexdigest()
    return [{"source_id": source_id, "source": path.name, "source_sha256": source_hash,
             "source_path": source_path, "matched_terms": matched, "content": excerpt,
             "sha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest()}
            for _, source_path, excerpt, matched in ranked]
