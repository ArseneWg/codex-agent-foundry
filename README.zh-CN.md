# Codex Agent Foundry 中文说明

[English](./README.md) | [简体中文](./README.zh-CN.md)

如果只记住一句话：

> **Codex Agent Foundry 的核心，是用尽量少、职责清晰的 Agent，规范 Codex 在一个代码仓库里怎样协作，而不是尽可能多地创建 Agent。**

它主要回答：

- Root 应该一直负责什么？
- 哪些工作值得交给 Subagent？
- 为什么长期只有 Explorer 和 Reviewer？
- Codex 已经有 `worker` / `explorer`，为什么还要自定义 Agent？
- Codex 已经有 `/review`，为什么还要 `reviewer`？
- 为什么没有常驻 `implementer`、`tester`、`architect`？
- 为什么一个 checkout 默认只有一个 writer？
- 什么情况下才值得新增第三个长期 Agent？
- 最后凭什么判断任务真的完成？

Installer Skill、安装脚本、升级、冲突保护、验证、测试和 CI，都是为了安全地分发和维护这套协作规范。

---

## 1. 第一原则：不是 Agent 越多越好

很容易把多 Agent 系统设计成：

```text
Planner
→ Architect
→ Implementer
→ Tester
→ Reviewer
→ Researcher
→ Root
```

看起来角色很完整，但每增加一个长期 Agent 都会产生真实成本：

- 上下文要重新转述；
- 结果要重新汇总；
- Agent 之间可能得出冲突结论；
- token、延迟、线程都会增加；
- write ownership 更难判断；
- 自定义 profile 越多，越容易和 Codex 自带能力重复；
- Codex 自身升级后维护面也更大。

Foundry 因此只把**高频、稳定、隔离后明显有收益**的工作长期化。

当前 baseline：

```text
                         Root
            目标 / 规划 / 集成 / 最终验证
                         │
                 默认 source-code writer
                         │
          ┌──────────────┴──────────────┐
          ▼                             ▼
  repo_explorer                     reviewer
  Terra / medium                  GPT-5.6 / high
      只读                            只读
          │                             │
          └──────────────┬──────────────┘
                         ▼
                       Root
                 根据证据做最终判断
```

长期 Custom Agent 只有两个：

- `repo_explorer`：read-heavy 调查；
- `reviewer`：material implementation 后的独立冷 Review。

实现、验证、研究默认按需出现。

---

## 2. Foundry 不是从“Codex 什么都没有”开始设计

当前 Codex 官方文档已经提供内置 Subagent：

```text
default   → 通用 fallback
worker    → implementation / fixes
explorer  → read-heavy codebase exploration
```

Codex 还有原生：

```text
/review
codex review
```

代码审查工作流。

所以 Foundry 的规则是：

> **能直接利用 Codex 内置能力，就不重复造泛化角色；只有需要更窄、更稳定的行为契约时，才做 Custom Agent。**

