# Codex Agent Foundry

[English](README.md) | [简体中文](README.zh-CN.md)

面向 Codex 的小型仓库级协作规范。Root 保留决策和最终责任，子 Agent 提供范围明确的证据或实现。Installer 负责分发与维护，不是另一套编排框架。

## 角色

| 角色 | 默认模型 / 推理强度 | 职责 |
| --- | --- | --- |
| Root | 当前会话 | 规划、默认实现、集成、验证、最终答复。 |
| `explorer` | `gpt-5.6-terra` / `medium` | 不改文件，追踪调用链、依赖和测试；区分事实与假设。覆盖 Codex 内置同名角色。 |
| `reviewer` | `gpt-5.6-terra` / `high` | 独立冷审实质性正确性、回归、安全、状态与测试风险。 |
| `verifier` | `gpt-5.6-luna` / `low` | 执行长时间或高输出验证，聚合等待/轮询，返回精简证据和日志；不自行诊断、修复。 |
| 内置 `worker` | 随任务确定 | 仅在修改范围、独占写入权和验收标准明确时承担实现。 |

短命令留给 Root；只有隔离或并行收益超过交接成本时才派发。规划、架构留在 Root，研究按需进行，不增加常驻 Planner/Dispatcher。新增长期角色必须有高频窄任务、可验证收益、清晰边界，并且现有角色不足以承担。

Foundry Reviewer 用于完整任务中的独立审查；原生 `/review`、`codex review` 仍适合用户主动发起的代码审查。价值是独立上下文，不是多一个角色名字。

## 运行规则

唯一规范源是 [runtime/AGENTS.fragment.md](runtime/AGENTS.fragment.md)。

Root 每次派发前按角色检查 Mission。使用自然语言，不要求 JSON。已有事实可自动补齐；无法确认的安全关键条件不能猜，任务暂留 Root。Reviewer 输出格式和 Verifier 结果协议由 profile 提供，无需每次复述。

一个 checkout 同时只有一个源码 writer。Worker 独占时 Root 不并行编辑；大规模并行写入使用不同 worktree。验证必须绑定稳定源码；Root 需要继续编辑时，验证使用独立 worktree/snapshot，源码变化后旧证据作废。Explorer/Reviewer 不编辑；Verifier 只允许约定的临时构建产物、缓存和日志，不得主动修改源码、配置或用户内容。这些是行为规则，不是独立文件系统 sandbox。

按 `agent_type` 选择长期角色，不重复传模型/推理参数。自包含任务在客户端支持且可靠时优先 `fork_turns="none"`，否则只传最小必要历史。大输出留文件，机械轮询合并执行，不无故重复验证，长会话保留 checkpoint。

派发结果为 PASS，必须同时有工具退出码 0 和最后由 wrapper 生成的 `FOUNDRY_RESULT_V1 exit_code=0 status=PASS`。证据缺失或矛盾只能是 INDETERMINATE。Root 必须读取对应日志并确认验证范围和最终源码状态；footer 不能单独证明所有预期步骤都执行了。Agent 结论一致不等于正确。

## 安装、更新、卸载

维护脚本要求 **Python 3.11+**。系统 `python3` 较旧时，显式使用已有的 3.11+ 解释器。两个入口会在导入 `tomllib` 前给出版本错误。

在 Foundry checkout 中执行：

```bash
SKILL=.agents/skills/install-codex-agent-foundry
python3 "$SKILL/scripts/install.py" /path/to/repo --check
python3 "$SKILL/scripts/install.py" /path/to/repo
python3 "$SKILL/scripts/verify.py" /path/to/repo
```

先检查计划中的模型、推理强度、所有改动、备份及冲突，再应用。目标仓库安装 AGENTS 管理区块、`.codex/config.toml`、三个 `.codex/agents/*.toml` 及 `.codex/.agent-foundry.json`。完成后在目标仓库启动**新 Codex 会话**。

模型覆盖只影响对应角色：

```bash
python3 "$SKILL/scripts/install.py" /path/to/repo \
  --explorer-model <model> --reviewer-model <model> --verifier-model <model>
```

选择保存在 state 中。未显式指定 Reviewer 模型时，历史值 `gpt-5.6` 会迁至当前默认值；其他模型选择保留。Luna Verifier 无法启动时，由 Root 本次执行验证，或显式改为 `--verifier-model gpt-5.6-terra`。不静默换模型，也不全局降低子 Agent 模型。实际可用性取决于账户和客户端，配置不等于权限证明。

卸载同样先预览：

```bash
python3 "$SKILL/scripts/install.py" /path/to/repo --uninstall --check
python3 "$SKILL/scripts/install.py" /path/to/repo --uninstall
```

外部同名 profile 默认阻塞安装；只有明确授权 `--force` 才备份后替换。模型参数是受支持的定制方式；其他 managed 文件的手工修改需在更新前检查。卸载会拒绝删除已漂移的 profile。边界见 [生命周期说明](.agents/skills/install-codex-agent-foundry/references/design.md)。

## 迁移与来源

v1 的 `repo_explorer` 迁为 `explorer`；v2 升级增加 Verifier。v1/v2 历史模板保持原样，并以固定哈希保护，供 ownership、drift 和卸载检查使用。漂移阻塞迁移，不能修改历史模板来“修好”测试。

State v3 记录角色/模型、并发配置归属、runtime 版本、`source_revision` 和 `runtime_sha256`。只有干净的 Foundry checkout 且 runtime 与发布副本一致时才记录 revision；复制安装的 Skill 记为 `unknown`，不会误记目标仓库提交。无法证明 Git 来源时，以内容哈希为准。

## 验证边界

`verify.py` 检查路径、state、TOML、profile 和漂移；`--runtime-check` 额外检查 Codex CLI/version 并报告配置模型。它们不证明账户可用性、新会话加载成功、实际 child 模型，或目标项目构建通过。

[Forward eval](evals/README.md) 才检查实际角色派发、ownership、Mission 和验证证据。CI 不能替代真实模型验证。

## 开发

| 路径 | 用途 |
| --- | --- |
| `runtime/` | 安装到项目的规范和角色配置源。 |
| `.agents/skills/install-codex-agent-foundry/` | 维护流程、脚本、历史模板、生成的 `assets/project/`。 |
| `evals/` | 行为场景和评估方法。 |
| `scripts/`、`tests/`、`.github/workflows/` | 打包、回归测试、CI。 |
| 根 `AGENTS.md` | 开发 Foundry 自身的规则，不是分发的运行规则。 |

只改 `runtime/`，再生成发布副本，不独立编辑 assets。精简时保留完整安全条件；[设计理由](.agents/skills/install-codex-agent-foundry/references/design.md) 按需阅读，不要求每次会话加载。

```bash
python3 scripts/package_runtime.py
python3 scripts/package_runtime.py --check
python3 -m unittest discover -s tests -v
python3 -m compileall -q .agents/skills/install-codex-agent-foundry/scripts scripts tests
```

CI 覆盖 Python 3.11/3.12/3.13，另用 3.10 检查版本保护。静态契约、提示词大小和脚本测试不代表真实 Agent 行为已经验证。

官方参考：[Subagents](https://developers.openai.com/codex/subagents) · [AGENTS.md](https://developers.openai.com/codex/guides/agents-md) · [Skills](https://developers.openai.com/codex/skills) · [Review](https://developers.openai.com/codex/cli/slash-commands)
