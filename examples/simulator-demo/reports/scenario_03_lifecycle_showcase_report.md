# Scenario 03 Showcase Report: Lifecycle, Terminal Stage, and Persistence

**Generated**: 2026-05-06  
**Session ID**: scenario-03  
**Execution Mode**: Real `tg-hook` and `tg-mcp` subprocess boundaries  
**Data Source**: Real SQLite `governance.db`, `audit_log`, `events.jsonl`

---

## Executive Summary

本场景验证 Tool-Gate 的 **Stage-first Skill Governance** 生命周期能力，覆盖：

- ✅ **Terminal Stage Enforcement** — `allowed_next_stages: []` 阻止非法状态转移
- ✅ **Stage State Persistence** — `current_stage`, `stage_history`, `exited_stages` 持久化到 SQLite
- ✅ **Expired Grant Filtering** — TTL 过期后 grant 不再贡献 `active_tools`
- ✅ **Disable/Revoke Lifecycle** — `disable_skill` 后工具立即不可用
- ✅ **Full Audit Trail** — 所有治理决策可追溯（`stage.transition.allow/deny`, `grant.expire`, `skill.disable`）
- ✅ **Real Subprocess Boundary** — 真实 `tg-hook` / `tg-mcp` 子进程，通过 SQLite 共享状态

**关键成果**: 本场景通过真实子进程边界验证了 Tool-Gate 的可控、可审计、可恢复的 Agent 工具治理能力。

---

## 1. Tool-Gate 治理模型概览

Tool-Gate 通过 **Skill → Stage → Grant → RuntimeContext → active_tools → PreToolUse** 构成渐进式工具治理闭环。

| 概念 | 含义 |
|------|------|
| **Skill** | 一项业务能力 / SOP（Standard Operating Procedure） |
| **Stage** | Skill 内部的流程阶段，控制工具可见性演进 |
| **Tool** | 某个 Stage 中允许调用的外部执行能力 |
| **Grant** | `enable_skill` 后创建的授权凭证，带 TTL 和 scope |
| **RuntimeContext** | 每回合派生出的只读运行时视图 |
| **active_tools** | 当前真正可调用的工具集合（权威来源） |
| **PreToolUse** | 工具调用前的准入检查点 |

**核心公式**:
```
active_tools = META_TOOLS ∪ (enabled skills with valid grant 的 stage_tools) − blocked_tools
```

---

## 2. Scenario 03 验证目标

| 验证目标 | 说明 | 结果 |
|---------|------|------|
| **Terminal stage enforcement** | `verification` 阶段 `allowed_next_stages=[]`，拒绝继续跳转 | ✅ |
| **Stage state persistence** | `current_stage` / `stage_history` / `exited_stages` 持久化到 SQLite | ✅ |
| **Expired grant filtering** | TTL 过期后不再贡献 `active_tools` | ✅ |
| **Disable / revoke lifecycle** | `disable_skill` 后工具不可用 | ✅ |
| **Audit trail completeness** | `stage.transition.allow/deny`, `grant.expire`, `skill.disable` 等事件可审计 | ✅ |
| **Real subprocess boundary** | 真实 `tg-hook` / `tg-mcp` / `governance.db` | ✅ |

---

## 3. 运行环境和输入

| 项目 | 值 |
|------|-----|
| **Scenario** | `scenario_03_lifecycle.py` |
| **Session ID** | `scenario-03` |
| **Skills Directory** | `examples/simulator-demo/fixtures/skills` |
| **Config Directory** | `examples/01-knowledge-link/config` |
| **Data Directory** | `examples/simulator-demo/.scenario-03-data` |
| **Database** | `.scenario-03-data/governance.db` |
| **Execution Mode** | Real `tg-hook` / `tg-mcp` subprocess |
| **Subprocess Confirmation** | ✅ Verified via stdout logs showing MCP server processing requests |

---

## 4. 总体 Pipeline 图

