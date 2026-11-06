# R/3 Runtime Health Contract

Health snapshot schema version 2 distinguishes configuration from observed activity.

- `resident_execution_configured` reports enabled resident handlers registered at startup.
- `resident_active_executions` lists scheduler tasks active when the snapshot was written.
- `resident_inference_configured` reports resident inference handlers configured at startup.
- `resident_inference_response_observed` is true only after an assistant response has been durably recorded in `resident_turns`.
- `resident_tool_discovery_connected` reports whether every configured tool endpoint answered discovery during this health cycle.
- `resident_tool_execution_configured` reports whether any resident has a configured tool client.
- `resident_tool_execution_status` remains `unverified`; discovery does not prove an authorized tool invocation succeeded.

The former `resident_execution_connected`, `resident_inference_connected`, and `resident_tool_execution_connected` fields are omitted. Those names implied live execution or inference connectivity from registration or discovery alone. Health snapshots do not perform synthetic model or tool invocations.
