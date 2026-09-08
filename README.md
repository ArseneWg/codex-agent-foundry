# Codex Agent Foundry

[English](./README.md) | [简体中文](./README.zh-CN.md)

**Codex Agent Foundry is a repository-level multi-agent orchestration baseline for Codex.**

Its core product is not the installer and not a large catalog of agent personas. It is a small runtime policy for deciding:

- what the root agent must continue to own;
- which work benefits from context isolation;
- which work is safe to parallelize;
- when a subagent is worth its coordination cost;
- who is allowed to write in a checkout;
- what evidence is required before a task is complete.

The installer Skill, packaging, migration logic, state tracking, conflict protection, verification, tests, and CI exist to distribute and maintain that policy safely.

## Design goal: the smallest useful agent system

Foundry deliberately does **not** model a software team as `planner + architect + implementer + tester + reviewer + researcher + ...`.

More agents are not automatically better. Every persistent role adds:

- context handoff and summarization loss;
- token and latency overhead;
- more opportunities for contradictory conclusions;
- more ownership and scheduling decisions;
- a larger configuration surface that can drift from Codex itself.

The baseline therefore keeps only roles that are frequent, narrow, reusable, and materially improved by an isolated context.

```text
                         Root
          goal / plan / integration / final validation
                         │
              default source-code writer
                         │
          ┌──────────────┼──────────────┐
          ▼               ▼              ▼
      explorer         verifier       reviewer
  Terra / medium      Luna / low    GPT-5.6 / high
       no-edit          no-edit         no-edit
          │               │              │
          └───────────────┴──────────────┘
                          ▼
                        Root
                  evidence + final call
```

Three project-scoped specialist profiles are persistent:

- **`explorer`** — Codex-native exploration vocabulary with Foundry's evidence/cost contract.
- **`verifier`** — a low-cost execution specialist for long/noisy/repetitive builds, tests, logs, waits, and environment checks.
- **`reviewer`** — an independent cold-review specialist after material implementation.

Implementation remains Root/built-in-worker territory; narrow research stays on demand.

## Build on Codex primitives instead of inventing parallel vocabulary

Codex already provides built-in subagents such as:

- `default` — general-purpose fallback;
- `worker` — implementation and fixes;
- `explorer` — read-heavy codebase exploration.

Codex also provides a native `/review` / `codex review` workflow.

Foundry's rule is:

> **Reuse Codex-native roles when the role concept already exists. Create or override a project agent only when a narrower stable contract is worth maintaining.**

That is why Foundry now installs `.codex/agents/explorer.toml` instead of inventing a second active role called `repo_explorer`.

Current Codex documentation states that a custom agent with the same name as a built-in role takes precedence. The project-scoped `explorer.toml` therefore overrides the built-in `explorer` while preserving the same orchestration vocabulary.

### Role decision table

| Work | Foundry choice | Why |
| --- | --- | --- |
| Goal, decomposition, architecture, integration, final validation | **Root** | Root has the fullest task context and remains the final decision owner. |
| Codebase exploration | **Project override `explorer`** | Exploration is frequent, naturally no-write, highly parallelizable, and benefits from a stable evidence/cost contract. |
| Implementation / fixes | **Root by default; built-in `worker` on demand** | Codex already has a worker. A generic custom implementer would mostly duplicate it while increasing write-ownership complexity. |
| Independent review | **Persistent `reviewer`** | A fresh no-edit context can challenge assumptions inherited by the writer and can be invoked inside the orchestration flow. |
| Single short deterministic validation | **Root directly** | Spawning a subagent solely for a cheaper model can cost more than the command. |
| Large/noisy/repetitive validation | **Persistent `verifier`** | A stable no-edit execution/output contract isolates logs, waits and polling from Root context while using a low-cost profile. |
| Planning / architecture | **Root** | Extra planner/architect personas add handoffs and blur final responsibility. |
| Research | **Temporary unless a stable domain/tool specialization emerges** | A generic researcher is too broad; a docs/MCP/domain specialist may be worth adding later. |

