# Engineering Workspace Capability Module

This package contains the digest-pinned implementation for the existing
`engineering.workspace.apply_patch` capability operation. The operation ID,
work-order scope, evidence requirement, and independent verifier contract remain
unchanged. Grace receives no direct filesystem access; CME performs grants and
work-order validation before invoking the provider.

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
grant plus a validated Engineering work order remain necessary for invocation.

After the operation is loaded into CME's registry, use the generic
`capability.module.install`, `.activate`, `.status`, `.deactivate`, and
`.replace` controls. A new implementation must use a new immutable provider
version and artifact digest. No CME source edit is needed to install, disable,
or replace a configured provider version.
