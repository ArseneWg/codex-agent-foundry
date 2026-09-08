# Codex Agent Foundry 中文说明

[English](./README.md) | [简体中文](./README.zh-CN.md)

如果只记住一句话：

> **Codex Agent Foundry 的核心，是用尽量少、职责清晰的 Agent，规范 Codex 在一个代码仓库里怎样协作；能沿用 Codex 原生角色，就不另外发明一套平行角色名。**

它主要解决：

- Root 应该一直负责什么？
- 哪些工作值得交给 Subagent？
- 为什么现在长期保留 Explorer / Verifier / Reviewer？
- Codex 已经有 `explorer` / `worker`，Foundry 应该怎么利用它们？
- 为什么没有常驻 `implementer` / `architect`，以及为什么 Verifier 现在值得长期化？
- 为什么一个 checkout 默认只有一个 writer？
- Explorer 如何控制模型成本？
- 静态配置写了 Terra / medium，和“实际 child 一定用了 Terra / medium”有什么区别？
- v1 的 `repo_explorer` 怎么安全迁移？
- 什么情况下才值得再增加新的长期 Agent？

Installer Skill、升级迁移、冲突保护、验证、测试和 CI，都是为了把这套协作规范安全地分发和维护到不同仓库。

---

## 1. 第一原则：不是 Agent 越多越好

多 Agent 很容易被设计成：

```text
Planner
→ Architect
→ Implementer
→ Tester
→ Reviewer
→ Researcher
→ Root
```

看起来角色很完整，但每增加一个长期 Agent 都有真实成本：

- 上下文要重新转述；
- 结果要重新汇总；
- Agent 之间可能得出冲突结论；
- token、延迟和线程都会增加；
- write ownership 更难判断；
- 自定义 profile 越多，越容易和 Codex 本身重复；
- Codex 升级后维护面更大。

所以 Foundry 只把**高频、边界稳定、隔离后明显有收益**的能力长期化。

当前 baseline：

```text
                         Root
            目标 / 规划 / 集成 / 最终验证
                         │
                 默认 source-code writer
                         │
          ┌──────────────┼──────────────┐
          ▼               ▼              ▼
      explorer         verifier       reviewer
  Terra / medium      Luna / low    GPT-5.6 / high
      不写              不写             不写
          │               │              │
          └───────────────┴──────────────┘
                          ▼
                        Root
                  根据证据做最终判断
```

长期项目级 profile 现在有三个：

- `explorer`：覆盖 Codex 内置同名 Explorer，负责 read-heavy 证据调查；
- `verifier`：低成本执行长时间、noisy、重复性的 build/test/log/wait/device 检查；
- `reviewer`：实现后的独立 cold review。

实现仍由 Root / built-in `worker` 负责；窄范围 research 按需出现。

---

## 2. Foundry 尽量沿用 Codex 原生 vocabulary

Codex 当前已经提供内置 Subagent：

```text
default   → 通用 fallback
worker    → implementation / fixes
explorer  → read-heavy codebase exploration
```

还提供原生：

```text
/review
codex review
```

代码审查工作流。

Foundry 的原则是：

> **如果 Codex 已经有正确的角色概念，就沿用那个角色名；只有需要固定更窄的 model / effort / tools / behavior contract 时，才做项目级覆盖或额外 specialist。**

因此现在不再同时保留：

```text
built-in explorer
+
Foundry repo_explorer
```

而是直接安装：

```text
.codex/agents/explorer.toml
```

当前 Codex 文档明确：项目自定义 Agent 与 built-in 同名时，自定义 Agent 优先。因此 Foundry 的 `explorer.toml` 会覆盖 built-in `explorer`，但 Root/Codex 仍然使用原生角色名 `explorer`。

---

## 3. 为什么长期保留 Explorer + Verifier + Reviewer？

| 工作 | Foundry 选择 | 原因 |
| --- | --- | --- |
| 目标、拆解、架构判断、集成、最终验证 | **Root** | Root 拥有最完整上下文，最终责任不转交 |
| 代码库调查 | **项目级 `explorer` override** | 高频、天然只读、适合并行、隔离收益明显，同时适合独立控制成本 |
| 实现 / 修复 | **Root 默认；built-in `worker` 按需** | Codex 已有 worker，再造 generic implementer 收益低且增加写 ownership |
| 独立 Review | **长期 `reviewer`** | cold context 可以挑战 writer 的原有假设 |
| 单个短小确定性验证 | **Root 直接执行** | 仅为了便宜模型去 spawn，协调成本可能比命令本身更高 |
| 大型/noisy/重复性验证 | **长期 `verifier`** | 稳定的是执行/输出边界：低成本运行、聚合等待、压缩日志、只回传证据 |
| Planner / Architect | **Root** | 高层判断与用户目标强耦合，多一层角色会增加上下文传递和责任模糊 |
| Research | **临时；稳定领域出现后再专门化** | 泛化 researcher 太宽，绑定稳定 MCP/领域后才更值得长期存在 |

