<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/RESIDENT_AUTHORITY_AND_CAPABILITIES.md
Component: R3-RESIDENT-AUTHORITY-ARCHITECTURE
File Revision: 1.0.0
Created: 2026-11-06T23:06:45Z
Created By: Codex GPT-6
Purpose: Define the R3 boundary between capability registration, resident identity, institutional policy, and execution.
Execution Model: N/A; architecture contract.
Observability: Identity provenance, policy decision source, operation correlation, and execution audit.
Dependencies: Approved R3 Charter Revision 2; HR identity-association contract; Riverview institutional AuthorityRegistry.
Authority: Steward directive GRACE-AUTHORITY-ARCH-001; approved charter governs; this document does not create permissions.
Changed: 2026-11-06T23:06:45Z | GRACE-AUTHORITY-ARCH-001 | Codex GPT-6 | Record source-of-authority boundaries and remove duplicate proposal authorization.
Supersedes: None.
Contracts: docs/PROJECT_CHARTER_REVISION_2_REVIEW.md; docs/r3-native-tool-contract.md; HR branch contract in Issue #41.
Tests: tests/test_capabilities.py; tests/test_internal_proposal_tool_integration.py; tests/test_proposal_gateway_adapter.py; tests/test_native_broker_composer.py.
History/Predecessor: New document; no predecessor.
-->
# Resident authority and capability contract

## Governing rule

Capability registration describes what an operation can do. Registration, resource discovery, a resident title, and model-visible tool configuration do not themselves grant authority. A runtime must authenticate the resident and use the institution's authoritative decision for the requested operation. It must not add a second per-tool Steward approval merely because a new adapter was registered.

The approved R3 Charter Revision 2 requires an autonomous, capability-first institution, distinguishes residents from replaceable implementations, and directs Security oversight to protect real information boundaries without routine permission bureaucracy. Steward decisions remain mandatory where the applicable institutional policy requires them. This document does not imply blanket resident access.

## Authority sources and boundaries

| Concern | Source of truth | Current R3 boundary |
|---|---|---|
| Registered tools and operations | Broker capability registrations (`GovernedToolGateway` / `CapabilityRegistry`) | Descriptors are metadata; registration is not authorization. |
| Registered hosts and operational resources | Owning broker catalog and `runtime/resource_registry.py` observations | The R3 `ResourceRegistry` is descriptive: freshness/online state is not authority or proof of operation. |
| Resident identity association | Authoritative HR record's confidential `r3_principal` and `authority_principal` extensions | Resolve exact stored identities. Never case-fold, infer, or hardcode a resident alias. |
| Institutional action/scope policy | Riverview `AuthorityRegistry` and its protected runtime decision interface | The policy service authenticates the institutional resident and applies its currently commissioned grant/policy rules. A denial or unavailable decision is fail-closed. |
| Resident-specific assignment/conditions | The authoritative HR/policy contract, when present and exposed to the runtime | The current R3 HR contract inspected for this workstream exposes identity association, not capability assignments, restrictions, or Ingrid classifications. Do not invent local substitutes. |
| Temporary exceptions | Institutional delegation mechanism, only when its active policy requires one | Exact scope, parent lineage, and expiry remain binding. Never create or renew an exception automatically. |
| R3-owned operations | R3 canonical authority store | Exact R3 grants continue to govern R3-owned resources and services; they are not duplicated for an operation already decided by an authoritative institutional service. |

The accessible Riverview legacy implementation (`Riverview-Comms5-Operations`, source revision `4905c667c6e7657f16a7702dbf3710b60c01c705`) documents an institutional `AuthorityRegistry` with exact action/scope checks. Its `RESIDENT_PERMISSION_PROFILES.md` and migration 0008 describe an additional profile gate, but explicitly state that migration/profile activation was not commissioned in that source snapshot. Those development-only rules are not evidence that R3 HR assignments or Ingrid classifications are currently available at runtime. Confirm deployed policy state through the owning service before relying on either behavior.

## Grace internal proposal path

1. R3 authenticates the caller's existing resident credential.
2. The broker resolves the caller's institutional principal through the exact confidential HR crosswalk.
3. `r3.proposal.submit` or `r3.proposal.status` invokes the existing `/api/v1/internal/resident-proposals` service with the mapped institutional identity and correlation.
4. The institutional registry makes the action/scope authorization decision and owns proposal persistence/readback. R3 records the named authority source and operation outcome; it does not require a duplicate R3 proposal grant.
5. A registry 401/403 remains an authorization denial. Registry outage, conflict, or uncertain write remains a backend failure requiring reconciliation; it is never reported as success.
6. A successful draft stays `DRAFT` and awaiting the existing Steward decision. This capability cannot approve, promote, create a work order, or dispatch Engineering work.

R3 exact grants continue to apply to R3-owned operations. New capabilities default to that authority path. A capability can delegate its decision to an authoritative service only when its registration explicitly names that existing service and its executor actually calls that authenticated service. A tool must not implement a private allowlist or treat its own registration as a grant.

## Known contract gap

The current R3 HR projection (`residents/grace/personnel.json`) is explicitly not the authoritative HR record. The established HR contract inspected in the HR worktree defines a confidential principal association and no capability-assignment or restriction schema. R3 therefore cannot prove that a particular HR job assignment or Ingrid security classification has been evaluated. Until HR and the institutional decision service expose a shared contract for those fields, R3 must preserve any denial returned by the owning policy service and must report the absent policy input as unverified rather than silently granting access.

No production identity association, permission, proposal, policy profile, or grant was changed by this correction. The live website-clock acceptance remains unverified unless the current HR association and the authoritative institutional policy decision are both available to the deployed resident runtime.
