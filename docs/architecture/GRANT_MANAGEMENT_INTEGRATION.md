# R3 Grant Management — authenticated integration contract

Status: IMPLEMENTATION GATED; not deployed or accepted. 2026-11-03.
Authority: Steward-only institutional delegation administration; not resident/Grace invocable.

## Reuse rather than duplicate

R2 PR #335 introduced Settings → Permissions → Delegation Approvals with canonical read projections, request details, SHA-bound decision endpoint, and audited revocation. Relevant source: `website/v2/deployed/assets/delegation-approvals.js`, `src/riverview_core/status_dashboard/delegation_routes.py`, `delegation_projection.py`, `tests/test_delegation_routes.py`. R2 PR #345 implemented delegation lifecycle extension/upgrade/successor operations. PR #291 concerns website account roles and account access grants, which are **not** command delegation grants.

Do not transplant R2's appearance. Do not create an independent grant database or duplicate AuthorityRegistry decisions.

## Hard prerequisites

1. Site-wide R3 authentication and authorization must be independently verified. All operational pages and APIs, including Infrastructure, require the intended authenticated boundary. Do not interpret an R3 chat-only session as site-wide authentication.
2. Verify R2 deployed delegation API routes, creation of new extension requests, CSRF contract, Steward principal binding, and reverse proxy behavior. Do not assume source code is deployed.
3. Grant management is Steward-only. Non-Stewards receive 403; unauthenticated callers receive 401; no grants or metadata leak in either case. Requests require same-origin session and CSRF. Do not proxy administrative operations through generic resident tools.
4. Do not display live buttons that cannot execute safely. If prerequisites are absent, show an unavailable state, not a success or mock renewal.

## Four-grant renewal

Renew these four **distinct** action/principal/scope combinations for seven days from actual approval, unlimited successful uses (`max_uses:null`), with no privilege expansion:

| Host | Role | Principal | Action | Scope |
| --- | --- | --- | --- | --- |
| Windows | Submitter | `steward:camrui` | `comms5.command.submit.task.desktop-ja3rpnq.standard` | `host:desktop-ja3rpnq` |
| Windows | Executor | `service:command-gateway` | `comms5.command.execute.task.desktop-ja3rpnq.standard` | `host:desktop-ja3rpnq` |
| Camrui | Submitter | `steward:camrui` | `comms5.command.submit.task.camrui.standard` | `host:camrui` |
| Camrui | Executor | `service:command-gateway` | `comms5.command.execute.task.camrui.standard` | `host:camrui` |

Discover current active grants and pending successors first. Use the canonical `comms5_request_delegation_grant_change` lifecycle `change_kind:"extend"`, `duration_spec:{unit:"days",value:7}`, `max_uses:null`. This creates a **pending** request, not an active successor. Present the new request IDs and expected SHA-256 digests to the Steward; approval uses `POST /api/v1/steward/delegation-grant-requests/{literal-request-id}/decision` with `decision:"approve"`, `expected_request_sha256`, `idempotency_key`, `approval_ref`, same-origin session and `X-Riverview-CSRF` matching `rv_account_csrf`. Preserve the literal colon in `delegation-request:` identifiers; percent-encoding the colon previously produced HTTP 405.

After approval, independently read back all four active successor grants, exact actions/scopes/principals, expiration timestamps, unlimited use limits, predecessor lineage, and audit references. Report partial failures individually; do not claim four-grant success from a request-creation response.

## Interface and permanent acceptance

Use R3 Settings → Institutional → Grant Management: compact four-row status, expiry, usage, host and role, with a Steward-only Renew Four action, individual grant lifecycle controls, request review, audit/history, revocation and errors. Distinguish account access grants from institutional delegation grants.

Permanent regression tests must cover: anonymous 401; viewer 403; missing/invalid CSRF; wrong principal/scope/action rejection; no privilege expansion; fresh request IDs and hashes; stale hash denial; duplicate idempotency; pending-versus-approved distinction; partial renewal failure; unlimited usage and seven-day duration; independent four-grant readback; revocation/audit; no resident capability exposure; site-wide auth including Infrastructure; browser interaction and failure messaging. Test with isolated disposable grants, never live production mutations.

## Deployment boundary

R3 source: `ppow1/R3`; existing branch `engineering/institution-runtime-v1-20261101`. Windows command gateway → `A:\AI\Scripts\Riverview\Q2` numbered PowerShell work item → durable `Queue\Results` → established `scripts/Deploy-R3.ps1` (PowerShell 7 → `ssh camrui` → Bash). Preserve stderr/exit code, deployment SHA, process ownership checks, HTTP checks, rollback and permanent regression evidence. Deployment and visual acceptance are separate gates. **No Camrui Codex.**

Next implementation: verify and land site-wide authentication before connecting administrative delegation operations. Do not deploy grant controls until those gates pass.
