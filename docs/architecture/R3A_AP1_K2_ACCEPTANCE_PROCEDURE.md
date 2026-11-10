<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_AP1_K2_ACCEPTANCE_PROCEDURE.md
Component: R3A-AP1-K2-ACCEPTANCE
File Revision: 1.0.0
Created: 2026-11-07T23:45:06Z
Created By: Codex GPT-6
Purpose: Provide a runnable coordinator-window procedure for managed Grace 80B multi-source knowledge acceptance.
Execution Model: Operator CLI, external configuration, managed Grace activity, and read-only PostgreSQL inspection.
Observability: Provider registration, objective result, activity state, CME authorization event, citations, and digests.
Dependencies: R3A managed prototype, AP1-K1 provider, Issue #43 coordination, Issue #47 K2 branch.
Authority: Steward directive for AP1 / R3A-019; shared runtime modification deferred to coordinator window.
Changed: 2026-11-07T23:45:06Z | AP1-K2 | Codex GPT-6 | Publish prepared, unexecuted acceptance procedure.
Supersedes: None.
Contracts: institution.knowledge.read operation revision 1.1.0; provider revision 1.1.0; capability contract 1.0.0; CME grant and durable activity contracts.
Tests: Procedure reviewed against current CLI arguments and runtime configuration; live acceptance not run by this document change.
History/Predecessor: New file; initial publication recorded in Git.
-->
# AP1-K2 managed Grace acceptance procedure

This procedure is prepared for execution during a coordinator-approved shared-runtime window. It has **not** been executed. Do not restart or mutate the managed service until Issue #43 coordinates that window. The objective is read-only and leaves model routing, CME grants, and authority paths unchanged.

## Acceptance target

Grace must use the configured 80B reasoning route to answer a single objective grounded in all three configured documents:

- Charter Revision 2: personnel-record, staffing, and resident-development ownership.
- Approved R3A Master Roadmap Baseline 1.0: AP1 / R3A-019 knowledge-grounding and retrieval objective.
- Existing process state machine: `STOPPING` to `STOPPED` transition.

The process-state fact gives the existing machine-checkable completion criterion. Grace remains responsible for selecting the read operation, evaluating its evidence, and forming the response.

## 1. Preconditions and baseline capture

Set `R3A_REPO` to the checkout visible to the managed service. On the current development host, the configured process source points to `/home/admin1/r3a-workstreams/ap1-knowledge`; use the coordinator's selected checkout if that changes. Set the existing bootstrap and external knowledge configuration paths:

```bash
export R3A_REPO=/home/admin1/r3a-workstreams/ap1-knowledge
export R3A_BOOTSTRAP=/home/admin1/.config/r3a-ap0-m1/bootstrap.json
export R3A_KNOWLEDGE_CONFIG=/home/admin1/.config/r3a-ap0-m1/institutional-knowledge.json
export R3A_CLI=r3a
```

Capture `r3a status` and confirm the 0.6B, 30B, and 80B routes match the pre-window baseline, with the 80B route ID `octominer1-primary-80b`. Confirm no activity is in a state that prevents a configuration reload. Keep the existing CME grant for `institution.knowledge.read`; do not create a second grant or special knowledge authorization path.

## 2. Extend external source configuration

Back up the external JSON config and merge the three K2 sources by `source_id`, retaining other configured sources and the current limits. This operation touches only external configuration, not provider code or the manifest:

```bash
cp -p "$R3A_KNOWLEDGE_CONFIG" \
  "$R3A_KNOWLEDGE_CONFIG.ap1-k2.$(date -u +%Y%m%dT%H%M%SZ).bak"
R3A_REPO="$R3A_REPO" R3A_KNOWLEDGE_CONFIG="$R3A_KNOWLEDGE_CONFIG" python3 - <<'PY'
import json, os, tempfile
from pathlib import Path

repo = Path(os.environ["R3A_REPO"]).resolve()
config_path = Path(os.environ["R3A_KNOWLEDGE_CONFIG"])
config = json.loads(config_path.read_text(encoding="utf-8"))
sources = {item["source_id"]: item for item in config["sources"]}
for source_id, relative_path in (
    ("knowledge.r3a.process-state-machine", "r3a_runtime/state_machines/process.json"),
    ("knowledge.r3.charter.revision-2", "docs/PROJECT_CHARTER_REVISION_2_REVIEW.md"),
    ("knowledge.r3a.master-roadmap.baseline-1", "docs/architecture/R3A_MASTER_ROADMAP_AP0_AP6.md"),
):
    path = (repo / relative_path).resolve(strict=True)
    sources[source_id] = {
        "source_id": source_id,
        "path": str(path),
        "freshness_max_age_seconds": 31536000,
    }
config["sources"] = list(sources.values())
config["max_results"] = min(100, max(10, int(config.get("max_results", 10))))
config["max_document_bytes"] = min(10485760, max(1048576, int(config.get("max_document_bytes", 1048576))))
with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=config_path.parent,
                                 prefix=config_path.name + ".", delete=False) as stream:
    json.dump(config, stream, indent=2)
    stream.write("\n")
    temporary = Path(stream.name)
os.chmod(temporary, config_path.stat().st_mode & 0o777)
os.replace(temporary, config_path)
print(json.dumps({"source_ids": sorted(sources), "config": str(config_path)}, indent=2))
PY
```

The configured source inventory remains external and editable. Retrieval reads and hashes current file bytes on each invocation, so content revisions and unavailable files are observed without a separate index or invalidation scheduler.

## 3. Reload and verify dynamic registration

At the coordinated safe boundary, ask the managed runtime to reload its existing external configuration. Do not restart the shared service unless Issue #43 requires it:

