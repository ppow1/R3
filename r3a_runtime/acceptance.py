"""
R3 CONTROLLED SOURCE
File: r3a_runtime/acceptance.py
Component: R3A-OBJECTIVE-ACCEPTANCE
File Revision: 1.0.3
Created: 2026-11-07T02:35:35Z
Created By: Codex GPT-6
Purpose: Validate structured objective acceptance criteria against cited, digested evidence.
Execution Model: Deterministic in-process contract validation.
Observability: Typed criterion results and actionable evidence gaps persisted with activity progress.
Dependencies: Python standard library; Grace capability evidence contracts.
Authority: AP1 / R3A-019 false-completion correction, Steward Issue #43 comment 6701062165.
Changed: 2026-11-07T02:35:35Z | R3A-019-ACCEPTANCE-CORRECTION | Codex GPT-6 | Add generic evidence-backed directed path acceptance.
Changed: 2026-11-07T02:41:51Z | R3A-019-ACCEPTANCE-CORRECTION | Codex GPT-6 | Require current configured source digests and report unresolved reachable evidence states.
Changed: 2026-11-07T02:43:15Z | R3A-019-ACCEPTANCE-CORRECTION | Codex GPT-6 | Accept any answer route whose individual edges are independently evidenced.
Supersedes: None.
Contracts: r3a.objective-acceptance.v1.
Tests: tests/test_r3a_ap1.py.
History/Predecessor: New file; no predecessor.
"""
from __future__ import annotations

import hashlib
import re
from collections import deque
from typing import Any


OBJECTIVE_ACCEPTANCE_CONTRACT_ID = "r3a.objective-acceptance"
OBJECTIVE_ACCEPTANCE_CONTRACT_VERSION = "1.0.0"
_IDENTIFIER = re.compile(r"^[A-Z][A-Z0-9_]*$")
_TRANSITION = re.compile(r"^Transitions from ([A-Z][A-Z0-9_]*):\s*(.*)$")
_PATH_IN_ANSWER = re.compile(r"\b[A-Z][A-Z0-9_]*(?:\s*(?:->|→)\s*[A-Z][A-Z0-9_]*)+\b")