```text
Scenario 03: Lifecycle / Terminal / Persistence
   │
   ├─► [1] SessionStart
   │      └─ 初始化 session，建立治理上下文
   │
   ├─► [2] Refresh Skills
   │      └─ 从 fixtures/skills 扫描 staged + no-stage skills
   │
   ├─► [3] Enable Staged Skill
   │      └─ enable_skill(yuque-doc-edit-staged) → current_stage=analysis
   │
   ├─► [4] Stage Transitions (Full Lifecycle)
   │      ├─ analysis → execution ✅ (legal)
   │      ├─ execution → verification ✅ (legal, enters terminal)
   │      └─ verification → execution ❌ (terminal deny)
   │
   ├─► [5] Persistence Verification
   │      └─ 从 SQLite sessions.state_json 恢复 current_stage / stage_history / exited_stages
   │
   ├─► [6] Expired Grant Check
   │      ├─ enable no-stage skill (yuque-knowledge-link) with TTL=2s
   │      ├─ before expiry: yuque_search allow ✅
   │      ├─ wait 3 seconds
   │      └─ after expiry: yuque_search deny ✅
   │
   ├─► [7] Disable / Revoke
   │      ├─ disable_skill(yuque-doc-edit-staged)
   │      └─ disabled skill tool deny ✅
   │
   └─► [8] Artifacts + Audit
          ├─ governance.db (SQLite audit_log + sessions + grants)
          ├─ events.jsonl (complete event trace)
          ├─ audit_summary.md (human-readable summary)
          └─ metrics.json (event statistics)
```

---

## 5. Stage 状态机展示

### 5.1 Staged Skill: yuque-doc-edit-staged

```text
yuque-doc-edit-staged (3-stage workflow)
   │
   ├─► analysis (initial_stage)
   │      allowed_tools: [yuque_search, yuque_get_doc]
   │      allowed_next_stages: [execution]
   │
   ├─► execution
   │      allowed_tools: [yuque_get_doc, yuque_update_doc]
   │      allowed_next_stages: [verification]
   │
   └─► verification [TERMINAL]
          allowed_tools: [yuque_get_doc]
          allowed_next_stages: []  ← blocks all further transitions
```

### 5.2 实际 Stage Transitions

| From | To | Expected | Actual | Audit Event |
|------|-----|----------|--------|-------------|
| `analysis` | `execution` | allow | ✅ allow | `stage.transition.allow` |
| `execution` | `verification` | allow | ✅ allow | `stage.transition.allow` |
| `verification` | `execution` | deny | ✅ deny | `stage.transition.deny` |

**Terminal Stage Enforcement**: `verification` 阶段的 `allowed_next_stages: []` 成功阻止了向 `execution` 的非法回退。

---

## 6. Step-by-Step 运行结果

| Step | Action | Expected | Actual Result | Status |
|------|--------|----------|---------------|--------|
| 1 | SessionStart | session 初始化 | Session initialized, skills catalog composed | ✅ |
| 2 | refresh_skills | skills loaded | `{'refreshed': True, 'skill_count': 2}` | ✅ |
| 3 | enable staged skill | granted=True | `{'granted': True, 'allowed_tools': [8 meta + 2 stage tools]}` | ✅ |
| 4 | verify initial stage | current_stage=analysis | `current_stage: analysis` | ✅ |
| 5 | analysis→execution | changed=True | `{'changed': True, 'new_active_tools': [...yuque_update_doc]}` | ✅ |
| 6 | execution→verification | changed=True | `{'changed': True, 'new_active_tools': [...yuque_get_doc only]}` | ✅ |
| 7 | verify terminal state | current_stage=verification | `current_stage: verification` | ✅ |
| 8 | verification→execution | changed=False | `{'error': 'terminal', 'error_bucket': 'stage_transition_not_allowed'}` | ✅ |
| 9 | denied transition no-op | state unchanged | `stage_history length: 2` (unchanged) | ✅ |
| 10 | persistence restore | state persisted | SQLite state_json contains stage_history, exited_stages | ✅ |
| 11a | enable with TTL=2s | granted=True | `{'granted': True}` | ✅ |
| 11b | tool before expiry | allow | `decision: allow` | ✅ |
| 11c | wait 3 seconds | grant expires | TTL elapsed | ✅ |
| 11d | tool after expiry | deny | `decision: deny, error_bucket: tool_not_available` | ✅ |
| 12 | disable skill | disabled=True | `{'disabled': True}` | ✅ |
| 13 | disabled tool check | deny | `decision: deny` | ✅ |
| 14 | artifacts | generated | governance.db, events.jsonl, audit_summary.md, metrics.json | ✅ |

