<!--
R3 CONTROLLED DOCUMENT
File: examples/r3a_module_boilerplate/README.md
Component: R3A-MODULE-BOILERPLATE-EXAMPLE
File Revision: 1.0.1
Created: 2026-11-11T21:52:37Z
Created By: Codex GPT-6
Purpose: Explain how to adapt the offline base process-module example without changing frozen contracts.
Execution Model: Reference package and worker documentation.
Observability: Exact file list, artifact tree digest, external bundle digest, and test evidence.
Dependencies: Shared R3A module-release-package v2 builder; AP0-M1 process protocol; module metadata and process-binding schemas.
Authority: Steward assignment #68 comment 6807799874; Planned Step 126 comment 6807801282. No production activation or grants.
Changed: 2026-11-11T21:52:37Z | R3A-MODULE-BOILERPLATES-STEP-120 | Codex GPT-6 | Add offline reusable process-module example and integration instructions.
Changed: 2026-11-11T21:59:39Z | R3A-MODULE-BOILERPLATES-STEP-120 | Codex GPT-6 | Pin builder source and use the configured Python 3 command.
Supersedes: None.
Contracts: r3a.module-release-package.v2@2.0.0; r3a.module-release-metadata.v1@1.0.0; r3a.module-process-binding.v1@1.0.0; r3a.resident.module-binding.v1@1.0.0; AP0-M1 r3a.module.v1.
Tests: tests/test_module_boilerplate_example.py.
History/Predecessor: New file.
-->
# Offline process-module boilerplate

This example is a generic resident-executor process fixture, not a production module. It has synthetic identity `example.module-boilerplate@1.0.0`, contains no secrets or grants, and returns a protocol error from `execute` until module behavior is implemented.

## Contents

- `MODULE_METADATA.json` — package-only metadata using `r3a.module-release-metadata.v1@1.0.0`; it does not claim to be the canonical module manifest.
- `process-binding.json` — the fixed JSON-lines process binding and launch arguments.
- `configuration.schema.json` and `configuration.example.json` — an external, non-secret configuration sample.
- `resident-module-binding.example.json` — a synthetic fixture conforming to the existing resident binding schema; it is not an installed or authorized binding.
- `artifact/boilerplate_worker/` — the small process implementation. The host-supplied `r3a_runtime.protocol` library owns the existing wire protocol.

## Build with the shared package tool

Use `scripts/r3a_module_release_package.py` from the shared Modular Plugins #46 [package-builder source at commit `2641bda`](https://github.com/ppow1/R3/blob/2641bda993384d6f0a78d3798401a2a1585d39b8/scripts/r3a_module_release_package.py). From a repository containing that tool, run:

```sh
python3 scripts/r3a_module_release_package.py build \
  --module-metadata examples/r3a_module_boilerplate/MODULE_METADATA.json \
  --process-binding examples/r3a_module_boilerplate/process-binding.json \
  --source-root examples/r3a_module_boilerplate/artifact \
  --file boilerplate_worker/__init__.py \
  --file boilerplate_worker/worker.py \
  --output /tmp/r3a-example-module.tar.gz
```

The shared tool recalculates the artifact-tree digest from the declared source files, creates a deterministic release package, and reports its bundle SHA-256. Record that digest in the review/evidence record; verify and stage with the same shared tool and an independently supplied expected SHA-256. This worktree does not contain the shared builder, so do not copy or fork its implementation into this workstream.

## Configuration, authority, and lifecycle

The config path is passed to the process through the fixed `--config {configuration_path}` argument. Place the real config outside the package, validate it against the schema, and use protected references for secrets. The example only loads its external JSON config; it does not select a resident identity, capability, handler, grant, or service.

The package's resident-executor role and process binding describe the launch boundary. The canonical module manifest continues to own capability references and optional activity-handler declarations under its existing contract. A resident binding is a separate CME-owned configuration with authoritative identity provenance. Registry presence, package installation, and successful `prepare`/`activate` protocol calls do not grant capability authority. CME performs authorization for every operation.

The package installer stages immutable bytes; it does not register or activate the module. For an in-scope staged candidate, keep the previous version available. CME owns stopping, effective-version changes, and rollback. Remove only a failed, unactivated candidate using the shared `discard_unactivated_candidate` helper with the durable effective version, digest, and lifecycle state; never remove the effective or in-progress module.

## Checks

Run `python3 -m unittest tests.test_module_boilerplate_example` from this checkout. The test launches the worker over the existing local socket implementation and checks its lifecycle responses. It proves local fixture behavior only; package installation, CME registration, activation, authorization, and production acceptance remain outside this example's claim.
