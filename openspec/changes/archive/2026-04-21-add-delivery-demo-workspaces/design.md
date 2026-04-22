## Context

tool-governance-plugin 已完成 Phase 1–3 核心链路,端到端测试基于 `tests/fixtures/skills/mock_*` 和 `tests/fixtures/mcp/mock_*_stdio.py`,运行在 pytest harness 内。交付评审需要**独立于 pytest** 的真实运行场景:从用户在 Claude CLI 中装载插件、启动会话、输入自然语言开始,到观察到拦截 / 放行 / 审计的可见效果结束。

本设计面向的阅读者:
- **交付评审人**:产品、安全、集成角色,关心"能不能演示"
- **二次开发者**:下游插件作者,关心"我该怎么参考"
- **Phase B 实现者**:按 Phase A 冻结的契约实现 mock MCP 的工程师

约束来源:explore 阶段已确认的 8 项补充要求 + 3 项前置决策(见 proposal "What Changes")。核心技术决策都围绕**降低 Phase B 返工风险**与**保护主代码不被演示压力污染**。

## Goals / Non-Goals

**Goals:**

- 在 `examples/` 下建立**每样例独立 demo workspace**的组织方式,演示时 `cd` 即可启动
- 用**三列表达 + 绝对递增时间轴**让三个关心层次(人 / 模型 / 系统)可以被独立验收
- 用**两张覆盖矩阵**同时证明"抽象能力齐了"(capability)与"关键接口都被打过一次"(功能/接口)
- 用**契约层 + JSON Schema** 把 Phase A 的文档与 Phase B 的 mock 实现**强绑定**,漂移时必须回改契约
- 把 `refresh_skills` 主线从 Example 03 拿走,收敛 03 的"生命周期与风险升级"主题
- 通过 `mock_shell_stdio.py` 的强约束文案防止把"演示工具混杂拦截"误读为"本项目支持 shell 执行"
- 首页固定 Yuque 免责声明,防止语雀域名被误读为项目绑定域

**Non-Goals:**

- 不触碰 `src/tool_governance/`、`tests/functional/`、`skills/` 主目录、根级 `.mcp.json` / `config/default_policy.yaml` / `hooks/hooks.json`
- 不替代既有 `tests/functional/`(它仍是回归守门)
- 不追求 mock 业务真实性(返回硬编码样本即可)
- 不引入真实 Yuque API / Token / 网络调用
- 不做 Phase 4 的 Langfuse / funnel 实打实集成;样例只呈现"这些信号应该出现在何处"
- 不新增主项目运行时依赖(`jsonschema` 只在演示校验脚本 / Phase B 回归里用)

## Decisions

### D1 · `examples/` 顶层结构 + 三个独立 workspace

```
examples/
├── README.md                            # 总入口
├── 01-knowledge-link/
├── 02-doc-edit-staged/
└── 03-lifecycle-and-risk/
```

**为什么独立 workspace 而不是共享 `examples/skills/` + `examples/mcp/`**:
- 共享方案下,演示者必须从仓库根启动 Claude,并通过 `--plugin-dir` / `--mcp-config` 组合拼出三套不同的 CLI,极易出错
- 独立 workspace 允许 `cd examples/0X-*/ && claude --plugin-dir ../../ --mcp-config ./.mcp.json`,路径单点可控
- 每个 workspace 的硬编码样本可以贴合自身故事(e.g. 03 里才出现 `yuque_delete_doc`),避免样本互相污染
- 代价 = 每个 workspace 各自携带一份 `mock_yuque_stdio.py`(共 3 份,每份 <150 行,冗余可控)

**否决的方案**:`examples/shared/skills + shared/mcp + 01-docs/ + 02-docs/ + 03-docs/`。否决理由 = 启动命令复杂、路径变量多样、跨样例污染风险。

### D2 · 单个 workspace 的最小资产清单

