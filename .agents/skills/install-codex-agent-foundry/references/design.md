# Design reference

## Product boundary

Codex Agent Foundry's primary product is the runtime collaboration policy under `runtime/`: how Root, stable behaviorally no-write specialists, and on-demand workers coordinate, own writes, delegate, and validate completion.

The installer Skill is the delivery/lifecycle layer. Its packaged `assets/project/` directory is generated from `runtime/` and must never become an independent source of truth.

## Design objective

Foundry optimizes for the **smallest useful persistent-agent set**, not for a simulation of a complete software organization.

Every permanent role adds context transfer, scheduling, token/latency cost, configuration surface, and ownership questions. A role should persist only when its mission is frequent, narrow, stable, and materially improved by isolation or pinned supported model/tool behavior.

Root remains the owner of user intent, requirements, decomposition, architecture decisions, integration, validation responsibility, and the final answer.

## Build on Codex-native roles

Foundry prefers Codex's own role vocabulary when the concept already exists.

Current baseline:

- `explorer`: project-scoped override of Codex's built-in `explorer`;
- `reviewer`: Foundry custom cold-review specialist;
- built-in `worker`: on-demand implementation when the write mission is bounded;
- temporary verifier/research: on demand.

This replaces the v1 design where Foundry introduced a parallel role named `repo_explorer` next to Codex's built-in `explorer`.

### Why the role is now named `explorer`

Codex already has the correct semantic category: read-heavy codebase exploration. Current Codex agent configuration supports project custom agents in `.codex/agents/` and gives a custom agent precedence when it has the same name as a built-in role.

Foundry therefore installs:

```text
.codex/agents/explorer.toml
```

instead of maintaining two nearly synonymous active role names.

The project override pins a narrower contract:

- `gpt-5.6-terra` / `medium` by default;
- no-edit behavioral contract;
- real execution-path tracing with file/symbol evidence;
- facts separated from hypotheses;
- smallest likely change boundary;
- no edits, speculative refactors, or recursive spawning;
- concise findings/risks/unknowns returned to Root.

The benefit is native routing vocabulary plus deterministic project policy. The maintenance cost is intentional dependence on the documented same-name override behavior.

### Permission and sandbox boundary

Current Codex role application does not apply `sandbox_mode` as a separate role-level filesystem sandbox. The role layer applies bounded fields such as model, reasoning effort, developer instructions, features, and skills; spawn runtime overrides then copy the live parent permission profile into the child.

Therefore Explorer and Reviewer are **behaviorally no-write**: their policy and developer instructions prohibit edits, but they do not receive an independently enforced read-only filesystem merely from the role TOML. Hard isolation belongs at the parent session/runtime permission layer. This distinction is part of Foundry's safety model.

