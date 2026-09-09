"""Static context budgets and executable checks of the actual Verifier runner.

Byte budgets are review guardrails, not tokenizer or live-model quality claims.
"""
import os
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/install-codex-agent-foundry"
RUNTIME = ROOT / "runtime"
RUNNER = RUNTIME / ".codex/foundry-verifier-run.py"


class PromptSurfaceTests(unittest.TestCase):
    def test_context_budgets(self):
        budgets = {
            RUNTIME / "AGENTS.fragment.md": 6500,
            SKILL / "SKILL.md": 3000,
            ROOT / "README.md": 9000,
            ROOT / "README.zh-CN.md": 9000,
            SKILL / "references/design.md": 11000,
            ROOT / "evals/README.md": 3000,
        }
        for path, limit in budgets.items():
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertLessEqual(len(path.read_bytes()), limit)

    def test_discovery_description_is_small_and_scoped(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        header = text.split("---\n", 2)[1]
        match = re.search(r"(?m)^description: (.+)$", header)
        self.assertIsNotNone(match)
        description = match.group(1)
        self.assertLessEqual(len(description.encode("utf-8")), 240)
        self.assertIn("uninstall", description)
        self.assertIn("Not a general coding or review skill", description)

    def test_role_models_and_efforts_are_unchanged(self):
        expected = {
            "explorer": ("gpt-5.6-terra", "medium"),
            "reviewer": ("gpt-5.6-terra", "high"),
            "verifier": ("gpt-5.6-luna", "low"),
        }
        for role, selection in expected.items():
            with self.subTest(role=role):
                profile = tomllib.loads((RUNTIME / f".codex/agents/{role}.toml").read_text(encoding="utf-8"))
                self.assertEqual((profile["model"], profile["model_reasoning_effort"]), selection)

    def test_verifier_profile_uses_deterministic_stage_runner(self):
        profile = tomllib.loads((RUNTIME / ".codex/agents/verifier.toml").read_text(encoding="utf-8"))
        instructions = profile["developer_instructions"]
        self.assertIn(".codex/foundry-verifier-run.py", instructions)
        self.assertIn("separate argv command", instructions)
        self.assertIn("skipped stages can never be treated as PASS", instructions)
        self.assertIn("shell `-c` command strings", instructions)

    def test_actual_runner_preserves_direct_status_and_rejects_shell_c(self):
        if os.name == "nt":
            self.skipTest("POSIX shell rejection fixture")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            success_log = root / "success.log"
            success = subprocess.run(
                [sys.executable, str(RUNNER), "--log", str(success_log), "--", sys.executable, "-c", "print('ok')"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(success.returncode, 0)
            self.assertEqual(success_log.read_text().splitlines()[-1], "FOUNDRY_RESULT_V1 exit_code=0 status=PASS")

            fail_log = root / "fail.log"
            failure = subprocess.run(
                [sys.executable, str(RUNNER), "--log", str(fail_log), "--", sys.executable, "-c", "raise SystemExit(9)"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(failure.returncode, 9)
            self.assertEqual(fail_log.read_text().splitlines()[-1], "FOUNDRY_RESULT_V1 exit_code=9 status=FAIL")

            compound_log = root / "compound.log"
            compound = subprocess.run(
                [sys.executable, str(RUNNER), "--log", str(compound_log), "--", "bash", "-c", "false && printf impossible; printf masked"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(compound.returncode, 64)
            self.assertIn("status=INDETERMINATE", compound_log.read_text().splitlines()[-1])


if __name__ == "__main__":
    unittest.main()
