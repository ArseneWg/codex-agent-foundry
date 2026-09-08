---
name: install-codex-agent-foundry
description: Install, update, inspect, verify, or uninstall Codex Agent Foundry in a target repository. Use when a user wants the Foundry multi-agent orchestration policy, project .codex configuration, repo_explorer/reviewer custom agents, safe upgrades, model overrides, runtime checks, provenance, or conservative removal without overwriting unrelated project configuration.
metadata:
  version: "1"
---

# Install Codex Agent Foundry

Use this Skill only to distribute or maintain the Foundry orchestration runtime. The runtime policy itself lives in the bundled project assets and defines how Codex agents collaborate.

## Workflow

1. Resolve the target repository. Default to the current working directory only when the user's intent clearly refers to it.
2. Inspect existing `AGENTS.md`, `.codex/config.toml`, `.codex/agents/`, and Foundry state when present.
3. Run `scripts/install.py <target> --check` first. The plan must list every file that would be created, updated, backed up, deleted, or blocked, plus the selected specialist models and runtime provenance.
4. Explain conflicts. Do not silently overwrite foreign same-name agent profiles.
5. If the plan is safe and matches the request, run `scripts/install.py <target>`.
6. Run `scripts/verify.py <target>`. When the user wants local Codex CLI/config validation and `codex` is available, use `scripts/verify.py <target> --runtime-check` as an additional check.
7. Report what was installed, preserved, updated, backed up, or left conflicted, and remind the user to start a new Codex session in the target project so project-level `AGENTS.md` and `.codex/agents/` are loaded.

For removal, use `scripts/install.py <target> --uninstall --check` before `--uninstall`.

## Runtime requirements

- Python 3.11+ is recommended and uses only the standard library.
- Python 3.10 is supported when `tomli` is installed (`python3 -m pip install tomli`). Without it, the scripts must fail with an actionable dependency message instead of a traceback.
- The Codex CLI is required only for the optional `--runtime-check`; structural verification does not require Codex in `PATH`.
- `--runtime-check` validates the local Codex binary, strict project-config parsing, and the bundled model catalog. It does **not** prove that the authenticated account can access the selected models.

## Safety

- The installer owns only the managed Foundry block in `AGENTS.md`.
- Preserve unrelated `AGENTS.md` content.
- Preserve valid user concurrency values.
- Update an agent profile automatically only when it is already marked `managed-by: codex-agent-foundry`.
- Use `--force` only when the user explicitly authorizes backup and replacement of a foreign same-name profile.
- Model overrides are explicit install options and are recorded in Foundry state so verification can distinguish customization from drift.
- Runtime provenance records a content version/hash and a best-effort Git source revision. A missing source revision is valid when the Skill was distributed without Git metadata.
- Do not treat `sandbox_mode = "read-only"` as an absolute security boundary; parent session permissions still matter.

Read `references/design.md` when changing runtime behavior or installer semantics.
