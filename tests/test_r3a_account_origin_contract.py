"""
R3 CONTROLLED TEST SOURCE
File: tests/test_r3a_account_origin_contract.py
Component: R3A AP3 Remote Access
File Revision: 1.0.0
Created: 2026-11-09T13:30:00Z
Created By: Codex GPT-6
Purpose: Guard the exact LAN Origin binding for the existing authoritative account provider.
Execution Model: unittest checks the deployment override; opt-in loopback integration probes have no credentials.
Observability: Confirms exact origin allowlisting and foreign-origin rejection without account lookup.
Authority: Steward directive AP3 Remote Access; Issues #49 and #56.
Changed: 2026-11-09T13:30:00Z | AP3-M1 | Codex GPT-6 | Add allowlist and no-credential live regression checks.
Supersedes: None.
Contracts: Existing R3 account authority accepts HTTP LAN login only at 192.168.1.155:8303.
Tests: python -m unittest tests.test_r3a_account_origin_contract.
History/Predecessor: New file; initial publication recorded in Git.
"""
from __future__ import annotations

import os
from pathlib import Path
import unittest
import urllib.error
import urllib.request


OVERRIDE = Path(__file__).parents[1] / "deploy/systemd/riverview-account-lan-origin.conf"
LAN_ORIGIN = "http://192.168.1.155:8303"
AUTHORITY = os.environ.get("R3A_ACCOUNT_AUTHORITY_URL", "http://127.0.0.1:8767")


class AccountOriginContractTests(unittest.TestCase):
    def test_override_retains_https_origins_and_adds_only_exact_lan_origin(self):
        text = OVERRIDE.read_text(encoding="utf-8")
        expected = (
            'Environment="RIVERVIEW_PUBLIC_ORIGINS='
            'https://192.168.1.155,https://riverview.ionoge.com,'
            'http://192.168.1.155:8303"'
        )
        self.assertIn(expected, text)
        self.assertNotIn("*", text)


@unittest.skipUnless(os.environ.get("R3A_ACCOUNT_ORIGIN_LIVE_TEST") == "1",
                     "requires the coordinated account-authority LAN Origin deployment")
class LiveAccountOriginTests(unittest.TestCase):
    def _post_without_credentials(self, origin: str) -> int:
        request = urllib.request.Request(
            AUTHORITY.rstrip("/") + "/api/v1/auth/session",
            data=b"{}",
            headers={"Content-Type": "application/json", "Origin": origin},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                return response.status
        except urllib.error.HTTPError as error:
            return error.code

    def test_exact_lan_origin_reaches_validation_without_account_lookup(self):
        # Empty object is rejected by request-shape validation before account lookup.
        self.assertEqual(400, self._post_without_credentials(LAN_ORIGIN))

    def test_untrusted_origin_remains_denied(self):
        self.assertEqual(403, self._post_without_credentials("https://attacker.invalid"))


if __name__ == "__main__":
    unittest.main()
