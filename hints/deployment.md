<!--
R3 CONTROLLED DOCUMENT
File: hints/deployment.md
Component: DEPLOYMENT
File Revision: 1.0.2 (provenance baseline; prior revisions untracked)
Created: Unknown (legacy; initial commit can establish earliest publication)
Created By: Unknown (legacy)
Purpose: R3 engineering reference and continuation guidance
Execution Model: N/A
Observability: N/A
Dependencies: R3 docs and hints index
Authority: R3 engineering guidance; approved charter prevails
Changed: 2026-11-05 UTC | R3-DEPLOY-BOOTSTRAP-005 | ChatGPT GPT-6 | Require verified real activation and protected integration/fallback
Changed: 2026-11-05 UTC | R3-MANIFEST-DEPLOY-001 | ChatGPT GPT-6 | Index manifest-driven deployment runbook and scripts
Changed: 2026-10-31 UTC | R3-PROVENANCE-001 | ChatGPT GPT-6 | Add provenance baseline
Supersedes: None
Contracts: hints/file-provenance.md
Tests: Not run (metadata-only change)
History/Predecessor: Git blob f894822145bbe8eed99d56cf787d550b4054ac96
-->
# Deployment and operations

- [Current implementation handoff](../docs/IMPLEMENTATION_HANDOFF.md) — Camrui target, manual bootstrap and pending work.
- [R3 capability API](../r3_app.py) — current source; not yet verified deployed.

Try Riverview Comms 1.1 before asking the Steward to run commands. Do not claim deployment or runtime behavior without observed evidence. Keep credentials out of browser-facing code.

**Bootstrap deployment gate (2026-11-05):** Before every website deployment, distinguish plan-only manifest validation from actual activation. Verify the current user-service, active code/release, branch divergence, backup and isolated integration candidate. Preserve the dirty shared checkout and Grace/avatar services. Try Comms 1.1 for actual host work, and use the documented full PowerShell 7 clipboard fallback if host commands are denied. See [Development Bootstrap](development-bootstrap.md) and [Development Execution](development-execution.md). Do not run the legacy in-place 8303 script against the 18303 website service without verifying current ownership and compatibility.

## Manifest-driven deployment (phase 1)

- [Canonical manifest deployment runbook](../docs/runbooks/R3_MANIFEST_DEPLOYMENT.md) — Windows working directory, exact PowerShell commands, manifest schema, source examples, bounded checks, acceptance and activation prerequisites.
- [Plan-only deployment runner](../scripts/deployment/Deploy-R3.ps1), [double-click launcher](../scripts/deployment/Launch-Deploy.cmd), [website example manifest](../scripts/deployment/manifests/website.example.json).
- [Legacy in-place deployment script](../scripts/Deploy-R3.ps1) and [first website deployment evidence](../docs/runbooks/R3_FIRST_WEBSITE_DEPLOYMENT.md) remain available for reference.
- **Current status:** Manifest validation only. Do not report a deployment or restart from this runner; live activation requires verified current Camrui topology and a separately tested activation implementation. Do not restart Grace or native tools for website changes.
