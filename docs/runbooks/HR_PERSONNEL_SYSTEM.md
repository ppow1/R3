<!-- R3 CONTROLLED DOCUMENT
File: docs/runbooks/HR_PERSONNEL_SYSTEM.md
Component: HR-OPERATIONS-RUNBOOK
Created: 2026-11-05 UTC
Purpose: R/3 HR personnel architecture, authorization, operational procedures, examples and recovery
Authority: Steward governance; Helen HR administration; production permissions are enforced by canonical grants
Source: R3 HR branch source files and verified 2026-11-05 live roundtrip
-->
# R/3 Personnel (HR) System — Engineering and Operations Runbook

**Status (2026-11-05):** R/3 HR foundation deployed and verified for Grace's *public read* access to the directory and Marie's record. A write without a grant was denied. Helen's privileged HR API, full resident onboarding, historical imports, management UI, and independent audit-ledger inspection are **not** established by this verification.

## 1. Purpose and institutional boundaries

Helen owns the authoritative R/3 personnel file system, subject to Steward oversight. Each resident has an expandable, durable personnel file that grows with employment/appointment history, responsibilities, development, training, decisions and provenance. **Riverview 1, Riverview 2 and Riverview 3 are distinct institutions**. Records brought forward from R/1 or R/2 are historical provenance, not shared live databases, inherited grants or automatic authentication. Do not collapse resident identities or overwrite historical institutional provenance.

There is no fixed roster size, fixed number of fields, or test-only HR record type. A new resident's file may start with a minimal identity and be enriched over time. Creating an HR file **does not** activate a resident, grant a credential, appoint an office, start an inference loop, or grant access to tools.

## 2. Source and deployed topology

| Component | Source / deployed location | Function |
|---|---|---|
| Record schema | `runtime/hr_records.py` | `ResidentHRRecord`, `HRField`, classification and role-sensitive view |
| Storage | `runtime/hr_store.py` | Local SQLite `HRStore`, optimistic revision control |
| Governed HR capabilities | `runtime/hr_governed_capabilities.py` | `hr.directory`, `hr.read`, `hr.save` |
| Native tool HTTP server | `runtime/tool_server.py` in deployed native release | `GET /v1/tools`, `POST /v1/tools/invoke` |
| Governed authorization | `runtime/governed_tools.py` in deployed native release | Authenticate resident, enforce exact grant, audit, reserve writes |
| HR database | `/home/admin1/.local/share/r3/hr/residents.sqlite3` | Persistent R/3 HR records; **not** in Git/web root |
| Authority database | `/home/admin1/.local/state/r3-runtime/authority.db` | Canonical resident credentials, grants and authority evidence |
| Credential directory | `/home/admin1/.local/state/r3-runtime/credentials/` | Resident credential files, directory mode 0700; files 0600 |
| Native release | `/home/admin1/.local/share/r3/releases/hr-native-010c2d971828` | Verified isolated native HR tool deployment |
| Institution release | `/home/admin1/.local/share/r3/releases/grace-33f0edb48eef` | Credential-loading module available here |
| Native service | `r3-native-tools.service` | Tool endpoint at `127.0.0.1:8765` |
| Institution service | `r3-institution.service` | Resident runtime; configured with credential directory |

Paths and releases are **observed deployment values**, not portable constants. Verify the active systemd release before using them after a deployment. The native tool server uses a different release than the institutional runtime: **do not import `runtime.resident_credentials` from the native release**.

The HR SQLite table is `hr_records(resident_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL)`. Storage has no inherent caller authorization; it must be invoked through an authenticated, governed adapter. Never expose this database via a web-served path or put confidential personnel files in Git.

## 3. Personnel record contract

```json
{
  "resident_id": "r3:marie",
  "display_name": "Marie",
  "office": "Research / Independent Review",
  "status": "onboarding",
  "schema_version": 1,
  "fields": {
    "role": {"value": "Research / Independent Review", "classification": "public"}
  },
  "extensions": {
    "training": {"value": {"course": "Example"}, "classification": "request"}
  },
  "history_refs": ["estate://historical/example"]
}
```

This is an **illustrative serialization**, not a claim that these extensions/history entries exist in Marie's live record. `resident_id`, `display_name` and `office` must be nonempty. `status` defaults to `onboarding`; `schema_version` currently accepts **1 only**. `fields` and `extensions` hold arbitrary named `HRField` values with a classification. Duplicate names across those two maps are invalid. `history_refs` stores references to provenance, not automatically fetched or verified history. No fixed list of allowable extension names exists.

Classifications:
- `public`: visible in the resident/public view.
- `request`: visible to a server-verified `approved_requester` only for explicitly approved field names.
- `confidential`: visible only to server-verified `helen` or `steward` role views.

