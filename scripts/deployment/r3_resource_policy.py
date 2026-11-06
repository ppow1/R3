"""Fail-closed R/3 deployment resource allowlist.

This module is intentionally policy-only: callers validate their complete plan
before staging, activation, rollback, or cleanup. R3A is never an eligible target.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable


R3A_PROTECTED_PATHS = (
    Path("/home/admin1/r3a-phase0"),
    Path("/home/admin1/.local/state/r3a-ap0-m1"),
    Path("/home/admin1/.config/r3a-ap0-m1"),
)
R3A_PROTECTED_UNITS = frozenset({
    "r3a-ap0-m1-postgres.service",
    "r3a-ap0-m1-ring0.service",
})
R3A_PROTECTED_PORTS = frozenset({55492})
R3A_PROTECTED_DATABASES = frozenset({"r3a_ap0_m1"})
R3A_PROTECTED_ROLES = frozenset({"r3a_runtime"})

# Proposal activation owns only the resident loop and existing native broker.
# The website has a separate HR-backed release and is not in this operation.
R3_UNITS = {
    "r3-institution.service": frozenset({8770}),
    "r3-native-tools.service": frozenset({8765}),
}
R3_RELEASE_ROOT = Path("/home/admin1/.local/share/r3/releases")
R3_RUNTIME_ROOT = Path("/home/admin1/.local/state/r3-runtime")
R3_UNIT_DROPIN_ROOT = Path("/home/admin1/.config/systemd/user")

_ACTIONS = frozenset({"stage", "activate", "rollback", "cleanup"})
_FORBIDDEN_PROCESS_ACTIONS = frozenset({
    "kill", "pkill", "killall", "process-scan-kill", "broad-stop",
})


class IsolationError(ValueError):
    """The proposed operation is outside the explicit R/3 resource boundary."""


def _resolved(path: str | Path) -> Path:
    # resolve(strict=False) detects existing symlinks without requiring staged
    # releases to exist yet.
    return Path(path).expanduser().resolve(strict=False)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _reject_protected_path(path: Path) -> None:
    for protected in R3A_PROTECTED_PATHS:
        protected = _resolved(protected)
        if _inside(path, protected) or _inside(protected, path):
            raise IsolationError(f"R3A-protected path rejected: {protected}")


def validate_unit(unit: str) -> str:
    if unit in R3A_PROTECTED_UNITS:
        raise IsolationError(f"R3A-protected unit rejected: {unit}")
    if unit not in R3_UNITS:
        raise IsolationError(f"Unit is not allowlisted for Grace proposal activation: {unit}")
    return unit


def validate_port(unit: str, port: int) -> int:
    validate_unit(unit)
    if port in R3A_PROTECTED_PORTS:
        raise IsolationError(f"R3A-protected port rejected: {port}")
    if type(port) is not int or port not in R3_UNITS[unit]:
        raise IsolationError(f"Port is not allowlisted for {unit}: {port}")
    return port


def validate_release_path(path: str | Path) -> Path:
    resolved = _resolved(path)
    root = _resolved(R3_RELEASE_ROOT)
    _reject_protected_path(resolved)
    if resolved == root or not _inside(resolved, root):
        raise IsolationError(f"Release must be below the R/3 immutable release root: {root}")
    # A release directory itself must not be a symlink. Resolve above also
    # prevents a symlinked child from escaping the R/3 release root.
    if Path(path).is_symlink():
        raise IsolationError("Release target must be a real immutable directory")
    return resolved


def validate_runtime_path(path: str | Path) -> Path:
    resolved = _resolved(path)
    root = _resolved(R3_RUNTIME_ROOT)
    _reject_protected_path(resolved)
    if resolved == root or not _inside(resolved, root):
        raise IsolationError(f"Runtime path must be below the R/3 runtime state root: {root}")
    return resolved


def validate_unit_dropin(unit: str, path: str | Path) -> Path:
    validate_unit(unit)
    resolved = _resolved(path)
    _reject_protected_path(resolved)
    expected = _resolved(R3_UNIT_DROPIN_ROOT / f"{unit}.d")
    if not _inside(resolved, expected) or resolved == expected:
        raise IsolationError(f"Unit override must be inside the allowlisted drop-in for {unit}")
    return resolved


def validate_database_target(name: str, role: str | None = None) -> None:
    if name in R3A_PROTECTED_DATABASES:
        raise IsolationError(f"R3A-protected database rejected: {name}")
    if role in R3A_PROTECTED_ROLES:
        raise IsolationError(f"R3A-protected database role rejected: {role}")
    # Proposal deployment is code/config only. It must not run SQL or touch a
    # database, even when that database is not R3A-owned.
    raise IsolationError("Database targets are not part of the R/3 proposal deployment allowlist")


def validate_process_action(action: str) -> None:
    if action in _FORBIDDEN_PROCESS_ACTIONS or any(token in action for token in ("*", "?", "[", "]")):
        raise IsolationError(f"Broad or direct process control rejected: {action}")
    raise IsolationError(f"Process action is not allowlisted; use exact systemd unit control: {action}")


def validate_plan(*, action: str, units: Iterable[str], ports: Iterable[tuple[str, int]],
                  release_paths: Iterable[str | Path] = (),
                  runtime_paths: Iterable[str | Path] = (),
                  dropins: Iterable[tuple[str, str | Path]] = (),
                  database_targets: Iterable[tuple[str, str | None]] = (),
                  process_actions: Iterable[str] = ()) -> dict:
    """Validate an entire deployment/rollback plan before any filesystem or service mutation."""
    if action not in _ACTIONS:
        raise IsolationError(f"Unsupported deployment action: {action}")
    selected_units = tuple(units)
    if not selected_units or len(selected_units) != len(set(selected_units)):
        raise IsolationError("Plan requires a non-empty unique R/3 unit allowlist")
    for unit in selected_units:
        validate_unit(unit)
    selected_ports = tuple((unit, port) for unit, port in ports)
    if set(selected_ports) != {
        (unit, port) for unit in selected_units for port in R3_UNITS[unit]
    }:
        raise IsolationError("Plan ports must exactly match the selected R/3 unit allowlist")
    checked_releases = tuple(str(validate_release_path(path)) for path in release_paths)
    checked_runtime = tuple(str(validate_runtime_path(path)) for path in runtime_paths)
    checked_dropins = tuple(
        (unit, str(validate_unit_dropin(unit, path))) for unit, path in dropins
    )
    for name, role in database_targets:
        validate_database_target(name, role)
    for process_action in process_actions:
        validate_process_action(process_action)
    if action == "cleanup" and checked_releases:
        raise IsolationError("Release cleanup is disabled; retain immutable rollback releases")
    return {
        "action": action,
        "units": selected_units,
        "ports": selected_ports,
        "release_paths": checked_releases,
        "runtime_paths": checked_runtime,
        "dropins": checked_dropins,
        "database_targets": (),
        "process_actions": (),
        "r3a_isolated": True,
    }
