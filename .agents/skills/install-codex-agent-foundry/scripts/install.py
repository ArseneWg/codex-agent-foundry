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
import copy
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

VERSION = 3
LEGACY_VERSION = 1
PREVIOUS_VERSION = 2
SUPPORTED_VERSIONS = {LEGACY_VERSION, PREVIOUS_VERSION, VERSION}
RUNTIME_VERSION = "3"
DEFAULT_CONCURRENCY = 4
START = "<!-- codex-agent-foundry:start -->"
END = "<!-- codex-agent-foundry:end -->"
MANAGED = "# managed-by: codex-agent-foundry"
SKILL_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = SKILL_ROOT / "assets" / "project"
LEGACY_ROOT = SKILL_ROOT / "assets" / "legacy"
RUNTIME_FILES = (
    "AGENTS.fragment.md",
    ".codex/config.toml",
    ".codex/agents/explorer.toml",
    ".codex/agents/reviewer.toml",
    ".codex/agents/verifier.toml",
    ".codex/foundry-verifier-run.py",
)
V1_MANAGED_AGENTS = ["repo_explorer.toml", "reviewer.toml"]
V2_MANAGED_AGENTS = ["explorer.toml", "reviewer.toml"]
CURRENT_MANAGED_AGENTS = ["explorer.toml", "reviewer.toml", "verifier.toml"]
MANAGED_AGENTS_BY_VERSION = {
    LEGACY_VERSION: V1_MANAGED_AGENTS,
    PREVIOUS_VERSION: V2_MANAGED_AGENTS,
    VERSION: CURRENT_MANAGED_AGENTS,
}
MODEL_KEYS_BY_VERSION = {
    LEGACY_VERSION: {"repo_explorer", "reviewer"},
    PREVIOUS_VERSION: {"explorer", "reviewer"},
    VERSION: {"explorer", "reviewer", "verifier"},
}
VERIFIER_RUNNER = ".codex/foundry-verifier-run.py"
CURRENT_MANAGED_PATHS = [
    ".codex/agents/explorer.toml",
    ".codex/agents/reviewer.toml",
    ".codex/agents/verifier.toml",
    VERIFIER_RUNNER,
]
OBSOLETE_REVIEWER_MODEL = "gpt-5.6"

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
        return any(step.action == "conflict" for step in self.steps)


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


def file_mode(path: Path) -> int | None:
    try:
        return path.stat().st_mode & 0o7777
    except FileNotFoundError:
        return None


def sha256(data: bytes | None) -> str | None:
    return hashlib.sha256(data).hexdigest() if data is not None else None


def is_foundry_managed(content: str) -> bool:
    return any(line.strip() == MANAGED for line in content.splitlines()[:5])


def reject_managed_symlink_paths(
    target: Path,
    *,
    profile_names: list[str] | tuple[str, ...] | None = None,
    include_runner: bool = True,
) -> None:
    directory_paths = {".codex", ".codex/agents"}
    paths = [
        ".codex",
        ".codex/agents",
        "AGENTS.md",
        ".codex/config.toml",
        ".codex/.agent-foundry.json",
    ]
    if include_runner:
        paths.append(VERIFIER_RUNNER)
    for name in CURRENT_MANAGED_AGENTS if profile_names is None else profile_names:
        paths.append(f".codex/agents/{name}")
    for rel in paths:
        path = target / rel
        if path.is_symlink():
            raise InstallError(f"{path}: symlink paths are not modified by Foundry")
        if path.exists():
            if rel in directory_paths and not path.is_dir():
                raise InstallError(f"{path}: expected a directory")
            if rel not in directory_paths and not path.is_file():
                raise InstallError(f"{path}: expected a regular file")


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
    runtime_root = repo_root / "runtime"
    try:
        for rel in RUNTIME_FILES:
            if (runtime_root / rel).read_bytes() != (ASSET_ROOT / rel).read_bytes():
                return "unknown"
    except OSError:
        return "unknown"
    try:
        top = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--show-toplevel"],
            text=True,
            capture_output=True,
            timeout=2,
            check=False,
        )
        if top.returncode != 0 or Path(top.stdout.strip()).resolve() != repo_root.resolve():
            return "unknown"
        clean = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "diff",
                "--quiet",
                "HEAD",
                "--",
                "runtime",
                ".agents/skills/install-codex-agent-foundry/assets/project",
            ],
            timeout=2,
            check=False,
        )
        if clean.returncode != 0:
            return "unknown"
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


