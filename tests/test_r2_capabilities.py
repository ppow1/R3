# Permanent contract regression tests for the R2 capability adapter.
import unittest

from runtime.r2_capabilities import R2Capabilities, CapabilityBridgeError


class FakeRegistry:
    def __init__(self, result=None):
        self.result = result
        self.calls = []

    def tool_specs(self):
        return [{"tool": "grace.example", "definition": {
            "type": "function", "function": {"name": "grace.example",
            "parameters": {"type": "object"}}}, "read_only": False}]

    def invoke(self, name, arguments):
        self.calls.append((name, arguments))
        return self.result


class R2CapabilityBridgeTests(unittest.TestCase):
    def test_discovery_does_not_force_read_only(self):
        adapter = R2Capabilities(FakeRegistry())
        self.assertFalse(adapter.discover()[0]["read_only"])

    def test_authorized_result_preserved(self):
        result = {"status": "ok", "authorization": {"status": "authorized",
                  "principal_id": "resident:grace", "grant_id": "g"},
                  "result": {"revision": 2}}
        registry = FakeRegistry(result)
        self.assertEqual(R2Capabilities(registry).invoke("grace.example",
                         {"scope_ref": "office:grace", "input": {}}), result)
        self.assertEqual(len(registry.calls), 1)

    def test_denial_is_fail_closed(self):
        for result in (None, {}, {"status": "error"},
                       {"status": "ok", "result": {}},
                       {"status": "ok", "authorization": {"status": "denied"}}):
            with self.subTest(result=result):
                with self.assertRaises(CapabilityBridgeError):
                    R2Capabilities(FakeRegistry(result)).invoke("grace.example", {})

    def test_invalid_arguments_not_forwarded(self):
        registry = FakeRegistry()
        with self.assertRaises(CapabilityBridgeError):
            R2Capabilities(registry).invoke("grace.example", [])
        self.assertEqual(registry.calls, [])

    def test_registry_failure_propagates(self):
        class Unavailable(FakeRegistry):
            def invoke(self, name, arguments):
                raise ConnectionError("database unavailable")
        with self.assertRaises(ConnectionError):
            R2Capabilities(Unavailable()).invoke("grace.example", {})


if __name__ == "__main__":
    unittest.main()
