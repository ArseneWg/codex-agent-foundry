import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/install-codex-agent-foundry"
INSTALL = SKILL / "scripts/install.py"
VERIFY = SKILL / "scripts/verify.py"

spec = importlib.util.spec_from_file_location("foundry_install_experience", INSTALL)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class RuntimeExperienceTests(unittest.TestCase):
    def test_state_records_v3_roles_and_runtime_provenance(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mod.apply_plan(mod.build_install_plan(root))
            state = json.loads((root / ".codex/.agent-foundry.json").read_text())
            self.assertEqual(state["version"], 3)
            self.assertEqual(state["runtime_version"], "3")
            self.assertEqual(state["managed_agents"], ["explorer.toml", "reviewer.toml", "verifier.toml"])
            self.assertEqual(set(state["models"]), {"explorer", "reviewer", "verifier"})
            self.assertEqual(state["models"]["verifier"], "gpt-5.6-luna")
            self.assertEqual(state["runtime_sha256"], mod.runtime_sha256())
            self.assertRegex(state["runtime_sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(state["source_revision"])

    def test_source_revision_is_unknown_for_a_copied_skill_inside_an_unrelated_repo(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake_skill = root / ".agents/skills/install-codex-agent-foundry"
            fake_skill.mkdir(parents=True)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.com"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            (root / "README.md").write_text("target repo\n")
            subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "target commit"], check=True)
            target_revision = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
            with mock.patch.object(mod, "SKILL_ROOT", fake_skill):
                revision = mod.source_revision()
            self.assertEqual(revision, "unknown")
            self.assertNotEqual(revision, target_revision)

    def test_idempotent_plan_uses_current_wording(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mod.apply_plan(mod.build_install_plan(root))
            plan = mod.build_install_plan(root)
            agents = next(step for step in plan.steps if step.path == root / "AGENTS.md")
            self.assertEqual(agents.action, "unchanged")
            self.assertEqual(agents.detail, "managed block already current")

    def test_check_prints_selected_models_and_effort(self):
        with tempfile.TemporaryDirectory() as td:
            result = subprocess.run([sys.executable, str(INSTALL), td, "--check"], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("explorer: gpt-5.6-terra / medium", result.stdout)
            self.assertIn("reviewer: gpt-5.6 / high", result.stdout)
            self.assertIn("verifier: gpt-5.6-luna / low", result.stdout)

    def test_verifier_model_override_is_role_local(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            verifier_override = "gpt-verifier-only-test"
            mod.apply_plan(mod.build_install_plan(root, verifier_model=verifier_override))
            state = json.loads((root / ".codex/.agent-foundry.json").read_text())
            self.assertEqual(state["models"]["verifier"], verifier_override)
            self.assertEqual(state["models"]["explorer"], "gpt-5.6-terra")
            self.assertEqual(state["models"]["reviewer"], "gpt-5.6")
            self.assertIn(f'model = "{verifier_override}"', (root / ".codex/agents/verifier.toml").read_text())
            self.assertIn('model = "gpt-5.6-terra"', (root / ".codex/agents/explorer.toml").read_text())
            self.assertIn('model = "gpt-5.6"', (root / ".codex/agents/reviewer.toml").read_text())

    def test_apply_prints_new_session_hint(self):
        with tempfile.TemporaryDirectory() as td:
            result = subprocess.run([sys.executable, str(INSTALL), td], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Start a new Codex session in this project to load Foundry.", result.stdout)

    def test_runtime_check_reports_verifier_and_model_limit(self):
        if os.name == "nt":
            self.skipTest("POSIX executable fixture")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mod.apply_plan(mod.build_install_plan(root))
            bindir = root / "bin"
            bindir.mkdir()
            fake = bindir / "codex"
            fake.write_text("#!/bin/sh\necho 'codex-cli 9.9.9-test'\n")
            fake.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
            result = subprocess.run([sys.executable, str(VERIFY), str(root), "--runtime-check"], text=True, capture_output=True, env=env, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("explorer: gpt-5.6-terra / medium", result.stdout)
            self.assertIn("reviewer: gpt-5.6 / high", result.stdout)
            self.assertIn("verifier: gpt-5.6-luna / low", result.stdout)
            self.assertIn("--verifier-model gpt-5.6-terra", result.stdout)
            self.assertIn("resolved child model/effort: not verified", result.stdout)

    def test_python_guard_precedes_tomllib_import(self):
        for path in (INSTALL, VERIFY):
            text = path.read_text()
            self.assertLess(text.index("sys.version_info < (3, 11)"), text.index("import tomllib"))


if __name__ == "__main__":
    unittest.main()
