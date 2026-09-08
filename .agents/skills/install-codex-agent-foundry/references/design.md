# Design reference

## Product boundary

Codex Agent Foundry's primary product is the runtime collaboration policy under `runtime/`: how Root, stable specialist profiles, and on-demand workers coordinate, own writes, delegate, and validate completion.

The installer Skill is the delivery/lifecycle layer. Its packaged `assets/project/` directory is generated from `runtime/` and must never become an independent source of truth.

## Design objective

Foundry optimizes for the **smallest useful persistent-agent set**, not for a simulation of a complete software organization.

Every permanent role adds context transfer, scheduling, token/latency cost, configuration surface, and ownership questions. A role should persist only when its mission is frequent, narrow, stable, and materially improved by isolation or pinned supported model/tool behavior.

Root remains the owner of user intent, requirements, decomposition, architecture decisions, integration, validation responsibility, and the final answer.

## Build on Codex-native roles

Foundry prefers Codex's own role vocabulary when the concept already exists.

Current workload-aware baseline:

- `explorer`: project-scoped override of Codex's built-in `explorer`;
- `verifier`: Foundry low-cost execution specialist for bounded noisy/repetitive verification;
- `reviewer`: Foundry custom cold-review specialist;
- built-in `worker`: on-demand implementation when the write mission is bounded;
- narrow research: on demand.

This replaces the v1 design where Foundry introduced a parallel role named `repo_explorer` next to Codex's built-in `explorer`.

### Why the role is named `explorer`

Codex already has the correct semantic category: read-heavy codebase exploration. Current Codex agent configuration supports project custom agents in `.codex/agents/` and gives a custom agent precedence when it has the same name as a built-in role.

Foundry therefore installs:

```text
.codex/agents/explorer.toml
```

The project override pins:

- `gpt-5.6-terra` / `medium` by default;
- a no-edit behavioral contract;
- real execution-path tracing with file/symbol evidence;
- facts separated from hypotheses;
- the smallest likely change boundary;
- no speculative refactors or recursive spawning;
- concise findings/risks/unknowns returned to Root.

The benefit is native routing vocabulary plus deterministic project policy.

## Permission, write, and artifact boundaries

Current Codex role application does not create a separate child filesystem sandbox from `sandbox_mode` in a role file. Spawned children retain the live parent permission/sandbox profile for authority-sensitive settings.

Explorer and Reviewer are therefore **behaviorally no-write**. Verifier is slightly different: builds and tests frequently write caches, generated build products, coverage data, device/log captures, or redirected stdout/stderr. Treating Verifier as literally filesystem-no-write would contradict its execution contract.

Verifier is instead **behaviorally source-preserving**:

- it must not intentionally modify source, project configuration, or user-owned content;
- it must not fix failures;
- validation commands may create their normal transient build/test artifacts and caches;
- designated validation log files are allowed, preferably outside source-owned paths;
- hard filesystem isolation still comes from the parent session/runtime, not the role TOML.

