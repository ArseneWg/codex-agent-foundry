# Orchestration evaluation scenarios

These scenarios are contract examples for the Foundry runtime policy. They are not a substitute for real model forward-evaluation.

Use them when changing `runtime/AGENTS.fragment.md` or agent profiles:

1. Ask Codex to handle each scenario without telling it the expected routing.
2. Record whether it delegates, which role it chooses, whether write/validation-state ownership remains safe, and how it validates completion.
3. Compare the observed behavior with `scenarios.json`.
4. Treat repeated mismatches as evidence that the runtime policy needs revision.

CI performs static contract checks so accidental removal of key guardrails is caught, while human/model forward-evals remain the behavioral test.

For workload-aware v3, also record whether Codex:

- keeps a single short deterministic validation with Root;
- selects `verifier` for noisy/repetitive independent validation;
- preserves the exact validation command exit status through redirection, logging, timing, and shell wrappers;
- appends and propagates a final `FOUNDRY_RESULT_V1` footer and never reports PASS when footer/tool status is missing, nonzero, or inconsistent;
- has Root independently read the final machine footer before accepting delegated PASS as completion evidence;
- spawns persistent Foundry profiles by role without redundant spawn-time model overrides;
- keeps relevant source stable during same-checkout verification;
- moves long verification to a separate worktree/snapshot when Root must continue relevant edits;
- discards stale verification evidence after a relevant source-state change;
- allows only transient validation artifacts/logs rather than intentional source/config edits;
- uses the minimum useful history instead of defaulting to full-history forks;
- bounds command/log output returned to the model;
- aggregates mechanical polling inside a tool invocation;
- avoids rerunning deterministic validation without a relevant state change.
