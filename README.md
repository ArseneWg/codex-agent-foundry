# Codex Agent Foundry

[English](./README.md) | [简体中文](./README.zh-CN.md)

**Codex Agent Foundry is a repository-level multi-agent orchestration baseline for Codex.**

Its core product is not the installer. It is the runtime policy that defines how a root agent, read-only specialists, and on-demand workers should collaborate inside a code repository.

Foundry answers questions such as:

- What must the root agent continue to own?
- When is exploration worth delegating?
- When should a completed change get an independent review?
- When is a temporary worker or verifier useful?
- How do we avoid multiple writers colliding in one checkout?
- When should parallel writes move to Git worktrees?
- What evidence is required before work is considered complete?

The installer Skill, packaging, state tracking, conflict protection, verification, tests, and CI exist to distribute and maintain that runtime policy safely.

## Collaboration model

```text
                         Root
          goal / plan / integration / final validation
                         │
              default source-code writer
                         │
          ┌──────────────┴──────────────┐
          ▼                             ▼
  repo_explorer                     reviewer
  Terra / medium                  GPT-5.6 / high
      read-only                       read-only
          │                             │
          └──────────────┬──────────────┘
                         ▼
                       Root
                 evidence + final call
```

Two specialists are persistent:

- **`repo_explorer`** — read-heavy investigation: code paths, call chains, dependencies, tests, ownership boundaries, and implementation risk.
- **`reviewer`** — independent cold review after material implementation: correctness, regressions, security, state/concurrency risk, and meaningful test gaps.

Other roles are intentionally on demand:

- a bounded worker when scope, ownership, behavior, acceptance criteria, and validation are explicit;
- a temporary verifier for large/noisy tests, CI logs, diagnostics, or failure triage;
- narrow research when isolation materially reduces root-context noise.

## Core orchestration rules

1. **Root keeps final responsibility.** It owns the goal, decomposition, integration, final validation, and final answer.
2. **Root is the default writer.** Delegated writes are optional, not the normal path.
3. **One source-code writer per checkout at a time.** If a worker owns a write task, root should not edit the same checkout concurrently.
4. **Use worktrees for substantial parallel writes.** Parallel read-only work is fine in one checkout; parallel substantial writes should be isolated.
5. **Default to one-level fan-out/fan-in.** Subagents do not recursively delegate unless root explicitly authorizes nested delegation for a specific mission.
6. **Delegate only when it buys something.** Prefer read-heavy, noisy, independently verifiable, or latency-sensitive work.
7. **Give every delegated task a mission contract.** At minimum: goal, scope/ownership, known facts/constraints, acceptance evidence, expected return, and stop condition.
8. **Agent agreement is not correctness evidence.** Final judgment returns to diffs, tests, builds, logs, source, reproduction steps, and other concrete evidence.

The canonical policy lives in [`runtime/AGENTS.fragment.md`](./runtime/AGENTS.fragment.md).

## Repository map

```text
.
├── runtime/                       # core product / source of truth
│   ├── AGENTS.fragment.md
│   └── .codex/
│       ├── config.toml
│       └── agents/
│           ├── repo_explorer.toml
│           └── reviewer.toml
│
├── evals/                         # orchestration contract scenarios
│   ├── README.md
│   └── scenarios.json
│
├── .agents/skills/
│   └── install-codex-agent-foundry/
│       ├── SKILL.md
│       ├── agents/openai.yaml
│       ├── scripts/
│       │   ├── install.py
│       │   └── verify.py
│       ├── assets/project/        # generated copy of runtime/
│       └── references/design.md
│
├── scripts/
│   └── package_runtime.py
│
├── tests/
│   ├── test_installer.py
│   ├── test_cli.py
│   ├── test_runtime.py
│   └── test_hardening.py
│
├── .github/workflows/test.yml
├── AGENTS.md                      # rules for developing Foundry itself
├── README.md
└── README.zh-CN.md
```

### Source vs generated package

There are intentionally two identical runtime trees:

```text
runtime/                                      # edit this
        │
        │  scripts/package_runtime.py
        ▼
.agents/skills/install-codex-agent-foundry/
└── assets/project/                           # generated distribution copy
```

`runtime/` is the **only source of truth**. The Skill carries `assets/project/` so it remains self-contained when installed outside this repository.

Do not hand-edit `assets/project/`. After changing `runtime/`, run:

```bash
python3 scripts/package_runtime.py
python3 scripts/package_runtime.py --check
```

CI fails if the generated package drifts from `runtime/`.

## What each major area does

