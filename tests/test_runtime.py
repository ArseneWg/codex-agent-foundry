import json
import subprocess
import sys
import unittest
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
SKILL = ROOT / ".agents/skills/install-codex-agent-foundry"
PACKAGE = ROOT / "scripts/package_runtime.py"


class RuntimeContractTests(unittest.TestCase):
    def test_runtime_manifest_is_valid(self):
        manifest = json.loads((RUNTIME / "manifest.json").read_text())
        self.assertEqual(manifest["runtime_version"], "1")
        self.assertIn("AGENTS.fragment.md", manifest["files"])
        self.assertIn(".codex/agents/reviewer.toml", manifest["files"])

    def test_runtime_toml_is_valid_and_roles_are_safe_defaults(self):
        config = tomllib.loads((RUNTIME / ".codex/config.toml").read_text())
        value = config["agents"]["max_concurrent_threads_per_session"]
        self.assertIsInstance(value, int)
        self.assertGreaterEqual(value, 1)
        for name in ("repo_explorer.toml", "reviewer.toml"):
            profile = tomllib.loads((RUNTIME / ".codex/agents" / name).read_text())
            self.assertEqual(profile["sandbox_mode"], "read-only")
            self.assertIn("Do not", profile["developer_instructions"])
            self.assertIn("spawn subagents", profile["developer_instructions"])

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
            "repo_explorer",
            "reviewer",
            "worker",
            "temporary_verifier",
            "worktrees",
            "parallel_writers_same_checkout",
        }
        for scenario in payload["scenarios"]:
            self.assertEqual(set(scenario["expected"]), expected_keys)

    def test_installer_default_models_and_runtime_hash_come_from_runtime_package(self):
        import importlib.util
        script = SKILL / "scripts/install.py"
        spec = importlib.util.spec_from_file_location("foundry_model_source", script)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        for filename in ("repo_explorer.toml", "reviewer.toml"):
            runtime_profile = tomllib.loads((RUNTIME / ".codex/agents" / filename).read_text())
            self.assertEqual(module.bundled_profile_model(filename), runtime_profile["model"])
        self.assertEqual(module.bundled_runtime_version(), "1")
        self.assertRegex(module.bundled_runtime_sha256(), r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