关键不是“软件团队里有没有这个职位”，而是：

> **这个任务边界是否稳定？独立 context 是否真的有价值？固定配置是否真的带来收益？**

---

## 4. 为什么直接覆盖 built-in `explorer`？

内置 `explorer` 已经给了正确的角色概念，但 Foundry 希望把它收窄成一个更确定的项目级 contract：

```toml
name = "explorer"
model = "gpt-5.6-terra"
model_reasoning_effort = "medium"
```

同时要求：

```text
追真实 execution path
返回 file / symbol evidence
区分 confirmed facts / hypotheses
找最小修改边界
不改文件
不做 speculative refactor
不递归 spawn
只返回 findings / evidence / risks / unknowns
```

这样有三个直接收益。

### 1）不再创造平行角色名

以前：

```text
built-in explorer
Foundry repo_explorer
```

语义很接近，Root 还要选择到底用谁。

现在：

```text
explorer
→ Codex 原生 vocabulary
→ Foundry 只覆盖成本和输出 contract
```

### 2）Explorer 的成本可以独立控制

Root 可能使用更强、更贵的模型；Explorer 大多数工作是：

```text
grep / symbol lookup
调用链追踪
测试定位
依赖 / ownership 调查
证据收集
```

所以 Foundry 当前固定：

```text
explorer → gpt-5.6-terra / medium
verifier → gpt-5.6-luna / low
reviewer → gpt-5.6 / high
```

而不是用全局：

```toml
[agents]
default_subagent_model = "..."
```

把 `worker` 和其他未 pin 的 Subagent 一起降档。

### 3）行为比泛化 built-in 更稳定

Foundry 明确要求证据导向、不改代码、不递归 delegation。这样 Root 收到的是 investigation evidence，而不是第二个偷偷开始实现的 writer。

需要明确一个边界：当前 Codex 的 agent role 不会把 `sandbox_mode` 应用成独立的 child 文件系统 sandbox。role 可以固定 model / reasoning effort / instructions / features / skills 等受支持字段，但 spawned child 的 permission/sandbox profile 会继承当前 parent session。因此 Explorer / Verifier / Reviewer 的“不写文件”是**行为与编排契约**，不是独立 sandbox 强制。如果需要硬隔离，应在 parent session/runtime 层设置权限。

---

## 5. 一个重要区别：requested model ≠ 已证明的 resolved model

`explorer.toml` 写：

```text
Terra / medium
```

能证明的是：

> **Foundry 请求并配置了 Terra / medium。**

不能仅靠 TOML 证明：

> **你当前安装的每一个 Codex release / execution path 里，实际 spawned child 一定最终 resolved 到 Terra / medium。**

原因是 Subagent model routing 在历史 release 中出现过 bug，不同 Codex 版本的实际行为不能只靠配置文件推断。

所以 Foundry 把两层严格区分：

```text
静态配置验证
→ explorer.toml = Terra / medium

真实运行验证
→ child 最终 resolved model / effort
→ 只有 Codex 提供稳定、机器可读的 spawned-thread metadata 时才能可靠证明
```

现在的：

```bash
verify.py --runtime-check
```

会显示配置中的 Explorer / Verifier / Reviewer model + effort，也会检查 `codex --version`，但会明确写：

```text
resolved child model/effort: not verified
```

Foundry 宁可承认“目前不可观测”，也不把静态配置包装成真实 runtime 保证。

另外，本次迁移**不同时把 medium 改成 low**。角色身份迁移和 reasoning 质量调整是两个变量；如果未来 eval 证明 Terra / low 足够，再单独修改。

---

## 6. 为什么还保留 custom `reviewer`？

Codex 有 `/review`，但两者工作流边界不同。

### `/review` / `codex review`

更像：

```text
人：
“Review 当前 working tree / branch / commit。”
```

这是原生显式 Review workflow。

