# R3A Institutional Directory Capability

The directory operation is registered in the existing capability registry as
`institutional.directory.discover` (`r3a.capability-operation.v1`, revision
1.0.0, effect `read`). CME validates every invocation, evaluates the
`institutional.directory.read` grant, records the decision, and only then calls
the R3A-owned provider. Discovery returns the descriptor and a separate human
presentation projection; it does not authorize invocation.

## Source and ownership

The provider reads the externally configured HR SQLite source using SQLite
`mode=ro` and `PRAGMA query_only=ON`. It does not import or call the older R/3
website, HR service, or their capability dispatcher. The source remains owned by
HR; R3A owns the adapter, output contract, provenance, freshness evaluation,
and capability-registry projection. The environment variable
`R3A_HR_DIRECTORY_DATABASE` names the configured source path. No database path
or resident roster is embedded in Python or the manifest.

The adapter projects HR resident ID, display name, office, status, record
schema/revision, and the `role` field only when HR classifies it as `public`.
It does not return other fields or authority-principal extensions. Every
record's `availability` and `responsibilities` fields carry explicit states;
absence in HR data is never translated into an inferred assignment or a
positive availability claim. Source freshness uses the SQLite file modification
timestamp, carries the collection timestamp and maximum age, and can return
stale data with an explicit stale state.

## Responsibilities and capability association

The current HR resident-record schema has no structured office responsibility
or responsibility-to-capability relationship. The versioned
`r3a.institutional-responsibility-catalog.v1` schema is therefore an optional
HR-owned external data extension, selected through the environment variable
named by `responsibility_catalog_path_env`. A configured catalog binds an exact
HR office label to sourced responsibility IDs/descriptions and canonical
operation IDs. The provider resolves those operation IDs against the live R3A
registry and includes their unchanged descriptors and separate presentation.
Unknown IDs remain marked `not_registered`; authorization is never inferred.

Until HR supplies this catalog, office responsibility and capability binding
states remain `unavailable`. The provider still returns source-backed resident
and office facts plus the current dynamic R3A capability descriptors so Grace
can consume them through the existing read-capability tool and evidence path.
Grace/AP2 owns any delegate selection; execution still requires the normal CME
invocation grant and effect controls.

## Output provenance

The invocation output is `r3a.institutional-directory.v1`. CME separately
persists the canonical invocation result, authorization evidence, and provider
evidence. The provider evidence includes the HR source contract and digest, file
timestamp/freshness, returned HR record revisions, R3A registry configuration
revision, and responsibility-catalog source digest/state. Source facts,
registered capability descriptors, and execution authorization remain
distinguishable in the output.