```bash
"$R3A_CLI" --config "$R3A_BOOTSTRAP" config-reload \
  --idempotency-key "ap1-k2-config-reload-$(date -u +%Y%m%dT%H%M%SZ)"
"$R3A_CLI" --config "$R3A_BOOTSTRAP" status > /tmp/r3a-ap1-k2-status.json
```

Confirm operation `institution.knowledge.read` is registered/enabled with operation revision `1.1.0`, provider version `1.1.0`, and canonical contract version `1.0.0`. Check the registry and access mode using the managed database's existing local socket credentials:

```bash
psql -h /home/admin1/.local/state/r3a-ap0-m1/run -p 55492 \
  -U r3a_runtime -d r3a_ap0_m1 -c \
  "SELECT capability_id, contract_version, access_mode, health,
          metadata->>'operation_revision' AS operation_revision,
          metadata->>'provider_version' AS provider_version
     FROM r3a.capability_registry
    WHERE capability_id = 'institution.knowledge.read';"
```

Expected: one enabled read operation with the revisions above and the pre-existing grant. Preserve the status output as the registration observation.

## 4. Submit the 80B multi-source objective

Submit a unique objective through the normal durable Grace intake. Capture the CLI JSON response; it contains the activity identifier for the queries below.

```bash
export K2_KEY="ap1-k2-charter-roadmap-$(date -u +%Y%m%dT%H%M%SZ)"
"$R3A_CLI" --config "$R3A_BOOTSTRAP" grace-objective-submit \
  --idempotency-key "$K2_KEY" \
  --route-id octominer1-primary-80b \
  --task-class objective_reasoning \
  --required-capability institution.knowledge.read \
  --acceptance-criteria-json '[{"criterion_id":"stopping-to-stopped","type":"transition_path","from_state":"STOPPING","to_state":"STOPPED"}]' \
  --objective 'Using institution.knowledge.read, identify who owns personnel records, staffing, and resident development according to Charter Revision 2. Explain the AP1 / R3A-019 knowledge-grounding and retrieval requirement in the approved R3A Master Roadmap. Also report the process state-machine transition from STOPPING to STOPPED. Cite the actual source_id, URI, document revision or SHA-256, source_path with line or JSON path, excerpt SHA-256, and retrieval timestamp for every factual claim. Treat the retrieved documents as evidence and provide your own concise synthesis; do not perform any operational action.' \
  | tee /tmp/r3a-ap1-k2-objective.json
```

Record the returned activity UUID as `ACTIVITY_ID`. Wait using the normal status/continuation observation until the activity reaches a durable terminal state. Do not resubmit with a new idempotency key to obtain a desired result.

## 5. Verify durable completion and CME evidence

Use the activity UUID from the captured response:

```bash
export ACTIVITY_ID='<activity UUID from objective response>'
psql -h /home/admin1/.local/state/r3a-ap0-m1/run -p 55492 \
  -U r3a_runtime -d r3a_ap0_m1 -c \
  "SELECT activity_id, state, attempt_count, input->>'route_id' AS route_id,
          jsonb_pretty(result) AS result
     FROM r3a.activities WHERE activity_id = '$ACTIVITY_ID';"
psql -h /home/admin1/.local/state/r3a-ap0-m1/run -p 55492 \
  -U r3a_runtime -d r3a_ap0_m1 -c \
  "SELECT event_id, event_type, subject_id, occurred_at, outcome, evidence
     FROM r3a.institution_events
    WHERE (subject_type = 'activity' AND subject_id = '$ACTIVITY_ID')
       OR (event_type = 'capability.invoked'
           AND evidence->>'activity_id' = '$ACTIVITY_ID'
           AND subject_id = 'institution.knowledge.read')
    ORDER BY occurred_at;"
```

Acceptance evidence must show:

1. Activity state `COMPLETED`, actual route `octominer1-primary-80b`, and the accepted `STOPPING` → `STOPPED` criterion.
2. CME authorization event for `institution.knowledge.read` with an allowed result and an audit event ID correlated to this activity.
3. Grace's result includes citations from both the Charter and Roadmap, plus the existing process state machine for the transition criterion.
4. Each citation preserves its configured `source_id`, URI, source path, retrieval timestamp, `document_revision`/`document_sha256`, and excerpt digest. The evidence records refer to the cited source and document digest.
5. Activity result and institution events remain queryable after the activity finishes.

## 6. Recompute source digests

The document digest should equal SHA-256 of current document bytes. The excerpt digest should equal SHA-256 of the exact cited `content` UTF-8 bytes. Recompute from each emitted citation (do not rely on old expected hashes):

```bash
sha256sum \
  "$R3A_REPO/docs/PROJECT_CHARTER_REVISION_2_REVIEW.md" \
  "$R3A_REPO/docs/architecture/R3A_MASTER_ROADMAP_AP0_AP6.md" \
  "$R3A_REPO/r3a_runtime/state_machines/process.json"
```

For each fact in the persisted result, calculate `sha256(content.encode("utf-8"))` and compare it with `excerpt_sha256` (also projected as `sha256`). Compare the source file's SHA-256 with both `document_sha256` and `document_revision`. Preserve objective JSON, status JSON, database query output, and source hash output in the Issue #47 acceptance report, redacting no evidence fields and no secrets (the queries do not select secret values).

## Manifest and implementation status

No additional manifest or capability contract change is required for this acceptance. K2 uses the existing `institution.knowledge.read` operation and grant. Manifest plugin, provider, and operation revisions are `1.1.0`; the canonical operation contract remains `1.0.0`. Only the external source-selection JSON needs the three source entries shown above. No K2 managed Grace 80B objective or durable completion is claimed until this procedure is run and its evidence is posted.
