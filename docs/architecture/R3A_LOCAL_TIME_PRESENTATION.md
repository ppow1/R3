# R3A local-time presentation standard

## Decision and prior implementation audit

The November 7 branch had no shared presentation-timezone setting or timezone
formatter. PostgreSQL stores `timestamptz`; runtime evidence, capability
results, telemetry snapshots, activity/event records, and diagnostics use UTC
ISO-8601 values. The diagnostic socket is a machine interface and remains UTC.
The operator CLI previously printed those values without a local rendering.
Ring 0's operational messages also had no timestamp prefix.

This change adds `r3a_runtime.timestamp_presentation` and wires the existing
human-facing R3A operator surfaces to it. It does not change stored evidence,
UTC timestamps in API contracts, machine request/response fields, or the Linux
system timezone.

## Configuration

The external bootstrap JSON accepts an optional root key:

```json
{
  "presentation_timezone": "America/New_York"
}
```

If omitted, R3A uses `America/New_York`. The value must be a valid IANA timezone
known by Python `zoneinfo`; an invalid value rejects bootstrap/reload before
the new settings are activated. `America/New_York` supplies EST/EDT and DST
transitions from the timezone database; there are no fixed UTC offsets. The
setting is recorded in sanitized configuration history. The host timezone is
not read or changed.

## Shared interface and formatting

Python presentation code imports:

```python
from r3a_runtime.timestamp_presentation import format_timestamp, human_report

local_label = format_timestamp(utc_value, settings.presentation_timezone)
report_for_people = human_report(machine_result, settings.presentation_timezone)
```

`format_timestamp` emits the local ISO timestamp with numeric offset, timezone
abbreviation, IANA name, and normalized UTC correlation value, for example:

```text
2026-11-06T11:35:00-05:00 EST [America/New_York] | UTC 2026-11-06T16:35:00Z
```

`human_report` recursively copies a report, retains each original field
unchanged, adds a companion such as `persisted_at_local`, and includes
`_presentation.timezone`. Missing timestamps display as unavailable. Invalid
or timezone-naive timestamps display as unconverted with the reason and raw
value; naive values are never assumed to be UTC or local.

The R3A CLI uses this report projection for `status`, `events`, `definitions`,
activity/report responses and operator command results. The original timestamp
keys remain byte-for-byte as returned. The diagnostic Unix socket and all
machine-to-machine capability/provider contracts remain UTC-only. Ring 0
stdout/stderr lines now begin with the shared local-plus-UTC label.

## Before and after using an R3A record

The runtime-evidence document itself carries the actual source timestamp
`Created: 2026-11-06T16:36:18Z` in its header. The report projection preserves
that exact value and adds:

| View | Timestamp |
|---|---|
| Existing R3A report timestamp | `2026-11-06T16:36:18Z` |
| Human report local companion | `2026-11-06T11:36:18-05:00 EST [America/New_York] | UTC 2026-11-06T16:36:18Z` |

The raw UTC value remains available for audit correlation. The local companion
shows the timezone explicitly.

## Surface audit and ownership

| Human-facing surface | This workstream change | Remaining integration |
|---|---|---|
| CME status, lifecycle and activity reports | CLI report projection adds local companions; diagnostic socket remains canonical UTC. | Coordinator should use `human_report` in any additional operator renderer and keep socket contracts unchanged. |
| Resident execution and verification histories | `status`/`events` report values receive local companions recursively. Durable activity/evidence values remain UTC. | Autonomy should call the shared formatter for Grace-authored summaries and resident-specific history views. |
| Engineering and capability execution records | CLI report projection covers invocation, evidence, work-order and verifier timestamp fields. No new timestamps are written. | Coordinator-managed dashboards/log viewers should use the same formatter. |
| Infrastructure and telemetry reports | Provider/source contracts remain UTC and retain source timestamp basis. | Website and telemetry consumers must format only at render time using the configured IANA timezone. |
| Human-readable logs and exports | Ring 0 process messages include local and UTC timestamps; CLI outputs add local companions. Backup/archive payloads stay canonical UTC. | Other service loggers should prefix human-readable lines through `format_timestamp`. |
| Website operational displays | No active website branch is modified. Current infrastructure adapter in this checkout is a disconnected placeholder. | Website should use `Intl.DateTimeFormat` with `timeZone: presentation_timezone` (default `America/New_York`), display the short zone name, and preserve the raw UTC value for audit/copy/export. Never use the browser's implicit local zone. |
| Notifications and alerts | No notification branch is modified. | Notification renderers should use the same configured zone for visible time and include the UTC value or a correlation link in details. Keep event payloads and delivery timestamps UTC. |
| Steward diagnostics and summaries | The local `r3a` CLI is covered by the shared report projection. | Other summary clients should consume the setting and formatter instead of manually applying offsets. |

### Workstream integration instructions

- **Coordinator / CME:** retain UTC in diagnostics, database, durable evidence,
  and APIs. Use `settings.presentation_timezone` and `human_report()` only in
  operator-facing output. Invalid config must fail before replacing active
  settings. A runtime using a changed external setting must reload through the
  normal coordinator path; this change does not reload or restart the active
  managed service.
- **Website:** read the externally supplied `presentation_timezone` alongside
  data and format ISO timestamps with `Intl.DateTimeFormat`'s explicit
  `timeZone`, e.g. `new Intl.DateTimeFormat('en-US', {year:'numeric',
  month:'short', day:'2-digit', hour:'2-digit', minute:'2-digit',
  second:'2-digit', timeZone: presentation_timezone, timeZoneName:'short'})`.
  Render both local zone label and access to original UTC.
- **Notifications:** add local time only to rendered alert text; retain source
  occurrence/received timestamps as UTC in event and delivery contracts.
- **Autonomy / Grace:** use the shared formatter for reports, never rewrite
  event evidence or model/provider timestamps. Keep `timestamp_basis` and
  source provenance next to telemetry timestamps.

## Required regression coverage

Tests in `tests/test_r3a_timestamp_presentation.py` cover:

- UTC source value preservation while adding local presentation.
- Winter EST and summer EDT.
- The spring-forward skipped hour and fall-back repeated hour, with UTC
  correlation distinguishing the two `01:30` local instants.
- Invalid timezone bootstrap rejection, default timezone, missing values,
  invalid timestamp strings, and timezone-naive values.
- Zone name and numeric offset included in the human-readable value.

Do not change PostgreSQL timestamps, evidence digests, or API contracts to
make these tests pass. DST behavior comes from `zoneinfo`, not fixed offsets.
