"""Filesystem-backed immutable dossier revisions with explicit approval and rollback."""

# R3 CONTROLLED SOURCE
# File: r3a_runtime/residents/repository.py
# Component: R3A-RESIDENT-DOSSIERS
# File Revision: 1.0.0
# Created: 2026-11-08 UTC (exact time not independently captured)
# Created By: Codex GPT-6
# Purpose: Store and retrieve versioned resident dossier artifacts without a resident map in code.
# Execution Model: Local filesystem adapter; database adapter remains an integration boundary.
# Observability: Append-only JSONL audit events include actor claim, digest and revision lineage.
# Dependencies: Python standard library; dossier JSON contract.
# Authority: File writes do not authenticate HR/Character Architecture roles or grant runtime authority.
# Changed: 2026-11-08 UTC (exact time not independently captured) | CHARACTER-ARCHITECTURE | Codex GPT-6 | Add versioned repository and lifecycle operations.
# Supersedes: None
# Contracts: r3a.resident.dossier.v1; data/residents/index.json
# Tests: tests/test_r3a_resident_dossiers.py
# History/Predecessor: New file.

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .validation import validate_dossier


class DossierError(RuntimeError):
    """Repository operation failed without changing the active dossier pointer."""


class RevisionConflict(DossierError):
    """Expected active dossier revision did not match the repository."""


