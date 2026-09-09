# Design reference

Read this for design or lifecycle work, not for every coding task. [The runtime policy](../../../../runtime/AGENTS.fragment.md) is authoritative in the Foundry source checkout; a distributed Skill carries its generated copy under `assets/project/`.

## Product and context boundary

Foundry is a small collaboration policy plus a deterministic maintenance layer. Root keeps user intent, requirements, architecture, default implementation, integration, validation, and the final answer. Extra agents must justify handoff cost through independent evidence, isolation, or parallel latency savings.

Keep the installed `AGENTS.md` block self-contained: routing, mission preflight, write/state ownership, evidence acceptance, and context limits belong there. Put each specialist's detailed behavior in its profile, maintenance steps in `SKILL.md`, user commands in README, and rationale here. Do not make routine missions load this reference or duplicate complete role instructions.

A repository file consumes model context when loaded; disk duplication is not automatically prompt duplication. `assets/project/` intentionally duplicates `runtime/` for standalone distribution.

## Roles and admission

| Role | Reason to keep it |
| --- | --- |
| Explorer | A native role name with pinned evidence, no-edit, and cost boundaries; project same-name configuration overrides the built-in role. |
| Reviewer | Independent cold context inside an ongoing task, unlike the user-triggered `/review` workflow. It reports material findings without fixing them. |
| Verifier | A reusable execution/output boundary across test frameworks: run exact stages, retain logs, and report machine results without taking over diagnosis. |
| Worker | The existing built-in writer is sufficient; bounded ownership matters more than adding an Implementer persona. |

Root already handles planning and architecture; narrow research is on demand. Add a permanent specialist only when work is frequent, narrow, repeatable, benefits from isolation and supported configuration, has clear ownership, exceeds existing roles, and can be evaluated.

Default models remain Explorer `gpt-5.6-terra / medium`, Reviewer `gpt-5.6-terra / high`, and Verifier `gpt-5.6-luna / low`. Model/effort changes need separate eval evidence.

Use `agent_type`, not redundant spawn-time model/effort overrides. Some clients reject an explicit Luna override even when role-based spawning works. A role startup failure is reported, not silently retried with a different model; Root may validate or an explicit installer override may select Terra. Avoid a global subagent model downgrade that would also affect Worker.

Configured models are requests, not proof of account access or actual child selection. The historical Reviewer value `gpt-5.6` failed in the reported ChatGPT-account environment; the current default is Terra. Do not generalize one environment's smoke test into universal model availability.

## Mission and execution boundaries

Before each spawn, Root checks task-specific semantic completeness, not serialization. Explorer needs goal, scope, evidence, and stop; Reviewer needs target/baseline, scope, material focus, and stop. Worker additionally needs exclusive write scope, constraints, acceptance, and validation. Verifier needs exact argv command(s), cwd, baseline, per-stage log policy, and stop condition.

Root fills established facts without asking formatting questions. Unknown safety-critical facts remain unknown: keep work with Root until resolved. Profiles already supply standard result formats; no JSON mission schema or Dispatcher agent is added. Default to one-level fan-out/fan-in; recursive delegation requires explicit mission-specific authorization.

One checkout has one writer. Root must not edit concurrently with its Worker. Separate substantial parallel writes into worktrees. Source-preserving agents may run together only while relevant source remains stable. If edits must overlap validation, use an independent snapshot; identify relevant dirty changes as well as the commit. Changed baseline means invalid evidence and required checks must run again.

Explorer/Reviewer are no-edit. Verifier may produce permitted transient artifacts, caches, and logs, not intentionally alter source/configuration/user content. Role instructions are behavioral constraints, not independent filesystem sandboxes. Hard enforcement belongs to the runtime permission boundary.

## Verification evidence

Foundry installs `.codex/foundry-verifier-run.py` as a deterministic stage runner. Each source-dependent required stage is one argv command executed with `shell=False`, with stdout/stderr written to a designated log. The runner appends `FOUNDRY_RESULT_V1`, returns the same normalized process status, and rejects shell `-c` command strings.

Required validation stages are not encoded as `bash -c`, `sh -c`, `&&`, `||`, pipelines, or trailing cleanup/summary sequences. Multi-stage validation invokes the runner once per stage and stops on the first nonzero or INDETERMINATE result. If a required stage needs shell language, Root/Verifier must use a reviewed executable script whose own exit status represents that stage, or return INDETERMINATE rather than invent an opaque wrapper.

