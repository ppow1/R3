<!--
R3 CONTROLLED DOCUMENT
File: docs/runbooks/COMMAND_ACCESS_GRANTS_AND_DELEGATIONS.md
Component: STEWARD-AUTHORITY-MANAGEMENT
File Revision: 1.0.0
Created: 2026-11-04 UTC (date only)
Created By: ChatGPT GPT-6, acting on Steward instruction
Purpose: Preserve verified command-access grant procedures and R3 management acceptance requirements
Execution Model: Operational runbook; website/API implementation tracked separately
Observability: Canonical grant read-back, audit events, live website acceptance
Dependencies: Riverview canonical delegation registry, Comms5, authenticated Steward website
Authority: Steward; delegated operations only when authorized by canonical policy
Changed: 2026-11-04 UTC | R3-GRANT-RUNBOOK-MIGRATION | ChatGPT GPT-6 | Import historical November 3 procedure into R3
Supersedes: Riverview- docs/operations/command-access/README.md at commit 70375e8963d0c438fac0763009bd527f1f51d3a3 for all NEW R3 grant-management documentation; historical source retained
Contracts: Exact grant/request IDs and SHA-256, CSRF, idempotency, canonical authorization and audit
Tests: Source-content preservation and GitHub read-back; runtime acceptance remains outstanding
History/Predecessor: https://github.com/ppow1/Riverview-/blob/70375e8963d0c438fac0763009bd527f1f51d3a3/docs/operations/command-access/README.md
-->
# R3 Command Access Grants and Delegations — canonical management runbook

**Repository rule:** New grant/delegation management procedures, findings, and implementation updates belong in `ppow1/R3`. The Riverview- document below is historical evidence, not the destination for new R3 runbooks.

**Source preservation:** The full historical commissioning record follows unchanged, including its provisional qualifications, historical single-use scripts, and November 3 renewal acceptance gate. References within the imported record to relative files remain historical and should be resolved against the source repository/branch.

---

<!-- Document Revision: 1.0.0 -->

# ChatGPT ↔ Riverview Command Access — commissioning record v0.1

> **PROVISIONAL, 2026-10-26.** This records the working Windows path and the commissioning chronology. Facts labeled *reported* came from Windows/Camrui Codex and require source/configuration reconciliation. Do not store bearer values, private keys, or credentials in Git. This is **not yet a complete reproducible installation manual**. See [verification punch list](PUNCH_LIST.md).

## Navigation and operating baseline

**Verified live from ChatGPT Comms5:** `ChatGPT → Comms5 → Riverview Dashboard on Camrui → authenticated Windows agent → standard PowerShell → response/audit`.

- Windows host: `DESKTOP-JA3RPNQ`, LAN `192.168.1.88`, agent HTTPS port `8443`.
- Camrui: `192.168.1.155`; Steward Dashboard `https://192.168.1.155/`.
- Windows execution account: `desktop-ja3rpnq\riverviewcmdagent` (standard, not elevated).
- Windows agent scheduled task: `Riverview Command Gateway Agent`; executable `C:\WINDOWS\system32\cmd.exe`; arguments `/d /c ""C:\Program Files\Riverview\CommandGateway\scripts\start_windows_command_agent.cmd""`; working directory `C:\Program Files\Riverview\CommandGateway`.
- Agent Python process observed: `C:\Users\wille\AppData\Local\Programs\Python\Python312\python.exe -u "C:\Program Files\Riverview\CommandGateway\scripts\run_windows_command_agent.py"`.
- Windows agent module reported at `C:\Program Files\Riverview\CommandGateway\...` with installed `command_gateway.py` SHA-256 `B615B77F8313C30779D5ED03CD8353F380F3A86D4B62C9E488B36C999578D2EE` (exact module path to verify). Prior module backup `command_gateway.py.pre-ad764f1.bak`.
- Windows firewall: port 8443 restricted to Camrui (reported). Windows agent TLS cert issued by Riverview LAN Root CA; chain and `desktop-ja3rpnq` hostname verified. Root CA on Camrui: `/etc/riverview/command-gateway/agent-ca.pem`.
- Agent bearer installed on Camrui: `/etc/riverview/command-gateway/agent.token`, `root:root`, mode `0400`; transferred once over existing strict-host-key SSH alias from Windows via staging file `/tmp/command-gateway-agent.token.incoming`, then staged copy removed after installation (removal to verify).
- Service principal `service:command-gateway` registered through authenticated Steward POST `/api/v1/steward/service-principals/command-gateway/register`, JSON `{"confirmation":"REGISTER service:command-gateway"}`; HTTP 201 and credential_stored true. Protected credential: `/var/lib/riverview-status-dashboard/identity-credentials/service-command-gateway.credential`, owner `riverview:riverview`, mode `0400`.
- Dashboard systemd credential drop-in installed; `riverview-status-dashboard.service` restarted and authenticated agent GET returned HTTP 200. Exact drop-in file and environment key mapping to verify.
- Windows dedicated SSH identity public-key fingerprint `SHA256:mqhE3Ax4u/FDvAQlVZzw9Hs5TMO+aDtUYPdiEJqMUPo`; Camrui SSH host fingerprint `SHA256:dtKs11Qd1CyyH5nQ9z3GCB0k5XSPcYPO0OvmIoQ78mU` (Windows Codex reported). These are **not** the Windows agent HTTPS certificate fingerprint.

