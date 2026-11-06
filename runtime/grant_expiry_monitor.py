"""Read-only expiry visibility for Grace's two temporary proposal grants."""
from __future__ import annotations

import logging
import threading
import time

LOG = logging.getLogger("r3.grant_expiry")
WARNING_WINDOW_SECONDS = 50 * 60 * 60
SCAN_INTERVAL_SECONDS = 60 * 60
_logged_state: dict[str, str] = {}
_log_lock = threading.Lock()


def scan_once(authority, *, now: float | None = None) -> list[dict]:
    """Log each newly observed expiring grant once; never renew or mutate it."""
    grants = authority.expiring_proposal_grants(
        now=now, warning_window=WARNING_WINDOW_SECONDS)
    for grant in grants:
        with _log_lock:
            if _logged_state.get(grant["grant_id"]) == grant["state"]:
                continue
            _logged_state[grant["grant_id"]] = grant["state"]
        if grant["state"] in {"EXPIRED", "MISSING_EXPIRY"}:
            event = "AUTHORIZATION_EXPIRED" if grant["state"] == "EXPIRED" else "GRANT_MISSING_EXPIRY"
            LOG.error("%s grant_id=%s principal=%s action=%s expires_at=%s; %s",
                      event,
                      grant["grant_id"], grant["principal"], grant["action"],
                      grant["expires_at_utc"], grant["renewal_action"])
        else:
            LOG.warning("GRANT_EXPIRING grant_id=%s principal=%s resource=%s action=%s scope=%s operation=%s issued_at=%s expires_at=%s; %s",
                        grant["grant_id"], grant["principal"], grant["resource"],
                        grant["action"], grant["scope"], grant["operation"],
                        grant["issued_at_utc"], grant["expires_at_utc"], grant["renewal_action"])
    return grants


def start_monitor(authority, *, interval: float = SCAN_INTERVAL_SECONDS) -> threading.Thread:
    """Run a best-effort read-only scan in a daemon; the diagnostics endpoint remains authoritative."""
    if interval <= 0:
        raise ValueError("positive monitor interval required")

    def run():
        while True:
            try:
                scan_once(authority)
            except Exception:
                LOG.exception("Grace proposal grant expiry scan failed")
            time.sleep(interval)

    thread = threading.Thread(target=run, name="r3-grant-expiry-monitor", daemon=True)
    thread.start()
    return thread
