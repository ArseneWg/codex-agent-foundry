# Design reference

## Product boundary

Codex Agent Foundry's primary product is the runtime collaboration policy under `runtime/`: how the root agent, persistent specialists, and on-demand agents coordinate, own writes, delegate work, and validate completion.

The installer Skill is the delivery layer. Its `assets/project/` directory is generated from `runtime/` and must never become an independent source of truth.

## Design objective

Foundry optimizes for the **smallest persistent agent set that creates repeatable value**.

It intentionally avoids mirroring a human software organization with permanent `planner`, `architect`, `implementer`, `tester`, `reviewer`, `researcher`, and other personas. Every permanent role creates coordination cost:

- context must be transferred and summarized;
- more conclusions must be reconciled;
- more threads consume tokens and latency;
- write ownership becomes harder to reason about;
- role definitions can duplicate Codex built-ins or dedicated workflows;
- every custom profile becomes another configuration surface that can drift.

The baseline therefore prefers root ownership plus a small number of narrow evidence-producing specialists.

## Current Codex primitives

Foundry is designed around Codex rather than pretending Codex starts from an empty agent system.

Current Codex documentation provides built-in subagents:

- `default`: general-purpose fallback;
- `worker`: implementation and fixes;
- `explorer`: read-heavy codebase exploration.

Codex also provides a dedicated `/review` / `codex review` workflow for reviewing working-tree, branch, or commit changes.

Foundry treats these as existing primitives and adds custom profiles only where a narrower persistent contract is useful.

## Runtime shape

Foundry keeps two persistent read-only custom specialists:

- `repo_explorer`: isolates read-heavy investigation and returns evidence before root edits.
- `reviewer`: performs independent cold review after material implementation.

The root remains the default source-code writer and owns requirements, decomposition, architecture decisions, integration, final validation, and the final answer.

Implementation workers, verification agents, and researchers are on demand rather than permanent profiles.

## Why `repo_explorer` is custom even though Codex has built-in `explorer`

This is intentional overlap.

The built-in explorer already covers general read-heavy investigation. Foundry's custom profile exists to pin a narrower baseline contract:

- read-only sandbox;
- explicit model and reasoning effort;
- trace the real execution path with file/symbol evidence;
- separate facts from hypotheses;
- find the smallest likely change boundary;
- do not edit, refactor, or spawn further agents;
- return findings, evidence, risks, and remaining unknowns.

Benefits:

- predictable behavior across Foundry installations;
- clear read-only ownership;
- a stable evidence format for the root;
- explicit model-cost routing.

Cost:

- it duplicates some built-in explorer functionality;
- it is another custom profile to maintain.

This profile is not sacred. If the built-in explorer eventually satisfies Foundry's contract closely enough, deleting `repo_explorer` would be a valid simplification.

## Why `reviewer` is custom even though Codex has `/review`

The two mechanisms overlap in purpose but differ in orchestration boundary.

### Native `/review` / `codex review`

Use the native review workflow when a person explicitly wants a review of a working tree, branch, commit, or supplied review target.

It is a first-class Codex review workflow and should not be replaced merely for the sake of using a custom agent.

### Foundry `reviewer`

Use the custom reviewer when the root wants an independent review *inside a larger multi-agent task*:

```text
exploration
  → implementation
  → spawned reviewer cold review
  → root reconciles findings
  → root fixes / validates / finishes
```

The custom reviewer has a fixed read-only sandbox, model/effort selection, and instructions to report findings rather than fix them. This makes it an evidence-producing node that root can compose into a longer workflow.

Benefits:

- cold context separate from the writer;
- autonomous in-flow review without requiring a user command;
- stable severity/evidence/return contract;
- root remains the only integration/final-decision owner.

Cost:

- deliberate functional overlap with the native review workflow.

Foundry's reviewer is therefore complementary to `/review`, not a replacement for it.

## Why there is no permanent implementer

Codex already provides the built-in `worker` for implementation and fixes, so a generic `implementer.toml` would duplicate an existing primitive.

More importantly, implementation is write-heavy. Write parallelism is fundamentally more expensive than read parallelism because multiple writers can:

- modify the same file;
- act on stale assumptions after another writer changes the checkout;
- obscure ownership;
- create merge/integration work that cancels the latency benefit.

Foundry therefore uses this routing rule:

```text
small or tightly coupled implementation
→ root writes

large but clearly bounded implementation
→ built-in worker may own the write task

multiple substantial independent implementations
→ separate Git worktrees
```

A worker receives a write mission only when scope, ownership, intended behavior, constraints, acceptance criteria, and expected validation are explicit. While that worker owns a checkout, root does not edit the same checkout concurrently.

Trade-off: Foundry gives up some maximum write parallelism in exchange for simpler ownership and fewer stale-write races.

## Why there is no permanent tester

"Testing" is not a stable cross-repository role. Validation can mean unit tests, integration tests, compiler output, browser reproduction, CI analysis, performance checks, migrations, flaky-test triage, or repository-specific tooling.

A generic permanent tester would have little stable specialization beyond "run tests and report results".

Foundry therefore keeps:

- small/critical validation with root;
- large or noisy independent verification with a temporary verifier;
- project-specific persistent verification agents only when a stable tool surface and mission actually emerge.

A browser debugger with dedicated browser tools is an example of a specialization that may deserve its own persistent profile. A generic `tester` does not by default.

