# Codex Agent Foundry 中文说明

[English](./README.md) | [简体中文](./README.zh-CN.md)

如果你刚开始用 Codex，可以先记住一句话：

> **Codex Agent Foundry 的核心，是规范 Codex 在一个代码仓库里应该怎样进行多 Agent 协作。**

它不是为了“多开几个 Agent”，而是解决这些更实际的问题：

- Root Agent 应该一直负责什么？
- 什么时候值得调用 Explorer？
- 什么时候需要独立 Reviewer？
- 什么任务才适合临时 Worker / Tester？
- 多个 Agent 能不能同时修改同一个 checkout？
- 什么情况下应该使用 Git worktree？
- Subagent 能不能继续创建 Subagent？
- 一个委派任务至少应该说明哪些边界？
- 最后凭什么判断“任务真的完成了”？

Installer Skill、安装脚本、升级、冲突保护、验证、测试和 CI，都是为了**把这套协作规范安全地分发和维护到不同代码仓库里**。

---

## 1. 默认协作模型

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

Foundry 默认只长期配置两个专职 Subagent。

### `repo_explorer`

负责 **read-heavy 调查**，例如：

- 找真正的代码入口；
- 追调用链；
- 找测试和依赖；
- 判断模块边界；
- 找最小修改范围；
- 收集实现前证据。

它默认只读，不负责直接修代码。

### `reviewer`

负责实现完成后的 **独立冷 Review**，重点看：

- correctness；
- regression；
- security；
- concurrency / state 风险；
- 边界条件；
- 真正重要的测试缺口。

它同样默认只读，发现问题后把证据交回 Root，而不是自己偷偷修改。

### 临时 Worker / Verifier

不是常驻角色。

只有当任务边界足够明确，或者测试/log 很大、很吵、适合隔离时，Root 才按需委派。

---

## 2. 最重要的协作规则

### 1）Root 保留最终责任

Root 默认负责：

- 理解用户目标；
- 拆解任务；
- 关键架构判断；
- 默认写代码；
- 汇总 Subagent 结果；
- 检查最终 diff；
- 看 tests / build / logs / source 等证据；
- 决定任务是否真的完成。

### 2）一个 checkout 同时只保留一个 source-code writer

默认 Root 写代码。

如果一个 bounded worker 接管了明确实现任务，那么它工作期间 Root 不应该同时修改同一个 checkout。

如果确实需要多个 Agent 同时进行大规模实现，应使用不同 Git worktree。

### 3）默认只做一层 fan-out / fan-in

```text
Root
├── Explorer
├── Reviewer
└── Temporary agent
      ↓
   结果回 Root
```

Subagent 默认不继续递归创建 Subagent。只有 Root 针对一个明确 mission 显式授权 nested delegation 时才例外。

### 4）不要为了并发而并发

只有 delegation 能带来真正收益时才委派，例如：

- read-heavy 调查；
- noisy log / test；
- 可以独立验证的任务；
- 明确有延迟收益的并行工作。

### 5）Agent 说“没问题”不算证据

最终完成应该回到：

```text
diff
+ tests
+ build
+ logs
+ source
+ reproduction
+ 其他可验证证据
```

真正的协作规范源文件在：

```text
runtime/AGENTS.fragment.md
```

---

## 3. 先理解仓库结构

```text
codex-agent-foundry/
├── runtime/                       # 核心产品 / 唯一 source of truth
│   ├── AGENTS.fragment.md
│   └── .codex/
│       ├── config.toml
│       └── agents/
│           ├── repo_explorer.toml
│           └── reviewer.toml
│
├── evals/                         # 协作策略场景
│   ├── README.md
│   └── scenarios.json
│
├── .agents/skills/
│   └── install-codex-agent-foundry/
│       ├── SKILL.md
│       ├── agents/openai.yaml
│       ├── scripts/
│       │   ├── install.py
│       │   └── verify.py
│       ├── assets/project/        # runtime/ 的生成副本
│       └── references/design.md
│
├── scripts/
│   └── package_runtime.py
│
├── tests/
│   ├── test_installer.py
│   ├── test_cli.py
│   ├── test_runtime.py
│   └── test_hardening.py
│
├── .github/workflows/test.yml
├── AGENTS.md                      # 开发 Foundry 自己时使用
├── README.md
└── README.zh-CN.md
```

最重要的是先区分三层：

```text
runtime/       = 核心产品
Installer Skill = 交付工具
tests / CI     = 质量保障
```

