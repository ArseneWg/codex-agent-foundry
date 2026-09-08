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

The installer Skill, packaging, state tracking, conflict protection, verification, tests, and CI exist to distribute and maintain that policy safely.

## Design goal: the smallest useful agent system

Foundry deliberately does **not** model a software team as `planner + architect + implementer + tester + reviewer + researcher + ...`.

More agents are not automatically better. Every persistent role adds:

- context handoff and summarization loss;
- token and latency overhead;
- more opportunities for contradictory conclusions;
- more ownership and scheduling decisions;
- a larger configuration surface that can drift from Codex itself.

The baseline therefore keeps only roles that are frequent, narrow, reusable across repositories, and materially improved by an isolated context.

The default shape is:

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

Only two custom specialists are persistent:

- **`repo_explorer`** — read-heavy investigation before or during implementation.
- **`reviewer`** — independent cold review after a material implementation.

Implementation, verification, and research remain on demand.

## Why these roles — and why not the obvious alternatives?

Codex already ships built-in subagents. Current Codex documentation lists:

- `default` — general-purpose fallback;
- `worker` — implementation and fixes;
- `explorer` — read-heavy codebase exploration.

Foundry uses those capabilities rather than rebuilding every role as a custom profile.

### Role decision table

| Work | Foundry choice | Why |
| --- | --- | --- |
| Goal, decomposition, architecture, integration, final validation | **Root** | Root has the fullest task context and remains the single final decision owner. |
| Codebase exploration | **Persistent `repo_explorer`** | Exploration is frequent, naturally read-only, highly parallelizable, and benefits from a fixed evidence-oriented contract. |
| Implementation / fixes | **Root by default; built-in `worker` on demand** | Codex already provides a worker. A permanent custom implementer would mostly duplicate it while increasing write-ownership complexity. |
| Independent review | **Persistent `reviewer`** | A fresh read-only context can challenge assumptions inherited by the writer and can be invoked inside the orchestration flow. |
| Large/noisy test or log analysis | **Temporary verifier** | Verification varies heavily by project; a generic permanent tester profile adds little until a stable specialization exists. |
| Planning / architecture | **Root** | Splitting high-level judgment across extra personas increases context-transfer cost and makes final responsibility less clear. |
| Research | **Temporary research, unless a stable tool/domain specialization emerges** | Generic research is too broad; persistent specialists are more valuable when tied to a repeatable domain or tool surface. |

### Why a custom `repo_explorer` when Codex already has built-in `explorer`?

This is intentional overlap.

The built-in `explorer` is a useful general read-heavy agent. Foundry's `repo_explorer` narrows that role further by fixing a project-level contract:

- read-only sandbox;
- a selected model and reasoning effort;
- trace the real execution path with file/symbol evidence;
- separate confirmed facts from hypotheses;
- identify the smallest likely change boundary;
- do not edit, refactor, or recursively delegate;
- return findings, risks, evidence, and unknowns.

That gives Foundry a stable baseline independent of changes to the generic built-in role. The cost is one extra custom profile that overlaps built-in functionality. If Codex's built-in explorer eventually matches the desired contract closely enough, removing this custom profile is a valid future simplification.

### Why a custom `reviewer` when Codex has `/review` / `codex review`?

They overlap in purpose but serve different workflow boundaries.

**`/review` / `codex review`** is a first-class Codex code-review workflow. It is a good choice when a person explicitly wants to review a working tree, branch, or commit.

**Foundry `reviewer`** is a project-scoped subagent that the root can invoke *inside* a larger multi-agent task:

```text
Explore
   ↓
Root or Worker implements
   ↓
Foundry reviewer performs a cold read-only review
   ↓
Root reconciles findings, fixes if needed, validates
```

The custom reviewer also has a fixed sandbox/model/instruction contract and is explicitly told not to fix its own findings. This makes it useful as an independent evidence producer during orchestration.

The trade-off is intentional duplication with Codex's dedicated review workflow. Foundry does not claim its reviewer replaces `/review`; explicit human-triggered review can and should still use the native review workflow when that is the better fit.

