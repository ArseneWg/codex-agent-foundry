---
name: install-codex-agent-foundry
description: Install, update, inspect, verify, migrate, or uninstall Codex Agent Foundry in a target repository. Use when a user wants workload-aware Codex multi-agent policy, project .codex configuration, explorer/reviewer/verifier profiles, safe upgrades, model overrides, runtime checks, or conservative removal without overwriting unrelated project configuration.
metadata:
  version: "3"
---

# Install Codex Agent Foundry

Use this Skill only to distribute or maintain the Foundry orchestration runtime. The runtime policy itself lives in the bundled project assets and defines how Codex agents collaborate.

Foundry v3 keeps Root as the final owner and uses three narrow project profiles: `explorer` for investigation, `verifier` for bounded noisy/repetitive validation, and `reviewer` for cold review. `worker` remains Codex built-in and on demand.

## Requirements

- Run the installer and verifier with Python 3.11 or newer.
- Ubuntu 22.04 commonly provides Python 3.10 by default; use an explicit Python 3.11+ interpreter there.

Both entry scripts check the interpreter version before importing `tomllib` and return a clear error on older Python versions.

## Workflow

1. Resolve the target repository and inspect existing `AGENTS.md`, `.codex/config.toml`, `.codex/agents/`, and Foundry state.
2. Run `scripts/install.py <target> --check` first. The plan must show every path and the selected Explorer/Reviewer/Verifier model and effort.
3. Explain conflicts. Do not silently overwrite foreign same-name profiles.
4. Apply with `scripts/install.py <target>`, then run `scripts/verify.py <target>`.
5. When requested, run `scripts/verify.py <target> --runtime-check`. It checks Codex CLI/version and configured role models; it does not prove account entitlement or resolved child models.
6. Tell the user to start a new Codex session in the target project.

Model overrides are role-specific:

```bash
scripts/install.py <target>   --explorer-model <model>   --reviewer-model <model>   --verifier-model <model>
```

The default Verifier is `gpt-5.6-luna` / `low`. Spawn persistent Foundry agents by role and let their role profiles own model/reasoning settings; do not pass an explicit spawn-time Luna model merely to restate `verifier.toml`. Some MultiAgent V2 client/model-catalog combinations reject Luna as an explicit spawn-time model override even when a custom role can apply it. If the configured Verifier role itself cannot spawn, use Root for that session or explicitly reinstall/reconfigure with `--verifier-model gpt-5.6-terra`; do not silently fall back to another model.

## Workload-aware runtime rules

- Do not spawn Verifier for one short deterministic command merely to use a cheaper model.
- Use Verifier for long/noisy builds, tests, logs, device/environment checks, waits, or repeated polling that can run independently.
- Prefer minimal-history missions. When supported and self-contained, use `fork_turns = "none"`; if a client release fails no-history task delivery, use the smallest useful last-N history rather than full history.
- Keep the relevant source state stable during same-checkout verification. If Root must keep editing relevant source, use a separate worktree/snapshot; discard validation evidence if its source state changed underneath it.
- Aggregate polling into one bounded shell/program loop when no fresh model judgment is needed per sample.
- Keep large stdout/stderr in files and return bounded evidence plus a log path.
- Avoid deterministic reruns when relevant state has not changed.
- Explorer and Reviewer are behaviorally no-write. Verifier is source-preserving: normal transient build/test artifacts, caches, and designated logs are allowed, but source/project configuration/user content must not be intentionally modified.
- These are behavioral contracts, not independent filesystem sandboxes; hard isolation comes from parent session/runtime permissions.

## Lifecycle safety

- v1 `repo_explorer` migration and v1 uninstall remain supported with frozen v1 fixtures.
- v2 Explorer/Reviewer upgrade and v2 uninstall remain supported with frozen v2 fixtures.
- CI pins hashes for the frozen v1/v2 lifecycle fixtures so accidental historical-template edits fail validation.
- v3 adds `verifier.toml`; a foreign same-name Verifier blocks unless the user explicitly authorizes `--force` backup + replacement.
- Update managed profiles only when ownership is established; preserve unrelated project configuration.
- State records runtime version, role model selections, conservative source revision, and deterministic runtime SHA-256.

For removal, run `scripts/install.py <target> --uninstall --check` before `--uninstall`.

Read `references/design.md` when changing runtime behavior, role identity, model routing, history policy, verification-state ownership, migration semantics, or installer safety guarantees.
