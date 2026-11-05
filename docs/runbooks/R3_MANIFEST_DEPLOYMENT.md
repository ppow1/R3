<!--
R3 CONTROLLED DOCUMENT
File: docs/runbooks/R3_MANIFEST_DEPLOYMENT.md
Component: R3-MANIFEST-DEPLOY
File Revision: 1.0.1
Created: 2026-11-05 UTC (exact time not independently verified)
Created By: ChatGPT GPT-6
Purpose: Document manifest-driven deployment workflow and exact operator commands
Execution Model: Documentation
Observability: Git history and deployment reports
Dependencies: scripts/deployment/ and hints/deployment.md
Authority: Steward directive for R3 repository-owned deployment package
Changed: 2026-11-05 UTC | R3-MANIFEST-DEPLOY-002 | ChatGPT GPT-6 | Specify isolated dependency provisioning and bounded regression contract
Changed: 2026-11-05 UTC | R3-MANIFEST-DEPLOY-001 | ChatGPT GPT-6 | Initial documentation
Supersedes: None
Superseded By: None
Contracts: hints/file-provenance.md
Tests: Documentation review only; live deployment not run
History/Predecessor: Git blob 5f7282dcc27e9bd22c249fb9e055a3e5e7711c92
-->
# R3 manifest-driven deployment — website first

**Status: PHASE 1 / PLAN-ONLY. NOT a production deployer.** The included runner validates and prints a plan; it does not connect to Camrui, stop services, copy code, or activate releases. Do not mistake exit 0 for a successful deployment.

## Why this exists
Routine code corrections must not require dozens of copied SSH commands or rediscovery of topology. Developer produces an exact Git commit or local source directory and a deployment manifest; a stable deployment engine handles the installation. Preserve service isolation, bounded checks, durable evidence, and truthful acceptance status. Do not redesign deployment during a feature fix.

## Authoritative files
- Lightweight index: [AI_HINTS.md](../../AI_HINTS.md) -> [deployment hint](../../hints/deployment.md).
- Existing historical first-website runbook: [R3_FIRST_WEBSITE_DEPLOYMENT.md](R3_FIRST_WEBSITE_DEPLOYMENT.md).
- Existing legacy deploy script: [scripts/Deploy-R3.ps1](../../scripts/Deploy-R3.ps1) (commit argument, in-place checkout, estate-image-specific checks; **not** the general deployer).
- New phase-1 package: [scripts/deployment/Deploy-R3.ps1](../../scripts/deployment/Deploy-R3.ps1), [launcher](../../scripts/deployment/Launch-Deploy.cmd), [example manifest](../../scripts/deployment/manifests/website.example.json).