## Comms5 tool registration and refresh

Original conversation exposed 39 MCP tools; updated connector advertises 41, including `comms5_command_task_submit` and `comms5_command_task_status`. Older `comms5_command_submit/status` were fixed-operation probes, not general command execution. Fresh ChatGPT session initially refreshed schema; later this session also showed all 41. `comms5_capabilities` operation count is **not** MCP tool count. Tool registration, schema publication, OAuth verified caller attestation, and client schema-refresh mechanics require source verification.

Task submit parameters: `host_id`, task-specific `command`, `privilege_level`, `execution_grant_id`, `idempotency_key`. Windows standard is operational; Windows elevated unsupported. The live behavior recorded above had a 12-second synchronous limit. [PR #358](https://github.com/ppow1/Riverview-/pull/358) implements a separate asynchronous backend: it waits up to 2 seconds for fast results, then returns queued/running task IDs for status polling; the task deadline defaults to one hour (configurable up to 24 hours). It retains the 32 KiB per-stream output limit and 8,000-byte command bound, stores the command digest rather than command text, supports caller-authorized cancellation, and marks unfinished tasks interrupted on agent restart rather than replaying them. This code is not merged or deployed; C1's route restoration in #356 and a live >12-second acceptance remain outstanding.

## AuthorityRegistry and website Steward approvals

Authenticated OAuth steward is mapped by Dashboard to `steward:camrui` for command authorization. Executor is registered `service:command-gateway`. The two **separate host-scoped** grants use `policy:delegation.v1`, scope `host:desktop-ja3rpnq`, unlimited successful uses and a seven-day duration measured at approval:

| Function | Principal | Action | Request ID | Request SHA-256 | Grant ID |
| --- | --- | --- | --- | --- | --- |
| Submit | `steward:camrui` | `comms5.command.submit.task.desktop-ja3rpnq.standard` | `delegation-request:b17e212a49bc405090a6151b0631a5c1` | `27ef4abe6e6deaf174eb39887408ea1240cce1681a919880f72c28372966a5f1` | `grant:bc790c0beb1746b295aade230d4a56cf` |
| Execute | `service:command-gateway` | `comms5.command.execute.task.desktop-ja3rpnq.standard` | `delegation-request:7a7a42a08f544bd68c5a609ff9f2d59b` | `509949605b63067ba4fe1b3a55b4e60a56e3e769dc0a49241a56d251471770f4` | `grant:2c4cd34bcc484a61814f6f489f25c8f1` |

Both requests approved 2026-10-26 ~19:55 EDT and confirmed through `comms5_get_delegation_grant_status` as `approved`, `IMPLEMENTED`. These are historical identifiers, **not reusable installation defaults**. Use authenticated Steward website with CSRF and exact request digest for approval: POST `/api/v1/steward/delegation-grant-requests/{literal-request-id}/decision`; body `decision:approve`, `expected_request_sha256`, `idempotency_key`, `approval_ref`. Do not percent-encode the colon in `delegation-request:` for this route (encoded colon produced 405). Grant renewal, extension, revocation and different durations must be independently verified in the canonical registry.


## Steward browser-console grant approvals — verified November 2026

Both scripts below use the R2 authenticated Steward session, cookie `rv_account_csrf`, header `X-Riverview-CSRF`, exact digest and literal unencoded `delegation-request:` path. They are historical, single-use request approval records, **not** reusable grant-creation or renewal scripts. The permanent website UI for dynamic renewals remains outstanding. Do not store session cookie values in Git.

### Windows / desktop-ja3rpnq — 2026-11-03 approved request replay (historical)

The following is the **exact-request approval procedure**, not a weekly renewal generator. These request IDs and SHA-256 values were used for the November 2026 renewal; the registry reports the approvals as implemented. Re-running cannot create new seven-day renewals. Use only against the matching pending requests, on the authenticated R2 Steward Dashboard; do not use for future renewal requests without replacing IDs/digests from live registry.

```javascript
(async () => {
  const csrf = document.cookie.split("; ")
    .find((part) => part.startsWith("rv_account_csrf="))
    ?.split("=").slice(1).join("=");

  if (!csrf) {
    console.error("rv_account_csrf not found; no requests sent.");
    return;
  }

  const requests = [
    {
        "id": "delegation-request:7bda65d27b5040ad85a5931e3cfa64f8",
        "digest": "55c167051c9627b2be8f62a19522c0eadccc8f2ebed20dce035aaa132de77483",
        "key": "steward-console-windows-submit-renewal-20261103",
        "approval": "steward-console:windows-submit-renewal-2026-11-03"
    },
    {
        "id": "delegation-request:dc8e90694d3c4cacba9860373648a9b5",
        "digest": "8f78d8335ae961140c9875f7f00a81760f500ea98b7bfd54d7987bb6cd2e4d2d",
        "key": "steward-console-windows-execute-renewal-20261103",
        "approval": "steward-console:windows-execute-renewal-2026-11-03"
    }
];

  for (const item of requests) {
    // Preserve the literal colon in delegation-request:; encoding it produced HTTP 405.
    const response = await fetch(
      `/api/v1/steward/delegation-grant-requests/${item.id}/decision`,
      {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-Riverview-CSRF": csrf
        },
        body: JSON.stringify({
          decision: "approve",
          expected_request_sha256: item.digest,
          idempotency_key: item.key,
          approval_ref: item.approval
        })
      }
    );
    console.log(item.id, response.status, await response.text());
    if (!response.ok) {
      console.error("Approval failed; stopping.");
      break;
    }
  }
})();
```

### Camrui — 2026-11-03 approved request replay (historical)

The following is the **exact-request approval procedure**, not a weekly renewal generator. These request IDs and SHA-256 values were used for the November 2026 renewal; the registry reports the approvals as implemented. Re-running cannot create new seven-day renewals. Use only against the matching pending requests, on the authenticated R2 Steward Dashboard; do not use for future renewal requests without replacing IDs/digests from live registry.

```javascript
(async () => {
  const csrf = document.cookie.split("; ")
    .find((part) => part.startsWith("rv_account_csrf="))
    ?.split("=").slice(1).join("=");

  if (!csrf) {
    console.error("rv_account_csrf not found; no requests sent.");
    return;
  }

  const requests = [
    {
        "id": "delegation-request:272a96432f9e4fb3bf10f31016b7fe0b",
        "digest": "bdee58be69ccb71b63afc6fd569df93934514af852bce0c12c63a2f9becfd035",
        "key": "steward-console-camrui-submit-renewal-20261103",
        "approval": "steward-console:camrui-submit-renewal-2026-11-03"
    },
    {
        "id": "delegation-request:e2abebe354da4329b4e57e2771a2f9a2",
        "digest": "89e2c8f315031d41bb8e360a64cc5d0ba8bf7262b85d5744eae3378d9e225d8d",
        "key": "steward-console-camrui-execute-renewal-20261103",
        "approval": "steward-console:camrui-execute-renewal-2026-11-03"
    }
];

  for (const item of requests) {
    // Preserve the literal colon in delegation-request:; encoding it produced HTTP 405.
    const response = await fetch(
      `/api/v1/steward/delegation-grant-requests/${item.id}/decision`,
      {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-Riverview-CSRF": csrf
        },
        body: JSON.stringify({
          decision: "approve",
          expected_request_sha256: item.digest,
          idempotency_key: item.key,
          approval_ref: item.approval
        })
      }
    );
    console.log(item.id, response.status, await response.text());
    if (!response.ok) {
      console.error("Approval failed; stopping.");
      break;
    }
  }
})();
```

Registry verification on 2026-11-03: Windows submitter `grant:821fffd983ad4dbcaf57d084aab3cf0a` and executor `grant:9a4e87ce7bd84bd196e941a0d8a315bd` active through 2026-11-09 ~20:12 EST; Camrui submitter `grant:dd4ded3b165f4435b29fe78d184132ed` and executor `grant:be2d2a60f99048ad9237a28fe938d080` active through 2026-11-10 ~19:11 EST. All four have `max_uses: null`, `status: active`, `implementation_status: IMPLEMENTED` at verification time.


## R2 grant-management audit and permanent four-grant renewal acceptance

**Steward requirement, 2026-11-03:** One authenticated R2/R3 website action must renew all four *current* standard command grants (Windows submitter/executor and Camrui submitter/executor) for **seven days from approval**, with **unlimited successful executions**. This is a live grant-management workflow, not replay of the four historical November 2026 approval requests above. The historical F12 scripts are preserved solely as recovery evidence; do not describe them as a reusable renewal command.

**Verified backend contracts:** Comms5 `comms5_get_delegation_grant_status` reads an exact grant or request; `comms5_request_delegation_grant_change` supports `change_kind: extend`, `duration_spec: {unit: "days", value: 7}`, `max_uses: null`, exact action/scope/policy and creates a **pending successor**, not approval. Authenticated R2 Steward approval uses `POST /api/v1/steward/delegation-grant-requests/{literal-request-id}/decision` with `decision: approve`, `expected_request_sha256`, `idempotency_key`, `approval_ref`, `rv_account_csrf` cookie and `X-Riverview-CSRF` header. **Never percent-encode the colon** in `delegation-request:` (observed HTTP 405). The browser-accessible endpoint to create extension requests and enumerate the four current grants **has not been verified**; do not invent it.

| Host | Grant role | Principal | Action | Scope |
| --- | --- | --- | --- | --- |
| Windows | Submitter | `steward:camrui` | `comms5.command.submit.task.desktop-ja3rpnq.standard` | `host:desktop-ja3rpnq` |
| Windows | Executor | `service:command-gateway` | `comms5.command.execute.task.desktop-ja3rpnq.standard` | `host:desktop-ja3rpnq` |
| Camrui | Submitter | `steward:camrui` | `comms5.command.submit.task.camrui.standard` | `host:camrui` |
| Camrui | Executor | `service:command-gateway` | `comms5.command.execute.task.camrui.standard` | `host:camrui` |

**Required behavior:** Discover current active grant IDs and expiry; identify any pending successor and reconcile without duplicates; create missing extension requests with fresh idempotency keys; display all four exact request IDs and digests for the Steward's authenticated approval; approve each through existing AuthorityRegistry; read back the resulting four successor grants and show actual expiry, unlimited use, principal, action, scope, and audit trail. Fail closed and visibly report partial approvals or unavailable services. Do not bypass Steward approval, change principal identity, widen scope, or silently mark incomplete renewal as successful. Preserve revocation, duration selection, use-limit selection, grant history, and audit controls from R2.

**R2 inspection status:** The existing dashboard and documented grant-approval route demonstrate partial management functionality. Full deployed UI/source inspection is **not verified**. Two read-only Camrui command submissions on 2026-11-03 were authorized by both new grants but the host gateway returned `bounded_request_or_state_invalid` with exit code 2; no website source was retrieved. Determine whether this is a command transport/policy issue before assuming missing R2 features.

**Website UX direction:** Use R2 as a functional inventory, **not** a visual clone. Provide a clean Steward-only Grant Management page with four grouped grant rows (Windows/Camrui × submitter/executor), concise expiry/status indicators, a prominent **Renew all four — 7 days / unlimited** confirmation action, and expandable details for individual extension, revoke, usage, request/approval history and errors. Avoid raw debug tables and console-first operation. Provide authenticated API hooks for Grace and Steward, with the same authority enforcement. The one-paste F12 command remains a documented emergency fallback, not the normal UX.

**Acceptance gate:** Verify live website request creation, approval, four active successors, exact seven-day expiration, unlimited use, successful Windows and Camrui task execution, rejection/partial-failure handling, permanent regression tests, and post-deployment read-back. Do not claim completion based solely on historical approvals or UI screenshots.

## Chronology: failure → correction

1. Fixed command probes were mistaken for general execution. Added task-specific submit/status tools, deployed Comms5 41-tool catalog; initial combined deployment reported `9698cf5fbf1e24c4021ae2f9d4f2c53c936f43a8`.
2. Windows agent installed with TLS, dedicated `RiverviewCmdAgent`, restricted port 8443, scheduled task. TLS succeeded but anonymous HTTPS 401 did **not** establish authentication.
3. Gateway principal registration route initially blocked by Dashboard global POST allowlist 405. Corrected; Steward owner POST returned 201 registered. Dashboard release reported `d1cb69bc653c184f484070e3db65d3e27c6b3760`.
4. Agent bearer absent on Camrui; attempts via automated SSH stdin were runner-blocked. Normal owner-authorized SSH alias transfer succeeded. C1 installed token, CA and systemd credential drop-in. Authenticated GET returned HTTP 200.
5. Caller and executor grants requested and approved. First ChatGPT command returned `NOT_AUTHORIZED`: not a missing grant, but Dashboard database role `riverview_core` lacked protected AuthorityRegistry reservation table rights. Corrected reservation/release/consume through protected AuthorityRegistry adapter with service credential; release reported `143a5b64e4dfe6ff660f08c6213cd548c9349a1f`. Do **not** widen DB role grants as workaround.
6. POST still failed, originally obscured as 503; diagnostic propagation reported Windows agent HTTP 400 `invalid_command_request`. Dashboard release reported `ad764f1cd709e29db898de878c3d23e29d6e0805`.
7. Windows Codex found older agent strict 8-field validator, while Dashboard sent three additional fields `host_id`, `transport`, `command`. Updated Windows module from deployed Dashboard code; compilation succeeded, prior module backed up.
8. Windows agent restart failed with Security event 4625, status `0xC000015B` (batch logon denied). Owner added `DESKTOP-JA3RPNQ\RiverviewCmdAgent` to **Log on as a batch job** in Local Security Policy after checking **Deny log on as a batch job**. Do not add to Deny. Task Scheduler result `267009` (`0x41301`) means task running, not necessarily failed. Python process later observed. An earlier port check showed no listener; the successful remote command later proves agent was serving requests.
9. **Live ChatGPT acceptance passed.** Submitted `hostname; whoami; $PSVersionTable.PSVersion.ToString()` via `comms5_command_task_submit`. Result `completed`, `executed:true`, exit `0`, stderr empty; stdout `DESKTOP-JA3RPNQ`, `desktop-ja3rpnq\riverviewcmdagent`, `5.1.26100.9596`. Execution ID `d12f2b65-7f15-433d-9332-feb79c7d790c`; audit event `5e313d43-30a6-4df1-a50b-9c221413f368`; executor reservation `consumed`.

**Repository caveat:** Above deployment SHAs are C1-reported, **not yet independently located in connected GitHub default branch**. GitHub repository `PPOW1/Riverview-` has relevant operational issue #343, but GitHub commit lookup for those SHAs returned not found. Reconcile branches, deployment origins and repository visibility before calling them source-verified.

## Desired owner website automation

**Commission a host once; grant access repeatedly in a few clicks.** Website should let Steward select host(s), standard/elevated capability (only if supported), duration (e.g. 1 day, 7 days, 3 months, custom), and use limit (1/N/unlimited), then approve both caller/executor grants using existing AuthorityRegistry. Show active grant pair, exact principal/action/scope, activation/expiry, usage, audit and immediate revoke/extend. Do not regenerate CA, agent credentials or reinstall service for each grant. Separate machine enrollment and transport readiness from temporary access authorization. Reuse existing #343 grant lifecycle rather than new grant architecture. Verify true expiry/revocation on both caller and executor; prevent one-sided grants and partial activation.

## Next phase (not yet commissioned)

Camrui SSH task execution: verify actual agent SSH account, pinned host key and authorized noninteractive identity, host mapping, command handler, Camrui-specific caller/executor grants and sudo boundary for elevated commands. Do not claim operational until ChatGPT submits and receives an actual SSH command. Async execution is implemented for review in #358 but awaits #356 route integration, merge, and live >12-second acceptance. Windows elevated PowerShell remains separate work.

## Documentation evidence and completion

This file is a *publishable historical checkpoint*, not proof every installation detail is reproduced. [PUNCH_LIST.md](PUNCH_LIST.md) tracks missing exact files, code paths, deployment SHAs, tests, recovery, website UI and evidence. Every future correction should update this document and close the matching punch-list entry; do not reconstruct from chat again.
