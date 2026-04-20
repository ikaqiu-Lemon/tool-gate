## 1. Phase A — 入口与免责声明

- [x] 1.1 创建 `examples/` 顶层目录(仅目录占位,不放任何文件)
- [x] 1.2 撰写 `examples/README.md`:H1 标题 + 第一段固定写入 Yuque 免责声明原文
- [x] 1.3 `examples/README.md` 追加"演示前置"章节:期望 Python 版本、tool-gate 安装、`cd examples/0X-*/` 启动命令模板
- [x] 1.4 `examples/README.md` 追加"三个样例一句话定位"段
- [x] 1.5 `examples/README.md` 追加 capability coverage matrix(6 行 × 3 列)
- [x] 1.6 `examples/README.md` 追加 function/interface coverage matrix(15 行 × 3 列,语义与 design §D6 完全一致)
- [x] 1.7 `examples/README.md` 追加"常见问题"一节:无 Claude CLI 时如何用 `tg-hook` / `tg-mcp` 子进程退化验证

## 2. Phase A — Workspace 01 骨架(knowledge-link)

- [x] 2.1 创建 `examples/01-knowledge-link/` 目录及 7 类子资产空壳(`skills/`、`mcp/`、`config/`、`contracts/`、`schemas/` 目录;`README.md`、`.mcp.json` 文件占位)
- [x] 2.2 撰写 `01-knowledge-link/README.md` §0 业务背景与展示目标(Alice 做 RAG 笔记知识关联)
- [x] 2.3 撰写 §1 需求点(低风险自动授权 + 混杂工具拦截 + refresh 插曲)
- [x] 2.4 撰写 §2 演示前置(`cd examples/01-knowledge-link && claude --plugin-dir ../../ --mcp-config ./.mcp.json`)
- [x] 2.5 撰写 §3 三列操作步骤表(时间戳起点 `2026-04-19T10:32:15+08:00`,严格递增,覆盖 SessionStart → list → read → enable → run_skill_action → PreToolUse allow/deny × N → PostToolUse)
- [x] 2.6 §3 末尾追加"附录:refresh_skills 插曲"小节(同事推新技能 → `refresh_skills` → `list_skills` 可见)
- [x] 2.7 撰写 §4 系统内部行为说明(逐条对应 §3 的"系统侧事件"列做段落展开)
- [x] 2.8 撰写 §5 预期输出 / 日志 / 审计(按时间轴列出 governance.db 审计行形状,标注"Phase B 回填实测 stdout")
- [x] 2.9 撰写 §6 Mock 工具契约速览(表格 + 指向 contracts/ 的链接)
- [x] 2.10 撰写 §7 代码与测试依据(引用 `hook_handler.py` / `mcp_server.py` / 对应 functional tests)

## 3. Phase A — Workspace 01 技能与策略

- [x] 3.1 撰写 `01-knowledge-link/skills/yuque-knowledge-link/SKILL.md` YAML frontmatter(`risk_level: low`、`allowed_tools: [yuque_search, yuque_list_docs, yuque_get_doc]`、`allowed_ops` 含 `relate`)
- [x] 3.2 为 `yuque-knowledge-link/SKILL.md` 写骨架 SOP(H1 + 三个 H2:触发场景 / 操作流程 / 错误处理,每节 `<!-- Phase B 前补齐 -->`)
- [x] 3.3 `skills/yuque-knowledge-link` 首句 `description` 含"演示用"字样
- [x] 3.4 撰写 `01-knowledge-link/config/demo_policy.yaml`(默认 `low=auto` / `medium=approval` / `high=approval`,空 `blocked_tools`,空 `skill_policies`)
- [x] 3.5 撰写 `01-knowledge-link/.mcp.json`(注册 `tool-governance` 用 `tg-mcp` + 3 个 mock MCP 用 `./mcp/mock_*_stdio.py` 相对路径)

## 4. Phase A — Workspace 01 契约与 Schema

