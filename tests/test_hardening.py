import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/install-codex-agent-foundry"
SCRIPT = SKILL / "scripts/install.py"
VERIFY = SKILL / "scripts/verify.py"

spec = importlib.util.spec_from_file_location("foundry_install_hardening", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class InstallerHardeningTests(unittest.TestCase):
    def test_uninstall_restores_existing_config_without_agents_table(self):
        cases = ["", 'model = "example"\n', '[features]\nfoo = true\n']
        for original in cases:
            with self.subTest(original=original), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                (root / ".codex").mkdir()
                cfg = root / ".codex/config.toml"
                cfg.write_text(original)
                mod.apply_plan(mod.build_install_plan(root))
                mod.apply_plan(mod.build_uninstall_plan(root))
                self.assertTrue(cfg.exists())
                self.assertEqual(cfg.read_text(), original)

    def test_managed_file_path_that_is_directory_is_preflight_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "AGENTS.md").mkdir()
            with self.assertRaisesRegex(mod.InstallError, "regular file"):
                mod.build_install_plan(root)

    def test_managed_directory_path_that_is_file_is_preflight_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".codex").write_text("not a directory")
            with self.assertRaisesRegex(mod.InstallError, "expected a directory"):
                mod.build_install_plan(root)

    def test_force_backup_skips_broken_symlink_candidate(self):
        if os.name == "nt":
            self.skipTest("symlink semantics")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            agents = root / ".codex/agents"
            agents.mkdir(parents=True)
            foreign = agents / "reviewer.toml"
            foreign.write_text('name = "reviewer"\n# foreign\n')
            (agents / "reviewer.toml.foundry-backup").symlink_to(agents / "missing-target")
            plan = mod.build_install_plan(root, force=True)
            backups = [step for step in plan.steps if step.action == "backup"]
            self.assertEqual(len(backups), 1)
            self.assertTrue(backups[0].path.name.endswith("foundry-backup-2"))

    def test_verify_rejects_incomplete_core_state_schema(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mod.apply_plan(mod.build_install_plan(root))
            state_path = root / ".codex/.agent-foundry.json"
            state = json.loads(state_path.read_text())
            del state["models"]
            state_path.write_text(json.dumps(state))
            result = subprocess.run([sys.executable, str(VERIFY), str(root)], text=True, capture_output=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing required fields", result.stdout)

    def test_verify_rejects_partial_provenance(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mod.apply_plan(mod.build_install_plan(root))
            state_path = root / ".codex/.agent-foundry.json"
            state = json.loads(state_path.read_text())
            del state["runtime_sha256"]
            state_path.write_text(json.dumps(state))
            result = subprocess.run([sys.executable, str(VERIFY), str(root)], text=True, capture_output=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("provenance is incomplete", result.stdout)

    def test_verify_rejects_managed_file_path_that_is_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mod.apply_plan(mod.build_install_plan(root))
            agents_md = root / "AGENTS.md"
            agents_md.unlink()
            agents_md.mkdir()
            result = subprocess.run([sys.executable, str(VERIFY), str(root)], text=True, capture_output=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("AGENTS.md must be a regular file", result.stdout)

    def test_verify_reports_invalid_utf8_without_traceback(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mod.apply_plan(mod.build_install_plan(root))
            (root / "AGENTS.md").write_bytes(b"\xff\xfe")
            result = subprocess.run([sys.executable, str(VERIFY), str(root)], text=True, capture_output=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not valid UTF-8", result.stdout)
            self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
