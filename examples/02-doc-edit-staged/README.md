# 样例 02 · 受控编辑:分阶段与 blocked_tools

> 本样例展示 tool-gate 在**中风险 + 需要写入**的场景下如何落地"先理解、再修改"的两阶段工作流,同时通过 `blocked_tools` 演示全局红线。

---

## 0. 业务背景与展示目标

**业务背景**:样例 01 的关联报告出炉后,Alice 决定把"相关文档"区块**实际写回**一篇指定的文档。写回动作是中等风险,需要一个**明确的理由**(`require_reason`);并且写入前 Alice 想先看一眼原文避免覆盖别人的新修改。

**展示目标**:
1. 证明中风险技能不带 `reason` 被拒,带上 `reason` 后进入 `analysis` 阶段
2. 证明 `analysis` 阶段只能读,不能写;只有 `change_stage("execution")` 后 `yuque_update_doc` 才可用
3. 证明 `blocked_tools` 全局红线高于任何阶段授权 —— `run_command` 无论什么时候都过不了

---

## 1. 需求点

- N1 · `yuque-doc-edit` 技能 `risk_level: medium`,策略 `require_reason: true`;不带 reason 的 `enable_skill` 直接 deny
- N2 · 启用后进入默认阶段 `analysis`,`active_tools` = `meta + yuque_get_doc + yuque_list_docs`;`yuque_update_doc` 不在其中
- N3 · `change_stage("yuque-doc-edit", "execution")` 后,`active_tools` 切换为 `meta + yuque_get_doc + yuque_update_doc`
- N4 · 全局 `blocked_tools: [run_command]`:即使第三方 `mock-shell` MCP 在 `.mcp.json` 里注册,`run_command` 任何时刻尝试都被 deny,且原因标记 `blocked`(区别于 `whitelist_violation`)
- N5 · 审计表应出现 `skill.enable (denied)` → `skill.enable (granted)` → `stage.change analysis → execution` → `whitelist_violation yuque_update_doc stage=analysis` → `tool.call yuque_update_doc decision=allow stage=execution` → `tool.call run_command decision=deny reason=blocked`

---

## 2. 演示前置

### 2.1 一次性环境准备

```bash
# 在仓库根执行
pip install -e ".[dev]"     # 安装 tool-gate + FastMCP + jsonschema
```

### 2.2 进入 workspace 启动

```bash
cd examples/02-doc-edit-staged/

export GOVERNANCE_DATA_DIR="$PWD/.demo-data"
export GOVERNANCE_SKILLS_DIR="$PWD/skills"
export GOVERNANCE_CONFIG_DIR="$PWD/config"

# 方式 A · Claude Code CLI
claude --plugin-dir ../../ --mcp-config ./.mcp.json

# 方式 B · mock 握手冒烟
python ./mcp/mock_yuque_stdio.py
python ./mcp/mock_shell_stdio.py         # 启动时也会自检;运行后任何调用都会被 PreToolUse 拦截
```

### 2.3 Phase B 已交付

- ✅ `mcp/mock_yuque_stdio.py`:yuque_get_doc(含 `version` 字段用于并发版本演示)/ yuque_list_docs / yuque_update_doc
- ✅ `mcp/mock_shell_stdio.py`:run_command(**混杂变量工具**,module docstring 首段固化免责声明)
- ✅ 启动自检:两个 mock 都会在 `mcp.run()` 之前跑 `jsonschema.validate`

---

## 3. 操作步骤

