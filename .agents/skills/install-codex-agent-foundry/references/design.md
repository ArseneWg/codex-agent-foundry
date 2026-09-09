# Design reference

Read this for design or lifecycle work, not for every coding task. [The runtime policy](../../../../runtime/AGENTS.fragment.md) is authoritative in the Foundry source checkout; a distributed Skill carries its generated copy under `assets/project/`.

## Product and context boundary

Foundry is a small collaboration policy plus a deterministic maintenance layer. Root keeps user intent, requirements, architecture, default implementation, integration, validation, and the final answer. Extra agents must justify handoff cost through independent evidence, isolation, or parallel latency savings.

Keep the installed `AGENTS.md` block self-contained: routing, mission preflight, write/state ownership, evidence acceptance, and context limits belong there. Put each specialist's detailed behavior in its profile. Keep installation steps in `SKILL.md`, user commands in README, and rationale here. Do not make routine missions load this reference or duplicate complete role instructions.

A repository file consumes model context when loaded; disk duplication is not automatically prompt duplication. `assets/project/` intentionally duplicates `runtime/` for standalone distribution. Preserve that packaging contract rather than hand-maintaining two sources.

## Roles and admission

| Role | Reason to keep it |
| --- | --- |
| Explorer | A native role name with pinned evidence, no-edit, and cost boundaries; project same-name configuration overrides the built-in role. |
| Reviewer | Independent cold context inside an ongoing task, unlike the user-triggered `/review` workflow. It reports material findings without fixing them. |
| Verifier | A reusable execution/output boundary across test frameworks: run an exact scope, aggregate polling, retain logs, and report status without taking over diagnosis. |
| Worker | The existing built-in writer is sufficient; bounded ownership matters more than adding an Implementer persona. |

Root already handles planning and architecture; narrow research is on demand. Add a permanent specialist only when work is frequent, narrow, repeatable, benefits from isolation and supported configuration, has clear ownership, exceeds existing roles, and can be evaluated. Browser, documentation, or security specialists are possibilities, not default additions.

Default models remain Explorer `gpt-5.6-terra / medium`, Reviewer `gpt-5.6-terra / high`, and Verifier `gpt-5.6-luna / low`. Read defaults from packaged profiles rather than a second constant list. Model/effort changes need separate eval evidence; a role rename or prompt cleanup is not a reason to tune them.

Use `agent_type`, not redundant spawn-time model/effort overrides. Some clients reject an explicit Luna override even when role-based spawning works. A role startup failure is reported, not silently retried with a different model; Root may validate or an explicit installer override may select Terra. Avoid a global subagent model downgrade that would also affect Worker.

Configured models are requests, not proof of account access or actual child selection. The historical Reviewer value `gpt-5.6` failed in the reported ChatGPT-account environment; the current default is Terra. Do not generalize one environment's smoke test into universal model availability.

## Mission and execution boundaries

Before each spawn, Root checks task-specific semantic completeness, not serialization. Explorer needs a goal, scope, evidence, and stop; Reviewer needs a target/baseline, scope, material focus, and stop. Worker additionally needs exclusive write scope, constraints, acceptance, and validation. Verifier needs the exact command, cwd, baseline, artifact/log policy with a log path, and stop condition.

Root fills established facts without asking formatting questions. Unknown safety-critical facts remain unknown: keep work with Root until resolved, without treating that retention as permission to act unsafely. Profiles already supply standard result formats; no JSON mission schema or Dispatcher agent is added. Default to one-level fan-out/fan-in; recursive delegation requires explicit mission-specific authorization.

One checkout has one writer. Root must not edit concurrently with its Worker. Separate substantial parallel writes into worktrees. Source-preserving agents may run together only while relevant source remains stable. If edits must overlap validation, use an independent snapshot; identify relevant dirty changes as well as the commit. Changed baseline means invalid evidence and required checks must run again.

Explorer/Reviewer are no-edit. Verifier may produce permitted transient artifacts, caches, and logs, not intentionally alter source/configuration/user content. Role instructions are behavioral constraints, not independent filesystem sandboxes. Hard enforcement belongs to the runtime permission boundary.

## Verification evidence

