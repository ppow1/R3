# R3A Institutional Directory Capability

The operation is registered in the common capability registry as
`institutional.directory.discover` (`r3a.capability-operation.v1`, revision
1.0.0, effect `read`). CME validates each invocation and enforces the matching
operation grant before calling the provider. Discovery returns a stable
technical identity and a separate human-facing presentation; discovery itself
does not authorize execution.

## Authoritative source

The provider reads Riverview's authoritative PostgreSQL schema
`riverview_authority` directly. Its projection uses `institutional_offices`,
`office_bindings`, `resident_occupants`, `capability_catalog`, and
`capability_resources`. It does not import or call the legacy R/3 website or
HR service and does not copy their SQLite records. Resident identity, office
role/status, active occupant bindings, capability ownership/action, and
registration metadata remain owned by Riverview.

R3A receives the database connection string only through the external
environment variable named by `dsn_env` (the example names
`R3A_DIRECTORY_POSTGRES_DSN`). The value is never returned in results or error
evidence. Deployment must provide a least-privilege read-only database role;
the provider additionally opens a bounded `REPEATABLE READ READ ONLY`
transaction, uses parameterized values and fixed table names, applies a
statement/connect timeout, and caps result sizes. If the DSN is missing or the
source cannot be read, it returns empty arrays with `availability` and
`freshness` set to `unavailable`; it does not fall back to another roster.

The current source fields do not include resident display names or authoritative
availability observations. The provider returns `display_name: null` and
availability `unavailable`. Capability catalog values such as `enabled`,
`availability_policy`, and `registration_blocker` are reported as source
metadata; they are not treated as provider health or execution authorization.
The source snapshot digest hashes the bounded rows observed in the single
transaction. Freshness is based on the live transaction timestamp; source row
revision evidence is retained from `binding_revision`.

## Capability and delegation semantics

Office-owned capability catalog records are returned with their authority
action, owner office, enablement/policy/blocker fields, schemas, authorization
contract, and associated resource IDs. Provider availability remains
`unavailable`/not probed unless a separate authoritative health source exists.
The R3A dynamic capability descriptors are separately returned by CME
discovery. Neither an office binding nor a directory capability record grants
permission to invoke an R3A operation. CME remains the only authorization and
invocation path.

Grace's resident capability adapter passes the provider's typed `output`
separately from source `evidence` into the next reasoning turn. This lets Grace
consume directory facts while keeping provenance and authorization distinct.
The integration test covers that adapter path with synthetic PostgreSQL
fixtures. Selecting or executing a delegate still requires AP2 policy and a
separate authorized invocation.

## Live integration limit

Comms5 does not currently expose a directory read operation, and the R3A
prototype has no Riverview read-only database credential configured. The
prototype configuration references `R3A_DIRECTORY_POSTGRES_DSN` but leaves its
value unset. Therefore the operation is discoverable and contract-valid, but
its live provider response is explicitly unavailable until Riverview provisions
an approved least-privilege credential/API for R3A. Do not substitute the
legacy R/3 HR SQLite file or invent resident/capability facts.
