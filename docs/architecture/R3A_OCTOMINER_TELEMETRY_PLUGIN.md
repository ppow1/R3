<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_OCTOMINER_TELEMETRY_PLUGIN.md
Component: R3A-PLUG-OCTOMINER
File Revision: 3.0.0
Purpose: Record V2 archive provenance, telemetry parity, and independent R3A adapter behavior.
Authority: Issue #46 steward directives; independent R3A operation and read-only access.
Contracts: r3a.capability-plugin 1.0.0; r3a.octominer-nvidia-smi-ssh.config.v1.
Tests: tests/test_r3a_octominer_plugin.py.
-->
# R3A OctoMiner telemetry plug-in

## Evidence and source provenance

The transferred reference archive is `riverview-v2-2026-11-07T04-27-10.101Z-cd2e5e74-353d-4f71-aebe-e9813cc11b10.zip`. Its `manifest.json` reports schema `rv.website.diagnostic-snapshot.v2`, authenticated dashboard capture, complete, captured at `2026-11-07T04:27:10.101Z`, dashboard source commit `2aee5e234c9d0461e1a788e5f0c43c4d715f7f07`, 15 screens, 24 workflows, 6,512 controls, 680 workflow nodes and 913 edges. The telemetry evidence is primarily `website/v2/screens/resources.json` (SHA-256 `6ab7bd3566cb4dc91d35086b32ead788b94fe46509c73d9e1b3ad29f34789374`) and its HTML presentation. The archive privacy declaration says credentials, cookies, authorization headers and form values are redacted.

The Resources screen says the GPU source is `nvidia-smi via restricted SSH`; its latest GPU snapshot is `2026-11-07T04:26:50.598Z`. GPU readings include device name/index, memory, utilization, temperature and per-device fan speed when available. NVIDIA index, UUID/PCI identity and physical chassis bay are separate identities. The screen explicitly labels bay mapping as unverified and the depicted chassis/fan geometry as manufacturer reference. GPU samples are system observations and are not attributed to a Grace request.

Other demonstrated sources are direct model-server slot occupancy (`04:26:49.911Z`), ComfyUI system/queue APIs (`04:26:49.859Z`), and filesystem measurements (Camrui and OCTO1, about `04:26:50.6Z`). Five-second polling is described; the history control reports eight recent samples over two pages. The archive also shows durable router/conversation events with provider-call start/end, elapsed milliseconds, prompt/completion token counts, response persistence, and streamed text cadence semantics. The displayed event history is historical (for example, `2026-11-06T00:10Z`); it is not a live sample at capture time. It says model-server receipt/prompt/generation timeline and per-request GPU correlation are unavailable. Fan controller installation, environmental sensors, PSU feed, watchdog feed, OCTO2 and Windows host capacity, and workload-control authority are explicitly unverified/unavailable. No value is inferred from a chassis diagram or assigned a zero when absent.

The archive is a V2 presentation/diagnostic capture, not collector source. Its deployed page references `/api/v1/resources/telemetry`, a legacy Riverview route; R3A does not call it. The workflow record `diagnostics/workflows/020-rv_steward-dashboard_status.json` identifies the V2 source files as `src/riverview_core/status_dashboard/resource_telemetry.py`, `scripts/rv_gpu_telemetry_command.py`, `src/riverview_core/status_dashboard/storage_inventory.py`, and `src/riverview_core/status_dashboard/server.py`. It says the GPU source used strict-pinned SSH and a host forced-command collector; it points to `tests/test_resource_telemetry.py`, `tests/test_gpu_telemetry_command.py`, `tests/test_storage_inventory.py`, and source-observation artifacts. The archive contains those provenance references and test names, but not the source files or referenced source-observation artifacts. The dashboard deployment commit `2aee5e234c9d0461e1a788e5f0c43c4d715f7f07` is not available in the checked repositories, and GitHub file retrieval for the named V2 source paths returned 404. Thus the actual V2 source was located by provenance but could not be inspected or copied. No V2 collector code is claimed as reused.

The proven donor is The Estate's independent [`collect_nvidia_smi`](https://github.com/ppow1/theestate/blob/6f8c620225bc757eaf11b0b090c9c56bd13bb110/src/estate/core/compute_resources.py) at commit `6f8c620225bc757eaf11b0b090c9c56bd13bb110`: bounded `nvidia-smi` CSV query, physical UUID identity, and numeric metric parsing. R3A reimplements those proven patterns in its own package; it imports no Estate/Riverview code or data store. For storage, R3A independently parses fixed `df` output; this follows the archive's reported source behavior, not copied V2 implementation.

## Feature parity matrix