A stage PASS requires matching tool exit 0 and final `FOUNDRY_RESULT_V1 exit_code=0 status=PASS`. Overall PASS requires every required stage to PASS; skipped stages cannot pass. Root reads each actual referenced footer and reconciles stage command, cwd, baseline, scope, and source state. This directly addresses the earlier failure mode where a compound shell command could skip a required stage yet return zero after later successful work.

The machine footer is still not a cryptographic attestation or a substitute for live forward evaluation. The reported BlueZ false-PASS case should be rerun after installing the updated runtime.

Keep large output in files; use targeted reads and bounded diagnostics. Aggregate mechanical polling into one bounded executable/program when its exit status directly represents the terminal condition. Rerun only for relevant changes, a plausible transient failure, explicit request, or unreliable evidence. After milestones or repeated compaction, checkpoint durable state and prefer a fresh session when old tool history dominates.

## Lifecycle and ownership

| Installed version | Managed profiles | Upgrade behavior |
| --- | --- | --- |
| v1 | `repo_explorer`, `reviewer` | Validate frozen templates, normalize Explorer identity/model key, and delete the legacy role only after ownership is established. |
| v2 | `explorer`, `reviewer` | Validate frozen templates, preserve selections except the historical Reviewer default, and add Verifier. |
| v3 | `explorer`, `reviewer`, `verifier` | Maintain current profiles plus the deterministic Verifier runner with state-recorded content fingerprints. |

v1/v2 upgrade and uninstall use immutable fixtures under `assets/legacy/v1/` and `v2/`, not current templates. CI pins their hashes. Drift blocks historical migration; foreign destination profiles require explicit `--force` for backup/replacement. An orphan marked `repo_explorer` without matching state requires inspection; an unrelated file with that old name is left alone. v2 uninstall does not claim a foreign Verifier.

Current v3 state records `managed_sha256` for the three profiles and `.codex/foundry-verifier-run.py`. Automatic update or uninstall is permitted only when state ownership and content fingerprints establish that the managed path has not drifted. Manual edits block instead of being overwritten/deleted. Explicit `--force` backs up then replaces a drifted or unowned target.

Older v3 state may predate `managed_sha256`. If a managed file already equals the new desired template it can be adopted and fingerprinted safely. If it differs, automatic update blocks: without an old content fingerprint the installer cannot distinguish a previous template from a user edit. After inspection, explicit `--force` backs up the old content and establishes the new baseline. This is deliberately conservative.

Model selections persist in state. Without an explicit Reviewer override, recorded `gpt-5.6` migrates to the current default. Explicit non-default selections are preserved. This is installer migration, not a silent runtime fallback.

## Configuration editing and transaction boundary

The installer parses `.codex/config.toml` before and after changes. Text insertion/removal only considers structural lines outside multiline TOML strings, and the parsed result must differ exactly by `agents.max_concurrent_threads_per_session`. A fake `[agents]` or dotted key inside a string therefore cannot be mistaken for the owned setting; ambiguous edits fail before write.

The installer builds a full plan, rejects blocked plans, checks preconditions, preserves file modes, writes atomically per file, and attempts rollback on failure. Dry-run enumerates mutations including backups/state. This is not a filesystem transaction against concurrent external writers or process crashes.

## Provenance and packaging

State records version, roles/models, managed AGENTS markers, concurrency/config ownership, `source_revision`, `runtime_sha256`, and current managed-content fingerprints. `source_revision` is recorded only for a clean Foundry checkout whose runtime matches the package; copied Skills use `unknown`, never the target project's revision. `runtime_sha256` covers bundled runtime files; `managed_sha256` binds installed current profiles/runner to the content last written by Foundry.

Edit `runtime/` and run `scripts/package_runtime.py`. `--check` verifies source/package equality, rejects stale packaged `repo_explorer`, and checks frozen fixtures. Do not simplify historical fixtures or remove safety checks to save tokens; scripts cost context only when read.

## Validation levels

`verify.py` checks managed paths, state/runtime fingerprints, expected AGENTS/profile/runner contents, TOML, and drift. `--runtime-check` adds CLI presence/version and configured role values. It does not prove model entitlement, session loading, resolved child metadata, mission compliance, or project test success.

Unit/CLI tests cover deterministic behavior; static phrase/size checks guard accidental prompt regressions. [Forward evals](../../../../evals/README.md) assess actual routing, missing-mission handling, ownership, history, bounded output, stage completion, and result integrity. Scenario descriptions containing expected behavior are evaluator material, not prompts to give the model.

Official references: [Subagents](https://developers.openai.com/codex/subagents) · [AGENTS.md](https://developers.openai.com/codex/guides/agents-md) · [Skills](https://developers.openai.com/codex/skills)
