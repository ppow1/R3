"""Authenticated R3 adapter to Riverview's existing internal proposal registry."""
from __future__ import annotations

import hashlib
import json
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit


class InstitutionalProposalError(RuntimeError):
    """Safe, content-free failure from the internal proposal registry."""


def read_resident_credential(path: str | Path) -> str:
    token_path = Path(path)
    try:
        metadata = token_path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) & 0o077:
            raise InstitutionalProposalError("Institutional credential file permissions are invalid")
        value = token_path.read_text(encoding="ascii").strip()
    except InstitutionalProposalError:
        raise
    except (OSError, UnicodeError):
        raise InstitutionalProposalError("Institutional resident credential is unavailable") from None
    if not value or "\n" in value or "\r" in value:
        raise InstitutionalProposalError("Institutional resident credential is invalid")
    return value


@dataclass(frozen=True)
class InstitutionalProposalClient:
    url: str
    resident_credential: str
    timeout: float = 5.0

    def __post_init__(self):
        parsed = urlsplit(self.url)
        local_http = parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        if ((parsed.scheme != "https" and not local_http) or not parsed.netloc
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("Institutional proposal endpoint must be HTTPS or loopback HTTP")
        if not self.resident_credential or "\n" in self.resident_credential:
            raise ValueError("Institutional resident credential is invalid")

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        data = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
        request = Request(self.url.rstrip("/") + path, data=data, method=method,
            headers={"Authorization": f"Bearer {self.resident_credential}",
                     **({"Content-Type": "application/json"} if data is not None else {})})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read(65536))
        except HTTPError as exc:
            if exc.code in {401, 403, 404, 409}:
                raise InstitutionalProposalError("Internal proposal operation was denied or conflicted") from None
            raise InstitutionalProposalError("Internal proposal service is unavailable") from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise InstitutionalProposalError("Internal proposal service is unavailable") from None
        if not isinstance(result, dict):
            raise InstitutionalProposalError("Internal proposal response is invalid")
        return result

    @staticmethod
    def _idempotency(principal: str, correlation_id: str) -> str:
        return "r3-proposal-" + hashlib.sha256((principal + "\0" + correlation_id).encode()).hexdigest()

    def submit(self, content: dict, *, principal: str, correlation_id: str) -> dict:
        if not isinstance(principal, str) or not re.fullmatch(r"resident:[A-Za-z0-9_.:-]+", principal):
            raise InstitutionalProposalError("Authenticated R3 resident identity is invalid")
        if not isinstance(correlation_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,200}", correlation_id):
            raise InstitutionalProposalError("Tool correlation identifier is invalid")
        result = self._request("POST", "", {"content": content,
            "correlation_id": correlation_id, "expected_principal": principal,
            "idempotency_key": self._idempotency(principal, correlation_id)})
        if (result.get("persistence") != "durably_persisted" or
                result.get("readback_verified") is not True or
                result.get("author_principal_id") != principal or
                result.get("lifecycle_status") != "DRAFT"):
            raise InstitutionalProposalError("Internal proposal persistence was not verified")
        return {"status": "persisted", "proposal_id": result["proposal_id"],
            "revision": result["revision"], "content_sha256": result["content_sha256"],
            "lifecycle_status": result["lifecycle_status"], "persisted": True,
            "steward_decision_required": True, "approval_granted": False,
            "author_principal_id": result["author_principal_id"],
            "correlation_id": result["correlation_id"]}

    def proposal_status(self, proposal_id: str) -> dict:
        if not isinstance(proposal_id, str) or not re.fullmatch(r"proposal:[0-9a-f-]{36}", proposal_id):
            raise InstitutionalProposalError("Institutional proposal ID is invalid")
        record = self._request("GET", "/" + proposal_id)
        proposal, revision = record.get("proposal"), record.get("revision")
        if (not isinstance(proposal, dict) or not isinstance(revision, dict)
                or proposal.get("proposal_id") != proposal_id):
            raise InstitutionalProposalError("Internal proposal readback did not match the requested record")
        return {"proposal_id": proposal_id, "revision": revision.get("revision"),
            "content_sha256": revision.get("content_sha256"),
            "lifecycle_status": proposal.get("lifecycle_status"), "persisted": True,
            "author_principal_id": proposal.get("created_by"),
            "approval_granted": proposal.get("lifecycle_status") in {"APPROVED", "PROMOTED"}}


def proposal_submission_capability(client: InstitutionalProposalClient):
    from runtime.capabilities import Capability

    def submit(params, context):
        if set(params) != {"content"}:
            raise InstitutionalProposalError("Proposal operation received unsupported fields")
        return client.submit(params["content"], principal=context.principal,
            correlation_id=context.correlation_id)

    fields = {
        "title": {"type": "string", "minLength": 1, "maxLength": 200},
        "summary": {"type": "string", "minLength": 1, "maxLength": 1000},
        "objective": {"type": "string", "minLength": 1, "maxLength": 4000},
        "scope": {"type": "string", "minLength": 1, "maxLength": 4000},
        "proposed_approach": {"type": "string", "minLength": 1, "maxLength": 6000},
        "constraints": {"type": "array", "items": {"type": "string", "maxLength": 1000}, "maxItems": 24},
        "acceptance_criteria": {"type": "array", "items": {"type": "string", "maxLength": 1000}, "minItems": 1, "maxItems": 24},
        "tags": {"type": "array", "items": {"type": "string", "maxLength": 64}, "maxItems": 24},
    }
    return Capability(name="r3.proposal.submit", action="proposal.draft.submit",
        description="Create a durable draft in Riverview's internal institutional proposal registry. It cannot approve or promote the proposal.",
        parameters={"type": "object", "properties": {"content": {
            "type": "object", "properties": fields, "required": list(fields),
            "additionalProperties": False}}, "required": ["content"], "additionalProperties": False},
        contextual_executor=submit, read_only=False,
        resource_ref="riverview:institutional-proposals", scope_ref="institution:proposal-drafts")


def proposal_status_capability(client: InstitutionalProposalClient):
    from runtime.capabilities import Capability
    def status(params, _context):
        if set(params) != {"proposal_id"}:
            raise InstitutionalProposalError("Proposal status received unsupported fields")
        return client.proposal_status(params["proposal_id"])
    return Capability(name="r3.proposal.status", action="proposal.status.read",
        description="Read the authenticated resident's authoritative institutional proposal state.",
        parameters={"type": "object", "properties": {
            "proposal_id": {"type": "string", "minLength": 1}},
            "required": ["proposal_id"], "additionalProperties": False},
        contextual_executor=status, read_only=True,
        resource_ref="riverview:institutional-proposals", scope_ref="institution:proposal-drafts")