- [x] 4.1 撰写 `01-knowledge-link/contracts/yuque_tools_contract.md`(每个工具一段:yuque_search / yuque_list_docs / yuque_get_doc,角色=主业务,以及 search_web / search_doc / yuque_update_doc 作为 deny 路径工具各一段,角色=混杂变量或越界工具)
- [x] 4.2 所有契约段必填:所在 MCP / 角色 / 输入字段 / 返回字段 / 示例返回 JSON(2-3 条样本) / 本样例作用 / Schema 链接
- [x] 4.3 撰写 `01-knowledge-link/schemas/yuque_search.schema.json`(Draft 2020-12,含 `input` + `output` 双子 schema)
- [x] 4.4 撰写 `01-knowledge-link/schemas/yuque_list_docs.schema.json`
- [x] 4.5 撰写 `01-knowledge-link/schemas/yuque_get_doc.schema.json`
- [x] 4.6 撰写 `01-knowledge-link/schemas/yuque_list_comments.schema.json`(refresh 插曲对应工具;文件 description 标注 "Reserved for refresh-episode skill; not called by main flow.")
- [x] 4.7 撰写 `01-knowledge-link/schemas/search_web.schema.json` + `search_doc.schema.json`(混杂变量工具,仍需 schema 以便 Phase B 启动自检);另追加 `yuque_update_doc.schema.json` 覆盖越界 deny 路径
- [x] 4.8 用 `python -m json.tool` / 自建 Python 脚本对所有 `*.schema.json` 做语法合法性检查(16 份 schema 全部通过,含 `$schema` + `input/output` 双子 schema)

## 5. Phase A — Workspace 02 骨架(doc-edit-staged)

- [x] 5.1 创建 `examples/02-doc-edit-staged/` 目录及 7 类子资产空壳
- [x] 5.2 撰写 `02-doc-edit-staged/README.md` §0–§2(业务背景:Alice 确认关联报告后把"相关文档"区块写回;需求点:require_reason + 两阶段 + blocked_tools;演示前置)
- [x] 5.3 撰写 §3 三列操作步骤表(时间戳起点接 01 末尾时间之后,严格递增;覆盖 enable 无 reason 被拒 → 带 reason 再试 → analysis 阶段尝试 update 被拒 → change_stage → execution 写入 → run_command 被 blocked 拦)
- [x] 5.4 撰写 §4 系统内部行为说明(重点:reason_missing 分支、stage 过滤重算 active_tools、blocked_tools 全局红线相对阶段授权的优先级)
- [x] 5.5 撰写 §5 预期输出 / 日志 / 审计(含 `stage.change`、`whitelist_violation yuque_update_doc stage=analysis`、`whitelist_violation run_command reason=blocked` 三条关键审计行形状)
- [x] 5.6 撰写 §6 契约速览 + §7 代码依据(引用 `core/policy_engine.py` 的 require_reason 分支、`tool_rewriter.py` 的 stage 过滤)

## 6. Phase A — Workspace 02 技能 / 策略 / 契约 / Schema

- [x] 6.1 撰写 `02-doc-edit-staged/skills/yuque-doc-edit/SKILL.md` YAML frontmatter(`risk_level: medium`、`stages: [analysis, execution]`,每阶段各自 `allowed_tools`,`allowed_ops: [analyze, write_back]`)
- [x] 6.2 为该 SKILL.md 写骨架 SOP(H1 + 三个 H2,均带 `<!-- Phase B 前补齐 -->`)
- [x] 6.3 撰写 `02-doc-edit-staged/config/demo_policy.yaml`(`skill_policies.yuque-doc-edit.require_reason: true` + `blocked_tools: [run_command]`)
- [x] 6.4 撰写 `02-doc-edit-staged/.mcp.json`(仅 2 个 mock MCP:mock_yuque_stdio + mock_shell_stdio,均相对路径)
- [x] 6.5 撰写 `02-doc-edit-staged/contracts/yuque_tools_contract.md`(yuque_get_doc / yuque_list_docs / yuque_update_doc 三段)
- [x] 6.6 撰写 `02-doc-edit-staged/contracts/shell_tools_contract.md`,**首段固定声明**"混杂变量工具 / 不代表本项目支持任意 shell 执行"原文,再给 run_command 契约段
- [x] 6.7 撰写 `02-doc-edit-staged/schemas/yuque_get_doc.schema.json`、`yuque_list_docs.schema.json`、`yuque_update_doc.schema.json`
- [x] 6.8 撰写 `02-doc-edit-staged/schemas/run_command.schema.json`(混杂变量工具的 schema 仍需完整,含 output 分支以便 Phase B 启动自检)
- [x] 6.9 对所有 `*.schema.json` 做语法校验(通过)

## 7. Phase A — Workspace 03 骨架(lifecycle-and-risk)