```
examples/01-knowledge-link/
├── README.md                            # 样例完整文档(统一模板)
├── skills/                              # 只装本样例用到的技能
│   └── yuque-knowledge-link/SKILL.md
├── mcp/                                 # 只装本样例用到的 mock stdio server
│   ├── mock_yuque_stdio.py
│   ├── mock_web_search_stdio.py         # 混杂变量
│   └── mock_internal_doc_stdio.py       # 混杂变量
├── config/
│   └── demo_policy.yaml
├── .mcp.json                            # 相对路径引用
├── contracts/
│   └── yuque_tools_contract.md
└── schemas/                             # Phase A 额外产出
    ├── yuque_search.schema.json
    ├── yuque_list_docs.schema.json
    └── yuque_get_doc.schema.json
```

```
examples/02-doc-edit-staged/
├── README.md
├── skills/yuque-doc-edit/SKILL.md       # medium, stages: analysis / execution
├── mcp/
│   ├── mock_yuque_stdio.py
│   └── mock_shell_stdio.py              # 混杂变量,用于演示 blocked_tools
├── config/demo_policy.yaml              # require_reason + blocked_tools
├── .mcp.json
├── contracts/
│   ├── yuque_tools_contract.md
│   └── shell_tools_contract.md          # 开头强制声明"混杂变量工具"
└── schemas/
    ├── yuque_get_doc.schema.json
    ├── yuque_update_doc.schema.json
    └── run_command.schema.json
```

```
examples/03-lifecycle-and-risk/
├── README.md
├── skills/
│   ├── yuque-knowledge-link/SKILL.md    # 复刻,用于 TTL 演示
│   ├── yuque-doc-edit/SKILL.md          # 复刻,用于 disable 演示
│   └── yuque-bulk-delete/SKILL.md       # high-risk
├── skills_incoming/                     # 插曲用,refresh 时拷入 skills/
│   └── yuque-comment-sync/SKILL.md
├── mcp/
│   └── mock_yuque_stdio.py              # 03 聚焦生命周期,不再引入混杂 MCP
├── config/demo_policy.yaml              # max_ttl + approval_required + blocked: [yuque_delete_doc]
├── .mcp.json
├── contracts/yuque_tools_contract.md
└── schemas/
    ├── yuque_search.schema.json
    ├── yuque_update_doc.schema.json
    └── yuque_delete_doc.schema.json
```

### D3 · `.mcp.json` 使用相对路径

样本(`01-knowledge-link/.mcp.json`):

```json
{
  "mcpServers": {
    "tool-governance": { "command": "tg-mcp" },
    "mock-yuque":        { "command": "python", "args": ["./mcp/mock_yuque_stdio.py"] },
    "mock-web-search":   { "command": "python", "args": ["./mcp/mock_web_search_stdio.py"] },
    "mock-internal-doc": { "command": "python", "args": ["./mcp/mock_internal_doc_stdio.py"] }
  }
}
```

**为什么相对路径**:
- `${CLAUDE_PLUGIN_ROOT}` 风格变量在 workspace 外启动时解析到错误位置
- 相对路径要求演示者必须 `cd` 到 workspace 根,自动强化"独立 workspace"语义
- Phase B 在 CI 里跑启动冒烟时也只需要 `cd examples/0X-*/` 一步,无额外 env var

**代价**:演示者**必须**进入 workspace 目录;README 在"演示前置"章节硬性标注。

### D4 · 统一文档模板(含三列表)

`examples/0X-*/README.md` 固定段序:

```
# <样例序号与标题>

## 0. 业务背景与展示目标
## 1. 需求点
## 2. 演示前置                     (cd 到 workspace / 启动 CLI / 期望版本)
## 3. 操作步骤                     (三列表 + 递增时间戳)
## 4. 系统内部行为说明
## 5. 预期输出 / 日志 / 审计
## 6. Mock 工具契约速览             (链接到 contracts/, 列出本样例调用的工具)
## 7. 代码与测试依据
```

**§3 三列表硬格式**:

| 时间戳 | 操作者输入 | 模型预期动作 | 系统侧事件 |
|---|---|---|---|
| 2026-04-19T10:32:15+08:00 | `cd examples/01-knowledge-link && claude ...` | — | SessionStart 注入技能目录 |
| 2026-04-19T10:32:18+08:00 | "帮我把 RAG 相关笔记做关联" | `list_skills()` | UserPromptSubmit 重算 active_tools |
| ... | | | |

