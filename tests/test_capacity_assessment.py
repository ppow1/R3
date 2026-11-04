# R3 CONTROLLED SOURCE
# File: tests/test_capacity_assessment.py
# Purpose: Permanent conservative capacity assessment regression tests.
import unittest
from runtime.capacity_assessment import assess_gpu_capacity


def gpu(*, free=200, fresh=True, state="online", source="r3:local-nvidia-smi"):
    return {"resource_id": "gpu:example", "kind": "nvidia-gpu", "host": "local",
            "capacity": {"vram_free_bytes": free}, "fresh": fresh,
            "state": state, "source": source}


class CapacityAssessmentTests(unittest.TestCase):
    def test_sufficient_observed_vram_is_not_execution_authority(self):
        result = assess_gpu_capacity([gpu()], required_vram_bytes=100)
        self.assertEqual(len(result["candidates"]), 1)
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["model_fit_verified"])
        self.assertIsNone(result["candidates"][0]["authorized"])

    def test_stale_offline_and_untrusted_capacity_not_selected(self):
        for changed, reason in [
            ({"fresh": False}, "stale-or-unknown"),
            ({"state": "offline"}, "not-online"),
            ({"source": "manual-guess"}, "untrusted-source"),
            ({"free": 50}, "insufficient-free-vram"),
            ({"free": None}, "unknown-free-vram")]:
            with self.subTest(changed=changed):
                candidate = gpu(**changed)
                result = assess_gpu_capacity([candidate], required_vram_bytes=100)
                self.assertEqual(result["candidates"], [])
                self.assertEqual(result["evaluated"][0]["reason"], reason)

    def test_host_memory_not_mistaken_for_gpu_vram(self):
        result = assess_gpu_capacity([{"kind": "physical-host",
            "capacity": {"ram_total_bytes": 10**12}, "fresh": True}],
            required_vram_bytes=100)
        self.assertEqual(result["evaluated"], [])

    def test_invalid_requirement_denied(self):
        for value in (0, -1, True, 1.5, "100"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    assess_gpu_capacity([gpu()], required_vram_bytes=value)


if __name__ == "__main__":
    unittest.main()
