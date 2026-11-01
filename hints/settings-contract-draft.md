<!--
R3 CONTROLLED DOCUMENT
File: hints/settings-contract-draft.md
Component: R3-SETTINGS-CONTRACT-DRAFT
File Revision: 1.0.2
Created: 2026-11-01 UTC
Created By: ChatGPT GPT-6
Purpose: Define a reviewable hierarchical settings interaction contract for R3
Execution Model: Draft registry/capability consumer; no live setting writes implied
Observability: Effective values, overrides, authorization, and configuration history
Dependencies: Approved R3 charter revision 2; settings registry and capability manifests; historical database qualification
Authority: Working draft only. Backend qualification and Steward review required before API adoption.
Changed: 2026-11-01 UTC | R3-CHAT-OPACITY-QUICK-PRESET-001 | ChatGPT GPT-6 | Add per-panel opacity and quick layout access
Supersedes: None; new draft
Contracts: docs/PROJECT_CHARTER_REVISION_2_REVIEW.md; docs/IMPLEMENTATION_HANDOFF.md
Tests: Not run; contract only
History/Predecessor: N/A; new document
-->
# R3 settings interaction contract — draft

**Status:** Review draft, not an approved backend API or schema.

## Scopes and inheritance

The settings experience is hierarchical and can present institutional, departmental, resident, chat, user, device, and infrastructure scopes. Each setting's registry definition identifies its valid scope, inheritance behavior, override support, constraints, and required capability. The interface displays the inherited value, any scoped override, and the effective value together, with provenance.

A child scope may override a parent only where the registry permits it. The effective value is computed according to registry policy and shown with its source. Do not assume every setting applies everywhere or that every scope can write it.

## Registry and authorization

- Populate settings and available operations from the authoritative settings registry and capability manifests. The interface must not hardcode a global list of operational switches or infer write access from visibility.
- Before a read or update, resolve the caller's identity and scope access. Enforce authorization on the backend; frontend disabled states are informative only.
- Display whether a value is inherited, locally overridden, locked, unavailable, or not authorized.
- Configuration changes record actor, scope, prior/effective value, time, authorization decision, and change reference in durable history.
- Expose the same authorized configuration capabilities to the website and approved residents where policy allows.

## Visual and unavailable behavior

Use the existing translucent estate style and compact controls. Clearly distinguish functional, unavailable, and planned operations. When the registry or manifest is absent, show the scope navigation with an explicit unavailable state and no fabricated values. A browser-only presentation preference, if offered, must be labeled local and must not be presented as institutional configuration.

## User-local presentation preferences

The User scope may expose browser-local presentation controls, including independent opacity for Chat, Engineering Foundry, and Infrastructure, plus up to ten named floating-window layouts. Each panel offers an opacity slider from its header. A saved layout captures the positions, sizes, and open or minimized state of Chat, Engineering Foundry, and Infrastructure, so a user can arrange all three together and restore that arrangement later.

A compact launcher above the profile button shows preset slots 1–10 vertically, with saved layouts enabled and empty slots visibly inactive. Its final settings icon opens the User-scope save and edit controls. Identify these values as stored in this browser; they do not imply an authorized settings registry write or synchronize to another device. Keep this local preference section distinct from registry-backed institutional settings.

## Backend coordination

The backend team will inspect and qualify historical Riverview database implementations before selecting schemas or creating replacements. Reconcile registry ownership, inherited values, override semantics, configuration history, authorization, secret handling, concurrency, and recovery with that review. This draft makes no database-selection decision.

## First acceptance milestone

Read one verified registry entry through the authorized settings capability. Show its scope, inherited value, scoped override (if present), effective value, authorization state, and source history accurately. Verify a permitted override and a denied write under separate test identities before claiming settings are operational.