**所有 14 个步骤全部通过 ✅**

---

## 7. RuntimeContext / active_tools 解释

### 7.1 Stage-driven active_tools

Tool-Gate 的核心机制是 **active_tools 随 Stage 变化**，而非一次性暴露所有工具。

| 当前状态 | 有效 Grant | current_stage | 可贡献工具 | 结果 |
|---------|-----------|---------------|-----------|------|
| staged skill enabled | ✅ yes | `analysis` | `analysis.allowed_tools` | allow `yuque_search`, `yuque_get_doc` |
| after transition | ✅ yes | `execution` | `execution.allowed_tools` | allow `yuque_update_doc`, `yuque_get_doc` |
| after transition | ✅ yes | `verification` | `verification.allowed_tools` | allow `yuque_get_doc` only |
| terminal deny | ✅ yes | `verification` | unchanged | state no-op, tools unchanged |
| after disable | ❌ revoked | - | none | deny all skill tools |

**关键观察**: 
- `yuque_update_doc` 只在 `execution` 阶段可用
- `verification` 阶段只保留只读工具 `yuque_get_doc`
- Terminal stage 拒绝转移，但不影响当前 stage 的工具可用性

### 7.2 Expired Grant Filtering

| 时刻 | Skill | TTL | Grant 状态 | Tool | PreToolUse |
|------|-------|-----|-----------|------|-----------|
| T+0s | yuque-knowledge-link | 2s | active | yuque_search | ✅ allow |
| T+3s | yuque-knowledge-link | expired | expired | yuque_search | ❌ deny |

**核心验证**: 
- Expired grant 不要求主动从 `skills_loaded` 删除
- 关键是 `build_runtime_context()` 在计算 `active_tools` 时过滤掉 expired grant
- PreToolUse 检查时，expired grant 的工具已不在 `active_tools` 中

---

## 8. Persistence 验证

### 8.1 Stage State 持久化字段

从 SQLite `sessions.state_json` 中提取的 stage state（在 disable 之前的快照）:

| 字段 | 期望值 | 实际值 | 说明 |
|------|--------|--------|------|
| `current_stage` | `verification` | ✅ `verification` | 当前处于 terminal stage |
| `stage_history` length | 2 | ✅ 2 | `analysis→execution`, `execution→verification` |
| `exited_stages` | `[analysis, execution]` | ✅ `[analysis, execution]` | 已离开的 stages |
| `stage_entered_at` | exists | ✅ exists | 进入 `verification` 的时间戳 |

### 8.2 Stage History 详细记录

```json
stage_history: [
  {
    "from_stage": "analysis",
    "to_stage": "execution",
    "transitioned_at": "2026-05-06T06:11:42.522438Z"
  },
  {
    "from_stage": "execution",
    "to_stage": "verification",
    "transitioned_at": "2026-05-06T06:11:42.526389Z"
  }
]
```

**关键特性**:
- `stage_history` 只记录成功的 transitions
- 被拒绝的 transition（verification→execution）不进入 `stage_history`
- 拒绝的 transition 记录在 `audit_log` 中，带 `error_bucket`

### 8.3 Persistence 架构图

```text
SQLite sessions.state_json
   │
   └─ skills_loaded["yuque-doc-edit-staged"]
        ├─ current_stage: "verification"
        ├─ stage_history: [
        │    {from: "analysis", to: "execution", at: "..."},
        │    {from: "execution", to: "verification", at: "..."}
        │  ]
        ├─ exited_stages: ["analysis", "execution"]
        └─ stage_entered_at: "2026-05-06T06:11:42.526389Z"
```

