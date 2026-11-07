<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_OCTOMINER_TELEMETRY_PLUGIN.md
Component: R3A-PLUG-OCTOMINER
File Revision: 1.0.0
Created: 2026-11-07T04:19:12Z
Created By: Codex GPT-6
Purpose: Record provenance, installation configuration, and boundaries for the first R3A telemetry capability plug-in.
Execution Model: N/A
Observability: Capability registration, source evidence, digest, timestamps, freshness and per-endpoint availability.
Dependencies: Issue #46; R3A module contract; Riverview Octo Control v0.6.1 API documentation.
Authority: Issue #46; isolated development; read-only Octo Control telemetry only.
Changed: 2026-11-07T04:19:12Z | R3A-PLUG-001 | Codex GPT-6 | Initial documentation.
Supersedes: None.
Contracts: r3a.capability-plugin 1.0.0; r3a.octominer-telemetry.config.v1; Issue #46.
Tests: tests/test_r3a_octominer_plugin.py.
History: New file; initial publication recorded in Git.
-->
# OctoMiner telemetry capability plug-in

## Findings and source provenance

The Riverview repository documents the installed OCTOMINER2 Riverview OCTO Control v0.6.1 API and its exact read-only routes: `GET /api/v1/gpus` provides live GPU telemetry, while `GET /api/v1/fans` provides Octofan, fan, PSU, sensor, and watchdog telemetry. Both require a Bearer token. Its API documentation identifies the separate write routes (`POST` and `DELETE`); this plug-in does not expose or call them. The source also says GPU utilization, temperature, power and VRAM are reported by the controller, and that PSU input is controller-reported rather than a calibrated wall measurement.

Source document: [Riverview OCTO Control v0.6.1 — Features and Remote API](https://github.com/ppow1/Riverview/blob/4590f2fb5e6813d409b3faf8e37a151778aea1f6/docs/operations/octominer/RIVERVIEW_OCTO_CONTROL_FEATURES_AND_API_2026-09-14.md), fetched at commit `4590f2fb5e6813d409b3faf8e37a151778aea1f6`. The separate documented controller utility `/hive/opt/octofan/fan_controller_cli -r` is machine-readable, read-only status, but authenticated host transport and its payload contract are not configured in this workstream. No live API request was made.

The local R3 website [adapter seam](../../web/index.html) currently reports telemetry as unavailable and is not connected to Octo Control. The available R3 code does not contain an OctoMiner collector or R/2 telemetry integration to reuse. The plug-in therefore reuses the documented Octo Control API contract rather than pretending that the local website has a live feed. The production website remains untouched.

## Package and configuration

Package files are under `r3a_plugins/octominer_telemetry/`:

- `manifest.json` declares plug-in identity/version, the `r3a.capability-plugin` contract, read-only capability, tool schema, entrypoint, and SHA-256 digest of its executable artifact.
- `plugin.py` issues only fixed GET requests to `/api/v1/gpus` and `/api/v1/fans`. It retains returned payloads and source units without interpreting or inventing fields. Each endpoint yields its own evidence record, digest, retrieval timestamp, source timestamp when the HTTP `Date` header is present, and freshness/availability state. Errors omit credential and response-body content.
- `config.example.json` demonstrates the external config shape. The configured base URL, timeout, maximum age, and optional bearer-token environment variable name are independent from CME code. Secret values stay in the environment and never enter the manifest or config file.

To enable in an isolated R3A config, copy the example config to a protected per-installation path, set its base URL, and add a `capability_plugins` entry pointing to the package manifest and that config file. Add `infrastructure.octominer.telemetry.read` to the Grace module's declared `capabilities`. CME discovers the manifest, validates the declared read-only mode and artifact digest, registers it as read-only, and exposes the tool to Grace. Each call still passes the existing capability-grant authorization provider. Discovery does not create a grant. Runtime/activation integration must separately supply an explicit grant and authorized endpoint credential.

Example root configuration addition:

```json
"capability_plugins": [
  {
    "manifest": "/absolute/path/to/r3a_plugins/octominer_telemetry/manifest.json",
    "configuration": "/absolute/path/to/octominer-telemetry.config.json"
  }
]
```

## Limits

The source API's full payload schema, actual live endpoint response, network reachability, token provisioning, and source-side sample timestamps have not been verified here. `observed_at` is the local retrieval time; `source_timestamp` is only populated from HTTP `Date` and is not represented as a per-metric sample time. `freshness` describes the retrieval age, not an upstream monitor sample age. Source payload field names and units are preserved, but unit completeness depends on Octo Control. Model throughput is not provided by the selected endpoints. No live telemetry claim is made.