## Why override built-in `explorer`?

The built-in `explorer` already provides the correct high-level role name. Foundry does not need a parallel exploration vocabulary; it needs a **more deterministic project contract**.

The installed profile pins:

```toml
name = "explorer"
model = "gpt-5.6-terra"
model_reasoning_effort = "medium"
```

and requires the agent to:

- trace the real execution path with file/symbol evidence;
- separate confirmed facts from hypotheses;
- identify the smallest likely change boundary;
- avoid edits and speculative refactors;
- avoid recursively spawning subagents;
- return findings, evidence, risks, and unknowns.

This gives Foundry three useful properties:

1. **Native routing vocabulary.** Root and Codex still say `explorer`, not `repo_explorer`.
2. **Cost control.** Exploration is intentionally pinned to a cheaper/faster model profile than a potentially expensive root session.
3. **Behavioral stability.** A no-edit, evidence-oriented contract is explicit in project instructions instead of being left entirely to a generic built-in default.

Current Codex does **not** apply `sandbox_mode` from an agent role as a separate child filesystem sandbox. Role application pins supported fields such as model, reasoning effort, instructions, features, and skills, while spawned children inherit the live parent permission/sandbox profile. Explorer, Verifier, and Reviewer are therefore **behaviorally no-write**, not independently sandbox-enforced. If hard filesystem isolation is required, enforce it at the parent session/runtime level.

### Requested model versus actual resolved child model

The profile expresses the model and reasoning effort that Foundry requests. Current Codex documentation gives role-file model/effort settings high precedence, so this is the most precise project-level way to pin exploration cost without globally downgrading `worker` or every other subagent.

However, Foundry deliberately distinguishes:

```text
configured/requested model
≠
proof of the model actually resolved by every installed Codex release
```

Subagent model-routing bugs have existed in some Codex releases and execution paths. `verify.py --runtime-check` therefore reports the selected profile values but does **not** claim that a spawned child thread was observed using them. A stronger guarantee should only be added when Codex exposes stable machine-readable spawned-thread model metadata.

Foundry also keeps `medium` as the current Explorer baseline. Changing role identity and changing reasoning quality are separate decisions; a future `medium → low` change should be justified by evals rather than bundled into this migration.

## Why keep a custom `reviewer` when Codex has `/review`?

They overlap in purpose but serve different workflow boundaries.

**`/review` / `codex review`** is a native code-review workflow. It is the natural choice when a person explicitly wants to review a working tree, branch, or commit.

**Foundry `reviewer`** is a project-scoped subagent that Root can invoke inside a larger task:

```text
explorer gathers evidence
        ↓
Root or Worker implements
        ↓
reviewer performs a cold no-edit review
        ↓
Root reconciles findings, fixes if needed, validates
```

The reviewer is instructed not to edit files and uses a strong/high-reasoning profile, focuses on material correctness/regression/security/state/test risks, does not fix its own findings, and returns evidence to Root.

Its value is not “another agent is smarter.” Its value is **context separation from the writer**.

## Why no permanent `implementer`?

Codex already provides built-in `worker` for implementation and fixes. More importantly, implementation is **write-heavy**.

Foundry therefore defaults to:

```text
small / tightly coupled implementation
→ Root writes

large but clearly bounded implementation
→ built-in worker may own the write mission

multiple substantial implementations in parallel
→ separate Git worktrees
```

A worker receives a write mission only when scope, ownership, intended behavior, constraints, acceptance criteria, and validation are explicit. While the worker owns a checkout, Root does not edit the same checkout concurrently.

This sacrifices some maximum parallelism for simpler ownership and fewer stale-write conflicts.

## Why Verifier became persistent

The original baseline kept verification temporary because repositories use different test frameworks. The observed workload changes that decision: the repeated cross-stack behavior is stable even when commands differ.

Verifier is deliberately **not a Tester persona**. It is an execution boundary:

