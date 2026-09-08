#!/usr/bin/env python3
from __future__ import annotations

import argparse
import filecmp
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
ASSETS = ROOT / ".agents" / "skills" / "install-codex-agent-foundry" / "assets" / "project"
MANIFEST = "manifest.json"


class ManifestError(RuntimeError):
    pass


def load_manifest() -> tuple[str, list[str]]:
    path = RUNTIME / MANIFEST
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManifestError(f"missing runtime manifest: {MANIFEST}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"invalid runtime manifest: {exc}") from exc
    if not isinstance(payload, dict):
        raise ManifestError("runtime manifest must contain a JSON object")
    version = payload.get("runtime_version")
    files = payload.get("files")
    if not isinstance(version, str) or not version.strip():
        raise ManifestError("runtime manifest runtime_version must be a non-empty string")
    if not isinstance(files, list) or not files or not all(isinstance(x, str) and x.strip() for x in files):
        raise ManifestError("runtime manifest files must be a non-empty list of paths")
    for rel in files:
        rel_path = Path(rel)
        if rel_path.is_absolute() or ".." in rel_path.parts or rel_path.as_posix() != rel:
            raise ManifestError(f"runtime manifest contains unsafe path: {rel!r}")
    if len(set(files)) != len(files):
        raise ManifestError("runtime manifest files contains duplicates")
    if MANIFEST in files:
        raise ManifestError("runtime manifest must not list itself in files")
    return version, files


def package_files() -> list[str]:
    _, files = load_manifest()
    return [MANIFEST, *files]


def copy_runtime() -> None:
    for rel in package_files():
        src = RUNTIME / rel
        dst = ASSETS / rel
        if not src.is_file():
            raise ManifestError(f"missing runtime source: {rel}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def check_runtime() -> list[str]:
    try:
        files = package_files()
    except ManifestError as exc:
        return [str(exc)]
    errors: list[str] = []
    for rel in files:
        src = RUNTIME / rel
        dst = ASSETS / rel
        if not src.is_file():
            errors.append(f"missing runtime source: {rel}")
        elif not dst.is_file():
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
        version, _ = load_manifest()
        print(f"Runtime package is synchronized (runtime {version}).")
        return 0
    try:
        copy_runtime()
        version, _ = load_manifest()
    except ManifestError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Runtime {version} packaged into installer Skill assets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
