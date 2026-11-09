"""
R3 CONTROLLED TEST SOURCE
File: tests/test_r3a_portal_login_proxy_config.py
Component: R3A AP3 Remote Access
File Revision: 1.0.0
Created: 2026-11-09T13:04:00Z
Created By: Codex GPT-6
Purpose: Guard the LAN-only Nginx mount for the existing R3 account login application.
Execution Model: unittest static configuration contract assertions.
Observability: Checks LAN bind/ACL, exact mutation Origin, and existing loopback upstream.
Authority: Steward directive AP3 Remote Access; Issues #49, #51, #56.
Changed: 2026-11-09T13:04:00Z | AP3-M1 | Codex GPT-6 | Add LAN proxy configuration regression checks.
Supersedes: None.
Contracts: R3 portal login at 192.168.1.155:8303; existing app at 127.0.0.1:18303.
Tests: python -m unittest tests.test_r3a_portal_login_proxy_config.
History/Predecessor: New file; initial publication recorded in Git.
"""

from pathlib import Path
import unittest


CONFIG = Path(__file__).parents[1] / "deploy/nginx/r3-steward-login-lan.conf"


class PortalLoginProxyConfigTests(unittest.TestCase):
    def test_mount_is_lan_bound_and_uses_existing_account_app(self):
        config = CONFIG.read_text(encoding="utf-8")

        self.assertIn("listen 192.168.1.155:8303;", config)
        self.assertIn("allow 192.168.1.0/24;", config)
        self.assertIn("deny all;", config)
        self.assertIn("proxy_pass http://127.0.0.1:18303;", config)
        self.assertIn("proxy_set_header Host $http_host;", config)
        self.assertIn("proxy_set_header X-Forwarded-Proto $scheme;", config)

    def test_mutations_require_the_exact_configured_lan_origin(self):
        config = CONFIG.read_text(encoding="utf-8")

        self.assertIn(
            r"~^(POST|PUT|PATCH|DELETE)\|http://192\.168\.1\.155:8303$ 0;",
            config,
        )
        self.assertIn("if ($r3a_login_invalid_origin) { return 403; }", config)
        self.assertNotIn("proxy_pass http://127.0.0.1:8767", config)


if __name__ == "__main__":
    unittest.main()
