# Engineering Workspace Capability Module

This package contains the digest-pinned implementation for the existing
`engineering.workspace.apply_patch` capability operation and the registered
`r3a.engineering.workflow` durable handler for `engineering.execute`. The handler
owns proposal, work-order, verifier, and resident-decision coordination. CME
continues to own generic activity scheduling, handler authorization, canonical
capability invocation, checkpoint persistence, audit, and recovery. Residents
receive no direct filesystem access.

To configure a development instance, add the operation ID to the instance's
`module.capabilities` list and add this external manifest/config pair to its
existing `capability_operations` array:

```json
{
  "manifest": "/configured/r3a_plugins/engineering_workspace/manifest.json",
  "configuration": "/configured/r3a_plugins/engineering_workspace/config.json"
}
```

Use a writable isolated workspace path in `config.json`; do not point it at a
production repository or the R3 source checkout. The manifest pins the provider
artifact and validates configuration. CME's existing `engineering.workspace.apply_patch`
grant remains necessary for invocation.

Submit `engineering.execute` through the versioned generic activity-intake
contract with the objective and Engineering assignment in `activity.input`. The
handler requests resident decisions and bounded operations through the generic
v1.1 handler continuation; CME validates grants and invokes registered providers.
Isolated writes must not be submitted as direct capability invocations.

After the operation is loaded into CME's registry, use the generic
`capability.module.install`, `.activate`, `.status`, `.deactivate`, and
`.replace` controls. A new implementation must use a new immutable provider
version and artifact digest. No CME source edit is needed to install, disable,
or replace a configured provider version.
