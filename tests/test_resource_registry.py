# R3 CONTROLLED SOURCE
# File: tests/test_resource_registry.py
# Purpose: Permanent resource freshness and provenance contracts.
import unittest
from datetime import datetime, timezone, timedelta
from runtime.resource_registry import Resource, ResourceRegistry
# Permanent capacity-assessment contract tests are collected by the existing
# Grace-native resource registry CI module until the workflow list is expanded.
from tests.test_capacity_assessment import CapacityAssessmentTests

class ResourceRegistryTests(unittest.TestCase):
    def test_stale_resource_never_claimed_usable(self):
        now = datetime.now(timezone.utc)
        r = Resource("host:a", "compute", "a", ("inference",), {"vram_gib": 16},
                     (now-timedelta(minutes=10)).isoformat(), "online", "probe:a")
        item = ResourceRegistry((lambda: (r,),)).snapshot(now=now)[0]
        self.assertFalse(item["fresh"])
        self.assertFalse(item["usable"])
        self.assertIsNone(item["authorized"])
        self.assertIsNone(item["verified_working"])

    def test_online_fresh_resource_not_implicitly_authorized(self):
        now = datetime.now(timezone.utc)
        r = Resource("host:b", "compute", "b", ("inference",), {},
                     now.isoformat(), "online", "probe:b")
        item = ResourceRegistry((lambda: (r,),)).snapshot(now=now)[0]
        self.assertTrue(item["usable"])
        self.assertIsNone(item["authorized"])

    def test_duplicate_identity_rejected(self):
        now = datetime.now(timezone.utc)
        r = Resource("same", "compute", "a", (), {}, now.isoformat(), "online", "probe")
        with self.assertRaises(ValueError):
            ResourceRegistry((lambda: (r,), lambda: (r,))).snapshot(now=now)

    def test_unprovenanced_observation_rejected(self):
        with self.assertRaises(ValueError):
            Resource("x", "compute", "a", (), {}, datetime.now(timezone.utc).isoformat(), "online", "")
