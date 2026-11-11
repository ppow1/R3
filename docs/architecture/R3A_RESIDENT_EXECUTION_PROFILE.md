<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_RESIDENT_EXECUTION_PROFILE.md
Component: R3A-RESIDENT-PROFILE
File Revision: 1.0.1
Created: 2026-11-08T01:04:33Z
Created By: Codex GPT-6
Purpose: Specify the additive resident-side profile input used to bind a generic resident executor to directory identity and external model route configuration.
Execution Model: N/A
Observability: Profile lineage and route identity are included in resident inference provenance.
Dependencies: r3a_plugins/institutional_directory/manifest.json; r3a_runtime/grace_module.py; future CME resident dispatch integration.
Authority: R3A Multi-Resident Autonomy Steward directives. The profile grants no execution authority.
Changed: 2026-11-08T01:04:33Z | R3A-MULTI-RESIDENT | Codex GPT-6 | Document generic resident execution-profile payload and current directory limitations.
Changed: 2026-11-11 | R3A-RESIDENT-ID-AUDIT | Codex GPT-6 | Specify canonical resident principal separately from the executable module ID.
Supersedes: None
Contracts: Proposed r3a.resident.execution-profile@1.0.0; existing r3a.resident.execution.v1 remains unchanged.
Tests: Fixture-based validation in tests/test_r3a_ap1.py; no live resident invocation.
History/Predecessor: Prior integration-tree blob 95729a6b3e36e9e36cfbd32282faa24af0fa2141.
-->
# Resident execution profile

## Purpose and ownership

This optional payload binds a resident execution request to the resident identity and office role discovered from the authoritative directory, and to a model route selected by external configuration. It is an additive resident-side contract; CME has not yet been changed to schedule multiple resident processes or deliver this payload.

The profile is descriptive routing context. It is not a grant, capability list, work order, or authority assertion. CME continues to resolve/discover operations and enforce grants at invocation. Resident identity, directory office binding, model route, and capability authorization remain separate facts.

## Payload

```json
{
  "contract_id": "r3a.resident.execution-profile",
  "contract_version": "1.0.0",
  "resident_id": "directory-returned principal ID",
  "display_name": null,
  "office_id": "directory-returned office ID",
  "office_role": "directory-returned office role",
  "directory_evidence": {
    "source_id": "directory source reference",
    "snapshot_sha256": "64 lowercase hexadecimal characters",
    "observed_at": "RFC3339 timestamp"
  },
  "model_route_id": "externally configured route identifier",
  "config_revision": "active configuration digest/revision"
}
```

`resident_id` is the canonical institutional principal (`resident:<slug>`) resolved through the existing HR/directory association. It is not the executable module ID (`resident.<slug>`), which is carried in the module registry, binding, and process protocol. The approved binding joins those identities; it grants no authority. The execution envelope, profile, and activity target must carry the same canonical principal, while process selection continues to use the registered module ID. If an explicit activity route conflicts with the profile route, the resident rejects the request. The configured route must exist in the resident's loaded model settings. Durable conversation remains activity-scoped and supplied by CME; this profile creates no private session store.

No candidate names, resident IDs, office assignments, responsibilities, operation IDs, or grants are embedded in code. The current directory operation contract exposes `resident_id`, nullable `display_name`, `office_id`, `office_role`, binding revision, and availability. It does **not** expose a separate office-responsibilities field; that remains an authoritative-directory contract gap. No responsibility text should be inferred beyond returned `office_role` until its owner provides an authoritative field.

## Current implementation status

- **Implemented:** Grace module validates the profile's contract/version, exact resident binding, configuration revision, directory source reference/digest/time, and route ID. A non-primary resident request must provide the profile. Profile identity/office role become the resident's system-context framing; the selected route and profile provenance are retained in the model request/result record.
- **Fixture-tested:** A generic directory-bound resident uses a distinct configured route and profile identity; identity mismatch is rejected before inference.
- **Not integrated:** CME currently supervises one resident module process/socket and sends objectives through that module. CME must own recipient resolution, per-resident module configuration/process lifecycle, activity assignment, and handoff result continuation through the existing scheduler/state/event mechanisms.
- **Unavailable live evidence:** Managed directory DSN is unset, so no canonical Vicky/Helen identities or office bindings can currently be read by the directory capability. The directory provider returns unavailable rather than a legacy fallback. No model invocation or service changes are claimed by this profile slice.
