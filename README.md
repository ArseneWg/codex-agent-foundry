# Codex Agent Foundry

[English](README.md) | [简体中文](README.zh-CN.md)

A small repository-level collaboration policy for Codex: Root owns decisions and completion; specialists provide bounded evidence. The installer distributes that policy, not a second orchestration framework.

## Roles

| Role | Default model / effort | Responsibility |
| --- | --- | --- |
| Root | Current session | Plan, implement by default, integrate, validate, and answer. |
| `explorer` | `gpt-5.6-terra` / `medium` | Trace code paths, dependencies, and tests without edits; distinguish evidence from hypotheses. Overrides the built-in Explorer. |
| `reviewer` | `gpt-5.6-terra` / `high` | Independent no-edit review of material correctness, regression, security, state, and test risks. |
| `verifier` | `gpt-5.6-luna` / `low` | Run long/noisy validation, aggregate waits/polling, and return bounded results with logs. Do not diagnose broadly or fix failures. |
| Built-in `worker` | Mission-dependent | Implement only when scope, exclusive write ownership, and acceptance are clear. |

Keep short commands with Root. Use specialists only when isolation or parallel work offsets handoff cost. Planning/architecture stay with Root; research stays on demand. A new permanent role needs recurring narrow work, measurable benefit, clear ownership, and a reason built-ins cannot suffice.

Foundry Reviewer supports review inside a larger task; native `/review` or `codex review` remains the user-triggered review workflow. Context separation, not another persona, is its purpose.

## Runtime contract

The canonical instructions are in [runtime/AGENTS.fragment.md](runtime/AGENTS.fragment.md).

Root checks role-specific mission completeness before spawning. Missions remain natural language: fill details already known, never invent safety-critical facts, and retain underspecified work until bounded. Reviewer output format and Verifier result handling belong in role profiles, not repeated mission templates.

Use one writer per checkout. Root does not edit alongside a Worker that owns it. Separate substantial parallel writes into worktrees. Source-dependent verification requires stable source; isolate it when edits must continue, and discard evidence from a changed baseline. Explorer/Reviewer are no-edit; Verifier may create permitted transient artifacts, caches, and logs, but must preserve source/configuration/user content. These are behavioral rules, not independent filesystem sandboxes.

Spawn persistent agents by role and omit redundant model/effort overrides. Prefer `fork_turns="none"` for self-contained missions when supported and reliable; otherwise use the smallest useful history. Keep raw logs in files, aggregate mechanical polling, avoid unjustified reruns, and checkpoint long sessions.

A delegated PASS requires matching tool exit zero and the final wrapper-generated `FOUNDRY_RESULT_V1 exit_code=0 status=PASS` footer. Missing or conflicting evidence is INDETERMINATE. Root reads the referenced footer and checks the assigned scope and final source state; a footer alone does not prove every intended stage ran. Agent agreement is not correctness evidence.

## Install, update, remove

Use **Python 3.11+**. On systems whose `python3` is older, substitute an available 3.11+ interpreter. Both maintenance entry points return a clear version error before importing `tomllib`.

From the Foundry checkout:

```bash
SKILL=.agents/skills/install-codex-agent-foundry
python3 "$SKILL/scripts/install.py" /path/to/repo --check
python3 "$SKILL/scripts/install.py" /path/to/repo
python3 "$SKILL/scripts/verify.py" /path/to/repo
```

Inspect the plan before applying: it lists selected models/effort and all changes, conflicts, backups, and state updates. The target receives a managed `AGENTS.md` block, `.codex/config.toml`, three `.codex/agents/*.toml` profiles, and `.codex/.agent-foundry.json`. Start a **new Codex session** in the target afterward.

Model overrides are role-local:

```bash
python3 "$SKILL/scripts/install.py" /path/to/repo \
  --explorer-model <model> --reviewer-model <model> --verifier-model <model>
```

Selections persist in state. The historical Reviewer value `gpt-5.6` is migrated to the current default when no Reviewer override is supplied; other selections remain preserved. If a configured Luna Verifier cannot start, Root validates directly or the installation explicitly uses `--verifier-model gpt-5.6-terra`. There is no silent fallback or global subagent model downgrade. Availability depends on the actual account/client; configuration is not entitlement proof.

Removal also starts with a preview:

```bash
python3 "$SKILL/scripts/install.py" /path/to/repo --uninstall --check
python3 "$SKILL/scripts/install.py" /path/to/repo --uninstall
```

Foreign same-name profiles block installation unless explicit `--force` authorizes backup and replacement. Model overrides are supported customization; inspect other managed-file edits before any update. Uninstall refuses drifted profiles. See [lifecycle details](.agents/skills/install-codex-agent-foundry/references/design.md) for guarantees and boundaries.

## Upgrades and provenance

v1 `repo_explorer` migrates to `explorer`; v2 upgrades add Verifier. Historical v1/v2 profiles are frozen and hash-pinned for ownership/drift checks and uninstall. Drift blocks migration; foreign profiles are not silently claimed. Never edit legacy fixtures to make an upgrade pass.

State v3 records roles/models, managed concurrency/config ownership, runtime version, `source_revision`, and `runtime_sha256`. Revision is recorded only for a provably clean Foundry checkout with matching runtime/package; a copied Skill records `unknown`, not the target repository's commit. The content hash is authoritative when revision is unknown.

## Verification boundaries

`verify.py` checks managed paths, state, TOML, expected profiles, and drift. `--runtime-check` adds CLI presence/version and reports configured models. Neither proves account access, new-session loading, actual child model selection, or a successful project build.

[Forward evals](evals/README.md) test real routing, ownership, mission completion, and evidence handling. CI is necessary but does not replace those tests.

## Development

| Path | Purpose |
| --- | --- |
| `runtime/` | Installed policy and role source of truth. |
| `.agents/skills/install-codex-agent-foundry/` | Maintenance workflow, scripts, frozen legacy fixtures, and generated `assets/project/`. |
| `evals/` | Behavioral scenarios and evaluation guidance. |
| `scripts/`, `tests/`, `.github/workflows/` | Packaging, regression tests, and CI. |
| `AGENTS.md` | Guidance for developing Foundry itself, not the installed policy. |

Edit `runtime/`, then generate the distribution copy; never hand-edit packaged assets. Preserve explicit safety conditions when shortening prompts. Design rationale is [on-demand reference material](.agents/skills/install-codex-agent-foundry/references/design.md), not mandatory session context.

```bash
python3 scripts/package_runtime.py
python3 scripts/package_runtime.py --check
python3 -m unittest discover -s tests -v
python3 -m compileall -q .agents/skills/install-codex-agent-foundry/scripts scripts tests
```

CI runs Python 3.11/3.12/3.13 and a Python 3.10 version-guard check. Tests include frozen fixtures, lifecycle safety, runtime contracts, and bounded prompt sizes. Live-model behavior still requires forward evaluation.

Official references: [Subagents](https://developers.openai.com/codex/subagents) · [AGENTS.md](https://developers.openai.com/codex/guides/agents-md) · [Skills](https://developers.openai.com/codex/skills) · [Review commands](https://developers.openai.com/codex/cli/slash-commands)
