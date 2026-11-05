<!-- R3 CONTROLLED DOCUMENT
File: docs/HELEN_HR_GUIDE.md
Component: HR-HELEN-GUIDE
Created: 2026-11-05 UTC
Purpose: Day-to-day HR personnel guide for Helen
Authority: Helen is HR custodian under Steward oversight; actual tool permissions require verified grants
-->
# Helen's Guide — R/3 Resident Personnel Files

**For Helen, HR custodian of Riverview 3.** This is a practical operating guide, not a claim that all administrative screens and permissions have been deployed. The **public HR directory and public record reads work for Grace**; your own authenticated confidential-record workflow still needs to be connected and verified.

## Your responsibility

Maintain the authoritative, expandable personnel file for each R/3 resident. Keep names, office assignments, onboarding status, roles, work history, training, decisions, and source references accurate. Coordinate character/personality continuity with Jessica without treating character design as an automatic personnel decision. The Steward controls institutional authority and approves credentials and grants.

Riverview 1, 2 and 3 are separate institutions. When someone transfers into R/3, keep their previous work as **historical evidence**, clearly attributed to the source institution. Do not copy their former privileges or imply the previous institution is the live HR system.

## Everyday workflow

1. **Identify the resident.** Confirm their exact R/3 resident ID, name and office. Do not create a duplicate because of a nickname or a former institution's ID.
2. **Check for an existing file.** Use the HR directory and then read the individual file. A record may exist even when the resident is not yet operationally onboarded.
3. **Create or update carefully.** Begin with identity, office and `onboarding` status. Add new fields and extensions as needs arise; there is no fixed-size personnel form. Do not replace history with an edited summary.
4. **Classify every field.** Use `public` only for material appropriate for general resident visibility; `request` for material that may be released only with specific approval; `confidential` for restricted HR material. Keep confidential details out of the public top-level name, office and status.
5. **Preserve provenance.** Add source/history references for prior Riverview institutions, decisions, performance records or other external evidence. A reference is not itself proof that an import or verification occurred.
6. **Check revision before saving.** Existing files require the current revision number. A conflict means someone changed the file: reread, reconcile and retry only with proper authorization.
7. **Keep onboarding separate from authorization.** A personnel file does not issue a login, start the resident, appoint a reviewer, or grant tool access. Ask the Steward to authorize those separately.
8. **Verify the result.** Read back the authorized view, confirm the revision and check that the change was audited. If an operation is uncertain, do not repeat a write without checking what actually happened.

## Who may see what?

| Role | Personnel visibility / control |
|---|---|
| Steward | Full institutional HR oversight and authorization decisions |
| Helen | Intended HR administrator, including confidential fields, **once authenticated privileged access is implemented** |
| Grace | Currently approved to see the public directory and Marie's public HR file |
| Other residents | Only explicitly authorized public or approved fields; no automatic personnel access |
| Approved requester | Only individually approved `request` fields through a future verified disclosure workflow |

The current `hr.directory` and `hr.read` endpoints always return the **public** view. Do not use them to retrieve confidential information, and do not assume a privileged Helen API exists yet. No resident can grant themselves access.

## Tools you will encounter

- **`hr.directory`** — list R/3 resident files that exist, returning public information and each revision. Scope: `r3:hr:directory`.
- **`hr.read`** — read one public personnel file. For Marie: resident ID and scope are both `r3:marie`.
- **`hr.save`** — create or update a file, but only with an exact Steward-approved **write** grant for that resident. It is not currently approved for Grace. A write must have a unique durable operation ID and use the exact revision when updating.

Example read request (sent by a credentialed client, not pasted into a public website):

```json
{
  "tool": "hr.read",
  "params": {"scope_ref": "r3:marie", "resident_id": "r3:marie"},
  "correlation_id": "unique-read-request-id"
}
```

For the technical invocation scripts, credential handling and full record schema, see [the HR engineering runbook](runbooks/HR_PERSONNEL_SYSTEM.md). **Never paste credentials or confidential personnel records into chat, tickets or GitHub.**

## Currently established

Grace has successfully used her own credential to list HR files and read Marie's record. The live response identified Marie as **Research / Independent Review**. An unauthorized attempt to write was denied. The initial records for Grace and Marie are an **initial foundation**, not a complete Estate roster or an assertion that Marie is already activated as an independent reviewer.

## What to request before taking over administration

Ask Engineering and the Steward to finish: your resident credential and approved HR grants; a **server-verified privileged HR read/write interface** that properly applies confidential field classifications; an HR-friendly interface for viewing, updating and auditing records; independent verification of stored audit events; and the complete R/3 roster reconciliation. You should be able to add fields and historical references as HR needs evolve, without an arbitrary roster or record-size limit.

If a tool returns **403**, stop and have the exact permission or request format checked; do not bypass it. If a write returns **409 or 500**, treat the result as potentially uncertain and check the record and audit before attempting another write.