## Why there is no permanent planner or architect

Root already has the richest context: user intent, requirements, conversation history, repository evidence, subagent results, final diff, tests, and integration state.

Splitting planning and architecture into persistent agents creates additional handoffs and can make decision ownership ambiguous:

```text
User → Root → Planner → Architect → Worker → Reviewer → Root
```

Foundry keeps high-level judgment in the context that already has the most information and delegates primarily for isolation, parallel evidence gathering, or bounded execution.

Trade-off: this avoids role theater and coordination overhead, but it also means Foundry does not force an independent architecture opinion on every task. A repository that repeatedly benefits from a specialized architecture domain may choose to add one explicitly.

## Why research is temporary by default

Generic research is too broad to justify a baseline persistent profile. Research becomes a strong custom-agent candidate when it has a stable domain or tool surface, such as a dedicated documentation MCP server or repository-specific knowledge source.

The rule is: specialize around repeatable capability, not around a generic job title.

## Core design axiom: read concurrency is cheap; write concurrency is expensive

This axiom explains much of the runtime shape.

Read-only work usually composes safely:

- multiple agents can inspect the same checkout;
- each can gather independent evidence;
- no shared source state is mutated;
- fan-in is mostly a reasoning/reconciliation problem.

Write work adds state coordination:

- writes can overlap;
- assumptions can go stale;
- integration becomes a separate task;
- ownership must be explicit.

Therefore Foundry favors persistent read-only specialists, one writer per checkout, and worktrees for substantial parallel implementation.

## Persistent-agent admission criteria

A new persistent agent should satisfy most of these conditions before entering the baseline:

1. **Frequent** — the mission recurs across many meaningful tasks.
2. **Stable** — the mission boundary can be stated narrowly and consistently.
3. **Repeatable value** — the role is broadly useful or intentionally project-specific, not a one-off convenience.
4. **Isolation benefit** — separate context materially improves quality, focus, or noise control.
5. **Configuration benefit** — pinning model, effort, sandbox, tools, MCP, or skills materially improves the role.
6. **Clear ownership** — it does not create unnecessary competing writers.
7. **Built-ins are insufficient** — built-in agents or temporary delegation cannot express the specialization cleanly enough.
8. **Evaluable** — scenarios can describe the expected routing or quality improvement.

Possible future candidates:

- browser debugger with browser tooling;
- docs researcher bound to a stable docs MCP server;
- specialized security/database agent in a repository that repeatedly needs that exact workflow.

Generic `architect`, `implementer`, `tester`, or `researcher` do not qualify merely by name.

## Baseline trade-offs

Foundry intentionally accepts several compromises:

- **Minimality over maximum specialization.** The baseline is easier to understand and maintain, but less tailored to niche workflows.
- **Custom explorer over zero duplication.** `repo_explorer` overlaps the built-in explorer to pin a stricter contract.
- **Custom reviewer plus native review.** The reviewer overlaps `/review` to support autonomous in-flow cold review.
- **Single-writer clarity over maximum parallelism.** Shared-checkout write races are avoided at the cost of worktree/setup overhead.
- **One-level fan-out over recursive flexibility.** Nested delegation requires explicit root authorization so coordination remains legible.
- **Root judgment over role separation.** Planning/architecture remain centralized instead of being split into extra personas.

These are baseline defaults, not universal truths. Projects should change them when repeated evidence shows a better local structure.

## Mission contract

Every delegated mission should define at least:

- goal;
- scope and ownership;
- known facts and constraints;
- evidence or acceptance criteria;
- expected return;
- stop condition.

A subagent should return evidence/results and should not silently broaden its own mission.

## Completion model

Agent agreement is not evidence of correctness. Root owns completion and must reconcile:

- final diff;
- relevant tests/builds;
- logs or reproduction evidence;
- material reviewer findings;
- unresolved assumptions.

Delegated evidence can accelerate validation, but it does not transfer final responsibility away from root.

## Evals as policy contracts

`evals/scenarios.json` encodes small routing contracts:

- trivial change → root only;
- unclear cross-module bug → explore, then review after material implementation;
- bounded mechanical implementation → worker may own implementation;
- noisy verification → temporary verifier;
- substantial parallel writes → worktrees, not shared-checkout writers.

These scenarios are directional contracts, not a complete deterministic router. When the runtime policy changes, eval expectations should change intentionally rather than accidentally.

## Installer model

Installer behavior follows one rule: build one complete plan first, then apply exactly that same plan.

- `--check` prints the full plan, including state files and backups;
- conflicts block the whole apply and produce zero writes;
- apply rechecks each path against the bytes observed during planning;
- a mid-apply failure rolls back paths already changed;
- existing file modes are preserved;
- state records managed agents, model selections, and whether Foundry introduced the concurrency key;
- uninstall removes only Foundry-owned state and preserves user-owned configuration.

The installer exists to preserve the runtime policy safely; installer complexity should not drive the collaboration design.

## Model routing

Default role models come from the packaged runtime profiles themselves, so `runtime/` remains the source of truth. Explicit installer model overrides are persisted in state and verified as intentional customization.

Model choices are implementation details of roles, not reasons for creating roles. A role should exist because its mission and isolation boundary are valuable, not because a particular model happens to be available.

## References

- Codex Subagents: https://developers.openai.com/codex/subagents
- Codex developer commands / review workflow: https://developers.openai.com/codex/cli/slash-commands
