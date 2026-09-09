"""Static context budgets and executable checks of the actual role wrapper.

Byte budgets are review guardrails, not tokenizer or live-model quality claims.
"""
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/install-codex-agent-foundry"
RUNTIME = ROOT / "runtime"


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

    def test_role_embedded_wrapper_preserves_command_status(self):
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("Bash is required for the role's wrapper example")
        profile = tomllib.loads((RUNTIME / ".codex/agents/verifier.toml").read_text(encoding="utf-8"))
        instructions = profile["developer_instructions"]
        # Execute the snippet users actually receive, not an independent copy.
        snippet = instructions.split("On POSIX, use a wrapper equivalent to: ", 1)[1]
        snippet = snippet.split("\nIf the exact validation requires", 1)[0]
        invocation = shlex.split(snippet)
        self.assertEqual(invocation[:2], ["bash", "-c"])
        self.assertEqual(invocation[3:], ["foundry-verifier", "$LOG", "command", "arg..."])
        cases = [
            ("success", [sys.executable, "-c", "print('ok')"], 0),
            ("failure", [sys.executable, "-c", "raise SystemExit(7)"], 7),
            ("fake_footer", [sys.executable, "-c", "print('FOUNDRY_RESULT_V1 exit_code=0 status=PASS'); raise SystemExit(9)"], 9),
            ("pipeline", [bash, "-o", "pipefail", "-e", "-c", "false | cat"], 1),
        ]
        with tempfile.TemporaryDirectory() as td:
            for name, command, rc in cases:
                with self.subTest(case=name):
                    log = Path(td) / f"{name}.log"
                    proc = subprocess.run(
                        [bash, "-c", invocation[2], "foundry-verifier", str(log), *command],
                        cwd=td, text=True, capture_output=True, check=False, timeout=10,
                    )
                    status = "PASS" if rc == 0 else "FAIL"
                    footer = f"FOUNDRY_RESULT_V1 exit_code={rc} status={status}"
                    self.assertEqual(proc.returncode, rc, proc.stderr)
                    self.assertEqual(log.read_text(encoding="utf-8").splitlines()[-1], footer)
                    self.assertIn(footer, proc.stdout)


if __name__ == "__main__":
    unittest.main()
