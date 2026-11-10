"""
R3 CONTROLLED SOURCE
File: r3a_runtime/module_contracts.py
Component: R3A-MODULE-CONTRACTS
File Revision: 1.0.1
Created: 2026-11-08
Created By: R3A Coordinator
Purpose: Validate reusable semantic version and dependency graph rules for modules.
Execution Model: Pure in-process contract helpers.
Observability: Deterministic configuration errors before module registration or activation.
Dependencies: Python standard library.
Authority: Steward Directive — Coordinator Next Integration Cycle.
Changed: 2026-11-08 | R3A-MODULAR-PLUGINS-INTEGRATION | Add dependency range and cycle validation.
Changed: 2026-11-10T02:02:46Z | R3A-MODULAR-PLUGINS-46 | Accept the versioned v1.1 module-manifest promotion while preserving v1.0 compatibility.
Supersedes: None.
Contracts: r3a.module-manifest.v1@1.0.0 and @1.1.0.
Tests: tests/test_r3a_module_contracts.py.
History/Predecessor: New file.
"""
from __future__ import annotations

import re


def semantic_version(version: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"([0-9]+)\.([0-9]+)\.([0-9]+)", version)
    if match is None:
        raise ValueError("module version must use major.minor.patch")
    return tuple(map(int, match.groups()))


def version_satisfies(version: str, expression: str) -> bool:
    """Evaluate the bounded module range grammar used by manifests (AND clauses)."""
    candidate = semantic_version(version)
    if not isinstance(expression, str) or not expression.strip():
        raise ValueError("module dependency version range must be nonempty")
    for clause in expression.split(","):
        clause = clause.strip()
        match = re.fullmatch(r"([~^])?([0-9]+\.[0-9]+\.[0-9]+)", clause)
        if match:
            operator, raw_lower = match.groups()
            lower = semantic_version(raw_lower)
            if operator:
                if operator == "~":
                    upper = (lower[0], lower[1] + 1, 0)
                elif lower[0] > 0:
                    upper = (lower[0] + 1, 0, 0)
                elif lower[1] > 0:
                    upper = (0, lower[1] + 1, 0)
                else:
                    upper = (0, 0, lower[2] + 1)
                if candidate < lower or candidate >= upper:
                    return False
                continue
            if candidate != lower:
                return False
            continue
        match = re.fullmatch(r"(>=|<=|>|<|==)?([0-9]+\.[0-9]+\.[0-9]+)", clause)
        if match is None:
            raise ValueError(f"unsupported module dependency version range: {expression}")
        operator, raw_bound = match.groups()
        bound = semantic_version(raw_bound)
        operator = operator or "=="
        if not {">=": candidate >= bound, "<=": candidate <= bound, ">": candidate > bound,
                "<": candidate < bound, "==": candidate == bound}[operator]:
            return False
    return True


def validate_dependency_graph(configured_versions: dict[str, set[str]],
                              declarations: list[dict]) -> dict[tuple[str, str], set[tuple[str, str]]]:
    """Resolve every declared dependency and reject missing modules and cycles."""
    graph: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for declaration in declarations:
        module_key = (declaration["module_id"], declaration["module_version"])
        dependencies = graph.setdefault(module_key, set())
        for dependency in declaration["dependencies"]:
            versions = configured_versions.get(dependency["module_id"], set())
            matches = {version for version in versions
                       if version_satisfies(version, dependency["version_range"])}
            if not matches:
                raise ValueError(
                    f"{module_key[0]}@{module_key[1]} requires unconfigured "
                    f"{dependency['module_id']}@{dependency['version_range']}")
            dependencies.update((dependency["module_id"], version) for version in matches)

    visiting: set[tuple[str, str]] = set()
    visited: set[tuple[str, str]] = set()

    def visit(module_key: tuple[str, str]) -> None:
        if module_key in visiting:
            raise ValueError(f"module dependency cycle includes {module_key[0]}@{module_key[1]}")
        if module_key in visited:
            return
        visiting.add(module_key)
        for dependency in graph.get(module_key, set()):
            visit(dependency)
        visiting.remove(module_key)
        visited.add(module_key)

    for module_key in graph:
        visit(module_key)
    return graph


def is_legacy_manifest_promotion(previous: dict, current: dict) -> bool:
    """Permit only synthesized-default metadata to become an explicit v1 manifest."""
    if (previous.get("manifest_contract") is not None
            or current.get("manifest_contract") not in {
                "r3a.module-manifest.v1@1.0.0", "r3a.module-manifest.v1@1.1.0"}
            or previous.get("owner") != "manifest"
            or previous.get("configuration_ref") != "external-config"
            or previous.get("migration_contract") != "provider-stateless.v1"
            or previous.get("recovery_policy") != "replay-per-operation-contract"):
        return False
    stable_fields = ("module_id", "module_version", "contract_id", "protocol_major", "protocol_minor",
                     "protocol_min_minor", "protocol_max_minor", "entrypoint", "artifact_ref",
                     "artifact_digest", "dependencies", "configuration_schema", "capability_refs",
                     "resource_refs", "state_namespace")
    return all(previous.get(field) == current.get(field) for field in stable_fields)
