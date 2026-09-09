import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/install-codex-agent-foundry"
SCRIPT = SKILL / "scripts/install.py"
VERIFY = SKILL / "scripts/verify.py"

spec = importlib.util.spec_from_file_location("foundry_install", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class InstallerPlanTests(unittest.TestCase):
    def test_check_plan_includes_state_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plan = mod.build_install_plan(root)
            paths = {s.path.relative_to(root).as_posix() for s in plan.steps}
            self.assertIn(".codex/.agent-foundry.json", paths)

    def test_force_plan_includes_backup_path(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            agents = root / ".codex/agents"
            agents.mkdir(parents=True)
            (agents / "reviewer.toml").write_text('name = "reviewer"\n# foreign\n')
            plan = mod.build_install_plan(root, force=True)
            backups = [s for s in plan.steps if s.action == "backup"]
            self.assertEqual(len(backups), 1)
            self.assertIn("reviewer.toml.foundry-backup", backups[0].path.name)

    def test_conflict_plan_is_complete_and_zero_write(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            agents = root / ".codex/agents"
            agents.mkdir(parents=True)
            foreign = agents / "reviewer.toml"
            foreign.write_text('name = "reviewer"\n# foreign\n')
            before = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
            plan = mod.build_install_plan(root)
            self.assertTrue(plan.blocked)
            paths = {s.path.relative_to(root).as_posix() for s in plan.steps}
            self.assertIn("AGENTS.md", paths)
            self.assertIn(".codex/config.toml", paths)
            self.assertIn(".codex/.agent-foundry.json", paths)
            after = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
            self.assertEqual(before, after)

    def test_invalid_existing_concurrency_is_preflight_error(self):
        cases = ["0", '"four"', "true"]
        for raw in cases:
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                (root / ".codex").mkdir()
                cfg = root / ".codex/config.toml"
                cfg.write_text(f"[agents]\nmax_concurrent_threads_per_session = {raw}\n")
                with self.assertRaises(mod.InstallError):
                    mod.build_install_plan(root)
                self.assertFalse((root / "AGENTS.md").exists())

    def test_reversed_markers_are_clean_install_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "AGENTS.md").write_text(f"{mod.END}\ntext\n{mod.START}\n")
            with self.assertRaisesRegex(mod.InstallError, "reversed"):
                mod.build_install_plan(root)

    def test_model_override_is_recorded_and_persists(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plan = mod.build_install_plan(root, reviewer_model="gpt-custom")
            mod.apply_plan(plan)
            reviewer = (root / ".codex/agents/reviewer.toml").read_text()
            self.assertIn('model = "gpt-custom"', reviewer)
            state = json.loads((root / ".codex/.agent-foundry.json").read_text())
            self.assertEqual(state["models"]["reviewer"], "gpt-custom")
            plan2 = mod.build_install_plan(root)
            self.assertFalse(any(s.action in {"create", "update"} and s.path.name == "reviewer.toml" for s in plan2.steps))

    def test_apply_rolls_back_on_failure(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "AGENTS.md").write_text("# Existing\n")
            original = (root / "AGENTS.md").read_bytes()
            plan = mod.build_install_plan(root)
            real_write = mod.atomic_write
            calls = {"n": 0}

            def flaky(path, content, mode=None):
                calls["n"] += 1
                if calls["n"] == 3:
                    raise OSError("synthetic failure")
                return real_write(path, content, mode)

            with mock.patch.object(mod, "atomic_write", side_effect=flaky):
                with self.assertRaises(mod.InstallError):
                    mod.apply_plan(plan)
            self.assertEqual((root / "AGENTS.md").read_bytes(), original)
            self.assertFalse((root / ".codex/config.toml").exists())
            self.assertFalse((root / ".codex/.agent-foundry.json").exists())
            self.assertFalse((root / ".codex").exists())

    def test_tampered_state_is_rejected_before_uninstall(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mod.apply_plan(mod.build_install_plan(root))
            state_path = root / ".codex/.agent-foundry.json"
            state = json.loads(state_path.read_text())
            state["managed_agents"] = ["../../outside.toml"]
            state_path.write_text(json.dumps(state))
            with self.assertRaises(mod.InstallError):
                mod.build_uninstall_plan(root)
            self.assertTrue((root / ".codex/agents/reviewer.toml").exists())

    def test_unsupported_state_version_is_rejected_before_update(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mod.apply_plan(mod.build_install_plan(root))
            state_path = root / ".codex/.agent-foundry.json"
            state = json.loads(state_path.read_text())
            state["version"] = 999
            state_path.write_text(json.dumps(state))
            with self.assertRaisesRegex(mod.InstallError, "unsupported Foundry state version"):
                mod.build_install_plan(root)

    def test_symlink_target_is_rejected_without_touching_referent(self):
        if os.name == "nt":
            self.skipTest("symlink semantics")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            outside = root / "outside.md"
            outside.write_text("outside\n")
            (root / "AGENTS.md").symlink_to(outside)
            with self.assertRaisesRegex(mod.InstallError, "symlink"):
                mod.build_install_plan(root)
            self.assertEqual(outside.read_text(), "outside\n")

    def test_symlink_managed_directory_is_rejected(self):
        if os.name == "nt":
            self.skipTest("symlink semantics")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            outside = root / "outside-dir"
            outside.mkdir()
            (root / ".codex").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(mod.InstallError, "symlink"):
                mod.build_install_plan(root)
            self.assertEqual(list(outside.iterdir()), [])

    def test_uninstall_refuses_drifted_managed_profile(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mod.apply_plan(mod.build_install_plan(root))
            reviewer = root / ".codex/agents/reviewer.toml"
            reviewer.write_text(reviewer.read_text() + "\n# user modification\n")
            plan = mod.build_uninstall_plan(root)
            self.assertTrue(plan.blocked)
            self.assertTrue(any(s.action == "conflict" and s.path == reviewer for s in plan.steps))
            with self.assertRaises(mod.InstallError):
                mod.apply_plan(plan)
            self.assertIn("# user modification", reviewer.read_text())

    def test_existing_file_mode_is_preserved(self):
        if os.name == "nt":
            self.skipTest("POSIX mode semantics")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            agents = root / "AGENTS.md"
            agents.write_text("# Existing\n")
            agents.chmod(0o640)
            mod.apply_plan(mod.build_install_plan(root))
            self.assertEqual(stat.S_IMODE(agents.stat().st_mode), 0o640)

    def test_uninstall_removes_only_foundry_owned_runtime(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "AGENTS.md").write_text("# Existing\n")
            mod.apply_plan(mod.build_install_plan(root))
            plan = mod.build_uninstall_plan(root)
            mod.apply_plan(plan)
            self.assertEqual((root / "AGENTS.md").read_text(), "# Existing\n")
            self.assertFalse((root / ".codex/.agent-foundry.json").exists())
            self.assertFalse((root / ".codex/agents/reviewer.toml").exists())
            self.assertFalse((root / ".codex/agents/explorer.toml").exists())
            self.assertFalse((root / ".codex/agents/verifier.toml").exists())
            cfg = root / ".codex/config.toml"
            self.assertFalse(cfg.exists())

    def test_uninstall_preserves_user_concurrency(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".codex").mkdir()
            cfg = root / ".codex/config.toml"
            cfg.write_text("[agents]\nmax_concurrent_threads_per_session = 7\n")
            mod.apply_plan(mod.build_install_plan(root))
            mod.apply_plan(mod.build_uninstall_plan(root))
            self.assertIn("max_concurrent_threads_per_session = 7", cfg.read_text())


class VerifyTests(unittest.TestCase):
    def run_verify(self, root: Path):
        return subprocess.run([sys.executable, str(VERIFY), str(root)], text=True, capture_output=True)

    def test_verify_accepts_model_override(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mod.apply_plan(mod.build_install_plan(root, explorer_model="gpt-explorer-x"))
            result = self.run_verify(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_verify_rejects_symlinked_managed_directory(self):
        if os.name == "nt":
            self.skipTest("symlink semantics")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mod.apply_plan(mod.build_install_plan(root))
            real_codex = root / ".codex-real"
            (root / ".codex").rename(real_codex)
            (root / ".codex").symlink_to(real_codex, target_is_directory=True)
            result = self.run_verify(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("symlink", result.stdout)

    def test_verify_detects_profile_drift(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mod.apply_plan(mod.build_install_plan(root))
            reviewer = root / ".codex/agents/reviewer.toml"
            reviewer.write_text(reviewer.read_text() + "\n# drift\n")
            result = self.run_verify(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("drifted", result.stdout)


if __name__ == "__main__":
    unittest.main()
