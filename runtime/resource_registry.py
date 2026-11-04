# R3 CONTROLLED SOURCE
# File: runtime/resource_registry.py
# Purpose: R3-owned capacity/resource inventory with provenance and freshness.
"""Resource discovery is descriptive, never an authorization grant."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Callable, Iterable

STATES = frozenset({"unknown", "offline", "online", "degraded"})
@dataclass(frozen=True)
class Resource:
    resource_id: str
    kind: str
    host: str
    capabilities: tuple[str, ...]
    capacity: dict
    observed_at: str
    state: str
    source: str

    def __post_init__(self):
        if not all((self.resource_id, self.kind, self.host, self.source)):
            raise ValueError("Resource identity and provenance required")
        if self.state not in STATES:
            raise ValueError("Invalid resource state")
        observed = datetime.fromisoformat(self.observed_at.replace("Z", "+00:00"))
        if observed.tzinfo is None:
            raise ValueError("Observation must be timezone aware")
        if not isinstance(self.capacity, dict) or not isinstance(self.capabilities, tuple):
            raise ValueError("Invalid capacity/capabilities")

class ResourceRegistry:
    def __init__(self, providers: Iterable[Callable[[], Iterable[Resource]]] = ()):
        self.providers = tuple(providers)

    def snapshot(self, *, now: datetime | None = None, max_age_seconds: float = 120) -> list[dict]:
        if max_age_seconds <= 0:
            raise ValueError("max_age_seconds must be positive")
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError("now must be timezone aware")
        results = {}
        for provider in self.providers:
            for resource in provider():
                if resource.resource_id in results:
                    raise ValueError("Duplicate resource identity")
                observation = datetime.fromisoformat(resource.observed_at.replace("Z", "+00:00"))
                age = (now - observation).total_seconds()
                entry = asdict(resource)
                entry["fresh"] = 0 <= age <= max_age_seconds
                entry["age_seconds"] = age
                # A listed resource is not necessarily online, healthy, authorized or verified.
                entry["usable"] = bool(entry["fresh"] and resource.state == "online")
                entry["authorized"] = None
                entry["verified_working"] = None
                results[resource.resource_id] = entry
        return [results[key] for key in sorted(results)]
