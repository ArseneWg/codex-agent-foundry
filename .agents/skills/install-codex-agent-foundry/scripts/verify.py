#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        print(
            "ERROR: Codex Agent Foundry requires Python 3.11+ or Python 3.10 with the 'tomli' package. "
            "On Python 3.10 run: python3 -m pip install tomli",
            file=sys.stderr,
        )
        raise SystemExit(2)

VERSION = 1
START = "<!-- codex-agent-foundry:start -->"
END = "<!-- codex-agent-foundry:end -->"
MANAGED = "# managed-by: codex-agent-foundry"
SKILL_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = SKILL_ROOT / "assets" / "project"
RUNTIME_MANIFEST = "manifest.json"


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


def runtime_manifest(errors: list[str] | None = None) -> tuple[str, list[str]] | None:
    path = ASSET_ROOT / RUNTIME_MANIFEST
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        if errors is not None:
            errors.append(f"bundled runtime manifest is invalid: {exc}")
            return None
        raise
    if not isinstance(payload, dict):
        if errors is not None:
            errors.append("bundled runtime manifest must contain a JSON object")
            return None
        raise ValueError("runtime manifest must contain a JSON object")
    version = payload.get("runtime_version")
    files = payload.get("files")
    if not isinstance(version, str) or not version.strip():
        if errors is not None:
            errors.append("bundled runtime manifest has invalid runtime_version")
            return None
        raise ValueError("invalid runtime_version")
    if not isinstance(files, list) or not files or not all(isinstance(x, str) and x.strip() for x in files):
        if errors is not None:
            errors.append("bundled runtime manifest has invalid files")
            return None
        raise ValueError("invalid files")
    if len(set(files)) != len(files) or RUNTIME_MANIFEST in files:
        if errors is not None:
            errors.append("bundled runtime manifest contains invalid or duplicate file entries")
            return None
        raise ValueError("invalid file entries")
    return version, files


def bundled_runtime_sha256(errors: list[str] | None = None) -> str | None:
    manifest = runtime_manifest(errors)
    if manifest is None:
        return None
    _, files = manifest
    digest = hashlib.sha256()
    for rel in (RUNTIME_MANIFEST, *files):
        path = ASSET_ROOT / rel
        try:
            data = path.read_bytes()
        except OSError as exc:
            if errors is not None:
                errors.append(f"bundled runtime file cannot be read: {rel}: {exc}")
                return None
            raise
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(data)
        digest.update(b"\0")
    return digest.hexdigest()


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


