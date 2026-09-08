#!/usr/bin/env python3
from __future__ import annotations

import sys

if sys.version_info < (3, 11):
    print(
        f"ERROR: Codex Agent Foundry requires Python 3.11+ (found {sys.version_info.major}.{sys.version_info.minor}). "
        "Ubuntu 22.04 ships Python 3.10 by default; run this installer with Python 3.11 or newer.",
        file=sys.stderr,
    )
    raise SystemExit(2)

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

VERSION = 1
RUNTIME_VERSION = "1"
DEFAULT_CONCURRENCY = 4
START = "<!-- codex-agent-foundry:start -->"
END = "<!-- codex-agent-foundry:end -->"
MANAGED = "# managed-by: codex-agent-foundry"
SKILL_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = SKILL_ROOT / "assets" / "project"
RUNTIME_FILES = (
    "AGENTS.fragment.md",
    ".codex/config.toml",
    ".codex/agents/repo_explorer.toml",
    ".codex/agents/reviewer.toml",
)

Action = Literal["create", "update", "delete", "backup", "unchanged", "conflict"]


@dataclass(frozen=True)
class Step:
    action: Action
    path: Path
    detail: str
    content: bytes | None = None
    expected_before: bytes | None = None
    mode: int | None = None

    @property
    def mutates(self) -> bool:
        return self.action in {"create", "update", "delete", "backup"}


@dataclass
class Plan:
    target: Path
    steps: list[Step] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def blocked(self) -> bool:
        return any(s.action == "conflict" for s in self.steps)


class InstallError(RuntimeError):
    pass


def read_bytes(path: Path) -> bytes | None:
    if path.is_symlink():
        raise InstallError(f"{path}: symlink targets are not modified by Foundry")
    if path.exists() and not path.is_file():
        raise InstallError(f"{path}: expected a regular file")
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise InstallError(f"{path}: cannot read managed file: {exc}") from exc


def read_text(path: Path) -> str:
    data = read_bytes(path)
    if data is None:
        return ""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InstallError(f"{path}: managed text file is not valid UTF-8") from exc


def reject_managed_symlink_paths(target: Path) -> None:
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
            raise InstallError(f"{path}: symlink paths are not modified by Foundry")
        if path.exists():
            if rel in directory_paths and not path.is_dir():
                raise InstallError(f"{path}: expected a directory")
            if rel not in directory_paths and not path.is_file():
                raise InstallError(f"{path}: expected a regular file")


def file_mode(path: Path) -> int | None:
    try:
        return path.stat().st_mode & 0o7777
    except FileNotFoundError:
        return None


def sha256(data: bytes | None) -> str | None:
    return hashlib.sha256(data).hexdigest() if data is not None else None


def runtime_sha256() -> str:
    digest = hashlib.sha256()
    for rel in sorted(RUNTIME_FILES):
        data = read_bytes(ASSET_ROOT / rel)
        if data is None:
            raise InstallError(f"missing bundled runtime file: {ASSET_ROOT / rel}")
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(data)
        digest.update(b"\0")
    return digest.hexdigest()


def source_revision() -> str:
    repo_root = SKILL_ROOT.parents[2]
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    revision = result.stdout.strip()
    return revision if result.returncode == 0 and re.fullmatch(r"[0-9a-fA-F]{7,64}", revision) else "unknown"


def atomic_write(path: Path, content: bytes, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    old_mode = file_mode(path)
    final_mode = mode if mode is not None else (old_mode if old_mode is not None else 0o644)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_name, final_mode)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def managed_block() -> str:
    fragment = read_text(ASSET_ROOT / "AGENTS.fragment.md").strip()
    if not fragment:
        raise InstallError("bundled AGENTS.fragment.md is missing or empty")
    return f"{START}\n{fragment}\n{END}"


def marker_bounds(text: str, path: Path) -> tuple[int, int] | None:
    start_count = text.count(START)
    end_count = text.count(END)
    if start_count == 0 and end_count == 0:
        return None
    if start_count != 1 or end_count != 1:
        raise InstallError(f"{path}: malformed Foundry managed block markers")
    start = text.index(START)
    end = text.index(END)
    if start >= end:
        raise InstallError(f"{path}: Foundry managed block markers are reversed")
    return start, end + len(END)