---

## 4. 为什么 `runtime/` 和 Skill 下面有一份重复内容？

这是有意设计的。

```text
runtime/                                      ← 人修改这里
    │
    │ scripts/package_runtime.py
    ▼
.agents/skills/install-codex-agent-foundry/
└── assets/project/                           ← 自动生成的发布副本
```

两边当前内容应完全一致，但只有：

```text
runtime/
```

是 **source of truth**。

为什么还需要 `assets/project/`？

因为 Installer Skill 以后可能被单独安装到全局 Skills。如果 Skill 离开这个 Git 仓库，它仍然必须自己携带 Runtime 模板才能完成安装。

所以这更像：

```text
src/   → 源码
dist/  → 发布产物
```

而不是“两套配置同时维护”。

**不要手工修改 `assets/project/`。**

修改 `runtime/` 后运行：

```bash
python3 scripts/package_runtime.py
python3 scripts/package_runtime.py --check
```

CI 会阻止两边发生漂移。

---

## 5. 每个主要目录/文件是干什么的？

| 路径 | 作用 |
| --- | --- |
| `runtime/` | **核心产品**，保存多 Agent Runtime 规范 |
| `runtime/AGENTS.fragment.md` | 安装到业务项目里的 orchestration policy |
| `runtime/.codex/config.toml` | Foundry 需要的最小 Codex 项目配置 |
| `runtime/.codex/agents/repo_explorer.toml` | Explorer Custom Agent 配置 |
| `runtime/.codex/agents/reviewer.toml` | Reviewer Custom Agent 配置 |
| `evals/` | 典型协作场景，用来检查策略修改后是否“跑偏” |
| `.agents/skills/.../SKILL.md` | Installer Skill 的工作说明 |
| `.../scripts/install.py` | 规划、安装、升级、冲突保护、rollback、model override、uninstall |
| `.../scripts/verify.py` | 验证目标项目里的 Foundry 是否完整、是否 drift |
| `.../assets/project/` | `runtime/` 的生成副本，用于 Skill 自包含分发 |
| `scripts/package_runtime.py` | `runtime/ → Skill assets` 打包和一致性检查 |
| `tests/test_installer.py` | Plan / Apply / rollback / state / uninstall 等内部语义测试 |
| `tests/test_cli.py` | 从真正 CLI 角度测试 stdout、exit code、dry-run、BLOCKED PLAN |
| `tests/test_runtime.py` | Runtime TOML、协作不变量、eval、模型默认值来源、打包同步 |
| `tests/test_hardening.py` | 独立 Review 后补充的边界回归测试 |
| `.github/workflows/test.yml` | GitHub 自动在 Python 3.11 / 3.12 / 3.13 上测试 |
| 根目录 `AGENTS.md` | **开发 Foundry 本身**时 Codex 应遵守的规则 |

---

## 6. 根目录 `AGENTS.md` 和 `runtime/AGENTS.fragment.md` 有什么区别？

这是很容易混淆的一点。

### 根目录 `AGENTS.md`

作用：

> 当 Codex 在开发 **这个 Foundry 仓库本身** 时使用。

例如规定：

- `runtime/` 是 source of truth；
- generated assets 不应手工修改；
- installer 必须保守、可回滚；
- 修改后必须跑 tests。

### `runtime/AGENTS.fragment.md`

作用：

> 安装到你的业务项目之后，规范 **业务项目里的多 Agent 协作**。

所以两者不是重复文件。

---

## 7. 如何安装到业务项目？

假设目标项目是：

```text
~/work/my-project
```

### 第一步：只看计划，不写文件

```bash
python3 .agents/skills/install-codex-agent-foundry/scripts/install.py \
  ~/work/my-project \
  --check
```

### 第二步：执行安装

```bash
python3 .agents/skills/install-codex-agent-foundry/scripts/install.py \
  ~/work/my-project
```

### 第三步：验证

```bash
python3 .agents/skills/install-codex-agent-foundry/scripts/verify.py \
  ~/work/my-project
```

安装后目标项目大致会变成：

```text
my-project/
├── AGENTS.md                  # 原有内容 + Foundry managed block
└── .codex/
    ├── config.toml
    ├── .agent-foundry.json    # 版本 / ownership / model 状态
    └── agents/
        ├── repo_explorer.toml
        └── reviewer.toml
```

Codex 日常真正使用的是：

