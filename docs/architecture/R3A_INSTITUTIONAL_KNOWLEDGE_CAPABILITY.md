# R3A institutional knowledge retrieval capability

Grace selects the existing `institution.knowledge.read` operation through the
resident capability interface. In the canonical configuration, that identity
is registered from `r3a_plugins/institutional_knowledge/manifest.json` with
the common `r3a.capability-operation.v1` contract and a digest-pinned provider.
This evolves the existing operation rather than adding a parallel search tool.

The provider reuses `r3a_runtime.knowledge.retrieve_bytes` for deterministic
fact extraction and matching. Its external configuration lists the source IDs,
absolute document paths, freshness thresholds, and result/document limits.
The included source example points at the versioned R3A process state machine;
operators must configure real source paths for the runtime in use.

Each returned fact carries the configured source ID, file URI, source fact
path, SHA-256 document revision, excerpt digest, file modification time,
retrieval timestamp, and freshness. Missing, oversized, or unreadable documents
remain visible as unavailable source observations. Stale documents remain
identified as stale. A query with no matching source fact returns no evidence.
Source reads are bounded and hash the exact bytes parsed by the extractor.

CME continues to check the activity-scoped `institution.knowledge.read` grant,
dispatch the provider, and persist the capability result in Grace's existing
continuation state. Grace remains responsible for selecting the operation,
reasoning over its output, and citing supplied evidence. Registry presence
does not create a grant. Existing configurations without the canonical
operation retain the temporary legacy adapter until migrated.

The live AP1 prototype configuration currently references
`/home/admin1/r3a-phase0/r3a_runtime/state_machines/process.json` and runs from
that separate runtime checkout. Enabling this implementation in that service
requires activating the new manifest/provider in its runtime configuration
and loading the matching source revision; unit/integration tests alone are not
live acceptance evidence.