### Why no permanent `implementer`?

Codex already ships a built-in `worker` for implementation and fixes. More importantly, implementation is **write-heavy**.

Read-only agents can usually run safely in parallel. Multiple writers in one checkout cannot.

Foundry therefore defaults to:

```text
small / coupled implementation
→ Root writes

large but clearly bounded implementation
→ built-in worker may own the write task

multiple substantial implementations in parallel
→ separate Git worktrees
```

A worker receives a write task only when scope, ownership, intended behavior, constraints, acceptance criteria, and validation are explicit. While the worker owns that checkout, root does not edit it concurrently.

This sacrifices some maximum parallelism in exchange for simpler ownership and fewer stale-write conflicts.

### Why no permanent `tester`?

"Testing" is not one stable cross-repository job. Verification may mean:

- a focused unit test;
- a large test suite;
- compiler diagnostics;
- browser reproduction;
- CI log analysis;
- performance checks;
- migration validation;
- flaky-test triage.

A generic permanent tester would mostly say "run tests and report results". Foundry instead keeps ordinary critical validation with root and delegates **large/noisy independent verification** to a temporary agent.

If a repository develops a stable specialized verification role — for example a browser debugger with dedicated browser tools — that may justify a real custom agent later.

### Why no permanent planner or architect?

Root already owns requirements, decomposition, architecture decisions, integration, and final validation. Those decisions are tightly coupled to the user's intent and to all evidence returned by subagents.

Adding permanent `planner` and `architect` layers would create more handoffs:

```text
User → Root → Planner → Architect → Worker → Reviewer → Root
```

Foundry prefers to keep high-level judgment in the context that already has the most information, and use subagents primarily for **isolated evidence-producing work**.

## The deeper rule: read concurrency is cheap, write concurrency is expensive

This is one of Foundry's central design assumptions.

Read-only work is easy to parallelize because agents can independently gather evidence without changing shared state. That is why exploration and review are good persistent specialists.

Write-heavy work carries additional coordination costs:

- two agents can modify the same file or assumption;
- one writer can act on stale code after another writer changes it;
- ownership becomes ambiguous;
- integration cost can erase the latency benefit of parallelism.

Therefore:

- one checkout has one source-code writer at a time;
- read-only agents may run in parallel;
- substantial parallel writes move to separate worktrees;
- root remains the integration owner.

## When should Foundry add another persistent agent?

A role should **not** become permanent merely because it resembles a software-engineering job title.

A new persistent agent should satisfy most of these conditions:

1. **Frequent** — the mission recurs across many meaningful tasks.
2. **Stable** — its boundaries can be described narrowly and consistently.
3. **Cross-repository or intentionally project-specific** — the role has repeatable value, not a one-off need.
4. **Isolation helps** — a separate context materially improves quality, focus, or noise control.
5. **Stable configuration helps** — model, reasoning effort, sandbox, tools, MCP, or skills can be meaningfully pinned.
6. **Ownership stays clear** — the role does not introduce unnecessary competing writers.
7. **Built-ins are insufficient** — a built-in agent or temporary delegation cannot express the specialization cleanly enough.
8. **Evals can describe the expected improvement** — the role's value can be checked instead of assumed.

Examples that *might* qualify later:

- a browser debugger with dedicated browser tooling;
- a documentation researcher bound to a project-specific docs MCP server;
- a specialized security or database agent for repositories that repeatedly need that exact workflow.

Generic `architect`, `implementer`, `tester`, or `researcher` roles do not qualify by default.

## Trade-offs Foundry accepts

The baseline is intentionally opinionated and conservative.