def _toml_structural_lines(text: str) -> set[int]:
    """Return line indexes that begin outside multiline TOML strings."""
    structural: set[int] = set()
    mode: Literal["basic", "literal"] | None = None
    for i, line in enumerate(text.splitlines()):
        if mode is None:
            structural.add(i)
        j = 0
        while j < len(line):
            if mode == "basic":
                if line.startswith('"""', j):
                    backslashes = 0
                    k = j - 1
                    while k >= 0 and line[k] == "\\":
                        backslashes += 1
                        k -= 1
                    if backslashes % 2 == 0:
                        mode = None
                        j += 3
                        continue
                j += 1
                continue
            if mode == "literal":
                if line.startswith("'''", j):
                    mode = None
                    j += 3
                    continue
                j += 1
                continue

            ch = line[j]
            if ch == "#":
                break
            if line.startswith('"""', j):
                mode = "basic"
                j += 3
                continue
            if line.startswith("'''", j):
                mode = "literal"
                j += 3
                continue
            if ch == '"':
                j += 1
                while j < len(line):
                    if line[j] == '"':
                        backslashes = 0
                        k = j - 1
                        while k >= 0 and line[k] == "\\":
                            backslashes += 1
                            k -= 1
                        if backslashes % 2 == 0:
                            j += 1
                            break
                    j += 1
                continue
            if ch == "'":
                end = line.find("'", j + 1)
                j = len(line) if end < 0 else end + 1
                continue
            j += 1
    return structural


def _toml_table_lines(text: str) -> tuple[list[str], set[int], re.Pattern[str]]:
    lines = text.splitlines()
    structural = _toml_structural_lines(text)
    any_table = re.compile(r"^\s*\[\[?.+\]?\]\s*(?:#.*)?$")
    return lines, structural, any_table


def find_agents_section(text_or_lines: str | list[str]) -> tuple[int, int] | None:
    text = text_or_lines if isinstance(text_or_lines, str) else "\n".join(text_or_lines)
    lines, structural, any_table = _toml_table_lines(text)
    header = re.compile(r"^\s*\[\s*agents\s*\]\s*(?:#.*)?$")
    start: int | None = None
    for i, line in enumerate(lines):
        if i not in structural:
            continue
        if start is None and header.match(line):
            start = i
            continue
        if start is not None and i > start and any_table.match(line):
            return start, i
    return (start, len(lines)) if start is not None else None


def _first_structural_table(text: str) -> int:
    lines, structural, any_table = _toml_table_lines(text)
    return next((i for i, line in enumerate(lines) if i in structural and any_table.match(line)), len(lines))


