import unittest
from unittest.mock import patch

from runtime.native_tools import NativeTools, ToolContractError


class NativeCorrelationContractTests(unittest.TestCase):
    def setUp(self):
        self.client = NativeTools(
            "http://127.0.0.1:8765",
            timeout=5,
            allowed_tools=("r3.test.write",),
            credential="test-only-credential",
        )
        self.descriptor = {
            "tool": "r3.test.write",
            "read_only": False,
        }

    def test_correlation_is_transport_metadata(self):
        arguments = {"scope_ref": "scope:test", "value": 42}
        with patch.object(
            NativeTools, "_request",
            return_value={"ok": True, "result": {"done": True}},
        ) as request:
            self.client.invoke(
                self.descriptor,
                arguments,
                correlation_id="tool-call-123",
            )

        method, path, payload = request.call_args.args
        self.assertEqual(method, "POST")
        self.assertEqual(path, "/v1/tools/invoke")
        self.assertEqual(payload["correlation_id"], "tool-call-123")
        self.assertEqual(payload["params"], arguments)
        self.assertNotIn("correlation_id", payload["params"])

    def test_write_without_correlation_denied(self):
        with self.assertRaises(ToolContractError):
            self.client.invoke(
                self.descriptor,
                {"scope_ref": "scope:test"},
            )


if __name__ == "__main__":
    unittest.main()