The record's top-level `resident_id`, `display_name`, `office`, `status` and `schema_version` are returned by `view()` regardless of field classification. **Do not place confidential details in those top-level values.** Unknown roles or classifications fail closed. The `view(role=...)` function is a data projection, **not an authentication system**. Never accept the role or approved field list directly from an untrusted client.

### Revision control

`HRStore.put(record, expected_revision=None)` creates a new record at revision 1 only if it does not exist. Updating an existing record requires the exact current `expected_revision`; a mismatch raises a revision conflict. The governed `hr.save` capability accepts the same `expected_revision` (integer >=1). Read the current revision first, then update; never bypass a conflict by silently overwriting.

## 4. Who has access — policy versus live grant

| Actor | Intended authority | What is proven operational |
|---|---|---|
| Steward | Full HR governance, approvals, personnel access, credential/grant administration | Local `admin1` Steward-controlled issuance and grant approval were used; no website HR management UI verified |
| Helen | HR file administrator, maintain personnel history and confidential fields; **not** automatically the grant issuer | `ResidentHRRecord.view(role="helen")` exists; a live authenticated Helen-specific privileged HR adapter/grants have **not** been verified |
| Grace | Director of Operations; access only under exact resident grants | **Verified:** public `hr.directory` and public `hr.read` for `r3:marie`; `hr.save` denied |
| Other residents | No implicit HR permissions; explicit least-privilege grants | Not verified |
| Approved requester | Access to approved `request`-classified fields, by field | Model supports projection; production request/approval/field-scoped API not verified |

The current `hr.directory` and `hr.read` capability executors explicitly call `record.view(role="resident")`. Thus **even a Helen credential with a matching grant would receive only the public projection via these endpoints**. Implement a separate server-verified, field-filtered privileged interface before claiming confidential HR reads work.

Grace's verified canonical identity is `resident:Grace`. Her active approved grants are:

| Tool | resource_id / resource_ref | action | operation | scope_ref |
|---|---|---|---|---|
| `hr.directory` | `r3:hr` | `hr.directory` | `read` | `r3:hr:directory` |
| `hr.read` | `r3:hr` | `hr.read` | `read` | `r3:marie` |

Grace has **no approved `hr.save` grant**. Credential and these two grants were independently checked with expiration epoch `2556161999` (2050-12-31 23:59:59 America/New_York). The long lifetime was specifically Steward-directed, not a general default. Expiration changes were made with a database backup; their administrative audit trail requires follow-up.

Registration of a tool does **not** issue authority. Authentication uses the resident bearer credential and the canonical authority; a client-supplied principal, role, grant or permission is never trusted. For a governed invocation the gateway checks exact capability, resource, action, operation, scope, authenticated principal and grant evidence. Authorization and completion events are submitted to the authority audit. Writes also reserve a durable correlation ID in an execution-attempt ledger; uncertain writes must not be blindly replayed.

## 5. HTTP tool contract

The native service binds to localhost `127.0.0.1:8765`. `GET /v1/tools` lists registered tools, **not** grants or permission to execute. `POST /v1/tools/invoke` requires this exact top-level envelope (no extra keys):

```json
{
  "tool": "hr.read",
  "params": {"scope_ref": "r3:marie", "resident_id": "r3:marie"},
  "correlation_id": "unique-stable-id-for-this-attempt"
}
```

Use HTTP `Authorization: Bearer <resident-credential>` and `Content-Type: application/json`. The correlation ID is mandatory, nonempty, at most 200 characters. For a **write**, reuse the same correlation ID when determining an uncertain outcome; never substitute a new ID to force a replay.

| Tool | Exact params | Meaning |
|---|---|---|
| `hr.directory` | `{"scope_ref":"r3:hr:directory"}` | Enumerate all stored residents, return **public** projections plus revision |
| `hr.read` | `{"scope_ref":"r3:marie","resident_id":"r3:marie"}` | Read Marie's **public** projection; scope must equal resident ID |
| `hr.save` | `{"scope_ref":"r3:marie","record":{...},"expected_revision":1}` | Authorized create/update; scope must equal record's resident ID; omit expected_revision **only for a new record** |

For `hr.save`, the record object must follow the full record contract above, including `fields` and `extensions` entries as `{"value": ..., "classification": "public|request|confidential"}`. The governed adapter declares an object schema with no extra properties at the params level.

Successful governed response: `{"ok":true,"result":{"status":"ok","authorization":{"principal_id":"resident:Grace","grant_id":"...","resource_id":"r3:hr","action":"hr.read","operation":"read","scope_ref":"r3:marie"},"correlation_id":"...","result":{...}}}`. An authorization denial is HTTP 403. An uncertain write may return HTTP 409; do not retry blindly. A 500 may represent failed execution or an uncertain write; inspect evidence before action.

