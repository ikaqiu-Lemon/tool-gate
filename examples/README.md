# Tool-Gate 交付演示样例

本示例使用 Yuque 风格的 mock 工具仅作为稳定、可控的演示载体;项目本身并不绑定 Yuque 领域。

---

> 面向交付评审人 / 二次开发者。每个样例是一个**独立 demo workspace**,演示时 `cd` 进入该样例目录即可启动 Claude Code。
>
> 本目录包含**一个 canonical Stage-first demo** 和**三个 legacy examples**。规范要求详见 `openspec/specs/delivery-demo-harness/`。

---

## 1. 样例一句话定位

### Canonical Stage-first Demo

| 样例 | 主题 | 演示重点 |
|---|---|---|
| [`simulator-demo/`](./simulator-demo/) | **Stage-first Skill Governance (Canonical)** | 子进程隔离 + 协议边界 + SQLite 共享状态 + 完整审计链 + Stage-first metadata + Stage transition governance |

**`simulator-demo/`** 是 **Stage-first Skill Governance 的 canonical acceptance target**。它通过 Python 子进程模拟完整的 Claude Code 调用链路(SessionStart → UserPromptSubmit → PreToolUse → PostToolUse),演示:
- Stage-first metadata discovery (`initial_stage`, `stages`, `allowed_next_stages`, terminal stages)
- Stage transition governance (legal/illegal `change_stage`, `stage.transition.allow/deny` audit events)
- No-stage skill fallback behavior (uses `allowed_tools` directly when skill has no `stages` field)
- Lifecycle, terminal stage, persistence, and revoke behavior
- Hook/MCP 子进程隔离、SQLite 共享状态、完整审计链路

详见 [`simulator-demo/README.md`](./simulator-demo/README.md)。

### Legacy Examples (Deprecated)

> ⚠️ **DEPRECATED**: The following examples demonstrate earlier governance patterns and do **not** demonstrate Stage-first governance. For Stage-first governance acceptance, see [`simulator-demo/`](./simulator-demo/).

| 样例 | 主题 | 演示重点 |
|---|---|---|
| [`01-knowledge-link/`](./01-knowledge-link/) | 首次发现与自动授权 | 低风险技能自动启用 + 混杂工具硬拦截 + `refresh_skills` 插曲 |
| [`02-doc-edit-staged/`](./02-doc-edit-staged/) | 受控编辑与分阶段 | `require_reason` + 两阶段 `change_stage` + `blocked_tools` 全局红线 |
| [`03-lifecycle-and-risk/`](./03-lifecycle-and-risk/) | 会话生命周期与风险升级 | TTL 过期回收 / 主动 `disable` / 高风险 `approval_required` / 审计顺序闭环 |

前三个样例围绕同一个虚构业务故事展开:**知识工程师 Alice 用 Claude Code 维护她的内部知识库**。Alice 的工作台刻意混装了若干 MCP:除语雀风格 MCP 外,还安装了通用 Web 搜索、内部 wiki 搜索、以及一个能跑 shell 的第三方 MCP。tool-gate 的职责是**只让当前启用技能真正需要的工具进到 `active_tools`**,其它一律被 `PreToolUse` 拦下。

这些 legacy examples 保留用于参考早期治理模式,但**不演示 Stage-first governance**。

---

## 2. 演示前置

> 🆕 **新手读者**:先读 [`QUICKSTART.md`](./QUICKSTART.md)。它是三个样例共用的概念 + 安装 + 启动 + verify + reset + troubleshooting 入口,瘦身了各 workspace README 的前置章节。本节保留作为交付评审人的速查;零知识读者不必从这里开始。

### 2.1 环境要求

- Python 3.11+
- 已安装本项目(仓库根目录执行 `pip install -e .`)
- 可选:Claude Code CLI(未安装时可退化为子进程冒烟,见 §5)

### 2.2 启动方式(统一模板)

```bash
cd examples/<01-02-or-03-workspace>/
claude --plugin-dir ../../ --mcp-config ./.mcp.json
```

**关键约束**:每个样例的 `.mcp.json` 使用**相对路径**(`./mcp/mock_*.py`),必须**从 workspace 根启动**才能被正确解析。

### 2.3 Phase A 与 Phase B

| 阶段 | 已交付 |
|---|---|
| **Phase A** | `README.md` / `SKILL.md`(骨架) / `contracts/*.md` / `schemas/*.schema.json` / `demo_policy.yaml` / `.mcp.json` |
| **Phase B**(当前已完成) | 4 类 mock stdio server(共 6 份 Python 文件);每个 mock 启动自检 `jsonschema.validate`;workspace README 端到端命令已补齐 |

Phase B 完成后,每个 workspace **可直接启动真实 MCP 握手**;Claude CLI 加载 + 端到端现场实测记录待每次交付前按需补填到各 README §5 的"实测记录"小节(差异 = 0 则写"无差异")。

---

## 3. Capability Coverage Matrix

六个 capability spec 与样例对应关系。证明**抽象能力面**被完整覆盖。

