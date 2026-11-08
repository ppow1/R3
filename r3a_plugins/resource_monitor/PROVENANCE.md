<!--
R3 CONTROLLED DOCUMENT
File: r3a_plugins/resource_monitor/PROVENANCE.md
Component: R3A-PLUG-RESOURCE-MONITOR-PROVENANCE
File Revision: 1.0.0
Created: 2026-11-08T18:43:38Z
Created By: Codex GPT-6
Purpose: Sidecar provenance and registration notes for JSON module configuration and manifests.
Execution Model: N/A; package record.
Observability: Git history and immutable artifact SHA-256 pins in operation manifests.
Dependencies: Issue #46; unified CME capability registry.
Authority: No managed runtime activation or grant is included by this package.
Changed: 2026-11-08T18:43:38Z | R3A-RESOURCE-MONITOR-001 | Codex GPT-6 | Record source files and registration ownership.
Supersedes: None.
Contracts: r3a.capability-operation.v1; r3a.physical-resource-inventory.v1; r3a.software-environment-inventory.v1.
Tests: tests/test_r3a_resource_monitor.py.
History/Predecessor: New file.
-->
# Resource monitor package provenance

Manifest files use standard JSON and therefore carry their provenance in this sidecar. Each manifest pins `monitor.py` by SHA-256 and declares a separate provider identity at version `1.0.0`; this keeps their lifecycle and entrypoint binding independent even though they share a source file. Their descriptors are validated against `r3a.capability-operation.v1`.

- `disk-health.manifest.json` registers `infrastructure.resources.disk-health.read`.
- `software-environments.manifest.json` registers `infrastructure.software-environments.discover`.
- `config.example.json` contains a placeholder host identifier and example bounded executable list. Replace it in externally managed configuration; do not activate the example unchanged.
- `monitor.py` issues only read-only `lsblk` and `smartctl --json --all` commands, and resolves software executables without executing them.

The physical inventory, software inventory, and CME capability registry are separate datasets. `resource_id` is the observed host plus block-device name; serial numbers are intentionally omitted. The manifests require the already-governed `infrastructure.resource-inventory.read` grant; this package does not create that grant.
