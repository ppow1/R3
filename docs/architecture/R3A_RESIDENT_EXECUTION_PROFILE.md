<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_RESIDENT_EXECUTION_PROFILE.md
Component: R3A-RESIDENT-PROFILE
File Revision: 1.1.0
Created: 2026-11-08T01:04:33Z
Created By: Codex GPT-6
Purpose: Specify the additive resident-side profile input used to bind a generic resident executor to directory identity and external model route configuration.
Execution Model: N/A
Observability: Profile lineage and route identity are included in resident inference provenance.
Dependencies: r3a_plugins/institutional_directory/manifest.json; r3a_runtime/grace_module.py; future CME resident dispatch integration.
Authority: R3A Multi-Resident Autonomy Steward directives and AD-024. The profile grants no execution authority.
Changed: 2026-11-08T01:04:33Z | R3A-MULTI-RESIDENT | Codex GPT-6 | Document generic resident execution-profile payload and current directory limitations.
Changed: 2026-11-10T00:17:40Z | R3A-MODULARITY-DECISIONS | Codex GPT-6 | Preserve profile v1 and require versioned generic resident-to-module binding under AD-024.
Supersedes: None
Contracts: Proposed r3a.resident.execution-profile@1.0.0; existing r3a.resident.execution.v1 remains unchanged.
Tests: Fixture-based validation in tests/test_r3a_ap1.py; no live resident invocation.
History/Predecessor: New controlled document; immediate predecessor commit ac3e9c36ca426fbbbf7703f3761e40011baeb87e (file blob 95729a6b3e36e9e36cfbd32282faa24af0fa2141).
-->
# Resident execution profile

## Purpose and ownership

This payload binds a resident execution request to identity and office-role evidence from the authoritative directory and to a model route selected by external configuration. CME now has per-resident process bindings and passes this profile for secondary resident execution; the module implementation selected for those profiles is still hardcoded to the Grace entrypoint. AD-024 requires the adjacent module-binding contract described below.

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

The profile must match the executing module's resident identity and configuration revision. If an explicit activity route conflicts with the profile route, the resident rejects the request. The configured route must exist in the resident's loaded model settings. Durable conversation remains activity-scoped and supplied by CME; this profile creates no private session store.

No candidate names, resident IDs, office assignments, responsibilities, operation IDs, or grants are embedded in code. The current directory operation contract exposes `resident_id`, nullable `display_name`, `office_id`, `office_role`, binding revision, and availability. It does **not** expose a separate office-responsibilities field; that remains an authoritative-directory contract gap. No responsibility text should be inferred beyond returned `office_role` until its owner provides an authoritative field.

## Current implementation status

- **Implemented:** CME keeps resident processes keyed by resident ID and passes validated execution-profile context; Grace validates profile contract/version, resident identity, config revision, directory evidence, and route.
- **Fixture-tested:** A generic directory-bound resident uses a distinct configured route and profile identity; identity mismatch is rejected before inference.
- **Limitation:** `r3a_runtime/config.py` restricts the top-level configured module entrypoint to Observer/Grace, and `CME._ensure_resident_module` launches `r3a_runtime.grace_module` for secondary residents. No authoritative resident-to-module binding currently selects another registered executor artifact/version. CME therefore has multi-resident process coordination, but not independently replaceable resident executor selection. The existing scheduler, profile, registry, lifecycle, and grants are the extension points to reuse.
- **Unavailable live evidence:** Managed directory DSN is unset, so no canonical Vicky/Helen identities or office bindings can currently be read by the directory capability. The directory provider returns unavailable rather than a legacy fallback. No model invocation or service changes are claimed by this profile slice.

## Required resident-to-module binding under AD-024

Keep `r3a.resident.execution-profile@1.0.0` as the resident execution context; do not encode a module ID or grants as an identity assertion in that payload. Add adjacent versioned contract `r3a.resident.module-binding.v1` to resolve an authoritative resident identity to a registered executor module.

The binding record references the canonical resident principal, authoritative existing HR/directory association and source revision, module ID/version, pinned artifact digest, resident execution contract range, external executor configuration reference/revision, and binding revision. Identity and HR remain in the existing authority; the binding neither creates resident rows nor grants capabilities. Display name, office title, and route are not binding keys.

CME resolves the current binding through its existing module registry/lifecycle and safe-boundary configuration reload, then passes the existing execution profile and activity envelope to the registered process. Generic dispatch must replace the current hardcoded Grace launch for all secondary resident profiles and the config allowlist that permanently limits resident entrypoints to Observer/Grace. The dispatch path must not add a resident-specific CME branch. Compatible binding changes use normal module operations without restarting CME or Ring 0; failed replacement preserves the prior effective binding or reports a recoverable blocked state.

Before dispatch, CME revalidates current canonical identity association, binding/module compatibility and applicable grants. Binding and roster discovery are not authorization. Existing resident capability invocations continue through CME's authorization contract. The executor owns its reasoning and choices within that authority.

Acceptance requires an unlisted disposable executor artifact and fixture identity/HR association to register, activate, execute, stop and replace through external configuration and existing module lifecycle; invalid/missing identity association, module version, binding revision, route, or grant must fail closed. Exercise two residents to prove no cross-binding, conversation, or private-state leakage. Keep directory roster visibility independent from executor readiness.
