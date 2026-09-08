import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/install-codex-agent-foundry"
INSTALL = SKILL / "scripts/install.py"
VERIFY = SKILL / "scripts/verify.py"

spec = importlib.util.spec_from_file_location("foundry_install_runtime_check", INSTALL)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class RuntimeCheckTests(unittest.TestCase):
    def make_fake_codex(self, directory: Path, *, catalog_ok: bool = True) -> Path:
        path = directory / "codex"
        body = f'''#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
if "--version" in args:
    print("codex-cli 9.9.9")
    raise SystemExit(0)
if "debug" in args and "models" in args and "--bundled" in args:
    if "--strict-config" not in args:
        print("strict config flag missing", file=sys.stderr)
        raise SystemExit(7)
    if {str(catalog_ok)}:
        print(json.dumps([{{"id":"gpt-5.6-terra"}}, {{"id":"gpt-5.6"}}]))
        raise SystemExit(0)
    print("synthetic strict config failure", file=sys.stderr)
    raise SystemExit(5)
print("unexpected args: " + " ".join(args), file=sys.stderr)
raise SystemExit(9)
'''
        path.write_text(body)
        path.chmod(0o755)
        return path

    def run_verify(self, root: Path, env: dict[str, str]):
        return subprocess.run(
            [sys.executable, str(VERIFY), str(root), "--runtime-check"],
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    def test_runtime_check_reports_cli_config_and_models(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as bindir:
            root = Path(td)
            mod.apply_plan(mod.build_install_plan(root))
            fake_dir = Path(bindir)
            self.make_fake_codex(fake_dir)
            env = os.environ.copy()
            env["PATH"] = str(fake_dir) + os.pathsep + env.get("PATH", "")
            result = self.run_verify(root, env)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("version: codex-cli 9.9.9", result.stdout)
            self.assertIn("strict config: passed", result.stdout)
            self.assertIn("repo_explorer: gpt-5.6-terra / medium (bundled catalog: present)", result.stdout)
            self.assertIn("reviewer: gpt-5.6 / high (bundled catalog: present)", result.stdout)
            self.assertIn("Account model availability is not verified", result.stdout)

    def test_runtime_check_fails_when_codex_missing(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as empty_path:
            root = Path(td)
            mod.apply_plan(mod.build_install_plan(root))
            env = os.environ.copy()
            env["PATH"] = empty_path
            result = self.run_verify(root, env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("codex is not in PATH", result.stdout)

    def test_runtime_check_surfaces_strict_config_failure(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as bindir:
            root = Path(td)
            mod.apply_plan(mod.build_install_plan(root))
            fake_dir = Path(bindir)
            self.make_fake_codex(fake_dir, catalog_ok=False)
            env = os.environ.copy()
            env["PATH"] = str(fake_dir) + os.pathsep + env.get("PATH", "")
            result = self.run_verify(root, env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("strict-config/model-catalog check failed", result.stdout)
            self.assertIn("synthetic strict config failure", result.stdout)


if __name__ == "__main__":
    unittest.main()
