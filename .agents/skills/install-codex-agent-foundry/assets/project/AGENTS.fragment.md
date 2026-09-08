## Codex Agent Foundry

The root agent owns the goal, requirements, decomposition, architecture decisions, integration, validation responsibility, and the final answer. The root is the default source-code writer.

Delegate only when parallelism, context isolation, or noise isolation has a material benefit that outweighs the extra agent overhead. Do not delegate a single short deterministic command merely to use a cheaper model; when Root already knows the exact command and the output is small, Root should run it directly.

### Persistent specialist profiles

- Use `explorer` for no-write codebase investigation when behavior, ownership, dependencies, tests, or call paths are unclear. This project-scoped profile intentionally overrides Codex's built-in `explorer` so Foundry can pin a no-write evidence contract plus model/reasoning defaults.
- Use `verifier` for bounded, independently runnable, noisy or repetitive verification: builds, tests, CI/log analysis, device/environment checks, waits, and polling. Verifier executes and reports evidence; it does not diagnose broadly, modify source/project configuration, or fix failures. Validation commands may create their normal transient build/test artifacts, caches, and designated log files.
- Use `reviewer` after a material implementation for an independent cold review of correctness, regressions, security, concurrency/state risks, and meaningful test gaps.

Explorer and Reviewer are behaviorally no-write. Verifier is behaviorally source-preserving: it may produce validation artifacts and logs but must not intentionally change source, project configuration, or user-owned content. Current Codex spawned roles inherit the live parent session permission/sandbox profile, so these collaboration rules are not independent per-role sandbox boundaries.

### Role selection and model routing

Spawn persistent Foundry profiles by role (`agent_type`) and let the profile own its configured model and reasoning effort. Do not pass a spawn-time model or reasoning-effort override merely to restate a persistent profile.

In particular, spawn Verifier as `agent_type = "verifier"` without an explicit `model = "gpt-5.6-luna"` override. Some MultiAgent V2 client/model-catalog combinations reject Luna as an explicit spawn-time model override even when a custom role can apply Luna successfully. If the configured Verifier role itself cannot spawn on an installed client, do not silently change models mid-task: Root should run the validation directly for that session or the user can reinstall/reconfigure with `--verifier-model gpt-5.6-terra`.

### Minimal-history delegation

Give every subagent only the history required for its mission. When the client supports `fork_turns`, prefer `fork_turns = "none"` for self-contained Explorer, Verifier, and Reviewer missions and pass the needed goal, paths, commands, constraints, and evidence explicitly. When prior turns are genuinely required, use the smallest useful positive last-N value. Full-history forks are exceptional and should be justified by a mission that truly depends on broad conversation history.

Client compatibility is part of this rule: if an installed Codex release fails to deliver a self-contained mission correctly with no-history spawning, retry with the smallest useful last-N history rather than silently escalating to full history.

### Verification state ownership and output discipline

- Keep short deterministic validation with Root when spawning a subagent would cost more than the command itself.
- Delegate long-running, noisy, repetitive, or independently running validation to `verifier` with an exact command/scope, validation baseline, and stop condition.
- When Verifier runs in the same checkout, Root must keep the relevant source state stable until Verifier returns. If Root needs to continue changing relevant source, run verification from a separate worktree or other immutable snapshot.
- If relevant source state changes during a same-checkout verification, discard that evidence and rerun the required validation against the final state.
- For polling that does not require fresh model judgment on every observation, use one bounded shell/program loop and return the terminal condition instead of repeated model-tool turns.
- Keep large build, test, device, and log output in files when practical. Prefer logs outside source-owned paths. Return bounded evidence: command, cwd, validation baseline, PASS/FAIL, exit code, elapsed time when available, concise relevant diagnostics, and a full-log path.
- Do not repeat a deterministic build/test/check without a relevant state change, a plausibly transient failure, or an explicit reason.
- On failure, Verifier stops and returns evidence to Root. Root decides whether diagnosis needs Explorer, a stronger model, implementation, or a rerun.

### Evidence reuse and session lifecycle

Prefer targeted reads and searches over broad transcript-sized output. Reuse evidence from unchanged files instead of repeatedly rereading the same content. Use narrow `rg`, bounded `sed`, `tail`, or focused diagnostics before full-file/full-log output when those are sufficient.

After a major milestone or repeated context compaction, Root should checkpoint the durable task state: goal, decisions, changed files, validation results, blockers, and next action. If stale tool history dominates the session, prefer continuing from that checkpoint in a fresh session instead of preserving an ever-growing transcript.

### On-demand delegation

- Bounded implementation may be delegated to a worker only when scope, write ownership, intended behavior, constraints, acceptance criteria, and expected validation are explicit. While that worker owns the change, the root must not edit the same checkout concurrently.
- Narrow research may be delegated when it keeps substantial supporting material out of the root context.

### Write ownership and spawn discipline

Keep one source-code writer per checkout at a time. Source-preserving agents may run in parallel only when their evidence remains bound to stable relevant source state. For substantial parallel implementation, or for long verification while Root must continue relevant edits, use separate Git worktrees or independent snapshots.

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

Verifier missions that depend on repository contents must also identify the validation baseline and whether transient validation artifacts/logs are allowed.

A subagent should return evidence and results, not silently broaden its mission.

### Completion

Agent agreement is not evidence of correctness. Before declaring work complete, the root must inspect the final diff, confirm relevant validation evidence still matches the final source state, reconcile material reviewer findings, rerun critical checks when delegated evidence is incomplete, stale, or high-risk, and distinguish verified facts from unresolved assumptions.