官方参考：[Subagents](https://developers.openai.com/codex/subagents) · [Developer commands / review](https://developers.openai.com/codex/cli/slash-commands)

---

## 3. 为什么恰好长期保留两个 Agent？

| 工作 | Foundry 选择 | 原因 |
| --- | --- | --- |
| 目标、拆解、架构判断、集成、最终验证 | **Root** | Root 拥有最完整上下文，最终责任不转交 |
| 代码库调查 | **长期 `repo_explorer`** | 高频、天然只读、适合并行、隔离收益明显 |
| 实现 / 修复 | **Root 默认；内置 `worker` 按需** | Codex 已有 worker，没必要再造 generic implementer |
| 独立 Review | **长期 `reviewer`** | 冷上下文可以挑战 writer 原有假设，并能嵌入完整工作流 |
| 大型测试 / log / diagnostics | **临时 verifier** | 验证方式高度项目相关，generic tester 稳定价值不高 |
| Planner / Architect | **Root** | 高层判断与用户目标强耦合，额外角色增加上下文传递和责任模糊 |
| Research | **临时；稳定领域出现后再专门化** | 泛化 researcher 太宽，绑定稳定领域/MCP 时才更值得长期存在 |

核心不是“角色名字”，而是：

> **这个任务边界是否稳定？独立 context 是否真的有价值？**

---

## 4. 已经有内置 `explorer`，为什么还有 `repo_explorer`？

这是一个**有意接受的功能重叠**。

内置 `explorer` 已经适合普通 read-heavy 调查；Foundry 的 `repo_explorer` 则固定更窄的契约：

```text
read-only sandbox
固定 model / reasoning effort
追真实 execution path
返回 file / symbol evidence
区分 confirmed facts 与 hypotheses
找最小修改边界
不改文件
不做 speculative refactor
不继续 spawn
只返回 findings / evidence / risks / unknowns
```

收益是行为更稳定、明确只读、Root 更容易消费结果，也可以固定更合适的模型成本。代价是和内置 explorer 有一定功能重复，并且多维护一个 profile。

所以 `repo_explorer` 不是不可删除的。如果未来内置 explorer 已充分满足这些约束，**删掉自定义 explorer 反而可能是更好的简化**。

---

## 5. 已经有 `/review`，为什么还有 `reviewer`？

两者目标重叠，但工作流边界不同。

### `/review` / `codex review`

适合用户明确提出：

```text
“Review 当前 working tree / branch / commit。”
```

这是 Codex 原生 Review 工作流，不需要为了 Foundry 而替换。

### Foundry `reviewer`

它是 Root 可以在完整多 Agent 流程里主动 spawn 的节点：

```text
repo_explorer 调查
       ↓
Root / Worker 实现
       ↓
reviewer 独立冷 Review
       ↓
Root 消化 findings
       ↓
必要时修改 + 验证 + 收口
```

它固定 read-only、独立 model / reasoning effort，只找 material correctness / regression / security / state / tests 问题，不自己修 finding，也不继续 spawn。

真正的价值不是“多一个 Agent 更聪明”，而是：

> **制造一次尽量独立于 writer 的 cold context。**

Foundry 接受它和 `/review` 有功能重叠，因为它支持**自主编排中的 in-flow review**。它不是 `/review` 的替代品。

---

## 6. 为什么没有长期 `implementer`？

首先，Codex 已经有内置 `worker`，就是用于 implementation / fixes 的。

更重要的是：**实现属于 write-heavy 工作。**

多个 writer 在同一个 checkout 里可能造成写冲突、stale context、基于旧代码继续工作、ownership 不清，以及高昂的整合成本。

所以默认：

```text
小型 / 强耦合实现
→ Root 自己写

较大但边界明确的实现
→ 内置 worker 可以接管

多个 substantial write 真要并行
→ 分开 Git worktree
```

Worker 只有在 `scope / ownership / behavior / constraints / acceptance / validation` 清楚时才值得委派。

这牺牲一部分最大并发，换取更清晰的 ownership 和更少的写冲突。

---

## 7. 为什么没有长期 `tester`？

“测试”不是一个稳定统一的跨项目角色，它可能是 unit test、integration test、compiler diagnostics、browser reproduction、CI logs、benchmark、migration validation 或 flaky test triage。

一个 generic `tester.toml` 最后往往只是“跑测试并汇报”，专门化价值很低。

Foundry 因此选择：

```text
小型 / 关键验证
→ Root

大型 / noisy / 独立验证
→ 临时 verifier

反复出现的特殊验证能力
→ 再考虑真正的 Custom Agent
```

例如一个有稳定 browser tooling 的 `browser_debugger`，就比 generic `tester` 更值得长期存在。

---

## 8. 为什么没有 Planner / Architect？

Root 拥有最完整的信息：用户目标、对话历史、requirements、repository evidence、Subagent 结果、实现状态、final diff、tests / build / logs。

如果强制变成：

```text
User → Root → Planner → Architect → Worker → Reviewer → Root
```

会增加上下文转述，并让“谁负责最终判断”更模糊。

Foundry 选择：

> **高层判断留在拥有最多上下文的 Root；Subagent 主要用于隔离证据、独立判断和边界明确的执行。**

---

## 9. Research 为什么默认临时？

偶尔查文档或背景资料时，临时 research 足够。真正值得长期存在的通常类似 `docs_researcher + 固定 docs MCP + 明确领域 + 稳定返回证据格式`。

也就是：

> **长期 Agent 应围绕稳定能力建立，而不是围绕宽泛职位名称建立。**

---

## 10. 更深层原则：Read 并发便宜，Write 并发昂贵

Read-only Agent 可以独立收集证据，不修改共享 source state，也不会互相覆盖；主要成本只是 Root 最后汇总。

Write-heavy Agent 则额外需要处理 state coordination、stale assumptions、ownership、merge / integration。

因此 Foundry 更愿意把**长期 Agent 名额给只读 specialist**，写 Agent 按需出现。

---

## 11. 什么情况下才新增第三个长期 Agent？

新 persistent agent 最好满足大部分条件：

1. **高频**：很多重要任务反复需要；
2. **边界稳定**：Mission 可以长期写得很窄、很清楚；
3. **可重复收益**：不是一次性便利；
4. **隔离有价值**：独立 context 能改善质量或减少噪声；
5. **固定配置有意义**：model / effort / sandbox / MCP / tools / skills 值得固定；
6. **ownership 清楚**：不会制造多余 writer 冲突；
7. **内置能力不够**：built-in agent 或临时 delegation 不足以表达 specialization；
8. **可以 eval**：能写场景说明什么时候该调用、改善了什么。

可能合理的未来角色包括 browser debugger、绑定稳定 docs MCP 的 docs researcher、特殊安全流程的 security specialist，或长期复杂数据库项目里的 DB specialist。

默认不因为名字听起来合理就加入 `architect / implementer / tester / researcher`。

---

## 12. Foundry 主动接受哪些妥协？

| 选择 | 收益 | 代价 |
| --- | --- | --- |
| 少量长期 Agent | 简单、易理解、易维护 | 特殊项目不够细分 |
| Custom `repo_explorer` | 固定窄行为和 sandbox/model contract | 与 built-in explorer 重叠 |
| Custom `reviewer` + 原生 `/review` | 同时支持显式 Review 和自主 cold review | 两套能力部分重叠 |
| 一个 checkout 一个 writer | ownership 清晰，减少 stale write | 牺牲部分 write parallelism |
| 默认一层 fan-out / fan-in | 流程容易理解和收口 | recursive delegation 需要 Root 授权 |
| Planner / Architect 留 Root | 减少上下文转述和责任分裂 | baseline 不强制第二套高层意见 |

这些是默认值，不是不可修改的真理。如果长期 evidence 表明另一种结构更好，就应该演进。

---

## 13. Evals 如何表达这些设计？

`evals/scenarios.json` 当前表达：

```text
很小、范围明确的修改
→ Root only

跨模块 bug，execution path 不清楚
→ repo_explorer → Root 实现 → reviewer

边界清楚的机械实现
→ built-in worker 可实现 → reviewer → Root 验证

大型 / noisy verification
→ 临时 verifier

两个 substantial write 要并行
→ 分开 worktree，不在同一 checkout 多 writer
```

Evals 不是硬编码路由器，而是 policy 的方向性 contract：防止未来修改时设计悄悄跑偏。

---

## 14. 最重要的运行时规则

1. **Root 保留最终责任**：目标、拆解、集成、最终验证、最终答案都由 Root 收口。
2. **Root 默认写代码**：delegated write 是可选优化，不是固定流程。
3. **一个 checkout 同时一个 source-code writer**。
4. **substantial parallel writes 使用不同 worktree**。
5. **默认一层 fan-out / fan-in**，Subagent 不自行递归 spawn。
6. **只有 delegation 真正带来收益时才委派**。
7. **每个 Subagent 都拿明确 Mission Contract**。
8. **Agent 互相同意不等于正确**，最终回到 diff / tests / build / logs / source / reproduction 等证据。

真正的 runtime policy：[`runtime/AGENTS.fragment.md`](./runtime/AGENTS.fragment.md)

完整设计记录：[`.agents/skills/install-codex-agent-foundry/references/design.md`](./.agents/skills/install-codex-agent-foundry/references/design.md)

---

## 15. 仓库结构：核心产品、交付层、质量层

```text
codex-agent-foundry/
├── runtime/                       # 核心产品 / 唯一 source of truth
│   ├── AGENTS.fragment.md
│   └── .codex/agents/
│       ├── repo_explorer.toml
│       └── reviewer.toml
├── evals/                         # policy contract
├── .agents/skills/
│   └── install-codex-agent-foundry/
│       ├── SKILL.md
│       ├── scripts/install.py
│       ├── scripts/verify.py
│       ├── assets/project/        # runtime/ 生成发布副本
│       └── references/design.md
├── scripts/package_runtime.py
├── tests/
├── .github/workflows/test.yml
└── AGENTS.md                      # 开发 Foundry 自己时使用
```

`runtime/` 与 `assets/project/` 重复是有意的：

```text
runtime/                         ← 人修改的源码
   ↓ package_runtime.py
Skill/assets/project/            ← 自动生成的分发副本
```

只有 `runtime/` 是 source of truth；不要手工修改生成副本。

---

## 16. Python 版本要求

Installer 和 verifier 要求 **Python 3.11+**，因为使用标准库 `tomllib`。

Ubuntu 22.04 默认通常还是 Python 3.10。如果机器上的 `python3` 指向 3.10，请显式使用 Python 3.11 或更新版本。

两个入口脚本都会在导入 `tomllib` **之前**检查 Python 版本，所以旧版本会得到清晰提示，而不是：

```text
ModuleNotFoundError: No module named 'tomllib'
```

---

## 17. 安装与验证

```bash
# 只看完整计划，不写文件；这里也会显示最终选中的模型 / reasoning effort
python3 .agents/skills/install-codex-agent-foundry/scripts/install.py /path/to/repo --check

# 安装
python3 .agents/skills/install-codex-agent-foundry/scripts/install.py /path/to/repo

# 本地确定性验证：文件、state、TOML、profile、drift
python3 .agents/skills/install-codex-agent-foundry/scripts/verify.py /path/to/repo
```

安装成功后会提示：

```text
Start a new Codex session in this project to load Foundry.
```

这是因为项目级 `AGENTS.md` 和 `.codex/agents/` 应从一个新的 Codex 会话完整加载。

Installer 使用 **Plan → Apply**：冲突会在写入前阻塞；中途失败会回滚已经修改的路径。

幂等 dry-run 的文案也会反映“当前已一致”，例如：

```text
unchanged AGENTS.md: managed block already current
```

### dry-run 直接显示模型选择

PLAN 顶部会显示类似：

```text
Selected agents:
- repo_explorer: gpt-5.6-terra / medium
- reviewer: gpt-5.6 / high
```

这样用户可以在写文件前确认配置是否符合预期。但这**不代表账户一定有这些模型的使用权限**。

### 可选 `--runtime-check`

如果希望再检查本机 Codex 环境：

```bash
python3 .agents/skills/install-codex-agent-foundry/scripts/verify.py \
  /path/to/repo \
  --runtime-check
```

它额外检查：

- `codex` 是否在 `PATH`；
- `codex --version` 是否能正常执行；
- 项目 config 和 Foundry profile 是否通过严格 TOML 解析；
- 当前 Explorer / Reviewer 的 model + reasoning effort；
- 明确提示 **账户模型可用性尚未验证**。

目前 Foundry 不依赖未公开或不稳定的非交互 config-validation 命令，因此不会把这个检查包装成“Codex 已真实加载全部配置”的强保证。

### 状态文件记录来源信息

`.codex/.agent-foundry.json` 现在额外记录：

```json
{
  "runtime_version": "1",
  "source_revision": "<git-commit-or-unknown>",
  "runtime_sha256": "<deterministic-runtime-content-hash>"
}
```

其中：

- `runtime_version`：Foundry Runtime 版本；
- `source_revision`：如果 Installer 位于 Git checkout 中，记录 Git commit；如果 Skill 被单独分发、不带 `.git`，可能是 `unknown`；
- `runtime_sha256`：对打包 Runtime 文件做确定性 SHA-256，作为更可靠的内容指纹。

因此即使 `source_revision = unknown`，仍然可以通过 `runtime_sha256` 做升级、审计和问题复现。

旧的 state 仍能被 Installer 读取并升级；如果 verifier 发现缺少 provenance 字段，会提示重新运行 installer 刷新 metadata。

需要时可以覆盖模型：

```bash
python3 .../install.py /path/to/repo \
  --explorer-model <model> \
  --reviewer-model <model>
```

卸载：

```bash
python3 .../install.py /path/to/repo --uninstall --check
python3 .../install.py /path/to/repo --uninstall
```

---

## 18. 开发 Foundry

修改协作行为时先改 `runtime/`；如果预期路由变化，也同步更新 `evals/`。

```bash
python3 scripts/package_runtime.py
python3 scripts/package_runtime.py --check
python3 -m unittest discover -s tests -v
python3 -m compileall -q .agents/skills/install-codex-agent-foundry/scripts scripts tests
```

CI 会在 Python 3.11 / 3.12 / 3.13 上运行完整测试，并额外用 Python 3.10 验证版本 guard 会给出清晰错误而不是 traceback。

---

## 19. 最后一张图

```text
Root
├── 目标 / 架构 / 集成 / 最终责任
├── 默认 writer
│
├── repo_explorer      ← 长期、只读、证据调查
├── reviewer           ← 长期、只读、独立 cold review
│
├── built-in worker    ← 按需、边界明确时实现
├── temp verifier      ← 按需、noisy validation
└── temp research      ← 按需；稳定 specialization 出现后才长期化

多 substantial writers
→ 不共享 checkout
→ Git worktrees
```

这就是 Foundry 当前最核心的设计取舍。

官方参考：[Subagents](https://developers.openai.com/codex/subagents) · [Developer commands / review](https://developers.openai.com/codex/cli/slash-commands) · [Build skills](https://developers.openai.com/codex/skills)
