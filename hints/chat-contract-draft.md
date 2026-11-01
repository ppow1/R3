<!--
R3 CONTROLLED DOCUMENT
File: hints/chat-contract-draft.md
Component: R3-CHAT-CONTRACT-DRAFT
File Revision: 1.0.0
Created: 2026-11-01 UTC (date precision)
Created By: ChatGPT GPT-6
Purpose: Define a reviewable interaction contract for R3 chat across the website and authorized resident tools
Execution Model: Draft capability boundary; no implementation or live API implied
Observability: Conversation and message lifecycle events must be auditable and queryable
Dependencies: Approved R3 charter revision 2; R3-P002; R3-P005; R3 capability and authorization architecture
Authority: Working draft only. Steward and runtime architecture review required before API adoption.
Changed: 2026-11-01 UTC | R3-COMMS-CHAT-DRAFT-001 | ChatGPT GPT-6 | Establish initial chat interaction contract draft
Supersedes: None; new draft
Contracts: docs/PROJECT_CHARTER_REVISION_2_REVIEW.md; docs/PUNCH_LIST.md
Tests: Not run; contract only
History/Predecessor: N/A; new document
-->
# R3 chat interaction contract — draft

**Status:** Review draft. This document defines expected behavior and shared concepts; it is not an approved backend API or a claim that chat services are implemented.

## Purpose

R3 chat is a durable institutional capability. The website, Grace, authorized residents, and other clients use the same permission-checked service. The browser is a client, not the system of record. Conversation history and operational events must survive browser refreshes and service restarts according to the R3 persistence and recovery design.

## Shared concepts

The service should represent conversations, participants, messages, ordered lifecycle events, optional authorized attachments, and tool requests linked to their originating message and execution record. Conceptual message data includes identity, conversation, sender, content, service timestamp, and delivery or failure state. These are semantic requirements, not proposed wire-format names. Canonical schemas and identifiers must come from the runtime and database architecture.

## Client behavior

- List conversations the caller may access; open a conversation; fetch history in stable order; send a message; and receive new messages and status changes through an API-backed event or subscription hook.
- Show sending, delivered, failed, and retryable states only when the service reports them. Preserve a message identity or idempotency token across retries to prevent duplicate sends.
- Show participant identity and message time. Make missing, delayed, or stale service state visible.
- Keep composition usable while history loads. Paginate older history without reordering rendered messages.
- Render attachments only through safe, authorized capabilities. A UI control never grants access by itself.

## Resident and tool access

- Grace and residents use the same conversation and capability service as the website, subject to their identities, permissions, and audit records.
- Tool use is separate from sending text. A message may request an action, but the service resolves the capability, checks current authorization, and records the outcome. The interface displays pending, denied, executing, succeeded, and failed states only from authoritative service events.
- Any required Steward approval uses the existing authorization flow; chat creates no alternate approval path.
- Callers may only read or act in conversations and attachments permitted by the authorization service. An identifier alone does not grant access.

## Freshness, failures, and audit

- The service reports connection and source freshness. Clients distinguish current data from stale cached history and unavailable service state.
- Failed sends remain visible with a clear retry path. The client does not claim delivery before confirmation.
- Durable event history preserves ordering, actor, timestamps, and correlation between messages, tool requests, authorization, and execution results.
- No synthetic conversation, resident activity, delivery, or tool result is presented as live runtime data.

## Decisions required before API approval

1. Reconcile conversation, participant, message, event, attachment, and tool activity records with the R3 database and historian.
2. Define identity, membership, visibility, retention, correction/deletion, and attachment access rules.
3. Select authoritative send/history operations, the event/subscription mechanism, and freshness/reconnect semantics.
4. Reconcile tool invocation and approval references with the capability registry, policy service, and execution records.
5. Specify ordering, pagination, idempotency, and audit guarantees supported by the runtime.

## First acceptance milestone

Using a verified non-production runtime source, a Steward and one authorized resident exchange one durable message. Both clients observe the same sender, conversation, message ordering, and service timestamp after refresh; an unauthorized principal cannot read it. A placeholder event does not count as acceptance.
