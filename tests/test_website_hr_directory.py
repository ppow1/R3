# R3 CONTROLLED SOURCE
# File: tests/test_website_hr_directory.py
# Component: WEBSITE-HR-DIRECTORY-REGRESSIONS
# File Revision: 1.1.0
# Created: 2026-11-05 UTC
# Created By: ChatGPT GPT-6
# Purpose: Permanent regression coverage for authorized HR discovery and Chat routing.
# Execution Model: unittest with isolated HR/runtime fixtures and HTTP adapter stubs.
# Observability: Assertions only; no credentials or protected field values logged.
# Dependencies: FastAPI; website Chat API; HR capability contract.
# Authority: Steward multi-resident Chat directive; permanent product contracts.
# Changed: 2026-11-05 UTC | WEBSITE-MULTIRESIDENT-CHAT | ChatGPT GPT-6 | Cover authorization, dynamic metadata, canonical identity mapping, and runtime routing.
# Supersedes: 1.0.0 directory-only regression suite; predecessor working-tree file.
# Contracts: runtime/hr_capability.py; runtime/conversations.py; tests/test_conversation_runtime_integration.py
# Tests: /home/admin1/R3/.venv/bin/python -m unittest tests.test_website_hr_directory
# History/Predecessor: Prior file added in Website Development worktree.
"""Permanent contract tests for dynamic HR-backed website Chat."""
import json
import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

import r3_chat_api as chat
import r3_resident_directory as directory


class FakeStore:
    def __init__(self, records):
        self.records = records
        self.closed = False

    def close(self):
        self.closed = True

    def get(self, resident_id):
        return self.records.get(resident_id)


class RequestStub:
    def __init__(self, headers=None, cookies=None, body=b""):
        self.headers = Headers({key.lower(): value for key, value in (headers or {}).items()})
        self.cookies = cookies or {}
        self._body = body

    async def body(self):
        return self._body


class Headers(dict):
    def get(self, key, default=None):
        return super().get(key.lower(), default)


class FakeCapability:
    def __init__(self, store):
        self.store = store

    def directory(self, principal):
        if principal.role != "steward":
            raise PermissionError("hr.read denied")
        result = []
        for record, revision in self.store.records.values():
            fields = {key: value for key, value in record.fields.items()}
            result.append({
                "resident_id": record.resident_id,
                "display_name": record.display_name,
                "office": record.office,
                "status": record.status,
                "fields": fields,
                "revision": revision,
            })
        return result

    def resolve_authority_principal(self, principal, resident_id):
        if principal.role != "steward":
            raise PermissionError("hr.read denied")
        stored = self.store.get(resident_id)
        if stored is None:
            raise ValueError("HR resident not found")
        link = stored[0].extensions.get("authority_principal")
        if link is None:
            raise ValueError("authority principal association missing")
        return link.value


def record(identifier, name, status="onboarding", fields=None, office="Office",
           authority_principal=None):
    return (SimpleNamespace(
        resident_id=identifier,
        display_name=name,
        office=office,
        status=status,
        fields=fields or {},
        extensions=({"authority_principal": SimpleNamespace(
            value=authority_principal, classification="confidential",
        )} if authority_principal else {}),
    ), 1)


class WebsiteHRDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.records = {
            "r3:grace": record("r3:grace", "Grace", fields={
                "role": "Director of Operations",
            }, authority_principal="resident:grace"),
            "r3:chloe": record("r3:chloe", "Chloe", authority_principal="resident:Chloe"),
            "r3:evelyn": record("r3:evelyn", "Evelyn", fields={"personnel_classification": "protected"}),
            "r3:gm": record("r3:gm", "Gray Man", fields={"personnel_classification": "protected"}),
            # Field presence by itself does not mean an identity is protected.
            "r3:other": record("r3:other", "Other", fields={"personnel_classification": "confidential"}),
        }
        for index in range(1, 9):
            resident_id = f"r3:resident-{index:02d}"
            self.records[resident_id] = record(resident_id, f"Resident {index:02d}")
        self.store = FakeStore(self.records)
        self.capability = FakeCapability(self.store)
        self.steward = directory.AuthorizedStewardSession("steward@example.test")
        self.directory_patch = patch.object(
            directory, "_directory",
            return_value=(self.capability, self.store, lambda principal_id, role: SimpleNamespace(
                principal_id=principal_id, role=role)),
        )
        self.directory_patch.start()
        self.addCleanup(self.directory_patch.stop)
        self.runtime_config = self.root / "runtime.json"
        self.runtime_config.write_text(json.dumps({"residents": {
            "grace": "residents/grace.json", "Chloe": "residents/chloe.json",
        }}))
        self.runtime_patch = patch.object(directory, "RUNTIME_CONFIG", self.runtime_config)
        self.runtime_patch.start()
        self.addCleanup(self.runtime_patch.stop)
        self.runtime_identity_map = self.root / "runtime-identities.json"
        self.runtime_identity_map.write_text(json.dumps({
            "authority_principals": {
                "resident:grace": "grace",
                "resident:Chloe": "Chloe",
            },
        }))
        self.identity_map_patch = patch.object(
            directory, "RUNTIME_IDENTITY_MAP", self.runtime_identity_map,
        )
        self.identity_map_patch.start()
        self.addCleanup(self.identity_map_patch.stop)
        self.cfg = {
            "conversation_api_base_url": "http://127.0.0.1:8770",
            "conversation_api_credential_file": str(self.root / "token"),
            "resident_id": "Grace",
            "required_role": "steward",
            "request_timeout_seconds": 5,
            "allowed_origins": ["https://r3.example.test"],
        }
        Path(self.cfg["conversation_api_credential_file"]).write_text("server-token")
        self.auth_store = SimpleNamespace(authenticate=self._authenticate)
        self.routes = {
            (route.path, method): route.endpoint
            for route in chat.build_chat_router().routes
            for method in getattr(route, "methods", ())
        }

    def tearDown(self):
        self.temp.cleanup()

    def _authenticate(self, token, csrf=None, mutation=False):
        if token != "session" or (mutation and csrf != "csrf"):
            raise chat.AuthenticationDenied("unauthorized")
        return {"email": "steward@example.test", "role": "steward"}

    def authenticated(self, *, mutation=False):
        headers = {"Origin": "https://r3.example.test"}
        if mutation:
            headers["X-Riverview-CSRF"] = "csrf"
        return RequestStub(headers, {"r3_steward_session": "session"})

    def test_dynamic_hr_discovery_includes_resident_fourteen_and_updates(self):
        self.records["r3:new"] = record("r3:new", "New Resident", fields={"role": "Research"})
        rows = directory.load_residents(self.steward)
        self.assertEqual(len(rows), 14)
        self.assertIn("r3:new", {row["id"] for row in rows})
        self.records["r3:new"] = record("r3:new", "Updated Name", office="Updated Office")
        updated = next(row for row in directory.load_residents(self.steward) if row["id"] == "r3:new")
        self.assertEqual(updated["name"], "Updated Name")
        self.assertEqual(updated["department"], "Updated Office")
        self.assertEqual(updated["availability"], "unavailable")

    def test_deactivated_residents_are_removed(self):
        self.records["r3:grace"] = record("r3:grace", "Grace", status="deactivated")
        self.assertNotIn("r3:grace", {row["id"] for row in directory.load_residents(self.steward)})

    def test_authoritative_protected_classification_and_field_classification(self):
        rows = {row["id"]: row for row in directory.load_residents(self.steward)}
        self.assertTrue(rows["r3:evelyn"]["protected"])
        self.assertTrue(rows["r3:gm"]["protected"])
        self.assertFalse(rows["r3:other"]["protected"])

    def test_directory_requires_authenticated_steward_server_side(self):
        with patch.object(chat, "load_config", return_value=self.cfg), \
             patch.object(chat, "native_store", return_value=self.auth_store):
            endpoint = self.routes[("/api/v1/chat/residents", "GET")]
            with self.assertRaises(HTTPException) as unauthorized:
                endpoint(RequestStub())
            response = endpoint(self.authenticated())
        self.assertEqual(unauthorized.exception.status_code, 401)
        self.assertEqual(response.status_code, 200)
        ids = {row["id"] for row in json.loads(response.body)["residents"]}
        self.assertTrue({"r3:evelyn", "r3:gm"}.issubset(ids))
        self.assertNotIn("authority_principal", response.body.decode())

    def test_non_steward_session_cannot_read_directory(self):
        non_steward_store = SimpleNamespace(authenticate=lambda *args, **kwargs: {
            "email": "resident@example.test", "role": "resident",
        })
        with patch.object(chat, "load_config", return_value=self.cfg), \
             patch.object(chat, "native_store", return_value=non_steward_store):
            with self.assertRaises(HTTPException) as response:
                self.routes[("/api/v1/chat/residents", "GET")](self.authenticated())
        self.assertEqual(response.exception.status_code, 403)

    def test_missing_principal_denied_by_directory_projection(self):
        with self.assertRaises(HTTPException) as context:
            directory.load_residents(directory.AuthorizedStewardSession(""))
        self.assertEqual(context.exception.status_code, 401)

    def test_runtime_identity_must_match_actual_runtime_registry(self):
        self.assertEqual(directory.runtime_resident_id(
            "r3:grace", legacy_runtime_id="Grace"), "grace")
        with self.assertRaises(HTTPException) as context:
            directory.runtime_resident_id("r3:new", "resident:independent-reviewer")
        self.assertEqual(context.exception.status_code, 404)

    def test_confidential_hr_principal_association_maps_to_runtime_registry(self):
        self.runtime_config.write_text(json.dumps({
            "residents": {"independent-reviewer": "residents/reviewer.json"},
        }))
        self.runtime_identity_map.write_text(json.dumps({
            "authority_principals": {"resident:Independent Reviewer": "independent-reviewer"},
        }))
        self.assertEqual(directory.runtime_resident_id(
            "r3:new-resident", "resident:Independent Reviewer"
        ), "independent-reviewer")

    def test_non_grace_directory_route_uses_confidential_association(self):
        self.runtime_config.write_text(json.dumps({
            "residents": {"independent-reviewer": "residents/reviewer.json"},
        }))
        self.runtime_identity_map.write_text(json.dumps({
            "authority_principals": {"resident:Independent Reviewer": "independent-reviewer"},
        }))
        self.records["r3:new-resident"] = record(
            "r3:new-resident", "New Resident",
            authority_principal="resident:Independent Reviewer",
        )
        rows = {row["id"]: row for row in directory.load_residents(
            self.steward, legacy_runtime_id="Grace",
        )}
        self.assertEqual(rows["r3:new-resident"]["_runtime_id"], "independent-reviewer")
        self.assertNotIn("authority_principal", rows["r3:new-resident"])

    def test_grace_legacy_endpoint_preserves_runtime_routing_and_history(self):
        class Reply:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, _limit): return b'{"conversations":[{"conversation_id":"old"}]}'
        seen = {}
        def open_request(req, timeout):
            seen["url"] = req.full_url
            seen["principal"] = req.get_header("X-r3-principal")
            return Reply()
        with patch.object(chat, "load_config", return_value=self.cfg), \
             patch.object(chat, "native_store", return_value=self.auth_store), \
             patch.object(chat.urllib.request, "urlopen", side_effect=open_request):
            response = self.routes[("/api/v1/chat/conversations", "GET")](self.authenticated())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(seen["url"].endswith("/v1/residents/grace/conversations"))
        self.assertEqual(seen["principal"], "steward@example.test")
        self.assertEqual(json.loads(response.body)["conversations"][0]["conversation_id"], "old")

    def test_canonical_resident_creation_targets_confirmed_runtime_and_requires_csrf(self):
        class Reply:
            status = 201
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, _limit): return b'{"conversation":{"conversation_id":"new","resident":"grace"}}'
        seen = {}
        def open_request(req, timeout):
            seen["url"] = req.full_url
            seen["body"] = req.data
            return Reply()
        with patch.object(chat, "load_config", return_value=self.cfg), \
             patch.object(chat, "native_store", return_value=self.auth_store), \
             patch.object(chat.urllib.request, "urlopen", side_effect=open_request):
            endpoint = self.routes[("/api/v1/chat/residents/{resident_id}/conversations", "POST")]
            with self.assertRaises(HTTPException) as no_csrf:
                asyncio.run(endpoint("r3:grace", RequestStub(
                    {"Origin": "https://r3.example.test"},
                    {"r3_steward_session": "session"}, b'{"title":"New"}',
                )))
            request = self.authenticated(mutation=True)
            response = asyncio.run(endpoint("r3:grace", RequestStub(
                request.headers, request.cookies, b'{"title":"New"}',
            )))
        self.assertEqual(no_csrf.exception.status_code, 401)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(seen["url"].endswith("/v1/residents/grace/conversations"))
        self.assertEqual(json.loads(seen["body"]), {"title": "New"})

    def test_runtime_identity_mismatch_rejected_before_conversation_access(self):
        with patch.object(chat, "load_config", return_value=self.cfg), \
             patch.object(chat, "native_store", return_value=self.auth_store):
            with self.assertRaises(HTTPException) as response:
                self.routes[("/api/v1/chat/residents/{resident_id}/conversations", "GET")]("r3:other", self.authenticated())
        self.assertEqual(response.exception.status_code, 404)

    def test_selected_resident_message_route_checks_runtime_ownership(self):
        self.runtime_config.write_text(json.dumps({
            "residents": {"independent-reviewer": "residents/reviewer.json"},
        }))
        self.runtime_identity_map.write_text(json.dumps({
            "authority_principals": {"resident:Independent Reviewer": "independent-reviewer"},
        }))
        self.records["r3:new-resident"] = record(
            "r3:new-resident", "New Resident",
            authority_principal="resident:Independent Reviewer",
        )
        conversation_id = "3b08cc55-75f8-4cc8-a84c-8841796e1fd6"

        class Reply:
            status = 200
            def __init__(self, payload): self.payload = payload
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, _limit): return self.payload

        seen = []
        def open_request(req, timeout):
            seen.append(req.full_url)
            if req.full_url.endswith("/v1/residents/independent-reviewer/conversations"):
                return Reply(json.dumps({"conversations": [
                    {"conversation_id": conversation_id},
                ]}).encode())
            return Reply(b'{"messages":[]}')

        with patch.object(chat, "load_config", return_value=self.cfg), \
             patch.object(chat, "native_store", return_value=self.auth_store), \
             patch.object(chat.urllib.request, "urlopen", side_effect=open_request):
            response = self.routes[(
                "/api/v1/chat/residents/{resident_id}/conversations/{conversation_id}/messages", "GET",
            )]("r3:new-resident", conversation_id, self.authenticated())
        self.assertEqual(response.status_code, 200)
        self.assertIn("/v1/residents/independent-reviewer/conversations", seen[0])
        self.assertIn(f"/v1/conversations/{conversation_id}/messages", seen[1])

    def test_selected_resident_is_enforced_for_conversation_retrieval(self):
        conversation_id = "00000000-0000-4000-8000-000000000001"
        class Reply:
            status = 200
            def __init__(self, payload): self.payload = payload
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, _limit): return self.payload
        seen = []
        def open_request(req, timeout):
            seen.append(req.full_url)
            if req.full_url.endswith("/v1/residents/Chloe/conversations"):
                return Reply(b'{"conversations":[]}')
            raise AssertionError("message retrieval must be rejected before proxying")
        with patch.object(chat, "load_config", return_value=self.cfg), \
             patch.object(chat, "native_store", return_value=self.auth_store), \
             patch.object(chat.urllib.request, "urlopen", side_effect=open_request):
            with self.assertRaises(HTTPException) as response:
                self.routes[("/api/v1/chat/residents/{resident_id}/conversations/{conversation_id}/messages", "GET")](
                    "r3:chloe", conversation_id, self.authenticated(), 0, 200,
                )
        self.assertEqual(response.exception.status_code, 404)
        self.assertEqual(len(seen), 1)
        self.assertIn("/v1/residents/Chloe/conversations", seen[0])

    def test_selected_resident_is_enforced_before_message_sending(self):
        conversation_id = "00000000-0000-4000-8000-000000000002"
        class Reply:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, _limit): return b'{"conversations":[]}'
        seen = []
        def open_request(req, timeout):
            seen.append((req.full_url, req.get_method()))
            return Reply()
        with patch.object(chat, "load_config", return_value=self.cfg), \
             patch.object(chat, "native_store", return_value=self.auth_store), \
             patch.object(chat.urllib.request, "urlopen", side_effect=open_request):
            with self.assertRaises(HTTPException) as response:
                asyncio.run(self.routes[("/api/v1/chat/residents/{resident_id}/conversations/{conversation_id}/messages", "POST")](
                    "r3:chloe", conversation_id,
                    RequestStub({
                        "Origin": "https://r3.example.test",
                        "X-Riverview-CSRF": "csrf",
                    }, {"r3_steward_session": "session"},
                       b'{"content":"Hi","client_message_id":"stable"}'),
                ))
        self.assertEqual(response.exception.status_code, 404)
        self.assertEqual(seen, [("http://127.0.0.1:8770/v1/residents/Chloe/conversations", "GET")])

    def test_non_grace_creation_uses_confidential_principal_link(self):
        self.runtime_config.write_text(json.dumps({
            "residents": {"independent-reviewer": "residents/reviewer.json"},
        }))
        self.runtime_identity_map.write_text(json.dumps({
            "authority_principals": {"resident:Independent Reviewer": "independent-reviewer"},
        }))
        self.records["r3:new-resident"] = record(
            "r3:new-resident", "New Resident",
            authority_principal="resident:Independent Reviewer",
        )
        class Reply:
            status = 201
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, _limit): return b'{"conversation":{"conversation_id":"new"}}'
        seen = {}
        def open_request(req, timeout):
            seen["url"] = req.full_url
            return Reply()
        with patch.object(chat, "load_config", return_value=self.cfg), \
             patch.object(chat, "native_store", return_value=self.auth_store), \
             patch.object(chat.urllib.request, "urlopen", side_effect=open_request):
            response = asyncio.run(self.routes[("/api/v1/chat/residents/{resident_id}/conversations", "POST")](
                "r3:new-resident", RequestStub({
                    "Origin": "https://r3.example.test", "X-Riverview-CSRF": "csrf",
                }, {"r3_steward_session": "session"}, b'{"title":"New"}'),
            ))
        self.assertEqual(response.status_code, 201)
        self.assertTrue(seen["url"].endswith("/v1/residents/independent-reviewer/conversations"))


if __name__ == "__main__":
    unittest.main()
