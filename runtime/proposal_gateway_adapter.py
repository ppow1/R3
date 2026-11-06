"""Add the internal proposal operations to the existing governed R3 broker.

The deployed broker has HR and operational tools registered through
GovernedToolGateway. This adapter is additive and intentionally uses that same
credential, grant, audit, and write-idempotency boundary.
"""
from __future__ import annotations

from dataclasses import dataclass


RESOURCE = "riverview:institutional-proposals"
SCOPE = "institution:proposal-drafts"


@dataclass(frozen=True)
class ProposalGatewayCapability:
    name: str
    resource_id: str
    action: str
    operation: str
    description: str
    parameters: dict
    executor: object


def _scope_property() -> dict:
    return {"type": "string", "enum": [SCOPE]}


def register_internal_proposal_tools(gateway, client, *, hr_database=None) -> None:
    """Register exactly draft-write and proposal-read; issue no grants."""
    content_fields = {
        "title": {"type": "string", "minLength": 1, "maxLength": 200},
        "summary": {"type": "string", "minLength": 1, "maxLength": 1000},
        "objective": {"type": "string", "minLength": 1, "maxLength": 4000},
        "scope": {"type": "string", "minLength": 1, "maxLength": 4000},
        "proposed_approach": {"type": "string", "minLength": 1, "maxLength": 6000},
        "constraints": {"type": "array", "items": {"type": "string", "maxLength": 1000}, "maxItems": 24},
        "acceptance_criteria": {"type": "array", "items": {"type": "string", "maxLength": 1000}, "minItems": 1, "maxItems": 24},
        "tags": {"type": "array", "items": {"type": "string", "maxLength": 64}, "maxItems": 24},
    }

    def submit(params, context):
        if set(params) != {"scope_ref", "content"} or params["scope_ref"] != SCOPE:
            raise ValueError("Proposal draft scope or parameters are invalid")
        principal = context.principal
        if hr_database is not None:
            from runtime.hr_identity_association import resolve_authority_principal
            principal = resolve_authority_principal(hr_database, context.principal)
        return client.submit(params["content"], principal=principal,
                             correlation_id=context.correlation_id)

    def read(params, context):
        if set(params) != {"scope_ref", "proposal_id"} or params["scope_ref"] != SCOPE:
            raise ValueError("Proposal read scope or parameters are invalid")
        return client.proposal_status(params["proposal_id"])

    gateway.register(ProposalGatewayCapability(
        name="r3.proposal.submit",
        resource_id=RESOURCE,
        action="proposal.draft.submit",
        operation="write",
        description=("Create a durable draft in Riverview's internal proposal registry. "
                     "This operation cannot approve or promote it."),
        parameters={"type": "object", "properties": {
            "scope_ref": _scope_property(),
            "content": {"type": "object", "properties": content_fields,
                        "required": list(content_fields), "additionalProperties": False}},
            "required": ["scope_ref", "content"], "additionalProperties": False},
        executor=submit,
    ))
    gateway.register(ProposalGatewayCapability(
        name="r3.proposal.status",
        resource_id=RESOURCE,
        action="proposal.status.read",
        operation="read",
        description="Read the authenticated resident's authoritative proposal lifecycle state.",
        parameters={"type": "object", "properties": {
            "scope_ref": _scope_property(),
            "proposal_id": {"type": "string", "minLength": 1}},
            "required": ["scope_ref", "proposal_id"], "additionalProperties": False},
        executor=read,
    ))
