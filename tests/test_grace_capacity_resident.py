"""Permanent R3 Institution-to-Grace capacity-work integration regressions."""
import asyncio
import tempfile
import unittest
from pathlib import Path
from runtime.institution import Institution, Journal
from runtime.grace_capacity_work import CapacityWork
from runtime.grace_capacity_resident import make_capacity_resident

def gpu():
    return {"kind":"nvidia-gpu","resource_id":"gpu:local","host":"local",
            "source":"r3:local-nvidia-smi","state":"online","fresh":True,
            "capacity":{"vram_free_bytes":200}}

class CapacityResidentTests(unittest.IsolatedAsyncioTestCase):
    async def test_institution_runs_pending_work_and_stops_when_awaiting_review(self):
        with tempfile.TemporaryDirectory() as folder:
            queue=CapacityWork(Path(folder)/"work.db")
            journal=Journal(Path(folder)/"institution.db")
            queue.enqueue("work:1",100)
            institution=Institution(journal,tick_seconds=0.005)
            institution.add(make_capacity_resident(queue,lambda:[gpu()],interval=0.01))
            runner=asyncio.create_task(institution.run())
            try:
                for _ in range(100):
                    if queue.status("work:1")["state"]=="AWAITING_INDEPENDENT_REVIEW":
                        break
                    await asyncio.sleep(0.01)
                self.assertEqual(queue.status("work:1")["state"],"AWAITING_INDEPENDENT_REVIEW")
                self.assertFalse(queue.has_assessable_work())
                self.assertIsNone(queue.status("work:1")["review_ref"])
                self.assertEqual(journal.db.execute(
                    "SELECT COUNT(*) FROM events WHERE kind='STARTED'").fetchone()[0],1)
            finally:
                await institution.stop()
                await asyncio.wait_for(runner,timeout=2)
                queue.db.close()
                journal.db.close()

    async def test_failed_observation_remains_blocked_for_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            queue=CapacityWork(Path(folder)/"work.db")
            journal=Journal(Path(folder)/"institution.db")
            queue.enqueue("work:2",100)
            institution=Institution(journal,tick_seconds=0.005)
            institution.add(make_capacity_resident(queue,lambda: (_ for _ in ()).throw(OSError("offline")),interval=0.05))
            runner=asyncio.create_task(institution.run())
            try:
                for _ in range(100):
                    if journal.db.execute("SELECT COUNT(*) FROM events WHERE kind='FAILED'").fetchone()[0]:
                        break
                    await asyncio.sleep(0.01)
                self.assertEqual(queue.status("work:2")["state"],"BLOCKED")
                self.assertTrue(queue.has_assessable_work())
                self.assertEqual(journal.db.execute(
                    "SELECT COUNT(*) FROM events WHERE kind='COMPLETED'").fetchone()[0],0)
            finally:
                await institution.stop()
                await asyncio.wait_for(runner,timeout=2)
                queue.db.close()
                journal.db.close()
