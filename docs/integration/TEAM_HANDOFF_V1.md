# Unified Baseline v1 — Team Handoff

## Website team
Start from the published baseline SHA.
Priority: persistent resident-specific Chat.
Reuse native R/3 authentication, resident identity, and grants.
Do not revive the portal authentication proxy.
Acceptance: conversation isolation, persistence, access control,
resident selection, logout/revocation, and regression coverage.

## HR team
Start from the same baseline SHA.
Audit all existing residents and personnel records before creation.
Create missing personnel records through governed HR operations.
Produce a roster-to-record reconciliation with provenance.
Do not assign capabilities without approved grants.

## Grace autonomy team
Start from the same baseline SHA.
Connect resident lifecycle and identity to the governed execution
pipeline. Keep reviewer independence and fail-closed acceptance.
Resident identity and task history must survive model unloading.
Demonstrate one end-to-end independently verified work order.

## Integration ownership
All three teams share one baseline commit.
Changes to shared contracts require integration review.
No team should fork authentication, identity, grants, or HR storage.
