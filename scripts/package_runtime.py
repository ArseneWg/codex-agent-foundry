#!/usr/bin/env python3
from __future__ import annotations

import argparse
import filecmp
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
SKILL = ROOT / ".agents" / "skills" / "install-codex-agent-foundry"
ASSETS = SKILL / "assets" / "project"
LEGACY = SKILL / "assets" / "legacy"

FILES = [
    "AGENTS.fragment.md",
    ".codex/config.toml",
    ".codex/agents/explorer.toml",
    ".codex/agents/reviewer.toml",
    ".codex/agents/verifier.toml",
]
LEGACY_PACKAGED_FILES = [
    ".codex/agents/repo_explorer.toml",
]

# Historical lifecycle inputs are part of the migration contract. Keep these
# hashes independent of the migration tests so accidental fixture edits cannot
# silently redefine what "Foundry v1/v2" means.
FROZEN_LEGACY_SHA256 = {
    "v1/repo_explorer.toml": "a517586bc643c1214e186d6f2a738a6b5ccc850cd81c7edbb1a76ce00f8cb40e",
    "v1/reviewer.toml": "c352eba53459e8e3a971a68bc1ea75a03c4ce7f1624ba7ec5000c57afbfdf8af",
    "v2/explorer.toml": "4faffe2df9018c7d3ddf88d1152d2138c9d96275fee27867aa5c64778933d426",
    "v2/reviewer.toml": "041722cf72606d47e9d1068375d4132af58852d4f9cf0e3352675bb9c0e90aea",
}


def copy_runtime() -> None:
    for rel in FILES:
        src = RUNTIME / rel
        dst = ASSETS / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    for rel in LEGACY_PACKAGED_FILES:
        path = ASSETS / rel
        if path.exists() or path.is_symlink():
            path.unlink()


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
    for rel in LEGACY_PACKAGED_FILES:
        if (ASSETS / rel).exists() or (ASSETS / rel).is_symlink():
            errors.append(f"stale packaged legacy asset: {rel}")
    for rel, expected in FROZEN_LEGACY_SHA256.items():
        path = LEGACY / rel
        if not path.is_file() or path.is_symlink():
            errors.append(f"missing frozen lifecycle fixture: {rel}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            errors.append(
                f"frozen lifecycle fixture drift: {rel} "
                f"(expected sha256={expected}, actual sha256={actual})"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Package Foundry runtime into the self-contained installer Skill.")
    parser.add_argument("--check", action="store_true", help="verify packaged assets and frozen lifecycle fixtures")
    args = parser.parse_args()
    if args.check:
        errors = check_runtime()
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        print("Runtime package is synchronized and lifecycle fixtures are frozen.")
        return 0
    copy_runtime()
    print("Runtime packaged into installer Skill assets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
