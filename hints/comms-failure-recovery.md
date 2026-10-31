<!--
R3 CONTROLLED DOCUMENT
File: hints/comms-failure-recovery.md
Component: COMMS-RECOVERY
File Revision: 1.0.0
Created: 2026-10-31 UTC (time unverified)
Created By: ChatGPT GPT-6
Purpose: Capture failed and blocked Riverview Comms operations
Execution Model: N/A
Observability: Incident ledger and punch list
Dependencies: Riverview Comms 1.1 and applicable operational runbooks
Authority: Steward direction
Changed: 2026-10-31 UTC | R3-COMMS-001 | ChatGPT GPT-6 | Initial failure recording convention
Supersedes: None
Contracts: hints/file-provenance.md
Tests: Not applicable
History: Git
-->
# Comms failure recording and recovery

Every Riverview Comms command failure, denial, timeout, missing interface, or blocked prerequisite must generate or update a durable incident record, even if a workaround later succeeds. Distinguish **command attempted and failed** from **command not submitted because of preflight prerequisites**.

Record: incident ID, UTC time/precision, requested objective, operation, host, status/error, required grant or permission if known, whether submitted, attempted retries, verified evidence, hypotheses, impact, proposed remedy, related runbook, punch-list link, and closure evidence. Redact credentials and secrets.

For recurring errors, append evidence to the existing incident rather than multiplying tickets. Locate existing recovery runbooks before inventing scripts. Never mark an incident resolved until a successful retry or verified alternative is recorded.

The Steward reports a historical Riverview V2 grants UI issue: grants were visible but new grant initialization required a browser developer-console procedure documented in a Riverview dashboard runbook. The exact runbook path and current applicability are **not yet verified**; find and review it before following that procedure.

## Cases

- [R3-COMMS-001: Camrui command preflight blocked](../docs/comms-incidents/R3-COMMS-001.md)