Relevant Codex sources: [`agent/role.rs`](https://github.com/openai/codex/blob/main/codex-rs/core/src/agent/role.rs) and [`multi_agents_common.rs`](https://github.com/openai/codex/blob/main/codex-rs/core/src/tools/handlers/multi_agents_common.rs).

### Model-cost rationale

Exploration often consists of locating symbols, tracing call paths, identifying tests/dependencies/ownership, and collecting evidence. It usually does not require the same expensive reasoning profile as Root or Reviewer.

Pinning only `explorer` avoids using `[agents].default_subagent_model` to downgrade unrelated subagents such as `worker`.

Current baseline remains:

```text
Root       → user/current session model
explorer   → gpt-5.6-terra / medium
reviewer   → gpt-5.6 / high
worker     → Codex built-in / mission-dependent
```

Role migration and reasoning-quality tuning are intentionally separate changes. `medium → low` should be evaluated independently rather than coupled to the role rename.

### Requested versus resolved model

The profile is authoritative for **Foundry's requested configuration**, not proof of the actual model resolved by every Codex client/release path.

Model-routing regressions have existed in some Codex releases. Therefore Foundry must distinguish:

```text
configured model/effort
from
observed resolved child model/effort
```

`verify.py --runtime-check` currently verifies CLI presence/version and reports the configured role model/effort. It explicitly does not claim observed spawned-child model resolution. A stronger check should only be introduced when the installed Codex exposes stable machine-readable spawned-thread metadata.

## Why Reviewer remains custom

Codex's `/review` / `codex review` is a native user-triggered review workflow. Foundry's `reviewer` serves a different orchestration boundary: Root can spawn it inside a larger autonomous task after material implementation.

Its mission is intentionally cold and read-only:

- correctness/regression/security/concurrency-state risks;
- meaningful test gaps;
- no style-only noise unless it hides a defect;
- no self-fixing;
- findings and evidence returned to Root.

The value is context separation from the writer, not role count.

## Why no permanent Implementer

Codex already provides built-in `worker`, and implementation is write-heavy.

Foundry defaults to:

- small/tightly coupled implementation → Root writes;
- larger bounded implementation → worker may own the write mission;
- substantial parallel implementation → separate worktrees.

A worker mission must define scope, ownership, intended behavior, constraints, acceptance criteria, expected validation, and stop condition. Root must not edit the same checkout while a worker owns it.

## Why no permanent Tester

Verification is not a stable universal role. Different repositories need different test runners, browsers, compilers, migrations, benchmarks, CI/log analysis, or flaky-test workflows.

Ordinary critical checks stay with Root. Large/noisy independent verification can be delegated temporarily. A permanent validation agent should appear only when a stable specialization/tool surface exists.

## Why planning and architecture stay with Root

Requirements and high-level architecture are tightly coupled to user intent and all accumulated evidence. Adding Planner/Architect layers creates more handoffs and can blur final ownership.

Foundry uses subagents primarily for:

- isolated evidence gathering;
- independent judgment;
- bounded execution where ownership is explicit.

## Read concurrency versus write concurrency

A central Foundry assumption is:

> **Read concurrency is cheap; write concurrency is expensive.**

Read-only agents can run independently without mutating shared source state. Multiple writers need state coordination, stale-assumption handling, ownership rules, and integration.

Therefore:

- one checkout has one source-code writer at a time;
- read-only work may run in parallel;
- substantial parallel writes move to separate Git worktrees;
- Root remains integration owner.

## Persistent-agent admission criteria

A new permanent role should satisfy most of these:

1. recurring across meaningful tasks;
2. stable/narrow mission boundary;
3. repeatable value rather than one-off convenience;
4. material benefit from isolated context;
5. meaningful stable model/effort/tool/MCP configuration using settings Codex actually applies at role scope;
6. clear ownership without unnecessary competing writers;
7. existing built-ins or temporary delegation are insufficient;
8. expected benefit can be expressed in eval scenarios.

Role names that merely mirror job titles (`architect`, `implementer`, `tester`, `researcher`) do not qualify by default.

## Spawn discipline

Default to one-level fan-out from Root and fan-in back to Root. Spawn the minimum number of agents that can produce meaningfully independent evidence or latency savings.

Subagents do not recursively delegate by default. Nested delegation requires explicit Root authorization for a specific mission.

Every delegated mission should define:

- goal;
- scope and ownership;
- known facts and constraints;
- acceptance evidence;
- expected return;
- stop condition.

## Completion model

Agent agreement is not correctness evidence.

Before completion, Root should inspect the final diff, reconcile material reviewer findings, confirm relevant tests/build/log/source evidence, rerun high-risk checks when delegated evidence is incomplete, and distinguish verified facts from unresolved assumptions.

## Eval contracts

`evals/scenarios.json` is a directional contract, not a hard-coded router.

Current baseline expects:

- trivial local change → no unnecessary agent;
- unclear cross-module regression → `explorer` + later `reviewer`;
- bounded mechanical implementation → worker may implement + reviewer;
- noisy verification → temporary verifier;
- substantial parallel writes → worktrees, not shared-checkout multi-writer.

Repeated forward-eval mismatches should be treated as evidence that the policy needs revision.

## v1 → v2 Explorer migration

### v1

Foundry v1 installed:

```text
.codex/agents/repo_explorer.toml
```

and state similar to:

```json
{
  "version": 1,
  "managed_agents": ["repo_explorer.toml", "reviewer.toml"],
  "models": {
    "repo_explorer": "...",
    "reviewer": "..."
  }
}
```

### v2

Current Foundry installs:

```text
.codex/agents/explorer.toml
```

with state:

```json
{
  "version": 2,
  "runtime_version": "2",
  "managed_agents": ["explorer.toml", "reviewer.toml"],
  "models": {
    "explorer": "...",
    "reviewer": "..."
  }
}
```

### Migration safety

Migration must preserve ownership semantics rather than perform a blind rename.

- The v1 Explorer model override is normalized to the v2 `explorer` key.
- The legacy `repo_explorer.toml` is deleted only when it is still Foundry-managed and exactly matches the expected v1 template for the state-recorded model.
- A drifted legacy profile blocks the whole plan.
- An orphan legacy profile carrying the Foundry management marker without matching v1 state blocks for inspection; a foreign file that merely reuses the old `repo_explorer.toml` name is not claimed or reserved.
- A foreign target `explorer.toml` blocks the migration.
- `--force` may back up/replace a foreign `explorer.toml` only with explicit user authorization.
- If migration is blocked, the legacy profile is retained and no writes are applied.
- v1 uninstall remains supported so users are never forced to migrate before removing Foundry.

Exact v1 Explorer and Reviewer profile fixtures are frozen under `assets/legacy/v1/`. Migration and v1 uninstall compare against those immutable lifecycle fixtures rather than deriving legacy expectations from the current Runtime, so future Runtime changes cannot silently redefine what v1 meant.

## Installer model

Installer behavior follows one rule: build one complete plan first, then apply exactly that same plan.

- `--check` shows all create/update/delete/backup/unchanged/conflict paths;
- conflicts block the whole apply and produce zero writes;
- apply rechecks planned preconditions before mutation;
- mid-apply failures roll back paths already changed;
- existing file modes are preserved;
- foreign same-name profiles are not overwritten without explicit `--force`;
- uninstall removes only Foundry-owned content.

## State provenance

State records:

- schema version;
- runtime version;
- managed profiles;
- model selections;
- whether Foundry introduced concurrency/config state;
- best-effort `source_revision`;
- deterministic `runtime_sha256`.

`source_revision` may be `unknown` when the Skill is distributed without Git metadata. `runtime_sha256` remains the deterministic content fingerprint.

## Runtime packaging

`runtime/` is the source of truth. The Installer Skill carries a generated `assets/project/` package so it can operate independently of this repository.

`scripts/package_runtime.py --check` verifies byte-for-byte synchronization and also rejects a stale packaged v1 `repo_explorer.toml`.

## Current role models

Defaults come from the packaged runtime profiles themselves rather than separately hard-coded copies:

- `explorer`: `gpt-5.6-terra` / `medium`;
- `reviewer`: `gpt-5.6` / `high`.

Explicit model overrides are persisted in state and treated as intentional configuration by verification and future upgrades.
