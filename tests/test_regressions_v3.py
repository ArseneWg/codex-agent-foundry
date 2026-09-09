import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/install-codex-agent-foundry"
INSTALL = SKILL / "scripts/install.py"

spec = importlib.util.spec_from_file_location("foundry_install_regressions", INSTALL)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class V3RegressionTests(unittest.TestCase):
    def test_toml_multiline_string_is_not_mistaken_for_agents_table(self):
        original = '''developer_instructions = """
[agents]
agents.max_concurrent_threads_per_session = 4
Keep this text unchanged.
"""
[features]
foo = true
'''
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".codex").mkdir()
            config = root / ".codex/config.toml"
            config.write_text(original)
            mod.apply_plan(mod.build_install_plan(root))
            parsed = tomllib.loads(config.read_text())
            self.assertEqual(parsed["developer_instructions"], "[agents]\nagents.max_concurrent_threads_per_session = 4\nKeep this text unchanged.\n")
            self.assertEqual(parsed["agents"]["max_concurrent_threads_per_session"], 4)
            mod.apply_plan(mod.build_uninstall_plan(root))
            self.assertEqual(config.read_text(), original)

    def test_current_profile_drift_blocks_update_and_force_backs_up(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mod.apply_plan(mod.build_install_plan(root))
            state = json.loads((root / ".codex/.agent-foundry.json").read_text())
            self.assertEqual(set(state["managed_sha256"]), set(mod.CURRENT_MANAGED_PATHS))
            reviewer = root / ".codex/agents/reviewer.toml"
            reviewer.write_text(reviewer.read_text() + "\n# user change\n")

            blocked = mod.build_install_plan(root)
            self.assertTrue(blocked.blocked)
            self.assertTrue(any(step.action == "conflict" and step.path == reviewer for step in blocked.steps))

            forced = mod.build_install_plan(root, force=True)
            self.assertFalse(forced.blocked)
            backups = [step for step in forced.steps if step.action == "backup" and "reviewer.toml" in step.path.name]
            self.assertEqual(len(backups), 1)
            mod.apply_plan(forced)
            backup = backups[0].path
            self.assertIn("# user change", backup.read_text())
            self.assertNotIn("# user change", reviewer.read_text())

    def test_verifier_runner_rejects_compound_shell_and_preserves_direct_status(self):
        if os.name == "nt":
            self.skipTest("POSIX shell rejection fixture")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mod.apply_plan(mod.build_install_plan(root))
            runner = root / mod.VERIFIER_RUNNER
            self.assertTrue(runner.exists())

            fail_log = root / "fail.log"
            failed = subprocess.run(
                [sys.executable, str(runner), "--log", str(fail_log), "--", sys.executable, "-c", "raise SystemExit(7)"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(failed.returncode, 7)
            self.assertEqual(fail_log.read_text().splitlines()[-1], "FOUNDRY_RESULT_V1 exit_code=7 status=FAIL")

            marker = root / "should-not-exist"
            compound_log = root / "compound.log"
            compound = subprocess.run(
                [sys.executable, str(runner), "--log", str(compound_log), "--", "bash", "-c", f"false && touch {marker}; printf done"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(compound.returncode, 64)
            self.assertFalse(marker.exists())
            self.assertIn("status=INDETERMINATE", compound_log.read_text().splitlines()[-1])
            self.assertIn("reason=shell_command_string_rejected", compound_log.read_text().splitlines()[-1])

    def test_verifier_runner_is_removed_only_when_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mod.apply_plan(mod.build_install_plan(root))
            runner = root / mod.VERIFIER_RUNNER
            runner.write_text(runner.read_text() + "\n# local edit\n")
            plan = mod.build_uninstall_plan(root)
            self.assertTrue(plan.blocked)
            self.assertTrue(any(step.action == "conflict" and step.path == runner for step in plan.steps))


if __name__ == "__main__":
    unittest.main()