def validate_concurrency_value(path: Path, value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise InstallError(f"{path}: agents.max_concurrent_threads_per_session must be an integer >= 1")
    return value


def _parse_toml(path: Path, text: str, *, label: str) -> dict[str, object]:
    try:
        parsed = tomllib.loads(text) if text else {}
    except tomllib.TOMLDecodeError as exc:
        raise InstallError(f"{path}: {label} TOML is invalid: {exc}") from exc
    if not isinstance(parsed, dict):
        raise InstallError(f"{path}: {label} TOML root must be a table")
    return parsed


def desired_config(target: Path) -> tuple[Path, bytes, bool, str]:
    path = target / ".codex" / "config.toml"
    old_bytes = read_bytes(path)
    old = old_bytes.decode("utf-8") if old_bytes is not None else ""
    parsed = _parse_toml(path, old, label="existing")
    agents = parsed.get("agents")
    if agents is not None and not isinstance(agents, dict):
        raise InstallError(f"{path}: agents must be a TOML table")
    if isinstance(agents, dict) and "max_concurrent_threads_per_session" in agents:
        validate_concurrency_value(path, agents["max_concurrent_threads_per_session"])
        return path, old.encode(), False, "preserve existing concurrency value"

    if old_bytes is None:
        bundled = read_text(ASSET_ROOT / ".codex" / "config.toml")
        bundled_parsed = _parse_toml(path, bundled, label="bundled")
        expected = copy.deepcopy(parsed)
        expected.setdefault("agents", {})["max_concurrent_threads_per_session"] = DEFAULT_CONCURRENCY
        if bundled_parsed != expected:
            raise InstallError("bundled config does not contain only the expected Foundry concurrency setting")
        return path, bundled.encode(), True, "create Foundry project config"

    lines = old.splitlines()
    section = find_agents_section(old)
    key_line = f"max_concurrent_threads_per_session = {DEFAULT_CONCURRENCY}"
    if section is not None:
        lines.insert(section[0] + 1, key_line)
        detail = "add missing concurrency setting to existing [agents]"
    else:
        lines.insert(_first_structural_table(old), "agents." + key_line)
        detail = "add missing concurrency setting using top-level dotted key"
    new = "\n".join(lines).rstrip() + "\n"
    new_parsed = _parse_toml(path, new, label="merged")
    expected = copy.deepcopy(parsed)
    expected.setdefault("agents", {})["max_concurrent_threads_per_session"] = DEFAULT_CONCURRENCY
    if new_parsed != expected:
        raise InstallError(
            f"{path}: refusing config edit because parsed content would change beyond the Foundry concurrency setting"
        )
    return path, new.encode(), True, detail


def remove_managed_concurrency(target: Path, state: dict[str, object]) -> tuple[Path, bytes | None, str]:
    path = target / ".codex" / "config.toml"
    old = read_text(path)
    if not old or not bool(state.get("concurrency_added")):
        return path, read_bytes(path), "preserve config; concurrency was not Foundry-managed"
    parsed = _parse_toml(path, old, label="existing")
    agents = parsed.get("agents")
    value = agents.get("max_concurrent_threads_per_session") if isinstance(agents, dict) else None
    if value != DEFAULT_CONCURRENCY:
        return path, old.encode(), "preserve config; managed concurrency value was changed by user"

    lines, structural, _ = _toml_table_lines(old)
    section = find_agents_section(old)
    direct = re.compile(r"^\s*max_concurrent_threads_per_session\s*=\s*4\s*(?:#.*)?$")
    dotted = re.compile(r"^\s*agents\.max_concurrent_threads_per_session\s*=\s*4\s*(?:#.*)?$")
    remove_indexes: list[int] = []
    for i, line in enumerate(lines):
        if i not in structural:
            continue
        in_agents = section is not None and section[0] < i < section[1]
        if (in_agents and direct.match(line)) or dotted.match(line):
            remove_indexes.append(i)
    if len(remove_indexes) != 1:
        raise InstallError(f"{path}: could not safely locate exactly one Foundry-managed concurrency key")
    del lines[remove_indexes[0]]
    new = "\n".join(lines).rstrip()

    expected = copy.deepcopy(parsed)
    expected_agents = expected.get("agents")
    assert isinstance(expected_agents, dict)
    expected_agents.pop("max_concurrent_threads_per_session", None)

    if bool(state.get("config_created")) and new.strip() == "[agents]":
        return path, None, "remove Foundry-created project config"
    if new:
        new += "\n"
    new_parsed = _parse_toml(path, new, label="uninstall result")
    if new_parsed != expected:
        raise InstallError(
            f"{path}: refusing uninstall edit because parsed content would change beyond the Foundry concurrency setting"
        )
    desired = new.encode() if new else b""
    return path, desired, "remove Foundry-managed concurrency setting"


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


def lifecycle_profile(version: int, name: str) -> str:
    if version == VERSION:
        return default_profile(name)
    expected = MANAGED_AGENTS_BY_VERSION.get(version)
    if expected is None or name not in expected:
        raise InstallError(f"unsupported Foundry v{version} profile: {name}")
    path = LEGACY_ROOT / f"v{version}" / name
    content = read_text(path)
    if not content:
        raise InstallError(f"missing bundled Foundry v{version} lifecycle profile: {path}")
    try:
        tomllib.loads(content)
    except tomllib.TOMLDecodeError as exc:
        raise InstallError(f"bundled Foundry v{version} profile is invalid TOML: {path}: {exc}") from exc
    if not is_foundry_managed(content):
        raise InstallError(f"bundled Foundry v{version} profile is missing Foundry management marker: {path}")
    return content


def legacy_profile(name: str) -> str:
    return lifecycle_profile(LEGACY_VERSION, name)


def previous_profile(name: str) -> str:
    return lifecycle_profile(PREVIOUS_VERSION, name)


def legacy_explorer_profile() -> str:
    return legacy_profile("repo_explorer.toml")


def profile_template(name: str) -> str:
    return legacy_explorer_profile() if name == "repo_explorer.toml" else default_profile(name)


def set_profile_model(content: str, model: str) -> str:
    if not model.strip():
        raise InstallError("model override must not be empty")
    new, count = re.subn(
        r'(?m)^model\s*=\s*"[^"]*"\s*$',
        f"model = {json.dumps(model)}",
        content,
        count=1,
    )
    if count != 1:
        raise InstallError("bundled profile does not contain exactly one model assignment")
    try:
        tomllib.loads(new)
    except tomllib.TOMLDecodeError as exc:
        raise InstallError(f"model override would produce invalid profile TOML: {exc}") from exc
    return new


def bundled_profile_info(name: str) -> tuple[str, str]:
    parsed = tomllib.loads(profile_template(name))
    model = parsed.get("model")
    effort = parsed.get("model_reasoning_effort")
    if not isinstance(model, str) or not model.strip():
        raise InstallError(f"bundled profile {name} has an invalid model")
    if not isinstance(effort, str) or not effort.strip():
        raise InstallError(f"bundled profile {name} has an invalid model_reasoning_effort")
    return model, effort


def bundled_profile_model(name: str) -> str:
    return bundled_profile_info(name)[0]


def state_version(payload: dict[str, object]) -> int:
    value = payload.get("version")
    if not isinstance(value, int) or isinstance(value, bool) or value not in SUPPORTED_VERSIONS:
        supported = ", ".join(str(v) for v in sorted(SUPPORTED_VERSIONS))
        raise InstallError(f"unsupported Foundry state version {value!r}; expected one of {supported}")
    return value


def _managed_hashes(payload: dict[str, object] | None) -> dict[str, str]:
    if not isinstance(payload, dict):
        return {}
    value = payload.get("managed_sha256")
    if not isinstance(value, dict):
        return {}
    return {str(key): str(digest) for key, digest in value.items()}


def validate_state(path: Path, payload: dict[str, object]) -> None:
    base_required = {"version", "managed_agents", "agents_md_markers", "concurrency_added", "config_created", "models"}
    missing = sorted(base_required - payload.keys())
    if missing:
        raise InstallError(f"{path}: Foundry state is missing required fields: {', '.join(missing)}")
    try:
        version = state_version(payload)
    except InstallError as exc:
        raise InstallError(f"{path}: {exc}") from exc
    if version >= PREVIOUS_VERSION:
        missing = sorted({"runtime_version", "source_revision", "runtime_sha256"} - payload.keys())
        if missing:
            raise InstallError(f"{path}: Foundry v{version} state is missing provenance fields: {', '.join(missing)}")
    if payload.get("managed_agents") != MANAGED_AGENTS_BY_VERSION[version]:
        raise InstallError(f"{path}: unexpected managed_agents in Foundry state")
    if payload.get("agents_md_markers") != [START, END]:
        raise InstallError(f"{path}: unexpected AGENTS.md markers in Foundry state")
    for key in ("concurrency_added", "config_created"):
        if not isinstance(payload.get(key), bool):
            raise InstallError(f"{path}: state field {key} must be boolean")
    models = payload.get("models")
    if not isinstance(models, dict) or set(models) != MODEL_KEYS_BY_VERSION[version]:
        raise InstallError(f"{path}: state field models has unexpected role keys")
    if not all(isinstance(value, str) and value.strip() for value in models.values()):
        raise InstallError(f"{path}: state model values must be non-empty strings")
    if "runtime_version" in payload and payload["runtime_version"] != str(version):
        raise InstallError(f"{path}: runtime_version must be {str(version)!r} for state version {version}")
    if "source_revision" in payload and (not isinstance(payload["source_revision"], str) or not payload["source_revision"]):
        raise InstallError(f"{path}: source_revision must be a non-empty string")
    if "runtime_sha256" in payload and not re.fullmatch(r"[0-9a-f]{64}", str(payload["runtime_sha256"])):
        raise InstallError(f"{path}: runtime_sha256 must be a 64-character lowercase hex digest")
    if "managed_sha256" in payload:
        hashes = payload["managed_sha256"]
        if version != VERSION or not isinstance(hashes, dict) or set(hashes) != set(CURRENT_MANAGED_PATHS):
            raise InstallError(f"{path}: managed_sha256 has unexpected managed paths")
        if not all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) for value in hashes.values()):
            raise InstallError(f"{path}: managed_sha256 values must be lowercase SHA-256 digests")


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


