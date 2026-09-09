---
name: install-codex-agent-foundry
description: Install, update, inspect, verify, migrate, or uninstall Codex Agent Foundry in a repository, including role model overrides and conservative conflict handling. Not a general coding or review skill.
metadata:
  version: "3"
---

# Install Codex Agent Foundry

Maintain the Foundry runtime; do not act as its dispatcher. Collaboration rules and role contracts live in the bundled runtime, not this installation workflow.

## Workflow

Use Python 3.11+ explicitly when `python3` is older. Resolve the target repository from the request; inspect its `AGENTS.md`, `.codex/config.toml`, agent profiles, and Foundry state.

1. Preview: `python3 scripts/install.py <target> --check`. Explain conflicts and check every planned path, backup, and selected role model/effort.
2. Apply the matching options: `python3 scripts/install.py <target>`, then `python3 scripts/verify.py <target>`.
3. When requested, add `--runtime-check` to verification. It checks local configuration and CLI/version, not account model access, session loading, or actual child model/effort.
4. Report changes, preserved content, and unresolved conflicts. Start a new Codex session in the target project to load the updated runtime.

Resolve script paths relative to this Skill. For removal, preview `install.py <target> --uninstall --check` before applying `--uninstall`.

## Options and boundaries

`--explorer-model`, `--reviewer-model`, and `--verifier-model` change only the named role and are recorded in state. Default profiles are Explorer Terra/medium, Reviewer Terra/high, and Verifier Luna/low. Spawn by role, without redundant model overrides. A Verifier compatibility error requires Root-direct validation or an explicit `--verifier-model gpt-5.6-terra`; never silently switch models.

Preserve unrelated project content and user concurrency. Use `--force` only with explicit authorization to back up and replace foreign same-name profiles. A blocked plan must write nothing. v1/v2 migration and uninstall rely on frozen historical fixtures; never edit those fixtures to make a check pass. The historical Reviewer default migrates to Terra; non-default model selections are retained.

Read `references/design.md` only when changing or investigating runtime, model routing, mission preflight, evidence integrity, lifecycle, or provenance. `runtime/` is canonical in the Foundry source repository; generate `assets/project/` with `scripts/package_runtime.py`, never edit it independently.
