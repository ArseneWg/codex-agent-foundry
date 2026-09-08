import json
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
SKILL = ROOT / ".agents/skills/install-codex-agent-foundry"
PACKAGE = ROOT / "scripts/package_runtime.py"


class RuntimeContractTests(unittest.TestCase):
    def test_runtime_toml_is_valid_and_roles_are_safe_defaults(self):
        config = tomllib.loads((RUNTIME / ".codex/config.toml").read_text())
        value = config["agents"]["max_concurrent_threads_per_session"]
        self.assertIsInstance(value, int)
        self.assertGreaterEqual(value, 1)
        for name in ("explorer.toml", "reviewer.toml"):
            profile = tomllib.loads((RUNTIME / ".codex/agents" / name).read_text())
            self.assertNotIn("sandbox_mode", profile)
            self.assertIn("Do not edit files", profile["developer_instructions"])
            self.assertIn("spawn subagents", profile["developer_instructions"])
        explorer = tomllib.loads((RUNTIME / ".codex/agents/explorer.toml").read_text())
        self.assertEqual(explorer["name"], "explorer")
        self.assertFalse((RUNTIME / ".codex/agents/repo_explorer.toml").exists())

    def test_runtime_policy_contains_core_orchestration_invariants(self):
        policy = (RUNTIME / "AGENTS.fragment.md").read_text()
        required = [
            "root is the default source-code writer",
            "one source-code writer per checkout",
            "separate Git worktrees",
            "Subagents must not spawn additional subagents by default",
            "one-level fan-out",
            "Agent agreement is not evidence of correctness",
            "stop condition",
            "overrides Codex's built-in `explorer`",
            "not an independent per-role sandbox boundary",
        ]
        for text in required:
            self.assertIn(text, policy)

    def test_packaged_assets_match_runtime(self):
        result = subprocess.run([sys.executable, str(PACKAGE), "--check"], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_skill_frontmatter_has_required_fields_only_supported_shape(self):
        text = (SKILL / "SKILL.md").read_text()
        self.assertTrue(text.startswith("---\n"))
        header = text.split("---\n", 2)[1]
        self.assertIn("\nname:", "\n" + header)
        self.assertIn("\ndescription:", "\n" + header)
        self.assertNotIn("\ncompatibility:", "\n" + header)

    def test_eval_scenarios_cover_core_routes(self):
        payload = json.loads((ROOT / "evals/scenarios.json").read_text())
        ids = {s["id"] for s in payload["scenarios"]}
        required = {
            "trivial-change",
            "unclear-cross-module-bug",
            "bounded-implementation",
            "noisy-verification",
            "parallel-substantial-writes",
        }
        self.assertTrue(required.issubset(ids))
        expected_keys = {
            "explorer",
            "reviewer",
            "worker",
            "temporary_verifier",
            "worktrees",
            "parallel_writers_same_checkout",
        }
        for scenario in payload["scenarios"]:
            self.assertEqual(set(scenario["expected"]), expected_keys)
        scenarios = {s["id"]: s for s in payload["scenarios"]}
        self.assertFalse(scenarios["trivial-change"]["expected"]["explorer"])
        self.assertTrue(scenarios["unclear-cross-module-bug"]["expected"]["explorer"])
        self.assertTrue(scenarios["bounded-implementation"]["expected"]["worker"])
        self.assertTrue(scenarios["noisy-verification"]["expected"]["temporary_verifier"])
        self.assertFalse(scenarios["noisy-verification"]["expected"]["reviewer"])
        self.assertFalse(scenarios["parallel-substantial-writes"]["expected"]["parallel_writers_same_checkout"])

    def test_installer_default_models_come_from_runtime_profiles(self):
        import importlib.util
        script = SKILL / "scripts/install.py"
        spec = importlib.util.spec_from_file_location("foundry_model_source", script)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        for filename in ("explorer.toml", "reviewer.toml"):
            runtime_profile = tomllib.loads((RUNTIME / ".codex/agents" / filename).read_text())
            self.assertEqual(module.bundled_profile_model(filename), runtime_profile["model"])


if __name__ == "__main__":
    unittest.main()
