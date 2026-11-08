"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_module_contracts.py
Component: R3A-MODULE-CONTRACT-TESTS
File Revision: 1.0.0
Created: 2026-11-08
Created By: R3A Coordinator
Purpose: Verify generic semantic module dependency range matching.
Execution Model: Pytest unit tests; no runtime or database is started.
Observability: Assertions cover accepted/rejected version ranges and malformed contracts.
Dependencies: r3a_runtime.module_contracts.
Authority: Steward Directive — Coordinator Next Integration Cycle.
Changed: 2026-11-08 | R3A-MODULAR-PLUGINS-INTEGRATION | Validate the shared module dependency range contract.
Supersedes: None.
Contracts: r3a.module-manifest.v1.
Tests: tests/test_r3a_module_contracts.py.
History/Predecessor: New file.
"""
import pytest

from r3a_runtime.module_contracts import validate_dependency_graph, version_satisfies


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