def normalized_models(state: dict[str, object] | None) -> dict[str, str]:
    if not isinstance(state, dict):
        return {}
    models = state.get("models")
    if not isinstance(models, dict):
        return {}
    version = state_version(state)
    result = {
        "explorer": str(models.get("repo_explorer") if version == LEGACY_VERSION else models.get("explorer") or ""),
        "reviewer": str(models.get("reviewer") or ""),
    }
    if version == VERSION:
        result["verifier"] = str(models.get("verifier") or "")
    return result


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


def _backup_then_replace(
    plan: Plan,
    path: Path,
    old: bytes,
    desired: bytes,
    detail: str,
    reserved: set[Path],
) -> None:
    backup = backup_path(path, reserved)
    reserved.add(backup)
    plan.steps.append(
        Step(
            "backup",
            backup,
            f"back up {path.name} before replacement",
            content=old,
            expected_before=None,
            mode=file_mode(path),
        )
    )
    plan.steps.append(Step("update", path, detail, content=desired, expected_before=old, mode=file_mode(path)))


def _current_path_claim_status(
    prior_state: dict[str, object] | None,
    rel: str,
    old: bytes,
    desired: bytes,
) -> tuple[bool, str]:
    if not isinstance(prior_state, dict):
        return False, "no matching Foundry state"
    version = state_version(prior_state)
    if rel.startswith(".codex/agents/"):
        filename = Path(rel).name
        if filename not in MANAGED_AGENTS_BY_VERSION[version]:
            return False, f"Foundry v{version} state does not own this profile"
    elif rel == VERIFIER_RUNNER:
        if version != VERSION:
            return False, f"Foundry v{version} state does not own the verifier runner"
    else:
        return False, "path is not part of the Foundry managed set"

    if version != VERSION:
        return True, "legacy ownership will be checked against frozen lifecycle content"
    if old == desired:
        return True, "content already matches the current managed template"
    expected = _managed_hashes(prior_state).get(rel)
    if expected is None:
        return False, "current state predates managed-content fingerprints; drift cannot be distinguished safely"
    if sha256(old) != expected:
        return False, "managed content has drifted from the state-recorded fingerprint"
    return True, "state-recorded fingerprint matches"


