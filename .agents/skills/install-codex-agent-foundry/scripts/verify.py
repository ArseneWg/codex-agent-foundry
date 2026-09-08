#!/usr/bin/env python3
from __future__ import annotations

import sys

if sys.version_info < (3, 11):
    print(
        f"ERROR: Codex Agent Foundry requires Python 3.11+ (found {sys.version_info.major}.{sys.version_info.minor}). "
        "Ubuntu 22.04 ships Python 3.10 by default; run verification with Python 3.11 or newer.",
        file=sys.stderr,
    )
    raise SystemExit(2)

import argparse
import json
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

VERSION = 1
START = "<!-- codex-agent-foundry:start -->"
END = "<!-- codex-agent-foundry:end -->"
MANAGED = "# managed-by: codex-agent-foundry"
SKILL_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = SKILL_ROOT / "assets" / "project"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def checked_read_text(path: Path, errors: list[str], label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except UnicodeDecodeError:
        errors.append(f"{label} is not valid UTF-8")
        return ""
    except OSError as exc:
        errors.append(f"{label} cannot be read: {exc}")
        return ""


def managed_path_errors(target: Path) -> list[str]:
    errors: list[str] = []
    directory_paths = {".codex", ".codex/agents"}
    for rel in (
        ".codex",
        ".codex/agents",
        "AGENTS.md",
        ".codex/config.toml",
        ".codex/.agent-foundry.json",
        ".codex/agents/repo_explorer.toml",
        ".codex/agents/reviewer.toml",
    ):
        path = target / rel
        if path.is_symlink():
            errors.append(f"{rel} is a symlink; Foundry-managed paths must be regular repository paths")
        elif path.exists():
            if rel in directory_paths and not path.is_dir():
                errors.append(f"{rel} must be a directory")
            elif rel not in directory_paths and not path.is_file():
                errors.append(f"{rel} must be a regular file")
    return errors


def expected_agents_block() -> str:
    fragment = read_text(ASSET_ROOT / "AGENTS.fragment.md").strip()
    return f"{START}\n{fragment}\n{END}"


def foundry_block(text: str) -> str | None:
    if text.count(START) != 1 or text.count(END) != 1:
        return None
    start = text.index(START)
    end = text.index(END)
    if start >= end:
        return None
    return text[start : end + len(END)]


def is_foundry_managed(content: str) -> bool:
    return any(line.strip() == MANAGED for line in content.splitlines()[:5])


def set_profile_model(content: str, model: str) -> str:
    new, count = re.subn(r'(?m)^model\s*=\s*"[^"]*"\s*$', f"model = {json.dumps(model)}", content, count=1)
    if count != 1:
        raise ValueError("profile does not contain exactly one model assignment")
    return new


def load_state(target: Path, errors: list[str]) -> dict[str, object] | None:
    state = target / ".codex" / ".agent-foundry.json"
    if not state.exists():
        errors.append(".codex/.agent-foundry.json is missing")
        return None
    try:
        payload = json.loads(read_text(state))
    except Exception as exc:
        errors.append(f"Foundry state file is invalid: {exc}")
        return None
    if not isinstance(payload, dict):
        errors.append("Foundry state file must contain a JSON object")
        return None

    required = {
        "version",
        "managed_agents",
        "agents_md_markers",
        "concurrency_added",
        "config_created",
        "models",
        "runtime_version",
        "source_revision",
        "runtime_sha256",
    }
    missing = sorted(required - payload.keys())
    if missing:
        errors.append(
            "Foundry state is missing provenance fields; rerun the installer to refresh metadata: "
            + ", ".join(missing)
        )
    if payload.get("version") != VERSION:
        errors.append(f"installed Foundry version is not {VERSION}")
    if payload.get("managed_agents") != ["repo_explorer.toml", "reviewer.toml"]:
        errors.append("Foundry state has unexpected managed_agents")
    if payload.get("agents_md_markers") != [START, END]:
        errors.append("Foundry state has unexpected AGENTS.md markers")
    for key in ("concurrency_added", "config_created"):
        if not isinstance(payload.get(key), bool):
            errors.append(f"Foundry state field {key} must be boolean")
    models = payload.get("models")
    if not isinstance(models, dict):
        errors.append("Foundry state has invalid models")
    else:
        if set(models) != {"repo_explorer", "reviewer"}:
            errors.append("Foundry state models has unexpected role keys")
        if not all(isinstance(v, str) and v.strip() for v in models.values()):
            errors.append("Foundry state model values must be non-empty strings")
    if "runtime_version" in payload and (not isinstance(payload["runtime_version"], str) or not payload["runtime_version"]):
        errors.append("Foundry state runtime_version must be a non-empty string")
    if "source_revision" in payload and (not isinstance(payload["source_revision"], str) or not payload["source_revision"]):
        errors.append("Foundry state source_revision must be a non-empty string")
    if "runtime_sha256" in payload and not re.fullmatch(r"[0-9a-f]{64}", str(payload["runtime_sha256"])):
        errors.append("Foundry state runtime_sha256 must be a 64-character lowercase hex digest")
    return payload


def profile_runtime_info(target: Path, state: dict[str, object] | None, errors: list[str]) -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    models = state.get("models", {}) if isinstance(state, dict) else {}
    if not isinstance(models, dict):
        models = {}
    keys = {"repo_explorer.toml": "repo_explorer", "reviewer.toml": "reviewer"}
    for name in ("repo_explorer.toml", "reviewer.toml"):
        path = target / ".codex" / "agents" / name
        actual = checked_read_text(path, errors, str(path.relative_to(target)))
        if not actual:
            errors.append(f"{path.relative_to(target)} is missing")
            continue
        if not is_foundry_managed(actual):
            errors.append(f"{path.relative_to(target)} is not marked as Foundry-managed")
            continue
        try:
            actual_parsed = tomllib.loads(actual)
        except Exception as exc:
            errors.append(f"{path.relative_to(target)} is invalid TOML: {exc}")
            continue
        bundled = read_text(ASSET_ROOT / ".codex" / "agents" / name)
        try:
            bundled_parsed = tomllib.loads(bundled)
            default_model = bundled_parsed.get("model")
            if not isinstance(default_model, str) or not default_model.strip():
                raise ValueError("bundled profile has an invalid model")
            model = str(models.get(keys[name]) or default_model)
            expected = set_profile_model(bundled, model)
        except Exception as exc:
            errors.append(f"bundled {name} template is invalid: {exc}")
            continue
        if actual != expected:
            errors.append(f"{path.relative_to(target)} has drifted from the expected Foundry profile")
        effort = actual_parsed.get("model_reasoning_effort")
        if not isinstance(effort, str) or not effort.strip():
            errors.append(f"{path.relative_to(target)} has invalid model_reasoning_effort")
        else:
            result[keys[name]] = (model, effort)
    return result


def run_runtime_check(target: Path, role_info: dict[str, tuple[str, str]], errors: list[str]) -> list[str]:
    notes: list[str] = []
    codex = shutil.which("codex")
    if not codex:
        errors.append("runtime check: codex is not available on PATH")
        return notes
    try:
        proc = subprocess.run(
            [codex, "--version"],
            cwd=target,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        errors.append(f"runtime check: failed to execute codex --version: {exc}")
        return notes
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        errors.append(f"runtime check: codex --version failed: {detail or f'exit {proc.returncode}'}")
        return notes
    version = (proc.stdout or proc.stderr).strip()
    notes.append(f"codex: {version or 'version command succeeded'}")
    notes.append("strict TOML parsing: passed for project config and Foundry agent profiles")
    for role in ("repo_explorer", "reviewer"):
        if role in role_info:
            model, effort = role_info[role]
            notes.append(f"{role}: {model} / {effort}")
    notes.append("account model availability: not verified; start a new Codex session to confirm the selected models can be used")
    notes.append("Codex schema/session loading: not claimed beyond CLI presence/version and strict local TOML/profile validation")
    return notes


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Codex Agent Foundry installation.")
    parser.add_argument("target", nargs="?", default=".")
    parser.add_argument(
        "--runtime-check",
        action="store_true",
        help="also check Codex CLI presence/version and report selected models; does not verify account model availability",
    )
    args = parser.parse_args()
    target = Path(args.target).resolve()
    errors: list[str] = []
    errors.extend(managed_path_errors(target))
    if errors:
        print("Foundry verification failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    state = load_state(target, errors)

    agents_md = target / "AGENTS.md"
    agents_text = checked_read_text(agents_md, errors, "AGENTS.md")
    block = foundry_block(agents_text)
    if block is None:
        errors.append("AGENTS.md does not contain exactly one valid, correctly ordered Foundry managed block")
    elif block != expected_agents_block():
        errors.append("AGENTS.md Foundry managed block has drifted from the bundled template")

    config = target / ".codex" / "config.toml"
    if not config.exists():
        errors.append(".codex/config.toml is missing")
    else:
        try:
            parsed = tomllib.loads(read_text(config))
            value = parsed.get("agents", {}).get("max_concurrent_threads_per_session")
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                errors.append("Foundry concurrency setting must be an integer >= 1")
        except Exception as exc:
            errors.append(f".codex/config.toml is invalid: {exc}")

    role_info = profile_runtime_info(target, state, errors)
    runtime_notes: list[str] = []
    if args.runtime_check and not errors:
        runtime_notes = run_runtime_check(target, role_info, errors)

    if errors:
        print("Foundry verification failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Foundry verification passed: {target}")
    if args.runtime_check:
        print("Runtime check:")
        for note in runtime_notes:
            print(f"- {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
