---
name: install-codex-agent-foundry
description: Install, update, inspect, verify, or uninstall Codex Agent Foundry in a target repository. Use when a user wants the Foundry multi-agent orchestration policy, project .codex configuration, repo_explorer/reviewer custom agents, safe upgrades, model overrides, or conservative removal without overwriting unrelated project configuration.
metadata:
  version: "1"
---

# Install Codex Agent Foundry

Use this Skill only to distribute or maintain the Foundry orchestration runtime. The runtime policy itself lives in the bundled project assets and defines how Codex agents collaborate.

## Requirements

- Run the installer and verifier with Python 3.11 or newer.
- Ubuntu 22.04 commonly provides Python 3.10 by default; use an explicit Python 3.11+ interpreter there.

Both entry scripts check the interpreter version before importing `tomllib` and return a clear error on older Python versions.

## Workflow

1. Resolve the target repository. Default to the current working directory only when the user's intent clearly refers to it.
2. Inspect existing `AGENTS.md`, `.codex/config.toml`, `.codex/agents/`, and Foundry state when present.
3. Run `scripts/install.py <target> --check` first. The plan must list every file that would be created, updated, backed up, deleted, or blocked, and show the selected Explorer/Reviewer model and reasoning effort.
4. Explain conflicts. Do not silently overwrite foreign same-name agent profiles.
5. If the plan is safe and matches the request, run `scripts/install.py <target>`.
6. Run `scripts/verify.py <target>`.
7. When the user asks for an environment/runtime check, run `scripts/verify.py <target> --runtime-check`. This additionally checks `codex` on `PATH`, reports `codex --version`, and prints the selected role models. It does not claim to verify account-level model availability.
8. Report what was installed, preserved, updated, backed up, or left conflicted, and tell the user to start a new Codex session in the target project so project-level instructions and agents are loaded from a fresh session.

For removal, use `scripts/install.py <target> --uninstall --check` before `--uninstall`.

## Safety

- The installer owns only the managed Foundry block in `AGENTS.md`.
- Preserve unrelated `AGENTS.md` content.
- Preserve valid user concurrency values.
- Update an agent profile automatically only when it is already marked `managed-by: codex-agent-foundry`.
- Use `--force` only when the user explicitly authorizes backup and replacement of a foreign same-name profile.
- Model overrides are explicit install options and are recorded in Foundry state so verification can distinguish customization from drift.
- Foundry state records runtime version, best-effort source revision, and a deterministic runtime SHA-256 fingerprint for auditing and reproduction.
- `source_revision` may be `unknown` when the Skill is installed outside a Git checkout; `runtime_sha256` is the authoritative content fingerprint in that case.
- Do not treat `sandbox_mode = "read-only"` as an absolute security boundary; parent session permissions still matter.

Read `references/design.md` when changing runtime behavior or installer semantics.
