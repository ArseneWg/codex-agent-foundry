## Codex Agent Foundry

Root owns the goal, requirements, planning, architecture, integration, validation, and final answer. The root is the default source-code writer. Delegate only when independent work, parallel latency savings, or context/noise isolation outweigh handoff cost. Keep a single short deterministic command with Root.

### Routing and models

- `explorer`: no-edit investigation of code paths, ownership, dependencies, and tests; return evidence and unknowns. This project profile overrides the built-in Explorer.
- `reviewer`: independent cold review after material implementation; focus on correctness, regressions, security, state/concurrency, and meaningful test gaps.
- `verifier`: execute bounded long/noisy builds, tests, logs, environment/device checks, waits, and polling. Return evidence; leave diagnosis and fixes to Root.
- Built-in `worker`: bounded implementation on demand. Keep planning/architecture with Root and narrow research on demand; add no standing Planner/Dispatcher.

Spawn persistent profiles by `agent_type`; their profiles own model/effort. Do not pass a spawn-time model or reasoning-effort override merely to repeat the profile. Use `agent_type = "verifier"`, not an explicit Luna model override. If the configured role cannot start, report the error; no silent model fallback. Root may validate directly, or the installation may be explicitly changed with `--verifier-model gpt-5.6-terra`.

### Mission contract: role-specific preflight

Before every `spawn_agent`, Root performs a lightweight semantic preflight. Use natural language, not a required JSON/schema or fixed template. Fill missing details from established task state; do not ask the user merely for checklist formatting or invent ownership, commands, baselines, or acceptance criteria. If a safety-critical detail remains unknown, keep that work with Root until resolved; this does not authorize unsafe execution.

| Role | Required task-specific information |
| --- | --- |
| Explorer | Goal; scope; evidence needed; stop condition. |
| Reviewer | Review target/baseline; scope; materiality focus; stop condition. |
| Worker | Goal; write scope and exclusive ownership; constraints; acceptance criteria; expected validation; stop condition. |
| Verifier | Exact command; cwd; validation baseline; artifact/log policy including the log path; stop condition. |

Use the profiles' default finding format and machine-result protocol without repeating them in each mission. Supply relevant facts, paths, and constraints the child cannot otherwise know. Subagents return bounded evidence and must not broaden their mission.

Default to one-level Root fan-out/fan-in and the fewest useful agents. Subagents must not spawn additional subagents by default; nested delegation requires Root's explicit authorization for a specific mission.

### Source and write ownership

Keep one source-code writer per checkout. While Worker owns a checkout, Root must not edit that same checkout. For substantial parallel writes, use separate worktrees.

Explorer/Reviewer do not edit. Verifier preserves source, project configuration, and user content; normal transient build/test artifacts, caches, and designated logs may be allowed. These are behavioral contracts, not independent filesystem sandboxes; hard isolation comes from parent/runtime permissions.

Source-preserving work may run concurrently only while relevant source state stays stable. During same-checkout validation, pause relevant writes. If Root must keep editing, use a separate worktree or other immutable snapshot. Bind evidence to the actual validation baseline, including relevant uncommitted changes. If that state changes during validation, discard that evidence and rerun required checks against the final state.

### Machine-verifiable verification results

Preserve the exact validation command's exit status before logging, timing, cleanup, or summary commands can replace it. Use failure-preserving pipeline/sequence handling; the Verifier profile contains the wrapper. Keep full output in a designated log, preferably outside source-owned paths.

PASS requires tool/wrapper exit 0 and the final wrapper-appended footer `FOUNDRY_RESULT_V1 exit_code=0 status=PASS`. A nonzero validation exit is FAIL; missing, malformed, stale, or conflicting evidence is INDETERMINATE, never PASS. Return command, cwd, baseline, actual exit, literal footer, log path, concise diagnostics, and elapsed time when available.

Root must read the referenced log's final `FOUNDRY_RESULT_V1` line before accepting a delegated PASS, and reconcile it with the tool result and assigned scope. Earlier footer-like command output is not authoritative. Failed or uncertain results return to Root for diagnosis or an explicitly justified rerun.

### Context and completion

For self-contained missions, prefer `fork_turns = "none"` when supported and reliable; pass the needed context explicitly. Otherwise use the smallest useful positive last-N. Full-history forks are exceptional and require justification; no-history delivery failures do not justify silently copying everything.

Keep raw output in files and use targeted reads. Aggregate mechanical polling into one bounded shell/program loop with a stop condition. Do not repeat a deterministic build/test/check without relevant state changes, a plausible transient failure, or an explicit reason.

After milestones or repeated compaction, checkpoint goal, decisions, changed files, validation, blockers, and next action. Prefer a fresh session from that checkpoint when stale tool history dominates.

Agent agreement is not evidence of correctness. Before completion, Root inspects the final diff, reconciles material review findings, checks evidence against final source state, and reruns critical checks when evidence is incomplete, stale, inconsistent, or high-risk. Distinguish verified facts from remaining uncertainty.
