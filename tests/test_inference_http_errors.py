# R3 CONTROLLED SOURCE
# File: tests/test_inference_http_errors.py
# Component: R3-INFERENCE-HTTP-REGRESSION
# File Revision: 1.0.0
# Created: 2026-11-02 UTC (date precision)
# Created By: ChatGPT GPT-6
# Purpose: Verify HTTP error classification without disclosing response content.
# Execution Model: Python unittest with mocked urllib transport, outside production.
# Observability: unittest assertions.
# Dependencies: Python standard library; runtime.resident_inference.
# Authority: R3 engineering test policy; permanent general-purpose transport contract.
# Changed: 2026-11-02 UTC | R3-GRACE-005 | Initial diagnostic regression.
# Supersedes: None
# Contracts: hints/engineering-test-policy.md
# Tests: python3 -m unittest discover -s tests -p test_inference_http_errors.py -v
# History/Predecessor: New file.
from __future__ import annotations

import io
import json
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from runtime.resident_inference import InferenceEndpoint


class HttpErrorTests(unittest.TestCase):
    def test_inference_probe_uses_models_endpoint_and_configured_timeout(self):
        endpoint = InferenceEndpoint("http://127.0.0.1:8080/v1", "model", timeout=3)
        response = MagicMock()
        response.status = 200
        response.read.return_value = json.dumps({"data": [{"id": "model"}]}).encode()
        response.__enter__.return_value = response
        with patch("runtime.resident_inference.urllib.request.urlopen",
                   return_value=response) as open_url:
            endpoint.probe()
        request = open_url.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:8080/v1/models")
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(open_url.call_args.kwargs["timeout"], 3)

    def test_inference_probe_accepts_model_name_in_supported_models_shape(self):
        endpoint = InferenceEndpoint("http://127.0.0.1:8080/v1", "configured-model")
        response = MagicMock()
        response.status = 200
        response.read.return_value = json.dumps({
            "models": [{"name": "other-name", "aliases": ["configured-model"]}]
        }).encode()
        response.__enter__.return_value = response
        with patch("runtime.resident_inference.urllib.request.urlopen", return_value=response):
            endpoint.probe()

    def test_inference_probe_rejects_unadvertised_configured_model(self):
        endpoint = InferenceEndpoint("http://127.0.0.1:8080/v1", "configured-model")
        response = MagicMock()
        response.status = 200
        response.read.return_value = json.dumps({"data": [{"id": "different-model"}]}).encode()
        response.__enter__.return_value = response
        with patch("runtime.resident_inference.urllib.request.urlopen", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "Configured inference model unavailable"):
                endpoint.probe()

    def test_inference_probe_rejects_invalid_model_list(self):
        endpoint = InferenceEndpoint("http://127.0.0.1:8080/v1", "configured-model")
        response = MagicMock()
        response.status = 200
        response.read.return_value = b"not-json"
        response.__enter__.return_value = response
        with patch("runtime.resident_inference.urllib.request.urlopen", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "Invalid inference model list"):
                endpoint.probe()

    def test_inference_probe_reports_http_status_without_reading_body(self):
        endpoint = InferenceEndpoint("http://127.0.0.1:8080/v1", "model")
        failure = urllib.error.HTTPError(
            "http://127.0.0.1:8080/v1/models", 503, "Unavailable", {},
            io.BytesIO(b"private response body")
        )
        with patch("runtime.resident_inference.urllib.request.urlopen", side_effect=failure):
            with self.assertRaisesRegex(RuntimeError, "Inference HTTP 503") as caught:
                endpoint.probe()
        self.assertNotIn("private response body", str(caught.exception))

    def test_structured_error_code_preserved_without_body_disclosure(self):
        body = json.dumps({
            "error": {
                "type": "invalid_request_error",
                "code": "context_length_exceeded",
                "message": "private tool output must not be persisted",
            }
        }).encode()
        failure = urllib.error.HTTPError(
            "http://127.0.0.1:8080/v1/chat/completions", 400,
            "Bad Request", {}, io.BytesIO(body)
        )
        endpoint = InferenceEndpoint("http://127.0.0.1:8080/v1", "model")
        with patch("runtime.resident_inference.urllib.request.urlopen", side_effect=failure):
            with self.assertRaises(RuntimeError) as caught:
                endpoint.complete([{"role": "user", "content": "private request"}])
        message = str(caught.exception)
        self.assertIn("Inference HTTP 400", message)
        self.assertIn("invalid_request_error", message)
        self.assertIn("context_length_exceeded", message)
        self.assertNotIn("private tool output", message)
        self.assertNotIn("private request", message)


if __name__ == "__main__":
    unittest.main()
