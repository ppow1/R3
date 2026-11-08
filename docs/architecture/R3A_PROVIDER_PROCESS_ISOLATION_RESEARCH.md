# R3A Provider Process Isolation Research

Date: 2026-11-08

## Current state

`ProviderProcessManager` remains the sole owner of provider process launch, health, IPC, restart, replacement, and durable lifecycle transitions. It starts a digest-pinned worker with a restricted environment and a private Unix socket. The worker still runs as the CME OS user, so process separation currently provides fault containment, not a distinct UID, filesystem sandbox, or syscall boundary.

## Local capability check

- `/usr/bin/bwrap` is present and can establish the needed mount namespace in the isolated development environment.
- A bounded probe mounted `/` read-only, `/tmp` as a private tmpfs, and only a test workspace as writable. The process wrote into that workspace; an attempted write under `/etc` failed with `Read-only file system`.
- `unshare -Ur` was unavailable in this environment. Bubblewrap worked without that command, but the result is host-dependent and must be rechecked in the managed service account and runtime environment.
- The user systemd manager is running and accepted a basic transient scope. It rejected `NoNewPrivileges` as a scope property, so this experiment does not establish a usable systemd confinement profile.

## Integration direction

Bubblewrap could wrap the existing provider worker command while `ProviderProcessManager` continues to own the process and the canonical CME path stays unchanged. Before enabling it, the shared module contract needs a versioned, validated declaration of writable paths, required readable paths, network access, temporary storage, and the policy for hosts without the sandbox. The provider manifest must not grant paths broader than its declared resource/target scope. The host must fail closed when a module requires confinement but the requested policy cannot be enforced.

No sandbox policy field has been added to `r3a.module-manifest.v1` here. This contract change needs Coordinator agreement because it affects package authors and managed process launch. No Coordinator service was changed or restarted.

## Evidence

The actual isolated process lifecycle run used the installed runtime wheel and is recorded in [R3A_MODULE_LIFECYCLE_HARDENING_20261108.json](../evidence/R3A_MODULE_LIFECYCLE_HARDENING_20261108.json). Bubblewrap was tested as a bounded standalone filesystem probe; the lifecycle provider workers were not yet launched inside it.
