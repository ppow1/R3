#!/usr/bin/env python3
"""Idempotently load a reviewed catalog as pending proposals, never as knowledge."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from r3a_plugins.institutional_knowledge.review_store import KnowledgeReviewStore


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: import_knowledge_proposals.py CATALOG.json")
    env_name = os.environ.get("R3A_KNOWLEDGE_DATABASE_DSN_ENV", "R3A_KNOWLEDGE_DATABASE_DSN")
    dsn = os.environ.get(env_name)
    if not dsn:
        raise SystemExit(f"set {env_name} to the isolated R3A PostgreSQL DSN")
    catalog = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(json.dumps(KnowledgeReviewStore(dsn).import_catalog(catalog), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
