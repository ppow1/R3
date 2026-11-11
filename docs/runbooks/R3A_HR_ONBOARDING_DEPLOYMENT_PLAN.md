# R3A HR Onboarding Deployment and Recovery Plan

## Current disposition

This is a release-gated plan, not deployment authorization. The HR source candidate is not yet independently approved at its exact SHA, the packet service is not composed into an authenticated R3A host, and migration 019 has not been applied to shared R3A. Do not deploy or migrate shared R3A until the Auditor review and Coordinator release approval are recorded.

This plan covers only the R3A onboarding packet/event store and its host integration. It does not create HR identities or appointments, directory occupants or office bindings, credentials, grants, resident modules, or Website availability.

## Authority and interface handoff

| Operation | Authority / owner | Existing interface and evidence | Missing item / gate |
|---|---|---|---|
| HR identity and appointment read/write | HR authority; Helen's HR management approval must be represented by configured policy, not inferred from a role string | Issue #33 comment `6767817621` identifies the existing HR source branch `engineering/hr-foundation-grace-marie-20261105` at `4f50274c6c4fdd16e8d42cb26bcd33309f40486a` and the exposed `hr.directory`, `hr.read`, and `hr.save` operations | No current authenticated R3A personnel/appointment API or approved active Vicky appointment evidence. The accountable HR source maintainer/approver is not named in the available evidence; Steward/HR must identify that principal and approval route. |
| HR-to-directory association | HR authority, with exact authenticated HR write authorization | R3A consumer is `HRPrincipalAssociationAdapter` in `r3a_runtime/residents/hr_association.py`; expected host operation is `associate_authority_principal_with_provenance` | Operation is absent from the verified host interface. It must enforce authenticated actor, exact `r3:hr`/`hr.write`/`write` resident scope, current expected HR revision and active approved appointment, server-side resolution of fresh directory evidence, exact evidence-reference match, stable idempotency/correlation, conflict/duplicate rejection, and atomic association/provenance/audit persistence. Issue #33 says the accountable HR source owner has not been identified. The legacy PR #57 proposal is quarantined and is not deployed authority. |
| Canonical occupant and office binding | Riverview institutional directory authority (`riverview_authority`); HR appointment approval is a prerequisite | Coordinator's `institutional.directory.discover` read joins `institutional_offices`, `resident_occupants`, and `office_bindings`; the provider is read-only | No occupant/binding writer or authorized onboarding procedure is present in the verified R3A interface. Issue #33/58 evidence does not name the directory write owner. Coordinator must identify the source owner and sanctioned write/evidence path; do not write these tables from HR Development. |
| Packet and audit-event persistence | Coordinator owns R3A DB, service composition, and release | Additive migration `019_resident_onboarding.sql`; `Store.migrate()` checksummed runner; `PostgresResidentOnboardingRepository`; HTTP composition is host-injected | Migration has only been exercised in disposable PostgreSQL. No authenticated production `ResidentOnboardingService` composition/API or least-privilege database role grants are present in this workstream. Coordinator must review and provide these. |
| Credentials and capability grants | Security / canonical R3 authority | Existing CME grant enforcement and revocation remain separate from onboarding packet storage | No resident credential issuance interface or Vicky credential/grant approval is evidenced. Security must provide its procedure and separately approved exact-scope grants. |
| Character/canon and continuity | Character Architecture; Jessica's approval responsibilities use configured approval policy | Existing R3A character workflow and approved-context contracts | Vicky's dossier is provisional, with no approved canon/continuity association. Character Architecture approval remains required where applicable. |
| Runtime and communication | Coordinator integrates; Autonomy owns resident execution/model route; Website owns its communication module under Coordinator integration | Existing module and authenticated directory/chat contracts | Vicky module/model binding, execution authorization, Website roster, and live chat persistence have not been verified. |

### HR association request/response contract

The adapter's operation name and payload are defined in `hr_association.py`. The host call receives the authenticated/authorized HR principal, existing `r3:` HR record ID, expected HR revision, server-resolved canonical `resident:` principal and active office/binding evidence, opaque requested evidence reference, idempotency key, and correlation ID. The host returns the same HR record and associated principal, a newer revision, the exact persisted provenance, idempotency/correlation values, an association reference, and an audit-event reference. The adapter rejects absent operation, stale/inactive HR record, stale/mismatched evidence, caller-selected principal, and incomplete persistence evidence. The host remains responsible for its own authoritative transaction and audit. R3A must not implement a substitute HR or directory writer.

## Staged release procedure

