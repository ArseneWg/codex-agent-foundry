#!/usr/bin/env python3
# managed-by: codex-agent-foundry
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

SHELL_NAMES = {"sh", "bash", "dash", "zsh", "ksh"}


def _normalized_returncode(value: int) -> int:
    if value < 0:
        return min(255, 128 + abs(value))
    return min(255, value)


def _uses_shell_command_string(argv: list[str]) -> bool:
    if not argv or Path(argv[0]).name not in SHELL_NAMES:
        return False
    for arg in argv[1:]:
        if arg == "--":
            break
        if arg == "-c" or re.fullmatch(r"-[A-Za-z]*c[A-Za-z]*", arg):
            return True
    return False


def _write_footer(log: Path, *, exit_code: int, status: str, reason: str | None = None) -> str:
    fields = ["FOUNDRY_RESULT_V1", f"exit_code={exit_code}", f"status={status}"]
    if reason:
        fields.append(f"reason={reason}")
    footer = " ".join(fields)
    with log.open("ab") as handle:
        handle.write(("\n" + footer + "\n").encode("utf-8"))
    print(f"{footer} log={log}")
    return footer


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run exactly one Verifier argv stage, capture output, and propagate its machine result."
    )
    parser.add_argument("--log", required=True, help="designated log path for this validation stage")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="command after --; no shell command strings")
    args = parser.parse_args()

    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    log = Path(args.log).expanduser()
    log.parent.mkdir(parents=True, exist_ok=True)

    if not command:
        log.write_bytes(b"")
        _write_footer(log, exit_code=64, status="INDETERMINATE", reason="missing_command")
        return 64
    if _uses_shell_command_string(command):
        log.write_bytes(b"")
        _write_footer(log, exit_code=64, status="INDETERMINATE", reason="shell_command_string_rejected")
        return 64

    try:
        with log.open("wb") as handle:
            proc = subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT, check=False)
        rc = _normalized_returncode(proc.returncode)
    except FileNotFoundError as exc:
        log.write_text(f"command not found: {exc}\n", encoding="utf-8")
        rc = 127
    except PermissionError as exc:
        log.write_text(f"command not executable: {exc}\n", encoding="utf-8")
        rc = 126
    except OSError as exc:
        log.write_text(f"command execution failed: {exc}\n", encoding="utf-8")
        rc = 126

    status = "PASS" if rc == 0 else "FAIL"
    _write_footer(log, exit_code=rc, status=status)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
