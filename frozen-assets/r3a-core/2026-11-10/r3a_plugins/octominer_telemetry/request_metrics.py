"""Privacy-minimized projection of R3A's own durable Grace model-turn records."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _positive_count(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def normalize_stream_deltas(deltas: Any) -> dict[str, Any] | None:
    """Derive app-side chars/s only from two or more timestamped text delta lengths."""
    if not isinstance(deltas, list) or len(deltas) < 2:
        return None
    parsed = []
    for item in deltas:
        if not isinstance(item, dict):
            return None
        at = _time(item.get("observed_at"))
        count = _positive_count(item.get("delta_characters"))
        if at is None or count is None:
            return None
        parsed.append((at, count))
    parsed.sort(key=lambda x: x[0])
    elapsed = (parsed[-1][0] - parsed[0][0]).total_seconds()
    if elapsed <= 0:
        return None
    return {"characters": sum(count for _, count in parsed), "elapsed_seconds": elapsed,
            "characters_per_second": sum(count for _, count in parsed) / elapsed,
            "first_delta_at": parsed[0][0].isoformat().replace("+00:00", "Z"),
            "last_delta_at": parsed[-1][0].isoformat().replace("+00:00", "Z"),
            "measurement_basis": "R3A application-side timestamped text deltas; not model tokens/s"}


def project_turns(rows: list[dict[str, Any]], *, now: datetime, window_seconds: int,
                  max_rows: int, max_age_seconds: int = 30) -> dict[str, Any]:
    turns: dict[str, dict[str, Any]] = {}
    for row in rows[:max_rows]:
        activity_id = str(row.get("activity_id", "unknown"))
        state = row.get("state")
        turn_list = row.get("result_turns") or row.get("checkpoint_turns") or []
        if not isinstance(turn_list, list):
            continue
        for index, turn in enumerate(turn_list):
            if not isinstance(turn, dict):
                continue
            usage = turn.get("usage")
            usage = usage if isinstance(usage, dict) else {}
            timing = usage.get("r3a_measurement")
            timing = timing if isinstance(timing, dict) else {}
            finished_at = _time(timing.get("request_finished_at") or turn.get("observed_at"))
            if finished_at is None or (now - finished_at).total_seconds() > window_seconds:
                continue
            started_at = _time(timing.get("request_started_at"))
            elapsed_ms = timing.get("elapsed_ms")
            if (isinstance(elapsed_ms, bool) or not isinstance(elapsed_ms, (int, float))
                    or elapsed_ms < 0):
                elapsed_ms = ((finished_at - started_at).total_seconds() * 1000
                              if started_at is not None and finished_at >= started_at else None)
            request_ref = turn.get("request_ref") or timing.get("request_ref")
            key = str(request_ref or f"{activity_id}:{index}")
            prompt_tokens = _positive_count(usage.get("prompt_tokens"))
            completion_tokens = _positive_count(usage.get("completion_tokens"))
            delta_stats = normalize_stream_deltas(timing.get("stream_deltas"))
            turns[key] = {
                "activity_id": activity_id, "activity_state": state,
                "request_ref": request_ref, "route_id": timing.get("route_id"),
                "provider": timing.get("provider"), "model": timing.get("model"),
                "request_started_at": started_at.isoformat().replace("+00:00", "Z") if started_at else None,
                "request_finished_at": finished_at.isoformat().replace("+00:00", "Z"),
                "elapsed_ms": round(float(elapsed_ms), 3) if elapsed_ms is not None else None,
                "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                "stream_cadence": delta_stats,
                "evidence_source": "R3A durable Grace model-turn record",
            }
    samples = sorted(turns.values(), key=lambda x: x["request_finished_at"], reverse=True)
    latest_time = _time(samples[0]["request_finished_at"]) if samples else None
    age_seconds = max(0.0, (now - latest_time).total_seconds()) if latest_time else None
    freshness_state = ("unavailable" if not samples else
                       ("fresh" if age_seconds is not None and age_seconds <= max_age_seconds else "stale"))
    counted = [x for x in samples if x["completion_tokens"] is not None]
    measurable = [x for x in counted if x["elapsed_ms"] is not None and x["elapsed_ms"] > 0]
    output_tokens = sum(x["completion_tokens"] for x in counted)
    prompt_tokens = [x["prompt_tokens"] for x in samples if x["prompt_tokens"] is not None]
    elapsed = sum(x["elapsed_ms"] for x in measurable) / 1000
    stream = [x["stream_cadence"] for x in samples if x["stream_cadence"] is not None]
    content = {
        "available": bool(samples), "window_seconds": window_seconds,
        "requests": samples,
        "prompt_tokens": sum(prompt_tokens) if prompt_tokens else None,
        "completion_tokens": output_tokens if counted else None,
        "completed_output_tokens": output_tokens if counted else None,
        "provider_call_elapsed_seconds": elapsed if measurable else None,
        "completed_output_tokens_per_provider_call_second": output_tokens / elapsed if elapsed else None,
        "throughput_basis": "R3A provider-call output tokens / total provider-call elapsed time; includes service/transport overhead",
        "streaming_cadence": stream[-1] if stream else None,
        "streaming_cadence_state": "measured" if stream else "unavailable_no_timestamped_stream_deltas",
        "native_model_token_rate": None,
        "native_model_token_rate_state": "unavailable_not_observed",
    }
    digest = hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"source_id": "r3a.model.request-telemetry", "source_path": "R3A durable Grace activity model-turn projection",
            "content": content, "sha256": digest,
            "observed_at": latest_time.isoformat().replace("+00:00", "Z") if latest_time else None,
            "retrieved_at": now.isoformat().replace("+00:00", "Z"),
            "source_timestamp": None,
            "source_timestamp_basis": "R3A activity turn timestamps; history projection time is separate",
            "freshness": {"state": freshness_state, "age_seconds": age_seconds,
                          "max_age_seconds": max_age_seconds, "window_seconds": window_seconds}}


def read_r3a_model_turns(config: dict[str, Any]) -> dict[str, Any]:
    """Read only turn telemetry fields using a separately configured R3A read-only DSN."""
    now = _now()
    env_name = config.get("request_database_dsn_env", "")
    dsn = os.environ.get(env_name) if env_name else None
    window = int(config.get("history_window_seconds", 300))
    max_age = int(config.get("max_age_seconds", 30))
    max_rows = int(config.get("request_activity_limit", 100))
    if not dsn:
        evidence = project_turns([], now=now, window_seconds=window, max_rows=max_rows,
                                 max_age_seconds=max_age)
        evidence["content"]["error"] = "request_database_dsn_environment_not_configured"
        evidence["sha256"] = hashlib.sha256(json.dumps(evidence["content"], sort_keys=True,
                                                          separators=(",", ":")).encode()).hexdigest()
        return evidence
    try:
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(dsn, row_factory=dict_row) as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            rows = conn.execute(
                "SELECT activity_id::text AS activity_id,state, "
                "result->'reasoning_trace'->'model_turns' AS result_turns, "
                "checkpoint->'reasoning_state'->'model_turns' AS checkpoint_turns "
                "FROM r3a.activities WHERE activity_type='grace.objective' "
                "AND (result ? 'reasoning_trace' OR checkpoint ? 'reasoning_state') "
                "ORDER BY updated_at DESC LIMIT %s", (max_rows,)
            ).fetchall()
            conn.commit()
        return project_turns(rows, now=now, window_seconds=window, max_rows=max_rows,
                              max_age_seconds=max_age)
    except (ImportError, OSError, ValueError, TypeError, RuntimeError):
        evidence = project_turns([], now=now, window_seconds=window, max_rows=max_rows,
                                 max_age_seconds=max_age)
        evidence["content"]["error"] = "request_database_read_failed"
        evidence["sha256"] = hashlib.sha256(json.dumps(evidence["content"], sort_keys=True,
                                                          separators=(",", ":")).encode()).hexdigest()
        return evidence
    except Exception:
        # Database details/DSNs may contain secrets; expose only unavailable state.
        evidence = project_turns([], now=now, window_seconds=window, max_rows=max_rows,
                                 max_age_seconds=max_age)
        evidence["content"]["error"] = "request_database_read_failed"
        evidence["sha256"] = hashlib.sha256(json.dumps(evidence["content"], sort_keys=True,
                                                          separators=(",", ":")).encode()).hexdigest()
        return evidence
