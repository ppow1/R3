# R3 CONTROLLED SOURCE
# File: runtime/proposal_gateway_adapter.py
# Component: R3-INSTITUTIONAL-PROPOSAL-GATEWAY-ADAPTER
# File Revision: 1.1.0
# Created: Unknown (legacy; exact creation time not independently established)
# Created By: Unknown (legacy)
# Purpose: Register resident proposal draft/read operations on the existing HR-enabled broker.
# Execution Model: Governed broker capability adapter with exact HR identity resolution.
# Observability: Broker grant/audit and write idempotency; institutional registry owns policy decision.
# Dependencies: GovernedToolGateway; HR identity crosswalk; InstitutionalProposalClient.
# Authority: Proposal authorization is delegated to the existing institutional registry; no parallel grants.
# Changed: 2026-11-06T23:06:45Z | GRACE-AUTHORITY-ARCH-001 | Codex GPT-6 | Require HR principal mapping and mark registry as owning authority.
# Supersedes: Git predecessor behavior requiring a separate R3 proposal grant.
# Contracts: docs/r3-native-tool-contract.md; docs/architecture/RESIDENT_AUTHORITY_AND_CAPABILITIES.md.
# Tests: tests/test_proposal_gateway_adapter.py; tests/test_internal_proposal_tool_integration.py.
# History/Predecessor: Git blob 43d35fa1ee8d0f77d29a38932db93e9f6ad40d16 at cb162499a5ae94b801cbdbf9e5aa2dcd4c75ebaf.
"""Add the internal proposal operations to the existing governed R3 broker.

The deployed broker has HR and operational tools registered through
GovernedToolGateway. This adapter is additive, resolves identity from the
authoritative HR crosswalk, and delegates policy authorization to the existing
institutional proposal registry. R3 credentials, audit, and write-idempotency
remain in the broker; no duplicate proposal-specific R3 grant is required.
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
    authorization_mode: str = "authoritative-service"
    authority_source: str = "riverview.institutional-proposal-registry"


def _scope_property() -> dict:
    return {"type": "string", "enum": [SCOPE]}


def register_internal_proposal_tools(gateway, client, *, hr_database=None) -> None:
    """Register draft-write and proposal-read; the institution decides policy."""
    if hr_database is None:
        raise ValueError("Authoritative HR database is required for proposal identity resolution")

    def resolve_principal(r3_principal):
        from runtime.hr_identity_association import resolve_authority_principal
        return resolve_authority_principal(hr_database, r3_principal)
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
        principal = resolve_principal(context.principal)
        return client.submit(params["content"], principal=principal,
                             correlation_id=context.correlation_id)

    def read(params, context):
        if set(params) != {"scope_ref", "proposal_id"} or params["scope_ref"] != SCOPE:
            raise ValueError("Proposal read scope or parameters are invalid")
        principal = resolve_principal(context.principal)
        return client.proposal_status(params["proposal_id"], expected_principal=principal)

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
