import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / ".agents/skills/install-codex-agent-foundry/scripts/install.py"
VERIFY = ROOT / ".agents/skills/install-codex-agent-foundry/scripts/verify.py"

spec = importlib.util.spec_from_file_location("foundry_install_migration", INSTALL)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def seed_v1(root: Path, *, explorer_model: str = "gpt-5.6-terra", drift: bool = False) -> None:
    agents = root / ".codex/agents"
    agents.mkdir(parents=True)
    legacy = mod.set_profile_model(mod.legacy_explorer_profile(), explorer_model)
    if drift:
        legacy += "\n# user drift\n"
    (agents / "repo_explorer.toml").write_text(legacy)
    (agents / "reviewer.toml").write_text(mod.legacy_profile("reviewer.toml"))
    (root / ".codex/config.toml").write_text("[agents]\nmax_concurrent_threads_per_session = 4\n")
    (root / "AGENTS.md").write_text(f"{mod.START}\nlegacy policy\n{mod.END}\n")
    state = {
        "version": 1,
        "managed_agents": ["repo_explorer.toml", "reviewer.toml"],
        "agents_md_markers": [mod.START, mod.END],
        "concurrency_added": True,
        "config_created": True,
        "models": {"repo_explorer": explorer_model, "reviewer": "gpt-5.6"},
    }
    (root / ".codex/.agent-foundry.json").write_text(json.dumps(state))


class ExplorerMigrationTests(unittest.TestCase):
    def test_v1_install_migrates_to_native_explorer_and_preserves_model(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            seed_v1(root, explorer_model="gpt-custom-explorer")
            plan = mod.build_install_plan(root)
            self.assertFalse(plan.blocked)
            self.assertTrue(any(s.action == "delete" and s.path.name == "repo_explorer.toml" for s in plan.steps))
            mod.apply_plan(plan)
            self.assertFalse((root / ".codex/agents/repo_explorer.toml").exists())
            explorer = (root / ".codex/agents/explorer.toml").read_text()
            self.assertIn('name = "explorer"', explorer)
            self.assertIn('model = "gpt-custom-explorer"', explorer)
            state = json.loads((root / ".codex/.agent-foundry.json").read_text())
            self.assertEqual(state["version"], 2)
            self.assertEqual(state["models"]["explorer"], "gpt-custom-explorer")

    def test_migration_allows_explicit_model_change_without_marking_legacy_drift(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            seed_v1(root, explorer_model="gpt-old")
            plan = mod.build_install_plan(root, explorer_model="gpt-new")
            self.assertFalse(plan.blocked)
            mod.apply_plan(plan)
            self.assertIn('model = "gpt-new"', (root / ".codex/agents/explorer.toml").read_text())

    def test_drifted_legacy_profile_blocks_migration_and_writes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            seed_v1(root, drift=True)
            before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            plan = mod.build_install_plan(root)
            self.assertTrue(plan.blocked)
            with self.assertRaises(mod.InstallError):
                mod.apply_plan(plan)
            after = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            self.assertEqual(before, after)

    def test_foreign_explorer_blocks_legacy_migration_without_force(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            seed_v1(root)
            (root / ".codex/agents/explorer.toml").write_text('name = "explorer"\n# foreign\n')
            plan = mod.build_install_plan(root)
            self.assertTrue(plan.blocked)
            self.assertTrue((root / ".codex/agents/repo_explorer.toml").exists())

    def test_force_backs_up_foreign_explorer_then_migrates(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            seed_v1(root)
            foreign = root / ".codex/agents/explorer.toml"
            foreign.write_text('name = "explorer"\n# foreign\n')
            plan = mod.build_install_plan(root, force=True)
            self.assertFalse(plan.blocked)
            self.assertTrue(any(s.action == "backup" and "explorer.toml.foundry-backup" in s.path.name for s in plan.steps))
            mod.apply_plan(plan)
            self.assertFalse((root / ".codex/agents/repo_explorer.toml").exists())
            self.assertTrue((root / ".codex/agents/explorer.toml.foundry-backup").exists())

    def test_orphan_legacy_profile_is_not_automatically_claimed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            agents = root / ".codex/agents"
            agents.mkdir(parents=True)
            (agents / "repo_explorer.toml").write_text(mod.legacy_explorer_profile())
            plan = mod.build_install_plan(root)
            self.assertTrue(plan.blocked)
            self.assertTrue(
                any(
                    step.action == "conflict"
                    and step.path.name == "repo_explorer.toml"
                    and "without matching legacy Foundry state" in step.detail
                    for step in plan.steps
                )
            )

    def test_verifier_directs_v1_install_to_migrate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            seed_v1(root)
            result = subprocess.run(
                [sys.executable, str(VERIFY), str(root)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("legacy Foundry v1 explorer role detected", result.stdout)
            self.assertIn("rerun the current installer", result.stdout)

    def test_v2_ignores_foreign_legacy_role_name(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mod.apply_plan(mod.build_install_plan(root))
            (root / ".codex/agents/repo_explorer.toml").write_text('name = "repo_explorer"\n# foreign\n')
            plan = mod.build_install_plan(root)
            self.assertFalse(plan.blocked)
            result = subprocess.run([sys.executable, str(VERIFY), str(root)], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_v2_ignores_foreign_legacy_symlink(self):
        if os.name == "nt":
            self.skipTest("symlink semantics")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mod.apply_plan(mod.build_install_plan(root))
            foreign = root / "foreign-role.toml"
            foreign.write_text('name = "repo_explorer"\n# foreign\n')
            (root / ".codex/agents/repo_explorer.toml").symlink_to(foreign)
            plan = mod.build_install_plan(root)
            self.assertFalse(plan.blocked)
            result = subprocess.run([sys.executable, str(VERIFY), str(root)], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_v1_uninstall_ignores_foreign_current_explorer_symlink(self):
        if os.name == "nt":
            self.skipTest("symlink semantics")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            seed_v1(root)
            foreign = root / "foreign-explorer.toml"
            foreign.write_text('name = "explorer"\n# foreign\n')
            (root / ".codex/agents/explorer.toml").symlink_to(foreign)
            plan = mod.build_uninstall_plan(root)
            self.assertFalse(plan.blocked)
            mod.apply_plan(plan)
            self.assertEqual(foreign.read_text(), 'name = "explorer"\n# foreign\n')

    def test_v1_uninstall_remains_supported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            seed_v1(root)
            plan = mod.build_uninstall_plan(root)
            self.assertFalse(plan.blocked)
            mod.apply_plan(plan)
            self.assertFalse((root / ".codex/agents/repo_explorer.toml").exists())
            self.assertFalse((root / ".codex/.agent-foundry.json").exists())


if __name__ == "__main__":
    unittest.main()