**为什么三列**:
- 把"**人的意图** / **模型的决策** / **系统的响应**"三个独立验收面拆开;演示出现偏差时可以逐行定位是 SOP 没写清(列 2)还是拦截规则没生效(列 3)
- 两列写法下"模型动作 + 系统事件"粘在一起,评审人无法独立核对
- 产品看列 1、研发看列 2、安全看列 3,一表覆盖三类评审

### D5 · 时间戳策略 —— 绝对递增时间轴

全文档时间戳使用 `YYYY-MM-DDTHH:MM:SS+08:00`,**单个样例内部严格递增且不重复**。典型节拍:

```
2026-04-19T10:32:15+08:00   SessionStart
2026-04-19T10:32:18+08:00   list_skills
2026-04-19T10:32:24+08:00   read_skill
2026-04-19T10:32:31+08:00   enable_skill
...
```

**递增的价值**:
- `governance.db.audit` 表按 `created_at` 排序可直接与文档逐行比对
- 避免"同一时间发生多个事件"造成的因果链不清
- Phase B 实测出现"事件顺序不对"时可以定位到具体两行

### D6 · 两张覆盖矩阵设计

**第一张 · Capability coverage matrix**(对齐 `openspec/specs/` 下 6 个 capability):

| Capability | 01 | 02 | 03 |
|---|:-:|:-:|:-:|
| skill-discovery | ● | ○ | ● refresh 插曲(仍在 01) |
| skill-authorization | ● low/auto | ● medium/reason | ● high/approval |
| skill-execution | ● run_skill_action | ● stages + change_stage | ○ |
| session-lifecycle | ○ | ○ | ● TTL + revoke + disable |
| tool-surface-control | ● allow + deny | ● stage filter + blocked | ● blocked + whitelist 叠加 |
| audit-observability | ● 基础链 | ● stage.change + violation | ● revoke 顺序 + expire |

**第二张 · 功能 / 接口覆盖矩阵**(由用户指定,语义固化不得改):

| 功能 / 接口 | 01 | 02 | 03 |
|---|:-:|:-:|:-:|
| list_skills | ● | ○ | ● |
| read_skill | ● | ● | ○ |
| enable_skill | ● | ● | ● |
| disable_skill | ○ | ○ | ● |
| grant_status | ○ | ● | ● |
| run_skill_action | ● | ● | ○ |
| change_stage | ○ | ● | ○ |
| refresh_skills | ○ | ○ | ● |
| SessionStart | ● | ○ | ● |
| UserPromptSubmit | ● | ● | ● |
| PreToolUse | ● | ● | ● |
| PostToolUse | ● | ● | ● |
| error_bucket | ○ | ● | ● |
| TTL / revoke | ○ | ○ | ● |
| funnel / trace | ○ | ○ | ● |

**两张的分工**:
- Capability 矩阵回答"**面**"—— 抽象能力是否齐了(用于产品评审)
- 功能/接口矩阵回答"**点**"—— 具体元工具 / hook / 诊断信号是否都被触达(用于安全 / 实现评审)

**`refresh_skills` 在两张矩阵里的处理**:
- Capability 矩阵中 01 已标注 "refresh 插曲(仍在 01)"
- 功能/接口矩阵中保留用户给定 `refresh_skills: 03=●`,落地时 **主场景在 01 结尾插曲承担**,03 只在最后一步做一次"确认可见"式触发作为辅助打点

### D7 · 示例 03 主题收紧 —— `refresh_skills` 移出主线

Example 03 的主题**固定**为:TTL → revoke → disable → 高风险 `approval_required` → 审计顺序闭环。

**为什么不让 `refresh_skills` 占主线**:
- `refresh_skills` 的本质是"**动态发现能力**",应归于"发现层";放在 03 会在主叙事里出现"先发现 → 再治理 → 再回来发现"的节拍跳跃
- TTL / revoke / disable / approval 都是"**能力只出不进**"的单向节奏,主线聚焦度更高
- 插曲/辅助步骤 ≠ 主线;文档明确用"§附录:refresh_skills 辅助触发"形式给出,**不进入三列主表**

把主场景搬到 01 结尾("任务完成后,接到同事推送的新技能,触发一次 refresh"),叙事自然衔接"首次发现"主题。