def validate_criteria(value: Any) -> list[dict[str, str]]:
    """Validate the versioned, data-only acceptance criteria stored with an objective."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("acceptance_criteria must be an array")
    normalized = []
    seen: set[str] = set()
    for criterion in value:
        if not isinstance(criterion, dict) or set(criterion) != {
                "criterion_id", "type", "from_state", "to_state"}:
            raise ValueError("each acceptance criterion requires criterion_id, type, from_state, and to_state")
        criterion_id = criterion["criterion_id"]
        kind = criterion["type"]
        source = criterion["from_state"]
        target = criterion["to_state"]
        if not isinstance(criterion_id, str) or not criterion_id.strip() or len(criterion_id) > 100:
            raise ValueError("criterion_id must be nonempty text of at most 100 characters")
        if criterion_id in seen:
            raise ValueError("acceptance criterion identifiers must be unique")
        if kind != "transition_path":
            raise ValueError(f"unsupported acceptance criterion type: {kind!r}")
        if not isinstance(source, str) or not _IDENTIFIER.fullmatch(source):
            raise ValueError("from_state must be an uppercase state identifier")
        if not isinstance(target, str) or not _IDENTIFIER.fullmatch(target):
            raise ValueError("to_state must be an uppercase state identifier")
        if source == target:
            raise ValueError("transition path endpoints must differ")
        seen.add(criterion_id)
        normalized.append({"criterion_id": criterion_id, "type": kind,
                           "from_state": source, "to_state": target})
    return normalized


def evidence_fingerprint(evidence: list[dict[str, Any]]) -> str:
    """Stable fingerprint used to detect a repeated rejected final with no new evidence."""
    manifest = sorted((str(item.get("source_id", "")), str(item.get("source_path", "")),
                       str(item.get("sha256", "")), str(item.get("source_sha256", "")))
                      for item in evidence)
    return hashlib.sha256(repr(manifest).encode("utf-8")).hexdigest()


def _cited_transition_graph(evidence: list[dict[str, Any]], cited_sources: set[str],
                            trusted_source_digests: dict[str, set[str]]) -> dict[str, dict[str, set[str]]]:
    """Build a directed graph only from integrity-checked, cited knowledge facts."""
    graph: dict[str, dict[str, set[str]]] = {}
    for item in evidence:
        source_id = item.get("source_id")
        source_path = item.get("source_path")
        content = item.get("content")
        if (not isinstance(source_id, str) or source_id not in cited_sources
                or not source_id.startswith("knowledge.")
                or not isinstance(source_path, str) or not source_path.startswith("transitions.")
                or not isinstance(content, str)
                or item.get("source_sha256") not in trusted_source_digests.get(
                    str(item.get("source")), set())):
            continue
        excerpt_digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if item.get("sha256") != excerpt_digest:
            continue
        match = _TRANSITION.fullmatch(content.strip())
        if not match or source_path != f"transitions.{match.group(1)}":
            continue
        source_state = match.group(1)
        targets = {state.strip() for state in match.group(2).split(",") if state.strip()}
        if not targets or any(not _IDENTIFIER.fullmatch(state) for state in targets):
            continue
        graph.setdefault(source_id, {}).setdefault(source_state, set()).update(targets)
    return graph


def _find_path(graph: dict[str, dict[str, set[str]]], source: str,
               target: str) -> tuple[list[str] | None, set[str], set[str]]:
    queue: deque[tuple[str, list[str]]] = deque([(source, [source])])
    visited = {source}
    reachable: set[str] = set()
    while queue:
        state, path = queue.popleft()
        for source_id, transitions in graph.items():
            for destination in transitions.get(state, set()):
                reachable.add(source_id)
                if destination == target:
                    return path + [destination], reachable, visited | {destination}
                if destination not in visited:
                    visited.add(destination)
                    queue.append((destination, path + [destination]))
    return None, reachable, visited


def validate_acceptance(criteria: list[dict[str, str]], evidence: list[dict[str, Any]],
                        decision: dict[str, Any],
                        trusted_source_digests: dict[str, set[str]]) -> list[dict[str, Any]]:
    """Return criteria unsupported by cited source facts or absent from the deliverable."""
    gaps: list[dict[str, Any]] = []
    citations = decision.get("evidence_refs", [])
    cited_sources = set(citations) if isinstance(citations, list) else set()
    graph = _cited_transition_graph(evidence, cited_sources, trusted_source_digests)
    answer = decision.get("assessment", "")
    answer = answer if isinstance(answer, str) else ""
    answer_paths = [re.sub(r"\s*(?:->|→)\s*", "→", match.group(0)).upper()
                    for match in _PATH_IN_ANSWER.finditer(answer)]

    for criterion in criteria:
        source = criterion["from_state"]
        target = criterion["to_state"]
        path, supporting_sources, reachable_states = _find_path(graph, source, target)
        if path is None:
            recorded_sources = {state for transitions in graph.values() for state in transitions}
            unresolved_states = sorted(reachable_states - recorded_sources)
            gaps.append({"criterion_id": criterion["criterion_id"],
                         "code": "evidence_path_incomplete",
                         "message": (f"No complete cited transition path from {source} to {target} is proven "
                                     f"by the collected knowledge evidence. States without cited outgoing "
                                     f"transition evidence: {', '.join(unresolved_states) or 'unknown'}. Continue authorized evidence "
                                     "gathering if possible, or return BLOCKED with the unresolved edge."),
                         "reachable_evidence_sources": sorted(supporting_sources),
                         "unresolved_source_states": unresolved_states})
            continue
        answer_is_supported = any(
            (nodes := candidate.split("→"))[0] == source and nodes[-1] == target
            and all(any(destination in transitions.get(left, set())
                        for transitions in graph.values())
                        for left, destination in zip(nodes, nodes[1:]))
            for candidate in answer_paths)
        if not answer_is_supported:
            expected = "→".join(path)
            gaps.append({"criterion_id": criterion["criterion_id"],
                         "code": "deliverable_path_missing",
                         "message": (f"Evidence supports a route such as {expected}, but the final assessment "
                                     f"does not state an evidence-supported ordered route from {source} to "
                                     f"{target}. Include such a route in the deliverable.")})
    return gaps
