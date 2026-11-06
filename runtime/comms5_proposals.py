# R3 CONTROLLED SOURCE
# File: runtime/comms5_proposals.py
# Component: R3-COMMS5-PROPOSAL-ADAPTER
# File Revision: 1.1.0
# Created: 2026-11-06T01:39:36Z
# Created By: Codex GPT-6, acting on Steward instruction
# Purpose: Narrowly submit Grace-authored proposal drafts to Comms5's authoritative draft store.
# Execution Model: Synchronous adapter using the official MCP Python SDK over Streamable HTTP.
# Observability: Only operation name and outcome are exposed; tokens and proposal text are not logged.
# Dependencies: Optional `mcp` v1 SDK; Comms5 submit_steward_seed and seed_status operations.
# Authority: Steward-directed Grace recovery P1; R3 exact write grant plus authenticated Comms5 transport.
# Changed: 2026-11-06T01:39:36Z | GRACE-PROPOSAL-P1 | Codex GPT-6 | Add fixed-operation draft submission adapter.
# Changed: 2026-11-06T01:48:39Z | GRACE-PROPOSAL-P1 | Codex GPT-6 | Reconcile proposal ID from authoritative readback and reject unsupported tool fields.
# Changed: 2026-11-06T01:48:39Z | GRACE-PROPOSAL-P1 | Codex GPT-6 | Derive review/approval reporting from authoritative lifecycle state.
# Changed: 2026-11-06T01:48:39Z | GRACE-PROPOSAL-P1 | Codex GPT-6 | Use the maintained Streamable HTTP client entrypoint.
# Changed: 2026-11-06T01:48:39Z | GRACE-PROPOSAL-P1 | Codex GPT-6 | Document the Comms5 draft byte limit in tool discovery.
# Changed: 2026-11-06T02:15:00Z | GRACE-AUTONOMY-P2 | Codex GPT-6 | Add bounded read-only proposal/objective lifecycle capabilities.
# Supersedes: Revision 1.0.4; adds no proposal approval or work-order mutation.
# Contracts: riverview-comms-contract:5.0; docs/r3-native-tool-contract.md
# Tests: tests/test_comms5_proposals.py; tests/test_proposal_submission_integration.py
# History/Predecessor: New file; no predecessor.
"""A single-operation bridge to Comms5's existing authoritative proposal store."""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit


class ProposalSubmissionError(RuntimeError):
    """A safe, content-free error suitable for the resident journal."""


@dataclass(frozen=True)
class ProposalSubmission:
    proposal_id: str
    seed_id: str
    revision: int | None
    lifecycle_status: str
    persisted: bool
    steward_decision_required: bool
    approval_granted: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "status": "persisted" if self.persisted else "submission_unverified",
            "proposal_id": self.proposal_id,
            "seed_id": self.seed_id,
            "revision": self.revision,
            "lifecycle_status": self.lifecycle_status,
            "persisted": self.persisted,
            "steward_decision_required": self.steward_decision_required,
            "approval_granted": self.approval_granted,
        }


def read_bearer_token(path: str | Path) -> str:
    """Read a service credential without logging it; reject broadly readable files."""
    token_path = Path(path)
    try:
        metadata = token_path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) & 0o077:
            raise ProposalSubmissionError("Comms5 credential file permissions are invalid")
        value = token_path.read_text(encoding="utf-8").strip()
    except ProposalSubmissionError:
        raise
    except OSError:
        raise ProposalSubmissionError("Comms5 credential is unavailable") from None
    if not value or "\n" in value or "\r" in value:
        raise ProposalSubmissionError("Comms5 credential is invalid")
    return value


