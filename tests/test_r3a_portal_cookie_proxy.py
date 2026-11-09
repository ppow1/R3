"""
R3 CONTROLLED TEST SOURCE
File: tests/test_r3a_portal_cookie_proxy.py
Component: R3A AP3 Remote Access
File Revision: 1.0.0
Created: 2026-11-09T14:30:00Z
Created By: Codex GPT-6
Purpose: Verify Nginx clears Secure only on the two R3 portal cookies for the HTTP LAN exception.
Execution Model: Isolated local Nginx proxy and synthetic upstream Set-Cookie headers.
Observability: Checks cookie names and attributes only; synthetic values are never emitted.
Authority: Steward directive R3A Remote Access; Issues #49, #51, #56.
Changed: 2026-11-09T14:30:00Z | AP3-M1 | Codex GPT-6 | Test scoped LAN cookie flag transformation.
Supersedes: None.
Contracts: rv_account_session; rv_account_csrf; HttpOnly; SameSite; host-only Path=/.
Tests: python -m unittest tests.test_r3a_portal_cookie_proxy.
History/Predecessor: New file; initial publication recorded in Git.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path
import threading
import time
import unittest
import urllib.request


class _CookieUpstream(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Set-Cookie", "rv_account_session=synthetic; Path=/; Secure; HttpOnly; SameSite=Lax")
        self.send_header("Set-Cookie", "rv_account_csrf=synthetic; Path=/; Secure; SameSite=Strict")
        self.send_header("Set-Cookie", "unrelated=synthetic; Path=/; Secure; HttpOnly; SameSite=Lax")
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, _format, *_args):
        return


@unittest.skipUnless(shutil.which("nginx"), "Nginx binary is required for proxy cookie integration test")
class PortalCookieProxyTests(unittest.TestCase):
    def test_lan_proxy_removes_secure_only_from_expected_portal_cookies(self):
        upstream = ThreadingHTTPServer(("127.0.0.1", 0), _CookieUpstream)
        upstream_port = upstream.server_address[1]
        upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        upstream_thread.start()

        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            proxy_port = sock.getsockname()[1]

        with tempfile.TemporaryDirectory(prefix="r3a-cookie-proxy-test-") as temp:
            root = Path(temp)
            config = root / "nginx.conf"
            config.write_text(f"""worker_processes 1;
pid {root / 'nginx.pid'};
error_log {root / 'error.log'};
events {{ worker_connections 32; }}
http {{
    access_log off;
    server {{
        listen 127.0.0.1:{proxy_port};
        location / {{
            proxy_pass http://127.0.0.1:{upstream_port};
            proxy_cookie_flags rv_account_session nosecure;
            proxy_cookie_flags rv_account_csrf nosecure;
        }}
    }}
}}
""", encoding="utf-8")
            subprocess.run(["nginx", "-t", "-c", str(config), "-p", temp],
                           check=True, capture_output=True, text=True)
            process = subprocess.Popen(["nginx", "-c", str(config), "-p", temp,
                                        "-g", "daemon off;"],
                                       stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)
            try:
                response = None
                for _ in range(30):
                    try:
                        response = urllib.request.urlopen(
                            f"http://127.0.0.1:{proxy_port}/", timeout=1)
                        break
                    except OSError:
                        if process.poll() is not None:
                            self.fail("isolated Nginx exited before accepting the test request")
                        time.sleep(0.05)
                self.assertIsNotNone(response, "isolated Nginx did not start")
                cookies = response.headers.get_all("Set-Cookie") or []
                by_name = {cookie.split("=", 1)[0]: cookie for cookie in cookies}
                self.assertEqual({"rv_account_session", "rv_account_csrf", "unrelated"},
                                 set(by_name))
                session = by_name["rv_account_session"].lower()
                csrf = by_name["rv_account_csrf"].lower()
                unrelated = by_name["unrelated"].lower()
                self.assertNotIn("secure", session)
                self.assertIn("httponly", session)
                self.assertIn("samesite=lax", session)
                self.assertIn("path=/", session)
                self.assertNotIn("domain=", session)
                self.assertNotIn("secure", csrf)
                self.assertIn("samesite=strict", csrf)
                self.assertNotIn("httponly", csrf)
                self.assertNotIn("domain=", csrf)
                self.assertIn("secure", unrelated)
                self.assertIn("httponly", unrelated)
            finally:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
                upstream.shutdown()
                upstream.server_close()
                upstream_thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