| Path | Purpose |
| --- | --- |
| `runtime/` | Core multi-agent runtime policy and stable custom-agent profiles. |
| `runtime/AGENTS.fragment.md` | Policy merged into a target repository's `AGENTS.md`. |
| `runtime/.codex/config.toml` | Minimal project Codex configuration used by Foundry. |
| `runtime/.codex/agents/*.toml` | Stable read-only specialist profiles. |
| `evals/` | Scenario contracts for checking whether policy changes still route tasks sensibly. |
| `.agents/skills/install-codex-agent-foundry/` | Installer/update/uninstall Skill. Delivery layer, not the primary product. |
| `.../assets/project/` | Generated self-contained package of `runtime/`. |
| `.../scripts/install.py` | Builds a complete plan, detects conflicts, applies/rolls back changes, supports model overrides and uninstall. |
| `.../scripts/verify.py` | Verifies installed state, runtime content, and intentional model overrides. |
| `scripts/package_runtime.py` | Packages `runtime/` into the Skill or checks for packaging drift. |
| `tests/test_installer.py` | Plan/apply, ownership, rollback, state, model and uninstall semantics. |
| `tests/test_cli.py` | Black-box CLI output, exit codes, dry-run, blocked-plan and uninstall behavior. |
| `tests/test_runtime.py` | Runtime TOML, policy invariants, eval contract, model-source and packaging checks. |
| `tests/test_hardening.py` | Edge cases found during independent review: path types, backups, state schema, encoding and uninstall restoration. |
| root `AGENTS.md` | Rules for developing this Foundry repository itself. |

## Install into a repository

From a clone of Foundry:

```bash
python3 .agents/skills/install-codex-agent-foundry/scripts/install.py /path/to/repo --check
python3 .agents/skills/install-codex-agent-foundry/scripts/install.py /path/to/repo
python3 .agents/skills/install-codex-agent-foundry/scripts/verify.py /path/to/repo
```

After installation, the target repository contains roughly:

```text
your-project/
├── AGENTS.md                  # existing content + Foundry managed block
└── .codex/
    ├── config.toml
    ├── .agent-foundry.json    # Foundry ownership/version/model state
    └── agents/
        ├── repo_explorer.toml
        └── reviewer.toml
```

During normal development, Codex uses `AGENTS.md`, `.codex/config.toml`, and the custom agent profiles. `.agent-foundry.json` is lifecycle metadata for install/update/verify/uninstall.

## Installer behavior

The installer follows **plan → apply**.

`--check` builds the same complete plan that a successful apply would execute. The plan includes:

- creates;
- updates;
- backups;
- deletes;
- unchanged paths;
- conflicts;
- `.codex/.agent-foundry.json` state changes.

If installation is blocked by a foreign same-name agent profile, the CLI prints a **BLOCKED PLAN** and performs zero writes.

Before each mutation, apply rechecks that the file still matches what was observed during planning. If a write fails mid-apply, already changed files are rolled back and transaction-created empty directories are cleaned up. Existing POSIX file modes are preserved.

### Optional model overrides

Defaults come from the packaged Runtime profiles, not separate hard-coded copies.

```bash
python3 .../install.py /path/to/repo \
  --explorer-model <model> \
  --reviewer-model <model>
```

Selections are stored in `.codex/.agent-foundry.json`, so verification treats them as intentional configuration rather than drift.

### Uninstall

```bash
python3 .../install.py /path/to/repo --uninstall --check
python3 .../install.py /path/to/repo --uninstall
```

Uninstall removes only Foundry-owned state. It preserves unrelated `AGENTS.md` content and user-owned configuration, and refuses to delete a managed profile that has drifted from the version Foundry installed.

## Use the installer as a Skill

When Codex opens this repository:

```text
$install-codex-agent-foundry /path/to/repo
```

For global reuse, install the `install-codex-agent-foundry` Skill from this repository, then invoke it from other projects.

## Development and validation

When changing the orchestration policy, edit `runtime/` first.

Then run:

```bash
python3 scripts/package_runtime.py
python3 scripts/package_runtime.py --check
python3 -m unittest discover -s tests -v
python3 -m compileall -q .agents/skills/install-codex-agent-foundry/scripts scripts tests
```

CI runs the same package check and test suite on Python 3.11, 3.12, and 3.13.

`evals/scenarios.json` is the contract layer for the actual product behavior: trivial work should not trigger unnecessary agents, unclear cross-module work should favor exploration, bounded implementation may use a worker, noisy verification may use a temporary verifier, and substantial parallel writes should move to worktrees.

## Current Codex assumptions

- repository Skills are discovered from `.agents/skills/`;
- project custom agents are discovered from `.codex/agents/`;
- `repo_explorer` currently defaults to `gpt-5.6-terra` / `medium`;
- `reviewer` currently defaults to `gpt-5.6` / `high`;
- model availability may differ by account/client, so explicit model overrides are supported.

Official references: [Build skills](https://developers.openai.com/codex/skills) and [Subagents](https://developers.openai.com/codex/subagents).
