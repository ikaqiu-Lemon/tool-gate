## Why

项目已经完成 Phase 1–3 核心治理链路并积累了 167 项 functional tests(含 45 条端到端用例),但所有验证资产都以 `pytest + mock_` 夹具形式存在,**交付侧**尚无一份"把插件装进 Claude Code、按真实用户流程走一遍、能被第三方直观评审"的样例。评审人今天阅读 `docs/refer/yuque-eco-system.md` 能理解"Skills 负责教模型怎么做,MCP 负责把事做掉"的分层,却没有可直接复现的端到端演示。

交付窗口逼近,需要一份**可展示、可运行、可验收**的样例集,覆盖主流程与所有核心功能,同时防止主代码在演示压力下被临时重构。

## What Changes

- **新增 `examples/` 顶层目录**,作为交付展示样例的唯一入口;其下放置 3 个独立 demo workspace
- **每个 workspace 自带最小运行上下文**(独立的 `skills/`、`mcp/`、`config/`、`.mcp.json`、`contracts/`),演示时 `cd` 进入即可启动,避免全局路径耦合
- **3 个样例的主题边界**(固化,不得自行扩展):
  - `01-knowledge-link`:首次发现、低风险自动授权、只读闭环、混杂工具拦截、`refresh_skills` 插曲
  - `02-doc-edit-staged`:`require_reason`、两阶段 `change_stage`、`blocked_tools` 全局红线
  - `03-lifecycle-and-risk`:TTL 过期回收、主动 `disable`、高风险 `approval_required` 拒绝、审计顺序闭环(`refresh_skills` 不进入主线)
- **示例文档采用统一三列表达**:`操作者输入 / 模型预期动作 / 系统侧事件`,并使用**绝对递增时间轴**(不允许全篇同一时间戳)
- **两张覆盖矩阵**共存:capability coverage(面) + 功能 / 接口覆盖(点,含 8 个元工具、4 类 hook、`error_bucket` / `TTL/revoke` / `funnel/trace` 信号)
- **所有 mock 工具强制附"请求 / 返回契约表"**;Phase A 额外产出 `*.schema.json`(jsonschema),供 Phase B 直接校验 mock 输出
- **Yuque 免责声明**:`examples/README.md` 顶部固定写入"本示例使用 Yuque 风格的 mock 工具仅作为稳定、可控的演示载体;项目本身并不绑定 Yuque 领域"
- **`mock_shell_stdio.py` 角色强约束**:文档与契约必须明确"混杂变量工具,非主业务能力,不代表本项目支持任意 shell 执行"
- **分阶段交付**:Phase A 仅产出文档 + 契约 + `*.schema.json`(SOP 正文骨架级);Phase B 基于契约实现 mock stdio MCP 并做端到端加载验证
- **`.mcp.json` 一律使用相对路径**,解耦全局环境变量依赖
- **范围硬约束**:本次 change 只允许修改 `examples/` 下内容与必要的根级 `README.md` 指向链接,**不允许触碰 `src/tool_governance/` 或既有 `tests/`**

## Capabilities

### New Capabilities
- `delivery-demo-harness`: 面向交付展示的示例工作区体系 —— 独立 workspace 组织、统一三列文档模板、两张覆盖矩阵、mock 契约与 schema 体系、Phase A/B 资产边界

### Modified Capabilities
(无)本次 change 严格附加,不改变任何现有 capability 的需求行为。

## Impact

- **新增代码/文档位置**:`examples/`(全量新增) + 根 `README.md` / `README_CN.md` 文档导航一段指向 `examples/`(仅补链接)
- **无影响**:`src/tool_governance/`、`tests/functional/`、`config/default_policy.yaml`、`skills/`、`hooks/hooks.json`、`.mcp.json`(项目根)——全部保持不动
- **依赖新增**:Phase B 引入 `jsonschema`(仅在演示脚本路径校验 mock 输出),不进入主项目运行时依赖
- **文档同步**:Phase A 完成后,在 `docs/dev_plan.md` 末尾追加一节"交付演示样例"标注来源为本 change,不修改既有条目
- **评审对象**:交付评审人(产品 / 安全 / 集成);二次开发者(接入 tool-gate 的下游插件作者)