- **Minimality over maximum specialization.** Fewer permanent agents means less tuning for niche workflows.
- **Stable custom explorer over zero duplication.** `repo_explorer` overlaps Codex's built-in explorer so Foundry can pin a narrower contract.
- **Orchestrated reviewer plus native review workflow.** The custom reviewer overlaps `/review`, but supports autonomous in-flow cold review.
- **Single-writer clarity over maximum write parallelism.** Worktrees add setup cost, but shared-checkout multi-writer races are worse.
- **One-level fan-out over recursive flexibility.** Nested delegation is possible only when root explicitly authorizes it; the default keeps coordination legible.
- **Root judgment over role theater.** Planning and architecture stay with root even though separate personas may look more "agentic".

These are baseline choices, not universal truths. Repositories can override them when their workload provides evidence for a better structure.

## Example routing decisions

`evals/scenarios.json` encodes the intended baseline:

```text
tiny local change
→ Root only

unclear cross-module regression
→ repo_explorer → Root implementation → reviewer

mechanical bounded implementation
→ built-in worker may implement → reviewer → Root validates

large/noisy verification
→ temporary verifier → Root interprets evidence

two substantial independent writes
→ separate worktrees, not parallel writers in one checkout
```

These scenarios are deliberately small. They are contracts for the direction of the policy, not a claim that orchestration can be reduced to a fixed decision tree.

## Core orchestration rules

1. **Root keeps final responsibility.** It owns the goal, decomposition, integration, final validation, and final answer.
2. **Root is the default writer.** Delegated writes are optional, not the normal path.
3. **One source-code writer per checkout at a time.** If a worker owns a write task, root should not edit the same checkout concurrently.
4. **Use worktrees for substantial parallel writes.** Parallel read-only work is fine in one checkout; substantial parallel writes should be isolated.
5. **Default to one-level fan-out/fan-in.** Subagents do not recursively delegate unless root explicitly authorizes nested delegation for a specific mission.
6. **Delegate only when it buys something.** Prefer read-heavy, noisy, independently verifiable, or latency-sensitive work.
7. **Give every delegated task a mission contract.** At minimum: goal, scope/ownership, known facts/constraints, acceptance evidence, expected return, and stop condition.
8. **Agent agreement is not correctness evidence.** Final judgment returns to diffs, tests, builds, logs, source, reproduction steps, and other concrete evidence.

The canonical runtime policy lives in [`runtime/AGENTS.fragment.md`](./runtime/AGENTS.fragment.md). The longer rationale is in [the design reference](./.agents/skills/install-codex-agent-foundry/references/design.md).

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

The installer follows **plan → apply**. `--check` builds the same complete plan a successful apply would execute. Conflicts block the whole apply before any write; mid-apply failures roll back changed paths.

### Optional model overrides

Defaults come from the packaged Runtime profiles:

```bash
python3 .../install.py /path/to/repo \
  --explorer-model <model> \
  --reviewer-model <model>
```

Selections are stored in `.codex/.agent-foundry.json` and verification treats them as intentional configuration.

### Uninstall

```bash
python3 .../install.py /path/to/repo --uninstall --check
python3 .../install.py /path/to/repo --uninstall
```

Uninstall removes only Foundry-owned state and preserves unrelated project configuration.

## Development and validation

When changing orchestration behavior, edit `runtime/` first, update `evals/` when the expected routing contract changes, then run:

```bash
python3 scripts/package_runtime.py
python3 scripts/package_runtime.py --check
python3 -m unittest discover -s tests -v
python3 -m compileall -q .agents/skills/install-codex-agent-foundry/scripts scripts tests
```

## Current Codex assumptions

- Codex currently ships built-in `default`, `worker`, and `explorer` subagents.
- Project custom agents are discovered from `.codex/agents/`.
- `/review` and `codex review` provide a native code-review workflow distinct from a spawned custom reviewer.
- Repository Skills are discovered from `.agents/skills/`.
- `repo_explorer` currently defaults to `gpt-5.6-terra` / `medium`.
- `reviewer` currently defaults to `gpt-5.6` / `high`.
- Model availability may differ by account/client, so explicit model overrides are supported.

Official references: [Subagents](https://developers.openai.com/codex/subagents) · [Developer commands / code review](https://developers.openai.com/codex/cli/slash-commands) · [Build skills](https://developers.openai.com/codex/skills)