### Foundry `reviewer`

是 Root 可以嵌进完整多 Agent 流程的节点：

```text
explorer 调查
      ↓
Root / Worker 实现
      ↓
reviewer 独立 cold review
      ↓
Root 消化 findings
      ↓
修复 / 验证 / 收口
```

它在行为上要求不修改文件，并固定强模型/high reasoning，只看 material correctness / regression / security / state / tests 问题，不自己修 finding，也不继续 spawn。

真正价值是：

> **尽量制造一个和 writer 独立的 cold context。**

它不是 `/review` 的替代品；两者是不同入口。

---

## 7. 为什么没有长期 `implementer`？

Codex 已有 built-in `worker`。

更重要的是：实现属于 **write-heavy** 工作。

多个 writer 在同一个 checkout 会增加：

- 写冲突；
- stale context；
- 基于旧代码继续工作；
- ownership 不清；
- merge / integration 成本。

所以：

```text
小型 / 强耦合实现
→ Root 自己写

较大但边界明确
→ built-in worker 可以接管

多个 substantial write 真要并行
→ 分开 Git worktree
```

Worker 只有在 `scope / ownership / behavior / constraints / acceptance / validation` 都清楚时才值得委派。

---

## 8. 为什么现在增加长期 `verifier`？

这不是新增一个“Tester 职位”，而是根据实际 workload 把一个稳定的**执行边界**长期化。

你的审计显示，大量成本来自 shell/read/wait 循环、长会话、build/log 输出、device/sysfs 轮询和 fork 历史继承；测试调用本身并不是主要数量来源。因此 v3 的 Verifier 只负责：

```text
收到明确 command / cwd / stop condition
→ 执行、等待、聚合机械轮询
→ 大日志尽量留文件
→ 返回 PASS/FAIL + exit code + 精简错误 + log path
→ STOP
```

单个短小确定性命令仍由 Root 直接跑。Verifier 默认 `gpt-5.6-luna / low`，只在“长/noisy/重复/可独立运行”时值得 spawn；失败不自己 debug、不改代码，证据交回 Root。若某个 Codex release 不允许 child 使用 Luna，可用 `--verifier-model gpt-5.6-terra` 覆盖，不能为了省成本全局降低所有 Subagent。

### 最小历史 + 输出预算

自包含的 Explorer / Verifier / Reviewer mission，在客户端可靠支持时优先 `fork_turns = "none"`；确实依赖历史时只给最小 last-N；full history 是例外。如果特定 release 的 no-history task delivery 有 bug，就退到最小可用 last-N，不默认回到全部历史。

机械轮询应尽量合并进一次有界 shell/program loop；大 build/test/log 输出留在文件，只回传证据和路径；同一 deterministic validation 在 relevant state 没变化时不应重复执行。

完成大 milestone 或多次 compaction 后，Root 应 checkpoint：目标、决策、改动文件、验证结果、blocker、下一步。如果旧 tool history 已明显主导上下文，优先新 session 从 checkpoint 继续。

---

## 9. 为什么 Planner / Architect 留在 Root？

Root 拥有：

```text
用户目标
+ 对话历史
+ requirements
+ repository evidence
+ Subagent 结果
+ 实现状态
+ final diff
+ tests / build / logs
```

如果强制：

```text
User → Root → Planner → Architect → Worker → Reviewer → Root
```

会增加上下文转述，也会让“谁负责最终判断”变模糊。

所以 Foundry 选择：

> **高层判断留在拥有最多上下文的 Root；Subagent 主要提供隔离证据、独立判断和边界明确的执行。**

---

## 10. 更深层原则：Read 并发便宜，Write 并发昂贵

行为上 no-write 的 Agent 可以独立收集证据，不应修改共享 source state；主要成本只是 Root 最后汇总。这里的 no-write 是编排契约，不是独立 per-role sandbox 保证。

Write-heavy Agent 则额外需要处理：

```text
state coordination
stale assumptions
ownership
merge / integration
```

因此：

- 一个 checkout 同时只有一个 source-code writer；
- read-only Agent 可以并行；
- substantial parallel writes 使用不同 worktree；
- Root 最终负责 integration。

这也是为什么长期 Agent 名额优先给 Explorer / Reviewer 这类只读 specialist。

---

## 11. 什么情况下才新增第三个长期 Agent？

最好满足大部分条件：

