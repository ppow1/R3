"""HR identity classes and protected relationship disclosure contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, FrozenSet


RECORD_CLASSES = frozenset({"RESIDENT", "STEWARD"})
RELATIONSHIP_CLASSIFICATIONS = frozenset({"public", "institutional", "personnel_sensitive", "protected"})


@dataclass(frozen=True)
class InstitutionalIdentity:
    institutional_id: str
    display_name: str
    classification: str
    authority_ref: str

    def __post_init__(self) -> None:
        if not self.institutional_id or not self.display_name or not self.authority_ref:
            raise ValueError("institutional identity and authority reference are required")
        if self.classification not in RECORD_CLASSES:
            raise ValueError("unsupported institutional record classification")


def validate_steward_record(record: dict[str, Any]) -> None:
    """Require a separately classified governance record, never a resident lifecycle."""
    if record.get("classification") != "STEWARD":
        raise ValueError("Steward record must use STEWARD classification")
    if record.get("institutional_id") is None or record.get("authority_ref") is None:
        raise ValueError("Steward identity must be resolved from institutional authority")
    forbidden = {"employment_status", "performance_review", "resident_lifecycle",
                 "character_revision_authority", "personality_adjustment_authority"}
    if forbidden & set(record):
        raise ValueError("Steward record cannot inherit resident or employee lifecycle fields")
    if record.get("identity_write_policy") != "steward_governed_only":
        raise ValueError("Steward identity and authority require Steward-governed writes")


@dataclass(frozen=True)
class ProtectedRelationship:
    relationship_id: str
    parties: tuple[str, str]
    classification: str
    authorized_readers: FrozenSet[str]
    authorized_editors: FrozenSet[str]
    provenance_refs: tuple[str, ...]
    revision: str
    disclosure_rules: dict[str, tuple[str, ...]]
    facts: tuple[dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if not self.relationship_id or len(self.parties) != 2 or self.parties[0] == self.parties[1]:
            raise ValueError("relationship needs two distinct canonical identities")
        if self.classification != "protected":
            raise ValueError("this relationship contract requires protected classification")
        if not self.revision or not self.provenance_refs:
            raise ValueError("relationship revision and provenance are required")
        if not self.authorized_readers or not self.authorized_editors:
            raise ValueError("relationship ACLs must be explicit")
        if not self.authorized_editors <= self.authorized_readers:
            raise ValueError("relationship editors must also be authorized readers")
        for fact in self.facts:
            if not isinstance(fact, dict) or not fact.get("source_refs") or not fact.get("recorded_at"):
                raise ValueError("relationship facts require source references and timestamps")

    def project(self, principal_id: str, *, purpose: str) -> dict[str, Any]:
        """Return only an explicitly authorized projection; denial reveals no relationship data."""
        if principal_id not in self.authorized_readers:
            raise PermissionError("protected relationship access denied")
        permitted = self.disclosure_rules.get(purpose, ())
        return {"relationship_id": self.relationship_id, "classification": self.classification,
                "revision": self.revision, "facts": [fact for fact in self.facts
                if fact.get("disclosure_scope") in permitted]}

    def require_edit(self, principal_id: str) -> None:
        if principal_id not in self.authorized_editors:
            raise PermissionError("protected relationship edit denied")
