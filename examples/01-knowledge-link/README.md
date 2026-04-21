# 样例 01 · 知识关联:首次发现与自动授权

> 本样例展示 tool-gate 的**基础主流程**:一个新会话中,Claude 如何被引导从"看到技能目录 → 阅读 SOP → 启用技能 → 使用工具"一步步走过来;在这条链路上,**混杂工具会被真实拦住**。

> ⚠️ **Preflight**:本 workspace **不负责**项目安装。先读 [`../QUICKSTART.md`](../QUICKSTART.md)(§1 概念 + wiring / §2 零知识安装 / §7 preflight 自检),按 §2 在**仓库根**完成一次性安装之后再回来跑本样例。workspace 目录仅负责 demo run。

---

## 0. 业务背景与展示目标

**业务背景**:Alice 是一名知识工程师,正在维护团队内部的 RAG 知识库。她的工作台里装了**多种搜索源**(语雀、通用 Web 搜索、内部 wiki),今天她想让 Claude 做一次"最近写的 RAG 笔记的知识关联",**期望只用语雀读操作完成,不要触网,也不要改文档**。

**展示目标**:
1. 证明 tool-gate 在**低风险只读技能**上做到"默认可启用、无需人工确认"
2. 证明即使 Alice 的提示里有"顺便上网查下"/"顺手把标题改一下"之类越界诱导,tool-gate 依然只会放行**当前技能声明过的工具**
3. 证明**新技能的动态可发现性**(`refresh_skills` 插曲)

---

## 1. 需求点

- N1 · `yuque-knowledge-link` 技能 `risk_level: low`,命中 `default_risk_thresholds.low: auto`,无需 reason 即可启用
- N2 · 启用后,`active_tools` 仅含 `yuque_search / yuque_list_docs / yuque_get_doc`;**其它一律拦**
- N3 · Alice 提到"顺便上网查下最新 RAG 综述",模型若尝试 `search_web` → `PreToolUse deny` + 引导性 `additionalContext`
- N4 · Alice 提到"帮我把标题改一下",模型若尝试 `yuque_update_doc` → `PreToolUse deny`(不在该技能 `allowed_tools` 内)
- N5 · 任务完成后,Alice 的同事在共享 skills 目录推送了新技能 `yuque-comment-sync`;Alice 触发 `refresh_skills` → 新技能在 `list_skills` 中可见
- N6 · 所有放行 / 拒绝都在 `governance.db` 审计表留痕,时间戳严格按事件顺序递增

---

## 2. 演示前置与启动

### 2.1 环境变量(两条路径都要导出)

```bash
cd examples/01-knowledge-link/

export GOVERNANCE_DATA_DIR="$PWD/.demo-data"
export GOVERNANCE_SKILLS_DIR="$PWD/skills"
export GOVERNANCE_CONFIG_DIR="$PWD/config"
```

