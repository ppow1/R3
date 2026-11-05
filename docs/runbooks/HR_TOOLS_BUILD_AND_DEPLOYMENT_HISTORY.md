# R/3 HR tools — build, deployment and verification history

**Purpose:** chronological engineering record of how the R/3 HR tools were built and deployed, separate from the HR operations manual and Helen's guide. **Date:** 2026-11-05. **Branch:** `engineering/hr-foundation-grace-marie-20261105`.

**Evidence:** GitHub commits establish source changes; Camrui diagnostics establish the deployed behavior. Some original terminal commands were not retained; these are explicitly identified rather than fabricated.

## 1. Build the personnel model

1. Create `runtime/hr_records.py`: `HRField` with classifications `public`, `request`, `confidential`; `ResidentHRRecord` with ID, display name, office, onboarding status, schema version, extensible fields/extensions, and history references. Implement `view(role=...)` with fail-closed disclosure rules. This layer is not an authenticator.
2. Add `tests/test_hr_records.py` covering classification, role views, extension fields, historical references and invalid classifications.
3. Create `runtime/hr_store.py` using SQLite `hr_records(resident_id, revision, payload)`. Implement `get`, `put`, `resident_ids`, revision-conflict enforcement. The live HR DB is `/home/admin1/.local/share/r3/hr/residents.sqlite3`. No roster-size cap or cross-institution live dependency.
4. Seed the initial Grace and Marie records as the R/3 foundation. These are not a fixed or test-only roster. Personnel file creation is distinct from resident activation or granting tools.

## 2. Implement the native capabilities, then replace the first adapter

