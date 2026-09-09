# Runtime forward evaluation

`scenarios.json` records directional contracts, not a hard-coded router. Static CI checks their presence/shape; it does not execute Codex or establish behavioral reliability.

## Method

1. Fix the repository/source baseline, client version, and configured models. Record observable resolved models separately; do not infer them from config.
2. Give Codex a realistic task and necessary context, without expected routing or answers. Scenario descriptions that explain correct behavior are evaluator notes, not the task prompt.
3. Record spawn missions, edits, commands, tool exit statuses, logs/footers, and Root's final evidence. Score actions and outputs, not claimed compliance.
4. Repeat changed scenarios under comparable conditions. Investigate mismatches rather than accepting a green static test as forward-eval success.

## What to score

| Boundary | Evidence to inspect |
| --- | --- |
| Routing | Short validation stays with Root; noisy independent work uses Verifier; no redundant roles or model overrides. |
| Mission | Root fills established details before spawn, does not invent unknown safety facts, and retains unsafe underspecified work. Reviewer format and Verifier protocol need not be repeated. |
| Ownership | One writer per checkout; separate snapshots when validation overlaps edits; stale source evidence is rejected; only allowed artifacts/logs are created. |
| Result integrity | Actual command exit survives wrappers; the final machine footer matches; Root reads the referenced result. Missing/conflicting/stale evidence never passes, and unexecuted stages are not claimed. |
| Context | Minimal sufficient history, bounded diagnostics, aggregated polling, justified reruns, and usable checkpoints. |

Exercise both missing-mission branches: details known to Root but omitted by the user, and genuinely unresolved safety-critical facts. Include lightweight Explorer/Reviewer tasks so the checklist does not become boilerplate or cause unnecessary questions.

For false-PASS regression, use success, nonzero failure, a command printing a fake footer, failed pipelines, and failed earlier stages followed by successful logging. Also check absent/stale footers. A syntactically valid footer is not proof that the requested validation scope completed.

Keep task inputs, expected behavior, observed behavior, and unresolved limitations separate in the report. Real forward-eval results are required after policy changes; do not claim live behavior was tested by merely adding scenario IDs or running shell unit tests.
