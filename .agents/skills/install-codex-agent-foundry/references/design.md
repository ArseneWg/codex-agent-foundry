# Design reference

## Product boundary

Codex Agent Foundry's primary product is the runtime collaboration policy under `runtime/`: how the root agent, stable specialists, and on-demand workers coordinate, own writes, delegate, and validate completion.

The installer Skill is the delivery layer. Its packaged `assets/project/` directory is generated from `runtime/` and must never become an independent source of truth.

## Runtime shape

Foundry keeps two stable read-only specialist profiles:

- `repo_explorer`: isolates read-heavy codebase investigation.
- `reviewer`: performs independent cold review after material changes.

The root remains the default writer and owns final validation. Implementation workers and noisy verification agents are on-demand. One checkout has one writer at a time; substantial parallel writes move to worktrees.

Subagents do not recursively delegate by default. Nested delegation requires explicit root authorization for a specific mission.

## Installer model

Installer behavior follows one rule: build one complete plan first, then apply exactly that same plan.

- `--check` prints the full plan, including state files and backups.
- conflicts block the whole apply and produce zero writes;
- apply rechecks each path against the bytes observed during planning;
- a mid-apply failure rolls back paths already changed;
- existing file modes are preserved;
- state records managed agents, model selections, and whether Foundry introduced the concurrency key;
- uninstall removes only Foundry-owned state and preserves user-owned configuration.

## Model routing

Default role models come from the packaged runtime profiles themselves, so runtime remains the source of truth: `repo_explorer` currently uses `gpt-5.6-terra` / `medium`; `reviewer` currently uses `gpt-5.6` / `high`. Explicit installer model overrides are persisted in state and verified as intentional customization.
