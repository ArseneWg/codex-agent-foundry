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
        for name in ("explorer.toml", "reviewer.toml", "verifier.toml"):
            profile = tomllib.loads((RUNTIME / ".codex/agents" / name).read_text())
            self.assertNotIn("sandbox_mode", profile)
            self.assertIn("Do not edit files", profile["developer_instructions"])
            self.assertIn("spawn subagents", profile["developer_instructions"])
        explorer = tomllib.loads((RUNTIME / ".codex/agents/explorer.toml").read_text())
        verifier = tomllib.loads((RUNTIME / ".codex/agents/verifier.toml").read_text())
        self.assertEqual(explorer["name"], "explorer")
        self.assertEqual(verifier["name"], "verifier")
        self.assertEqual(verifier["model"], "gpt-5.6-luna")
        self.assertEqual(verifier["model_reasoning_effort"], "low")
        self.assertFalse((RUNTIME / ".codex/agents/repo_explorer.toml").exists())

    def test_runtime_policy_contains_workload_aware_invariants(self):
        policy = (RUNTIME / "AGENTS.fragment.md").read_text()
        required = [
            "root is the default source-code writer",
            "single short deterministic command",
            "fork_turns = \"none\"",
            "smallest useful positive last-N",
            "Full-history forks are exceptional",
            "one bounded shell/program loop",
            "Do not repeat a deterministic build/test/check",
            "full-log path",
            "fresh session",
            "one source-code writer per checkout",
            "Subagents must not spawn additional subagents by default",
            "Agent agreement is not evidence of correctness",
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
        self.assertIn('version: "3"', header)
        self.assertNotIn("\ncompatibility:", "\n" + header)

    def test_eval_scenarios_cover_workload_routes(self):
        payload = json.loads((ROOT / "evals/scenarios.json").read_text())
        self.assertEqual(payload["version"], 3)
        ids = {s["id"] for s in payload["scenarios"]}
        required = {
            "trivial-change",
            "single-short-validation",
            "unclear-cross-module-bug",
            "bounded-implementation",
            "noisy-verification",
            "polling-device-state",
            "repeated-validation-no-state-change",
            "parallel-substantial-writes",
        }
        self.assertTrue(required.issubset(ids))
        expected_keys = {
            "explorer", "reviewer", "worker", "verifier", "worktrees",
            "parallel_writers_same_checkout", "minimal_history", "bounded_output",
            "aggregate_polling", "avoid_redundant_rerun",
        }
        for scenario in payload["scenarios"]:
            self.assertEqual(set(scenario["expected"]), expected_keys)
        scenarios = {s["id"]: s for s in payload["scenarios"]}
        self.assertFalse(scenarios["single-short-validation"]["expected"]["verifier"])
        self.assertTrue(scenarios["noisy-verification"]["expected"]["verifier"])
        self.assertTrue(scenarios["polling-device-state"]["expected"]["aggregate_polling"])
        self.assertTrue(scenarios["repeated-validation-no-state-change"]["expected"]["avoid_redundant_rerun"])
        self.assertTrue(scenarios["unclear-cross-module-bug"]["expected"]["minimal_history"])
        self.assertTrue(scenarios["parallel-substantial-writes"]["expected"]["worktrees"])
        self.assertFalse(scenarios["parallel-substantial-writes"]["expected"]["parallel_writers_same_checkout"])

    def test_installer_default_models_come_from_runtime_profiles(self):
        import importlib.util
        script = SKILL / "scripts/install.py"
        spec = importlib.util.spec_from_file_location("foundry_model_source", script)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        for filename in ("explorer.toml", "reviewer.toml", "verifier.toml"):
            runtime_profile = tomllib.loads((RUNTIME / ".codex/agents" / filename).read_text())
            self.assertEqual(module.bundled_profile_model(filename), runtime_profile["model"])


if __name__ == "__main__":
    unittest.main()
