"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_module_contracts.py
Component: R3A-MODULE-CONTRACT-TESTS
File Revision: 1.0.2
Created: 2026-11-08
Created By: R3A Coordinator
Purpose: Verify generic semantic module dependency range matching.
Execution Model: Pytest unit tests; no runtime or database is started.
Observability: Assertions cover accepted/rejected version ranges and malformed contracts.
Dependencies: r3a_runtime.module_contracts.
Authority: Steward Directive — Coordinator Next Integration Cycle.
Changed: 2026-11-08 | R3A-MODULAR-PLUGINS-INTEGRATION | Validate the shared module dependency range contract.
Changed: 2026-11-10T02:02:46Z | R3A-MODULAR-PLUGINS-46 | Preserve synthetic-to-explicit manifest promotion for v1.1.0 declarations.
Changed: 2026-11-10T15:24:00Z | R3A-MODULAR-EXECUTOR-ROLE | Allow only same-version additive executor role promotion without artifact or identity drift.
Supersedes: None.
Contracts: r3a.module-manifest.v1.
Tests: tests/test_r3a_module_contracts.py.
History/Predecessor: New file; immediate predecessor blob 78573ee21439b988f1e2d522acdc6f33066676cf at base c62bb28d026e1c1cad99c90583f0debae067f2a1.
"""
import pytest

from r3a_runtime.module_contracts import (is_legacy_manifest_promotion,
                                         validate_dependency_graph, version_satisfies)


@pytest.mark.parametrize(("version", "expression", "expected"), [
    ("1.2.9", "^1.2.0", True),
    ("2.0.0", "^1.2.0", False),
    ("1.2.9", "~1.2.0", True),
    ("1.3.0", "~1.2.0", False),
    ("1.2.9", ">=1.2.0,<2.0.0", True),
    ("1.2.9", "1.2.9", True),
    ("1.2.8", "1.2.9", False),
])
def test_module_version_range(version, expression, expected):
    assert version_satisfies(version, expression) is expected


@pytest.mark.parametrize(("version", "expression"), [
    ("1.2", "^1.0.0"),
    ("1.0.0", "~1.0"),
    ("1.0.0", "~1.0.0 || ^2.0.0"),
    ("1.0.0", ""),
])
def test_module_version_range_rejects_unsupported_contract(version, expression):
    with pytest.raises(ValueError):
        version_satisfies(version, expression)


def test_dependency_graph_requires_a_compatible_configured_module():
    declarations = [{"module_id": "consumer", "module_version": "1.0.0",
                    "dependencies": [{"module_id": "provider", "version_range": "^2.0.0"}]}]
    with pytest.raises(ValueError, match="requires unconfigured provider"):
        validate_dependency_graph({"provider": {"1.4.0"}}, declarations)


def test_dependency_graph_rejects_cycles():
    declarations = [
        {"module_id": "a", "module_version": "1.0.0",
         "dependencies": [{"module_id": "b", "version_range": "^1.0.0"}]},
        {"module_id": "b", "module_version": "1.2.0",
         "dependencies": [{"module_id": "a", "version_range": "^1.0.0"}]},
    ]
    with pytest.raises(ValueError, match="dependency cycle"):
        validate_dependency_graph({"a": {"1.0.0"}, "b": {"1.2.0"}}, declarations)


def test_legacy_manifest_promotion_requires_same_identity_artifact_and_bindings():
    old = {"module_id": "provider", "module_version": "1.0.0", "contract_id": "r3a.capability-provider.v1",
           "protocol_major": 1, "protocol_minor": 0, "protocol_min_minor": 0, "protocol_max_minor": 0,
           "owner": "manifest", "entrypoint": "pkg:factory", "dependencies": [],
           "configuration_schema": {}, "configuration_ref": "external-config", "capability_refs": ["op"],
           "migration_contract": "provider-stateless.v1", "artifact_ref": "provider.py",
           "artifact_digest": "a" * 64, "recovery_policy": "replay-per-operation-contract",
           "resource_refs": [], "state_namespace": "provider"}
    new = {**old, "manifest_contract": "r3a.module-manifest.v1@1.0.0", "owner": "owner",
           "configuration_ref": "capability_operations[].configuration",
           "migration_contract": "r3a.stateless-provider.v1", "recovery_policy": "operation-contract.v1"}
    assert is_legacy_manifest_promotion(old, new)
    new_v11 = {**new, "manifest_contract": "r3a.module-manifest.v1@1.1.0",
               "resident_executor": {"contract_id": "r3a.resident.executor", "contract_version": "1.0.0"}}
    assert is_legacy_manifest_promotion(old, new_v11)
    assert not is_legacy_manifest_promotion(old, {**new, "artifact_digest": "b" * 64})
    assert not is_legacy_manifest_promotion(old, {**new, "dependencies": [{"module_id": "other",
                                                                           "version_range": "^1.0.0"}]})


def test_primary_executor_role_promotion_requires_exact_legacy_projection_and_v11_declaration():
    previous = {"module_id": "resident.orbit", "module_version": "1.2.3",
                "contract_id": "r3a.resident-module", "protocol_major": 1,
                "protocol_minor": 0, "protocol_min_minor": 0, "protocol_max_minor": 0,
                "owner": "Orbit Team", "entrypoint": "orbit.runtime",
                "dependencies": [], "configuration_schema": "r3a.bootstrap.v1",
                "configuration_ref": "/etc/r3a/bootstrap.json", "capability_refs": ["reason.plan"],
                "migration_contract": "none-v1", "artifact_ref": "/srv/r3a/orbit.py",
                "artifact_digest": "a" * 64, "recovery_policy": "idempotent",
                "resource_refs": ["foundation.observer"], "state_namespace": "resident.orbit"}
    role = {"contract_id": "r3a.resident.executor", "contract_version": "1.0.0",
            "execution_contract_range": {"contract_id": "r3a.resident.execution", "major": 1,
                                         "min_minor": 0, "max_minor": 2}}
    promoted = {**previous, "manifest_contract": "r3a.module-manifest.v1@1.1.0",
                "resident_executor": role}
    assert is_legacy_manifest_promotion(previous, promoted)
    assert not is_legacy_manifest_promotion(previous, {**promoted, "artifact_digest": "b" * 64})
    assert not is_legacy_manifest_promotion(previous, {**promoted, "module_version": "1.2.4"})
    assert not is_legacy_manifest_promotion(previous, {**promoted, "capability_refs": ["other"]})
    assert not is_legacy_manifest_promotion(
        previous, {**promoted, "resident_executor": {**role, "contract_version": "2.0.0"}})
    assert not is_legacy_manifest_promotion(previous, {**promoted, "activity_handler": {}})
