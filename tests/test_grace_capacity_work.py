# R3 CONTROLLED SOURCE
# File: tests/test_grace_capacity_work.py
# Purpose: Permanent durable capacity-work and independent review gate contracts.
import tempfile
import unittest
from pathlib import Path
from runtime.grace_capacity_work import CapacityWork

def gpu(free=200,fresh=True):
    return {"kind":"nvidia-gpu","resource_id":"gpu:test","host":"local",
            "source":"r3:local-nvidia-smi","state":"online","fresh":fresh,
            "capacity":{"vram_free_bytes":free}}

class CapacityWorkTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"capacity.db"
        self.work=CapacityWork(self.path)
        self.addCleanup(self.work.db.close)

    def test_enqueued_work_is_durable_and_idempotent(self):
        self.assertTrue(self.work.enqueue("work:1",100))
        self.assertFalse(self.work.enqueue("work:1",100))
        with self.assertRaises(ValueError):
            self.work.enqueue("work:1",200)
        reopened=CapacityWork(self.path)
        self.addCleanup(reopened.db.close)
        self.assertEqual(reopened.status("work:1")["state"],"PENDING")

    def test_observed_fit_waits_for_independent_review(self):
        self.work.enqueue("work:1",100)
        result=self.work.assess_next(lambda:[gpu()])
        self.assertEqual(result["state"],"AWAITING_INDEPENDENT_REVIEW")
        self.assertFalse(result["assessment"]["execution_authorized"])
        self.assertEqual(self.work.status("work:1")["state"],"AWAITING_INDEPENDENT_REVIEW")
        self.assertIsNone(self.work.assess_next(lambda:[gpu()]))
        with self.assertRaises(ValueError):
            self.work.accept_review("work:1","",verify_review=lambda w,r: {"accepted":True,"independent":True,"review_ref":r})
        with self.assertRaises(ValueError):
            self.work.accept_review("work:1","review:1",verify_review=lambda w,r: {"accepted":True,"independent":False,"review_ref":r})
        self.work.accept_review("work:1","review:1",verify_review=lambda w,r: {"accepted":True,"independent":True,"review_ref":r})
        self.assertEqual(self.work.status("work:1")["state"],"VERIFIED")

    def test_stale_and_insufficient_capacity_blocks_without_completion(self):
        self.work.enqueue("work:1",100)
        result=self.work.assess_next(lambda:[gpu(free=20)])
        self.assertEqual(result["state"],"BLOCKED")
        with self.assertRaises(ValueError):
            self.work.accept_review("work:1","review:1",independent=True)
        result=self.work.assess_next(lambda:[gpu(fresh=False)])
        self.assertEqual(result["state"],"BLOCKED")
        self.assertIsNone(self.work.status("work:1")["review_ref"])

    def test_failed_observation_can_recover_on_next_event(self):
        self.work.enqueue("work:1",100)
        def unavailable():
            raise OSError("GPU probe unavailable")
        self.assertEqual(self.work.assess_next(unavailable)["state"],"BLOCKED")
        result=self.work.assess_next(lambda:[gpu()])
        self.assertEqual(result["state"],"AWAITING_INDEPENDENT_REVIEW")
        self.assertIsNone(self.work.status("work:1")["review_ref"])

    def test_empty_queue_does_not_generate_work(self):
        self.assertIsNone(self.work.assess_next(lambda:[gpu()]))