### D8 · 契约层 + JSON Schema 双层

**契约层(markdown)**:`examples/0X-*/contracts/*.md`,每个 mock 工具一个小节:

```
### yuque_search

| 字段         | 值                                                 |
|------------|---------------------------------------------------|
| 所在 MCP    | mock_yuque_stdio                                   |
| 角色         | 主业务工具                                         |
| 输入字段     | query: str, type: "doc"                            |
| 返回字段     | items: List[{id, title, snippet, repo_id}]         |
| 示例返回     | (JSON 代码块,2-3 条硬编码样本)                      |
| 本样例作用   | 一句话:为什么这个样例需要它                         |
| Schema 文件  | [yuque_search.schema.json](../schemas/yuque_search.schema.json) |
```

**Schema 层(JSON Schema)**:`examples/0X-*/schemas/<tool>.schema.json`,每个 mock 工具对应**两份校验**:
- `input` 子 schema:校验 Claude 传入的参数
- `output` 子 schema:校验 mock 返回给 Claude 的负载

**为什么双层**:
- 契约 md 面向**人类评审**,可读,可在 README 里嵌套
- schema.json 面向**机器校验**,Phase B 的 mock 实现启动时做 self-check:用 `jsonschema.validate` 校验自己的硬编码样本符合 output schema,不合规则拒绝启动 —— 彻底杜绝"文档与 mock 实现漂移"
- 两层共享来源:Phase A 写契约 md 时一并敲定字段,Phase B 写 schema.json 时以契约 md 为准,任何偏离必须双向改

**`mock_shell_stdio.py` 的角色强约束**:
- `contracts/shell_tools_contract.md` 文件开头(schema 之前)必须有一段固定文字:
  > 此 MCP server 是**混杂变量工具**,仅为制造真实工具混杂环境以验证 tool-gate 的拦截能力。它**不代表**本项目支持任意 shell 执行,也不是任何主业务能力。
- `mock_shell_stdio.py` 文件头 docstring 重复一次同样文字
- README §6 契约速览里用黄色标注(markdown 引用块)再提示一次

### D9 · `examples/README.md` 顶部固定免责声明

第一段(标题正下方,无任何其它内容之前)**原文固化**:

> 本示例使用 Yuque 风格的 mock 工具仅作为稳定、可控的演示载体;项目本身并不绑定 Yuque 领域。

作用:
- 在评审人翻开 `examples/` 的第一眼消除"这是一个语雀集成插件"的误解
- 为将来把 mock 换成 Notion / 飞书 / 内部 wiki 领域时留下解释锚点
- 与 D8 `mock_shell_stdio.py` 的角色声明并列,两者都是"**降低对演示载体的过度归因**"的同类约束

### D10 · Phase A / Phase B 边界与验收

**Phase A**(本 change 主干工作):
- 产出 `examples/README.md` + 3 个 `README.md` + 6 个 `SKILL.md`(SOP 骨架级)+ 3 份 `demo_policy.yaml` + 3 份 `.mcp.json` + N 份 `contracts/*.md` + N 份 `schemas/*.schema.json`
- 零 Python 代码
- 验收:评审人仅阅读 `examples/` 就能复述每个样例 / 两张矩阵所有非空格子都在文档中有对应落脚点 / 每个 mock 工具契约表完整 / schema.json 文件存在且能通过 `jsonschema --version` 基础语法校验

**Phase B**(后续 change 或本 change 第二阶段):
- 基于契约实现 `mock_*_stdio.py`;mock 启动时用 `jsonschema.validate` 自检硬编码样本
- 每个 workspace 在 Claude CLI 中真实启动一次,把实测 stdout 与审计表行回填到 Phase A 的 "§5 预期输出 / 日志 / 审计" 段
- 偏差必须优先回改契约 + schema,不得悄悄修 mock

**为什么强制分阶段**:
- Phase A 不涉及代码 → 不会同时出现"代码与文档一起漂"的二元耦合失败
- Phase A 冻结 schema → Phase B 的自由度被限制在"实现层",不能反向影响文档
- 每个 workspace 独立 → 任一样例 Phase B 翻车不影响其它两个

