"""Notification module integration tests; set R3A_NOTIFICATION_TEST_DSN to an isolated PostgreSQL DB."""
from __future__ import annotations

from datetime import datetime, timezone
from http.client import HTTPConnection
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
import uuid

from psycopg.rows import dict_row

from r3a_plugins.notification_service.server import create_server, load_config
from r3a_plugins.notification_service.store import NotificationStore
from r3a_runtime.timestamp_presentation import format_timestamp


ROOT=Path(__file__).resolve().parents[1]
EVENT_ID="af6eb52f-d1f2-4dd1-8d5a-608478977f56"
CORRELATION="da02adce-1f9d-4ba9-9859-f42ffab649a2"
PRINCIPAL="steward.isolated-test"


def test_directory_snapshot(principal=PRINCIPAL, freshness="fresh"):
    snapshot={"schema_id":"r3a.institutional-directory.v1","schema_version":1,
        "observed_at":"2026-11-08T16:00:00Z",
        "source":{"source_id":"isolated-test-directory","source_contract":"test.directory.v1",
                  "freshness":freshness,"availability":"measured","snapshot_sha256":"0"*64},
        "offices":[{"office_id":"office.isolated-test","office_role":"Steward","status":"active"}],
        "residents":[{"resident_id":principal,"office_id":"office.isolated-test",
                       "office_role":"Steward","office_status":"active"}]}
    digest=hashlib.sha256(json.dumps(snapshot,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    snapshot["source"]["snapshot_sha256"]=digest
    return snapshot


def notification(event_type="process.failed", *, evidence=None):
    return {"contract_id":"r3a.notification-intake","contract_version":"1.0.0",
            "source_id":"r3a.institution-events","source_event_id":EVENT_ID,
            "event_type":event_type,"event_id":EVENT_ID,"correlation_id":CORRELATION,
            "occurred_at":"2026-11-08T16:00:00Z","received_at":"2026-11-08T16:00:01Z",
            "severity":"error","payload_ref":f"r3a.institution_events/{EVENT_ID}",
            "provenance":{"store":"r3a.institution_events","schema_version":1,
                          "actor":"pid:isolated","source_config_revision":"test",
                          "implementation_revision":"isolated-event"},
            "evidence":{"subject_type":"process","subject_id":"notification-demo",
                        "prior_state":"RUNNING","next_state":"FAILED","reason":"isolated source event",
                        "outcome":"failed","persisted_at":"2026-11-08T16:00:01Z",
                        "source_evidence":{},**(evidence or {})}}


class NotificationServiceHttpIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dsn=os.environ.get("R3A_NOTIFICATION_TEST_DSN")
        if not dsn:
            raise unittest.SkipTest("R3A_NOTIFICATION_TEST_DSN must point to an isolated PostgreSQL database")
        cls.config_path=Path("/tmp/r3a-notification-service-test-config.json")
        config=json.loads((ROOT/"r3a_plugins/notification_service/config.example.json").read_text())
        cls.config_path.write_text(json.dumps(config))
        os.environ.update({"R3A_NOTIFICATION_MODULE_DSN":dsn,
                           "R3A_NOTIFICATION_SOURCE_TOKEN":"isolated-source-token",
                           "R3A_NOTIFICATION_STEWARD_TOKEN":"isolated-steward-token",
                           "R3A_NOTIFICATION_STEWARD_PRINCIPAL":PRINCIPAL,
                           "R3A_NOTIFICATION_WEBSITE_BASE_URL":"https://steward.test"})
        cls.config=load_config(cls.config_path)
        cls.store=NotificationStore(dsn)
        cls.store.initialize("1.0.0")

    def setUp(self):
        with self.store.connect(self.store.dsn) as conn,conn.transaction():
            conn.execute("TRUNCATE r3a_notification.delivery_events,r3a_notification.deliveries")
        self.server=create_server(self.config,host="127.0.0.1",port=0,store=self.store)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.port=self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)

    def request(self,method,path,*,token=None,body=None):
        conn=HTTPConnection("127.0.0.1",self.port,timeout=3)
        headers={"Content-Type":"application/json"}
        if token: headers["Authorization"]=f"Bearer {token}"
        payload=json.dumps(body).encode() if body is not None else None
        conn.request(method,path,payload,headers)
        response=conn.getresponse();raw=response.read();conn.close()
        return response.status,json.loads(raw) if raw else {}

    def intake(self,event=None):
        return self.request("POST","/internal/v1/notifications",token="isolated-source-token",
                            body={"notification":event or notification(),
                                  "directory_snapshot":test_directory_snapshot()})

    def test_http_durable_delivery_ack_restart_and_duplicate_suppression(self):
        status,created=self.intake()
        self.assertEqual(status,202)
        delivery=created["deliveries"][0]
        delivery_id=delivery["delivery_id"]
        self.assertEqual("queued",delivery["status"])
        self.assertEqual(test_directory_snapshot()["source"]["snapshot_sha256"],
                         delivery["directory_snapshot_sha256"])
        self.assertEqual("America/New_York",format_timestamp(delivery["created_at"],"America/New_York").split("[")[1].split("]")[0])

        status,duplicate=self.intake()
        self.assertEqual(status,202)
        self.assertTrue(duplicate["deliveries"][0]["duplicate"])
        self.assertEqual(delivery_id,duplicate["deliveries"][0]["delivery_id"])
        refreshed_directory=test_directory_snapshot()
        refreshed_directory["observed_at"]="2026-11-08T16:05:00Z"
        refreshed_directory["source"]["snapshot_sha256"]="0"*64
        refreshed_directory["source"]["snapshot_sha256"]=hashlib.sha256(
            json.dumps(refreshed_directory,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        status,refreshed_replay=self.request("POST","/internal/v1/notifications",
            token="isolated-source-token",body={"notification":notification(),
                "directory_snapshot":refreshed_directory})
        self.assertEqual(status,202)
        self.assertTrue(refreshed_replay["deliveries"][0]["duplicate"])
        self.assertEqual(delivery_id,refreshed_replay["deliveries"][0]["delivery_id"])
        changed=notification(evidence={"reason":"different event content"})
        status,conflict=self.intake(changed)
        self.assertEqual(status,409)
        self.assertEqual("NotificationConflict",conflict["error"])
        status,unauthorized=self.request("GET","/api/v1/notifications")
        self.assertEqual(status,401)
        status,inbox=self.request("GET","/api/v1/notifications",token="isolated-steward-token")
        self.assertEqual(status,200)
        self.assertEqual(1,len(inbox["deliveries"]))
        self.assertEqual(delivery_id,inbox["deliveries"][0]["delivery_id"])
        self.assertIn("EST",inbox["deliveries"][0]["created_at_local"])
        self.assertIn("isolated source event",inbox["deliveries"][0]["message"]["reason"])
        self.assertEqual("https://steward.test/?view=notifications&notification_id="+delivery_id,
                         inbox["deliveries"][0]["message"]["detail_url"])
        self.assertEqual("disabled",inbox["deliveries"][0]["phone_delivery"]["state"])
        inbox_schema=json.loads((ROOT/"r3a_plugins/notification_service/notification-inbox.v1.schema.json").read_text())
        from r3a_runtime.capability_contracts import validate_json
        validate_json(inbox,inbox_schema)

        ack_path=f"/api/v1/notifications/{delivery_id}/acknowledgment"
        ack_body={"idempotency_key":"ack:isolated-001","note":"Reviewed in isolated test"}
        status,ack=self.request("POST",ack_path,token="isolated-steward-token",body=ack_body)
        self.assertEqual(status,200)
        self.assertEqual("acknowledged",ack["status"])
        self.assertEqual(PRINCIPAL,ack["acknowledged_by"])
        self.assertTrue(ack["acknowledgment_authorization"]["allowed"])
        status,ack_replay=self.request("POST",ack_path,token="isolated-steward-token",body=ack_body)
        self.assertEqual(status,200)
        self.assertTrue(ack_replay["duplicate"])

        # Stop/start the actual HTTP service while retaining the PostgreSQL cluster.
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
        self.server=create_server(self.config,host="127.0.0.1",port=0,store=self.store)
        self.port=self.server.server_address[1]
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        status,recovered=self.request("GET","/api/v1/notifications",token="isolated-steward-token")
        self.assertEqual(status,200)
        self.assertEqual("acknowledged",recovered["deliveries"][0]["status"])
        status,retry=self.intake()
        self.assertEqual(status,202)
        self.assertEqual(delivery_id,retry["deliveries"][0]["delivery_id"])
        self.assertEqual("acknowledged",retry["deliveries"][0]["status"])
        status,resolved=self.request("POST",f"/api/v1/notifications/{delivery_id}/resolution",
            token="isolated-steward-token",body={"idempotency_key":"resolve:isolated-001",
            "disposition":"reviewed","evidence_refs":["r3a.institution_events/"+EVENT_ID]})
        self.assertEqual(status,200)
        self.assertEqual("resolved",resolved["status"])

    def test_durable_phone_outbox_retries_failure_once_and_suppresses_successful_replay(self):
        event=notification()
        args={"subscription":{"subscriptions":self.config["subscriptions"]},
              "directory_snapshot_sha256":test_directory_snapshot()["source"]["snapshot_sha256"],
              "phone_enabled":True}
        created=self.store.ingest(event,[{"kind":"steward","recipient_id":PRINCIPAL}],**args)[0]
        self.assertEqual("pending",created["phone_delivery"]["state"])
        first=self.store.begin_phone_attempt(created["delivery_id"])
        self.assertEqual(1,first["phone_delivery"]["attempts"])
        failed=self.store.mark_phone_failed(created["delivery_id"],"NtfyPublishError")
        self.assertEqual("failed",failed["phone_delivery"]["state"])
        replay=self.store.ingest(event,[{"kind":"steward","recipient_id":PRINCIPAL}],**args)[0]
        self.assertTrue(replay["duplicate"])
        second=self.store.begin_phone_attempt(created["delivery_id"])
        self.assertEqual(2,second["phone_delivery"]["attempts"])
        sent=self.store.mark_phone_sent(created["delivery_id"],"ntfy-message-test-002")
        self.assertEqual("sent",sent["phone_delivery"]["state"])
        self.assertEqual("ntfy-message-test-002",sent["phone_delivery"]["message_id"])
        self.assertIsNone(self.store.begin_phone_attempt(created["delivery_id"]))
        with self.store.connect(self.store.dsn,row_factory=dict_row) as conn:
            events=conn.execute("SELECT event_type FROM r3a_notification.delivery_events "
                "WHERE delivery_id=%s ORDER BY occurred_at",(created["delivery_id"],)).fetchall()
        self.assertEqual(["notification.delivery.queued","notification.delivery.phone_failed",
                          "notification.delivery.phone_sent"],[row["event_type"] for row in events])

    def test_http_phone_failure_is_truthful_and_source_retry_reuses_delivery(self):
        class RetryPublisher:
            def __init__(self): self.calls=0
            def publish(self,delivery,*,presentation_timezone):
                self.calls+=1
                if self.calls==1: raise RuntimeError("private transport unavailable")
                return "ntfy-isolated-retry-001"
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
        publisher=RetryPublisher()
        self.server=create_server(self.config,host="127.0.0.1",port=0,store=self.store,
                                  phone_publisher=publisher)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.port=self.server.server_address[1]
        status,failed=self.intake()
        self.assertEqual(503,status)
        original=failed["deliveries"][0]
        self.assertEqual("failed",original["phone_delivery"]["state"])
        self.assertEqual("queued",original["status"])
        status,retried=self.intake()
        self.assertEqual(202,status)
        duplicate=retried["deliveries"][0]
        self.assertEqual(original["delivery_id"],duplicate["delivery_id"])
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual("sent",duplicate["phone_delivery"]["state"])
        self.assertEqual(2,duplicate["phone_delivery"]["attempts"])
        self.assertEqual(2,publisher.calls)
        with self.store.connect(self.store.dsn) as conn:
            module=conn.execute("SELECT module_version,lifecycle_state,schema_version FROM r3a_notification.module_state WHERE singleton=true").fetchone()
        self.assertEqual(("1.2.0","ACTIVE",3),tuple(module))

    def test_observer_suppression_and_subscription_filtering(self):
        observe=notification("activity.completed",evidence={"activity_type":"foundation.observe"})
        status,result=self.intake(observe)
        self.assertEqual(status,202)
        self.assertEqual("ignored",result["outcome"])
        self.assertEqual([],result["deliveries"])

    def test_stale_directory_and_wrong_recipient_fail_closed(self):
        stale=test_directory_snapshot(freshness="stale")
        status,_=self.request("POST","/internal/v1/notifications",token="isolated-source-token",
            body={"notification":notification(),"directory_snapshot":stale})
        self.assertEqual(status,400)
        foreign=test_directory_snapshot(principal="resident.other")
        status,created=self.request("POST","/internal/v1/notifications",token="isolated-source-token",
            body={"notification":notification(),"directory_snapshot":foreign})
        self.assertEqual(status,202)
        delivery_id=created["deliveries"][0]["delivery_id"]
        _,inbox=self.request("GET","/api/v1/notifications",token="isolated-steward-token")
        self.assertEqual([],inbox["deliveries"])
        status,denied=self.request("POST",f"/api/v1/notifications/{delivery_id}/acknowledgment",
            token="isolated-steward-token",body={"idempotency_key":"wrong-recipient-ack"})
        self.assertEqual(status,403)
        self.assertEqual("NotificationForbidden",denied["error"])


class NotificationServicePresentationTests(unittest.TestCase):
    def test_shared_timezone_helper_preserves_utc_and_displays_dst_zone(self):
        winter=format_timestamp("2026-01-15T12:00:00Z","America/New_York")
        summer=format_timestamp("2026-07-15T12:00:00Z","America/New_York")
        self.assertIn("EST [America/New_York]",winter)
        self.assertIn("EDT [America/New_York]",summer)
        self.assertIn("UTC 2026-01-15T12:00:00Z",winter)
        self.assertIn("UTC 2026-07-15T12:00:00Z",summer)

    def test_dst_boundaries_fold_and_invalid_zone(self):
        spring_before=format_timestamp("2026-03-08T06:59:00Z","America/New_York")
        spring_after=format_timestamp("2026-03-08T07:01:00Z","America/New_York")
        fall_first=format_timestamp("2026-11-01T05:30:00Z","America/New_York")
        fall_second=format_timestamp("2026-11-01T06:30:00Z","America/New_York")
        self.assertIn("EST [America/New_York]",spring_before)
        self.assertIn("EDT [America/New_York]",spring_after)
        self.assertIn("EDT [America/New_York]",fall_first)
        self.assertIn("EST [America/New_York]",fall_second)
        with self.assertRaises(ValueError):
            format_timestamp("2026-11-08T16:00:00Z","Invalid/Zone")

    def test_versioned_service_manifest_pins_runtime_artifacts_and_categories(self):
        manifest=json.loads((ROOT/"r3a_plugins/notification_service/manifest.json").read_text())
        self.assertEqual("r3a.notifications",manifest["module_id"])
        self.assertEqual("1.2.2",manifest["module_version"])
        references={item["artifact_ref"] for item in manifest["supporting_artifacts"]}
        self.assertTrue({"../notification_source/manifest.json","../notification_source/plugin.py",
            "../../r3a_runtime/schemas/activity-intake.v1.schema.json"} <= references)
        for item in [{"artifact_ref":manifest["artifact_ref"],"artifact_sha256":manifest["artifact_sha256"]},
                     *manifest["supporting_artifacts"]]:
            artifact=(ROOT/"r3a_plugins/notification_service"/item["artifact_ref"]).resolve()
            canonical=artifact.read_bytes().replace(b"\r\n",b"\n")
            self.assertEqual(item["artifact_sha256"],hashlib.sha256(canonical).hexdigest())
        config=load_config(ROOT/"r3a_plugins/notification_service/config.example.json")
        categories={item["category"] for item in config["subscriptions"]}
        self.assertTrue({"resident_objective_completed","resident_objective_blocked",
            "independent_verification_failed","steward_approval_required",
            "service_or_capability_unavailable","resident_delegation_completed"} <= categories)
        historical=json.loads((ROOT/"r3a_plugins/notification_service/manifest.v1.2.0.json").read_text())
        self.assertEqual("1.2.0",historical["module_version"])
    def test_service_manifest_pins_survive_autocrlf_true_and_false_checkouts(self):
        manifest_path=ROOT/"r3a_plugins/notification_service/manifest.json"
        manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
        artifacts=[{"artifact_ref":manifest["artifact_ref"],
                    "artifact_sha256":manifest["artifact_sha256"]},*manifest["supporting_artifacts"]]
        with tempfile.TemporaryDirectory() as temporary:
            temp_root=Path(temporary)
            seed=temp_root/"seed"
            seed.mkdir()
            paths={manifest_path.relative_to(ROOT)}
            for item in artifacts:
                artifact=(manifest_path.parent/item["artifact_ref"]).resolve()
                paths.add(artifact.relative_to(ROOT))
            for relative in paths:
                source=ROOT/relative
                target=seed/relative
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(source.read_bytes().replace(b"\r\n",b"\n"))
            shutil.copy2(ROOT/".gitattributes",seed/".gitattributes")

            def git(*args,cwd):
                subprocess.run(["git",*args],cwd=cwd,check=True,capture_output=True,text=True)

            git("init","--quiet",cwd=seed)
            git("config","user.name","Notification Manifest Test",cwd=seed)
            git("config","user.email","notification-manifest-test@example.invalid",cwd=seed)
            git("add","--all",cwd=seed)
            git("commit","--quiet","-m","fixture",cwd=seed)
            for checkout_name,autocrlf in (("windows","true"),("linux","false")):
                checkout=temp_root/checkout_name
                subprocess.run(["git","clone","--quiet","-c",f"core.autocrlf={autocrlf}",
                                str(seed),str(checkout)],check=True,capture_output=True,text=True)
                clone_manifest_path=checkout/manifest_path.relative_to(ROOT)
                clone_manifest=json.loads(clone_manifest_path.read_text(encoding="utf-8"))
                for item in [{"artifact_ref":clone_manifest["artifact_ref"],
                              "artifact_sha256":clone_manifest["artifact_sha256"]},
                             *clone_manifest["supporting_artifacts"]]:
                    artifact=(clone_manifest_path.parent/item["artifact_ref"]).resolve()
                    self.assertEqual(item["artifact_sha256"],
                                     hashlib.sha256(artifact.read_bytes()).hexdigest(),
                                     f"{checkout_name}:{item['artifact_ref']}")


if __name__=="__main__": unittest.main()
