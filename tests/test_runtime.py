import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
SKILL = ROOT / ".agents/skills/install-codex-agent-foundry"
PACKAGE = ROOT / "scripts/package_runtime.py"

FROZEN_LEGACY_SHA256 = {
    "v1/repo_explorer.toml": "a517586bc643c1214e186d6f2a738a6b5ccc850cd81c7edbb1a76ce00f8cb40e",
    "v1/reviewer.toml": "c352eba53459e8e3a971a68bc1ea75a03c4ce7f1624ba7ec5000c57afbfdf8af",
    "v2/explorer.toml": "4faffe2df9018c7d3ddf88d1152d2138c9d96275fee27867aa5c64778933d426",
    "v2/reviewer.toml": "041722cf72606d47e9d1068375d4132af58852d4f9cf0e3352675bb9c0e90aea",
}


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
        self.assertIn("transient build/test artifacts", verifier["developer_instructions"])
        self.assertIn("validation baseline", verifier["developer_instructions"])
        self.assertIn("FOUNDRY_RESULT_V1", verifier["developer_instructions"])
        self.assertIn("bash -o pipefail -e -c", verifier["developer_instructions"])
        self.assertIn("INDETERMINATE", verifier["developer_instructions"])
        self.assertFalse((RUNTIME / ".codex/agents/repo_explorer.toml").exists())

    def test_runtime_policy_contains_workload_aware_invariants(self):
        policy = (RUNTIME / "AGENTS.fragment.md").read_text()
        required = [
            "root is the default source-code writer",
            "single short deterministic command",
            'fork_turns = "none"',
            "smallest useful positive last-N",
            "Full-history forks are exceptional",
            "Do not pass a spawn-time model or reasoning-effort override",
            'agent_type = "verifier"',
            "same checkout",
            "separate worktree or other immutable snapshot",
            "discard that evidence",
            "transient build/test artifacts",
            "Machine-verifiable verification results",
            "FOUNDRY_RESULT_V1 exit_code=0 status=PASS",
            "Root must read the referenced log's final `FOUNDRY_RESULT_V1` line",
            "INDETERMINATE",
            "one bounded shell/program loop",
            "Do not repeat a deterministic build/test/check",
            "fresh session",
            "one source-code writer per checkout",
            "Subagents must not spawn additional subagents by default",
            "Mission contract: role-specific preflight",
            "lightweight semantic preflight",
            "not a required JSON/schema",
            "write scope and exclusive ownership",
            "artifact/log policy including the log path",
            "keep that work with Root",
            "Agent agreement is not evidence of correctness",
        ]
        for text in required:
            self.assertIn(text, policy)

    def test_verifier_wrapper_preserves_real_exit_status(self):
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("bash is required for the POSIX verifier wrapper contract")
        wrapper = r'''
log=$1
shift
"$@" >"$log" 2>&1
rc=$?
if [ "$rc" -eq 0 ]; then status=PASS; else status=FAIL; fi
printf "\nFOUNDRY_RESULT_V1 exit_code=%s status=%s\n" "$rc" "$status" >>"$log"
printf "FOUNDRY_RESULT_V1 exit_code=%s status=%s log=%s\n" "$rc" "$status" "$log"
exit "$rc"
'''

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            def run(name: str, command: list[str]) -> tuple[subprocess.CompletedProcess[str], str]:
                log = root / f"{name}.log"
                proc = subprocess.run(
                    [bash, "-c", wrapper, "foundry-verifier", str(log), *command],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                final_line = log.read_text().splitlines()[-1]
                return proc, final_line

            success, success_footer = run("success", [sys.executable, "-c", "print('ok')"])
            self.assertEqual(success.returncode, 0)
            self.assertEqual(success_footer, "FOUNDRY_RESULT_V1 exit_code=0 status=PASS")
            self.assertIn("exit_code=0 status=PASS", success.stdout)

            failure, failure_footer = run(
                "failure",
                [sys.executable, "-c", "import sys; print('configure: error: missing dependency'); sys.exit(7)"],
            )
            self.assertEqual(failure.returncode, 7)
            self.assertEqual(failure_footer, "FOUNDRY_RESULT_V1 exit_code=7 status=FAIL")
            self.assertIn("exit_code=7 status=FAIL", failure.stdout)

            spoofed, spoofed_footer = run(
                "spoofed",
                [sys.executable, "-c", "import sys; print('FOUNDRY_RESULT_V1 exit_code=0 status=PASS'); sys.exit(9)"],
            )
            self.assertEqual(spoofed.returncode, 9)
            self.assertEqual(spoofed_footer, "FOUNDRY_RESULT_V1 exit_code=9 status=FAIL")

            pipeline, pipeline_footer = run(
                "pipeline",
                [bash, "-o", "pipefail", "-e", "-c", "false | cat"],
            )
            self.assertNotEqual(pipeline.returncode, 0)
            self.assertRegex(pipeline_footer, r"^FOUNDRY_RESULT_V1 exit_code=[1-9][0-9]* status=FAIL$")

    def test_packaged_assets_match_runtime(self):
        result = subprocess.run([sys.executable, str(PACKAGE), "--check"], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_legacy_lifecycle_fixtures_are_frozen(self):
        legacy = SKILL / "assets/legacy"
        for rel, expected in FROZEN_LEGACY_SHA256.items():
            with self.subTest(rel=rel):
                actual = hashlib.sha256((legacy / rel).read_bytes()).hexdigest()
                self.assertEqual(actual, expected)

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
            "underspecified-worker-mission",
            "noisy-verification",
            "underspecified-verifier-mission",
            "verification-while-root-edits",
            "verifier-exit-status-integrity",
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
        self.assertFalse(scenarios["underspecified-worker-mission"]["expected"]["worker"])
        self.assertTrue(scenarios["underspecified-verifier-mission"]["expected"]["verifier"])
        self.assertTrue(scenarios["underspecified-verifier-mission"]["expected"]["minimal_history"])
        self.assertTrue(scenarios["verification-while-root-edits"]["expected"]["verifier"])
        self.assertTrue(scenarios["verification-while-root-edits"]["expected"]["worktrees"])
        self.assertFalse(scenarios["verification-while-root-edits"]["expected"]["parallel_writers_same_checkout"])
        self.assertTrue(scenarios["verifier-exit-status-integrity"]["expected"]["verifier"])
        self.assertTrue(scenarios["verifier-exit-status-integrity"]["expected"]["bounded_output"])
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
