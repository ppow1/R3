"""Authenticated ntfy publishing for recipient notifications.

ntfy actions only navigate to the Website. They never acknowledge or resolve a
notification directly; those state changes require the Website's authenticated
Steward session and the existing durable API.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from urllib.parse import urlencode, urlsplit, urlunsplit
from typing import Any
from uuid import UUID

from r3a_runtime.timestamp_presentation import format_timestamp


_EVENT_TITLES = {
    "activity.completed": "Objective completed",
    "activity.blocked": "Objective blocked",
    "engineering.verification.completed": "Verification result",
    "steward.approval.required": "Steward approval required",
    "process.failed": "Service unavailable",
    "capability.unavailable": "Capability unavailable",
    "resident.delegation.completed": "Delegation completed",
    "process.state_transition": "Service state changed",
}
_PRIORITY = {"info": 2, "warning": 3, "error": 4}
_SAFE_TEXT = re.compile(r"[^\x09\x20-\ud7ff\ue000-\ufffd]")


class NtfyPublishError(RuntimeError):
    """Transport failure that does not expose URL, topic, or credentials."""


def _text(value: Any, limit: int = 320) -> str:
    if value is None:
        return ""
    value = _SAFE_TEXT.sub("", str(value)).replace("\r", " ").replace("\n", " ")
    value = " ".join(value.split())
    return value[:limit]


def _website_url(base_url: str, delivery_id: str, intent: str | None = None) -> str:
    try:
        parsed = urlsplit(base_url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
            raise ValueError
        _ = parsed.port
        delivery_id = str(UUID(delivery_id))
    except (TypeError, ValueError, AttributeError):
        raise ValueError("invalid notification Website destination") from None
    query = {"view": "notifications", "notification_id": delivery_id}
    if intent is not None:
        if intent not in {"acknowledgment", "resolution"}:
            raise ValueError("unsupported notification action intent")
        query["notification_intent"] = intent
    return urlunsplit(("https", parsed.netloc, "/", urlencode(query), ""))


def render_notification_presentation(delivery: dict[str, Any], *, website_base_url: str | None,
                                    presentation_timezone: str) -> dict[str, Any]:
    notification = delivery.get("notification")
    if not isinstance(notification, dict):
        raise ValueError("notification envelope is missing")
    evidence = notification.get("evidence", {})
    event_type = _text(delivery.get("event_type"), 100)
    severity = delivery.get("severity")
    if severity not in _PRIORITY:
        raise ValueError("notification severity is unsupported")
    title = _EVENT_TITLES.get(event_type, event_type.replace(".", " ").replace("_", " ").title())
    subject = _text(evidence.get("subject_id") or evidence.get("subject_type"), 100)
    prior, next_state = _text(evidence.get("prior_state"), 50), _text(evidence.get("next_state"), 50)
    if prior or next_state:
        summary = f"{title}: {subject or 'institutional service'} {prior or 'unknown'} → {next_state or 'unknown'}"
    elif subject:
        summary = f"{title}: {subject}"
    else:
        summary = title
    reason = _text(evidence.get("reason"), 400) or "No source reason was recorded."
    occurred_at = notification.get("occurred_at")
    try:
        occurred_local = format_timestamp(occurred_at, presentation_timezone)
    except (TypeError, ValueError):
        occurred_local = _text(occurred_at, 80) or "Unknown"
    source_id = _text(delivery.get("source_id"), 120)
    correlation_id = _text(delivery.get("correlation_id"), 80)
    source_event_id = _text(delivery.get("source_event_id"), 80)
    delivery_id = _text(delivery.get("delivery_id"), 80)
    needs_action = "yes" if delivery.get("requires_action") else "no"
    details = "\n".join((
        summary,
        f"Severity: {severity} · urgency: {_text(delivery.get('urgency'), 20)} · action required: {needs_action}",
        f"Source: {source_id} · {event_type}",
        f"Reason: {reason}",
        f"Occurred: {occurred_local}",
        f"Correlation: {correlation_id}",
        f"Source event: {source_event_id}",
        f"Delivery: {delivery_id}",
    ))
    urls = ({"open": _website_url(website_base_url, delivery_id),
             "acknowledgment": _website_url(website_base_url, delivery_id, "acknowledgment"),
             "resolution": _website_url(website_base_url, delivery_id, "resolution")}
            if website_base_url else {})
    actions = ([
        {"action_id": "open", "label": "Open details", "destination": urls["open"],
         "method": "view", "requires_authenticated_website": True, "mutates": False},
        {"action_id": "acknowledgment", "label": "Acknowledge", "destination": urls["acknowledgment"],
         "method": "view", "requires_authenticated_website": True, "mutates": False},
        {"action_id": "resolution", "label": "Resolve", "destination": urls["resolution"],
         "method": "view", "requires_authenticated_website": True, "mutates": False},
    ] if urls else [])
    return {
        "title": f"{severity.upper()} · {title}"[:120],
        "summary": summary,
        "details": details[:3500],
        "source": {"source_id": source_id, "event_type": event_type,
                   "source_event_id": source_event_id},
        "reason": reason,
        "occurred_at": notification.get("occurred_at"),
        "occurred_at_local": occurred_local,
        "correlation_id": correlation_id,
        "evidence_refs": list(delivery.get("evidence_refs", [])),
        "detail_url": urls.get("open"),
        "actions": actions,
    }


def render_phone_message(delivery: dict[str, Any], *, website_base_url: str,
                         presentation_timezone: str) -> dict[str, Any]:
    presentation = render_notification_presentation(delivery, website_base_url=website_base_url,
                                                    presentation_timezone=presentation_timezone)
    return {
        "title": presentation["title"],
        "message": presentation["details"],
        "priority": _PRIORITY[delivery["severity"]],
        "tags": ["r3a", delivery["severity"]],
        "click": presentation["detail_url"],
        "actions": [
            {"action": "view", "label": action["label"], "url": action["destination"], "clear": True}
            for action in presentation["actions"]
        ],
    }


class NtfyPublisher:
    """Publish a bounded actionable message to an authenticated private topic."""

    def __init__(self, base_url: str, *, topic: str, token: str,
                 website_base_url: str, timeout: float = 8):
        parsed = urlsplit(base_url)
        loopback_http = parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "::1", "localhost"}
        if not parsed.hostname or not (parsed.scheme == "https" or loopback_http) or parsed.path not in {"", "/"}:
            raise ValueError("ntfy endpoint must be HTTPS or loopback HTTP")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", topic or ""):
            raise ValueError("invalid ntfy topic")
        if not isinstance(token, str) or not token or "\n" in token or "\r" in token:
            raise ValueError("invalid ntfy token")
        if not 1 <= timeout <= 30:
            raise ValueError("invalid ntfy timeout")
        self.base_url = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
        self.topic, self._token, self.timeout = topic, token, timeout
        _website_url(website_base_url, "00000000-0000-0000-0000-000000000000")
        self.website_base_url = website_base_url

    def publish(self, delivery: dict[str, Any], *, presentation_timezone: str) -> str:
        message = render_phone_message(delivery, website_base_url=self.website_base_url,
                                       presentation_timezone=presentation_timezone)
        payload = {"topic": self.topic, **message}
        request = urllib.request.Request(self.base_url, data=json.dumps(payload).encode("utf-8"),
            method="POST", headers={"Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json", "Accept": "application/json"})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(request, timeout=self.timeout) as response:
                result = json.loads(response.read(8192))
                message_id = result.get("id") if response.status == 200 else None
                if not isinstance(message_id, str) or not message_id:
                    raise NtfyPublishError("unexpected_ntfy_response")
                return message_id
        except urllib.error.HTTPError as exc:
            raise NtfyPublishError(f"ntfy_http_{exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            if isinstance(exc, NtfyPublishError):
                raise
            raise NtfyPublishError(type(exc).__name__) from None