- [x] 7.1 创建 `examples/03-lifecycle-and-risk/` 目录及 7 类子资产空壳 + 额外 `skills_incoming/` 目录
- [x] 7.2 撰写 `03-lifecycle-and-risk/README.md` §0–§2(业务背景:长会话,能力清理;需求点:TTL/revoke/disable/高风险 deny/审计闭环;演示前置包含"手动推进时间"的替代脚本提示)
- [x] 7.3 撰写 §3 三列主操作步骤表(时间戳起点接 02 之后,严格递增;覆盖 TTL 过期 → `grant.expire` 扫描 → PreToolUse deny 过期工具 → `disable_skill` → `grant.revoke` → `skill.disable` → 尝试 `enable yuque-bulk-delete` → `approval_required` deny → 尝试调 `yuque_delete_doc` → blocked_tools 拦截)
- [x] 7.4 §3 主表**严禁**出现 `refresh_skills`(自检 9.4 通过);refresh 主场景在样例 01 附录,样例 03 末尾仅做辅助复核打点
- [x] 7.5 撰写 §4 系统内部行为说明(重点:`GrantManager.cleanup_expired`、UserPromptSubmit 扫描、revoke→disable 顺序不变量、两层防线 `approval_required + blocked_tools`)
- [x] 7.6 撰写 §5 预期输出 / 日志 / 审计(审计行序列强制对齐 §3 时间轴)
- [x] 7.7 撰写 §6 契约速览 + §7 代码依据(引用 `grant_manager.py`、`state_manager.py`、`skill_indexer.py`;对齐 `test_functional_ttl.py` / `test_functional_revoke.py` / `test_functional_policy_e2e_lifecycle.py`)

## 8. Phase A — Workspace 03 技能 / 策略 / 契约 / Schema

- [x] 8.1 撰写 `03-lifecycle-and-risk/skills/yuque-knowledge-link/SKILL.md`(复刻 01 的定义,frontmatter 与 01 保持一致)
- [x] 8.2 撰写 `03-lifecycle-and-risk/skills/yuque-doc-edit/SKILL.md`(复刻 02)
- [x] 8.3 撰写 `03-lifecycle-and-risk/skills/yuque-bulk-delete/SKILL.md`(`risk_level: high`、`allowed_tools: [yuque_list_docs, yuque_delete_doc]`、`allowed_ops: [bulk_delete]`、首句 description 含"演示用")
- [x] 8.4 撰写 `03-lifecycle-and-risk/skills_incoming/yuque-comment-sync/SKILL.md`(低风险,供辅助 refresh 步骤用;frontmatter 完整)
- [x] 8.5 撰写 `03-lifecycle-and-risk/config/demo_policy.yaml`(`skill_policies.yuque-knowledge-link.max_ttl: 120` + `skill_policies.yuque-bulk-delete.approval_required: true` + `blocked_tools: [yuque_delete_doc]`)
- [x] 8.6 撰写 `03-lifecycle-and-risk/.mcp.json`(仅 `tool-governance` + `mock-yuque`,相对路径)
- [x] 8.7 撰写 `03-lifecycle-and-risk/contracts/yuque_tools_contract.md`(覆盖 yuque_search / yuque_list_docs / yuque_get_doc / yuque_update_doc / yuque_delete_doc 五段;`yuque_delete_doc` 角色标为"高风险工具")
- [x] 8.8 撰写 `03-lifecycle-and-risk/schemas/yuque_search.schema.json`、`yuque_list_docs.schema.json`、`yuque_get_doc.schema.json`、`yuque_update_doc.schema.json`、`yuque_delete_doc.schema.json`
- [x] 8.9 对所有 `*.schema.json` 做语法校验(通过)

## 9. Phase A — 验收

