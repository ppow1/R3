<!--
R3 CONTROLLED DOCUMENT
File: hints/chat-contract-draft.md
Component: R3-CHAT-CONTRACT-DRAFT
File Revision: 1.0.1
Created: 2026-11-01 UTC
Created By: ChatGPT GPT-6
Purpose: Define reviewable R3 chat interaction requirements across the website and authorized residents
Execution Model: Draft capability boundary; no implementation or live API implied
Observability: Conversation, message, capability, and work-link lifecycle events require audit and history
Dependencies: Approved R3 charter revision 2; R3-P002; R3-P005; existing Riverview database implementations pending backend qualification
Authority: Working draft only. Backend qualification and Steward review required before API adoption.
Changed: 2026-11-01 UTC | R3-CHAT-SETTINGS-UI-001 | ChatGPT GPT-6 | Add Steward's chat interaction and V2 responsiveness requirements
Supersedes: Revision 1.0.0; clarify user-approved interaction direction
Contracts: docs/PROJECT_CHARTER_REVISION_2_REVIEW.md; docs/PUNCH_LIST.md
Tests: Not run; contract only
History/Predecessor: Git blob 9ccfd0ad0efdcc848c98af7c3f9940a091398974
-->
# R3 chat interaction contract — draft

**Status:** Review draft. It defines visual and capability requirements, not an approved API or a claim that chat is implemented.

## Experience

Preserve Riverview 2's responsive, low-latency interaction: quick navigation, incremental history display, and a composer that stays responsive while older messages load. Keep the estate's understated translucent visual language. Use compact icons, tooltips, and three-dot contextual menus rather than large labeled action buttons.

Provide conversation affordances for new, rename, search, archive, delete, reopen, and conference-room use. Add contextual menus at conversation and message level. Reserve message actions for copy, edit, quote, branch, generate image, save reference, and work-related actions. These affordances may be unavailable or planned until their capabilities are connected.

The interface shows no synthetic conversations, messages, residents, work orders, or results. Each feature is explicitly identified as functional, unavailable, or planned. The UI distinguishes an empty account from an unavailable service.

## Shared institutional capability

Chat is a durable institution-wide capability, not a browser-owned transcript. The website, Grace, and authorized residents use shared services under their own identities and permissions. Conversations persist across refresh and service restart according to the qualified R3 persistence architecture.

The service represents conversations, participants, messages, ordered lifecycle events, authorized attachments, and work-resource links. Message and event identity, sender, service timestamp, ordering, delivery/failure state, and correlation with tool activity are runtime-owned concepts. This document does not impose wire-format names or schemas.

## Capability-aware interaction

- Conversation and message action menus are populated from the caller's resident-specific capability manifest. Do not ship one assumed toolbar as the operational menu for every resident.
- Sending text does not authorize tool execution. A work-related action resolves through the registered capability, current authorization, audit, and execution-result services.
- A tool request links to its source message and authoritative work record. Required Steward approval uses existing policy and approval services.
- Conversations, attachments, and links are accessible only after authorization checks; an identifier does not grant access.
- Resource links can target work orders, documents, reports, charts, and other institutional records. Resolve them through the resource registry and preserve their authorization boundaries.

## Reliability and history

- Support persistent, searchable conversation history, stable ordering, and pagination without reordering messages already shown.
- Preserve idempotency across retries. A client never labels a message delivered before service confirmation.
- Show connection status, stale cached history, source freshness, send failures, and retry availability from service state.
- Keep composition interactive during history loading and reconnect; V2 responsiveness is the performance reference to preserve.
- Record actor, timestamp, message/conversation identity, authorization outcome, and tool-result correlation in the durable event history.

## Visual status

The interface distinguishes:
- **Functional:** verified against a connected runtime service.
- **Unavailable:** intended capability exists but its service or authorization manifest is not connected or healthy.
- **Planned:** interaction is reserved but no approved implementation is available.

A visual placeholder is never presented as live operational data.

## Backend reconciliation before API approval

The backend team will inspect and qualify existing historical Riverview database implementations before choosing schemas or creating replacements. Reconcile identity, conversation membership, retention, edit/correction/deletion semantics, search, attachments, event ordering, idempotency, capability manifests, authorization, work-resource linking, and recovery with that review.

## First acceptance milestone

Using a verified non-production source, a Steward and authorized resident exchange one durable message; both see the same sender, ordering, and service timestamp after refresh, while an unauthorized principal cannot read it. Then verify menu options differ according to actual resident capability manifests. No placeholder counts as acceptance.