| 时间戳 | 操作者输入 | 模型预期动作 | 系统侧事件 |
|---|---|---|---|
| 2026-04-19T11:15:00+08:00 | Alice:"帮我把样例 01 输出的相关文档区块写回 `rag-overview-v2`" | `read_skill("yuque-doc-edit")` | `UserPromptSubmit` 重算 `active_tools`;MCP `read_skill` 返回 SOP + 两阶段 `stages`;审计写 `skill.read risk=medium` |
| 2026-04-19T11:15:08+08:00 | — | `enable_skill("yuque-doc-edit")`(**未带 reason**) | `PolicyEngine.evaluate` → `require_reason=true` 触发 `denied reason=reason_missing`;**不创建 grant**;审计写 `skill.enable decision=denied reason=reason_missing` |
| 2026-04-19T11:15:15+08:00 | — | `enable_skill("yuque-doc-edit", reason="Append 相关文档区块到 rag-overview-v2,源自 01 的关联报告")` | `PolicyEngine.evaluate` → `granted`;创建 `Grant(scope=session, ttl=3600, stage=analysis)`;`active_tools` += `[yuque_get_doc, yuque_list_docs]`;审计写 `skill.enable granted_by=policy reason="..."` |
| 2026-04-19T11:15:22+08:00 | — | `yuque_get_doc(doc_id="rag-overview-v2")` | `PreToolUse` allow(analysis 允许读);mock 返回最新正文;`PostToolUse` 审计 |
| 2026-04-19T11:15:40+08:00 | — | `grant_status()` | 返回 `[{skill: yuque-doc-edit, stage: analysis, ttl_remaining: 3578, ...}]`;帮助模型确认当前能做什么 |
| 2026-04-19T11:16:02+08:00 | — | `yuque_update_doc(doc_id="rag-overview-v2", body_markdown="...<新增区块>")` | `PreToolUse` **deny** → `additionalContext`:"`yuque_update_doc` 不在 stage `analysis` 的 `allowed_tools` 中;调用 `change_stage` 切到 `execution` 后再试";审计写 `tool.call whitelist_violation yuque_update_doc stage=analysis` |
| 2026-04-19T11:16:08+08:00 | — | `change_stage("yuque-doc-edit", "execution")` | state 表更新 `stage=execution`;`ToolRewriter` 重算 → `active_tools` = `meta + yuque_get_doc + yuque_update_doc`;审计写 `stage.change analysis → execution` |
| 2026-04-19T11:16:20+08:00 | — | `yuque_update_doc(doc_id="rag-overview-v2", body_markdown="...<新增区块>")` | `PreToolUse` allow;mock 返回 `{ok:true, version:5}`;`PostToolUse` 审计 `tool.call yuque_update_doc decision=allow stage=execution` |
| 2026-04-19T11:16:38+08:00 | Alice(误试):"顺手用 shell 查一下磁盘占用" | `run_command(cmd="df -h")` | `PreToolUse` **deny** → `additionalContext`:"`run_command` 在全局 `blocked_tools` 列表中,任何技能都无法启用此工具";审计写 `tool.call run_command decision=deny reason=blocked` |
| 2026-04-19T11:16:45+08:00 | Alice:"好的,不用 shell 了" | — | `UserPromptSubmit` 重算(无变化) |
| 2026-04-19T11:17:10+08:00 | Alice:"再次确认一下现在我的权限" | `grant_status()` | 返回当前 `stage=execution`、TTL 剩余、`active_tools` 快照;用于 `error_bucket` 分析(若出现 deny 可对照) |

---

## 4. 系统内部行为说明

- **`require_reason` 分支**:`PolicyEngine.evaluate(skill, reason=None)` 当 `skill_policies.<skill>.require_reason=true` 时,短路返回 `decision=denied, reason=reason_missing`,**不生成 grant 也不扣减 TTL**。这是 `skill-authorization` 规范中的"reason 缺失即失败"不变量。
- **Stage 过滤**:`ToolRewriter.compute_active_tools` 会根据 `state_manager.get_stage(skill_id)` 选择对应阶段的 `allowed_tools`;默认进入技能 `stages[0]`。`change_stage` 写入 state 表并**立即**触发下一次 rewrite(无需等下一轮 `UserPromptSubmit`)。
- **`blocked_tools` 优先级**:策略评估顺序 = `global blocked → skill-specific policy → risk default`。因此即使某个 skill 的 `allowed_tools` 里写了 `run_command`,`ToolRewriter` 也会在最终合集前把它剔除;`PreToolUse` 看到时直接 deny,原因字段 = `blocked`(不是 `whitelist_violation`)。
- **`grant_status` 的诊断价值**:该元工具返回 `active_tools` 快照 + 每个 grant 的 TTL/stage/reason。当模型被拒时,调一次 `grant_status` 能自己回答"我现在该怎么走下一步",这是 `error_bucket`(按拒绝原因分桶)与 `funnel/trace` 指标的上游输入。