```text
exact command/scope
→ run / wait / aggregate polling
→ keep large logs outside model context
→ return PASS/FAIL + exit code + bounded diagnostics + log path
→ STOP
```

A single short deterministic command still stays with Root. Verifier is for long-running, noisy, repetitive, or independently running work where context isolation and a low-cost model offset spawn overhead. It never edits code or broadens a failure into debugging; failure evidence returns to Root.

Default profile: `gpt-5.6-luna / low`. If an installed Codex release rejects Luna for child agents, `--verifier-model gpt-5.6-terra` is the compatibility fallback. Foundry does not globally set a cheap default for all subagents because that could also downgrade `worker`.

## Minimal history, bounded output, fewer model-mediated loops

For self-contained Explorer/Verifier/Reviewer missions, Foundry prefers `fork_turns = "none"` when the installed client reliably supports no-history task delivery. If history is genuinely needed, use the smallest useful positive last-N; full-history is exceptional. If a client release has a no-history delivery bug, fall back to the smallest useful last-N rather than silently using the full transcript.

Large command output should remain in files when practical. Repeated device/sysfs/process polling that does not require fresh reasoning should run in one bounded shell/program loop. The same deterministic validation should not be rerun without a relevant state change, a plausibly transient failure, or an explicit reason.

After major milestones or repeated compaction, Root checkpoints goal, decisions, changed files, validation results, blockers, and next action. When stale tool history dominates, continuing from that checkpoint in a fresh session is preferred over carrying an ever-growing transcript.

## Why no permanent planner or architect?

Root owns requirements, decomposition, architecture decisions, integration, final validation, and the final answer. Those decisions are tightly coupled to user intent and all evidence returned by subagents.

Adding permanent layers such as:

```text
User → Root → Planner → Architect → Worker → Reviewer → Root
```

creates more context transfers and makes responsibility less clear. Foundry keeps high-level judgment in the context that already has the most information and uses subagents mainly for **isolated evidence-producing work** or clearly bounded execution.

## The deeper rule: read concurrency is cheap, write concurrency is expensive

Behaviorally no-write agents can independently gather evidence without intentionally mutating shared source state. They are easy to parallelize and easy for Root to reconcile. This is an orchestration assumption, not a separate per-role sandbox guarantee.

Write-heavy agents add coordination costs:

- two writers can modify the same file or assumption;
- one writer can act on stale code after another changes it;
- ownership becomes ambiguous;
- merge/integration cost can erase the latency benefit of parallelism.

Therefore:

- one checkout has one source-code writer at a time;
- read-only agents may run in parallel;
- substantial parallel writes move to separate worktrees;
- Root remains the integration owner.

## When should Foundry add another persistent agent?

A role should not become permanent merely because it resembles a software-engineering job title.

A new persistent agent should satisfy most of these conditions:

1. **Frequent** — the mission recurs across meaningful tasks.
2. **Stable** — its boundaries can be described narrowly and consistently.
3. **Repeatable** — the role has durable value rather than one-off convenience.
4. **Isolation helps** — a separate context materially improves focus, quality, or noise control.
5. **Stable configuration helps** — model, reasoning effort, tools, MCP, skills, or other actually supported role settings are worth pinning.
6. **Ownership stays clear** — it does not create unnecessary competing writers.
7. **Built-ins/temporary delegation are insufficient** — a stable specialization adds something real.
8. **Evals can describe the expected improvement** — value can be checked instead of assumed.

Potential future examples include a browser debugger with dedicated browser tooling, a docs researcher bound to a stable docs MCP, or a repository-specific security/database specialist.

## Runtime policy

The canonical policy lives in [`runtime/AGENTS.fragment.md`](./runtime/AGENTS.fragment.md).

Core rules:

