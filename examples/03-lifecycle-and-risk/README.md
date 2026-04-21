# 样例 03 · 会话生命周期与风险升级

> 本样例展示 tool-gate 在**长会话**中的能力**回收**与**风险升级**机制。主线围绕 TTL / revoke / disable / 高风险审批 / 审计闭环展开;`refresh_skills` 不在主线(其主场景在[样例 01 的附录](../01-knowledge-link/README.md#附录--refresh_skills-插曲)),本样例仅在末尾做一次辅助复核触发。

> ⚠️ **Preflight**:本 workspace **不负责**项目安装。先读 [`../QUICKSTART.md`](../QUICKSTART.md)(§1 概念 + wiring / §2 零知识安装 / §7 preflight 自检),按 §2 在**仓库根**完成一次性安装之后再回来跑本样例。workspace 目录仅负责 demo run。

---

## 0. 业务背景与展示目标

**业务背景**:Alice 下午继续工作,会话已经开了几个小时。早上启用的 `yuque-knowledge-link`(short TTL = 120s)应该早就过期;她顺手还把 `yuque-doc-edit` 也启用着。现在她要清理权限、并尝试一个危险操作(批量删除过期文档)——这个操作预期会被 tool-gate 拦两层:高风险策略审批 + 全局 `blocked_tools`。

**展示目标**:
1. 证明 TTL 到期后,`UserPromptSubmit` 下一轮重算自动把过期技能从 `active_tools` 移除;相关工具尝试被拦
2. 证明 `disable_skill` 立即下线工具,并在审计表里呈现 **`grant.revoke` → `skill.disable`** 严格顺序
3. 证明高风险技能 `enable_skill` 返回 `approval_required`;即便用户硬启用成功(演示不走该分支),对应工具在 `blocked_tools` 里仍被兜底拦截 —— **两层防线**
4. 证明审计闭环可追查:`grant.expire` / `grant.revoke` / `skill.disable` / `skill.enable (denied)` / `tool.call (blocked)` 每一行都有清晰的 subject、reason、时间戳

---

## 1. 需求点

- N1 · `config/demo_policy.yaml` 将 `yuque-knowledge-link` 的 `max_ttl` 限制为 120 秒,`yuque-bulk-delete` 设置为 `approval_required: true`,并把 `yuque_delete_doc` 列入 `blocked_tools`
- N2 · 从早上 10:32 启用的 `yuque-knowledge-link` grant 应在 10:34 过期;下午 14:00 开始新回合时,`grant.expire` 应该已经发生
- N3 · `UserPromptSubmit` 重算时应把 `yuque_search / yuque_list_docs / yuque_get_doc` 从 `active_tools` 移除
- N4 · 对已过期技能再调 `yuque_search` → `PreToolUse deny`;模型应走 `read_skill` + `enable_skill` 重新授权路径
- N5 · `disable_skill("yuque-doc-edit")` 立即让 `yuque_update_doc` 下线;审计表严格先出现 `grant.revoke` 再出现 `skill.disable`(D7 不变量)
- N6 · `enable_skill("yuque-bulk-delete")` 返回 `decision=denied reason=approval_required`
- N7 · 若通过假设路径强行走到调 `yuque_delete_doc`,`PreToolUse` 因 `blocked_tools` deny;原因字段为 `blocked`
- N8 · 本样例**末尾**做一次 `refresh_skills` 作为辅助复核(让功能/接口矩阵 03 列 `refresh_skills=●` 有实际打点);但**不得**让 refresh 承担主剧情

---

## 2. 演示前置与启动

### 2.1 环境变量(两条路径都要导出)

```bash
cd examples/03-lifecycle-and-risk/

export GOVERNANCE_DATA_DIR="$PWD/.demo-data"
export GOVERNANCE_SKILLS_DIR="$PWD/skills"
export GOVERNANCE_CONFIG_DIR="$PWD/config"
```

三个 env var 的作用与缺失时的症状见 [`../QUICKSTART.md §1.3`](../QUICKSTART.md#13--三个-governance_-环境变量)。

### 2.2 启动(两条路径,方式 B 首推)

**方式 B · 离线子进程 replay**(零 API key,决策 stdout 可见;通用模板见 [`../QUICKSTART.md §3.1`](../QUICKSTART.md#31--方式-b--子进程-replayoffline--免-api-key))

```bash
# SessionStart:期望 stdout 列出 3 个技能
# (Yuque Knowledge Link low / Yuque Doc Edit medium / Yuque Bulk Delete high)
echo '{"event":"SessionStart","session_id":"03","cwd":"'"$PWD"'"}' | tg-hook

# PreToolUse on yuque_delete_doc(全局 blocked_tools 兜底):期望 permissionDecision:"deny"
echo '{"event":"PreToolUse","session_id":"03","tool_name":"yuque_delete_doc","tool_input":{}}' | tg-hook

# PreToolUse on yuque_search(yuque-knowledge-link 未 enable):期望 permissionDecision:"deny"
echo '{"event":"PreToolUse","session_id":"03","tool_name":"yuque_search","tool_input":{}}' | tg-hook
```

实测 stdout 见 §5.2。方式 B replay **不写审计**,完整生命周期链(TTL 到期 / `grant.revoke` / `skill.disable` / `approval_required`)走方式 A。

**方式 A · Claude Code CLI**(需 Anthropic API key;完整交互演示)

```bash
claude --plugin-dir ../../ --mcp-config ./.mcp.json
```

启动后按 §3 操作三列表逐行演示。链路概览见 [`../QUICKSTART.md §3.2`](../QUICKSTART.md#32--方式-a--claude-code-cli进阶需-anthropic-api-key--联网)。

### 2.3 时间推进(TTL 加速)

实际演示不等 120 秒 TTL 过期太慢。两种加速方案任选其一:

- **方案 A(推荐,文件切换)**:使用 Stage D 提供的 `config/demo_policy.fast.yaml`(`max_ttl: 5`),临时把启动命令的 `GOVERNANCE_CONFIG_DIR` 指到它,或在 `config/demo_policy.yaml` 上做软链 —— 文件由 Stage D 落地,届时本段会补齐具体切换命令
- **方案 B(现场 inline diff)**:临时把 `config/demo_policy.yaml` 的 `max_ttl` 从 120 改成 5,配合手动 `sleep 6` 等待过期;演示后 `git checkout -- config/demo_policy.yaml` 回滚

两种方案都在 §5.1 预期审计中预留了 `grant.expire` 行。Stage D 落地 `demo_policy.fast.yaml` 前,建议用方案 B。

---

## 3. 操作步骤(主线)

| 时间戳 | 操作者输入 | 模型预期动作 | 系统侧事件 |
|---|---|---|---|
| 2026-04-19T14:00:00+08:00 | Alice 继续之前的会话 | `grant_status()` | `UserPromptSubmit` → `cleanup_expired_grants` 发现 `yuque-knowledge-link` 已过期;返回当前仅剩 `yuque-doc-edit`(execution);审计已有 `grant.expire yuque-knowledge-link at=10:34:31+08:00` |
| 2026-04-19T14:00:07+08:00 | Alice:"再查一次早上那批 RAG 笔记有没有新的" | `yuque_search(query="RAG")` | `PreToolUse` **deny** → `additionalContext`:"`yuque_search` 不在当前 `active_tools`;已过期技能 `yuque-knowledge-link` 需要重新 `enable_skill`";审计写 `tool.call whitelist_violation yuque_search reason=expired_skill` |
| 2026-04-19T14:00:14+08:00 | — | `read_skill("yuque-knowledge-link")` → `enable_skill("yuque-knowledge-link")` | `PolicyEngine.evaluate` → `max_ttl=120` 适用;新的 `Grant` 创建 TTL=120;`active_tools` 重新追加 3 个 yuque 只读工具;审计写 `skill.enable granted_by=auto ttl=120` |
| 2026-04-19T14:00:30+08:00 | Alice:"算了,这批的权限清掉吧,今天先不搞了" | `disable_skill("yuque-doc-edit")` | `GrantManager.revoke_grant` → 审计写 `grant.revoke yuque-doc-edit`;然后 `StateManager.unload_skill` → 审计写 `skill.disable yuque-doc-edit`;**顺序严格:revoke 先,disable 后**;`active_tools` 去除 `yuque_update_doc` 与 execution stage 的其它工具 |
| 2026-04-19T14:00:35+08:00 | Alice:"顺手把过期的冗余文档批量删了吧" | `read_skill("yuque-bulk-delete")` | 返回 `risk_level: high`、`allowed_tools: [yuque_list_docs, yuque_delete_doc]`;审计写 `skill.read risk=high` |
| 2026-04-19T14:00:42+08:00 | — | `enable_skill("yuque-bulk-delete", reason="清理 2024 年之前的过期笔记")` | `PolicyEngine.evaluate` → `skill_policies.yuque-bulk-delete.approval_required=true` → `decision=denied reason=approval_required`;审计写 `skill.enable decision=denied reason=approval_required` |
| 2026-04-19T14:00:50+08:00 | Alice(假设路径):"那走管理员通道强启用了" | (假设审批通过)`yuque-bulk-delete` 已启用 → `yuque_delete_doc(doc_id="old-2023")` | 即便跳过 approval,`yuque_delete_doc` 仍在 `blocked_tools` 中 → `PreToolUse` **deny** → `additionalContext`:"`yuque_delete_doc` 在全局 `blocked_tools`,与 skill 的授权状态无关";审计写 `tool.call yuque_delete_doc decision=deny reason=blocked` |
| 2026-04-19T14:01:00+08:00 | Alice:"好吧我放弃这条路,改手动清" | `grant_status()` | 返回当前仅剩 `yuque-knowledge-link`(ttl_remaining ≈ 90s);用于给 Alice 做能力盘点 |
| 2026-04-19T14:02:15+08:00 | (等待 ~90s 后)Alice 继续看文档 | `yuque_search(query="RAG")` | 第二次 TTL 过期 + `UserPromptSubmit` 重算 → `yuque_search` 再次被拦;审计写 `grant.expire yuque-knowledge-link` 的第二行 |

### 附录(辅助复核)· `refresh_skills` 打点

> 主场景见[样例 01](../01-knowledge-link/README.md#附录--refresh_skills-插曲)。此处仅为让功能/接口矩阵的 `refresh_skills: 03=●` 有实际打点,不承担剧情。

| 时间戳 | 操作者输入 | 模型预期动作 | 系统侧事件 |
|---|---|---|---|
| 2026-04-19T14:05:00+08:00 | (后台)拷 `skills_incoming/yuque-comment-sync` 到 `skills/` | — | 目录变化但尚未 refresh |
| 2026-04-19T14:05:03+08:00 | — | `refresh_skills()` | `SkillIndexer.build_index()` 执行一次;返回 `{count: 4}`(原 3 + 新 1);审计写 `skills.index.refresh count=4 single_scan=true` |

---

## 4. 系统内部行为说明

- **TTL 到期 → 自动出场**:grant 有 `expires_at`,`GrantManager.cleanup_expired` 在 `SessionStart` 和 `UserPromptSubmit` 都会跑;过期的 grant 被标记并发 `grant.expire` 审计;`skills_loaded` 集合里的对应 skill 移除;`ToolRewriter` 下一次重算自然把对应工具踢出。**全量重算**意味着过期处理不需要额外"减法"逻辑。
- **`disable_skill` 的审计顺序 = D7 不变量**:`mcp_server.disable_skill` 先调 `grant_manager.revoke_grant`(写 `grant.revoke`)再调 `state_manager.unload_skill`(写 `skill.disable`)。两条审计的 `created_at` 严格 `revoke < disable`,若顺序颠倒视为 D7 违规。
- **两层防线**(高风险):
  - 第一层 = `PolicyEngine.evaluate` 的 `approval_required` 分支,返回 `denied`,**不创建 grant**
  - 第二层 = 即便 grant 存在(例如走 `granted_by=user` 的管理员通道),`ToolRewriter` 仍会在 `compute_active_tools` 里用 `blocked_tools` 过滤掉 `yuque_delete_doc`;`PreToolUse` 兜底 deny,原因 = `blocked`
- **`grant_status` 的诊断价值**:长会话中用它可以快速回答"哪些 grant 还活着、各自 TTL 剩多少、处于什么 stage";这是 `error_bucket`(按拒绝原因分桶)与 `funnel/trace` 指标的关键上游。

---

## 5. 预期输出 / 日志 / 审计

### 5.1 Audit 行形状(仅列本样例新增的关键行,按时间戳顺序)

```
created_at                         event                     subject                                       meta
2026-04-19T10:34:31+08:00          grant.expire              skill=yuque-knowledge-link                    reason=ttl
2026-04-19T14:00:00+08:00          session.resume            session=demo-03                               cleanup_expired=1
2026-04-19T14:00:07+08:00          tool.call                 tool=yuque_search                             decision=deny reason=whitelist_violation (expired_skill)
2026-04-19T14:00:14+08:00          skill.enable              skill=yuque-knowledge-link                    decision=granted ttl=120 granted_by=auto
2026-04-19T14:00:30+08:00          grant.revoke              skill=yuque-doc-edit                          trigger=disable_skill
2026-04-19T14:00:30+08:00          skill.disable             skill=yuque-doc-edit                          (直接紧跟上一行,顺序不可颠倒)
2026-04-19T14:00:35+08:00          skill.read                skill=yuque-bulk-delete                       risk=high
2026-04-19T14:00:42+08:00          skill.enable              skill=yuque-bulk-delete                       decision=denied reason=approval_required
2026-04-19T14:00:50+08:00          tool.call                 tool=yuque_delete_doc                         decision=deny reason=blocked
2026-04-19T14:02:15+08:00          grant.expire              skill=yuque-knowledge-link                    reason=ttl
2026-04-19T14:05:03+08:00          skills.index.refresh      count=4                                       single_scan=true
```

### 5.2 关键拒绝 `additionalContext` 形状(Phase B 回填)

```
// expired_skill 触发的 whitelist_violation:
"tool `yuque_search` requires skill `yuque-knowledge-link` which expired at 10:34:31+08:00. Run read_skill → enable_skill to re-authorize."

// approval_required:
"skill `yuque-bulk-delete` (risk=high) requires human approval. Escalate via your admin channel."

// blocked_tools 兜底:
"tool `yuque_delete_doc` is in global blocked_tools and cannot be invoked regardless of skill grants."
```

> **实测记录 · `tg-hook` 子进程退化路径(2026-04-21)**:
>
> 方式:`cd examples/03-lifecycle-and-risk && GOVERNANCE_DATA_DIR=/tmp/tg-demo-03 GOVERNANCE_SKILLS_DIR=$PWD/skills GOVERNANCE_CONFIG_DIR=$PWD/config`,事件通过 `echo '{"event":"<Name>",...}' | tg-hook` 送入。
>
> - **`SessionStart`** → `additionalContext` 列出 3 个技能:`Yuque Bulk Delete (high)` / `Yuque Doc Edit (medium)` / `Yuque Knowledge Link (low)`,`SkillIndexer` 对高风险技能仍发现并索引(符合 §4 "高风险技能进索引但 enable 时被 `approval_required` 拦"的前提)
> - **`PreToolUse` `yuque_delete_doc`**(`blocked_tools` 列表项 + 未 enable)→ `{"permissionDecision":"deny", …}`
> - **`PreToolUse` `yuque_search`**(`yuque-knowledge-link` 未 enable)→ 同上形状
> - **`governance.db.audit_log`** 新增 2 行 `tool.call / deny / error_bucket=whitelist_violation`
>
> **差异**:`grant.expire` / `grant.revoke` / `skill.disable` / `approval_required` / `blocked` bucket 依赖 TTL 到期 + `disable_skill` + `enable_skill` 元工具链,子进程退化仅覆盖 `whitelist_violation` 一类;§5.1 剩余生命周期 / 高风险 deny 审计行与 §5.2 上方针对性文案待 Claude CLI 交付现场补录。

### 5.3 Verify(通用 SQL 见 QUICKSTART §4)

按 [`../QUICKSTART.md §4`](../QUICKSTART.md#4--verify-通用套路) 的 SQL 模板查询 `$GOVERNANCE_DATA_DIR/governance.db`。**方式 A 完整跑完**时,期望看到 §5.1 列出的 11 行审计 —— 本样例的**强顺序不变量**:(a)`grant.expire yuque-knowledge-link reason=ttl` 至少 2 次(早晨一次 + 下午 ~90s 后再一次);(b)`grant.revoke yuque-doc-edit` 紧接 `skill.disable yuque-doc-edit`,`created_at` 严格 `revoke < disable`(D7 不变量);(c)`skill.enable yuque-bulk-delete decision=denied reason=approval_required` 必须出现;(d)`tool.call yuque_delete_doc decision=deny reason=blocked`(注意 `reason=blocked` 非 `whitelist_violation`,体现"两层防线"第二层)。**只跑方式 B** 时审计表为空或不存在是预期。

---

## 6. Mock 工具契约速览

| 工具 | 所在 MCP | 本样例调用? | 契约详表 |
|---|---|---|---|
| `yuque_search` | `mock-yuque` | ● 过期前后各一次(验证 TTL 出场) | [`contracts/yuque_tools_contract.md#yuque_search`](./contracts/yuque_tools_contract.md#yuque_search) |
| `yuque_list_docs` | `mock-yuque` | ○ 允许但主线未调 | [`contracts/yuque_tools_contract.md#yuque_list_docs`](./contracts/yuque_tools_contract.md#yuque_list_docs) |
| `yuque_get_doc` | `mock-yuque` | ○ | [`contracts/yuque_tools_contract.md#yuque_get_doc`](./contracts/yuque_tools_contract.md#yuque_get_doc) |
| `yuque_update_doc` | `mock-yuque` | ○ | [`contracts/yuque_tools_contract.md#yuque_update_doc`](./contracts/yuque_tools_contract.md#yuque_update_doc) |
| `yuque_delete_doc` | `mock-yuque` | ● **高风险工具**,被 `blocked_tools` 兜底 deny | [`contracts/yuque_tools_contract.md#yuque_delete_doc`](./contracts/yuque_tools_contract.md#yuque_delete_doc) |

---

## 7. 代码与测试依据

- 主链路对照实现:
  - `src/tool_governance/core/grant_manager.py` → `cleanup_expired` / `revoke_grant`
  - `src/tool_governance/core/state_manager.py` → TTL 扫描、revoke→disable 顺序
  - `src/tool_governance/core/skill_indexer.py` → `build_index` 单次调用(附录 refresh 辅助打点)
  - `src/tool_governance/core/policy_engine.py` → `approval_required` 分支 + `blocked_tools` 叠加
- 对照 functional tests:
  - `tests/functional/test_functional_ttl.py` — TTL 到期 + `grant.expire`
  - `tests/functional/test_functional_revoke.py` — `disable_skill` 审计顺序(D7)
  - `tests/functional/test_functional_policy_e2e_lifecycle.py::E7/E8/E9` — 策略下的 TTL / stage / revoke 闭环
  - `tests/functional/test_functional_refresh.py` — `refresh_skills` 单次 `build_index`(仅附录用)

---

## 8. Reset 与本 workspace 专属 troubleshooting

### 8.1 Reset(跑第二次前清理 demo 状态)

```bash
cd examples/03-lifecycle-and-risk/
rm -rf ./.demo-data
```

只删本 workspace 的 `.demo-data/`(含 `governance.db`);**不要触碰** `skills/`、`mcp/`、`schemas/`、`contracts/`、`config/`、`.mcp.json` —— 它们是演示资产本身。通用安全口径见 [`../QUICKSTART.md §5`](../QUICKSTART.md#5--reset-通用套路)。

> 本样例特别提示:如果跑过方案 B 的 inline TTL 改动又忘了回滚,Reset 时也要一并 `git checkout -- config/demo_policy.yaml`。

### 8.2 本 workspace 专属 troubleshooting

共性症状(pip 错目录、`tg-hook` 返回 `{}`、`GOVERNANCE_*` 未导出、`.mcp.json` 相对路径断裂等)见 [`../QUICKSTART.md §6`](../QUICKSTART.md#6--troubleshooting8-类常见启动失败)。本 workspace 独有症状如下:

| 症状 | 根因 | 验证 | 修复 |
|---|---|---|---|
| §3 14:00:00+08:00 那一行期望 `grant.expire yuque-knowledge-link` 已经发生,实际 `grant_status` 仍显示 `yuque-knowledge-link` 未过期 | 现场演示没跑足够长的时间窗口 —— `max_ttl=120` 默认值下必须等 120s;或时间推进方案未生效 | `grant_status()` 返回的 `ttl_remaining` 是否 `> 0` | 按 §2.3 方案 A 切 `demo_policy.fast.yaml`(Stage D 落地后)或方案 B 手工改 `max_ttl: 5` 并 `sleep 6` |
| `disable_skill("yuque-doc-edit")` 后审计表里 `skill.disable` 行在 `grant.revoke` **之前**出现 | D7 顺序违规,代表实现端问题(不应在 demo 路径发生) | `SELECT created_at, event, skill_id FROM audit WHERE event IN ('grant.revoke','skill.disable') AND skill_id='yuque-doc-edit' ORDER BY created_at;` | 这是实现回归,**不属于 demo 使用问题**;归档前请反馈给 `add-delivery-demo-workspaces` 或核心维护 |
| `yuque_delete_doc` 被 deny,看到原因 `whitelist_violation` 而非 `blocked` | 演示者没走"假设路径强启用 bulk-delete"那一步;未 enable 时 deny 归 `whitelist_violation` 是正常;`blocked` 只有在 `yuque-bulk-delete` 已 enable 的情况下才会被兜底拦 | §5.1 最后一行 `tool.call yuque_delete_doc decision=deny reason=blocked` 需要走管理员通道假设启用,才是两层防线第二层展示 | 按 §3 14:00:50 行的**假设路径**注释:即便跳过 `approval_required` 把 skill 强启用,`blocked_tools` 仍兜底拦;若仅演示第一层,止步于 `approval_required` deny 即可 |
| `refresh_skills` 附录(§3 附录 14:05:03)被当成主线,读者以为是 01 的 refresh 情节 | 03 主线**不包含** `refresh_skills`;附录仅为让功能矩阵的"03 列 refresh_skills=●"有实际打点;主场景在 [01 的附录](../01-knowledge-link/README.md#附录--refresh_skills-插曲) | 看 §0 开头粗体提示,以及附录的引言 | 直接跳过附录;主线验收只看 §3 主表 |