class DossierRepository:
    """Read dossiers by stored ID and immutable version, resolving source IDs explicitly."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.index_path = self.root / "index.json"
        self.audit_path = self.root / "audit.jsonl"

    def _index(self) -> dict[str, Any]:
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DossierError(f"cannot read dossier index: {exc}") from exc
        if data.get("schema_id") != "r3a.resident.dossier-index" or data.get("schema_version") != 1:
            raise DossierError("unsupported dossier index")
        return data

    def list_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._index().get("residents", {})))

    def get(self, resident_id: str, revision: str | None = None) -> dict[str, Any]:
        index = self._index().get("residents", {})
        item = index.get(resident_id)
        if item is None:
            raise KeyError(resident_id)
        selected = revision or item["current_revision"]
        if not re.fullmatch(r"\d+\.\d+\.\d+", selected):
            raise DossierError("invalid dossier revision selector")
        path = self._safe_path(item["revisions"][selected])
        try:
            dossier = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            raise DossierError(f"cannot load {resident_id}@{selected}: {exc}") from exc
        validate_dossier(dossier)
        if dossier["identity"]["resident_id"] != resident_id or dossier["revision"] != selected:
            raise DossierError("index-to-dossier identity mismatch")
        return dossier

    def create(self, dossier: dict[str, Any], *, actor: str, reason: str,
               approval_status: str = "proposed") -> str:
        """Register a new dossier record without appointing, activating, or granting authority."""
        validate_dossier(dossier)
        resident_id, revision = dossier["identity"]["resident_id"], dossier["revision"]
        if approval_status not in {"proposed", "in_review", "approved", "rejected"}:
            raise DossierError("invalid initial approval status")
        index = self._index()
        if resident_id in index.get("residents", {}):
            raise RevisionConflict(f"dossier already exists: {resident_id}")
        record = json.loads(json.dumps(dossier))
        record["governance"]["approval_status"] = approval_status
        record["governance"]["revision_actor"] = actor
        record["governance"]["revision_reason"] = reason
        record["governance"].setdefault("revision_history", []).append({
            "revision": revision, "status": approval_status, "actor_claim": actor,
            "reason": reason, "recorded_at": datetime.now(timezone.utc).isoformat(),
        })
        path = self.root / "dossiers" / _slug(resident_id) / f"{revision}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        content = self._canonical_bytes(record)
        path.write_bytes(content)
        index["residents"][resident_id] = {
            "current_revision": revision,
            "revisions": {revision: str(path.relative_to(self.root))},
            "identity_status": record["identity"]["identity_status"],
            "approval_status": approval_status,
        }
        self._write_index(index)
        self._audit({"event": "dossier_created", "resident_id": resident_id,
                     "revision": revision, "approval_status": approval_status,
                     "actor_claim": actor, "reason": reason,
                     "sha256": hashlib.sha256(content).hexdigest()})
        return revision

    def resolve_source_id(self, source_id: str, value: str, *, confirmed_only: bool = True) -> str:
        matches = []
        for resident_id in self.list_ids():
            dossier = self.get(resident_id)
            for alias in dossier.get("identity", {}).get("source_ids", []):
                if alias.get("source_id") == source_id and alias.get("value") == value:
                    if not confirmed_only or alias.get("link_status") == "confirmed":
                        matches.append(resident_id)
        if len(matches) != 1:
            raise KeyError(f"source identity unresolved or ambiguous: {source_id}/{value}")
        return matches[0]

    @staticmethod
    def _canonical_bytes(dossier: dict[str, Any]) -> bytes:
        return (json.dumps(dossier, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")) + "\n").encode("utf-8")

    def add_revision(self, dossier: dict[str, Any], *, expected_revision: str,
                     actor: str, reason: str, approval_status: str = "proposed") -> str:
        """Persist a new immutable version; caller identity/role must be externally attested."""
        validate_dossier(dossier)
        resident_id = dossier["identity"]["resident_id"]
        index = self._index()
        entry = index.get("residents", {}).get(resident_id)
        if entry is None or entry.get("current_revision") != expected_revision:
            raise RevisionConflict(f"current revision does not match {expected_revision}")
        if approval_status not in {"proposed", "in_review", "approved", "rejected"}:
            raise DossierError("invalid new revision approval status")
        revision = dossier["revision"]
        if revision in entry.get("revisions", {}):
            raise RevisionConflict(f"revision already exists: {revision}")
        updated = json.loads(json.dumps(dossier))
        updated.setdefault("governance", {})["approval_status"] = approval_status
        updated["governance"]["revision_actor"] = actor
        updated["governance"]["revision_reason"] = reason
        updated["governance"].setdefault("revision_history", []).append({
            "revision": revision, "status": approval_status, "actor_claim": actor,
            "reason": reason, "recorded_at": datetime.now(timezone.utc).isoformat(),
        })
        path = self.root / "dossiers" / _slug(resident_id) / f"{revision}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        content = self._canonical_bytes(updated)
        path.write_bytes(content)
        entry["revisions"][revision] = str(path.relative_to(self.root))
        entry["current_revision"] = revision
        self._write_index(index)
        self._audit({"event": "revision_added", "resident_id": resident_id,
                     "revision": revision, "prior_revision": expected_revision,
                     "approval_status": approval_status, "actor_claim": actor,
                     "reason": reason, "sha256": hashlib.sha256(content).hexdigest()})
        return revision

    def set_approval(self, resident_id: str, revision: str, *, expected_revision: str,
                     actor: str, owner: str, approved: bool, reason: str) -> None:
        """Record one domain owner's decision without implying the other domain approved."""
        if owner not in {"hr", "character_architecture"} or not isinstance(actor, str) or not actor.strip():
            raise DossierError("approval requires a declared workflow owner and actor reference")
        prior = self.get(resident_id, expected_revision)
        current = self._index()["residents"][resident_id]["current_revision"]
        if current != expected_revision:
            raise RevisionConflict("approval must start from the active revision")
        successor = json.loads(json.dumps(prior))
        successor["revision"] = revision
        governance = successor.setdefault("governance", {})
        owner_approvals = governance.setdefault("owner_approvals", {})
        owner_approvals[owner] = {
            "status": "approved" if approved else "rejected",
            "actor_claim": actor,
            "reason": reason,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        if not approved:
            governance["approval_status"] = "rejected"
        elif (all(owner_approvals.get(key, {}).get("status") == "approved"
                  for key in ("hr", "character_architecture"))
              and successor["identity"]["identity_status"] == "authoritative"):
            governance["approval_status"] = "approved"
        else:
            governance["approval_status"] = "in_review"
        self.add_revision(successor, expected_revision=expected_revision, actor=actor,
                          reason=f"{owner} approval decision: {reason}",
                          approval_status=governance["approval_status"])

    def rollback(self, resident_id: str, *, to_revision: str, expected_revision: str,
                 actor: str, reason: str) -> None:
        """Move the active pointer to a retained revision and record the reversal event."""
        index = self._index()
        entry = index.get("residents", {}).get(resident_id)
        if entry is None or entry.get("current_revision") != expected_revision:
            raise RevisionConflict("rollback active revision conflict")
        if to_revision not in entry.get("revisions", {}):
            raise KeyError(to_revision)
        if to_revision == expected_revision:
            raise DossierError("rollback target is already active")
        old = expected_revision
        entry["current_revision"] = to_revision
        self._write_index(index)
        target = self.get(resident_id, to_revision)
        self._audit({"event": "revision_rollback", "resident_id": resident_id,
                     "from_revision": old, "to_revision": to_revision,
                     "actor_claim": actor, "reason": reason,
                     "target_approval_status": target["governance"]["approval_status"]})

    def _write_index(self, index: dict[str, Any]) -> None:
        temp = self.index_path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(index, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        temp.replace(self.index_path)

    def _audit(self, event: dict[str, Any]) -> None:
        event["occurred_at"] = datetime.now(timezone.utc).isoformat()
        with self.audit_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    def _safe_path(self, relative_path: str) -> Path:
        candidate = (self.root / relative_path).resolve()
        root = self.root.resolve()
        if not candidate.is_relative_to(root):
            raise DossierError("dossier index path escapes repository root")
        return candidate


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
