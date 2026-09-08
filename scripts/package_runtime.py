#!/usr/bin/env python3
from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
ASSETS = ROOT / ".agents" / "skills" / "install-codex-agent-foundry" / "assets" / "project"

FILES = [
    "AGENTS.fragment.md",
    ".codex/config.toml",
    ".codex/agents/repo_explorer.toml",
    ".codex/agents/reviewer.toml",
]

def copy_runtime() -> None:
    for rel in FILES:
        src = RUNTIME / rel
        dst = ASSETS / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

def check_runtime() -> list[str]:
    errors: list[str] = []
    for rel in FILES:
        src = RUNTIME / rel
        dst = ASSETS / rel
        if not src.exists():
            errors.append(f"missing runtime source: {rel}")
        elif not dst.exists():
            errors.append(f"missing packaged asset: {rel}")
        elif not filecmp.cmp(src, dst, shallow=False):
            errors.append(f"packaged asset drift: {rel}")
    return errors

def main() -> int:
    parser = argparse.ArgumentParser(description="Package Foundry runtime into the self-contained installer Skill.")
    parser.add_argument("--check", action="store_true", help="verify packaged assets match runtime sources")
    args = parser.parse_args()
    if args.check:
        errors = check_runtime()
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        print("Runtime package is synchronized.")
        return 0
    copy_runtime()
    print("Runtime packaged into installer Skill assets.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
