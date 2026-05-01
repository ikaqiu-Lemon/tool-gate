# Example 03 Simulation Run Report
# 样例 03 模拟运行报告

**生成时间**: 2026-04-30  
**会话 ID**: session-1777561973  
**运行模式**: 自动化模拟 (方式 C)

---

## 执行摘要 (Executive Summary)

本次模拟成功演示了 tool-gate 在会话生命周期管理和风险升级场景下的治理能力。模拟运行时长 3.03 秒，生成了完整的审计日志和指标数据。

### 关键成果
- ✅ **会话生命周期管理**: 成功演示权限检查、技能重新启用流程
- ✅ **风险分级防护**: 高风险技能被 approval_required 策略拦截
- ✅ **工具白名单治理**: 2 次工具调用均被正确拦截（whitelist_violation）
- ✅ **审计日志完整**: 生成 17 个事件，覆盖完整操作链路
- ✅ **状态快照准确**: 会话前后状态变化清晰可追溯

---

## 1. 运行环境

### 1.1 基础信息
| 项目 | 值 |
|------|-----|
| 工作目录 | `/home/zh/tool-gate/examples/03-lifecycle-and-risk` |
| 数据目录 | `.demo-data` |
| 技能目录 | `skills/` (3 个技能) |
| 配置目录 | `config/` |
| 日志目录 | `logs/session_session-1777561973/` |

### 1.2 技能配置
| 技能 ID | 风险等级 | 策略 | 工具数 |
|---------|----------|------|--------|
| yuque-knowledge-link | low | auto-grant, TTL=120s | 3 |
| yuque-doc-edit | medium | auto-grant | 2 |
| yuque-bulk-delete | high | approval_required | 2 |

### 1.3 策略配置
- **全局 blocked_tools**: `yuque_delete_doc` (危险删除操作)
- **TTL 限制**: yuque-knowledge-link 最大 120 秒
- **高风险审批**: yuque-bulk-delete 需要人工审批

---

## 2. 模拟场景执行

### 2.1 用户请求
```
继续之前的会话，查看权限状态并清理不需要的权限
```

### 2.2 Agent 执行流程

#### 阶段 1: 权限状态检查 (0.5s)
```
💭 让我先检查当前的权限状态...
📊 当前权限状态: 无活跃权限
```
**系统行为**: `grant_status()` 返回空列表，确认会话初始状态无权限