def _plan_managed_path(
    plan: Plan,
    target: Path,
    rel: str,
    desired: bytes,
    *,
    force: bool,
    reserved: set[Path],
    prior_state: dict[str, object] | None,
    install_detail: str,
    update_detail: str,
) -> bool:
    path = target / rel
    old = read_bytes(path)
    if old is None:
        plan.steps.append(Step("create", path, install_detail, content=desired, expected_before=None, mode=file_mode(path)))
        return True

    claimed, reason = _current_path_claim_status(prior_state, rel, old, desired)
    if not claimed:
        if not force:
            plan.steps.append(Step("conflict", path, f"{reason}; explicit --force backup required", expected_before=old))
            return False
        _backup_then_replace(plan, path, old, desired, update_detail, reserved)
        return True

    if old == desired:
        plan.steps.append(Step("unchanged", path, "managed content already current", expected_before=old))
        return True
    plan.steps.append(Step("update", path, update_detail, content=desired, expected_before=old, mode=file_mode(path)))
    return True


def _plan_profile(
    plan: Plan,
    target: Path,
    filename: str,
    model: str,
    *,
    force: bool,
    reserved: set[Path],
    prior_state: dict[str, object] | None = None,
) -> bool:
    desired = set_profile_model(default_profile(filename), model).encode()
    return _plan_managed_path(
        plan,
        target,
        f".codex/agents/{filename}",
        desired,
        force=force,
        reserved=reserved,
        prior_state=prior_state,
        install_detail="install Foundry-managed profile",
        update_detail="update Foundry-managed profile",
    )


