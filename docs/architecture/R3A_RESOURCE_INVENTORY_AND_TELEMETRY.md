<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_RESOURCE_INVENTORY_AND_TELEMETRY.md
Component: R3A-RESOURCE-INVENTORY-CONTRACT
File Revision: 1.1.1
Created: 2026-11-08T18:43:38Z
Created By: Codex GPT-6
Purpose: Define resource, capability, and installed software inventory boundaries and source evidence.
Execution Model: N/A; provider architecture and acceptance record.
Observability: Provider schemas, digests, timestamps, state distinctions, and local read-only evidence.
Dependencies: Existing CME capability registry; local lsblk/smartctl; OctoMiner telemetry plug-in.
Authority: Issue #46; no managed runtime activation, production access, or service restart.
Changed: 2026-11-08T19:34:54Z | R3A-RESOURCE-MONITOR-002 | Codex GPT-6 | Correct provider identities and clarify process/entrypoint separation.
Supersedes: None.
Contracts: r3a.capability-operation.v1; r3a.physical-resource-inventory.v1; r3a.software-environment-inventory.v1.
Tests: tests/test_r3a_resource_monitor.py.
History/Predecessor: Git blob 571e4755665996ea916dbfefd1c10deff15938de at 30e05ce9ad483e8aecf3485b408bf3cc8867863b.
-->
# R3A resource inventory and monitoring boundary

R3A keeps three related inventories separate:

1. **Physical resources** are observed host devices. `r3a.physical-resource-inventory.v1` currently reports local block disks, byte capacity, transport, model, and independently reported SMART health/temperature. Disk health is `measured` only when smartctl returns parseable health data. Missing smartctl, permissions, malformed output, or a device error produce `unavailable`; a failed SMART health bit remains a measured `smart_passed: false` result.
2. **Callable capabilities** are operations in CME's existing dynamic capability registry. The disk and software operations below have independent read grants. Discovery does not grant invocation. This package adds no registry or dispatcher.
3. **Installed software environments** are reported by `r3a.software-environment-inventory.v1`. The operation resolves configured executable names through `PATH`; it does not claim that an installed binary is a registered capability or that an unavailable binary means a physical device is absent.

## Operations

| Operation | Provider | Output | Limitations |
|---|---|---|---|
| `infrastructure.resources.disk-health.read` | `r3a.disk-health-monitor` 1.0.0 | Physical block-device and SMART evidence | Local read-only `lsblk` and `smartctl`; no SMART self-tests or device writes. SMART may be unavailable without the binary or OS permission. SAS/SCSI JSON fields are parsed when present. |
| `infrastructure.software-environments.discover` | `r3a.software-environment-inventory` 1.0.0 | Host and configured executable availability | Reports resolution path and Python runtime version; does not inventory packages, CUDA libraries, services, or model installations. |
| `infrastructure.host-diagnostics.read` | `r3a.host-diagnostics` 1.0.0 | Configured host load average, memory, uptime, filesystem capacity and optional sensor readings | Local Linux interfaces; sensor/fan readings are unavailable when lm-sensors or sensor inputs are absent. A source host must be verified before labeling this as Camrui telemetry. |
| `infrastructure.octominer.telemetry.read` | `r3a.octominer-telemetry` 2.0.0 | GPU/VRAM/load/fan, mounted filesystem capacity, process-to-GPU mapping, model-server readiness, ComfyUI queues, R3A request metrics, bounded sample history | Existing independent configured SSH/HTTP/database collectors remain the owner of these domains. Native token throughput is not inferred. |

Physical inventory identities and telemetry observations can be joined by configured host and resource identifiers. The provider does not enumerate or assume OctoMiner hosts, endpoints, credentials, SAS devices, or GPU models. Register each manifest and its external configuration through the existing `capability_operations` input. Keep grants in the existing authorization authority.

Each provider response includes an observation timestamp, source path, source timestamp basis, freshness, and a SHA-256 digest of the content. This collector samples on invocation; it does not keep a last-known disk sample, so it reports `fresh` or `unavailable`. It never labels an old cached reading stale because there is no disk cache. The existing OctoMiner history provider retains its measured/stale/unavailable semantics.

`smartctl --json --all` is used only for retrieval. SCSI/SAS devices may return a nonzero smartctl status bitfield while still providing valid JSON health data; the status is retained with the measurement. The collector never runs `--test`, `--set`, enable/disable, formatting, or write commands.

## Source evidence in this development environment

Read-only local collection on 2026-11-08 observed one block disk (`sda`, SATA, 256,060,514,304 bytes) through `lsblk`. `smartctl` was not installed, so its health state is explicitly `unavailable`; this is not evidence of healthy media and is not evidence about any OctoMiner or SAS host. The SAS fixture tests demonstrate parsing only, not a live SAS measurement. The OctoMiner plug-in's GPU and inference providers remain registered as a separate implementation; no live remote access was performed in this increment.

The host diagnostic operation was then exercised read-only on local host identifier `admin1-Default-string`: 4 logical processors; measured load averages 21.55 / 29.13 / 36.10 for 1/5/15 minutes; memory 8,159,784,960 bytes total and 779,534,336 available; root filesystem 249,792,131,072 bytes total and 84.22% used. Sensor collection reported `unavailable` because `sensors` was absent. These values identify the current development host only; they do not establish that this host is Camrui. Result digest: `7ddb0f809d0c37ed4231ba450889e62c4723794f8962e31f3057fb59f6208748`.

## Backlog relationship

This work advances R3A punch-list R3A-005 (dynamic capability registry), R3A-007 (truthful states/provenance), and R3A-009 (bounded acceptance evidence), and informs R3-P004, R3-P012, R3-P022, and R3-P024. It does not mark those broader items complete. R3A parking-lot R3A-L005 remains open: this implementation consumes locally staged, digest-pinned manifests and does not create a general package-signing or remote-installation system. Host-level isolation remains a separate open item; no service or managed runtime is changed here.