1. **高频**：很多重要任务反复需要；
2. **边界稳定**：Mission 能长期写得很窄；
3. **可重复收益**：不是一次性便利；
4. **隔离有价值**：独立 context 真能改善质量或减少噪声；
5. **固定配置有意义**：model / effort / MCP / tools / skills 等当前真正受支持的 role 设置值得固定；
6. **ownership 清楚**：不会制造不必要的 writer 冲突；
7. **built-in / temporary delegation 不够**：确实存在稳定 specialization；
8. **可以 eval**：能写场景说明什么时候该调用、改善了什么。

可能合理的未来角色：browser debugger、绑定稳定 docs MCP 的 docs researcher、特殊 security/database specialist。

默认不因为名字听起来像软件团队职位，就加入 `architect / implementer / tester / researcher`。

---

## 12. Runtime 最重要的规则

真正的 policy 在：

[`runtime/AGENTS.fragment.md`](./runtime/AGENTS.fragment.md)

核心规则：

1. Root 保留目标、拆解、架构、集成、最终验证和最终答案。
2. Root 默认写代码。
3. 一个 checkout 同时一个 writer。
4. substantial parallel writes 用不同 worktree。
5. 默认一层 fan-out / fan-in。
6. Subagent 默认不继续递归 spawn，除非 Root 为具体 mission 明确授权。
7. 每个 delegated mission 至少说明 goal、scope/ownership、constraints、acceptance evidence、expected return、stop condition。
8. Agent 互相同意不等于正确，最终回到 diff / tests / build / logs / source / reproduction 等证据。

`evals/scenarios.json` 当前表达：

```text
很小、范围明确的修改
→ Root only

跨模块 bug，execution path 不清楚
→ explorer → Root 实现 → reviewer

边界清楚的机械实现
→ worker 可实现 → reviewer → Root 验证

大型 / noisy verification
→ 临时 verifier

两个 substantial write 要并行
→ 分开 worktree
```

---

## 13. 仓库结构

```text
codex-agent-foundry/
├── runtime/                       # 核心产品 / 唯一 source of truth
│   ├── AGENTS.fragment.md
│   └── .codex/
│       ├── config.toml
│       └── agents/
│           ├── explorer.toml      # 覆盖 Codex built-in explorer
│           └── reviewer.toml
├── evals/                         # policy contract
├── .agents/skills/
│   └── install-codex-agent-foundry/
│       ├── SKILL.md
│       ├── scripts/install.py
│       ├── scripts/verify.py
│       ├── assets/project/        # runtime/ 自动生成发布副本
│       └── references/design.md
├── scripts/package_runtime.py
├── tests/
├── .github/workflows/test.yml
└── AGENTS.md                      # 开发 Foundry 自己时使用
```

`runtime/` 与 `assets/project/` 的重复是有意的：

```text
runtime/                         ← 人修改的 source
   ↓ package_runtime.py
Skill/assets/project/            ← 自动生成的 distribution copy
```

只有 `runtime/` 是 source of truth。

---

## 14. Python 版本要求

Installer 和 verifier 要求 **Python 3.11+**，因为使用标准库 `tomllib`。

Ubuntu 22.04 默认常见是 Python 3.10。两个入口脚本都会在导入 `tomllib` 前检查版本，因此旧版本会得到清晰提示，而不是：

```text
ModuleNotFoundError: No module named 'tomllib'
```

---

## 15. 安装 / 更新

先 dry-run：

```bash
python3 .agents/skills/install-codex-agent-foundry/scripts/install.py \
  /path/to/repo \
  --check
```

PLAN 顶部会显示：

```text
Selected agents:
- explorer: gpt-5.6-terra / medium
- reviewer: gpt-5.6 / high
- verifier: gpt-5.6-luna / low
```

确认后安装并验证：

```bash
python3 .agents/skills/install-codex-agent-foundry/scripts/install.py /path/to/repo
python3 .agents/skills/install-codex-agent-foundry/scripts/verify.py /path/to/repo
```

安装成功后会提示：

```text
Start a new Codex session in this project to load Foundry.
```

新安装目标项目大致是：

```text
your-project/
├── AGENTS.md
└── .codex/
    ├── config.toml
    ├── .agent-foundry.json
    └── agents/
        ├── explorer.toml
        ├── reviewer.toml
        └── verifier.toml
```

### 模型覆盖

```bash
python3 .../install.py /path/to/repo \
  --explorer-model <model> \
  --reviewer-model <model> \
  --verifier-model <model>
```