---

## 9. Audit Trail 分析

### 9.1 Audit Event Counts

从真实 SQLite `audit_log` 表提取:

| Event Type | Count | Governance Meaning |
|-----------|------:|-------------------|
| `tool.call` | 3 | 工具准入检查（allow/deny） |
| `skill.enable` | 2 | 创建授权 / 启动能力 |
| `stage.transition.allow` | 2 | 合法阶段跳转 |
| `stage.transition.deny` | 1 | 非法阶段跳转被拒 |
| `grant.expire` | 1 | 授权过期 |
| `grant.revoke` | 1 | 授权撤销 |
| `skill.disable` | 1 | 禁用技能 |
| `prompt.submit` | 1 | Prompt 提交 |
| **Total** | **12** | **完整审计链** |

### 9.2 Critical Audit Events

| Event | Expected Detail | Found? | Evidence |
|-------|----------------|--------|----------|
| `stage.transition.allow` | analysis → execution | ✅ | `{"from_stage": "analysis", "to_stage": "execution"}` |
| `stage.transition.allow` | execution → verification | ✅ | `{"from_stage": "execution", "to_stage": "verification"}` |
| `stage.transition.deny` | verification → execution, error_bucket | ✅ | `{"from_stage": "verification", "to_stage": "execution", "error_bucket": "stage_transition_not_allowed"}` |
| `grant.expire` | yuque-knowledge-link | ✅ | `decision: expired, skill_id: yuque-knowledge-link` |
| `skill.disable` | yuque-doc-edit-staged | ✅ | `decision: revoked, skill_id: yuque-doc-edit-staged` |
| `grant.revoke` | yuque-doc-edit-staged | ✅ | `{"grant_id": "...", "reason": "explicit"}` |
| `tool.call` deny | after expiration | ✅ | `decision: deny, error_bucket: tool_not_available` |

**审计完整性**: 所有关键治理决策都有对应的 audit event，包含 `from_stage`, `to_stage`, `error_bucket` 等上下文。

---

## 10. What This Demonstrates About Tool-Gate

### 10.1 Stage-first Tool Surface Control

**特性**: 工具不是一次性全部暴露，而是随 SOP 阶段变化。

**证据**:
- `analysis` 阶段: 只读工具 (`yuque_search`, `yuque_get_doc`)
- `execution` 阶段: 增加写工具 (`yuque_update_doc`)
- `verification` 阶段: 回退到只读 (`yuque_get_doc`)

**价值**: 防止在分析阶段误操作写入，符合 SOP 的渐进式授权原则。

### 10.2 Progressive Capability Authorization

**特性**: 能力授权分三步：`enable_skill` → `change_stage` → `PreToolUse`

**证据**:
- `enable_skill`: 创建 grant，进入 `initial_stage`
- `change_stage`: 推进流程，更新 `active_tools`
- `PreToolUse`: 执行准入检查，拒绝不在 `active_tools` 中的工具

**价值**: 多层防护，每一层都有明确的治理语义。

### 10.3 Runtime / Persisted State Separation

**特性**: `SessionState` 持久化，`RuntimeContext` 每回合派生，`active_tools` 不持久化。

**证据**:
- `sessions.state_json` 包含 `skills_loaded`, `active_grants`
- `sessions.state_json` 不包含 `active_tools`
- `active_tools` 每回合从 `build_runtime_context()` 重新计算

**价值**: 
- 持久化状态最小化，减少不一致风险
- `active_tools` 始终反映当前 grant 状态（包括过期检查）

### 10.4 Deny-by-default Safety

**特性**: Terminal stage 拒绝非法跳转，expired grant 不贡献工具，disabled skill 工具不可用。

**证据**:
- Terminal stage: `verification → execution` denied
- Expired grant: `yuque_search` denied after TTL=2s
- Disabled skill: `yuque_get_doc` denied after `disable_skill`

