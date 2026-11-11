<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_NOTIFICATION_DELIVERY_V1.md
Component: R3A-AP1-NOTIFICATION-DELIVERY
File Revision: 0.1.0
Created: 2026-11-08
Purpose: Specify the AP1-N2 recipient delivery projection and Steward website handoff.
Authority: R3A Baseline 1.0, AP1, R3A-019; Steward continuation directive and Issue #48.
Contracts: r3a.notification-delivery.v1; r3a.institutional-directory.v1; r3a.authorization-decision.v1.
Status: Local routing/config and durable event-ledger methods implemented; CME control/API principal binding and website adapter pending coordinator interface confirmation.
-->
# R3A Notification Delivery v1

N1 remains the source notification contract and Grace activity lineage. N2 adds a recipient delivery projection. `r3a.notification-delivery` version `1.0.0` carries stable delivery identity, source and correlation references, directory-derived recipient identity, severity, urgency, whether action is required, lifecycle status, timestamps, and evidence references. Delivery identity is stable for `(notification event, recipient kind, recipient ID)`, so replay does not create a second recipient item.

Routing rules are external bootstrap configuration. A rule matches source and event type, then selects directory records by `office_role`; it does not contain resident IDs. Only active office/resident bindings in a fresh `r3a.institutional-directory.v1` snapshot can be selected. Missing, stale, or unavailable directory data must leave delivery blocked/pending with evidence; callers must not substitute a locally copied roster. An unmatched rule returns no recipient and must be recorded as an explicit no-route outcome by its caller.

Example configuration:

```json
{
  "notification_delivery": {
    "contract_id": "r3a.notification-delivery",
    "contract_version": "1.0.0",
    "rules": [
      {
        "source_id": "r3a.institution-events",
        "event_type": "process.failed",
        "recipient": {"kind": "steward", "office_role": "Steward"},
        "urgency": "critical",
        "requires_action": true
      },
      {
        "source_id": "r3a.institution-events",
        "event_type": "process.restarted",
        "recipient": {"kind": "office", "office_role": "Operations"},
        "urgency": "normal",
        "requires_action": false
      }
    ]
  }
}
```

## Steward website handoff proposal

The current primary Steward site exposes only the existing read APIs and has no notification route or authenticated identity binding. The following JSON API shape is a handoff proposal, not an implemented or remotely exposed interface:

| Operation | Request | Result |
| --- | --- | --- |
| `GET /api/v1/notifications` | Authenticated caller identity comes from the approved session; recipient ID is not caller-supplied. Optional status, severity and page cursor. | `r3a.notification-inbox.v1`: caller-visible deliveries, recipient scope, source/correlation, severity/urgency/actionable, current lifecycle state, timestamps, evidence references and next cursor. |
| `POST /api/v1/notifications/{delivery_id}/acknowledgment` | Idempotency key and optional note/evidence reference. | Durable acknowledged state, actor identity, authorization decision/audit reference and timestamp. |
| `POST /api/v1/notifications/{delivery_id}/resolution` | Idempotency key, disposition and evidence references. | Durable resolved state or explicit rejection/blockage with actor and authorization provenance. |

Each operation must enter CME and use existing capability grants (`notification.delivery.read`, `.acknowledge`, `.resolve`). Recipient visibility is checked against the directory-derived delivery recipient; office-scoped visibility requires a current directory binding. The CME event ledger remains the history authority. A website adapter must not write notification state directly or infer acknowledgment from a page view. Until identity binding and endpoint ownership are confirmed, these operations stay local contracts and are not activated.

## Current verification boundary

The current N2 Store methods write delivery queue, acknowledgment, and resolution events to `r3a.institution_events`; inbox reads filter against the current directory projection and require an allowed CME `notification.delivery.read` decision. These are interim methods inside the present core pending coordinator agreement on the generic event/activity boundary proposed in the #43 modularity audit. Do not add another intake or persistence branch while preparing that boundary. The methods are not yet invoked by a connected recipient/API adapter. The directory provider contract and synthetic response are covered by local tests. The documented live directory provider is unavailable until a least-privilege Riverview credential is configured. `r3_app.py` currently has no notification inbox or authenticated write endpoints. Therefore no real recipient delivery, website visibility, or live authorized recipient action has yet been demonstrated. Do not report this contract work as managed-runtime integration.
