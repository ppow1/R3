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

__all__ = [
    "DossierRepository", "DossierError", "RevisionConflict",
    "PromptComposition", "compose_prompt", "validate_dossier",
    "DossierValidationError", "resolve_personality", "runtime_binding",
    "validate_memory_entry", "validate_relationship", "validate_emotional_state",
    "append_memory_correction", "evolve_relationship", "transition_emotional_state",
    "extract_legacy_hr_candidates",
]
