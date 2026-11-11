<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_NOTIFICATION_AP3_PRINCIPAL_HANDOFF.md
Component: R3A-NOTIFICATION-WEBSITE-INTEGRATION
File Revision: 1.0.0
Created: 2026-11-11 UTC
Created By: Codex GPT-6
Purpose: Hand off generic CME/AP3 principal requirements and safe notification read activation.
Execution Model: Existing CME capability registry and AP3 Website session boundary.
Observability: CME grant decision/audit reference plus notification-owned lifecycle evidence.
Dependencies: R3A capability-operation v1.1; AP3 session; notification-inbox v1; Issue #51.
Authority: Steward follow-up #48 comment 6784755797.
Changed: 2026-11-11 | Issue #48 | Record exact principal contract gate, test cases, and read activation procedure.
Supersedes: Unspecified AP3 principal integration handoff.
Contracts: notification.delivery.read; notification.delivery.acknowledge; notification.delivery.resolve.
Tests: tests/test_r3a_notification_capability.py.
History/Predecessor: R3A_STEWARD_WORKSPACE_WEB_API_V1.md.
-->
# AP3 principal binding for notification capabilities

## Current behavior and boundary

The Website obtains `principal_id` from `StewardAccess.authenticated_principal()` and supplies it in the server-created `capability.invoke` request. It never accepts a caller identity from browser input. CME authorizes the exact capability grant before invoking the provider. The notification provider uses `context.caller.principal_id` as the `NotificationStore` recipient and writes CME's successful decision and audit reference into lifecycle records. The store continues to enforce recipient ownership independently.

`notification.delivery.read` is a direct-principal, read-only operation. Its pinned manifest uses effect `read`, exact required grant `notification.delivery.read`, and no static caller allowlist. This follows the existing direct-principal read path. The standard configuration loader accepts the manifest and registers it through `capability_operations`; the regression verifies this. Registration is not activation or proof that an exact grant exists in the managed runtime.

For `steward_write`, the current `validate_operation()` requires a non-empty `caller_constraints.allowed_principals` array. `validate_invocation_request()` then compares the caller string to that static list. This cannot express the Website's per-request AP3-authenticated Steward principal without a static identity roster. Empty arrays are rejected; wildcard strings are exact strings, not patterns. Do not hardcode people, use wildcards, or broaden the capability grant to get around this limitation.

## Generic CME contract-owner requirements

The capability contract owner should select and review the smallest existing-contract-compatible mechanism that allows the generic capability authorizer to bind a server-injected AP3 session principal while retaining all of the following:

- An authenticated AP3 Steward principal is established server-side; an input-body or browser-supplied principal is rejected or ignored.
- CME still makes and persists the decision for the exact operation grant (`notification.delivery.acknowledge` or `notification.delivery.resolve`).
- A principal with no matching grant is denied. A non-Steward or unauthenticated request is denied.
- The provider receives the same principal that CME authorized, plus a successful decision ID and audit event ID.
- The notification store independently rejects a principal who does not own the delivery.
- Acknowledgment and resolution retain stable idempotency, ordered state transitions, lifecycle events, and existing ownership.
- No `*`, identity bypass, new authorization store, route-specific CME branch, or notification-only identity protocol is introduced.

The notifications branch adds characterization tests for today's static constraint: empty `allowed_principals` fails descriptor validation; an explicit test principal passes; a different principal fails invocation validation. When the generic correction is available, the required acceptance tests are: authorized AP3 session plus exact grant succeeds; authenticated principal without exact grant is denied; non-Steward/unauthenticated caller is denied; spoofed browser principal cannot change the caller; a different notification recipient remains denied; and persisted actor/authorization references equal the CME-authorized session principal and decision.

## Safe read registration path

The pinned manifest is `r3a_plugins/notification_service/manifest.read.json`; its provider configuration example is `r3a_plugins/notification_service/capability.config.example.json`. To prepare an external bootstrap candidate:

1. Preserve existing module capabilities and add `notification.delivery.read` to the configured module capability references.
2. Add one standard `capability_operations` entry pointing to the absolute manifest path and a deployment-local copy of the example configuration. The config contains only the DSN environment variable name and presentation timezone; keep the DSN value in the provider process environment, never in bootstrap or Git.
3. Confirm the provider module's existing process environment allowlist admits only `R3A_NOTIFICATION_DATABASE_DSN` for this store connection.
4. Confirm the authorization provider has the exact `notification.delivery.read` grant for the intended AP3 Steward principal. Do not infer a grant from registry presence or the manifest's `required_grants` field.
5. Run the standard settings/registry validation, verify the registered provider digest and configuration revision, then use existing CME provider lifecycle operations to activate it. Do not change CME/Ring0 source or use the standalone fixed-principal HTTP service for the Website route.
6. After deployment, test a real AP3 session with at least one real delivery and verify recipient scope, source provenance, freshness, and audit correlation. This repository has no managed DSN, active grant, or authenticated browser session; no live acceptance is claimed here.

Acknowledgment and resolution stay unregistered until the generic principal constraint is reviewed and available. Then add their exact operation manifests, register exact grants, deploy Website and provider configuration through their owners, and run the authorized live lifecycle acceptance.
