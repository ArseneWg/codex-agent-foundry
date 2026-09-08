---
name: install-codex-agent-foundry
description: Install, update, inspect, verify, or uninstall Codex Agent Foundry in a target repository. Use when a user wants the Foundry multi-agent orchestration policy, project .codex configuration, repo_explorer/reviewer custom agents, safe upgrades, model overrides, or conservative removal without overwriting unrelated project configuration.
metadata:
  version: "1"
---

# Install Codex Agent Foundry

Use this Skill only to distribute or maintain the Foundry orchestration runtime. The runtime policy itself lives in the bundled project assets and defines how Codex agents collaborate.

## Workflow

1. Resolve the target repository. Default to the current working directory only when the user's intent clearly refers to it.
2. Inspect existing `AGENTS.md`, `.codex/config.toml`, `.codex/agents/`, and Foundry state when present.
3. Run `scripts/install.py <target> --check` first. The plan must list every file that would be created, updated, backed up, deleted, or blocked.
4. Explain conflicts. Do not silently overwrite foreign same-name agent profiles.
5. If the plan is safe and matches the request, run `scripts/install.py <target>`.
6. Run `scripts/verify.py <target>`.
7. Report what was installed, preserved, updated, backed up, or left conflicted.

For removal, use `scripts/install.py <target> --uninstall --check` before `--uninstall`.

## Safety

- The installer owns only the managed Foundry block in `AGENTS.md`.
- Preserve unrelated `AGENTS.md` content.
- Preserve valid user concurrency values.
- Update an agent profile automatically only when it is already marked `managed-by: codex-agent-foundry`.
- Use `--force` only when the user explicitly authorizes backup and replacement of a foreign same-name profile.
- Model overrides are explicit install options and are recorded in Foundry state so verification can distinguish customization from drift.
- Do not treat `sandbox_mode = "read-only"` as an absolute security boundary; parent session permissions still matter.

Read `references/design.md` when changing runtime behavior or installer semantics.