---

## 5. 预期输出 / 日志 / 审计

### 5.1 Audit 行形状

```
created_at                         event                subject                                          meta
2026-04-19T11:15:00+08:00          skill.read           skill=yuque-doc-edit                             risk=medium
2026-04-19T11:15:08+08:00          skill.enable         skill=yuque-doc-edit                             decision=denied reason=reason_missing
2026-04-19T11:15:15+08:00          skill.enable         skill=yuque-doc-edit                             decision=granted stage=analysis ttl=3600 reason="Append..."
2026-04-19T11:15:22+08:00          tool.call            tool=yuque_get_doc  stage=analysis               decision=allow
2026-04-19T11:16:02+08:00          tool.call            tool=yuque_update_doc  stage=analysis           decision=deny reason=whitelist_violation
2026-04-19T11:16:08+08:00          stage.change         skill=yuque-doc-edit  from=analysis to=execution
2026-04-19T11:16:20+08:00          tool.call            tool=yuque_update_doc  stage=execution          decision=allow
2026-04-19T11:16:38+08:00          tool.call            tool=run_command                                 decision=deny reason=blocked
```

### 5.2 关键拒绝 `additionalContext` 形状(Phase B 回填)

```
// reason_missing:
"skill `yuque-doc-edit` requires a reason (policy.require_reason=true). Retry enable_skill with reason=\"...\"."

// stage 不匹配:
"tool `yuque_update_doc` is not allowed in stage `analysis`. Call change_stage(\"yuque-doc-edit\", \"execution\") first."

// blocked_tools:
"tool `run_command` is in global blocked_tools and cannot be enabled by any skill."
```

> **实测记录**(Phase B 填写):<!-- Phase B 填写:实际 stdout 与本节形状差异 -->

---

## 6. Mock 工具契约速览

| 工具 | 所在 MCP | 本样例调用? | 契约详表 |
|---|---|---|---|
| `yuque_get_doc` | `mock-yuque` | ● 主业务工具(analysis + execution) | [`contracts/yuque_tools_contract.md#yuque_get_doc`](./contracts/yuque_tools_contract.md#yuque_get_doc) |
| `yuque_list_docs` | `mock-yuque` | ● 主业务工具(analysis) | [`contracts/yuque_tools_contract.md#yuque_list_docs`](./contracts/yuque_tools_contract.md#yuque_list_docs) |
| `yuque_update_doc` | `mock-yuque` | ● 主业务工具(仅 execution) | [`contracts/yuque_tools_contract.md#yuque_update_doc`](./contracts/yuque_tools_contract.md#yuque_update_doc) |
| `run_command` | `mock-shell` | ○ **混杂变量工具**,永远被 `blocked_tools` 拦截 | [`contracts/shell_tools_contract.md#run_command`](./contracts/shell_tools_contract.md#run_command) |

> ⚠️ `mock_shell_stdio.py` 是**混杂变量工具**,仅为制造真实工具混杂环境以验证 tool-gate 的拦截能力。它**不代表**本项目支持任意 shell 执行,也不是任何主业务能力。

---

## 7. 代码与测试依据

- 主链路对照实现:
  - `src/tool_governance/core/policy_engine.py` → `require_reason` 分支、`blocked_tools` 优先级
  - `src/tool_governance/core/tool_rewriter.py` → stage 过滤 + global blocked 剥离
  - `src/tool_governance/core/state_manager.py` → `change_stage` 持久化与审计
- 对照 functional tests:
  - `tests/functional/test_functional_stage.py` — `change_stage` + `stage.change` 审计
  - `tests/functional/test_functional_policy_e2e.py::E6` — `require_reason` 双分支
  - `tests/functional/test_functional_policy_e2e.py::E4` — `blocked_tools` 剥离 + PreToolUse deny