### D11 · SOP 深度 —— 骨架级

Phase A 的 6 份 `SKILL.md` 的 YAML frontmatter 必须完整且合法(可被 `SkillIndexer` 扫到);SOP 正文(frontmatter 之下的 markdown)**只写结构骨架**:
- 一级标题 + 二至三个二级标题("触发场景" / "操作流程" / "错误处理")
- 每节 1–3 行占位文字,标注 `<!-- Phase B 前补齐 -->`

**为什么骨架级**:
- Phase A 验收关心"能不能被扫到、能不能通过策略 → 授权 → 阶段"的链路,SOP 正文长度不改变这些验收点
- 完整 SOP(参考 yuque-eco-system 里 "知识关联 Skills" 一节,单份约 1000 字)会把 Phase A 写作量翻倍,且正文内容在 Phase B 实测时大概率要回改(模型按 SOP 走与预期轨迹不符时)
- 骨架级让 Phase A 先跑通流程骨架,Phase B 的"实测 → 回填" 阶段同时把 SOP 细节补齐,避免两次返工

### D12 · 混杂变量 MCP 与拦截路径

三类混杂变量:

| MCP | 出现于 | 拦截路径 | 存在意义 |
|---|---|---|---|
| `mock_web_search_stdio` | 01 | `active_tools` 白名单外 → PreToolUse deny | 证明:即使 Alice 说"顺便上网查" 模型也拿不到 `search_web` |
| `mock_internal_doc_stdio` | 01 | 同上 | 证明:多类搜索源同时存在时,只有 SOP 声明的 `yuque_search` 能用 |
| `mock_shell_stdio` | 02 | `blocked_tools: [run_command]` 全局红线 | 证明:即使某个技能写了 `allowed_tools: [run_command]` 也过不了全局黑名单 |

所有混杂 MCP 的硬编码样本只返回"我假装搜到了 X",不承担业务意义;在契约表 `本样例作用` 栏统一写"混杂变量工具,用于验证拦截"。

## Risks / Trade-offs

- **workspace 路径解析风险** → Phase A 完成后、Phase B 启动前做一次"空壳启动验证"(`.mcp.json` 已存在但 mock 文件先放空 stub),确认 Claude CLI 从 workspace 目录启动时相对路径被正确解析;任何一个 workspace 验证不通过则三个都必须改
- **契约与实现漂移风险** → Phase B 的 mock 启动时必须调 `jsonschema.validate` 自检输出;CI 冒烟任务(后续 change)里加一条"任何 mock 启动失败即失败"
- **文档示例与真实运行不一致** → Phase B 每个样例必须在文档 §5 后追加一小节 "实测差异记录"(若为 0 则写 "无差异"),不允许默认跳过
- **范围膨胀** → 硬上限:Skill 总数 6(01:1、02:1、03:3 + 1 插曲)/ mock MCP 文件 5(01:3、02:2、03:1),任何超出必须新开 change
- **Yuque 误解** → `examples/README.md` 开头免责声明 + 6 份 `SKILL.md` 的 `description` 字段首句要求含"演示用"字样
- **混杂 MCP 被误读为主业务能力** → D8 强约束三重提示(契约开头 + 文件 docstring + README 黄色引用块)
- **refresh_skills 回流 03** → 两张矩阵里都已硬标注"主场景在 01",任何在 03 文档中把 refresh 拉回主表的操作都算偏离本次 change 范围
- **跨 workspace 资产冗余造成维护成本** → 接受冗余;因为 3 份 `mock_yuque_stdio.py` 的差异恰好承载了各样例的故事,强制去重反而制造耦合

## Open Questions

- Phase B 的 mock `jsonschema` 自检脚本放在 `examples/0X-*/` 内(每个样例各自带)还是 `examples/_tooling/`(共享)? 当前倾向各自带,以保持 "cd 即启动" 语义;若出现明显重复再合并。
- 端到端实测阶段是否纳入本 change?当前设计将其划入 Phase B,但 Phase B 是否在本 change 内完成仍依赖用户决策 —— 若 Phase B 留到下一 change,本 change 验收止于 Phase A 完整产出 + schema 语法校验。
