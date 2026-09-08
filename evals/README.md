# Orchestration evaluation scenarios

These scenarios are contract examples for the Foundry runtime policy. They are not a substitute for real model forward-evaluation.

Use them when changing `runtime/AGENTS.fragment.md` or agent profiles:

1. Ask Codex to handle each scenario without telling it the expected routing.
2. Record whether it delegates, which role it chooses, whether write ownership remains safe, and how it validates completion.
3. Compare the observed behavior with `scenarios.json`.
4. Treat repeated mismatches as evidence that the runtime policy needs revision.

CI performs static contract checks so accidental removal of key guardrails is caught, while human/model forward-evals remain the behavioral test.