1. Root owns the goal, decomposition, architecture decisions, integration, final validation, and final answer.
2. Root is the default source-code writer.
3. One checkout has one writer at a time.
4. Substantial parallel writes use different worktrees.
5. Default to one-level fan-out/fan-in.
6. Subagents do not recursively delegate unless Root explicitly authorizes it for a specific mission.
7. Every delegated mission defines goal, scope/ownership, constraints, evidence/acceptance, expected return, and stop condition.
8. Agent agreement is not evidence of correctness; completion returns to diffs, tests, builds, logs, source, and reproduction evidence.

`evals/scenarios.json` encodes directional contracts such as:

```text
tiny local change
→ Root only

unclear cross-module regression
→ explorer → Root implementation → reviewer

bounded mechanical implementation
→ worker may implement → reviewer → Root validates

single short validation
→ Root directly

large/noisy/repetitive verification
→ verifier with minimal history + bounded output

parallel substantial writes
→ separate worktrees
```

## Repository layout

```text
.
├── runtime/                       # core product / source of truth
│   ├── AGENTS.fragment.md
│   └── .codex/
│       ├── config.toml
│       └── agents/
│           ├── explorer.toml      # overrides Codex built-in explorer
│           ├── reviewer.toml
│           └── verifier.toml        # low-cost bounded verification executor
├── evals/                         # orchestration contract scenarios
├── .agents/skills/
│   └── install-codex-agent-foundry/
│       ├── SKILL.md
│       ├── scripts/
│       │   ├── install.py
│       │   └── verify.py
│       ├── assets/project/        # generated copy of runtime/
│       └── references/design.md
├── scripts/package_runtime.py
├── tests/
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
        │ scripts/package_runtime.py
        ▼
.agents/skills/install-codex-agent-foundry/
└── assets/project/                           # generated distribution copy
```

`runtime/` is the only source of truth. Do not hand-edit `assets/project/`.

After runtime changes:

```bash
python3 scripts/package_runtime.py
python3 scripts/package_runtime.py --check
```

CI fails on packaging drift or a stale packaged legacy `repo_explorer.toml`.

## Requirements

Installer and verifier require **Python 3.11+** because they use standard-library `tomllib`.

Ubuntu 22.04 commonly ships Python 3.10. Both entry scripts check the Python version before importing `tomllib`, so old interpreters get a clear error rather than `ModuleNotFoundError`.

## Install / update

Preview first:

```bash
python3 .agents/skills/install-codex-agent-foundry/scripts/install.py /path/to/repo --check
```

The plan shows the effective role selections before writing:

```text
Selected agents:
- explorer: gpt-5.6-terra / medium
- reviewer: gpt-5.6 / high
- verifier: gpt-5.6-luna / low
```

Apply and verify:

```bash
python3 .agents/skills/install-codex-agent-foundry/scripts/install.py /path/to/repo
python3 .agents/skills/install-codex-agent-foundry/scripts/verify.py /path/to/repo
```

After a successful install, start a **new Codex session in the target repository** so project-level `AGENTS.md` and `.codex/agents/` are loaded from a fresh session.

A new install contains roughly:

```text
your-project/
├── AGENTS.md
└── .codex/
    ├── config.toml
    ├── .agent-foundry.json
    └── agents/
        ├── explorer.toml
        ├── reviewer.toml
        └── verifier.toml
```

### Model overrides

```bash
python3 .../install.py /path/to/repo \
  --explorer-model <model> \
  --reviewer-model <model> \
  --verifier-model <model>
```

Overrides are stored in Foundry state and survive future updates unless explicitly changed.

### v1 migration: `repo_explorer` → `explorer`

Foundry v1 installed:

```text
.codex/agents/repo_explorer.toml
```

Current Foundry migrates that profile to:

```text
.codex/agents/explorer.toml
```

The migration is ownership-safe:

- the v1 Explorer model override is preserved;
- the legacy profile is deleted only if it is still Foundry-managed and exactly matches the expected v1 content for the recorded model;
- a drifted or no-longer-managed legacy profile blocks the whole plan;
- an existing foreign `explorer.toml` blocks the whole plan;
- `--force` may back up and replace a foreign `explorer.toml` only when explicitly authorized;
- an orphan Foundry-managed `repo_explorer.toml` without matching v1 state blocks for manual inspection, while a foreign file using that old name is left alone;
- v1 uninstall remains supported using frozen v1 profile fixtures carried by the Installer Skill.