## 6. Working read-only verification script (Camrui, Python)

Run on Camrui under the authorized `admin1` account. It reads the secret from the credential file **without printing it**. The module import must use the institution release.

```python
import json, sys, uuid, urllib.request, urllib.error
from pathlib import Path

institution = Path("/home/admin1/.local/share/r3/releases/grace-33f0edb48eef")
sys.path.insert(0, str(institution))
from runtime.resident_credentials import load_resident_credential
token = load_resident_credential(
    Path("/home/admin1/.local/state/r3-runtime/credentials"), "Grace"
)

def invoke(tool, params):
    payload = {
        "tool": tool, "params": params,
        "correlation_id": "hr-read-" + uuid.uuid4().hex
    }
    req = urllib.request.Request(
        "http://127.0.0.1:8765/v1/tools/invoke",
        data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + token,
                 "Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode())

for name, params in [
    ("hr.directory", {"scope_ref": "r3:hr:directory"}),
    ("hr.read", {"scope_ref": "r3:marie", "resident_id": "r3:marie"}),
]:
    code, body = invoke(name, params)
    assert code == 200 and body.get("ok") is True, (name, code, body)
    auth = body["result"]["authorization"]
    assert auth["principal_id"] == "resident:Grace"
    assert auth["action"] == name and auth["operation"] == "read"
    print(name, "PASS", "scope:", auth["scope_ref"])
print("HR_READ_ROUNDTRIP=PASS")
```

**Windows PowerShell 7 wrapper:** save the Python example locally as `hr-read-check.py`, then use this clipboard-first remote pattern (do not paste credential contents):

