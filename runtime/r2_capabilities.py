# R3 CONTROLLED SOURCE
# File: runtime/r2_capabilities.py
# Purpose: Adapt the existing R2 exact-grant capability registry to R3 tool protocol.
# Authority: R2 GraceCapabilityRegistry is the sole authorization/execution source.
"""Protocol adapter; never grants capabilities or executes tools independently."""
from __future__ import annotations

import json


class CapabilityBridgeError(RuntimeError):
    pass


class R2Capabilities:
    """Expose an injected, fully configured R2 GraceCapabilityRegistry.

    The caller is responsible for obtaining the existing R2 registry from its
    trusted runtime composition root, including resident credentials and DSN.
    No secrets are accepted in HTTP payloads or stored here.
    """

    def __init__(self, registry):
        for method in ("tool_specs", "invoke"):
            if not callable(getattr(registry, method, None)):
                raise TypeError("Existing R2 capability registry required")
        self.registry = registry

    def discover(self):
        specs = self.registry.tool_specs()
        if not isinstance(specs, list):
            raise CapabilityBridgeError("R2 capability discovery unavailable")
        result = []
        for spec in specs:
            if not isinstance(spec, dict):
                raise CapabilityBridgeError("Invalid R2 capability specification")
            # R2 owns the authorization status and executable catalog.
            name = spec.get("tool") or spec.get("name")
            definition = spec.get("definition")
            if not isinstance(name, str) or not name or not isinstance(definition, dict):
                raise CapabilityBridgeError("Invalid R2 tool contract")
            if definition.get("function", {}).get("name") != name:
                raise CapabilityBridgeError("R2 tool name mismatch")
            result.append({"tool": name, "definition": definition,
                           "read_only": spec.get("read_only", False)})
        return result

    def invoke(self, name, params):
        if not isinstance(name, str) or not isinstance(params, dict):
            raise CapabilityBridgeError("Invalid invocation")
        # R2 validates exact grants, scope, arguments, and registered adapters.
        envelope = self.registry.invoke(name, params)
        if not isinstance(envelope, dict) or envelope.get("status") != "ok":
            raise CapabilityBridgeError("R2 capability invocation denied or failed")
        authorization = envelope.get("authorization")
        if not isinstance(authorization, dict) or authorization.get("status") != "authorized":
            raise CapabilityBridgeError("R2 authorization evidence missing")
        return envelope