def _validate_legacy_profiles(
    plan: Plan,
    target: Path,
    prior_state: dict[str, object] | None,
    prior_models: dict[str, str],
) -> None:
    if not isinstance(prior_state, dict):
        return
    version = state_version(prior_state)
    if version == LEGACY_VERSION:
        checks = [
            ("repo_explorer.toml", "explorer", legacy_profile("repo_explorer.toml")),
            ("reviewer.toml", "reviewer", legacy_profile("reviewer.toml")),
        ]
    elif version == PREVIOUS_VERSION:
        checks = [
            ("explorer.toml", "explorer", previous_profile("explorer.toml")),
            ("reviewer.toml", "reviewer", previous_profile("reviewer.toml")),
        ]
    else:
        return
    for filename, key, template in checks:
        path = target / ".codex" / "agents" / filename
        old = read_bytes(path)
        if old is None:
            continue
        expected = set_profile_model(template, prior_models[key]).encode()
        if old != expected:
            plan.steps.append(
                Step(
                    "conflict",
                    path,
                    f"Foundry v{version} {filename} has drifted; refusing automatic upgrade",
                    expected_before=old,
                )
            )


def _desired_managed_contents(models: dict[str, str]) -> dict[str, bytes]:
    contents = {
        f".codex/agents/{filename}": set_profile_model(default_profile(filename), models[key]).encode()
        for filename, key in (
            ("explorer.toml", "explorer"),
            ("reviewer.toml", "reviewer"),
            ("verifier.toml", "verifier"),
        )
    }
    runner = read_bytes(ASSET_ROOT / VERIFIER_RUNNER)
    if runner is None:
        raise InstallError(f"missing bundled verifier runner: {ASSET_ROOT / VERIFIER_RUNNER}")
    contents[VERIFIER_RUNNER] = runner
    return contents


