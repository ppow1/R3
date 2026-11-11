# R3 CONTROLLED SOURCE
# File: r3a_runtime/resident_identity.py
# Component: R3A-RESIDENT-IDENTITY-CONTRACT
# File Revision: 1.0.0
# Created: 2026-11-11 UTC
# Created By: Codex GPT-6
# Purpose: Keep canonical resident principal IDs distinct from executable module IDs.
# Execution Model: Pure validated value conversions at typed runtime boundaries.
# Observability: Invalid namespace use raises ValueError with the rejected identity type.
# Dependencies: Python standard library.
# Authority: AD-024 resident execution profile and capability invocation contracts.
# Changed: 2026-11-11 | R3A-RESIDENT-ID-AUDIT | Codex GPT-6 | Introduce nominal principal/module IDs and fail-closed parsers.
# Supersedes: None
# Contracts: r3a.resident.execution-profile@1.0.0; r3a.capability-invocation.v1.
# Tests: tests/test_r3a_resident_identity_kinds.py.
"""Typed boundary helpers for resident principals and resident executor modules.

The namespaces are intentionally different: ``resident:<slug>`` names the
institutional principal; ``resident.<slug>`` names executable module code.
This module validates that distinction without becoming an identity authority.
"""
from __future__ import annotations

import re
from typing import NewType


ResidentPrincipalId = NewType("ResidentPrincipalId", str)
ResidentModuleId = NewType("ResidentModuleId", str)

_PRINCIPAL = re.compile(r"^resident:[A-Za-z0-9][A-Za-z0-9._-]*$")
_MODULE = re.compile(r"^resident\.[A-Za-z0-9][A-Za-z0-9._-]*$")


def resident_principal_id(value: object) -> ResidentPrincipalId:
    """Parse a canonical resident principal ID."""
    if not isinstance(value, str) or not _PRINCIPAL.fullmatch(value):
        raise ValueError("resident principal ID must use the resident:<slug> namespace")
    return ResidentPrincipalId(value)


def resident_module_id(value: object) -> ResidentModuleId:
    """Parse a resident executor module ID."""
    if not isinstance(value, str) or not _MODULE.fullmatch(value):
        raise ValueError("resident module ID must use the resident.<slug> namespace")
    return ResidentModuleId(value)


def validate_resident_identity_pair(principal_id: object, module_id: object) -> tuple[ResidentPrincipalId, ResidentModuleId]:
    """Validate a principal/module pair at a resident execution boundary."""
    return resident_principal_id(principal_id), resident_module_id(module_id)