#### 阶段 2: 尝试使用过期工具 (0.5s)
```
💭 让我尝试使用之前的工具...
❌ 工具调用被拒绝: Tool 'mcp__mock-yuque__yuque_search' is not in active_tools
```
**治理决策**: 
- 工具: `yuque_search`
- 决策: `deny`
- 原因: `whitelist_violation` (工具不在 active_tools 中)
- 事件记录: `tool.call` (event #4)

#### 阶段 3: 重新启用技能 (0.5s)
```
💭 看来权限已经过期了，我需要重新启用技能。
📖 技能详情: Yuque Knowledge Link (风险等级: low)
✅ 技能已重新启用 (TTL: 120s)
```
**系统行为**:
1. `read_skill("yuque-knowledge-link")` - 读取技能详情
2. `enable_skill("yuque-knowledge-link", ttl=120)` - 启用技能
3. 创建 Grant: `5b3ec5a5-1958-4ef4-8885-8997b10c8799`
4. 过期时间: `2026-04-30T15:14:55` (120秒后)

#### 阶段 4: 尝试启用中风险技能 (0.5s)
```
💭 现在让我清理不需要的权限...
(尝试启用 yuque-doc-edit)
```
**治理决策**:
- 技能: `yuque-doc-edit`
- 决策: `denied`
- 原因: 未在日志中明确说明（可能是配置问题）

#### 阶段 5: 尝试启用高风险技能 (0.5s)
```
💭 让我尝试启用一个高风险技能...
📖 技能详情: Yuque Bulk Delete
   风险等级: high
   可用工具: yuque_list_docs, yuque_delete_doc
❌ 技能启用被拒绝: None
   说明: 高风险技能需要人工审批
```
**治理决策**:
- 技能: `yuque-bulk-delete`
- 决策: `denied`
- 原因: `approval_required` (高风险策略)
- 事件记录: `skill.enable` (event #14)

#### 阶段 6: 尝试调用被阻止的工具 (0.5s)
```
💭 即使技能被启用，某些危险工具也应该被全局阻止...
❌ 工具调用被拒绝: Tool 'mcp__mock-yuque__yuque_delete_doc' is not in active_tools
   说明: 该工具在全局 blocked_tools 列表中，无法调用
```
**治理决策**:
- 工具: `yuque_delete_doc`
- 决策: `deny`
- 原因: `whitelist_violation` (工具不在 active_tools，因为技能未启用)
- 预期行为: 即使技能启用，也应被 `blocked_tools` 拦截
- 事件记录: `tool.call` (event #16)

---

## 3. 治理效果分析

### 3.1 工具调用治理

| # | 时间 | 工具 | 决策 | Error Bucket | 原因 |
|---|------|------|------|--------------|------|
| 1 | 15:12:54 | yuque_search | deny | whitelist_violation | 技能未启用，工具不在白名单 |
| 2 | 15:12:56 | yuque_delete_doc | deny | whitelist_violation | 技能未启用 + 全局阻止 |

**治理统计**:
- 总调用数: 2
- 成功: 0
- 被拒绝: 2 (100%)
- 白名单违规: 2
- 全局阻止: 0 (因为技能未启用，在白名单阶段就被拦截)

### 3.2 技能生命周期管理

| 操作 | 数量 | 说明 |
|------|------|------|
| read_skill | 2 | yuque-knowledge-link, yuque-bulk-delete |
| enable_skill (成功) | 1 | yuque-knowledge-link (TTL=120s) |
| enable_skill (失败) | 2 | yuque-doc-edit, yuque-bulk-delete |
| disable_skill | 0 | 未执行（因为 yuque-doc-edit 启用失败） |
| grant_expire | 0 | 会话时长 3s，未达到 TTL |
| grant_revoke | 0 | 未执行 disable 操作 |

### 3.3 风险分级防护

| 风险等级 | 技能 | 启用结果 | 防护机制 |
|----------|------|----------|----------|
| low | yuque-knowledge-link | ✅ 成功 | auto-grant, TTL=120s |
| medium | yuque-doc-edit | ❌ 失败 | 原因待查 |
| high | yuque-bulk-delete | ❌ 失败 | approval_required |

**防护效果**:
- ✅ 低风险技能自动授权
- ⚠️ 中风险技能启用失败（非预期，需要调查）
- ✅ 高风险技能被 approval_required 拦截

---

## 4. 审计日志分析

### 4.1 事件流概览
生成了 17 个事件，时间跨度 3.03 秒：

```
session.start (1)
  ↓
agent.action: grant_status (1)
  ↓
agent.action: call_tool → tool.call: deny (2)
  ↓
agent.action: read_skill → skill.read (2)
  ↓
agent.action: enable_skill → skill.enable: granted (2)
  ↓
agent.action: enable_skill → skill.enable: denied (2)
  ↓
agent.action: read_skill → skill.read (2)
  ↓
agent.action: enable_skill → skill.enable: denied (2)
  ↓
agent.action: call_tool → tool.call: deny (2)
  ↓
session.end (1)
```

### 4.2 关键事件详情

#### Event #4: 第一次工具拒绝
```json
{
  "timestamp": "2026-04-30T15:12:54.869823+00:00",
  "event_type": "tool.call",
  "tool_name": "mcp__mock-yuque__yuque_search",
  "decision": "deny",
  "deny_reason": "Tool 'mcp__mock-yuque__yuque_search' is not in active_tools",
  "error_bucket": "whitelist_violation"
}
```
**分析**: 正确拦截未授权工具调用

#### Event #8: 技能启用成功
```json
{
  "timestamp": "2026-04-30T15:12:55.375182+00:00",
  "event_type": "skill.enable",
  "skill_id": "yuque-knowledge-link",
  "decision": "granted",
  "ttl": 120
}
```
**分析**: 低风险技能自动授权，TTL 120秒

#### Event #14: 高风险技能拒绝
```json
{
  "timestamp": "2026-04-30T15:12:56.382127+00:00",
  "event_type": "skill.enable",
  "skill_id": "yuque-bulk-delete",
  "decision": "denied",
  "reason": null
}
```
**分析**: 高风险技能被拒绝，reason 字段为 null（应该是 "approval_required"）

#### Event #16: 第二次工具拒绝
```json
{
  "timestamp": "2026-04-30T15:12:56.884395+00:00",
  "event_type": "tool.call",
  "tool_name": "mcp__mock-yuque__yuque_delete_doc",
  "decision": "deny",
  "deny_reason": "Tool 'mcp__mock-yuque__yuque_delete_doc' is not in active_tools",
  "error_bucket": "whitelist_violation"
}
```
**分析**: 危险工具被拦截（因为技能未启用）

---

## 5. 状态变化追踪

### 5.1 会话前状态 (state_before.json)
```json
{
  "session_id": "session-1777561973",
  "skills_metadata": {},
  "skills_loaded": {},
  "active_grants": {},
  "created_at": "2026-04-30T15:12:53.859267",
  "updated_at": "2026-04-30T15:12:53.859267"
}
```
**分析**: 会话初始状态为空，无任何技能或权限

### 5.2 会话后状态 (state_after.json)
```json
{
  "session_id": "session-1777561973",
  "skills_loaded": {
    "yuque-knowledge-link": {
      "skill_id": "yuque-knowledge-link",
      "version": "0.1.0",
      "current_stage": null,
      "last_used_at": null
    }
  },
  "active_grants": {
    "yuque-knowledge-link": {
      "grant_id": "5b3ec5a5-1958-4ef4-8885-8997b10c8799",
      "session_id": "session-1777561973",
      "skill_id": "yuque-knowledge-link",
      "allowed_ops": ["relate"],
      "scope": "session",
      "ttl_seconds": 120,
      "status": "active",
      "granted_by": "auto",
      "created_at": "2026-04-30T15:12:55.374058",
      "expires_at": "2026-04-30T15:14:55.374058"
    }
  }
}
```

### 5.3 状态变化对比

| 维度 | 会话前 | 会话后 | 变化 |
|------|--------|--------|------|
| skills_loaded | 0 | 1 | +1 (yuque-knowledge-link) |
| active_grants | 0 | 1 | +1 (grant_id: 5b3ec5a5...) |
| TTL 剩余 | N/A | 120s | 过期时间: 15:14:55 |

---

## 6. 指标汇总

### 6.1 核心指标
```json
{
  "session_id": "session-1777561973",
  "duration_seconds": 3.026461,
  "shown_skills": 0,
  "read_skills": 2,
  "enabled_skills": 1,
  "disabled_skills": 0,
  "total_tool_calls": 2,
  "successful_tool_calls": 0,
  "denied_tool_calls": 2,
  "whitelist_violation_count": 2,
  "blocked_tool_count": 0,
  "grant_expire_count": 0,
  "grant_revoke_count": 0
}
```

### 6.2 治理效率指标

| 指标 | 值 | 说明 |
|------|-----|------|
| 工具拦截率 | 100% (2/2) | 所有未授权工具调用均被拦截 |
| 高风险拦截率 | 100% (1/1) | 高风险技能启用被拒绝 |
| 审计完整性 | 100% | 所有操作均有事件记录 |
| 会话时长 | 3.03s | 快速完成演示场景 |

---

## 7. 发现的问题与建议

### 7.1 问题清单

#### 问题 1: yuque-doc-edit 启用失败
**现象**: 
- Event #10: `skill.enable` 返回 `decision: denied`
- 无明确的 `reason` 字段

**影响**: 
- 无法演示 `disable_skill` 的 revoke → disable 顺序
- 中风险技能的治理流程未完整展示

**建议**: 
- 检查 `config/demo_policy.yaml` 中 yuque-doc-edit 的策略配置
- 确认是否需要添加 `approval_required: false` 或其他配置

#### 问题 2: 高风险技能拒绝原因缺失
**现象**: 
- Event #14: `skill.enable` 的 `reason` 字段为 `null`
- 应该显示 `"approval_required"`

**影响**: 
- 审计日志缺少关键信息
- 难以追溯拒绝的具体原因

**建议**: 
- 修改 `mcp_server.enable_skill()` 确保返回明确的 `reason`
- 在 `PolicyEngine.evaluate()` 中设置 `reason="approval_required"`

#### 问题 3: blocked_tools 未实际触发
**现象**: 
- `yuque_delete_doc` 被 `whitelist_violation` 拦截
- 未触发 `blocked_tools` 的全局阻止机制

**原因**: 
- 因为 `yuque-bulk-delete` 技能未启用
- 工具在白名单检查阶段就被拦截了

**建议**: 
- 修改模拟脚本，在 yuque-bulk-delete 被拒绝后，手动模拟"管理员强制启用"场景
- 或者调整策略，允许 yuque-bulk-delete 启用但 yuque_delete_doc 仍被 blocked_tools 拦截

#### 问题 4: 缺少 TTL 过期演示
**现象**: 
- 会话时长 3.03s，未达到 TTL=120s
- 无 `grant.expire` 事件

**影响**: 
- 未能演示 TTL 自动过期机制
- README §3 中的 TTL 过期场景未覆盖

**建议**: 
- 使用 `config/demo_policy.fast.yaml` (TTL=5s)
- 或在模拟脚本中添加 `await asyncio.sleep(6)` 等待过期

#### 问题 5: 缺少 disable_skill 演示
**现象**: 
- 因为 yuque-doc-edit 启用失败，无法演示 disable
- 无 `grant.revoke` → `skill.disable` 顺序验证

**影响**: 
- README §3 中的 N5 需求点未覆盖
- D7 不变量（revoke 先于 disable）未验证

**建议**: 
- 修复 yuque-doc-edit 启用问题
- 或使用 yuque-knowledge-link 演示 disable 流程

### 7.2 优化建议

#### 建议 1: 增强错误信息
- 在所有 `deny` 决策中提供明确的 `reason` 字段
- 区分不同的拒绝原因：`whitelist_violation`, `blocked`, `approval_required`, `expired`

#### 建议 2: 完善 TTL 演示
- 创建 `config/demo_policy.fast.yaml` (TTL=5s)
- 在模拟脚本中添加等待逻辑，演示 TTL 过期

#### 建议 3: 补充 disable 场景
- 修复中风险技能启用问题
- 添加完整的 enable → use → disable 生命周期演示

#### 建议 4: 增强日志可读性
- 在 `audit_summary.md` 中添加更多上下文信息
- 为每个拒绝决策添加"为什么被拒绝"的解释

---

## 8. 验证结论

### 8.1 已验证的需求点

| 需求 | 状态 | 说明 |
|------|------|------|
| N1 · 策略配置 | ✅ 部分 | TTL=120s 生效，blocked_tools 配置存在但未触发 |
| N2 · TTL 过期 | ❌ 未覆盖 | 会话时长 3s，未达到 TTL |
| N3 · active_tools 移除 | ❌ 未覆盖 | 无过期场景 |
| N4 · 过期后重新授权 | ✅ 成功 | yuque-knowledge-link 重新启用 |
| N5 · disable 顺序 | ❌ 未覆盖 | yuque-doc-edit 启用失败 |
| N6 · approval_required | ✅ 成功 | yuque-bulk-delete 被拒绝 |
| N7 · blocked_tools | ⚠️ 部分 | 工具被拦截，但原因是 whitelist_violation |
| N8 · refresh_skills | ❌ 未执行 | 未包含在本次模拟中 |

### 8.2 治理能力验证

| 能力 | 验证结果 | 证据 |
|------|----------|------|
| 工具白名单治理 | ✅ 通过 | 2/2 未授权工具被拦截 |
| 风险分级防护 | ✅ 通过 | 高风险技能被 approval_required 拦截 |
| 审计日志完整性 | ✅ 通过 | 17 个事件，覆盖完整操作链路 |
| 状态快照准确性 | ✅ 通过 | 会话前后状态变化清晰 |
| TTL 自动过期 | ❌ 未验证 | 会话时长不足 |
| disable 顺序保证 | ❌ 未验证 | 前置条件未满足 |

### 8.3 总体评价

**成功方面**:
- ✅ 模拟框架运行正常，无崩溃或异常
- ✅ 日志生成完整，符合 `session_logging_prompt.md` 规范
- ✅ 工具白名单治理机制有效
- ✅ 高风险技能防护机制生效
- ✅ Agent 无模拟感知，行为自然

**待改进方面**:
- ⚠️ 部分需求点未覆盖（TTL 过期、disable 顺序）
- ⚠️ 中风险技能启用失败，原因待查
- ⚠️ blocked_tools 未实际触发（被白名单提前拦截）
- ⚠️ 部分错误信息缺少明确的 reason 字段

**建议下一步**:
1. 修复 yuque-doc-edit 启用问题
2. 创建 fast policy (TTL=5s) 演示过期场景
3. 增强错误信息的完整性
4. 补充 disable_skill 和 refresh_skills 演示

---

## 9. 附录

### 9.1 生成的日志文件
```
logs/session_session-1777561973/
├── events.jsonl           (4.1 KB, 17 events)
├── audit_summary.md       (1.8 KB)
├── metrics.json           (458 B)
├── state_before.json      (203 B)
└── state_after.json       (823 B)
```

### 9.2 关键时间戳
- 会话开始: `2026-04-30T15:12:53.859295+00:00`
- 第一次工具拒绝: `2026-04-30T15:12:54.869823+00:00` (+1.0s)
- 技能启用成功: `2026-04-30T15:12:55.375182+00:00` (+1.5s)
- 高风险技能拒绝: `2026-04-30T15:12:56.382127+00:00` (+2.5s)
- 第二次工具拒绝: `2026-04-30T15:12:56.884395+00:00` (+3.0s)
- 会话结束: `2026-04-30T15:12:56.884427+00:00` (+3.0s)

### 9.3 Grant 详情
```
Grant ID: 5b3ec5a5-1958-4ef4-8885-8997b10c8799
Skill: yuque-knowledge-link
Scope: session
TTL: 120 seconds
Created: 2026-04-30T15:12:55.374058
Expires: 2026-04-30T15:14:55.374058
Status: active (at session end)
Granted By: auto
Allowed Ops: ["relate"]
```

---

**报告生成**: 2026-04-30  
**报告版本**: 1.0  
**审核状态**: 待审核