def build_install_plan(
    target: Path,
    *,
    force: bool = False,
    explorer_model: str | None = None,
    reviewer_model: str | None = None,
    verifier_model: str | None = None,
) -> Plan:
    target = target.resolve()
    if not target.exists() or not target.is_dir():
        raise InstallError(f"target directory does not exist: {target}")
    reject_managed_symlink_paths(target)
    prior_state = read_state(target)
    prior_version = state_version(prior_state) if isinstance(prior_state, dict) else None
    prior_models = normalized_models(prior_state)

    explorer_default, explorer_effort = bundled_profile_info("explorer.toml")
    reviewer_default, reviewer_effort = bundled_profile_info("reviewer.toml")
    verifier_default, verifier_effort = bundled_profile_info("verifier.toml")
    requested_reviewer_model = reviewer_model
    explorer_model = explorer_model or prior_models.get("explorer") or explorer_default
    reviewer_model = requested_reviewer_model or prior_models.get("reviewer") or reviewer_default
    if requested_reviewer_model is None and reviewer_model == OBSOLETE_REVIEWER_MODEL:
        reviewer_model = reviewer_default
    verifier_model = verifier_model or prior_models.get("verifier") or verifier_default
    selected_models = {"explorer": explorer_model, "reviewer": reviewer_model, "verifier": verifier_model}

    plan = Plan(target)
    agents_path, agents_content, agents_detail = desired_agents_md(target)
    plan.steps.append(step_for_content(agents_path, agents_content, agents_detail, unchanged_detail="managed block already current"))
    config_existed = read_bytes(target / ".codex/config.toml") is not None
    config_path, config_content, concurrency_added_now, config_detail = desired_config(target)
    plan.steps.append(step_for_content(config_path, config_content, config_detail, unchanged_detail="project config already current"))

    _validate_legacy_profiles(plan, target, prior_state, prior_models)
    reserved: set[Path] = set()

    legacy_path = target / ".codex" / "agents" / "repo_explorer.toml"
    legacy_state = prior_version == LEGACY_VERSION
    legacy_old = read_bytes(legacy_path) if legacy_state else None
    if not legacy_state and not legacy_path.is_symlink() and legacy_path.is_file():
        candidate = legacy_path.read_bytes()
        if is_foundry_managed(candidate.decode("utf-8", errors="replace")):
            plan.steps.append(
                Step(
                    "conflict",
                    legacy_path,
                    "legacy repo_explorer profile exists without matching v1 Foundry state; refusing automatic migration",
                    expected_before=candidate,
                )
            )

    explorer_ready = _plan_profile(
        plan,
        target,
        "explorer.toml",
        explorer_model,
        force=force,
        reserved=reserved,
        prior_state=prior_state,
    )
    if legacy_state:
        legacy_conflict = any(step.action == "conflict" and step.path == legacy_path for step in plan.steps)
        if legacy_old is None:
            plan.steps.append(Step("unchanged", legacy_path, "legacy repo_explorer profile already absent", expected_before=None))
        elif explorer_ready and not legacy_conflict:
            plan.steps.append(Step("delete", legacy_path, "migrate legacy repo_explorer profile to explorer", expected_before=legacy_old))
        else:
            plan.steps.append(Step("unchanged", legacy_path, "legacy repo_explorer retained because migration is blocked", expected_before=legacy_old))

    _plan_profile(
        plan,
        target,
        "reviewer.toml",
        reviewer_model,
        force=force,
        reserved=reserved,
        prior_state=prior_state,
    )
    _plan_profile(
        plan,
        target,
        "verifier.toml",
        verifier_model,
        force=force,
        reserved=reserved,
        prior_state=prior_state,
    )

    managed_contents = _desired_managed_contents(selected_models)
    _plan_managed_path(
        plan,
        target,
        VERIFIER_RUNNER,
        managed_contents[VERIFIER_RUNNER],
        force=force,
        reserved=reserved,
        prior_state=prior_state,
        install_detail="install deterministic Verifier runner",
        update_detail="update deterministic Verifier runner",
    )

    prior_added = bool(prior_state.get("concurrency_added")) if isinstance(prior_state, dict) else False
    concurrency_added = prior_added or concurrency_added_now
    prior_config_created = bool(prior_state.get("config_created")) if isinstance(prior_state, dict) else False
    config_created = prior_config_created or (not config_existed and concurrency_added_now)
    provenance = {
        "runtime_version": RUNTIME_VERSION,
        "source_revision": source_revision(),
        "runtime_sha256": runtime_sha256(),
    }
    managed_hashes = {rel: hashlib.sha256(content).hexdigest() for rel, content in managed_contents.items()}
    state = {
        "version": VERSION,
        "managed_agents": CURRENT_MANAGED_AGENTS,
        "agents_md_markers": [START, END],
        "concurrency_added": concurrency_added,
        "config_created": config_created,
        "models": selected_models,
        "managed_sha256": managed_hashes,
        **provenance,
    }
    state_path = target / ".codex" / ".agent-foundry.json"
    state_content = (json.dumps(state, indent=2, sort_keys=True) + "\n").encode()
    plan.steps.append(step_for_content(state_path, state_content, "record Foundry installation state", unchanged_detail="Foundry installation state already current"))
    plan.metadata.update(
        {
            "mode": "install",
            "models": selected_models,
            "roles": {
                "explorer": {"model": explorer_model, "reasoning_effort": explorer_effort},
                "reviewer": {"model": reviewer_model, "reasoning_effort": reviewer_effort},
                "verifier": {"model": verifier_model, "reasoning_effort": verifier_effort},
            },
            "concurrency_added": concurrency_added,
            "config_created": config_created,
            "migrating_legacy_explorer": legacy_state,
            "managed_sha256": managed_hashes,
            **provenance,
        }
    )
    return plan


