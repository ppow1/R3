"""Versioned, provider-neutral resident dossier contracts."""

# R3 CONTROLLED SOURCE
# File: r3a_runtime/residents/__init__.py
# Component: R3A-RESIDENT-DOSSIERS
# File Revision: 1.0.0
# Created: 2026-11-08 UTC (exact time not independently captured)
# Created By: Codex GPT-6
# Purpose: Public package interface for resident dossier loading and composition.
# Execution Model: Imported by R3A runtime clients; no process or authority granted.
# Observability: Validation and provenance metadata are returned by package APIs.
# Dependencies: Python standard library.
# Authority: Steward directive, R3 Charter Revision 2, R3A capability boundaries.
# Changed: 2026-11-08 UTC (exact time not independently captured) | CHARACTER-ARCHITECTURE | Codex GPT-6 | Create provider-neutral resident dossier package.
# Supersedes: None
# Contracts: r3a.resident.dossier.v1; r3a.resident.epistemic-spans.v1
# Tests: tests/test_r3a_resident_dossiers.py
# History/Predecessor: New file.

from .repository import DossierRepository, DossierError, RevisionConflict
from .prompts import compose_prompt, PromptComposition
from .validation import validate_dossier, DossierValidationError
from .configuration import resolve_personality, runtime_binding
from .state_contracts import (validate_emotional_state, validate_memory_entry,
                              validate_relationship, append_memory_correction,
                              evolve_relationship, transition_emotional_state)
from .legacy_import import extract_legacy_hr_candidates
from .reconciliation import reconcile_records, ReconciliationItem
from .institutional_records import (InstitutionalIdentity, ProtectedRelationship,
                                    validate_steward_record)
from .workflow import (CharacterRevision, CharacterGovernance, transition_revision)
from .runtime_context import (RuntimePrincipal, load_runtime_context,
                              validate_runtime_character_context)
from .governance import (GovernedActor, GovernancePolicy, authorize_workflow_action)
from .postgres_repository import PostgresDossierRepository
from .workflow_service import CharacterWorkflowService
from .hr_gateway import HRCapabilityIdentityResolver
from .r3_authority_adapter import R3CapabilityGrantAdapter
from .identity_association import validate_identity_association
from .approved_context import (ApprovedCharacterContextProvider,
                               project_context_for_sink, validate_approved_context)
from .hr_association import (HRPrincipalAssociationAdapter,
                             validate_association_evidence)

__all__ = [
    "DossierRepository", "DossierError", "RevisionConflict",
    "PromptComposition", "compose_prompt", "validate_dossier",
    "DossierValidationError", "resolve_personality", "runtime_binding",
    "validate_memory_entry", "validate_relationship", "validate_emotional_state",
    "append_memory_correction", "evolve_relationship", "transition_emotional_state",
    "extract_legacy_hr_candidates",
    "reconcile_records", "ReconciliationItem", "InstitutionalIdentity",
    "ProtectedRelationship", "validate_steward_record", "CharacterRevision",
    "CharacterGovernance", "transition_revision", "RuntimePrincipal",
    "load_runtime_context",
    "validate_runtime_character_context",
    "GovernedActor", "GovernancePolicy", "authorize_workflow_action",
    "PostgresDossierRepository", "CharacterWorkflowService",
    "HRCapabilityIdentityResolver",
    "R3CapabilityGrantAdapter", "validate_identity_association",
    "ApprovedCharacterContextProvider", "project_context_for_sink",
    "validate_approved_context", "HRPrincipalAssociationAdapter",
    "validate_association_evidence",
]