```powershell
Clear-Host
$Encoded = [Convert]::ToBase64String(
    [Text.Encoding]::UTF8.GetBytes((Get-Content ./hr-read-check.py -Raw)))
$Output = & ssh -o BatchMode=yes camrui "echo '$Encoded' | base64 -d | python3" 2>&1
$Code = $LASTEXITCODE
$Report = ($Output | Out-String) + "`nSSH_EXIT_CODE=$Code"
Set-Clipboard -Value $Report
Write-Output $Report
```

### Unauthorized write regression (no personnel mutation)

Under Grace's current credential, `hr.save` **must** return 403 before executing the record decoder. Use a deliberately invalid record so a mistaken authorization does not silently change an HR file:

```python
code, body = invoke("hr.save", {
    "scope_ref": "r3:marie", "record": {}
})
assert code == 403 and body.get("ok") is False, (code, body)
print("UNAUTHORIZED_HR_WRITE_DENIED=PASS")
```

This denial test only establishes that the *current* caller lacks write permission; it is not a substitute for independent checking of the HR database or audit trail.

## 7. Controlled HR write example — **not approved for Grace**

This is an **example payload only** for a future authenticated, explicitly granted HR writer. Do **not** execute using Grace's credential or assume Helen has already been provisioned. First obtain Steward approval for the exact resident, `resource_id=r3:hr`, `action=hr.save`, `operation=write`, and `scope_ref=r3:<resident>`. Read the current revision, secure the authorized HR data, then invoke:

```json
{
  "tool": "hr.save",
  "params": {
    "scope_ref": "r3:example",
    "expected_revision": 3,
    "record": {
      "resident_id": "r3:example",
      "display_name": "Example Resident",
      "office": "Example Office",
      "status": "onboarding",
      "schema_version": 1,
      "fields": {
        "role": {"value": "Example Office", "classification": "public"}
      },
      "extensions": {
        "training": {"value": {"course": "Example"}, "classification": "confidential"}
      },
      "history_refs": []
    }
  },
  "correlation_id": "unique-durable-write-operation-id"
}
```

The `expected_revision=3` above is illustrative; it **must match the actual current revision**. For first creation, omit `expected_revision`. An authorized writer must have the **specific** `hr.save` grant for that scope. Successful write returns resident ID and new revision inside the governed result. No general-purpose grant or cross-institution wildcard should be inferred.

## 8. Credential and grant administration

Steward-controlled local provisioning used the canonical `R3GrantManagement` API, with an explicit local `admin1` administrative trust decision. It is **not** the same as a website-authenticated Steward session.

- `issue_resident_credential(steward_context=..., resident_principal="resident:Grace", expires_at=..., reason=..., idempotency_key=...)`
- `request(steward_context=..., target_principal="resident:Grace", resource_ref="r3:hr", action="hr.read", operation="read", scope_ref="r3:marie", reason=..., idempotency_key=..., expires_at=...)`
- `decide(steward_context=..., request_id=..., approve=True, reason=...)`

The `R3GrantManagement` constructor requires a canonical `R3Authority` and server-verified Steward authentication callback. Do **not** create an unconditional callback that returns Steward for arbitrary callers. Never print, paste, commit or log resident credential tokens. Do not write credentials into the HR database. Do not silently modify grants directly in SQLite; any emergency direct DB edit requires a backup, explicit Steward approval, independent verification and audit remediation.

To add another resident: establish the correct R/3 identity; create their HR file (authorized writer only); separately provision credential if operationally required; request and approve **exact** grants; configure runtime credential delivery; test authorized and denied operations; independently inspect audit; then mark onboarding complete. Personnel creation and technical activation are separate decisions.

## 9. Deployment and service checks

The deployed HR adapter was installed in an isolated native tools release at commit `010c2d971828b5555ef8fb489673894f5b21c47e` on branch `engineering/hr-foundation-grace-marie-20261105`. It registers HR tools into the existing governed gateway and uses the existing identity, authority, audit and write ledger. The native server must register the HR adapter against the **existing** HR database; registration does not create the database.

Read-only checks:

```bash
systemctl is-active r3-native-tools.service r3-institution.service
systemctl cat r3-native-tools.service
systemctl cat r3-institution.service
curl -fsS http://127.0.0.1:8765/v1/tools
```

Confirm `hr.directory`, `hr.read`, `hr.save` are listed, then run the authenticated script above. Tool discovery alone is **not** proof of authorization. Do not restart services, alter symlinks, or replace a release merely to diagnose a 403.

## 10. Audit, incident response and recovery

The native tool router writes a `tool_audit` entry (`at,tool,outcome`) for each invocation. The governed gateway also submits authority audit events with `principal`, `capability`, `resource_id`, `action`, `operation`, `scope_ref`, `correlation_id`, `outcome` and, when authorized, `grant_id`. Expected lifecycle includes `AUTHORIZED` and `COMPLETED`; denied attempts are `DENIED`. **Independent inspection of the stored authority audit events remains an outstanding acceptance check.** Do not claim it passed solely because the tool returned HTTP 200.

Troubleshooting:
1. **403 `Tool or arguments not authorized`:** usually wrong *router* envelope; it requires `tool`, `params`, `correlation_id`, not `name` and `arguments`. This exact error occurred during initial testing and was resolved without grant changes.
2. **403 `Resident authorization denied`:** governed path reached; inspect token validity, exact principal, grant resource/action/operation/scope, expiry/revocation and server audit. Do not issue a broader grant as a shortcut.
3. **Missing credential import:** `runtime.resident_credentials` was unavailable in the native release; import from the institution release.
4. **Credential loader TypeError:** pass a `pathlib.Path` directory, **not a string**, to `load_resident_credential(directory, "Grace")`.
5. **409/500 on write:** possible uncertain outcome; correlate ledger and DB revision before deciding whether any retry is safe.
6. **Revision conflict:** reread current record and revision, reconcile changes, seek HR approval; do not force overwrite.
7. **HR file missing or service down:** check service units, active releases, DB path and permissions. Preserve databases and authority before any rollback.

Back up the HR database and authority database separately with appropriate file permissions and restoration checks. Preserve credential files securely, never in Git. Restoring a prior authority database can revoke newer grants or resurrect stale ones; require Steward-directed recovery and independent reconciliation. Preserve R/1 and R/2 history as provenance, never silently import it as R/3 authority.

## 11. Verified acceptance and remaining work

**Verified on 2026-11-05 (live Camrui):**
- Grace credential loaded successfully.
- Native `GET /v1/tools` returned a list.
- `hr.directory` returned HTTP 200, governed authorization PASS and list.
- `hr.read` for `r3:marie` returned HTTP 200, governed authorization PASS and record with `display_name=Marie`, `office=Research / Independent Review`.
- `hr.save` with Grace credential returned HTTP 403.
- Test printed `GRACE_AUTHENTICATED_HR_ROUNDTRIP=PASS` and `SSH_EXIT_CODE=0`.
- Authority records independently showed Grace credential and both read grants active through 2050.

**Not yet verified/implemented:** independent persisted authority-audit review; Helen's authenticated private HR interface; full roster; resident self-service; field-level request approvals; write-capable onboarding for Helen; complete historical migration; GUI; credential rotation/revocation UI; operational backup/restore drill. These are not prerequisites to the **already proven Grace public-read path**, but must not be described as finished.

**Related planning:** [R/3 resident onboarding administration UI issue #33](https://github.com/ppow1/R3/issues/33); [Helen's operating guide](../HELEN_HR_GUIDE.md).