def build_uninstall_plan(target: Path) -> Plan:
    target = target.resolve()
    if not target.exists() or not target.is_dir():
        raise InstallError(f"target directory does not exist: {target}")
    reject_managed_symlink_paths(target, profile_names=(), include_runner=False)
    state = read_state(target, required=True)
    assert state is not None
    schema_version = state_version(state)
    managed = state.get("managed_agents")
    assert isinstance(managed, list)
    reject_managed_symlink_paths(target, profile_names=tuple(str(value) for value in managed), include_runner=True)

    plan = Plan(target)
    agents_path, desired_agents, detail = desired_agents_md_without_foundry(target)
    plan.steps.append(step_for_content(agents_path, desired_agents, detail, unchanged_detail="Foundry managed block already absent"))
    config_path, desired_config_bytes, detail = remove_managed_concurrency(target, state)
    plan.steps.append(step_for_content(config_path, desired_config_bytes, detail, unchanged_detail=detail))

    models = normalized_models(state)
    hashes = _managed_hashes(state)
    model_keys = {
        "explorer.toml": "explorer",
        "repo_explorer.toml": "explorer",
        "reviewer.toml": "reviewer",
        "verifier.toml": "verifier",
    }
    for filename in managed:
        path = target / ".codex" / "agents" / str(filename)
        old = read_bytes(path)
        if old is None:
            plan.steps.append(Step("unchanged", path, "managed profile already absent", expected_before=None))
            continue
        rel = f".codex/agents/{filename}"
        if schema_version == VERSION and rel in hashes:
            matches = sha256(old) == hashes[rel]
        else:
            expected_model = str(models.get(model_keys[str(filename)]) or bundled_profile_model(str(filename)))
            expected = set_profile_model(lifecycle_profile(schema_version, str(filename)), expected_model).encode()
            matches = old == expected
        if not matches:
            plan.steps.append(Step("conflict", path, "Foundry-managed profile has drifted; refusing to delete modified content", expected_before=old))
            continue
        plan.steps.append(Step("delete", path, "remove Foundry-managed profile", expected_before=old))

    if schema_version == VERSION and VERIFIER_RUNNER in hashes:
        runner_path = target / VERIFIER_RUNNER
        old = read_bytes(runner_path)
        if old is None:
            plan.steps.append(Step("unchanged", runner_path, "Verifier runner already absent", expected_before=None))
        elif sha256(old) != hashes[VERIFIER_RUNNER]:
            plan.steps.append(Step("conflict", runner_path, "Verifier runner has drifted; refusing to delete modified content", expected_before=old))
        else:
            plan.steps.append(Step("delete", runner_path, "remove Foundry-managed Verifier runner", expected_before=old))

    state_path = target / ".codex" / ".agent-foundry.json"
    plan.steps.append(step_for_content(state_path, None, "remove Foundry installation state", unchanged_detail="Foundry installation state already absent"))
    plan.metadata["mode"] = "uninstall"
    return plan


def _check_precondition(step: Step) -> None:
    current = read_bytes(step.path)
    if current != step.expected_before:
        raise InstallError(
            f"{step.path}: changed after plan was built "
            f"(expected sha256={sha256(step.expected_before)}, current sha256={sha256(current)})"
        )


def apply_plan(plan: Plan) -> None:
    if plan.blocked:
        raise InstallError("plan contains conflicts; nothing was written")
    agents_dir = plan.target / ".codex" / "agents"
    known_profile_names = set().union(*MANAGED_AGENTS_BY_VERSION.values())
    planned_profile_names = sorted(
        {
            step.path.name
            for step in plan.steps
            if step.path.parent == agents_dir and step.path.name in known_profile_names
        }
    )
    reject_managed_symlink_paths(plan.target, profile_names=tuple(planned_profile_names), include_runner=True)
    mutating = [step for step in plan.steps if step.mutates]
    snapshots: dict[Path, tuple[bytes | None, int | None]] = {
        step.path: (read_bytes(step.path), file_mode(step.path)) for step in mutating
    }
    candidate_dirs: set[Path] = set()
    for step in mutating:
        parent = step.path.parent
        while parent != plan.target and plan.target in parent.parents:
            candidate_dirs.add(parent)
            parent = parent.parent
    existing_dirs = {directory for directory in candidate_dirs if directory.exists()}
    applied: list[Step] = []
    try:
        for step in mutating:
            reject_managed_symlink_paths(plan.target, profile_names=tuple(planned_profile_names), include_runner=True)
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
        for directory in sorted(candidate_dirs - existing_dirs, key=lambda path: len(path.parts), reverse=True):
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
        for role in ("explorer", "reviewer", "verifier"):
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
    parser.add_argument("--force", action="store_true", help="back up and replace unowned or drifted Foundry-managed paths")
    parser.add_argument("--uninstall", action="store_true", help="remove Foundry-managed runtime state")
    parser.add_argument("--explorer-model", help="override explorer model; preserved in Foundry state")
    parser.add_argument("--reviewer-model", help="override reviewer model; preserved in Foundry state")
    parser.add_argument("--verifier-model", help="override verifier model; preserved in Foundry state")
    args = parser.parse_args()
    target = Path(args.target)
    try:
        if args.uninstall:
            if args.force or args.explorer_model or args.reviewer_model or args.verifier_model:
                raise InstallError("--uninstall cannot be combined with --force or model overrides")
            plan = build_uninstall_plan(target)
        else:
            plan = build_install_plan(
                target,
                force=args.force,
                explorer_model=args.explorer_model,
                reviewer_model=args.reviewer_model,
                verifier_model=args.verifier_model,
            )
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
