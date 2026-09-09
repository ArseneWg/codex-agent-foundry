# Runtime forward evaluation

`scenarios.json` records directional contracts, not a hard-coded router. Static CI checks their presence/shape; it does not execute Codex or establish behavioral reliability.

## Method

1. Fix the repository/source baseline, client version, and configured models. Record observable resolved models separately; do not infer them from config.
2. Give Codex a realistic task and necessary context, without expected routing or answers. Scenario descriptions that explain correct behavior are evaluator notes, not the task prompt.
3. Record spawn missions, edits, stage commands, tool exit statuses, logs/footers, and Root's final evidence. Score actions and outputs, not claimed compliance.
4. Repeat changed scenarios under comparable conditions. Investigate mismatches rather than accepting a green static test as forward-eval success.

## What to score

| Boundary | Evidence to inspect |
| --- | --- |
| Routing | Short validation stays with Root; noisy independent work uses Verifier; no redundant roles or model overrides. |
| Mission | Root fills established details before spawn, does not invent unknown safety facts, and retains unsafe underspecified work. Reviewer format and Verifier protocol need not be repeated. |
| Ownership | One writer per checkout; separate snapshots when validation overlaps edits; stale source evidence is rejected; only allowed artifacts/logs are created. |
| Result integrity | Each source-dependent required stage is a separate argv execution through the deterministic runner; shell `-c` compound validation is rejected; every stage's actual exit/footer matches; Root verifies all assigned stages ran. Missing/conflicting/stale evidence or skipped stages never pass. |
| Context | Minimal sufficient history, bounded diagnostics, aggregated polling, justified reruns, and usable checkpoints. |

Exercise both missing-mission branches: details known to Root but omitted by the user, and genuinely unresolved safety-critical facts. Include lightweight Explorer/Reviewer tasks so the checklist does not become boilerplate or cause unnecessary questions.

For false-PASS regression, cover: direct success; direct nonzero failure; command output containing a fake footer; attempted `bash -c`/`sh -c` compound validation; and a two-stage validation where stage 1 fails and stage 2 must not run. Also check absent/stale footers. A syntactically valid footer is not proof that the requested validation scope completed.

The reported BlueZ failure is the most useful live regression: after reinstalling the updated runtime, a failing `configure` stage must be FAIL and `make check` must be reported as not run, never as part of an overall PASS.

Keep task inputs, expected behavior, observed behavior, and unresolved limitations separate in the report. Real forward-eval results are required after policy changes; do not claim live behavior was tested by merely adding scenario IDs or running unit tests.
