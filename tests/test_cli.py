import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".agents/skills/install-codex-agent-foundry/scripts/install.py"

class CLITests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], text=True, capture_output=True)

    def test_check_lists_full_install_plan_including_state(self):
        with tempfile.TemporaryDirectory() as td:
            result = self.run_cli(td, "--check")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PLAN:", result.stdout)
            self.assertIn(".codex/.agent-foundry.json", result.stdout)
            self.assertIn("AGENTS.md", result.stdout)
            self.assertEqual(list(Path(td).iterdir()), [])

    def test_conflict_reports_blocked_plan_and_no_writes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            agents = root / ".codex/agents"
            agents.mkdir(parents=True)
            (agents / "reviewer.toml").write_text('name = "reviewer"\n# foreign\n')
            result = self.run_cli(root)
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
            self.assertIn("BLOCKED PLAN:", result.stdout)
            self.assertIn("No files were changed.", result.stdout)
            self.assertIn(".codex/.agent-foundry.json", result.stdout)
            self.assertFalse((root / "AGENTS.md").exists())
            self.assertFalse((root / ".codex/config.toml").exists())

    def test_force_check_lists_backup(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            agents = root / ".codex/agents"
            agents.mkdir(parents=True)
            (agents / "reviewer.toml").write_text('name = "reviewer"\n# foreign\n')
            result = self.run_cli(root, "--check", "--force")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("backup", result.stdout)
            self.assertIn("reviewer.toml.foundry-backup", result.stdout)

    def test_apply_output_paths_match_check_mutating_paths(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            check = self.run_cli(root, "--check")
            self.assertEqual(check.returncode, 0)
            applied = self.run_cli(root)
            self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
            def paths(output):
                found = set()
                for line in output.splitlines():
                    if line.startswith("- "):
                        parts = line.split(maxsplit=2)
                        if len(parts) == 3:
                            path = parts[2].split(":", 1)[0]
                            found.add(path)
                return found
            self.assertEqual(paths(check.stdout), paths(applied.stdout))

    def test_uninstall_check_and_apply(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.assertEqual(self.run_cli(root).returncode, 0)
            check = self.run_cli(root, "--uninstall", "--check")
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
            self.assertIn("PLAN:", check.stdout)
            self.assertTrue((root / ".codex/.agent-foundry.json").exists())
            applied = self.run_cli(root, "--uninstall")
            self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
            self.assertFalse((root / ".codex/.agent-foundry.json").exists())

if __name__ == "__main__":
    unittest.main()