1. **Review gate:** Record independent Auditor PASS against the exact candidate SHA, including authority-spoofing and recursive-reference regressions. Coordinator reviews migration 019, rollback SQL, repository code, test evidence, API/auth composition, and database grants. Steward/Coordinator release authority approves a maintenance window. No gate is implied by this plan.
2. **Preflight:** Pin the approved commit and Coordinator integration baseline. Require a clean release worktree, backup and verified restore point under the Coordinator database procedure, schema-migration ledger/checksum capture, healthy current service, and a tested application rollback artifact. Confirm the release's database role can access only the onboarding packet/event tables and has no writes to HR, directory, credential, or grant authority tables.
3. **Schema rollout:** In the approved Coordinator release window, apply the additive migration using the existing `Store.migrate()` runner. Verify the recorded `019_resident_onboarding.sql` checksum, packet/event relations, constraints, and audit append-only trigger. If any check fails, stop before enabling the API and use the Coordinator's database recovery procedure; do not hand-edit the ledger.
4. **Host composition:** Only after the schema gate, Coordinator composes the service with an authenticated session-to-actor resolver, exact action/scope authorization callback, HR/character/security/runtime/communications evidence verifiers, activation verifier, and the least-privilege repository. Missing authorities must remain explicit blocked evidence; no defaults may approve or synthesize identity, grants, or appointments. Coordinator owns route, service supervision, health checks, and release-specific commands.
5. **Controlled validation:** Use synthetic identities in the approved staging/isolated environment. Verify request idempotency, revision compare-and-swap, atomic packet/event persistence, redaction, denied actor/grant, unavailable-authority fail-closed behavior, restart/resume, and audit evidence. A successful packet operation is not an appointment or resident activation.
6. **Acceptance:** Auditor inspects persisted traces and Coordinator health. Steward separately approves any actual resident activation only after every authority domain and operational acceptance gate has verified evidence. Vicky remains excluded until her authoritative identity, approved active appointment, binding, canon decision, credentials, grants, runtime/model route, and authenticated communications evidence are supplied.

## Rollback and recovery

- **Application rollback:** If host composition or health checks fail, Coordinator rolls back the application release using the prior pinned release artifact and its normal release procedure. Preserve migration 019 and onboarding rows; an older application must not drop or rewrite workflow evidence.
- **Schema rollback:** The down migration `r3a_runtime/rollback/019_resident_onboarding.down.sql` is only for a separately approved maintenance action when both packet and event tables are empty. It checks this invariant and refuses to run if any onboarding evidence exists. Never delete packet/event rows to make rollback pass. If evidence exists, retain the additive schema and perform forward repair or a separately approved data-retention disposition.
- **Interrupted migration/host rollout:** Read the migration ledger and service state before retry. Do not rerun manual SQL or infer success from a process exit alone. Use the checksummed `Store.migrate()` runner and Coordinator release telemetry; packet and event writes are transactional and retries must reuse stable idempotency/event keys only for the same request.
- **Shared database protection:** The regression's destructive `DROP SCHEMA r3a` setup is permitted only for an explicitly named disposable database matching `r3a_onboarding_test_*` on loopback or a private `/tmp` socket. Never point it at shared, staging-with-data, or production R3A.

## Reproducible isolated database validation

The repository test is `tests/test_r3a_resident_onboarding_postgres.py`. Use the established isolated environment and a fresh disposable PostgreSQL cluster/database, for example:

```sh
R3A_TEST_ONBOARDING_DSN='host=/tmp/<private-test-socket> port=<private-port> dbname=r3a_onboarding_test_<run-id> user=<test-owner>' \
  /tmp/r3a-hr-development-venv/bin/python -m unittest tests.test_r3a_resident_onboarding_postgres -v
```

Use a UTF-8 database; migration SQL contains Unicode text. The test applies the full migration stack, checks repeat migration is a no-op, exercises rollback/re-upgrade for empty 019 tables, runs multi-resident packet/event repository and concurrency/privacy checks, and proves rollback refuses populated evidence. Stop and remove only the private cluster created for the test after capturing its test log.

## Current blockers and next actions

1. Auditor posts PASS/FAIL/BLOCKED for exact SHA `62d6aae84f2bf7d824078f5559fd77a010349bd0`.
2. Coordinator identifies the authenticated service-composition/API owner and reviews schema, DB role grants, and release procedure before shared migration.
3. HR authority names its accountable source owner/approver and provides current appointment/read evidence plus the governed association writer or exact equivalent.
4. Directory authority names its write owner and authorized `resident_occupants`/`office_bindings` onboarding procedure.
5. Security and Character Architecture provide their separately owned procedures/evidence; Coordinator and Autonomy provide runtime/model/Website readiness evidence.