Relevant Codex sources: [`agent/role.rs`](https://github.com/openai/codex/blob/main/codex-rs/core/src/agent/role.rs) and [`multi_agents_common.rs`](https://github.com/openai/codex/blob/main/codex-rs/core/src/tools/handlers/multi_agents_common.rs).

## Model-cost and role-selection policy

Current baseline:

```text
Root       → user/current session model
explorer   → gpt-5.6-terra / medium
verifier   → gpt-5.6-luna / low
reviewer   → gpt-5.6 / high
worker     → Codex built-in / mission-dependent
```

Foundry pins specialist models independently instead of using `[agents].default_subagent_model`, because a global cheap default could unintentionally downgrade `worker` or future unpinned roles.

### Spawn persistent profiles by role

Persistent Foundry profiles should be selected by role (`agent_type`) and their role files should own their configured model/reasoning effort. Root should not pass spawn-time `model` or reasoning-effort overrides merely to restate values already pinned by a persistent profile.

This matters especially for Verifier. Some MultiAgent V2 clients/model catalogs have rejected `gpt-5.6-luna` when Luna is passed as an **explicit spawn-time model override**. Current Codex main validates an explicit spawn model against the MultiAgent-compatible model list before applying the selected role; the role is then applied as a later configuration layer.

Foundry therefore uses:

```text
agent_type = "verifier"
model      = omitted at spawn time
```

and lets `verifier.toml` request `gpt-5.6-luna`.

If an installed client cannot spawn the configured Verifier role itself, Foundry does not silently switch the child to another model mid-task. Root should run the validation directly for that session, or the installation can be explicitly changed with:

```bash
--verifier-model gpt-5.6-terra
```

A silent model fallback would make cost/quality behavior difficult to audit and could hide a client compatibility regression.

### Requested versus resolved model

A role profile records **Foundry's requested configuration**, not proof of the model actually resolved by every Codex client/release path.

`verify.py --runtime-check` verifies CLI presence/version and reports the configured role model/effort. It does not claim account entitlement, successful role spawn, or observed child model resolution. A stronger runtime assertion should only be added when Codex exposes stable machine-readable child configuration metadata suitable for that check.

## Why Reviewer remains custom

Codex's `/review` / `codex review` is a native user-triggered review workflow. Foundry's `reviewer` serves a different orchestration boundary: Root can spawn it inside a larger task after material implementation.

Its mission is intentionally cold and no-edit:

- correctness/regression/security/concurrency-state risks;
- meaningful test gaps;
- no style-only noise unless it hides a defect;
- no self-fixing;
- findings and evidence returned to Root.

The value is context separation from the writer.

## Why no permanent Implementer

Codex already provides built-in `worker`, and implementation is write-heavy.

Foundry defaults to:

- small/tightly coupled implementation → Root writes;
- larger bounded implementation → worker may own the write mission;
- substantial parallel implementation → separate worktrees.

A worker mission must define scope, ownership, intended behavior, constraints, acceptance criteria, expected validation, and stop condition. Root must not edit the same checkout while a worker owns it.

## Why Verifier is persistent

The original baseline kept verification temporary because repositories use different runners, browsers, compilers, devices, migrations, and CI systems. The stable cross-stack behavior is the execution contract itself:

```text
exact command/scope + validation baseline
→ run / wait / aggregate polling
→ keep large logs outside model context
→ return bounded evidence
→ STOP
```

A single short deterministic command still stays with Root. Verifier is for long-running, noisy, repetitive, or independently running work where context/noise isolation and a low-cost role justify spawn overhead.

Verifier does not broaden a failed check into diagnosis or implementation.

## Validation evidence must belong to a stable source state

A PASS is useful only if Root can identify the source state that produced it.

When Verifier runs in the same checkout, Root must keep the **relevant source state stable** from the start of delegated validation until Verifier returns. The mission should identify a validation baseline, such as the relevant commit/working-tree state that Root intends to validate.

If Root needs to continue changing relevant source while a long verification runs, the validation must run from a separate worktree or another immutable snapshot.

If relevant source state changes underneath same-checkout validation, the evidence is stale regardless of exit status. Root must discard that evidence and rerun the required validation against the final state before completion.

This rule prevents a long-running test process from reading a mixture of pre-edit and post-edit files and then being incorrectly interpreted as validation of the final diff.

Transient test/build artifacts do not violate this rule; intentional source/configuration changes do.

## Minimal history, bounded output, and polling

For self-contained Explorer/Verifier/Reviewer missions, Foundry prefers `fork_turns = "none"` when the installed client reliably supports no-history task delivery. If history is genuinely needed, use the smallest useful positive last-N; full history is exceptional.

If a client release has a no-history delivery bug, fall back to the smallest useful last-N rather than silently returning to full history.

Large command output should remain in files when practical. Repeated device/sysfs/process polling that does not require fresh reasoning should run in one bounded shell/program loop. The same deterministic validation should not be rerun without a relevant state change, a plausibly transient failure, or an explicit reason.

A Verifier result should normally contain:

- command and cwd;
- validation baseline;
- PASS/FAIL and exit code;
- elapsed time when available;
- concise relevant diagnostics;
- full-log path when output was redirected.

## Read/source-preserving concurrency versus write concurrency

A central Foundry assumption is:

> **Read concurrency is cheap; write concurrency is expensive; validation evidence still needs stable input state.**

Therefore:

- one checkout has one source-code writer at a time;
- Explorer/Reviewer may run concurrently because they intentionally do not write;
- Verifier may run concurrently only when relevant source state remains stable;
- if Root must keep changing relevant source during long verification, use a separate worktree/snapshot;
- substantial parallel implementation uses separate Git worktrees;
- Root remains integration owner.

## Persistent-agent admission criteria

A new permanent role should satisfy most of these:

1. recurring across meaningful tasks;
2. stable/narrow mission boundary;
3. repeatable value rather than one-off convenience;
4. material benefit from isolated context;
5. meaningful stable model/effort/tool configuration using settings Codex actually applies at role scope;
6. clear ownership without unnecessary competing writers;
7. existing built-ins or temporary delegation are insufficient;
8. expected benefit can be expressed in eval scenarios.

Role names that merely mirror job titles (`architect`, `implementer`, `tester`, `researcher`) do not qualify by default.

## Spawn discipline and mission contract

Default to one-level fan-out from Root and fan-in back to Root. Spawn the minimum number of agents that can produce meaningfully independent evidence or latency savings.

Subagents do not recursively delegate by default. Nested delegation requires explicit Root authorization for a specific mission.

Every delegated mission should define:

- goal;
- scope and ownership;
- known facts and constraints;
- acceptance evidence;
- expected return;
- stop condition.

Verifier missions that depend on repository contents additionally identify the validation baseline and whether transient validation artifacts/logs are allowed.

## Completion model

Agent agreement is not correctness evidence.

Before completion, Root should inspect the final diff, reconcile material reviewer findings, confirm relevant test/build/log/source evidence, verify that delegated validation still corresponds to the final source state, rerun high-risk checks when evidence is incomplete or stale, and distinguish verified facts from unresolved assumptions.

## Eval contracts

`evals/scenarios.json` is a directional contract, not a hard-coded router.

Current baseline expects:

- trivial local change → no unnecessary agent;
- one short deterministic check → Root directly;
- unclear cross-module regression → `explorer` + later `reviewer`;
- bounded mechanical implementation → worker may implement + reviewer;
- noisy/repetitive verification → persistent `verifier`;
- long verification while Root must keep editing relevant source → Verifier on a separate worktree/snapshot;
- repeated deterministic validation without a state change → avoid rerun;
- substantial parallel writes → worktrees, not shared-checkout multi-writer.

Repeated forward-eval mismatches are evidence that the policy needs revision.

## Runtime lifecycle: v1, v2, v3

### v1

Foundry v1 installed `repo_explorer.toml` + `reviewer.toml`.

### v2

Foundry v2 installs `explorer.toml` + `reviewer.toml` and records state/runtime version 2.

### v3

The workload-aware runtime adds:

```text
.codex/agents/verifier.toml
```

and records state/runtime version 3 with model keys for `explorer`, `reviewer`, and `verifier`.

### Migration safety

Migration preserves ownership semantics rather than performing a blind rename/update.

- v1 Explorer model overrides normalize to the current `explorer` key.
- Legacy `repo_explorer.toml` is deleted only when still Foundry-managed and exactly equal to the expected v1 lifecycle template for the recorded model.
- Drift in Foundry-owned v1 Explorer/Reviewer or v2 Explorer/Reviewer blocks the whole upgrade.
- An orphan legacy profile carrying the Foundry marker without matching v1 state blocks for inspection; a foreign file that merely reuses the old name is not claimed.
- Foreign target profiles block unless explicit `--force` authorizes backup + replacement.
- If migration is blocked, no writes are applied.
- v1/v2 uninstall remains supported.
- v2 → v3 preserves Explorer/Reviewer model overrides and adds Verifier only after ownership/drift checks pass.

Exact v1 and v2 lifecycle profile fixtures live under `assets/legacy/v1/` and `assets/legacy/v2/`. Upgrade/uninstall logic compares against these historical fixtures rather than deriving historical expectations from current Runtime.

The fixture contents are hash-pinned by repository validation. This makes an accidental edit to a historical template fail CI instead of silently changing both the generated migration input and its expected result.

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

`runtime/` is the current source of truth. The Installer Skill carries a generated `assets/project/` package so it can operate independently of this repository.

`scripts/package_runtime.py --check` verifies byte-for-byte synchronization of current Runtime/package files, rejects stale active legacy assets, and verifies the pinned hashes of frozen v1/v2 lifecycle fixtures.

## Current role models

Defaults come from the packaged runtime profiles themselves:

- `explorer`: `gpt-5.6-terra` / `medium`;
- `verifier`: `gpt-5.6-luna` / `low`;
- `reviewer`: `gpt-5.6` / `high`.

Explicit installer model overrides are persisted in state and treated as intentional configuration by verification and future upgrades.

## Session checkpoints

After a major milestone or repeated compaction, Root should checkpoint durable task state rather than preserving an unlimited transcript: goal, decisions, changed files, validation results and their baselines, blockers, and next action.

If stale tool history dominates the active context, continuing from that checkpoint in a fresh session is preferred.