Foundry v2 already uses `explorer.toml` + `reviewer.toml`. A v2 → v3 upgrade validates both profiles against frozen v2 lifecycle fixtures, preserves their model overrides, and then adds `verifier.toml`. Drift blocks the plan instead of being overwritten. v2 uninstall remains supported, and a foreign `verifier.toml` is not claimed by v2 state.

Preview the migration with the same normal dry-run command. A blocked migration writes nothing.

State schema/runtime version is now v3. v1 and v2 lifecycle/uninstall remain supported through frozen legacy fixtures:

```json
{
  "version": 3,
  "runtime_version": "3",
  "managed_agents": ["explorer.toml", "reviewer.toml", "verifier.toml"],
  "models": {
    "explorer": "gpt-5.6-terra",
    "reviewer": "gpt-5.6",
    "verifier": "gpt-5.6-luna"
  },
  "source_revision": "...",
  "runtime_sha256": "..."
}
```

`source_revision` is conservative: it is recorded only when the installer can prove it is running from a clean Foundry checkout whose `runtime/` matches the packaged assets. A Skill copied into an unrelated target Git repository therefore records `unknown`, never the target project's commit. `runtime_sha256` is the deterministic content fingerprint and remains authoritative when Git provenance cannot be proven.

## Verification

Normal verification is deterministic and local:

```bash
python3 .../verify.py /path/to/repo
```

It checks managed paths, state schema, managed `AGENTS.md` block, TOML parsing, expected profiles/model overrides, and drift.

For an additional environment check:

```bash
python3 .../verify.py /path/to/repo --runtime-check
```

This additionally checks:

- `codex` is on `PATH`;
- `codex --version` succeeds in the target repository;
- strict local TOML/profile parsing passed;
- selected Explorer/Reviewer/Verifier model and reasoning effort.

It explicitly **does not** claim:

- account-level model availability;
- that a new Codex session loaded the files successfully;
- that an actually spawned Explorer child resolved to the requested model/effort.

Those require observable runtime/session metadata from Codex rather than static configuration alone.

## Uninstall

```bash
python3 .../install.py /path/to/repo --uninstall --check
python3 .../install.py /path/to/repo --uninstall
```

Uninstall removes only Foundry-owned state and profiles, preserves unrelated project configuration, and refuses to delete a managed profile that has drifted.

## Development and validation

When changing orchestration behavior, edit `runtime/` first. When role routing changes, update `evals/` too.

```bash
python3 scripts/package_runtime.py
python3 scripts/package_runtime.py --check
python3 -m unittest discover -s tests -v
python3 -m compileall -q .agents/skills/install-codex-agent-foundry/scripts scripts tests
```

CI runs the full suite on Python 3.11, 3.12, and 3.13, plus a Python 3.10 smoke job that verifies the clear version guard.

## Current Codex assumptions

- Project role files can lock role-level model and reasoning effort; current Codex exposes these as settings that cannot be changed for that role.
- Spawned role permissions/sandboxing are inherited from the live parent session; Foundry's no-write specialists are behavioral contracts, not separate sandbox profiles.
- built-in subagents include `default`, `worker`, and `explorer`;
- project custom agents are discovered from `.codex/agents/`;
- a custom agent with the same name as a built-in role takes precedence;
- agent profile `model` and `model_reasoning_effort` can pin role-level selection;
- `/review` / `codex review` is a native review workflow distinct from a spawned custom reviewer;
- model availability and model-routing behavior can vary by account/client/release.

Official references: [Subagents](https://developers.openai.com/codex/subagents) · [Developer commands / code review](https://developers.openai.com/codex/cli/slash-commands) · [Build skills](https://developers.openai.com/codex/skills)
