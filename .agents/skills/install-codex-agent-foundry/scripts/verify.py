#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
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
    }
    missing = sorted(required - payload.keys())
    if missing:
        errors.append(f"Foundry state is missing required fields: {', '.join(missing)}")
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
    return payload

def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Codex Agent Foundry installation.")
    parser.add_argument("target", nargs="?", default=".")
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

    models = state.get("models", {}) if isinstance(state, dict) else {}
    if not isinstance(models, dict):
        models = {}
    keys = {
        "repo_explorer.toml": "repo_explorer",
        "reviewer.toml": "reviewer",
    }
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
            tomllib.loads(actual)
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

    if errors:
        print("Foundry verification failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Foundry verification passed: {target}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
