from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.deployment.r3_resource_policy import (
    IsolationError,
    R3_RELEASE_ROOT,
    R3A_PROTECTED_PATHS,
    validate_plan,
    validate_port,
    validate_process_action,
    validate_release_path,
    validate_unit,
    validate_unit_dropin,
)


class R3DeploymentIsolationTests(unittest.TestCase):
    def valid_plan(self, **overrides):
        args = {
            "action": "activate",
            "units": ("r3-institution.service", "r3-native-tools.service"),
            "ports": (("r3-institution.service", 8770),
                      ("r3-native-tools.service", 8765)),
            "release_paths": (R3_RELEASE_ROOT / ("grace-" + "0" * 40),),
            "dropins": (
                ("r3-institution.service",
                 "/home/admin1/.config/systemd/user/r3-institution.service.d/zz-grace-autonomy.conf"),
                ("r3-native-tools.service",
                 "/home/admin1/.config/systemd/user/r3-native-tools.service.d/zz-grace-autonomy.conf"),
            ),
        }
        args.update(overrides)
        return args

    def test_exact_r3_units_ports_release_and_dropins_are_accepted(self):
        plan = validate_plan(**self.valid_plan())
        self.assertTrue(plan["r3a_isolated"])
        self.assertEqual(plan["units"],
                         ("r3-institution.service", "r3-native-tools.service"))
        self.assertEqual(len(plan["release_paths"]), 1)

    def test_r3a_units_and_website_unit_are_rejected(self):
        for unit in ("r3a-ap0-m1-ring0.service",
                     "r3a-ap0-m1-postgres.service", "r3-website.service"):
            with self.subTest(unit=unit), self.assertRaises(IsolationError):
                validate_unit(unit)

    def test_protected_port_is_rejected_even_for_an_r3_unit(self):
        with self.assertRaises(IsolationError):
            validate_port("r3-native-tools.service", 55492)

    def test_plan_rejects_r3a_paths_database_targets_and_process_actions(self):
        cases = (
            {"runtime_paths": (R3A_PROTECTED_PATHS[1] / "run",)},
            {"database_targets": (("r3a_ap0_m1", "r3a_runtime"),)},
            {"process_actions": ("pkill -f uvicorn",)},
            {"ports": (("r3-institution.service", 8770),
                       ("r3-native-tools.service", 55492))},
        )
        for change in cases:
            with self.subTest(change=change), self.assertRaises(IsolationError):
                validate_plan(**self.valid_plan(**change))

    def test_release_symlink_cannot_escape_to_r3a(self):
        with tempfile.TemporaryDirectory(prefix="r3-release-guard-") as tmp:
            link = Path(tmp) / "candidate"
            link.symlink_to(R3A_PROTECTED_PATHS[0], target_is_directory=True)
            with self.assertRaises(IsolationError):
                validate_release_path(link)

    def test_unit_dropin_must_be_inside_exact_r3_unit_directory(self):
        accepted = validate_unit_dropin(
            "r3-institution.service",
            "/home/admin1/.config/systemd/user/r3-institution.service.d/zz-grace.conf")
        self.assertTrue(str(accepted).endswith("r3-institution.service.d/zz-grace.conf"))
        with self.assertRaises(IsolationError):
            validate_unit_dropin(
                "r3-institution.service",
                "/home/admin1/.config/systemd/user/r3a-ap0-m1-ring0.service.d/override.conf")

    def test_direct_process_control_is_never_an_activation_mechanism(self):
        for action in ("kill 1234", "pkill -f r3", "systemctl --user stop '*'"):
            with self.subTest(action=action), self.assertRaises(IsolationError):
                validate_process_action(action)

    def test_cleanup_is_disabled_for_immutable_release_retention(self):
        plan = self.valid_plan(action="cleanup")
        with self.assertRaises(IsolationError):
            validate_plan(**plan)


if __name__ == "__main__":
    unittest.main()
