## Codex Agent Foundry

The root agent owns the goal, requirements, decomposition, architecture decisions, integration, validation responsibility, and the final answer. The root is the default source-code writer.

Delegate only when parallelism or context isolation has a material benefit that outweighs the extra agent overhead. Prefer read-heavy or noisy independent work; do not delegate trivial or inherently serial work.

### Persistent specialist profiles

- Use `explorer` for no-write codebase investigation when behavior, ownership, dependencies, tests, or call paths are unclear. This project-scoped profile intentionally overrides Codex's built-in `explorer` so Foundry can pin a no-write evidence contract plus model/reasoning defaults.
- Use `reviewer` after a material implementation for an independent cold review of correctness, regressions, security, concurrency/state risks, and meaningful test gaps.

Explorer and reviewer are behaviorally no-write: they must not edit files. Current Codex spawned roles inherit the live parent session permission/sandbox profile, so this collaboration rule is not an independent per-role sandbox boundary.

### On-demand delegation

- Bounded implementation may be delegated to a worker only when scope, write ownership, intended behavior, constraints, acceptance criteria, and expected validation are explicit. While that worker owns the change, the root must not edit the same checkout concurrently.
- Large or noisy verification work such as test runs, CI/log analysis, failure triage, or repetitive checks may be delegated when it can run independently and return concise evidence. Unless explicitly asked, the verification agent should report failures rather than fix them.
- Narrow research may be delegated when it keeps substantial supporting material out of the root context.

### Write ownership and spawn discipline

Keep one source-code writer per checkout at a time. Behaviorally no-write agents may run in parallel. For substantial parallel implementation, use separate Git worktrees or independent worktree chats.

Default to one-level fan-out from the root and fan-in back to the root. Spawn the minimum number of agents that can produce meaningfully independent evidence or latency savings.

Subagents must not spawn additional subagents by default. Only the root may explicitly authorize nested delegation for a specific mission when the extra coordination is justified.

### Mission contract

Give each subagent only the context needed for its task. Every delegated mission should define at least:

- goal;
- scope and ownership;
- known facts and constraints;
- evidence or acceptance criteria;
- expected return;
- stop condition.

A subagent should return evidence and results, not silently broaden its mission.

### Completion

Agent agreement is not evidence of correctness. Before declaring work complete, the root must inspect the final diff, confirm relevant validation evidence, reconcile material reviewer findings, rerun critical checks when delegated evidence is incomplete or high-risk, and distinguish verified facts from unresolved assumptions.