```text
AGENTS.md
.codex/config.toml
.codex/agents/*.toml
```

`.agent-foundry.json` 主要给安装、升级、验证和卸载记录状态。

---

## 8. Installer 为什么强调 Plan → Apply？

Installer 不会“先试着改一次，再正式改一次”。

它先构建一份完整 Plan：

```text
inspect
   ↓
build complete Plan
   ↓
├── --check      → 只显示 Plan
├── conflict     → BLOCKED PLAN，零写入
└── safe         → apply 同一份 Plan
                     ↓
                  verify / rollback
```

Plan 会明确包含：

```text
create
update
backup
delete
unchanged
conflict
```

其中也包括：

```text
.codex/.agent-foundry.json
```

以及 `--force` 时将创建的 backup 文件。

### 如果有冲突

例如业务项目已经有自己的：

```text
.codex/agents/reviewer.toml
```

正常安装会显示：

```text
BLOCKED PLAN
...
conflict reviewer.toml
...
No files were changed.
```

不会先写一半再失败。

### 如果 apply 中途失败

已经修改的文件会 rollback；事务中新建的空目录也会尽量清理。

更新已有文件时还会保留原来的 POSIX file mode。

---

## 9. 自定义 Explorer / Reviewer 模型

默认值来自 Runtime profile 本身：

```text
repo_explorer → gpt-5.6-terra / medium
reviewer      → gpt-5.6 / high
```

Installer 和 verifier 不单独维护另一套默认模型，所以 `runtime/` 仍然是唯一 source of truth。

如果你的账户可用模型不同，可以安装时覆盖：

```bash
python3 .../install.py ~/work/my-project \
  --explorer-model <model> \
  --reviewer-model <model>
```

选择会记录在：

```text
.codex/.agent-foundry.json
```

之后 `verify.py` 会把它当作有意配置，而不是误判成 drift。

---

## 10. 如何卸载？

先看计划：

```bash
python3 .../install.py ~/work/my-project --uninstall --check
```

再执行：

```bash
python3 .../install.py ~/work/my-project --uninstall
```

卸载只处理 Foundry 自己管理的内容：

- 删除 Foundry managed AGENTS block；
- 删除没有被用户修改过的 Foundry agent profile；
- 删除 Foundry state；
- 在能证明安全的情况下恢复 Foundry 添加的 concurrency 配置。

用户原本的 `AGENTS.md` 内容和用户自己的配置默认保留。

---

## 11. `evals/` 是什么？

Installer 测试只能证明：

> “文件有没有正确装进去。”

但 Foundry 真正的核心是：

> “多 Agent 应该怎么协作。”

所以 `evals/scenarios.json` 保存典型协作场景，例如：

- typo 不应该无意义 spawn agent；
- 不清楚的跨模块 bug 应优先 Explorer；
- 边界明确的实现可以考虑 Worker；
- noisy verification 可以用临时 verifier；
- 两个大任务并行写代码应该使用 worktree，而不是共享 checkout。

这些场景是 Runtime policy 的 contract。

---

## 12. 开发 Foundry 时怎么验证？

修改协作规范时，**先改 `runtime/`**。

然后运行：

```bash
python3 scripts/package_runtime.py
python3 scripts/package_runtime.py --check
python3 -m unittest discover -s tests -v
python3 -m compileall -q .agents/skills/install-codex-agent-foundry/scripts scripts tests
```

CI 会在 Python 3.11、3.12、3.13 上执行 package check 和完整测试。

---

## 13. 可以直接作为 Skill 使用吗？

可以，但要注意：

> **Skill 是安装入口，不是 Foundry 本体。**

当 Codex 打开这个仓库时可以调用：

```text
$install-codex-agent-foundry /path/to/repo
```

如果把 Installer Skill 安装成全局 Skill，以后在其他项目里也可以继续使用同样命令。

---

## 14. 最后用一句话区分所有东西

```text
runtime/
= Codex 多 Agent 协作规范本体

.agents/.../SKILL.md + install.py + verify.py
= 把规范安全装进项目的工具

.agents/.../assets/project/
= runtime/ 的生成发布副本，不是第二套源码

evals/
= 检查协作策略方向是否正确

tests/ + CI
= 检查安装器、Runtime 和边界条件是否可靠

根 AGENTS.md
= 开发 Foundry 自己时的仓库规则
```

官方参考：[Build skills](https://developers.openai.com/codex/skills) · [Subagents](https://developers.openai.com/codex/subagents)