The Verifier profile defines a shell wrapper that captures the command status before logging or summaries, appends `FOUNDRY_RESULT_V1`, and propagates the status. PASS requires matching tool exit 0 and the final wrapper footer; missing, malformed, stale, or inconsistent evidence cannot pass. Root reads the actual referenced footer and reconciles command, cwd, baseline, and required scope.

This protocol has limits: the captured status belongs to the supplied command. `pipefail` and `set -e` do not prove every intended stage ran; AND/OR lists and later successful commands can mask an earlier failure. The footer is not a cryptographic attestation or a substitute for stage-completion evidence. Do not treat a copied wrapper test as an end-to-end Agent test. The reported BlueZ false-PASS case still requires real forward evaluation after changes.

Keep large output in files; use targeted reads and bounded diagnostics. Aggregate mechanical polling into one bounded command. Rerun only for relevant changes, a plausible transient failure, explicit request, or unreliable evidence. After milestones or repeated compaction, checkpoint durable state and prefer a fresh session when old tool history dominates.

## Lifecycle and ownership

| Installed version | Managed profiles | Upgrade behavior |
| --- | --- | --- |
| v1 | `repo_explorer`, `reviewer` | Validate frozen templates, normalize Explorer identity/model key, and delete the legacy role only after ownership is established. |
| v2 | `explorer`, `reviewer` | Validate frozen templates, preserve selections except the historical Reviewer default, and add Verifier. |
| v3 | `explorer`, `reviewer`, `verifier` | Refresh current managed policy/profiles and provenance. |

v1/v2 upgrade and uninstall use immutable fixtures under `assets/legacy/v1/` and `v2/`, not current templates. CI pins their hashes. Drift or a lost marker blocks historical migration; foreign destination profiles require explicit `--force` for backup/replacement. An orphan marked `repo_explorer` without matching state requires inspection; an unrelated file with that old name is left alone. v2 uninstall does not claim a foreign Verifier. Uninstall checks expected ownership and refuses modified profiles.

Model selections persist in state. Without an explicit Reviewer override, recorded `gpt-5.6` migrates to the current default, including older v3 candidates. Explicit non-default selections are preserved. This is installer migration, not a silent runtime fallback.

Current-version installation can replace a profile carrying the Foundry marker; it does not provide the historical-version drift checks for arbitrary v3 instruction edits. Inspect those edits before updating. Supported model customization uses installer flags; a management marker alone is not a content-integrity check.

The installer builds a full plan, rejects blocked plans, checks preconditions, preserves file modes, writes atomically per file, and attempts rollback on failure. Dry-run enumerates mutations including backups/state. This is not a filesystem transaction against concurrent external writers or process crashes. Preserve unrelated configuration; valid TOML syntax alone is insufficient proof that a text edit touched the intended key.

## Provenance and packaging

State records version, roles/models, managed AGENTS markers, concurrency/config ownership, `source_revision`, and `runtime_sha256`. A revision is recorded only for a clean Foundry checkout whose runtime matches the package; copied Skills use `unknown`, never the target project's revision. The content hash covers bundled runtime files and remains authoritative when revision cannot be proven.

Edit `runtime/` and run `scripts/package_runtime.py`. `--check` verifies source/package equality, rejects stale packaged `repo_explorer`, and checks frozen fixtures. Do not simplify historical fixtures or remove safety checks to save tokens; scripts cost context only when read.

## Validation levels

`verify.py` checks managed paths, state schema/fingerprint, expected AGENTS/profile contents, TOML, and drift. `--runtime-check` adds CLI presence/version and configured role values. It does not prove model entitlement, session loading, resolved child metadata, mission compliance, or project test success.

Unit/CLI tests cover deterministic behavior; static phrase/size checks guard accidental prompt regressions. [Forward evals](../../../../evals/README.md) assess actual routing, missing-mission handling, ownership, history, bounded output, and result integrity. Scenario descriptions containing expected behavior are evaluator material, not prompts to give the model. Record actual task inputs and tool evidence; do not score only whether an agent spawned.

Official references: [Subagents](https://developers.openai.com/codex/subagents) · [AGENTS.md](https://developers.openai.com/codex/guides/agents-md) · [Skills](https://developers.openai.com/codex/skills) · [Bash status semantics](https://www.gnu.org/software/bash/manual/html_node/The-Set-Builtin.html)