## Recommended operator directory
**Windows development workstation:** clone the repository in a dedicated working checkout (for example `C:\R3\`). The actual checkout location is operator-configurable; **not a verified existing path**. Run from `<R3 checkout>\scripts\deployment\`. The launcher changes to its own directory, so a double-click does not depend on the shell's initial working directory. PowerShell 7 (`pwsh.exe`) is required.

### Exact commands — CURRENT PHASE 1
```powershell
Set-Location 'C:\R3\scripts\deployment' # example only; replace with actual checkout
pwsh -NoProfile -File .\Deploy-R3.ps1 -Manifest .\manifests\website.example.json
```
Or double-click `Launch-Deploy.cmd` from Explorer. **Before running, replace the placeholder SHA in the example manifest**. For a real deployment later, use a copied, release-specific manifest, not the example.

Expected output includes `R3_DEPLOYMENT_PLAN_ONLY=TRUE`, `ACTIVATION=DISABLED_PENDING_LIVE_TOPOLOGY_VERIFICATION`, `DEPLOY_PASS=NOT_RUN`, and `ACCEPTANCE_PASS=NOT_RUN`. The runner copies its diagnostic plan to the clipboard by default. `-SkipClipboard` disables copying. A zero exit code only confirms manifest validation.

### Manifest schema v1
- `schemaVersion`: integer `1`.
- `name`: human-readable label.
- `source.type`: `github` or `local`.
- For GitHub: `source.repositoryUrl` must equal `https://github.com/ppow1/R3.git`, and `source.commit` must be a full **40-character** hexadecimal SHA. No floating branches or tags.
- For local: `source.path` must name an existing **directory on the operator's machine**. Phase 1 does not transfer it.
- `target.sshAlias`: configured SSH alias (historically `camrui`); `target.service`: currently only `website`; `target.port`: 1–65535.
- `target.releaseRoot`, `activeSymlink`, `venvPath`, `entrypoint`, `healthPath`: required nonempty strings, currently **proposed values** in example, not proof of current production topology.
- `verification.browserAcceptance`: `manual` in example; browser acceptance cannot be inferred from HTTP 200.

### Dependency and regression-test contract

The manifest declares:
```json
"dependencies": {
  "manager": "pip",
  "pythonVersion": "3.12",
  "installMode": "locked",
  "requirementsFile": "requirements-deploy.lock",
  "hashesRequired": true
},
"tests": {
  "profile": "website",
  "timeoutSeconds": 300,
  "onFailure": "abort-before-activation"
}
```

**Important:** `requirements-deploy.lock` is a proposed name, not a verified existing lockfile. The exact Python version, dependency set, lockfile location, test command and required test extras must be established from the actual R3 source and latest deployment history before enabling activation. The example currently validates declaration syntax only; it does **not** check lockfile existence or install dependencies. Never claim dependency readiness from a plan-only pass.

Production implementation must:
1. Resolve the exact source and lockfile from the **same revision**, then verify the lockfile and package hashes. Never install unpinned latest versions during an ordinary deployment.
2. Create/reuse an isolated environment for the **candidate release**, not mutate the active website's environment. Verify Python interpreter version and required import/package metadata; log dependency resolution failures.
3. Provision any declared **test-only** dependencies in a separate candidate test environment, if necessary. Tests must use that environment explicitly; do not silently fall back to system Python or another service's virtualenv.
4. Run only the specified, bounded website regression profile with a hard timeout, capture full stdout/stderr and exit status, and abort **before stopping the active website** on failures. No speculative new test suite or unrequested virtual environment experiments.
5. Confirm the production candidate environment contains the required runtime packages; activate only after build and relevant regressions pass. Preserve environment/lockfile provenance in the deployment report.
6. Keep `BUILD_PASS`, `REGRESSION_PASS`, `DEPLOY_PASS` and `ACCEPTANCE_PASS` independent. A successful dependency installation does not establish browser login or Grace autonomy acceptance.

**No dependency list has been invented or installed.** Exact dependency discovery remains an evidence-gathering step, not permission to change production.

### Local-source example
Copy the website example to a new JSON manifest, replace `source` with:
```json
"source": {"type": "local", "path": "C:\\R3\\release-candidate"}
```
The directory must exist locally. This is **validation only**, not packaging or upload.

## Deployment contract for production implementation (not yet implemented)
1. Resolve manifest and exact source revision/content hash; reject unknown host/service/path.
2. Identify existing release topology and current supervisor **read-only**; never assume the old `/home/admin1/R3` process is still authoritative.
3. Acquire lock; stage candidate outside running release; preserve configuration and secrets; run only declared bounded checks before downtime.
4. Confirm ownership of the exact website process. Never use broad `pkill -f`. Activate only the website target, not port 18303, institutional runtime, or native tools.
5. Verify expected release identity, listener PID, HTTP health, and any manifest-declared checks. Capture exact previous/new revision and logs.
6. Report `BUILD_PASS`, `REGRESSION_PASS`, `DEPLOY_PASS`, and `ACCEPTANCE_PASS` separately. Browser login, protected-page access and logout are a distinct operational acceptance gate.
7. Preserve previous release for recovery; never automatically rollback a healthy server merely because browser acceptance remains pending. Do not turn a failed deployment into an unbounded testing or architecture task.

## Historical evidence and failure lessons
- The original `scripts/Deploy-R3.ps1` targets Camrui, `/home/admin1/R3`, `r3_app:app`, port 8303 and a feature-specific background image. Those are historical script assumptions, **not current topology verification**.
- A prior website release reported 22/22 regressions passing and process activation, but browser login initially failed. The Steward later established an HTTP-LAN versus previously stored Secure-cookie conflict; clearing site cookies restored login. That was browser acceptance evidence, not a reason to rewrite the deployment engine.
- A later website deployment reportedly left port 18303 and the institutional runtime untouched; the Grace integration remained only partially accepted pending a genuine autonomous cycle.
- Do not confuse an HTTP 200 response or successful SSH exit with feature acceptance.

## Remaining activation prerequisites
Read-only inspection of live Camrui supervisor, release paths, active revision, shared configuration, and startup command; review any existing production deployment script/runbook; establish one verified activation procedure. Then extend this same engine, rather than adding another competing script. No LAN-to-public routing changes.
