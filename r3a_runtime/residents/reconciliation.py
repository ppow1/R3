"""Read-only HR/directory reconciliation; never provisions from an incomplete view."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class ReconciliationItem:
    institutional_id: str
    state: str
    evidence: tuple[str, ...]


def reconcile_records(directory: dict[str, Any], hr_ids: Iterable[str],
                      dossier_ids: Iterable[str], *, confirmed_crosswalk: dict[str, str] | None = None,
                      credential_ids: Iterable[str] = (), office_binding_ids: Iterable[str] = (),
                      credential_states: dict[str, str] | None = None,
                      access_state: str = "authorized",
                      synchronization_state: str = "healthy",
                      hr_availability: str = "measured",
                      hr_access_state: str = "authorized") -> tuple[ReconciliationItem, ...]:
    """Classify observed records while treating unavailable/projection data as unknown.

    The function is intentionally a planner only. It does not create, update, or
    delete HR rows, bindings, credentials, or dossiers.
    """
    source = directory.get("source", {}) if isinstance(directory, dict) else {}
    if access_state == "insufficient":
        return (ReconciliationItem("*", "directory_access_insufficient", ("directory response cannot establish absence",)),)
    if hr_access_state == "insufficient":
        return (ReconciliationItem("*", "hr_access_insufficient", ("HR response cannot establish record absence",)),)
    if hr_availability != "measured":
        return (ReconciliationItem("*", "hr_source_unavailable", (hr_availability,)),)
    if synchronization_state != "healthy":
        return (ReconciliationItem("*", "directory_synchronization_unhealthy", (synchronization_state,)),)
    if source.get("availability") != "measured" or source.get("freshness") != "fresh":
        return (ReconciliationItem("*", "authoritative_source_unavailable", (
            str(source.get("error") or "directory snapshot not fresh and measured"),
        )),)
    residents = directory.get("residents")
    if not isinstance(residents, list):
        return (ReconciliationItem("*", "directory_projection_invalid", ("residents is not a list",)),)
    hr = set(hr_ids)
    dossiers = set(dossier_ids)
    credentials = set(credential_ids)
    bindings = set(office_binding_ids)
    credential_states = dict(credential_states or {})
    crosswalk = dict(confirmed_crosswalk or {})
    if (any(not isinstance(directory_id, str) or not directory_id for directory_id in crosswalk)
            or any(not isinstance(hr_id, str) or not hr_id for hr_id in crosswalk.values())
            or len(set(crosswalk.values())) != len(crosswalk)):
        return (ReconciliationItem("*", "identity_crosswalk_conflict", (
            "crosswalk IDs must be nonempty and one-to-one",
        )),)
    observed: dict[str, list[dict[str, Any]]] = {}
    for resident in residents:
        rid = resident.get("resident_id") if isinstance(resident, dict) else None
        if not isinstance(rid, str) or not rid:
            return (ReconciliationItem("*", "directory_projection_invalid", ("resident ID missing",)),)
        observed.setdefault(rid, []).append(resident)
    directory_to_hr = crosswalk
    hr_to_directory = {hr_id: directory_id for directory_id, hr_id in directory_to_hr.items()}
    mapped_hr = set(hr_to_directory)
    ids = sorted(hr | dossiers | credentials | bindings)
    result: list[ReconciliationItem] = []
    for rid in ids:
        directory_id = hr_to_directory.get(rid)
        rows = observed.get(directory_id, []) if directory_id is not None else []
        if rid in hr and rid not in mapped_hr:
            result.append(ReconciliationItem(rid, "hr_identity_crosswalk_missing", tuple(x for x, present in (
                ("hr", True), ("dossier", rid in dossiers), ("credential", rid in credentials),
                ("office_binding", rid in bindings),
            ) if present)))
            continue
        if len(rows) > 1:
            state = "directory_binding_ambiguous"
        elif rows and rid not in hr:
            state = "missing_hr_record_candidate_requires_resolution"
        elif rows and rid not in dossiers:
            state = "dossier_missing"
        elif rows and credential_states.get(rid) == "invalid":
            state = "resident_credential_invalid"
        elif rows and credential_states.get(rid) == "insufficient_access":
            state = "resident_credential_access_insufficient"
        elif rows and (rid not in credentials and credential_states.get(rid) != "valid"):
            state = "resident_credential_missing_or_unverified"
        elif not rows and rid in hr:
            state = ("directory_projection_incomplete" if source.get("potentially_truncated")
                     else "office_binding_missing_or_occupant_unregistered")
        elif not rows and rid in dossiers:
            state = "dossier_without_directory_projection"
        elif not rows and rid in credentials:
            state = "credential_without_directory_projection"
        elif not rows and rid in bindings:
            state = "binding_without_directory_projection"
        else:
            state = "matched_observed_records"
        evidence = tuple(x for x, present in (
            ("directory", bool(rows)), ("hr", rid in hr), ("dossier", rid in dossiers),
            ("credential", rid in credentials), ("office_binding", rid in bindings),
            ("confirmed_crosswalk", rid in hr_to_directory),
        ) if present)
        result.append(ReconciliationItem(rid, state, evidence))
    # Preserve directory-only occupants as unresolved evidence. A matching
    # spelling or equal ID never establishes HR identity equivalence.
    for directory_id in sorted(set(observed) - set(directory_to_hr)):
        rows = observed[directory_id]
        state = "directory_binding_ambiguous" if len(rows) > 1 else "directory_identity_crosswalk_missing"
        result.append(ReconciliationItem(f"directory_id:{directory_id}", state, ("directory",)))
    return tuple(sorted(result, key=lambda item: item.institutional_id))
