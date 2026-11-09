"""Versioned HTTP boundary for independently deployed institutional notifications."""
from __future__ import annotations

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import parse_qs, urlparse
from typing import Any
import uuid

from r3a_runtime.timestamp_presentation import format_timestamp, resolve_timezone
from r3a_runtime.notifications import validate_notification_envelope
from r3a_runtime.notification_delivery import route_notification

from .store import NotificationConflict, NotificationForbidden, NotificationStore
from .ntfy import NtfyPublisher, render_notification_presentation


MODULE_ID = "r3a.notifications"
MODULE_VERSION = "1.2.1"
MAX_BODY_BYTES = 1_048_576


class ConfigurationError(ValueError):
    pass


def load_config(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"notification module configuration cannot be loaded: {type(exc).__name__}") from None
    schema=json.loads((Path(__file__).with_name("config.schema.json")).read_text(encoding="utf-8"))
    from r3a_runtime.capability_contracts import validate_json
    validate_json(value,schema)
    if not isinstance(value, dict) or not {"contract_id", "contract_version", "dsn_env",
            "source_token_env", "steward_token_env", "steward_principal_env", "presentation_timezone",
            "source_ids", "subscriptions"} <= value.keys() or value.keys() - {
            "contract_id", "contract_version", "dsn_env", "source_token_env", "steward_token_env",
            "steward_principal_env", "presentation_timezone", "source_ids", "subscriptions", "ntfy",
            "website_base_url_env"}:
        raise ConfigurationError("notification module config has an invalid field set")
    if value["contract_id"] != "r3a.notification-module-config" or value["contract_version"] not in {"1.0.0", "1.1.0"}:
        raise ConfigurationError("unsupported notification module config contract")
    for name in ("dsn_env", "source_token_env", "steward_token_env", "steward_principal_env"):
        if not isinstance(value[name], str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", value[name]):
            raise ConfigurationError(f"{name} must name an environment variable")
    resolve_timezone(value["presentation_timezone"])
    if (not isinstance(value["source_ids"], list) or not value["source_ids"]
            or any(not isinstance(item,str) or not item.strip() for item in value["source_ids"])):
        raise ConfigurationError("source_ids must be a nonempty allowlist")
    subscriptions = value["subscriptions"]
    if not isinstance(subscriptions, list):
        raise ConfigurationError("subscriptions must be an array")
    seen: set[str] = set()
    categories = {"resident_objective_completed", "resident_objective_blocked",
                  "independent_verification_failed", "steward_approval_required",
                  "service_or_capability_unavailable", "resident_delegation_completed",
                  "service_state_changed"}
    for rule in subscriptions:
        required = {"category", "event_type", "urgency", "requires_action"}
        allowed = required | {"filter", "recipient"}
        if not isinstance(rule, dict) or not required <= rule.keys() or not rule.keys() <= allowed:
            raise ConfigurationError("subscription fields are invalid")
        if rule["category"] not in categories or rule["event_type"] in seen:
            raise ConfigurationError("subscription category is unsupported or event type duplicated")
        seen.add(rule["event_type"])
        if (not isinstance(rule["event_type"], str) or not rule["event_type"].strip()
                or rule["urgency"] not in {"low", "normal", "high", "critical"}
                or not isinstance(rule["requires_action"], bool)):
            raise ConfigurationError("subscription event type/action metadata is invalid")
        filters = rule.get("filter", {})
        if (not isinstance(filters, dict) or set(filters) - {"activity_type", "evidence_equals"}
                or ("evidence_equals" in filters and not isinstance(filters["evidence_equals"], dict))):
            raise ConfigurationError("subscription filter is invalid")
        recipient=rule.get("recipient")
        if (not isinstance(recipient,dict) or set(recipient)!={"kind","office_role"}
                or recipient["kind"] not in {"resident","office","steward"}
                or not isinstance(recipient["office_role"],str) or not recipient["office_role"].strip()):
            raise ConfigurationError("subscription recipient must select an authoritative directory role")
    ntfy = value.get("ntfy", {"enabled": False})
    if not isinstance(ntfy, dict) or ntfy.get("enabled") not in {True, False}:
        raise ConfigurationError("ntfy config must state whether phone delivery is enabled")
    if ntfy["enabled"]:
        if set(ntfy) != {"enabled", "base_url", "topic_env", "token_file_env", "timeout_seconds"}:
            raise ConfigurationError("enabled ntfy config has an invalid field set")
        for field in ("topic_env", "token_file_env"):
            if not isinstance(ntfy[field], str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", ntfy[field]):
                raise ConfigurationError(f"ntfy {field} must name an environment variable")
        if not isinstance(ntfy["base_url"], str) or not 1 <= ntfy["timeout_seconds"] <= 30:
            raise ConfigurationError("ntfy endpoint or timeout is invalid")
    elif set(ntfy) != {"enabled"}:
        raise ConfigurationError("disabled ntfy config accepts only enabled=false")
    if "website_base_url_env" in value and (not isinstance(value["website_base_url_env"], str)
            or not re.fullmatch(r"[A-Z][A-Z0-9_]*",value["website_base_url_env"])):
        raise ConfigurationError("website_base_url_env must name an environment variable")
    return value


def create_server(config: dict[str, Any], *, host: str = "127.0.0.1", port: int = 0,
                  store: NotificationStore | None = None,
                  phone_publisher: NtfyPublisher | None = None) -> ThreadingHTTPServer:
    if host not in {"127.0.0.1", "::1", "localhost"} and os.environ.get("R3A_NOTIFICATION_ALLOW_NONLOCAL") != "1":
        raise ConfigurationError("non-local bind requires an explicitly configured authenticated gateway")
    dsn = os.environ.get(config["dsn_env"], "")
    source_token = os.environ.get(config["source_token_env"], "")
    steward_token = os.environ.get(config["steward_token_env"], "")
    steward_principal = os.environ.get(config["steward_principal_env"], "")
    if not dsn or not source_token or not steward_token or not steward_principal:
        raise ConfigurationError("notification service requires configured database, source, and Steward credentials")
    phone_publisher = phone_publisher or _configured_ntfy_publisher(config)
    store = store or NotificationStore(dsn)
    store.initialize(MODULE_VERSION)

    class Handler(BaseHTTPRequestHandler):
        server_version = f"R3A-Notifications/{MODULE_VERSION}"

        def __init__(self,*args,**kwargs):
            self.request_id=str(uuid.uuid4())
            super().__init__(*args,**kwargs)

        def log_message(self, _format: str, *_args: Any) -> None:
            return

        def _log(self,log_type: str,**fields: Any) -> None:
            record={"event_type":log_type,"request_id":self.request_id,
                    "occurred_at":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),**fields}
            print(json.dumps(record,separators=(",",":"),ensure_ascii=False),file=sys.stderr,flush=True)

        def _send(self, status: int, value: Any) -> None:
            body = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Request-ID",self.request_id)
            self.end_headers()
            self.wfile.write(body)

        def _body(self) -> dict[str, Any]:
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise ValueError("invalid content length") from None
            if size < 1 or size > MAX_BODY_BYTES:
                raise ValueError("request body size is invalid")
            try:
                value = json.loads(self.rfile.read(size))
            except (UnicodeError, json.JSONDecodeError):
                raise ValueError("request body must be JSON") from None
            if not isinstance(value, dict):
                raise ValueError("request body must be a JSON object")
            return value

        def _bearer(self, expected: str) -> bool:
            supplied = self.headers.get("Authorization", "")
            prefix, _, token = supplied.partition(" ")
            return prefix.casefold() == "bearer" and bool(token) and hmac.compare_digest(token, expected)

        def _error(self, exc: Exception) -> None:
            if isinstance(exc, NotificationForbidden):
                status = 403
            elif isinstance(exc, NotificationConflict):
                status = 409
            elif isinstance(exc, (ValueError, KeyError)):
                status = 400
            else:
                status = 503
            self._log("notification.http.error",status=status,error_type=type(exc).__name__,path=urlparse(self.path).path)
            self._send(status, {"contract":"r3a.notification-inbox.v1","error":type(exc).__name__,
                                "message":str(exc) if status < 500 else "notification service dependency failed"})

        def do_GET(self) -> None:
            parsed=urlparse(self.path)
            if parsed.path == "/healthz":
                self._send(200,{"module_id":MODULE_ID,"module_version":MODULE_VERSION,"state":"ACTIVE",
                                "storage":"postgresql","observed_at":datetime.now(timezone.utc).isoformat().replace("+00:00","Z")})
                return
            if parsed.path != "/api/v1/notifications":
                self._send(404,{"error":"not_found"}); return
            if not self._bearer(steward_token):
                self._log("notification.recipient.unauthorized")
                self._send(401,{"error":"unauthenticated"}); return
            query=parse_qs(parsed.query)
            cursor=query.get("cursor",[None])[0]
            try:
                limit=int(query.get("limit",[50])[0])
                result=store.inbox(steward_principal,cursor=cursor,limit=limit)
                for delivery in result["deliveries"]:
                    _add_local_timestamps(delivery,config["presentation_timezone"])
                    _add_presentation(delivery,config)
                result["presentation_timezone"]=config["presentation_timezone"]
                self._send(200,result)
                self._log("notification.inbox.read",principal=steward_principal,delivery_count=len(result["deliveries"]))
            except Exception as exc:
                self._error(exc)

        def do_POST(self) -> None:
            parsed=urlparse(self.path)
            try:
                body=self._body()
                if parsed.path == "/internal/v1/notifications":
                    if not self._bearer(source_token):
                        self._log("notification.source.unauthorized")
                        self._send(401,{"error":"unauthenticated"}); return
                    if set(body)!={"notification","directory_snapshot"} or not isinstance(body["directory_snapshot"],dict):
                        raise ValueError("source intake requires notification and the authoritative directory snapshot")
                    notification=validate_notification_envelope(body["notification"])
                    if notification.get("source_id") not in config["source_ids"]:
                        raise ValueError("notification source is not allowlisted")
                    rules=[r for r in config["subscriptions"] if r["event_type"]==notification.get("event_type")]
                    matches=[r for r in rules if _matches_filter(notification,r.get("filter",{}))]
                    if len(matches)!=1:
                        self._log("notification.intake.filtered",source_event_id=notification["source_event_id"],
                                  source_event_type=notification["event_type"])
                        self._send(202,{"contract":"r3a.notification-source-result.v1","outcome":"ignored",
                                        "reason":"unsubscribed_or_ambiguous_event","deliveries":[]}); return
                    rule=matches[0]
                    routing_policy={"contract_id":"r3a.notification-delivery","contract_version":"1.0.0",
                        "rules":[{"source_id":notification["source_id"],"event_type":notification["event_type"],
                        "recipient":rule["recipient"],"urgency":rule["urgency"],
                        "requires_action":rule["requires_action"]}]}
                    routed=route_notification(notification,body["directory_snapshot"],routing_policy)
                    if not routed:
                        self._log("notification.intake.no_recipient",source_event_id=notification["source_event_id"])
                        self._send(202,{"contract":"r3a.notification-source-result.v1","outcome":"no_recipient",
                                        "source_event_id":notification["source_event_id"],"deliveries":[]}); return
                    recipients=[{"kind":item["recipient"]["kind"],"recipient_id":item["recipient"]["recipient_id"]}
                                for item in routed]
                    digest=body["directory_snapshot"]["source"]["snapshot_sha256"]
                    result=store.ingest(notification,recipients,
                                        directory_snapshot_sha256=digest,
                                        subscription={"subscriptions":config["subscriptions"]},
                                        phone_enabled=phone_publisher is not None)
                    delivery_error = False
                    for delivery in result:
                        if phone_publisher is not None and delivery["phone_delivery"]["state"] != "sent":
                            claimed = store.begin_phone_attempt(delivery["delivery_id"])
                            if claimed is None:
                                delivery_error = True
                            else:
                                try:
                                    ntfy_id = phone_publisher.publish(claimed,
                                        presentation_timezone=config["presentation_timezone"])
                                    delivery.update(store.mark_phone_sent(delivery["delivery_id"],ntfy_id))
                                except Exception as exc:
                                    delivery.update(store.mark_phone_failed(delivery["delivery_id"],type(exc).__name__))
                                    delivery_error = True
                                    self._log("notification.phone.failed",delivery_id=delivery["delivery_id"],
                                              error_type=type(exc).__name__)
                        _add_presentation(delivery,config)
                    response={"contract":"r3a.notification-source-result.v1","outcome":"persisted",
                              "deliveries":result}
                    self._send(503 if delivery_error else 202,response)
                    self._log("notification.intake.persisted",source_event_id=notification["source_event_id"],
                              source_event_type=notification["event_type"],delivery_ids=[item["delivery_id"] for item in result],
                              duplicate_count=sum(bool(item.get("duplicate")) for item in result),
                              phone_delivery_states=[item["phone_delivery"]["state"] for item in result])
                    return
                match=re.fullmatch(r"/api/v1/notifications/([0-9a-fA-F-]{36})/(acknowledgment|resolution)",parsed.path)
                if not match:
                    self._send(404,{"error":"not_found"}); return
                if not self._bearer(steward_token):
                    self._log("notification.recipient.unauthorized",delivery_id=delivery_id)
                    self._send(401,{"error":"unauthenticated"}); return
                delivery_id,action=match.groups()
                authorization_ref={"provider_id":"r3a.notifications.configured-gateway",
                                   "decision_id":str(uuid.uuid4()),"allowed":True,
                                   "actor_id":steward_principal}
                if action=="acknowledgment":
                    if set(body)-{"idempotency_key","note"} or "idempotency_key" not in body:
                        raise ValueError("acknowledgment requires idempotency_key and optional note")
                    result=store.acknowledge(delivery_id,steward_principal,body["idempotency_key"],
                                             authorization_ref,body.get("note"))
                else:
                    if set(body)!={"idempotency_key","disposition","evidence_refs"}:
                        raise ValueError("resolution requires idempotency_key, disposition, and evidence_refs")
                    result=store.resolve(delivery_id,steward_principal,body["idempotency_key"],
                                         body["disposition"],body["evidence_refs"],authorization_ref)
                result["contract"]="r3a.notification-inbox.v1"
                result["presentation_timezone"]=config["presentation_timezone"]
                _add_local_timestamps(result,config["presentation_timezone"])
                _add_presentation(result,config)
                self._send(200,result)
                self._log(f"notification.{action}.completed",delivery_id=delivery_id,
                          principal=steward_principal,decision_id=authorization_ref["decision_id"],
                          outcome=result["status"],duplicate=result.get("duplicate",False))
            except Exception as exc:
                self._error(exc)

    class ManagedHttpServer(ThreadingHTTPServer):
        def __init__(self,*args,notification_store:NotificationStore,**kwargs):
            self.notification_store=notification_store
            self._closed=False
            super().__init__(*args,**kwargs)

        def server_close(self):
            super().server_close()
            if not self._closed:
                self._closed=True
                self.notification_store.set_lifecycle("INACTIVE")

    server=ManagedHttpServer((host,port),Handler,notification_store=store)
    server.daemon_threads=True
    return server


def _matches_filter(notification: dict[str, Any], event_filter: dict[str, Any]) -> bool:
    evidence=notification.get("evidence",{})
    if notification.get("event_type","").startswith("foundation.observe"):
        return False
    if evidence.get("activity_type")=="foundation.observe":
        return False
    if event_filter.get("activity_type") is not None and evidence.get("activity_type")!=event_filter["activity_type"]:
        return False
    return all(evidence.get(key)==value for key,value in event_filter.get("evidence_equals",{}).items())


def _add_local_timestamps(value: dict[str, Any], timezone_name: str) -> None:
    for key in ("created_at","acknowledged_at","resolved_at"):
        if value.get(key) is not None:
            value[f"{key}_local"]=format_timestamp(value[key],timezone_name)


def _website_base_url(config: dict[str, Any]) -> str | None:
    env_name = config.get("website_base_url_env")
    return os.environ.get(env_name, "") or None if env_name else None


def _add_presentation(value: dict[str, Any], config: dict[str, Any]) -> None:
    value["message"] = render_notification_presentation(value,
        website_base_url=_website_base_url(config),
        presentation_timezone=config["presentation_timezone"])


def _configured_ntfy_publisher(config: dict[str, Any]) -> NtfyPublisher | None:
    ntfy = config.get("ntfy", {"enabled": False})
    if not ntfy.get("enabled"):
        return None
    names = {key: os.environ.get(ntfy[field], "") for key, field in (
        ("topic", "topic_env"), ("token_file", "token_file_env"))}
    names["website_base_url"] = _website_base_url(config)
    if any(not value for value in names.values()):
        raise ConfigurationError("enabled ntfy delivery requires topic, token file, and Website URL configuration")
    try:
        token = Path(names["token_file"]).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as exc:
        raise ConfigurationError(f"ntfy credential file unavailable: {type(exc).__name__}") from None
    try:
        return NtfyPublisher(ntfy["base_url"],topic=names["topic"],token=token,
            website_base_url=names["website_base_url"],timeout=float(ntfy["timeout_seconds"]))
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"ntfy configuration invalid: {type(exc).__name__}") from None


def main() -> None:
    import argparse
    parser=argparse.ArgumentParser(description="Run the R3A notification inbox service")
    parser.add_argument("--config",required=True)
    parser.add_argument("--host",default="127.0.0.1")
    parser.add_argument("--port",type=int,default=18480)
    args=parser.parse_args()
    config=load_config(args.config)
    server=create_server(config,host=args.host,port=args.port)
    print(json.dumps({"module_id":MODULE_ID,"module_version":MODULE_VERSION,"state":"ACTIVE",
                      "host":args.host,"port":server.server_address[1]}),flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown();server.server_close()


if __name__=="__main__":
    main()
