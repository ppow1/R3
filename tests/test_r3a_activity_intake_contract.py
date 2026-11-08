"""R3A generic activity-intake envelope contract tests."""
import copy
import json
from pathlib import Path

import pytest

from r3a_runtime.capability_contracts import CapabilityContractError, validate_json


SCHEMA = json.loads((Path(__file__).parents[1] / "r3a_runtime" / "schemas" /
                     "activity-intake.v1.schema.json").read_text(encoding="utf-8"))


def valid_notification_intake():
    digest = "a" * 64
    return {
        "contract_id": "r3a.activity-intake.v1",
        "contract_version": "1.0.0",
        "intake_id": "notification:r3a.institution-events:event-123",
        "correlation_id": "correlation-123",
        "source": {
            "source_id": "r3a.institution-events",
            "event_id": "event-123",
            "revision": "1",
            "idempotency_key": "notification:r3a.institution-events:event-123",
            "occurred_at": "2026-11-08T00:00:00Z",
            "received_at": "2026-11-08T00:00:01Z",
            "payload_ref": "r3a.institution_events/event-123",
            "payload_sha256": digest,
            "causation_id": "event-123"
        },
        "activity": {
            "activity_type": "grace.objective",
            "task_class": "objective_reasoning",
            "objective": "Review the event and cite evidence.",
            "input": {"notification": {"source_id": "r3a.institution-events"}},
            "evidence": [{
                "source_id": "notification:r3a.institution-events:event-123",
                "source_ref": "r3a.institution_events/event-123",
                "sha256": digest,
                "provenance": "r3a.institution-events"
            }]
        },
        "provenance": {
            "module_id": "r3a.notification-source",
            "module_version": "1.0.0",
            "artifact_sha256": digest,
            "configuration_revision": "sha256:config"
        },
        "lifecycle_projection": {
            "received": "grace.notification.received",
            "actionable": "grace.notification.actionable",
            "acknowledged": "grace.notification.acknowledged",
            "resolved": "grace.notification.resolved",
            "blocked": "grace.notification.blocked"
        }
    }


def test_notification_facts_fit_generic_activity_intake_contract():
    validate_json(valid_notification_intake(), SCHEMA)


@pytest.mark.parametrize("mutation", [
    lambda value: value["source"].update(idempotency_key=""),
    lambda value: value["source"].update(payload_sha256="not-a-digest"),
    lambda value: value["provenance"].update(module_version="latest"),
    lambda value: value["lifecycle_projection"].update(resolved="not-an-event-name"),
    lambda value: value.update(unreviewed_authority=True),
])
def test_invalid_or_authority_expanding_intake_is_rejected(mutation):
    intake = copy.deepcopy(valid_notification_intake())
    mutation(intake)
    with pytest.raises(CapabilityContractError):
        validate_json(intake, SCHEMA)