**价值**: 默认拒绝，只有显式授权的路径才允许。

### 10.5 Auditable Governance

**特性**: 每一次 allow / deny 都有 audit event，包含完整上下文。

**证据**:
- `stage.transition.allow/deny` 包含 `from_stage`, `to_stage`, `error_bucket`
- `tool.call` 包含 `decision`, `error_bucket`
- `grant.expire` / `grant.revoke` / `skill.disable` 全部可追溯

**价值**: 
- 事后审计：为什么某个工具调用被拒绝？
- 合规证明：所有治理决策有据可查

### 10.6 Realistic Subprocess Boundary

**特性**: `tg-hook` / `tg-mcp` 分离，通过 SQLite 共享状态。

**证据**:
- Stdout 日志显示 MCP server 处理 `CallToolRequest`
- Hook 和 MCP 通过 `governance.db` 共享 `sessions`, `grants`, `audit_log`
- 无直接进程间通信，完全通过持久化状态协调

**价值**: 
- 更接近 Claude Code plugin 的真实运行方式
- 验证了跨进程边界的状态一致性

---

## 11. 展示用亮点表

| 展示亮点 | 本场景证据 | 面试讲法 |
|---------|-----------|---------|
| **工具面按阶段收敛** | analysis/execution/verification 工具不同 | 我不是简单过滤工具，而是让工具面跟随 SOP 状态机变化 |
| **非法状态转移被阻断** | verification→execution deny | Stage metadata 不只是文档，而是 runtime enforcement |
| **授权过期自动失效** | TTL=2s 后 yuque_search deny | Grant TTL 参与 active_tools 计算，过期后自动失效 |
| **状态可恢复** | SQLite state_json 保存 stage_history | hook/MCP 子进程间通过持久化状态保持一致 |
| **全链路可审计** | audit_log 记录 allow/deny | 每次授权、转移、工具调用都有可追溯证据 |
| **Terminal stage 语义** | allowed_next_stages: [] 阻止转移 | 终止阶段不是"没有下一步"，而是"拒绝所有转移" |
| **Expired vs Disabled** | 两种不同的失效语义 | Expired 是自然过期，Disabled 是主动撤销，audit 分别记录 |

---

## 12. 结论

### 12.1 验证结果

✅ **Scenario 03 全部通过**

- ✅ Terminal stage enforcement (verification → execution denied)
- ✅ Stage state persistence (current_stage, stage_history, exited_stages)
- ✅ Expired grant filtering (TTL=2s natural expiration)
- ✅ Disable/revoke lifecycle (disable_skill removes tools)
- ✅ Full audit trail (12 events, all expected types present)
- ✅ Real subprocess boundary (tg-hook / tg-mcp / governance.db)

### 12.2 项目能力总结

Tool-Gate 展示了 **可控、可审计、可恢复** 的 Agent 工具治理能力：

1. **可控**: Stage-first 模型让工具暴露跟随 SOP 阶段，terminal stage 阻止非法转移
2. **可审计**: 完整 audit trail，每次 allow/deny 都有 from_stage/to_stage/error_bucket
3. **可恢复**: Stage state 持久化到 SQLite，跨进程边界保持一致

### 12.3 技术亮点

- **Runtime / Persisted State Separation**: `active_tools` 不持久化，每回合重新计算
- **Deny-by-default Safety**: Terminal stage / expired grant / disabled skill 全部默认拒绝
- **Realistic Subprocess Boundary**: 真实 hook/MCP 子进程，通过 SQLite 共享状态

---

## 附录：运行产物清单

| 文件 | 大小 | 说明 |
|------|------|------|
| `governance.db` | 40 KB | SQLite 数据库（sessions, grants, audit_log） |
| `events.jsonl` | 1.4 KB | 完整事件流水（11 events） |
| `audit_summary.md` | 231 B | 人类可读审计摘要 |
| `metrics.json` | 297 B | 事件统计 |

**数据来源**: 所有数据来自真实运行产物，非静态 mock 或手写假数据。

---

**报告结束**