class Comms5DraftClient:
    """Calls only `submit_steward_seed` and its read-only `seed_status` operation.

    It deliberately does not discover or proxy Comms5's general catalog, approval
    operations, objective promotion, or work-order operations.
    """

    MAX_DRAFT_BYTES = 8000

    def __init__(
        self,
        url: str,
        bearer_token: str,
        *,
        classification: str = "internal",
        client_id: str = "r3-resident-runtime",
        client_name: str = "R3 resident runtime",
        client_type: str = "local_ai",
        client_version: str = "1.0",
        call_tool: Callable[[str, dict], Any] | None = None,
    ):
        parsed = urlsplit(url)
        local_http = parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost", "::1")
        if ((parsed.scheme != "https" and not local_http) or not parsed.netloc
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("Comms5 MCP endpoint must be HTTPS or loopback HTTP")
        if not bearer_token or any(ch in bearer_token for ch in "\r\n"):
            raise ValueError("Comms5 bearer credential is invalid")
        if classification not in ("internal", "river"):
            raise ValueError("Unsupported Comms5 classification")
        self.url = url
        self.bearer_token = bearer_token
        self.classification = classification
        self.client_id = client_id
        self.client_name = client_name
        self.client_type = client_type
        self.client_version = client_version
        self._call_tool = call_tool or self._mcp_call_tool

    async def _mcp_call_tool(self, operation: str, arguments: dict) -> Any:
        # Import lazily so deployments without this optional integration remain
        # operational until the narrow Comms5 adapter is explicitly configured.
        import httpx
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client

        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        async with httpx.AsyncClient(headers=headers) as http_client:
            async with streamable_http_client(self.url, http_client=http_client) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await session.call_tool(operation, arguments=arguments)

    def _call(self, operation: str, arguments: dict) -> dict:
        try:
            response = self._call_tool(operation, arguments)
            if asyncio.iscoroutine(response):
                response = asyncio.run(response)
        except ProposalSubmissionError:
            raise
        except Exception:
            raise ProposalSubmissionError("Comms5 operation failed; outcome must be reconciled") from None
        if getattr(response, "isError", False):
            raise ProposalSubmissionError("Comms5 rejected the proposal operation")
        if isinstance(response, dict):
            data = response
        else:
            structured = getattr(response, "structuredContent", None)
            if isinstance(structured, dict):
                data = structured
            else:
                parts = getattr(response, "content", ())
                data = None
                for part in parts:
                    text = getattr(part, "text", None)
                    if isinstance(text, str):
                        try:
                            parsed = json.loads(text)
                        except (ValueError, TypeError):
                            continue
                        if isinstance(parsed, dict):
                            data = parsed
                            break
        if not isinstance(data, dict) or data.get("executed") is False:
            raise ProposalSubmissionError("Comms5 did not confirm the proposal operation")
        if data.get("status") not in (None, "available", "ok", "success", "submitted", "created"):
            raise ProposalSubmissionError("Comms5 returned an unsuccessful proposal state")
        return data

    @staticmethod
    def _idempotency_key(principal: str, correlation_id: str) -> str:
        digest = hashlib.sha256((principal + "\0" + correlation_id).encode("utf-8")).hexdigest()
        return "r3-proposal-" + digest

    def submit(self, proposal_text: str, *, principal: str, correlation_id: str) -> dict[str, object]:
        if not isinstance(proposal_text, str) or not proposal_text.strip():
            raise ProposalSubmissionError("Proposal draft must contain text")
        if len(proposal_text.encode("utf-8")) > self.MAX_DRAFT_BYTES:
            raise ProposalSubmissionError("Proposal draft exceeds Comms5's 8000-byte limit")
        if not isinstance(principal, str) or not re.fullmatch(r"resident:[A-Za-z0-9_.:-]+", principal):
            raise ProposalSubmissionError("Authenticated R3 resident identity is invalid")
        if not isinstance(correlation_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,200}", correlation_id):
            raise ProposalSubmissionError("Tool correlation identifier is invalid")

        seed_id = None
        proposal_id = None
        revision = None
        lifecycle_status = "UNKNOWN"
        try:
            submitted = self._call("submit_steward_seed", {
                "authenticated_principal": principal,
                "client_id": self.client_id,
                "client_name": self.client_name,
                "client_type": self.client_type,
                "client_version": self.client_version,
                "protocol_version": "riverview-comms-contract:5.0",
                "correlation_id": correlation_id,
                "classification": self.classification,
                "seed_text": proposal_text,
                "idempotency_key": self._idempotency_key(principal, correlation_id),
            })
            seed_id = self._record_id(submitted, "seed_id", "record_id", "proposal_id")
            submitted_proposal_id = submitted.get("proposal_id")
            proposal_id = (submitted_proposal_id if isinstance(submitted_proposal_id, str)
                           and submitted_proposal_id else seed_id)
            revision = self._revision(submitted)
            lifecycle_status = self._status(submitted) or lifecycle_status
        except ProposalSubmissionError:
            raise

        try:
            readback = self._call("seed_status", {"seed_id": seed_id})
            readback_proposal = self._record_id(readback, "proposal_id", "record_id", "seed_id")
            if submitted_proposal_id and readback_proposal != submitted_proposal_id:
                raise ProposalSubmissionError("Comms5 proposal readback did not match the submitted record")
            proposal_id = readback_proposal
            revision = self._revision(readback) or revision
            lifecycle_status = self._status(readback) or lifecycle_status
            persisted = True
        except ProposalSubmissionError:
            # The write may have succeeded. Preserve the identifier and report the
            # ambiguous readback without encouraging a new-key retry.
            return {
                "status": "submission_readback_unverified",
                "proposal_id": proposal_id,
                "seed_id": seed_id,
                "revision": revision,
                "lifecycle_status": lifecycle_status,
                "persisted": False,
                "approval_granted": False,
                "reconcile_before_retry": True,
            }
        terminal_states = {"APPROVED", "WORK_ORDER_CREATED", "COMPLETED", "CANCELLED", "SUPERSEDED"}
        approval_states = {"APPROVED", "WORK_ORDER_CREATED", "COMPLETED"}
        return ProposalSubmission(
            proposal_id=proposal_id,
            seed_id=seed_id,
            revision=revision,
            lifecycle_status=lifecycle_status,
            persisted=persisted,
            steward_decision_required=lifecycle_status not in terminal_states,
            approval_granted=lifecycle_status in approval_states,
        ).as_dict()

    @staticmethod
    def _status_metadata(data: dict, identifier_field: str, identifier: str) -> dict[str, object]:
        """Return lifecycle identifiers and states without forwarding protected content."""
        safe_fields = {
            "status", "lifecycle_status", "revision", "content_sha256",
            "specification_id", "specification_revision", "specification_sha256",
            "objective_id", "objective_status", "promotion_status",
            "authority_id", "work_order_id", "work_order_status",
            "assignment_id", "assignment_status", "verification_status",
            "decision", "steward_attention_required", "independently_accepted",
        }
        result: dict[str, object] = {
            identifier_field: identifier,
            "available": True,
        }
        for source in (data, *(value for value in data.values() if isinstance(value, dict))):
            for key in safe_fields:
                if key == "status" and source is not data:
                    continue
                value = source.get(key)
                if isinstance(value, (str, bool, int)):
                    if isinstance(value, str) and len(value) > 256:
                        continue
                    result[key] = value
        return result

    def proposal_status(self, seed_id: str) -> dict[str, object]:
        if not isinstance(seed_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,200}", seed_id):
            raise ProposalSubmissionError("Comms5 seed identifier is invalid")
        data = self._call("seed_status", {"seed_id": seed_id})
        returned_id = self._record_id(data, "seed_id", "proposal_id", "record_id")
        if returned_id != seed_id and data.get("seed_id") != seed_id:
            raise ProposalSubmissionError("Comms5 status did not match the requested seed")
        return self._status_metadata(data, "seed_id", seed_id)

    def objective_status(self, objective_id: str) -> dict[str, object]:
        if not isinstance(objective_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,200}", objective_id):
            raise ProposalSubmissionError("Comms5 objective identifier is invalid")
        data = self._call("objective_status", {"objective_id": objective_id})
        objective = data.get("objective")
        returned_id = objective.get("objective_id") if isinstance(objective, dict) else data.get("objective_id")
        if returned_id != objective_id:
            raise ProposalSubmissionError("Comms5 status did not match the requested objective")
        result = self._status_metadata(data, "objective_id", objective_id)
        if isinstance(objective, dict):
            result["lifecycle_status"] = objective.get("state")
            result["revision"] = objective.get("revision")
            assignment_id = objective.get("assignment_id")
            if isinstance(assignment_id, str):
                result["assignment_id"] = assignment_id
        for key, source in (("assignment", data.get("assignment")),
                             ("verification", data.get("verification"))):
            if isinstance(source, dict):
                state = source.get("state") or source.get("status") or source.get("decision")
                if isinstance(state, str):
                    result[f"{key}_status"] = state
                if key == "assignment":
                    assignment_id = source.get("id")
                    if isinstance(assignment_id, str):
                        result["assignment_id"] = assignment_id
                    for field in ("workflow_id", "workflow_step", "correlation_id"):
                        value = source.get(field)
                        if isinstance(value, str) and len(value) <= 256:
                            result[field] = value
                elif isinstance(source.get("verifier_revision"), (str, int)):
                    result["verifier_revision"] = source["verifier_revision"]
        steps = data.get("steps")
        if isinstance(steps, list):
            result["steps"] = [
                {key: item[key] for key in ("step_id", "order", "state", "assignment_id", "dispatch_count")
                 if isinstance(item.get(key), (str, int)) and not isinstance(item.get(key), bool)}
                for item in steps[:32]
                if isinstance(item, dict)
            ]
        intents = data.get("execution_intents")
        if isinstance(intents, list):
            result["execution_intents"] = [
                {key: item[key] for key in (
                    "assignment_id", "worker_id", "capability", "status", "attempt_id", "failure_class"
                ) if isinstance(item.get(key), str) and len(item[key]) <= 256}
                for item in intents[:32]
                if isinstance(item, dict)
            ]
            statuses = [item.get("status") for item in result["execution_intents"]]
            if statuses:
                result["execution_status"] = statuses[-1]
        return result

    @staticmethod
    def _record_id(data: dict, *keys: str) -> str:
        for key in keys:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value
        raise ProposalSubmissionError("Comms5 did not return a durable proposal identifier")

    @staticmethod
    def _revision(data: dict) -> int | None:
        value = data.get("revision")
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    @staticmethod
    def _status(data: dict) -> str | None:
        value = data.get("lifecycle_status")
        if value is None:
            proposal = data.get("proposal")
            if isinstance(proposal, dict):
                value = proposal.get("lifecycle_status")
        return value if isinstance(value, str) and value else None


def proposal_submission_capability(client: Comms5DraftClient):
    from runtime.capabilities import Capability

    def submit(params, context):
        if set(params) != {"proposal_text"}:
            raise ProposalSubmissionError("Proposal operation received unsupported fields")
        return client.submit(
            params["proposal_text"], principal=context.principal,
            correlation_id=context.correlation_id,
        )

    return Capability(
        name="r3.proposal.submit",
        action="proposal.draft.submit",
        description=("Persist a completed proposal draft of at most 8000 UTF-8 bytes in the authoritative "
                     "Comms5 proposal store. This creates a draft only; it does not approve, promote, or dispatch work."),
        parameters={
            "type": "object",
            "properties": {"proposal_text": {"type": "string", "minLength": 1}},
            "required": ["proposal_text"],
            "additionalProperties": False,
        },
        contextual_executor=submit,
        read_only=False,
        resource_ref="comms5:steward-proposals",
        scope_ref="institution:proposal-drafts",
    )


def proposal_status_capability(client: Comms5DraftClient):
    from runtime.capabilities import Capability

    def status(params, _context):
        if set(params) != {"seed_id"}:
            raise ProposalSubmissionError("Proposal status received unsupported fields")
        return client.proposal_status(params["seed_id"])

    return Capability(
        name="r3.proposal.status",
        action="proposal.status.read",
        description="Read authoritative Comms5 proposal lifecycle metadata by seed ID; protected content is omitted.",
        parameters={
            "type": "object",
            "properties": {"seed_id": {"type": "string", "minLength": 1}},
            "required": ["seed_id"],
            "additionalProperties": False,
        },
        contextual_executor=status,
        read_only=True,
        resource_ref="comms5:steward-proposals",
        scope_ref="institution:proposal-drafts",
    )


def objective_status_capability(client: Comms5DraftClient):
    from runtime.capabilities import Capability

    def status(params, _context):
        if set(params) != {"objective_id"}:
            raise ProposalSubmissionError("Objective status received unsupported fields")
        return client.objective_status(params["objective_id"])

    return Capability(
        name="r3.objective.status",
        action="objective.status.read",
        description=("Read authoritative Comms5 objective, assignment, execution, and independent verification "
                     "states by objective ID; protected content is omitted."),
        parameters={
            "type": "object",
            "properties": {"objective_id": {"type": "string", "minLength": 1}},
            "required": ["objective_id"],
            "additionalProperties": False,
        },
        contextual_executor=status,
        read_only=True,
        resource_ref="comms5:institutional-objectives",
        scope_ref="institution:objective-status",
    )