三个 env var 的作用与缺失时的症状见 [`../QUICKSTART.md §1.3`](../QUICKSTART.md#13--三个-governance_-环境变量)。

### 2.2 启动(两条路径,方式 B 首推)

**方式 B · 离线子进程 replay**(零 API key,决策 stdout 可见;通用模板见 [`../QUICKSTART.md §3.1`](../QUICKSTART.md#31--方式-b--子进程-replayoffline--免-api-key))

```bash
# SessionStart:期望 stdout 含 additionalContext 列出 "Yuque Knowledge Link (low)"
echo '{"event":"SessionStart","session_id":"01","cwd":"'"$PWD"'"}' | tg-hook

# PreToolUse on search_web(混杂变量工具,未 enable):期望 permissionDecision:"deny"
echo '{"event":"PreToolUse","session_id":"01","tool_name":"search_web","tool_input":{}}' | tg-hook
```

实测 stdout 与行为记录见 §5.2。方式 B replay **不写审计**,完整审计链走方式 A。

**方式 A · Claude Code CLI**(需 Anthropic API key;完整交互演示)

```bash
claude --plugin-dir ../../ --mcp-config ./.mcp.json
```

启动后按 §3 操作三列表逐行演示。链路概览见 [`../QUICKSTART.md §3.2`](../QUICKSTART.md#32--方式-a--claude-code-cli进阶需-anthropic-api-key--联网)。

---

## 3. 操作步骤

| 时间戳 | 操作者输入 | 模型预期动作 | 系统侧事件 |
|---|---|---|---|
| 2026-04-19T10:32:15+08:00 | `claude --plugin-dir ../../ --mcp-config ./.mcp.json` | — | `SessionStart` hook → 加载 state → `additionalContext` 注入技能目录(1 项:`yuque-knowledge-link`) |
| 2026-04-19T10:32:18+08:00 | "帮我把最近的 RAG 笔记做一下关联,顺便上网查下最新 RAG 综述" | `list_skills()` | `UserPromptSubmit` hook → 重算 `active_tools` = meta-tools only(尚未启用任何业务技能) |
| 2026-04-19T10:32:24+08:00 | — | `read_skill("yuque-knowledge-link")` | MCP `read_skill` 返回 SOP + `allowed_tools: [yuque_search, yuque_list_docs, yuque_get_doc]` + `risk_level: low`;审计写 `skill.read` |
| 2026-04-19T10:32:31+08:00 | — | `enable_skill("yuque-knowledge-link")` | `PolicyEngine.evaluate` → `risk=low → auto` → 创建 `Grant(scope=session, ttl=3600)`;`active_tools` 追加 3 个 yuque 只读工具;审计写 `skill.enable granted_by=auto` |
| 2026-04-19T10:32:37+08:00 | — | `yuque_search(query="RAG", type="doc")` | `PreToolUse` allow → mock 返回 3 条候选文档;`PostToolUse` 写 `tool.call yuque_search` + 更新 `last_used_at` |
| 2026-04-19T10:32:44+08:00 | — | `search_web(query="RAG 综述 2026")`(越界尝试) | `PreToolUse` **deny** → `additionalContext`:"`search_web` 不在当前已授权技能范围内,请先 `read_skill` / `enable_skill`";审计写 `tool.call whitelist_violation search_web` |
| 2026-04-19T10:32:50+08:00 | — | `yuque_list_docs(repo_id="team-rag")` | `PreToolUse` allow → mock 返回该 repo 文档列表;`PostToolUse` 写审计 |
| 2026-04-19T10:32:57+08:00 | — | `yuque_get_doc(doc_id="rag-overview-v2")` × 3(对 Top-3 候选逐篇深读) | 每次 allow + 审计 |
| 2026-04-19T10:33:12+08:00 | — | `run_skill_action("yuque-knowledge-link", op="relate", args={...})` | `skill_executor` 分发 → 返回关联报告(主题簇 + 关系边 + 缺口)+ 审计写 `skill.action relate` |
| 2026-04-19T10:33:20+08:00 | Alice 继续说:"顺手帮我把第一篇的标题改清楚一点" | `yuque_update_doc(...)`(越界尝试) | `PreToolUse` **deny** → `additionalContext`:"`yuque_update_doc` 不在 `yuque-knowledge-link` 的 `allowed_tools` 中;若需编辑,先 `read_skill` → `enable_skill('yuque-doc-edit')`";审计写 `tool.call whitelist_violation yuque_update_doc` |
| 2026-04-19T10:33:27+08:00 | Alice:"那先算了,下次再改" | — | `UserPromptSubmit` hook → 重算 `active_tools`(无变化) |

### 附录 · `refresh_skills` 插曲

| 时间戳 | 操作者输入 | 模型预期动作 | 系统侧事件 |
|---|---|---|---|
| 2026-04-19T10:35:02+08:00 | (后台)Alice 同事 Bob 往共享 skills 目录推送 `yuque-comment-sync/SKILL.md` | — | 演示时等价于 `cp -r ./skills_incoming/yuque-comment-sync ./skills/`(Phase A 下把该技能放在 `skills_incoming/`) |
| 2026-04-19T10:35:10+08:00 | Alice:"Bob 说他刚推了一个评论同步技能,能用了吗?" | `list_skills()` | 尚未 refresh → 目录里仍只有 1 项 |
| 2026-04-19T10:35:15+08:00 | — | `refresh_skills()` | `SkillIndexer.build_index()` 被调用 **恰好一次**(D3 不变量);返回 `{count: 2}`;审计写 `skills.index.refresh count=2` |
| 2026-04-19T10:35:18+08:00 | — | `list_skills()` | 返回 2 项(`yuque-knowledge-link` 已启用 + `yuque-comment-sync` 未启用) |

---

## 4. 系统内部行为说明

- **SessionStart**:`hook_handler.handle_session_start` 加载持久化 state,清理已过期 grant(此时为空),通过 `PromptComposer` 构造 `additionalContext`,把当前 `skills_loaded` 与可见技能目录注入 Claude 上下文。
- **UserPromptSubmit**:**每轮都触发**,核心动作是 `cleanup_expired_grants` + `ToolRewriter.compute_active_tools`(全量重算,而非增量)。本样例中随着 `enable_skill` 发生,`active_tools` 从 "仅 meta 工具" 扩展到 "meta + 3 个 yuque 只读工具"。
- **PreToolUse**:对 `active_tools` 外的工具返回 `{"permissionDecision": "deny", "additionalContext": "..."}`。白名单判定对 MCP 命名空间工具(如 `mcp__mock_yuque__yuque_search`)也生效 —— `ToolRewriter` 在匹配时同时支持 bare name 和 namespaced 两种形式。
- **PostToolUse**:写 `audit(tool.call)` 行,更新对应 skill 的 `last_used_at`(用于 LRU 回收,本样例未触发)。
- **`run_skill_action`**:由 `SkillExecutor` 分发到技能处理器;本样例 mock yuque-knowledge-link 返回假报告,不走真实 LLM 聚类。
- **`refresh_skills`**:`SkillIndexer.build_index()` 会重扫 `GOVERNANCE_SKILLS_DIR`,更新内存中的技能目录;**单次调用只跑一次扫描**(对应 D3 不变量:一次 refresh_skills 调用内 build_index 只执行 1 次)。

---

## 5. 预期输出 / 日志 / 审计

### 5.1 Audit 行形状(按时间戳顺序)

```
created_at                         event                       subject                                     reason/meta
2026-04-19T10:32:15+08:00          session.start               session=demo-01                             additionalContext_bytes=...
2026-04-19T10:32:24+08:00          skill.read                  skill=yuque-knowledge-link                  risk=low
2026-04-19T10:32:31+08:00          skill.enable                skill=yuque-knowledge-link                  granted_by=auto ttl=3600
2026-04-19T10:32:37+08:00          tool.call                   tool=yuque_search                           decision=allow
2026-04-19T10:32:44+08:00          tool.call                   tool=search_web                             decision=deny reason=whitelist_violation
2026-04-19T10:32:50+08:00          tool.call                   tool=yuque_list_docs                        decision=allow
2026-04-19T10:32:57+08:00 (×3)     tool.call                   tool=yuque_get_doc                          decision=allow
2026-04-19T10:33:12+08:00          skill.action                skill=yuque-knowledge-link op=relate        ok=true
2026-04-19T10:33:20+08:00          tool.call                   tool=yuque_update_doc                       decision=deny reason=whitelist_violation
2026-04-19T10:35:15+08:00          skills.index.refresh        count=2                                     single_scan=true
```

### 5.2 关键 stdout 形状(Phase B 回填)

```
// PreToolUse deny 例:
{"permissionDecision":"deny","additionalContext":"tool `search_web` is outside the current active_tools scope.\nIf you need web search, run read_skill → enable_skill for a web-search skill first."}
```

> **实测记录 · `tg-hook` 子进程退化路径(2026-04-21)**:
>
> 方式:`cd examples/01-knowledge-link && GOVERNANCE_DATA_DIR=/tmp/tg-demo-01 GOVERNANCE_SKILLS_DIR=$PWD/skills GOVERNANCE_CONFIG_DIR=$PWD/config`,事件通过 `echo '{"event":"<Name>",...}' | tg-hook` 送入。
>
> - **`SessionStart`** → `{"additionalContext":"[Tool Governance] Skills:\n  - Yuque Knowledge Link (low): 演示用 · Yuque 风格知识关联:…"}`(1 个低风险技能被注入上下文,对齐 §4 "注入技能目录")
> - **`PreToolUse` `search_web`**(混杂变量,未 enable)→ `{"hookSpecificOutput":{"permissionDecision":"deny","permissionDecisionReason":"Tool 'search_web' is not in active_tools. Please use read_skill and enable_skill to authorize the required skill first.","additionalContext":"To use this tool, first discover available skills with list_skills, then read_skill to understand the workflow, then enable_skill to authorize."}}`
> - **`PreToolUse` `yuque_search`**(未 enable)→ 同上形状,仅 `tool_name` 替换
> - **`governance.db.audit_log`** 新增 2 行 `event_type=tool.call / decision=deny / detail={"error_bucket":"whitelist_violation"}`,与 §5.1 形状一致(仅时间戳为实跑实际值)
>
> **差异**:`enable_skill` / `run_skill_action` / `PostToolUse` 与 `refresh_skills` 插曲走 MCP 元工具链(`tg-mcp`),`tg-hook` 单路径无法覆盖;`additionalContext` 当前返回的是 `hook_handler.py` 通用引导文案,与 §5.2 建议的情境化文案有差异 —— 完整 10 行审计序列与针对性文案待 Claude CLI 交付现场补录。

### 5.3 Verify(通用 SQL 见 QUICKSTART §4)

按 [`../QUICKSTART.md §4`](../QUICKSTART.md#4--verify-通用套路) 的 SQL 模板查询 `$GOVERNANCE_DATA_DIR/governance.db`。**方式 A 完整跑完**时,期望看到 §5.1 列出的 10 行审计(`session.start` → `skill.read` → `skill.enable` → `tool.call × N`(allow/deny 交叉)→ `skill.action relate` → `skills.index.refresh`),时间戳严格递增。**只跑方式 B** 时,审计表为空或不存在是预期行为(方式 B 不写审计,见 QUICKSTART §4 注释)。

---

## 6. Mock 工具契约速览

| 工具 | 所在 MCP | 本样例调用? | 契约详表 |
|---|---|---|---|
| `yuque_search` | `mock-yuque` | ● 主业务工具 | [`contracts/yuque_tools_contract.md#yuque_search`](./contracts/yuque_tools_contract.md#yuque_search) |
| `yuque_list_docs` | `mock-yuque` | ● 主业务工具 | [`contracts/yuque_tools_contract.md#yuque_list_docs`](./contracts/yuque_tools_contract.md#yuque_list_docs) |
| `yuque_get_doc` | `mock-yuque` | ● 主业务工具 | [`contracts/yuque_tools_contract.md#yuque_get_doc`](./contracts/yuque_tools_contract.md#yuque_get_doc) |
| `yuque_update_doc` | `mock-yuque` | ○ 仅作为越界 deny 路径的被拦对象 | [`contracts/yuque_tools_contract.md#yuque_update_doc`](./contracts/yuque_tools_contract.md#yuque_update_doc) |
| `yuque_list_comments` | `mock-yuque` | ○ refresh 插曲后可见,本样例主线不调 | [`contracts/yuque_tools_contract.md#yuque_list_comments`](./contracts/yuque_tools_contract.md#yuque_list_comments) |
| `search_web` | `mock-web-search` | ○ **混杂变量工具**,作为越界 deny 路径 | [`contracts/yuque_tools_contract.md#search_web`](./contracts/yuque_tools_contract.md#search_web) |
| `search_doc` | `mock-internal-doc` | ○ **混杂变量工具**,作为越界 deny 路径 | [`contracts/yuque_tools_contract.md#search_doc`](./contracts/yuque_tools_contract.md#search_doc) |

---

## 7. 代码与测试依据

- 主链路对照实现:
  - `src/tool_governance/hook_handler.py` → `handle_session_start` / `handle_user_prompt_submit` / `handle_pre_tool_use` / `handle_post_tool_use`
  - `src/tool_governance/mcp_server.py` → `list_skills` / `read_skill` / `enable_skill` / `run_skill_action` / `refresh_skills`
  - `src/tool_governance/bootstrap.py` → `load_policy` + `GovernanceRuntime` 组装
- 对照 functional tests:
  - `tests/functional/test_functional_happy_path.py` — happy chain(list → read → enable → run_skill_action → PostToolUse)
  - `tests/functional/test_functional_gating.py` — PreToolUse deny + `whitelist_violation` 审计 + MCP 命名空间 deny
  - `tests/functional/test_functional_refresh.py` — `refresh_skills` 可见性 + 单次 `build_index`

---

## 8. Reset 与本 workspace 专属 troubleshooting

### 8.1 Reset(跑第二次前清理 demo 状态)

```bash
cd examples/01-knowledge-link/
rm -rf ./.demo-data
```

只删本 workspace 的 `.demo-data/`(含 `governance.db`);**不要触碰** `skills/`、`mcp/`、`schemas/`、`contracts/`、`config/`、`.mcp.json` —— 它们是演示资产本身。通用安全口径见 [`../QUICKSTART.md §5`](../QUICKSTART.md#5--reset-通用套路)。

### 8.2 本 workspace 专属 troubleshooting

共性症状(pip 错目录、`tg-hook` 返回 `{}`、`GOVERNANCE_*` 未导出、`.mcp.json` 相对路径断裂等)见 [`../QUICKSTART.md §6`](../QUICKSTART.md#6--troubleshooting8-类常见启动失败)。本 workspace 独有症状如下:

| 症状 | 根因 | 验证 | 修复 |
|---|---|---|---|
| §3 附录 `refresh_skills` 调用后,`list_skills` 仍只返回 1 项 | 忘了**手动**把 `skills_incoming/yuque-comment-sync` 拷到 `skills/`;`SkillIndexer` 只扫 `$GOVERNANCE_SKILLS_DIR`,不触 `skills_incoming/` | `ls ./skills/` 是否含 `yuque-comment-sync/SKILL.md` | `cp -r ./skills_incoming/yuque-comment-sync ./skills/`,再调 `refresh_skills()`;两步顺序不能反 |
| 方式 B replay 中 `PreToolUse` on `yuque_search` 没看到针对语雀的引导文案 | `tg-hook` 在 `skills_loaded` 为空时返回通用引导文案,与 §5.2 建议的情境化文案不同(见 §5.2 末尾"差异"说明) | 对比 §5.2 "实测记录"块与上方期望文案块 | 走方式 A 完整流程即可看到情境化文案;或接受通用文案作为 `error_bucket=whitelist_violation` 的合法 stdout |
