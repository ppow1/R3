<!--
R3 CONTROLLED DOCUMENT
File: hints/module-boilerplates.md
Component: R3A-MODULE-BOILERPLATES
File Revision: 1.0.3
Created: 2026-11-11T21:52:37Z
Created By: Codex GPT-6
Purpose: Index the reusable offline R3A process-module boilerplate and its boundaries.
Execution Model: Documentation and source navigation; the example worker runs only when explicitly launched by tests or the existing CME process binding.
Observability: Pinned source-tree digest, correlated JSON-lines lifecycle responses, and focused test output.
Dependencies: AP0-M1 module protocol; R3A module lifecycle contract; shared module release package v2 and process binding v1.
Authority: Steward assignment #68 comment 6807799874; Planned Step 126 comment 6807801282. Offline development only; no shared runtime activation.
Changed: 2026-11-11T21:52:37Z | R3A-MODULE-BOILERPLATES-STEP-120 | Codex GPT-6 | Add navigation and describe the reusable process-module example.
Changed: 2026-11-11T21:59:39Z | R3A-MODULE-BOILERPLATES-STEP-120 | Codex GPT-6 | Pin shared builder guidance to the exact source commit.
Changed: 2026-11-11T22:02:24Z | R3A-MODULE-BOILERPLATES-STEP-120 | Codex GPT-6 | Add explicit artifact and review handoff locations.
Changed: 2026-11-11T22:07:30Z | R3A-MODULE-BOILERPLATES-STEP-120 | Codex GPT-6 | Identify the package contract source revision in provenance.
Supersedes: None.
Contracts: R3A_MODULE_LIFECYCLE_AND_CONTRACT_SPEC.md AP0-M1 profile; shared R3A_MODULE_RELEASE_PACKAGE_V2.md at commit 2641bda; resident-module-binding.v1.schema.json; r3a.module.v1.
Tests: tests/test_module_boilerplate_example.py.
History/Predecessor: New file.
-->
# R3A module boilerplates

## WHERE TO FIND IT

- Reusable process-module example: [`examples/r3a_module_boilerplate`](../examples/r3a_module_boilerplate)
- Focused source, digest, config, binding, and lifecycle checks: [`tests/test_module_boilerplate_example.py`](../tests/test_module_boilerplate_example.py)
- Canonical capability/activity-handler reference fixture: [`tests/fixtures/r3a_activity_handler_interop.v1.json`](../tests/fixtures/r3a_activity_handler_interop.v1.json)
- Shared package-builder contract/source: Modular Plugins #46 at [`2641bda`](https://github.com/ppow1/R3/tree/2641bda993384d6f0a78d3798401a2a1585d39b8)

The offline example at [`examples/r3a_module_boilerplate`](../examples/r3a_module_boilerplate) is a reusable starting point for a Python process module using the existing private Unix-socket JSON-lines contract. It includes a generic worker, package metadata, process binding, external configuration example and schema, plus a synthetic resident-binding fixture. The example uses no real resident identity, capability grant, credential, or deployment setting.

The runtime package contract is `r3a.module-release-package.v2@2.0.0`; its distinct package metadata contract is `r3a.module-release-metadata.v1@1.0.0`, and process launch uses `r3a.module-process-binding.v1@1.0.0`. Use the [shared package contract and builder from Modular Plugins #46 at commit `2641bda`](https://github.com/ppow1/R3/blob/2641bda993384d6f0a78d3798401a2a1585d39b8/docs/architecture/R3A_MODULE_RELEASE_PACKAGE_V2.md); do not add another package builder. The selected Module Boilerplates worktree does not contain that shared builder yet, so package generation is validated against that exact source revision in an isolated temporary copy and remains an integration dependency for consumers of this branch.

The example's default `execute` operation returns an explicit not-implemented protocol error. Replace it with module-owned behavior before a module is eligible for work. Package registration, capability references, activity-handler declarations, resident bindings, and grants remain separate existing contracts. For examples of the canonical capability and activity-handler declarations, see [`tests/fixtures/r3a_activity_handler_interop.v1.json`](../tests/fixtures/r3a_activity_handler_interop.v1.json); the process-release metadata does not replace or extend `r3a.module-manifest.v1`.

Build, verify, and stage using the shared package CLI documented in the [R3A Module Release Package v2 contract](https://github.com/ppow1/R3/blob/2641bda993384d6f0a78d3798401a2a1585d39b8/docs/architecture/R3A_MODULE_RELEASE_PACKAGE_V2.md). Staging does not activate a module or grant authority. CME owns effective lifecycle selection and rollback; failed unactivated candidate cleanup requires the shared helper's current effective version/digest and lifecycle inputs. Keep configuration outside the immutable artifact and supply secret references only through the approved external configuration channel.

Run the focused offline example checks with:

```sh
python3 -m unittest tests.test_module_boilerplate_example
```

These checks cover package metadata and file pins, the external config and binding contracts, worker launch/health/prepare/activate/checkpoint/stop, and the explicit unimplemented execution response. They do not claim CME registration, activation, capability authorization, or production operation.
