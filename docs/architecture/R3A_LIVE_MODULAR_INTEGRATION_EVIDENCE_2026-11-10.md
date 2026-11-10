# R3A live modular integration evidence — 2026-11-10

## Source and release identity

- Authoritative Coordinator V2 starting point: `integration/r3a-coordinator-v2-20261109` at `b1b38130e796adfe02c7343f71764e9ab0513f6b`.
- Reviewed modular contract producer preserved: #46 `a224a6b30f1e96b95a65fde6a50d81775f5e5039`.
- Reviewed checkpoint/handler consumer preserved: #43 `aeac6fcc3396b8f148b4b3c87754b6a2459f29a8`.
- Their integration merge is `2a590c3` in this branch. The Coordinator's b1 chat changes remain in the base and were retained while resolving only CME/DB file header conflicts.
- Feature work commit: `e149bdad5d445964533937d8edb23e3dc975f02e`.
- Module: `r3a.octominer-telemetry@2.0.0`; manifest contract `r3a.module-manifest.v1@1.1.0`; canonical operation `infrastructure.octominer.telemetry.read` (`read`, contract v1.0.0); required grant `infrastructure.octominer.telemetry.read`; module dependencies: none.
- Release bundle: `artifacts/r3a.octominer-telemetry-2.0.0.tar.gz`, **SHA-256 `3c5441e1942d0a769ae5e299571cbf6267b3ac67363cecf6906fe9b6a9c7352b`**, 13,882 bytes. Repeated deterministic builds produced the same digest.

## Package and staging evidence

At 2026-11-10 13:25:47–13:25:53 UTC, the recorded commands were:

```text
python3 scripts/package_octominer_module.py build --output artifacts/r3a.octominer-telemetry-2.0.0.tar.gz
python3 scripts/package_octominer_module.py verify artifacts/r3a.octominer-telemetry-2.0.0.tar.gz
/tmp/r3a-live-modular-test-venv/bin/python -m pytest -q tests/test_r3a_module_release_package.py
```

Build and bundle verification exited 0 (0.42s and 0.39s). The permanent package acceptance tests passed **4/4** (2.04s): deterministic package integrity, tamper rejection, versioned isolated installation/idempotency, and installed-provider registry discovery plus process-manager activation, functional telemetry invocation, and deactivation. The functional sample is synthetic: a fixture SSH executable returned a fixed GPU sample (35% utilization, 46°C, 50% fan, 16,384 MiB total memory); the provider returned fresh evidence with units and digest. The fixture made no network connection and did not contact OctoMiner.

The full source suite on this branch completed **481 passed, 10 skipped, 1 failed** (26.36s). The sole failure is the already tracked #48 notification-service artifact pin: expected `107ea3b45871477ab24038114d4f00b1bf92d4b78b2ca4882c859635800780c3`, actual `8f6584602d6b6a9c2e8e3f01694c75da721b40a0f1b8f64b91ec9bf587da5480`. The focused integration set completed **136 passed, 1 skipped** before the final full-suite fixture-state corrections; the final full-suite result includes those corrections.

## Acceptance boundary and open operational gates

- **Package contract: PASS.** Version, interface, configuration schema, artifact/supporting-file hashes, read-only effect, required authorization capability, dependency declaration, and bundle integrity validate. No capability grant is created by packaging or installation.
- **Isolated staging lifecycle: PASS.** The installed version is discovered and invoked through the generic provider process manager; test evidence covers activation and rollback to `STOPPED`. Other lifecycle regression tests cover durable module transitions, replacement failure, recovery, and CME authorization denial.
- **Authenticated managed live operation: NOT VERIFIED.** This workstream did not alter or invoke the shared managed runtime, change its bootstrap, create a grant, connect to OctoMiner, restart services, or use an authenticated Steward session. No current shared service version, real telemetry timestamp, live grant event, CME invocation ID, or managed rollback readback was collected here.
- **Coordinator-owned prerequisite:** add the installed manifest/configuration to the approved managed `capability_operations` and `module.capabilities` configuration, confirm the exact read-only source/host scope and required grant, then authorize the config reload and activation window. These use existing interfaces; this provider requires no CME core or Website source edit. The existing operator CLI does not create the module's package or grant.
- **Auditor gate:** independently review the source candidate, package digest, staging evidence, merged #46/#43 contracts, and the managed operational evidence after Coordinator activation. Package and fixture evidence alone do not establish a running R3A capability.
- Managed operator integration time and restart requirements remain unmeasured. The local package verify/staging commands took less than four seconds end-to-end in the recorded capture; that is not the end-to-end live integration time.
