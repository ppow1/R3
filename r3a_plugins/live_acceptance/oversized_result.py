"""Acceptance-only provider returning a payload above the 64 KiB module frame."""
from __future__ import annotations


class OversizedResultProvider:
    def invoke(self, arguments: dict, *, context: dict) -> dict:
        return {"payload": "x" * 70000}


def create_provider(configuration: dict) -> OversizedResultProvider:
    return OversizedResultProvider()