选择会写进 state，后续 update 会保留，除非显式换模型。

---

## 16. v1 升级：`repo_explorer` → `explorer`

Foundry v1 安装的是：

```text
.codex/agents/repo_explorer.toml
```

v2 改成：

```text
.codex/agents/explorer.toml
```

不是简单 rename，而是 ownership-safe migration。

Installer 会：

- 从 v1 state 读取旧 Explorer model override，并迁移到新 `explorer`；
- 只有旧 `repo_explorer.toml` 仍然是 Foundry-managed、且内容和旧 state 记录完全一致时才删除；
- 如果旧 profile 被用户改过，整个 PLAN 阻塞，零写入；
- 如果已经有用户自己的 `explorer.toml`，默认整个 PLAN 阻塞；
- 只有用户明确 `--force` 时，才 backup foreign `explorer.toml` 后接管；
- 如果没有匹配的 v1 state，只有带 Foundry 管理标记的 orphan `repo_explorer.toml` 才会阻塞人工检查；用户自己的同名 legacy 文件会保留且不影响 v2；
- v1 uninstall 仍然支持，并使用 Installer Skill 内冻结的 v1 profile fixture 校验旧文件。

已有 Foundry v2 的项目不需要角色 rename：Installer 会用冻结的 v2 Explorer/Reviewer fixture 校验 ownership 和 drift，保留两个模型 override，再新增 `verifier.toml`。如果 v2 profile 已被修改则整个升级阻塞；v2 uninstall 仍支持，而且不会认领一个 foreign `verifier.toml`。

所以升级前仍然先运行：

```bash
python3 .../install.py /path/to/repo --check
```

### State v3

新的 state 语义：

```json
{
  "version": 3,
  "runtime_version": "3",
  "managed_agents": ["explorer.toml", "reviewer.toml", "verifier.toml"],
  "models": {
    "explorer": "gpt-5.6-terra",
    "reviewer": "gpt-5.6",
    "verifier": "gpt-5.6-luna"
  },
  "source_revision": "...",
  "runtime_sha256": "..."
}
```

`source_revision` 采用保守证明：只有 Installer 能确认自己运行在干净的 Foundry checkout 中，并且 `runtime/` 与打包 assets 一致时才记录 commit；Skill 被复制进普通目标 Git 仓库时会写 `unknown`，不会误记目标项目的 commit。`runtime_sha256` 是确定性的 Runtime 内容指纹，在无法证明 Git 来源时仍是权威依据。

---

## 17. 验证

普通验证：

```bash
python3 .../verify.py /path/to/repo
```

检查 managed paths、state schema、AGENTS managed block、TOML、profile/model override 和 drift。

额外环境检查：

```bash
python3 .../verify.py /path/to/repo --runtime-check
```

还会检查：

- `codex` 是否在 PATH；
- `codex --version`；
- 本地 config/profile 严格 TOML 解析；
- Explorer / Reviewer 配置中的 model + reasoning effort。

但明确**不会声称**已经验证：

- 账户一定能用这些模型；
- 新 Codex session 已成功加载全部项目配置；
- 实际 spawned Explorer child 最终 resolved 到配置中的 model/effort。

最后一项只有在 Codex 提供稳定可观测的 spawned-thread runtime metadata 后，才能可靠做成硬验证。

---

## 18. 卸载

```bash
python3 .../install.py /path/to/repo --uninstall --check
python3 .../install.py /path/to/repo --uninstall
```

卸载只处理 Foundry-owned 内容，保留无关项目配置；managed profile 如果 drift，会拒绝删除。v1 state 的卸载也继续支持。

---

## 19. 开发与验证

修改协作行为时先改 `runtime/`；routing 预期变化时同步改 `evals/`。

```bash
python3 scripts/package_runtime.py
python3 scripts/package_runtime.py --check
python3 -m unittest discover -s tests -v
python3 -m compileall -q .agents/skills/install-codex-agent-foundry/scripts scripts tests
```

CI 在 Python 3.11 / 3.12 / 3.13 跑完整测试，并额外用 Python 3.10 验证版本提示。

完整设计记录：[`references/design.md`](./.agents/skills/install-codex-agent-foundry/references/design.md)

官方参考：[Subagents](https://developers.openai.com/codex/subagents) · [Developer commands / review](https://developers.openai.com/codex/cli/slash-commands) · [Build skills](https://developers.openai.com/codex/skills)
