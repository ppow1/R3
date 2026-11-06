# R3 CONTROLLED SOURCE
# File: tests/test_resident_personnel.py
# Component: R3-RESIDENT-PERSONNEL-REGRESSION
# File Revision: 1.0.0
# Created: Unknown (legacy)
# Created By: Unknown (legacy)
# Purpose: Permanent resident-neutral personnel metadata and authority-separation contract.
# Execution Model: unittest.
# Observability: Assertions.
# Dependencies: runtime.resident_personnel.
# Authority: HR association is identity metadata; the local projection cannot issue authority.
# Changed: 2026-11-06T23:06:45Z | GRACE-AUTHORITY-ARCH-001 | Codex GPT-6 | Verify personnel projections are resident-neutral and cannot define policy.
# Supersedes: Prior Grace-only reader tests; no runtime permissions granted.
# Contracts: docs/architecture/RESIDENT_AUTHORITY_AND_CAPABILITIES.md
# Tests: This module.
# History/Predecessor: Git history at current branch baseline.
import json
import tempfile
import unittest
from pathlib import Path
from runtime.resident_personnel import read_personnel_record

ROOT = Path(__file__).resolve().parents[1]
class PersonnelTests(unittest.TestCase):
    def test_grace_identity_projection_has_no_embedded_policy(self):
        record = read_personnel_record(ROOT / "residents/grace/personnel.json")
        self.assertEqual(record["authority_principal"], "resident:grace")
        self.assertNotIn("grants", record)
        self.assertNotIn("permissions", record)

    def test_reader_accepts_other_valid_resident_identity_without_aliasing(self):
        record = json.loads((ROOT / "residents/grace/personnel.json").read_text())
        record.update(resident_id="chloe", authority_principal="resident:Chloe")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "record.json"
            path.write_text(json.dumps(record), encoding="utf-8")
            self.assertEqual(read_personnel_record(path)["authority_principal"], "resident:Chloe")

    def test_personnel_projection_cannot_define_policy(self):
        record = read_personnel_record(ROOT / "residents/grace/personnel.json")
        for key, value in (("grants", [{"action": "*"}]),
                           ("permissions", ["proposal.draft.submit"]),
                           ("capabilities", ["r3.proposal.submit"]),
                           ("restrictions", [])):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                candidate = dict(record, **{key: value})
                path = Path(directory) / "record.json"
                path.write_text(json.dumps(candidate), encoding="utf-8")
                with self.assertRaises(ValueError):
                    read_personnel_record(path)
