"""Bounded R3A-owned SQLite sample journal with last-known stale fallback."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _open(path: str) -> sqlite3.Connection:
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not target.exists():
        descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
    else:
        target.chmod(0o600)
    conn = sqlite3.connect(target, timeout=2)
    conn.execute("PRAGMA max_page_count=16384")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("""CREATE TABLE IF NOT EXISTS telemetry_samples (
        sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('fresh','stale','unavailable')),
        observed_at TEXT NOT NULL,
        attempted_at TEXT NOT NULL,
        content_json TEXT NOT NULL,
        sha256 TEXT NOT NULL
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS telemetry_samples_source_time_idx "
                 "ON telemetry_samples(source_id, attempted_at DESC)")
    return conn


@contextmanager
def _connection(path: str):
    conn = _open(path)
    try:
        with conn:
            yield conn
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


def apply_freshness_and_history(samples: list[dict[str, Any]], config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Persist each source attempt, fall back to a recent measured sample, and return bounded history."""
    history_env = config.get("history_path_env", "")
    history_path = os.environ.get(history_env) if history_env else None
    if not history_path:
        history = {"available": False, "error": "history_path_environment_not_configured", "samples": []}
        return samples, _history_evidence(history, _now().isoformat().replace("+00:00", "Z"))

    now = _now()
    now_text = now.isoformat().replace("+00:00", "Z")
    window_seconds = int(config.get("history_window_seconds", 300))
    capacity = int(config.get("history_capacity_per_source", 128))
    result: list[dict[str, Any]] = []
    all_history: list[dict[str, Any]] = []
    try:
        with _connection(history_path) as conn:
            for sample in samples:
                source_id = str(sample["source_id"])
                state = sample.get("freshness", {}).get("state", "unavailable")
                attempted_at = str(sample.get("collection_finished_at") or sample.get("observed_at") or now_text)
                observed_at = str(sample.get("observed_at") or attempted_at)
                content = sample.get("content", {})
                if state != "fresh":
                    previous = conn.execute(
                        "SELECT observed_at,content_json,sha256 FROM telemetry_samples "
                        "WHERE source_id=? AND state='fresh' ORDER BY sample_id DESC LIMIT 1", (source_id,)
                    ).fetchone()
                    if previous:
                        age = max(0.0, (now - _parse_time(previous[0])).total_seconds())
                        if age <= float(sample.get("freshness", {}).get("max_age_seconds", config.get("max_age_seconds", 30))):
                            observed_at, content = previous[0], json.loads(previous[1])
                            state = "stale"
                            sample = {**sample, "content": content, "observed_at": observed_at,
                                      "last_attempt_at": attempted_at,
                                      "last_attempt_error": sample.get("error")}
                            sample["freshness"] = {**sample.get("freshness", {}), "state": "stale",
                                                    "age_seconds": age}
                digest = hashlib.sha256(_json(content).encode()).hexdigest()
                sample["sha256"] = digest
                conn.execute("INSERT INTO telemetry_samples(source_id,state,observed_at,attempted_at,content_json,sha256) "
                             "VALUES(?,?,?,?,?,?)", (source_id, state, observed_at, attempted_at,
                                                    _json(content), digest))
                cutoff = (now - timedelta(seconds=window_seconds)).isoformat().replace("+00:00", "Z")
                conn.execute("DELETE FROM telemetry_samples WHERE source_id=? AND attempted_at<?",
                             (source_id, cutoff))
                conn.execute("DELETE FROM telemetry_samples WHERE source_id=? AND sample_id NOT IN "
                             "(SELECT sample_id FROM telemetry_samples WHERE source_id=? "
                             "ORDER BY sample_id DESC LIMIT ?)", (source_id, source_id, capacity))
                latest_rows = conn.execute(
                    "SELECT state,observed_at,attempted_at,content_json,sha256 FROM telemetry_samples "
                    "WHERE source_id=? ORDER BY sample_id DESC LIMIT ?", (source_id, int(config.get("history_limit", 8)))
                ).fetchall()
                for row in latest_rows:
                    all_history.append({"source_id": source_id, "state": row[0], "observed_at": row[1],
                                        "attempted_at": row[2], "content": json.loads(row[3]), "sha256": row[4]})
                sample["freshness"] = {**sample.get("freshness", {}), "state": state,
                                        "age_seconds": max(0.0, (now - _parse_time(observed_at)).total_seconds())
                                        if state in {"fresh", "stale"} else None}
                result.append(sample)
        history_content = {"available": True, "window_seconds": window_seconds,
                           "capacity_per_source": capacity, "samples_per_source": int(config.get("history_limit", 8)),
                           "samples": all_history}
    except (OSError, sqlite3.Error, ValueError, TypeError) as exc:
        result = samples
        history_content = {"available": False, "error": type(exc).__name__, "samples": []}
    return result, _history_evidence(history_content, now_text)


def _history_evidence(content: dict[str, Any], observed_at: str) -> dict[str, Any]:
    digest = hashlib.sha256(_json(content).encode()).hexdigest()
    available = content.get("available") is True
    return {"source_id": "r3a.telemetry.history", "source_path": "R3A configured local SQLite journal",
            "content": content, "sha256": digest, "observed_at": observed_at,
            "source_timestamp": observed_at, "source_timestamp_basis": "R3A history journal retrieval time",
            "freshness": {"state": "fresh" if available else "unavailable",
                          "age_seconds": 0 if available else None}}
