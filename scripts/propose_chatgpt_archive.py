#!/usr/bin/env python3
"""Convert a ChatGPT export into pending Knowledge proposals without changing it.

R3 CONTROLLED SOURCE
File: scripts/propose_chatgpt_archive.py
Component: R3A-KNOWLEDGE-ARCHIVE-INTAKE
File Revision: 1.0.0
Created: 2026-11-08 UTC (exact time recorded in Git commit)
Created By: Codex GPT-6
Purpose: Build source-digested, review-only proposals from a supported ChatGPT JSON export.
Execution Model: Local, read-only source scan; writes a separate proposal catalog.
Observability: Catalog summary to stderr; output catalog contains source digest and conversation/message locators.
Dependencies: Python 3.12; existing r3a.knowledge-review-proposals.v1 importer.
Authority: Issue #47; no authority to approve or ingest.
Changed: 2026-11-08 | AP1-K2 | Codex GPT-6 | Add fixture-testable archive conversion into existing pending-proposal flow.
Supersedes: None.
Contracts: r3a.knowledge-review-proposals.v1; Website review contract v1.0.0.
Tests: tests/test_chatgpt_archive_intake.py.
History/Predecessor: New file; initial publication recorded in Git.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

MAX_ARCHIVE_BYTES = 256 * 1024 * 1024


def _message_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if not isinstance(content, dict):
        return ""
    parts = content.get("parts", [])
    if not isinstance(parts, list):
        return ""
    # Keep only plain text. Image/audio/file payloads and opaque attachment
    # references are omitted and never copied into the proposal catalog.
    return "\n".join(part.strip() for part in parts if isinstance(part, str) and part.strip())


def _sensitivity_flags(text: str) -> list[str]:
    flags = ["conversation-archive", "historical-reference", "individual-review-required"]
    patterns = {
        "credential": r"(?i)\b(password|passwd|api[_ -]?key|access[_ -]?token|secret)\b\s*[:=]\s*\S+",
        "personal-data-review": r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|\b\+?\d[\d(). -]{8,}\d\b",
        "private-hr": r"(?i)\b(social security|ssn|medical record|salary|disciplinary action)\b",
        "protected-relationship": r"(?i)\b(evelyn|gray man|romantic relationship|intimate relationship|relationship history)\b",
    }
    for flag, pattern in patterns.items():
        if re.search(pattern, text):
            flags.append(flag)
    return flags


def build_catalog(raw: bytes, *, source_label: str, source_path: str) -> dict[str, Any]:
    """Create a normal pending-proposal catalog from a conversations.json export."""
    if not source_label.strip() or len(source_label) > 160:
        raise ValueError("source_label must contain 1 to 160 characters")
    parsed = json.loads(raw.decode("utf-8"))
    if not isinstance(parsed, list):
        raise ValueError("ChatGPT export root must be a conversations array")
    archive_digest = hashlib.sha256(raw).hexdigest()
    entries: list[dict[str, Any]] = []
    for conversation in parsed:
        if not isinstance(conversation, dict):
            continue
        conversation_id = conversation.get("id")
        mapping = conversation.get("mapping")
        if not isinstance(conversation_id, str) or not conversation_id or not isinstance(mapping, dict):
            continue
        messages: list[tuple[str, str, str, str]] = []
        for node_id, node in mapping.items():
            if not isinstance(node, dict) or not isinstance(node.get("message"), dict):
                continue
            message = node["message"]
            author = message.get("author") or {}
            role = author.get("role") if isinstance(author, dict) else None
            if role not in {"user", "assistant"}:
                continue
            text = _message_text(message)
            if text:
                stamp = str(message.get("create_time") or "unknown-time")
                messages.append((str(message.get("id") or node_id), role, stamp, text))
        if not messages:
            continue
        title = str(conversation.get("title") or "Untitled conversation").strip()[:240]
        created = conversation.get("create_time")
        updated = conversation.get("update_time")
        transcript = "\n\n".join(f"[{stamp}] {role}: {text}" for _, role, stamp, text in messages)
        stable = hashlib.sha256(f"{archive_digest}:{conversation_id}".encode()).hexdigest()[:24]
        proposal_id = f"chat-archive-{stable}"
        batch_id = f"chat-archive-{archive_digest[:20]}"
        source = {
            "repository": "local-chatgpt-export",
            "path": source_label,
            "location": f"conversation:{conversation_id}; messages:{','.join(mid for mid, _, _, _ in messages)}",
            "revision": f"sha256:{archive_digest}",
            "commit": None,
            "git_blob": None,
            "sha256": archive_digest,
            "excerpt": f"Conversation title: {title}; message count: {len(messages)}; conversation ID: {conversation_id}",
            "url": None,
        }
        entries.append({
            "entry_id": proposal_id,
            "version": 1,
            "title": f"Historical conversation: {title}",
            "summary": f"Archived ChatGPT conversation from {source_label}; {len(messages)} text messages. Historical reference only.",
            "why_it_matters": "Potentially preserves prior institutional reasoning or decisions; claims require current-source verification and this archive does not confer authority.",
            "category": "historical-conversation-reference",
            "proposed_canonical_knowledge": f"Historical conversation transcript (not current policy or verified fact). Title: {title}. Created: {created!r}; updated: {updated!r}.\n\n{transcript}",
            "sources": [source],
            "authority_assessment": "Historical conversation export; no current institutional authority established.",
            "freshness": "historical; verify claims against current authoritative sources",
            "conflicts": ["Conversation content may be superseded or inaccurate; compare with current authoritative records."],
            "flags": _sensitivity_flags(transcript),
            "recommended_disposition": "defer",
            "decision": None,
        })
    batch = {
        "batch_id": f"chat-archive-{archive_digest[:20]}",
        "title": f"ChatGPT archive import candidates ({source_label})",
        "description": "Historical, source-digested candidates. Every conversation requires individual Steward review; no batch action implicitly approves any entry.",
        "project": "R3 institutional knowledge / historical conversation archive",
        "category": "historical-conversation-reference",
        "source_documents": [{"repository": "local-chatgpt-export", "path": source_label,
                              "revision": f"sha256:{archive_digest}", "sha256": archive_digest,
                              "modified_at": None, "url": None}],
        "summary": f"{len(entries)} conversation candidates from one export. Attachment payloads omitted.",
        "conflicts_and_supersession": "All content remains historical reference; validate authority and freshness individually before promotion.",
        "recommended_disposition": "Review each item individually; no default decision.",
        "entry_ids": [item["entry_id"] for item in entries],
        "source_count": 1,
        "source_digest": archive_digest,
    }
    return {"schema_id": "r3a.knowledge-review-proposals.v1", "schema_version": 1,
            "catalog_id": f"chatgpt-export-{archive_digest[:20]}", "catalog_revision": 1,
            "review_state": "proposed", "batches": [batch], "entries": entries,
            "intake": {"source_label": source_label, "source_sha256": archive_digest,
                       "source_size_bytes": len(raw), "source_path": source_path,
                       "ingestion_mode": "proposal-only", "original_modified": False}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="verified ChatGPT conversations.json export (read only)")
    parser.add_argument("output", type=Path, help="new proposal catalog path; source is never changed")
    parser.add_argument("--source-label", required=True, help="stable provenance label without personal filesystem path")
    args = parser.parse_args(argv)
    source = args.source.expanduser().resolve(strict=True)
    output = args.output.expanduser().resolve()
    if source == output:
        parser.error("output must not be the source archive")
    if output.exists():
        parser.error("output already exists; choose a new catalog path")
    if source.stat().st_size > MAX_ARCHIVE_BYTES:
        parser.error(f"archive exceeds the bounded prototype limit of {MAX_ARCHIVE_BYTES} bytes")
    raw = source.read_bytes()
    catalog = build_catalog(raw, source_label=args.source_label, source_path=str(source))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"catalog": str(output), "source_sha256": catalog["intake"]["source_sha256"],
                      "proposals": len(catalog["entries"]), "modified_source": False}), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