def load_state(target: Path, errors: list[str], warnings: list[str]) -> dict[str, object] | None:
    state = target / ".codex" / ".agent-foundry.json"
    if not state.exists():
        errors.append(".codex/.agent-foundry.json is missing")
        return None
    try:
        payload = json.loads(state.read_text(encoding="utf-8"))
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
        errors.append(f"installed Foundry state schema version is not {VERSION}")
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

    provenance = {"runtime_version", "runtime_sha256", "source_revision"}
    present = provenance.intersection(payload)
    if not present:
        warnings.append("Foundry state predates runtime provenance; re-run the installer to record runtime version/hash/source revision")
    elif present != provenance:
        errors.append(f"Foundry state provenance is incomplete: {', '.join(sorted(provenance - present))}")
    else:
        runtime_version = payload.get("runtime_version")
        runtime_digest = payload.get("runtime_sha256")
        revision = payload.get("source_revision")
        if not isinstance(runtime_version, str) or not runtime_version.strip():
            errors.append("Foundry state runtime_version must be a non-empty string")
        if not isinstance(runtime_digest, str) or re.fullmatch(r"[0-9a-f]{64}", runtime_digest) is None:
            errors.append("Foundry state runtime_sha256 must be a lowercase SHA-256 hex digest")
        if revision is not None and (not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{40,64}", revision) is None):
            errors.append("Foundry state source_revision must be a Git commit SHA or null")
    return payload


def _json_strings(value: object) -> set[str]:
    result: set[str] = set()
    if isinstance(value, str):
        result.add(value)
    elif isinstance(value, list):
        for item in value:
            result.update(_json_strings(item))
    elif isinstance(value, dict):
        for item in value.values():
            result.update(_json_strings(item))
    return result


def _short_command_error(result: subprocess.CompletedProcess[str]) -> str:
    text = (result.stderr or result.stdout or "unknown error").strip().replace("\n", " ")
    return text[:500]


def runtime_check(
    target: Path,
    state: dict[str, object] | None,
    errors: list[str],
    warnings: list[str],
) -> list[str]:
    details: list[str] = []
    codex = shutil.which("codex")
    if codex is None:
        errors.append("runtime check: codex is not in PATH")
        return details
    details.append(f"codex: {codex}")

    try:
        version_result = subprocess.run(
            [codex, "--version"],
            cwd=target,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        errors.append(f"runtime check: failed to run codex --version: {exc}")
        return details
    if version_result.returncode != 0:
        errors.append(f"runtime check: codex --version failed: {_short_command_error(version_result)}")
        return details
    version_text = (version_result.stdout or version_result.stderr).strip()
    details.append(f"version: {version_text or 'unknown'}")

    command = [codex, "--strict-config", "-C", str(target), "debug", "models", "--bundled"]
    try:
        catalog_result = subprocess.run(
            command,
            cwd=target,
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        errors.append(f"runtime check: failed to run Codex strict-config/model-catalog check: {exc}")
        return details
    if catalog_result.returncode != 0:
        errors.append(
            "runtime check: Codex strict-config/model-catalog check failed: "
            + _short_command_error(catalog_result)
        )
        return details
    details.append("strict config: passed")

    try:
        catalog = json.loads(catalog_result.stdout)
    except json.JSONDecodeError as exc:
        errors.append(f"runtime check: codex debug models --bundled did not return valid JSON: {exc}")
        return details
    catalog_strings = _json_strings(catalog)

    state_models = state.get("models", {}) if isinstance(state, dict) else {}
    if not isinstance(state_models, dict):
        state_models = {}
    for filename, role in (("repo_explorer.toml", "repo_explorer"), ("reviewer.toml", "reviewer")):
        path = target / ".codex" / "agents" / filename
        try:
            parsed = tomllib.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"runtime check: cannot inspect {filename}: {exc}")
            continue
        model = parsed.get("model") or state_models.get(role)
        effort = parsed.get("model_reasoning_effort")
        if not isinstance(model, str) or not model.strip():
            errors.append(f"runtime check: {role} has no valid model")
            continue
        if not isinstance(effort, str) or not effort.strip():
            effort = "unknown"
        present = model in catalog_strings
        details.append(f"{role}: {model} / {effort} (bundled catalog: {'present' if present else 'not found'})")
        if not present:
            warnings.append(
                f"{role} model {model!r} was not found in this Codex binary's bundled model catalog; "
                "a refreshed/remote catalog may differ"
            )

    warnings.append(
        "Account model availability is not verified by --runtime-check; start a new authenticated Codex session to confirm access."
    )
    return details


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Codex Agent Foundry installation.")
    parser.add_argument("target", nargs="?", default=".")
    parser.add_argument(
        "--runtime-check",
        action="store_true",
        help="also validate local Codex CLI, strict config parsing, and bundled model catalog",
    )
    args = parser.parse_args()
    target = Path(args.target).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    runtime_details: list[str] = []

    errors.extend(managed_path_errors(target))
    if errors:
        print("Foundry verification failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    state = load_state(target, errors, warnings)

    manifest = runtime_manifest(errors)
    runtime_digest = bundled_runtime_sha256(errors)
    if manifest is not None and isinstance(state, dict) and "runtime_version" in state:
        current_version, _ = manifest
        if state.get("runtime_version") != current_version:
            errors.append(
                f"installed runtime_version {state.get('runtime_version')!r} does not match verifier runtime {current_version!r}"
            )
        if runtime_digest is not None and state.get("runtime_sha256") != runtime_digest:
            errors.append("installed runtime_sha256 does not match this verifier's bundled runtime")

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
            parsed = tomllib.loads(config.read_text(encoding="utf-8"))
            value = parsed.get("agents", {}).get("max_concurrent_threads_per_session")
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                errors.append("Foundry concurrency setting must be an integer >= 1")
        except Exception as exc:
            errors.append(f".codex/config.toml is invalid: {exc}")

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

    if args.runtime_check and not errors:
        runtime_details = runtime_check(target, state, errors, warnings)

    if runtime_details:
        print("Runtime check:")
        for detail in runtime_details:
            print(f"- {detail}")

    if errors:
        print("Foundry verification failed:")
        for error in errors:
            print(f"- {error}")
        if warnings:
            print("Warnings:")
            for warning in warnings:
                print(f"- {warning}")
        return 1

    print(f"Foundry verification passed: {target}")
    if isinstance(state, dict) and "runtime_version" in state:
        print(
            "Runtime provenance: "
            f"version={state.get('runtime_version')} "
            f"sha256={state.get('runtime_sha256')} "
            f"source_revision={state.get('source_revision') or 'unavailable'}"
        )
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())