| Capability Spec | 01 knowledge-link | 02 doc-edit-staged | 03 lifecycle-and-risk |
|---|:-:|:-:|:-:|
| `skill-discovery` | ● | ○ | ● (仅辅助复核) |
| `skill-authorization` | ● low / auto | ● medium / reason | ● high / approval |
| `skill-execution` | ● `run_skill_action` | ● stages + `change_stage` | ○ |
| `session-lifecycle` | ○ | ○ | ● TTL + revoke + disable |
| `tool-surface-control` | ● allow + deny | ● stage filter + blocked | ● blocked + whitelist 叠加 |
| `audit-observability` | ● 基础链 | ● `stage.change` + violation | ● revoke 顺序 + expire |

> **关于 `refresh_skills`**:其**主场景**固定在样例 01 的"附录:refresh_skills 插曲"一节;样例 03 只在末尾做一次"辅助复核触发"以保证功能/接口矩阵里 03 列标 ● 能被实际打点。**样例 03 的主线严禁出现 `refresh_skills`。**

---

## 4. 功能 / 接口覆盖矩阵

8 个 MCP 元工具 + 4 类 hook + 3 类诊断信号与样例对应关系。证明**关键接口与事件点**被实际触达。

| 功能 / 接口 | 01 | 02 | 03 |
|---|:-:|:-:|:-:|
| `list_skills` | ● | ○ | ● |
| `read_skill` | ● | ● | ○ |
| `enable_skill` | ● | ● | ● |
| `disable_skill` | ○ | ○ | ● |
| `grant_status` | ○ | ● | ● |
| `run_skill_action` | ● | ● | ○ |
| `change_stage` | ○ | ● | ○ |
| `refresh_skills` | ○ (主场景在 01 插曲) | ○ | ● (辅助复核) |
| `SessionStart` | ● | ○ | ● |
| `UserPromptSubmit` | ● | ● | ● |
| `PreToolUse` | ● | ● | ● |
| `PostToolUse` | ● | ● | ● |
| `error_bucket` | ○ | ● | ● |
| `TTL / revoke` | ○ | ○ | ● |
| `funnel / trace` | ○ | ○ | ● |

**两张矩阵的分工**:
- **Capability 矩阵**回答"**面**"—— 抽象能力是否齐
- **功能 / 接口矩阵**回答"**点**"—— 具体元工具、hook、诊断信号是否都被触达一次

每个标 ● 的格子在对应样例的 §3 三列操作步骤表(或明确标注的附录)中有至少一行落脚点。

---

## 5. 常见问题

### 5.1 没有 Claude Code CLI,能看到拦截效果吗?

可以。每条 "系统侧事件" 对应的决策都可以用子进程管道重放:

```bash
# SessionStart
echo '{"hook_event_name":"SessionStart","session_id":"demo","cwd":"'"$PWD"'"}' | tg-hook

# PreToolUse 对白名单外工具
echo '{"hook_event_name":"PreToolUse","session_id":"demo","tool_name":"search_web","tool_input":{}}' | tg-hook
```

`tg-hook` stdout 就是 Claude Code 会收到的 `permissionDecision`(allow / deny / ask)JSON。Phase B 会在每个样例的 §5 末尾追加"实测子进程 stdout"段。

### 5.2 为什么样例里没有语雀真实 Token?

所有 `mock_yuque_*` 返回硬编码样本,不调用语雀真实 API。Yuque 只是**演示载体**,本项目不绑定该领域(见顶部免责声明)。

### 5.3 `mcp/mock_shell_stdio.py` 是用来做什么的?

它是**混杂变量工具**,仅为制造真实工具混杂环境以验证 tool-gate 的拦截能力。它**不代表**本项目支持任意 shell 执行,也不是任何主业务能力。仅样例 02 使用,用于演示 `blocked_tools: [run_command]` 的全局红线。

### 5.4 Phase A 产物能通过哪些自检?

- `examples/` 下无任何 `*.py` 文件
- 三份 `.mcp.json` 中所有路径相对、不出 workspace
- 每个样例 `README.md` §3 表时间戳单调递增且跨样例不回退
- 03 主表无 `refresh_skills` 字样
- 每个 `*.schema.json` 合法 JSON(Draft 2020-12)且含 `input` + `output` 双子 schema
- 6 份 `SKILL.md` 能被 `SkillIndexer` 扫到

详见 `openspec/specs/delivery-demo-harness/spec.md` 中的相关 requirements。

> 更完整的排障矩阵(pip 错目录、`tg-hook` 返回 `{}`、`GOVERNANCE_*` 未导出、`.mcp.json` 相对路径断裂等 8+ 类)见 [`QUICKSTART.md §6`](./QUICKSTART.md#6--troubleshooting8-类常见启动失败)。

---

## 6. 相关文档

- **`openspec/specs/delivery-demo-harness/spec.md`**: Demo workspace 规范要求（canonical）
- **`QUICKSTART.md`**: 零知识读者入门指南（安装、启动、verify、reset、troubleshooting）
- `docs/refer/yuque-eco-system.md`: 演示业务故事的参考来源
- `README_CN.md`: 项目整体概览

---

## 7. 授权与约束

本 change 只允许修改 `examples/` 下的内容与根级 README 的文档导航条目。任何触碰 `src/tool_governance/`、`tests/`、`skills/`(根)、`hooks/`、根 `.mcp.json`、`config/default_policy.yaml` 的改动都不属于本次 change。
