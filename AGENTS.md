# Repository guidance

This repository develops and distributes the Codex Agent Foundry multi-agent orchestration baseline.

- Treat `runtime/` as the source of truth for the collaboration policy and stable custom agent profiles.
- Pack `runtime/` into the installer Skill with `python3 scripts/package_runtime.py`; never hand-edit packaged assets independently.
- Keep the installer deterministic, conservative, transactional, and idempotent.
- A dry-run plan must enumerate every path a successful apply would mutate, including backups and state.
- Preserve unrelated user configuration by default; require explicit force for destructive conflict resolution.
- Keep the installer Skill concise. Put behavior in scripts and design rationale in references.
- Run the full test suite and `python3 scripts/package_runtime.py --check` after runtime or installer changes.
