"""Read-only retrieval from explicitly configured institutional documents.

This adapter delegates deterministic parsing and relevance matching to the
existing R3A knowledge helper, then enriches each result with document-level
provenance and retrieval-time freshness observations.
"""
from __future__ import annotations

import hashlib
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from r3a_runtime.capability_contracts import CapabilityProviderResult
from r3a_runtime.knowledge import retrieve_bytes


class InstitutionalKnowledgeProvider:
    def __init__(self, configuration: dict[str, Any]):
        if (not isinstance(configuration, dict) or set(configuration) !=
                {"sources", "max_results", "max_document_bytes"}):
            raise ValueError("knowledge provider configuration has an invalid shape")
        max_results = configuration["max_results"]
        max_document_bytes = configuration["max_document_bytes"]
        if isinstance(max_results, bool) or not isinstance(max_results, int) or not 1 <= max_results <= 100:
            raise ValueError("max_results must be between 1 and 100")
        if (isinstance(max_document_bytes, bool) or not isinstance(max_document_bytes, int)
                or not 1 <= max_document_bytes <= 10485760):
            raise ValueError("max_document_bytes must be between 1 and 10485760")
        if (not isinstance(configuration["sources"], list)
                or not 1 <= len(configuration["sources"]) <= 100):
            raise ValueError("sources must contain between 1 and 100 entries")
        source_ids: set[str] = set()
        for source in configuration["sources"]:
            if not isinstance(source, dict) or set(source) != {
                    "source_id", "path", "freshness_max_age_seconds"}:
                raise ValueError("each source must declare source_id, path, and freshness_max_age_seconds")
            source_id = source["source_id"]
            if (not isinstance(source_id, str)
                    or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", source_id) is None
                    or source_id in source_ids):
                raise ValueError("source IDs must be valid and unique")
            source_ids.add(source_id)
            if not isinstance(source["path"], str) or not Path(source["path"]).expanduser().is_absolute():
                raise ValueError("configured source paths must be absolute")
            age = source["freshness_max_age_seconds"]
            if isinstance(age, bool) or not isinstance(age, (int, float)) or not math.isfinite(age) or age < 0:
                raise ValueError("freshness_max_age_seconds must be finite and nonnegative")
        self.sources = tuple(configuration["sources"])
        self.max_results = max_results
        self.max_document_bytes = max_document_bytes

    def invoke(self, arguments: dict[str, Any], *, context: dict[str, Any]) -> Any:
        query = arguments["query"].strip()
        if not query or len(query) > 2000:
            raise ValueError("query must contain 1 to 2000 non-whitespace characters")
        limit = arguments.get("limit", self.max_results)
        observed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        results: list[dict[str, Any]] = []
        observations: list[dict[str, Any]] = []
        for source in self.sources:
            path = Path(source["path"]).expanduser().resolve()
            try:
                with path.open("rb") as document:
                    source_stat = os.fstat(document.fileno())
                    raw = document.read(self.max_document_bytes + 1)
                if len(raw) > self.max_document_bytes:
                    observations.append({"source_id": source["source_id"], "uri": path.as_uri(),
                                         "availability": "unavailable", "freshness": "unavailable",
                                         "error": "document_exceeds_configured_size_limit"})
                    continue
                digest = hashlib.sha256(raw).hexdigest()
                modified_at = datetime.fromtimestamp(source_stat.st_mtime, timezone.utc)
                age_seconds = max(0, (datetime.now(timezone.utc) - modified_at).total_seconds())
                freshness = "fresh" if age_seconds <= source["freshness_max_age_seconds"] else "stale"
                observations.append({"source_id": source["source_id"], "uri": path.as_uri(),
                                     "availability": "available", "freshness": freshness,
                                     "document_revision": digest, "document_sha256": digest,
                                     "document_modified_at": modified_at.isoformat().replace("+00:00", "Z"),
                                     "retrieved_at": observed_at, "age_seconds": age_seconds})
                # Reuse the AP1 source-aware extractor; it reads the same bounded,
                # digest-pinned document selected above.
                excerpts = retrieve_bytes(raw, path.name, source["source_id"], query)
                for excerpt in excerpts:
                    results.append({"source_id": source["source_id"], "uri": path.as_uri(),
                                    "source": path.name,
                                    "document_revision": digest, "document_sha256": digest,
                                    "source_sha256": digest,
                                    "document_modified_at": modified_at.isoformat().replace("+00:00", "Z"),
                                    "retrieved_at": observed_at, "freshness": freshness,
                                    "source_path": excerpt["source_path"],
                                    "content": excerpt["content"], "sha256": excerpt["sha256"],
                                    "excerpt_sha256": excerpt["sha256"],
                                    "matched_terms": excerpt["matched_terms"]})
            except (OSError, UnicodeError, ValueError) as exc:
                observations.append({"source_id": source["source_id"], "uri": path.as_uri(),
                                     "availability": "unavailable", "freshness": "unavailable",
                                     "error": type(exc).__name__})
        results.sort(key=lambda item: (-len(item["matched_terms"]), item["source_id"], item["source_path"]))
        results = results[:min(limit, self.max_results)]
        output = {"schema_id": "r3a.institutional-knowledge-results.v1", "schema_version": 1,
                  "query": query, "observed_at": observed_at, "sources": observations,
                  "results": results}
        evidence = [{"evidence_id": item["source_id"], **item} for item in results]
        return CapabilityProviderResult(output, evidence)


def create_provider(configuration: dict[str, Any]) -> InstitutionalKnowledgeProvider:
    return InstitutionalKnowledgeProvider(configuration)