- [x] 9.1 自检:`examples/` 下无 `*.py` 文件存在(通过,`find examples -name '*.py'` 返回 0 行)
- [x] 9.2 自检:三个 workspace `.mcp.json` 中所有路径均以 `./` 或 `../` 开头,且停留在本 workspace 内(通过)
- [x] 9.3 自检:三份 `README.md` 的 §3 主表时间戳严格递增且跨样例不回退(01 终止于 10:35:18 → 02 起自 11:15:00 → 03 起自 14:00:00;通过)
- [x] 9.4 自检:03 主表内无 `refresh_skills` 字样(仅出现在附录、需求点说明、代码引用段;通过)
- [x] 9.5 自检:两张覆盖矩阵的每个 `●` 格子都能在对应 workspace 的 §3 主表或附录中找到对应步骤(逐格对照通过)
- [x] 9.6 自检:每个 mock 工具在对应 `contracts/*.md` 中有完整 6 字段 + schema 链接(通过)
- [x] 9.7 自检:`mock_shell_stdio.py` 相关的三处(contracts/shell_tools_contract.md 首段 / 02 README §6 引用 / 未来 Python docstring 位置备注)都含混杂变量免责原文(通过;Phase B 补 docstring)
- [x] 9.8 自检:`examples/README.md` 首段为 Yuque 免责声明原文,前面无任何其它内容(通过)
- [x] 9.9 自检:6 份 `SKILL.md` 全部可被 `SkillIndexer` 本地扫描到(通过:01=1、02=1、03=3;skills_incoming 不扫描,属预期)
- [x] 9.10 在根 `README.md` / `README_CN.md` "文档导航"段添加一行 `examples/` 链接(纯追加,不改其它内容;通过)
- [x] 9.11 同步 `docs/dev_plan.md`:在末尾追加"交付演示样例"一节,引用本 change 名;标注 Phase A 完成日期 = 2026-04-19

## 10. Phase B — Mock MCP 实现(可选在本 change 完成,亦可切新 change)

- [x] 10.1 **前置冒烟**:三份 `.mcp.json` 在 mock `.py` 就位后,从 workspace 根 `python ./mcp/*.py` 启动,MCP initialize 握手全绿,相对路径解析正确
- [x] 10.2 实现 `01-knowledge-link/mcp/mock_yuque_stdio.py`(暴露 yuque_search / yuque_list_docs / yuque_get_doc / yuque_update_doc / yuque_list_comments;启动时 `jsonschema.validate` 硬编码输出样本)
- [x] 10.3 实现 `01-knowledge-link/mcp/mock_web_search_stdio.py`(暴露 search_web;文件头 docstring 标注"混杂变量")
- [x] 10.4 实现 `01-knowledge-link/mcp/mock_internal_doc_stdio.py`(暴露 search_doc;同上标注)
- [x] 10.5 实现 `02-doc-edit-staged/mcp/mock_yuque_stdio.py`(硬编码样本面向写回场景,`yuque_get_doc` 含 `version` 字段)
- [x] 10.6 实现 `02-doc-edit-staged/mcp/mock_shell_stdio.py`,**module docstring 首段**原文写入"混杂变量工具 / 不代表本项目支持任意 shell 执行"免责声明
- [x] 10.7 实现 `03-lifecycle-and-risk/mcp/mock_yuque_stdio.py`(新增 yuque_delete_doc 工具,硬编码返回样本仅供 schema 覆盖,实际被 blocked_tools 兜底拦截)
- [x] 10.8 每个 mock 启动自检:加载同目录 `../schemas/<tool>.schema.json`,对所有硬编码输出样本跑 `jsonschema.validate`;任一样本不合规即非零退出(6/6 通过)
- [ ] 10.9 每个 workspace 在 Claude CLI 中端到端跑一次完整演示,把实测 stdout 关键片段 / `governance.db` 审计行回填到 §5 "预期输出" 之后的"实测记录"小节(已完成 MCP `tools/list` 握手冒烟 6/6 通过;真 Claude CLI 交互实测待交付前现场补录)
- [ ] 10.10 补齐 6 份 `SKILL.md` 的 SOP 正文(参考 `docs/refer/yuque-eco-system.md`);**骨架保持到下一轮**,本轮 Phase B 只动 mock + README 运行说明
- [x] 10.11 在 `docs/dev_plan.md` 的"交付演示样例"一节更新 Phase B 完成条目

## 11. 文档同步(本 change 任何阶段 merge 前都要执行一次)

- [x] 11.1 检查 `docs/requirements.md`:本次演示未引出新需求,保持不动
- [x] 11.2 检查 `docs/technical_design.md`:design.md 未引入与现有架构的偏离,保持不动
- [x] 11.3 `docs/dev_plan.md` 末尾"交付演示样例"一节:Phase A 完成条目已追加(2026-04-19);Phase B 条目留待该阶段更新
- [ ] 11.4 本 change 完成后执行 `/opsx:archive add-delivery-demo-workspaces`,把本 change artifacts 归档(待 Phase B 完成)
