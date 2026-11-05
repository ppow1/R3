import os
import tempfile
import unittest
from pathlib import Path

from runtime.resident_credentials import load_resident_credential


class ResidentCredentialTests(unittest.TestCase):
    def test_unconfigured_is_read_only(self):
        self.assertIsNone(load_resident_credential(None, "Grace"))

    def test_missing_file_does_not_issue_credential(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(
                load_resident_credential(Path(directory), "Grace")
            )

    def test_private_credential_loads(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Grace.credential"
            path.write_text(("r3resident_v1." + "a" * 32 + "." + "b" * 43))
            os.chmod(path, 0o600)
            self.assertEqual(
                load_resident_credential(Path(directory), "Grace"),
                ("r3resident_v1." + "a" * 32 + "." + "b" * 43),
            )

    def test_world_readable_credential_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Grace.credential"
            path.write_text(("r3resident_v1." + "a" * 32 + "." + "b" * 43))
            os.chmod(path, 0o644)
            with self.assertRaises(PermissionError):
                load_resident_credential(Path(directory), "Grace")

    def test_symlink_credential_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.write_text(("r3resident_v1." + "a" * 32 + "." + "b" * 43))
            os.chmod(target, 0o600)
            (root / "Grace.credential").symlink_to(target)
            with self.assertRaises(PermissionError):
                load_resident_credential(root, "Grace")

    def test_malformed_credential_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Grace.credential"
            path.write_text("r3resident_v1.invalid")
            os.chmod(path, 0o600)
            with self.assertRaises(ValueError):
                load_resident_credential(Path(directory), "Grace")

    def test_path_traversal_denied(self):
        with self.assertRaises(ValueError):
            load_resident_credential(Path("/tmp"), "../Grace")


if __name__ == "__main__":
    unittest.main()