def desired_agents_md(target: Path) -> tuple[Path, bytes, str]:
    path = target / "AGENTS.md"
    old = read_text(path)
    block = managed_block()
    bounds = marker_bounds(old, path)
    if bounds:
        start, end = bounds
        head = old[:start].rstrip()
        tail = old[end:].strip()
        new = (head + "\n\n" if head else "") + block
        if tail:
            new += "\n\n" + tail
        new += "\n"
        detail = "update managed Foundry block"
    else:
        prefix = old.rstrip()
        new = (prefix + "\n\n" if prefix else "") + block + "\n"
        detail = "append managed Foundry block" if old else "create with managed Foundry block"
    return path, new.encode(), detail


def desired_agents_md_without_foundry(target: Path) -> tuple[Path, bytes | None, str]:
    path = target / "AGENTS.md"
    old = read_text(path)
    bounds = marker_bounds(old, path)
    if not bounds:
        return path, read_bytes(path), "Foundry managed block already absent"
    start, end = bounds
    head = old[:start].rstrip()
    tail = old[end:].strip()
    if head and tail:
        new = head + "\n\n" + tail + "\n"
    elif head:
        new = head + "\n"
    elif tail:
        new = tail + "\n"
    else:
        new = ""
    return path, new.encode() if new else None, "remove Foundry managed block"


def find_agents_section(lines: list[str]) -> tuple[int, int] | None:
    start = None
    header = re.compile(r"^\s*\[\s*agents\s*\]\s*(?:#.*)?$")
    any_table = re.compile(r"^\s*\[\[?.+\]?\]\s*(?:#.*)?$")
    for i, line in enumerate(lines):
        if start is None and header.match(line):
            start = i
            continue
        if start is not None and i > start and any_table.match(line):
            return start, i
    return (start, len(lines)) if start is not None else None


