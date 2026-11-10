"""
R3 CONTROLLED SOURCE
File: tests/r3a_activity_handler_interop_provider.py
Component: R3A-ACTIVITY-HANDLER-INTEROP-FIXTURE
File Revision: 1.0.0
Created: 2026-11-10T02:02:46Z
Created By: Codex GPT-6
Purpose: Provide a deterministic disposable provider artifact for the shared handler manifest fixture.
Execution Model: Existing capability-provider worker calls invoke with a typed activity payload.
Observability: Returns deterministic typed result, progress, and checkpoint values.
Dependencies: Existing r3a.capability-provider.v1 invoke contract.
Authority: AD-024 interop fixture only; grants and lifecycle remain CME-owned.
Changed: 2026-11-10T02:02:46Z | R3A-MODULAR-PLUGINS-46 | Codex GPT-6 | Add an executable deterministic billing-handler provider artifact for the shared fixture.
Supersedes: None.
Contracts: r3a.activity-handler.v1; r3a.capability-provider.v1.
Tests: tests/test_r3a_module_extensions.py.
History/Predecessor: New fixture artifact.
"""
from __future__ import annotations

from typing import Any


class InvoiceReviewProvider:
    def __init__(self, configuration: dict[str, Any]):
        if configuration != {"mode": "fixture"}:
            raise ValueError("interop fixture configuration is invalid")

    def invoke(self, arguments: dict[str, Any], *, context: dict[str, Any]) -> dict[str, Any]:
        request = arguments.get("input", arguments)
        invoice_id = request["invoice_id"]
        return {
            "outcome": "completed",
            "invoice_id": invoice_id,
            "status": "validated",
            "progress": {"phase": "completed", "completed": 1},
            "checkpoint": {"cursor": 1},
        }


def create_provider(configuration: dict[str, Any]) -> InvoiceReviewProvider:
    return InvoiceReviewProvider(configuration)
