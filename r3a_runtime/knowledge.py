"""
R3 CONTROLLED SOURCE
File: r3a_runtime/knowledge.py
Component: R3A-KNOWLEDGE-RETRIEVAL
File Revision: 1.1.0
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
Changed: 2026-11-06T19:16:11Z | R3A-019 | Codex GPT-6 | Resolve explicit transitions.STATE references to that single state fact.
Changed: 2026-11-07T21:57:39Z | AP1-K2 | Codex GPT-6 | Retrieve Markdown paragraphs with heading and line-range provenance.
Supersedes: None.
Contracts: R3A-019 knowledge grounding and retrieval; AP1 activity evidence lineage.
Tests: tests/test_r3a_ap1.py and tests/test_r3a_institutional_knowledge.py retrieval, citation, and digest checks.
History/Predecessor: Git blob ec02e7e4eae9944fe87335ac61f369e803957722 at commit 362510b7d32edd1eabdcb07c9677f1b6a47f2adf.
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
        return _markdown_chunks(text)
    return _json_facts(value)


def _markdown_chunks(text: str) -> list[tuple[str, str]]:
    """Split Markdown into source-located paragraphs without caching document state."""
    lines = text.splitlines()
    headings: list[tuple[int, str, int]] = []
    paragraphs: list[tuple[str, str]] = []
    block: list[str] = []
    block_start = 0
    paragraph_counts: dict[tuple[tuple[int, str, int], ...], int] = {}
    table_header: str | None = None
    table_header_line = 0
    fence_marker: tuple[str, int] | None = None
    in_comment = False

    def add_fact(content: str, start_line: int, end_line: int, kind: str) -> None:
        section_key = tuple(headings)
        paragraph_counts[section_key] = paragraph_counts.get(section_key, 0) + 1
        section_path = "/".join(
            f"h{level}.{re.sub(r'[^a-z0-9]+', '-', title.casefold()).strip('-') or 'untitled'}@L{line}"
            for level, title, line in section_key
        ) or "root"
        paragraphs.append((
            f"markdown.{section_path}.{kind}.{paragraph_counts[section_key]}@L{start_line}-L{end_line}",
            content,
        ))

    def flush(end_line: int) -> None:
        nonlocal block, block_start
        content = "\n".join(part.strip() for part in block if part.strip()).strip()
        if content:
            add_fact(content, block_start, end_line, "paragraph")
        block = []
        block_start = 0

    for number, line in enumerate(lines, start=1):
        visible = line
        if fence_marker is not None:
            block.append(visible)
            if re.match(rf"^\s*{re.escape(fence_marker[0])}{{{fence_marker[1]},}}\s*$", visible):
                flush(number)
                fence_marker = None
            continue
        if in_comment:
            if "-->" in visible:
                visible = visible.split("-->", 1)[1]
                in_comment = False
            else:
                continue
        if "<!--" in visible:
            before, _, after = visible.partition("<!--")
            visible = before
            if "-->" in after:
                visible += after.split("-->", 1)[1]
            else:
                in_comment = True
        fence = re.match(r"^\s*(`{3,}|~{3,})", visible)
        if fence:
            flush(number - 1)
            table_header = None
            fence_marker = (fence.group(1)[0], len(fence.group(1)))
            block_start = number
            block.append(visible)
            continue
        heading = re.match(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", visible)
        if heading:
            flush(number - 1)
            table_header = None
            level, title = len(heading.group(1)), heading.group(2).strip()
            headings = [item for item in headings if item[0] < level]
            headings.append((level, title, number))
            continue
        table_row = re.match(r"^\s*\|.*\|\s*$", visible)
        if table_row:
            flush(number - 1)
            normalized = visible.strip()
            if table_header is None:
                table_header, table_header_line = normalized, number
            elif re.fullmatch(r"\|[\s:|-]+\|", normalized) is None:
                add_fact(f"{table_header}\n{normalized}", table_header_line, number, "table-row")
            continue
        table_header = None
        if not visible.strip():
            flush(number - 1)
            continue
        if re.match(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", visible) and block:
            flush(number - 1)
        if not block:
            block_start = number
        block.append(visible)
    flush(len(lines))
    return paragraphs


def retrieve(path: Path, source_id: str, query: str) -> list[dict[str, Any]]:
    """Return all matching source facts in relevance order, preserving precise source lineage."""
    raw = path.read_bytes()
    return retrieve_bytes(raw, path.name, source_id, query)


def retrieve_bytes(raw: bytes, source_name: str, source_id: str,
                   query: str) -> list[dict[str, Any]]:
    """Retrieve from one already-read document snapshot."""
    text = raw.decode("utf-8")
    query_terms = set(_WORD.findall(query.casefold()))
    if not query_terms:
        return []
    facts = _chunks(text)
    transition_sources = {match.group(1).casefold() for source_path, _ in facts
                          if (match := re.match(r"transitions\.([a-z0-9_-]+)(?:\[|$)",
                                                source_path.casefold()))}
    transition_source = next((state for state in transition_sources
                              if (re.search(rf"\b(?:from|after|following)\s+(?:the\s+)?{re.escape(state)}\b",
                                            query.casefold())
                                  or re.search(rf"\btransitions\.{re.escape(state)}\b", query.casefold()))), None)
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
    return [{"source_id": source_id, "source": source_name, "source_sha256": source_hash,
             "source_path": source_path, "matched_terms": matched, "content": excerpt,
             "sha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest()}
            for _, source_path, excerpt, matched in ranked]