def validate_concurrency_value(path: Path, value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise InstallError(f"{path}: agents.max_concurrent_threads_per_session must be an integer >= 1")
    return value


def desired_config(target: Path) -> tuple[Path, bytes, bool, str]:
    path = target / ".codex" / "config.toml"
    old = read_text(path)
    if old:
        try:
            parsed = tomllib.loads(old)
        except tomllib.TOMLDecodeError as exc:
            raise InstallError(f"{path}: existing TOML is invalid: {exc}") from exc
    else:
        parsed = {}
    agents = parsed.get("agents")
    if agents is not None and not isinstance(agents, dict):
        raise InstallError(f"{path}: [agents] is not a TOML table")
    if isinstance(agents, dict) and "max_concurrent_threads_per_session" in agents:
        validate_concurrency_value(path, agents["max_concurrent_threads_per_session"])
        return path, old.encode(), False, "preserve existing concurrency value"
    lines = old.splitlines()
    section = find_agents_section(lines)
    key_line = f"max_concurrent_threads_per_session = {DEFAULT_CONCURRENCY}"
    if section is None and isinstance(agents, dict):
        if re.search(r"(?m)^\s*agents\s*=\s*\{", old):
            raise InstallError(f"{path}: inline `agents = {{...}}` table cannot be safely merged")
        first_table = next((i for i, line in enumerate(lines) if re.match(r"^\s*\[", line)), len(lines))
        lines.insert(first_table, "agents." + key_line)
        new = "\n".join(lines).rstrip() + "\n"
        detail = "add missing concurrency setting using existing dotted agents table"
    elif section is None:
        if read_bytes(path) is None:
            bundled = read_text(ASSET_ROOT / ".codex" / "config.toml")
            try:
                tomllib.loads(bundled)
            except tomllib.TOMLDecodeError as exc:
                raise InstallError(f"bundled config is invalid TOML: {exc}") from exc
            new = bundled
            detail = "create Foundry project config"
        else:
            first_table = next((i for i, line in enumerate(lines) if re.match(r"^\s*\[", line)), len(lines))
            lines.insert(first_table, "agents." + key_line)
            new = "\n".join(lines).rstrip() + "\n"
            detail = "add missing concurrency setting using dotted key"
    else:
        start, _ = section
        lines.insert(start + 1, key_line)
        new = "\n".join(lines).rstrip() + "\n"
        detail = "add missing concurrency setting to existing [agents]"
    try:
        tomllib.loads(new)
    except tomllib.TOMLDecodeError as exc:
        raise InstallError(f"{path}: merged TOML would be invalid: {exc}") from exc
    return path, new.encode(), True, detail


def remove_managed_concurrency(target: Path, state: dict[str, object]) -> tuple[Path, bytes | None, str]:
    path = target / ".codex" / "config.toml"
    old = read_text(path)
    if not old or not bool(state.get("concurrency_added")):
        return path, read_bytes(path), "preserve config; concurrency was not Foundry-managed"
    try:
        parsed = tomllib.loads(old)
    except tomllib.TOMLDecodeError as exc:
        raise InstallError(f"{path}: existing TOML is invalid: {exc}") from exc
    value = parsed.get("agents", {}).get("max_concurrent_threads_per_session")
    if value != DEFAULT_CONCURRENCY:
        return path, old.encode(), "preserve config; managed concurrency value was changed by user"
    lines = old.splitlines()
    key_patterns = [
        re.compile(r"^\s*max_concurrent_threads_per_session\s*=\s*4\s*(?:#.*)?$"),
        re.compile(r"^\s*agents\.max_concurrent_threads_per_session\s*=\s*4\s*(?:#.*)?$"),
    ]
    removed = False
    out: list[str] = []
    section = find_agents_section(lines)
    for i, line in enumerate(lines):
        in_agents = section is not None and section[0] < i < section[1]
        if (in_agents and key_patterns[0].match(line)) or key_patterns[1].match(line):
            removed = True
            continue
        out.append(line)
    if not removed:
        raise InstallError(f"{path}: could not safely locate the Foundry-managed concurrency key")
    new = "\n".join(out).rstrip()
    if bool(state.get("config_created")) and new.strip() == "[agents]":
        new = ""
    elif new:
        new += "\n"
    try:
        tomllib.loads(new) if new else {}
    except tomllib.TOMLDecodeError as exc:
        raise InstallError(f"{path}: uninstall would produce invalid TOML: {exc}") from exc
    desired = new.encode() if new else (None if bool(state.get("config_created")) else b"")
    return path, desired, "remove Foundry-managed concurrency setting"


def is_foundry_managed(content: str) -> bool:
    return any(line.strip() == MANAGED for line in content.splitlines()[:5])


def default_profile(name: str) -> str:
    path = ASSET_ROOT / ".codex" / "agents" / name
    content = read_text(path)
    if not content:
        raise InstallError(f"missing bundled profile: {path}")
    try:
        tomllib.loads(content)
    except tomllib.TOMLDecodeError as exc:
        raise InstallError(f"bundled profile is invalid TOML: {path}: {exc}") from exc
    if not is_foundry_managed(content):
        raise InstallError(f"bundled profile is missing Foundry management marker: {path}")
    return content


def set_profile_model(content: str, model: str) -> str:
    if not model.strip():
        raise InstallError("model override must not be empty")
    new, count = re.subn(r'(?m)^model\s*=\s*"[^"]*"\s*$', f'model = {json.dumps(model)}', content, count=1)
    if count != 1:
        raise InstallError("bundled profile does not contain exactly one model assignment")
    try:
        tomllib.loads(new)
    except tomllib.TOMLDecodeError as exc:
        raise InstallError(f"model override would produce invalid profile TOML: {exc}") from exc
    return new


def bundled_profile_info(name: str) -> tuple[str, str]:
    parsed = tomllib.loads(default_profile(name))
    model = parsed.get("model")
    effort = parsed.get("model_reasoning_effort")
    if not isinstance(model, str) or not model.strip():
        raise InstallError(f"bundled profile {name} has an invalid model")
    if not isinstance(effort, str) or not effort.strip():
        raise InstallError(f"bundled profile {name} has an invalid model_reasoning_effort")
    return model, effort


def bundled_profile_model(name: str) -> str:
    return bundled_profile_info(name)[0]


def validate_state(path: Path, payload: dict[str, object]) -> None:
    required = {"version", "managed_agents", "agents_md_markers", "concurrency_added", "config_created", "models"}
    missing = sorted(required - payload.keys())
    if missing:
        raise InstallError(f"{path}: Foundry state is missing required fields: {', '.join(missing)}")
    if payload.get("version") != VERSION:
        raise InstallError(f"{path}: unsupported Foundry state version {payload.get('version')!r}; expected {VERSION}")
    if payload.get("managed_agents") != ["repo_explorer.toml", "reviewer.toml"]:
        raise InstallError(f"{path}: unexpected managed_agents in Foundry state")
    if payload.get("agents_md_markers") != [START, END]:
        raise InstallError(f"{path}: unexpected AGENTS.md markers in Foundry state")
    for key in ("concurrency_added", "config_created"):
        if not isinstance(payload.get(key), bool):
            raise InstallError(f"{path}: state field {key} must be boolean")
    models = payload.get("models")
    if not isinstance(models, dict) or set(models) != {"repo_explorer", "reviewer"}:
        raise InstallError(f"{path}: state field models has unexpected role keys")
    if not all(isinstance(v, str) and v.strip() for v in models.values()):
        raise InstallError(f"{path}: state model values must be non-empty strings")
    if "runtime_version" in payload and (not isinstance(payload["runtime_version"], str) or not payload["runtime_version"]):
        raise InstallError(f"{path}: runtime_version must be a non-empty string")
    if "source_revision" in payload and (not isinstance(payload["source_revision"], str) or not payload["source_revision"]):
        raise InstallError(f"{path}: source_revision must be a non-empty string")
    if "runtime_sha256" in payload and not re.fullmatch(r"[0-9a-f]{64}", str(payload["runtime_sha256"])):
        raise InstallError(f"{path}: runtime_sha256 must be a 64-character lowercase hex digest")


def read_state(target: Path, required: bool = False) -> dict[str, object] | None:
    path = target / ".codex" / ".agent-foundry.json"
    data = read_bytes(path)
    if data is None:
        if required:
            raise InstallError(f"{path}: Foundry is not installed (state file missing)")
        return None
    try:
        payload = json.loads(data)
    except Exception as exc:
        raise InstallError(f"{path}: state file is invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise InstallError(f"{path}: state file must contain a JSON object")
    validate_state(path, payload)
    return payload


def backup_path(path: Path, reserved: set[Path]) -> Path:
    candidate = path.with_name(path.name + ".foundry-backup")
    n = 2
    while candidate.exists() or candidate.is_symlink() or candidate in reserved:
        candidate = path.with_name(path.name + f".foundry-backup-{n}")
        n += 1
    return candidate


def step_for_content(
    path: Path,
    desired: bytes | None,
    detail: str,
    *,
    action_if_absent: Action = "create",
    unchanged_detail: str | None = None,
) -> Step:
    old = read_bytes(path)
    if desired == old:
        return Step("unchanged", path, unchanged_detail or detail, expected_before=old)
    if desired is None:
        return Step("delete", path, detail, expected_before=old)
    action: Action = "update" if old is not None else action_if_absent
    return Step(action, path, detail, content=desired, expected_before=old, mode=file_mode(path))


def build_install_plan(target: Path, *, force: bool = False, explorer_model: str | None = None, reviewer_model: str | None = None) -> Plan:
    target = target.resolve()
    if not target.exists() or not target.is_dir():
        raise InstallError(f"target directory does not exist: {target}")
    reject_managed_symlink_paths(target)
    prior_state = read_state(target)
    prior_models = prior_state.get("models", {}) if isinstance(prior_state, dict) else {}
    if not isinstance(prior_models, dict):
        prior_models = {}

    explorer_default, explorer_effort = bundled_profile_info("repo_explorer.toml")
    reviewer_default, reviewer_effort = bundled_profile_info("reviewer.toml")
    explorer_model = explorer_model or str(prior_models.get("repo_explorer") or explorer_default)
    reviewer_model = reviewer_model or str(prior_models.get("reviewer") or reviewer_default)

    plan = Plan(target)
    agents_path, agents_content, agents_detail = desired_agents_md(target)
    plan.steps.append(step_for_content(agents_path, agents_content, agents_detail, unchanged_detail="managed block already current"))
    config_path, config_content, concurrency_added_now, config_detail = desired_config(target)
    plan.steps.append(step_for_content(config_path, config_content, config_detail, unchanged_detail="project config already current"))

    reserved: set[Path] = set()
    selected_models = {"repo_explorer": explorer_model, "reviewer": reviewer_model}
    for filename, model in (("repo_explorer.toml", explorer_model), ("reviewer.toml", reviewer_model)):
        dst = target / ".codex" / "agents" / filename
        old = read_bytes(dst)
        desired = set_profile_model(default_profile(filename), model).encode()
        if old == desired:
            plan.steps.append(Step("unchanged", dst, "profile already current", expected_before=old))
            continue
        if old is not None and not is_foundry_managed(old.decode("utf-8", errors="replace")):
            if not force:
                plan.steps.append(Step("conflict", dst, "foreign same-name profile; explicit --force required", expected_before=old))
                continue
            backup = backup_path(dst, reserved)
            reserved.add(backup)
            plan.steps.append(Step("backup", backup, f"back up foreign {filename} before replacement", content=old, expected_before=None, mode=file_mode(dst)))
        detail = "update Foundry-managed profile" if old is not None else "install Foundry-managed profile"
        plan.steps.append(Step("update" if old is not None else "create", dst, detail, content=desired, expected_before=old, mode=file_mode(dst)))

    prior_added = bool(prior_state.get("concurrency_added")) if isinstance(prior_state, dict) else False
    concurrency_added = prior_added or concurrency_added_now
    prior_config_created = bool(prior_state.get("config_created")) if isinstance(prior_state, dict) else False
    config_created = prior_config_created or (read_bytes(config_path) is None and concurrency_added_now)
    provenance = {
        "runtime_version": RUNTIME_VERSION,
        "source_revision": source_revision(),
        "runtime_sha256": runtime_sha256(),
    }
    state = {
        "version": VERSION,
        "managed_agents": ["repo_explorer.toml", "reviewer.toml"],
        "agents_md_markers": [START, END],
        "concurrency_added": concurrency_added,
        "config_created": config_created,
        "models": selected_models,
        **provenance,
    }
    state_path = target / ".codex" / ".agent-foundry.json"
    state_content = (json.dumps(state, indent=2, sort_keys=True) + "\n").encode()
    plan.steps.append(step_for_content(state_path, state_content, "record Foundry installation state", unchanged_detail="Foundry installation state already current"))
    plan.metadata.update({
        "mode": "install",
        "models": selected_models,
        "roles": {
            "repo_explorer": {"model": explorer_model, "reasoning_effort": explorer_effort},
            "reviewer": {"model": reviewer_model, "reasoning_effort": reviewer_effort},
        },
        "concurrency_added": concurrency_added,
        "config_created": config_created,
        **provenance,
    })
    return plan


def build_uninstall_plan(target: Path) -> Plan:
    target = target.resolve()
    if not target.exists() or not target.is_dir():
        raise InstallError(f"target directory does not exist: {target}")
    reject_managed_symlink_paths(target)
    state = read_state(target, required=True)
    assert state is not None
    plan = Plan(target)
    agents_path, desired_agents, detail = desired_agents_md_without_foundry(target)
    plan.steps.append(step_for_content(agents_path, desired_agents, detail, unchanged_detail="Foundry managed block already absent"))
    config_path, desired_config_bytes, detail = remove_managed_concurrency(target, state)
    plan.steps.append(step_for_content(config_path, desired_config_bytes, detail, unchanged_detail=detail))
    managed = state.get("managed_agents")
    if not isinstance(managed, list) or not all(isinstance(x, str) for x in managed):
        raise InstallError("state file has invalid managed_agents")
    models = state.get("models") if isinstance(state.get("models"), dict) else {}
    model_keys = {"repo_explorer.toml": "repo_explorer", "reviewer.toml": "reviewer"}
    for filename in managed:
        path = target / ".codex" / "agents" / filename
        old = read_bytes(path)
        if old is None:
            plan.steps.append(Step("unchanged", path, "managed profile already absent", expected_before=None))
            continue
        if not is_foundry_managed(old.decode("utf-8", errors="replace")):
            plan.steps.append(Step("conflict", path, "profile is no longer Foundry-managed; refusing to delete", expected_before=old))
            continue
        expected_model = str(models.get(model_keys[filename]) or bundled_profile_model(filename))
        expected = set_profile_model(default_profile(filename), expected_model).encode()
        if old != expected:
            plan.steps.append(Step("conflict", path, "Foundry-managed profile has drifted; refusing to delete modified content", expected_before=old))
            continue
        plan.steps.append(Step("delete", path, "remove Foundry-managed profile", expected_before=old))
    state_path = target / ".codex" / ".agent-foundry.json"
    plan.steps.append(step_for_content(state_path, None, "remove Foundry installation state", unchanged_detail="Foundry installation state already absent"))
    plan.metadata["mode"] = "uninstall"
    return plan


def _check_precondition(step: Step) -> None:
    current = read_bytes(step.path)
    if current != step.expected_before:
        raise InstallError(f"{step.path}: changed after plan was built (expected sha256={sha256(step.expected_before)}, current sha256={sha256(current)})")


def apply_plan(plan: Plan) -> None:
    if plan.blocked:
        raise InstallError("plan contains conflicts; nothing was written")
    reject_managed_symlink_paths(plan.target)
    mutating = [s for s in plan.steps if s.mutates]
    snapshots: dict[Path, tuple[bytes | None, int | None]] = {s.path: (read_bytes(s.path), file_mode(s.path)) for s in mutating}
    candidate_dirs: set[Path] = set()
    for step in mutating:
        parent = step.path.parent
        while parent != plan.target and plan.target in parent.parents:
            candidate_dirs.add(parent)
            parent = parent.parent
    existing_dirs = {d for d in candidate_dirs if d.exists()}
    applied: list[Step] = []
    try:
        for step in mutating:
            reject_managed_symlink_paths(plan.target)
            _check_precondition(step)
            if step.action in {"create", "update", "backup"}:
                if step.content is None:
                    raise InstallError(f"{step.path}: planned {step.action} has no content")
                atomic_write(step.path, step.content, step.mode)
            elif step.action == "delete":
                try:
                    step.path.unlink()
                except FileNotFoundError:
                    pass
            applied.append(step)
    except BaseException as exc:
        rollback_errors: list[str] = []
        for step in reversed(applied):
            before, mode = snapshots[step.path]
            try:
                if before is None:
                    try:
                        step.path.unlink()
                    except FileNotFoundError:
                        pass
                else:
                    atomic_write(step.path, before, mode)
            except Exception as rollback_exc:
                rollback_errors.append(f"{step.path}: {rollback_exc}")
        for directory in sorted(candidate_dirs - existing_dirs, key=lambda p: len(p.parts), reverse=True):
            try:
                directory.rmdir()
            except (FileNotFoundError, OSError):
                pass
        suffix = f"; rollback errors: {'; '.join(rollback_errors)}" if rollback_errors else ""
        if isinstance(exc, InstallError):
            raise InstallError(f"{exc}{suffix}") from exc
        raise InstallError(f"apply failed: {exc}{suffix}") from exc


def print_plan(plan: Plan, *, label: str) -> None:
    print(f"{label}: {plan.target}")
    roles = plan.metadata.get("roles")
    if isinstance(roles, dict):
        print("Selected agents:")
        for role in ("repo_explorer", "reviewer"):
            info = roles.get(role)
            if isinstance(info, dict):
                print(f"- {role}: {info.get('model')} / {info.get('reasoning_effort')}")
    for step in plan.steps:
        try:
            rel = step.path.resolve().relative_to(plan.target)
        except ValueError:
            rel = step.path
        print(f"- {step.action:9} {rel}: {step.detail}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install, update, inspect, or uninstall Codex Agent Foundry.")
    parser.add_argument("target", nargs="?", default=".", help="target repository (default: current directory)")
    parser.add_argument("--check", action="store_true", help="show the complete plan without writing")
    parser.add_argument("--force", action="store_true", help="back up and replace foreign same-name agent profiles")
    parser.add_argument("--uninstall", action="store_true", help="remove Foundry-managed runtime state")
    parser.add_argument("--explorer-model", help="override repo_explorer model; preserved in Foundry state")
    parser.add_argument("--reviewer-model", help="override reviewer model; preserved in Foundry state")
    args = parser.parse_args()
    target = Path(args.target)
    try:
        if args.uninstall:
            if args.force or args.explorer_model or args.reviewer_model:
                raise InstallError("--uninstall cannot be combined with --force or model overrides")
            plan = build_uninstall_plan(target)
        else:
            plan = build_install_plan(target, force=args.force, explorer_model=args.explorer_model, reviewer_model=args.reviewer_model)
    except InstallError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.check:
        print_plan(plan, label="PLAN")
        return 3 if plan.blocked else 0
    if plan.blocked:
        print_plan(plan, label="BLOCKED PLAN")
        print("No files were changed.")
        return 3
    try:
        apply_plan(plan)
    except InstallError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print_plan(plan, label="APPLIED")
    if not args.uninstall:
        print("Start a new Codex session in this project to load Foundry.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