| V2 demonstrated capability | Archive evidence / semantics | R3A implementation in this worktree | Status and limit |
|---|---|---|---|
| GPU inventory and identity | Five measured devices; UUID/PCI identity and device ordinal; names and driver | Fixed `nvidia-smi --query-gpu` over configured R3A SSH; retains UUID, PCI bus, name and driver | Implemented; fixture-verified, no live OCTO1 read |
| GPU utilization | Percent, timestamped source snapshots; rolling five-minute view may be unavailable | Per-device utilization in GPU evidence; collection timestamp and freshness | Implemented collector field; rolling-window aggregation/history is not implemented |
| VRAM | Total/used/free per device, explicit MiB/GiB presentation | Total/used/free MiB with units in evidence | Implemented |
| Temperature and power | Temperature per GPU; power is part of source collection | Temperature °C and power W | Implemented; power may be unavailable from driver and stays null |
| GPU fan | One device displayed at 50%; other GPU fans unavailable | `fan.speed` queried per GPU, with N/A represented as null | Implemented as GPU fan sensor; not chassis fan-controller telemetry |
| Grace/model GPU process mapping | Derived from live GPU process projection; source and model attribution distinguished | No process-enumeration adapter or model-to-GPU mapping | Missing; must add a read-only R3A source before claiming parity |
| Model service readiness and active slots | Reasoning 80B measured; vision/autonomic slots stale/unavailable; counts/configured slots | No model-server adapter | Missing; direct R3A-configured model endpoints and authorization contract required |
| ComfyUI health/version/queue/CUDA VRAM | Direct system and queue API; queue counts only, no prompt contents | No ComfyUI adapter | Missing; must be a separately configured direct service source, with queue content excluded |
| Provider-call output tokens/s | Router-recorded completed output tokens divided by elapsed provider call; includes transport/service overhead | CME model response can expose usage, but this plug-in has no R3A-owned durable call telemetry stream/aggregation | Missing; no V2 router/database dependency is acceptable |
| Streamed output characters/s | Application-side text-delta cadence, explicitly not server token speed | No R3A durable stream cadence samples | Missing; requires R3A-owned event capture and rolling aggregation |
| Correlated request trace | Request/attempt IDs, provider and start/end, persisted timestamp, returned token counts; prompts/responses excluded on page | No telemetry projection for these durable call events | Missing; existing core model execution records usage in the response path but does not publish this authorized telemetry capability |
| Filesystem capacity | Seven unique measured filesystems on Camrui/OCTO1; source, mount, used/free/total, timestamp; unavailable hosts excluded | Fixed `df -P -B1 -x tmpfs -x devtmpfs` via configured R3A SSH; filesystem, mount and byte counts | Implemented collector field; dedup across hosts and aggregate fleet totals/history not implemented |
| Rolling source history and freshness | Five-second updates; eight recent samples, two pages; measured/stale/unavailable distinct | Each read emits separately hashed GPU and storage source records, collection timestamps, fresh/unavailable state | Current sample and failure distinction implemented; durable multi-sample history, stale-cache presentation and five-minute rollups are missing |
| Chassis bay mapping / fan geometry | Steward/manufacturer statements only; mapping unverified | Not emitted as measured telemetry | Correctly withheld; cannot claim verified physical mapping |
| Chassis fan controller, environmental sensors, PSU, watchdog | Installation/feed unavailable or unverified in archive | No collector | Intentionally unavailable pending an authorized, verified read-only source; no fabricated measurements |
| Registered GPU workload controls | Status/action surface, but archive says authority service unavailable | No controls are in this read-only plug-in | Excluded by design; no control actions are exposed |

This is an evidence-based parity inventory, not a claim that R3A already matches the V2 dashboard. GPU and mounted-filesystem collection are implemented; the other missing rows are explicit follow-up work, especially model slots, ComfyUI, R3A-owned call/stream telemetry, process mapping and history/aggregation.

## R3A ownership and lifecycle

`r3a_plugins/octominer_telemetry/manifest.json` defines a generic dynamically discovered, read-only capability and its configuration schema. `r3a_runtime/config.py` validates manifest-declared plugin schemas and artifact digests; CME imports configured entrypoints and routes each call through its existing explicit capability authorization. There are no OctoMiner collector branches in CME, and adding another plugin does not require a CME source edit. Registration/discovery does not grant invocation authority.

`plugin.py` runs only two fixed remote commands, one at a time: `nvidia-smi --query-gpu=... --format=csv,noheader,nounits` and `df -P -B1 -x tmpfs -x devtmpfs`. SSH uses `/dev/null` config, a distinct R3A identity file, an R3A-pinned known-hosts file, strict host-key checking, batch mode, forwarding disabled, no TTY, and bounded timeouts. Neither command nor endpoint can be supplied by Grace. GPU UUID and filesystem mountpoint form source-local identities. Values include units and R3A collection timestamps; these commands provide no source-generation timestamp, so evidence labels timestamp basis as R3A collection time. Failed reads are `unavailable` and do not become zero. There is no cached measurement in this adapter to mislabel as fresh.

`config.example.json` is only a template. Its `192.0.2.10` address is documentation-only. A separately provisioned R3A key, pinned host key, host configuration and explicit read-only grant are prerequisites for activation. No credentials from the archive or legacy accounts are reused. The archive itself is reference evidence and is not loaded by the runtime.

## Independence and verification boundary

The adapter has no HTTP client and no legacy service endpoint. Its only network boundary is explicitly configured SSH to a host source using R3A-owned credentials and host-key trust. Unit tests mock that boundary and verify query allowlisting, SSH protections, parser identity/units, config-schema validation, digest pinning and unavailable behavior. These checks demonstrate code-path independence from legacy application services; they do not demonstrate network connectivity or live telemetry from OCTO1.

No legacy service was stopped. No OctoMiner service was restarted or contacted. No production system or shared R3A runtime was modified or activated. Integration approval, target provisioning and additional direct source adapters remain prerequisites for live operation and broader parity.
