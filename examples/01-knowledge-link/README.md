# 样例 01 · 知识关联:首次发现与自动授权

> 本样例展示 tool-gate 的**基础主流程**:一个新会话中,Claude 如何被引导从"看到技能目录 → 阅读 SOP → 启用技能 → 使用工具"一步步走过来;在这条链路上,**混杂工具会被真实拦住**。

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

## 2. 演示前置

### 2.1 一次性环境准备

```bash
# 在仓库根执行
pip install -e ".[dev]"     # 安装 tool-gate + FastMCP + jsonschema
```

### 2.2 进入 workspace 启动

```bash
cd examples/01-knowledge-link/

export GOVERNANCE_DATA_DIR="$PWD/.demo-data"
export GOVERNANCE_SKILLS_DIR="$PWD/skills"
export GOVERNANCE_CONFIG_DIR="$PWD/config"

# 方式 A · Claude Code CLI(完整交互演示)
claude --plugin-dir ../../ --mcp-config ./.mcp.json

# 方式 B · 不依赖 Claude CLI 的 mock 握手冒烟
python ./mcp/mock_yuque_stdio.py         # 启动会自检 schema;读 stdin 走 MCP JSON-RPC
```

### 2.3 自检与故障诊断

- 启动 mock 时如果 `[mock_yuque] sample for <tool> violates output schema` 则表示硬编码样本与 `schemas/*.schema.json` 漂移,优先核对契约
- `GOVERNANCE_DATA_DIR` 指向空目录即可,tool-gate 会自动创建 `governance.db`
- 本 workspace 的 mock 全部以**相对路径**方式在 `.mcp.json` 中注册 (`./mcp/*.py`),必须从 workspace 根启动

### 2.4 Phase B 已交付

- ✅ `mcp/mock_yuque_stdio.py`:yuque_search / yuque_list_docs / yuque_get_doc / yuque_update_doc / yuque_list_comments
- ✅ `mcp/mock_web_search_stdio.py`:search_web(混杂变量)
- ✅ `mcp/mock_internal_doc_stdio.py`:search_doc(混杂变量)
- ✅ 启动自检:每个 mock 在 `mcp.run()` 之前用 `jsonschema.validate` 核对所有硬编码样本

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

> **实测记录**(Phase B 填写):<!-- Phase B 填写:实际 stdout 与本节形状差异 -->

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