5. First adapter: commit [0d55aa0](https://github.com/ppow1/R3/commit/0d55aa05e39a33d49aab73d1359eb654515bab30), `runtime/hr_native_capabilities.py`, described the three native tools via `Capability`. It did not create a listener or independent grant authority.
6. Production adapter: commit [010c2d9](https://github.com/ppow1/R3/commit/010c2d971828b5555ef8fb489673894f5b21c47e), `runtime/hr_governed_capabilities.py`. It registers `GovernedCapability` instances into the existing `GovernedToolGateway` using `register_hr_governed_tools(gateway, database)`. **This is the deployed implementation**; do not wire the superseded adapter alongside it.
7. Exact capability definitions:
   - `hr.directory`: resource `r3:hr`, action `hr.directory`, operation `read`, scope `r3:hr:directory`.
   - `hr.read`: resource `r3:hr`, action `hr.read`, operation `read`, scope equal to the requested resident ID.
   - `hr.save`: resource `r3:hr`, action `hr.save`, operation `write`, scope equal to the record resident ID.
8. Directory and read always use `record.view(role="resident")`: **public projection only**. Save decodes a full record and uses revision-checked `HRStore.put`. Registration never issues credentials or grants.

## 3. Deploy on Camrui

9. The deployed native release was `/home/admin1/.local/share/r3/releases/hr-native-010c2d971828`. The `r3-native-tools.service` listens at `127.0.0.1:8765`. Its `runtime/tool_server.py` was wired to call `register_hr_governed_tools(gateway, "/home/admin1/.local/share/r3/hr/residents.sqlite3")` on the **existing** governed gateway. That gateway uses resident identity authentication, canonical `R3Authority`, authority audit and `ExecutionAttemptLedger`. The `ToolRouter` receives `governed=gateway`.
10. The HR SQLite file must exist before registration; the adapter raises `FileNotFoundError` otherwise. The original database-creation, immutable-release-copy, systemd-edit and restart commands were **not preserved verbatim**. Verify the active units before any redeployment:

```bash
systemctl cat r3-native-tools.service
systemctl cat r3-institution.service
systemctl is-active r3-native-tools.service r3-institution.service
curl -fsS http://127.0.0.1:8765/v1/tools
```

11. Live `GET /v1/tools` listed all three HR tools. Discovery does **not** establish permission to invoke them.

## 4. Provision Grace's credential and exact grants

12. Canonical authority DB: `/home/admin1/.local/state/r3-runtime/authority.db`, mode 0600. Credential directory: `/home/admin1/.local/state/r3-runtime/credentials`, mode 0700; Grace's credential file mode 0600. An initial permissions issue was corrected.
13. Steward approved local `admin1` SSH administration rather than waiting for the website UI. The original script verified local administrative context and used canonical `R3GrantManagement` with a narrowly scoped Steward callback. This local-admin trust decision is **not website authentication**. The exact original script is unavailable; do not invent a permissive callback or print credentials.
14. Canonical API methods used: `issue_resident_credential(steward_context, resident_principal, expires_at, reason, idempotency_key)`; `request(steward_context, target_principal, resource_ref, action, operation, scope_ref, reason, idempotency_key, ...)`; `decide(steward_context, request_id, approve, reason)`.
15. Principal `resident:Grace` received exactly two approved grants: `hr.directory/read/r3:hr:directory` and `hr.read/read/r3:marie`, both on `r3:hr`. **No `hr.save` grant** was issued.
16. Institution service `r3-institution.service` was restarted with `--resident-credential-dir /home/admin1/.local/state/r3-runtime/credentials`. The observed institution release was `/home/admin1/.local/share/r3/releases/grace-33f0edb48eef`. This release contains `runtime.resident_credentials`, unlike the native release.
17. The initial ~30-day expiration was changed at the Steward's explicit direction to **2050-12-31 23:59:59 America/New_York**. A backup was made under `/home/admin1/.local/state/r3-runtime/backups/authority-before-grace-2050-*.db`. A narrowly scoped SQLite change updated Grace's credential and two grants; this exceptional direct edit needs administrative audit remediation and must **not** be used as routine grant management.
18. The first expiry script ended with shell heredoc failure after the change; independent read-only verification returned `GRACE_CREDENTIAL_2050=PASS`, `GRACE_HR_GRANTS_2050=PASS`, `READ_ONLY_VERIFICATION=PASS`, `SSH_EXIT_CODE=0`.

## 5. Diagnose the actual HTTP contract — failures and corrections

19. First preflight failed `ModuleNotFoundError: runtime.resident_credentials`: it imported from the wrong (native) release. Correct: import from the **institution** release.
20. Next preflight failed `TypeError: unsupported operand type(s) for /: 'str' and 'str'`: `load_resident_credential` expects a `pathlib.Path`, not a string.
21. Correct loader:

```python
import sys
from pathlib import Path
sys.path.insert(0, "/home/admin1/.local/share/r3/releases/grace-33f0edb48eef")
from runtime.resident_credentials import load_resident_credential
token = load_resident_credential(
    Path("/home/admin1/.local/state/r3-runtime/credentials"), "Grace"
)
```

22. Corrected preflight returned `GRACE_CREDENTIAL_LOAD=PASS`, `LIVE_TOOL_DISCOVERY=PASS`, `CATALOG_TYPE=list`, `VERIFICATION_PREFLIGHT=PASS`, `SSH_EXIT_CODE=0`.
23. First HTTP test incorrectly used `name` and `arguments`; all three requests returned 403 `Tool or arguments not authorized`. Inspection of deployed `ToolRouter.invoke` proved the router expects `tool` and `params`. Inspection of `GovernedToolGateway.invoke` proved the **exact** top-level envelope is `tool`, `params`, `correlation_id`, plus an `Authorization: Bearer ...` header. A wrong envelope never reaches the governed capability; do **not** repair it by broadening grants.
24. Authority inspection confirmed active Grace credential and two exact grants, expiring in 2050.

## 6. Successful live invocation and regression

25. POST to `http://127.0.0.1:8765/v1/tools/invoke` with the credential in the Authorization header and a unique correlation ID:

```json
{
  "tool": "hr.read",
  "params": {"scope_ref": "r3:marie", "resident_id": "r3:marie"},
  "correlation_id": "unique-read-operation-id"
}
```

26. The test checked HTTP status, `ok`, governed result status, authenticated principal `resident:Grace`, grant ID, resource `r3:hr`, action, operation and exact scope. Then it attempted `hr.save` with `{"scope_ref":"r3:marie","record":{}}` and required a 403 **before** executing a write.

**Captured final results:**

```text
HR_DIRECTORY_HTTP_STATUS=200
HR_DIRECTORY_AUTHORIZATION=PASS
HR_DIRECTORY_RESULT_TYPE=list
MARIE_HR_READ_HTTP_STATUS=200
MARIE_HR_READ_AUTHORIZATION=PASS
MARIE_HR_READ_RESULT_TYPE=dict
MARIE_RECORD_FOUND=PASS
MARIE_DISPLAY_NAME=Marie
MARIE_OFFICE=Research / Independent Review
UNAUTHORIZED_WRITE_HTTP_STATUS=403
UNAUTHORIZED_WRITE_DENIED=PASS
GRACE_AUTHENTICATED_HR_ROUNDTRIP=PASS
SSH_EXIT_CODE=0
```

For the complete reusable Python invocation and clipboard-first PowerShell 7 wrapper, see [HR Personnel System — Engineering and Operations Runbook](HR_PERSONNEL_SYSTEM.md). It documents the exact JSON schema and both authorized and denied examples.

## 7. Rebuild/deploy checklist (reconstructed, not original commands)

1. Confirm repository commit and the **current** active systemd releases; capture rollback pointers.
2. Run HR record/store tests; preserve the existing native tool server, governed gateway, identity resolver, authority audit and write ledger.
3. Back up HR and authority databases independently; do not commit or serve them.
4. Create an immutable native release containing the compatible governed adapter and register it on the existing gateway, not a new listener.
5. Confirm the HR database already exists and correct filesystem permissions are enforced.
6. Use the established preflight → release → regression tests → activation → live health → rollback lifecycle. **The original exact deployment shell commands were not retained.**
7. Confirm `GET /v1/tools` exposes the three tools.
8. Provision credentials and exact grants via approved canonical Steward administration. Never accept a client-supplied role/principal or log the bearer token.
9. Execute authenticated public read tests and denied write test; assert exact authorization fields and record contents.
10. Independently inspect the persisted native router audit and canonical authority audit, correlated by request ID. **This independent audit inspection is still outstanding.**
11. Document evidence, rollback and any remaining exceptions.

## 8. Open acceptance gaps

- Helen's server-verified privileged HR read/write workflow is **not** implemented/verified; existing read tools expose only public fields.
- A successful authorized `hr.save` write has **not** been live-tested.
- Persisted authority audit events have not been independently inspected.
- Emergency direct-DB expiry change needs administrative audit remediation.
- Full resident roster, historical migration, UI, backup/restore drill and automated rollback are not complete.

## Related

- [HR Personnel System — Engineering and Operations Runbook](HR_PERSONNEL_SYSTEM.md)
- [Helen's HR Operating Guide](../HELEN_HR_GUIDE.md)
- [Onboarding administration UI issue #33](https://github.com/ppow1/R3/issues/33)
