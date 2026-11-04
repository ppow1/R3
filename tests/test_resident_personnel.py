# R3 CONTROLLED SOURCE
# File: tests/test_resident_personnel.py
# Purpose: Permanent institution-wide resident personnel/authority separation contract.
import json
import tempfile
import unittest
from pathlib import Path
from runtime.resident_personnel import read_personnel_record

ROOT = Path(__file__).resolve().parents[1]
class PersonnelTests(unittest.TestCase):
    def test_grace_identity_has_no_embedded_grants(self):
        record = read_personnel_record(ROOT / "residents/grace/personnel.json")
        self.assertEqual(record["authority_principal"], "resident:grace")
        self.assertNotIn("grants", record)
        self.assertNotIn("permissions", record)

    def test_same_schema_accepts_other_residents_without_authority(self):
        record = read_personnel_record(ROOT / "residents/grace/personnel.json")
        record["resident_id"] = "vicky"
        record["display_name"] = "Vicky"
        record["authority_principal"] = "resident:vicky"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "record.json"
            path.write_text(json.dumps(record), encoding="utf-8")
            loaded = read_personnel_record(path)
            self.assertEqual(loaded["authority_principal"], "resident:vicky")
            self.assertNotIn("grants", loaded)

    def test_personnel_rejects_mismatched_identity(self):
        record = read_personnel_record(ROOT / "residents/grace/personnel.json")
        record["resident_id"] = "vicky"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "record.json"
            path.write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaises(ValueError):
                read_personnel_record(path)

    def test_personnel_cannot_issue_grants(self):
        record = read_personnel_record(ROOT / "residents/grace/personnel.json")
        record["grants"] = [{"action": "*"}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "record.json"
            path.write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaises(ValueError):
                read_personnel_record(path)
