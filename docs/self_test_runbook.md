# Tool-Governance Plugin — 本地自测 Runbook

> 面向项目维护者 / 开发者。基于仓库内现有的 `mock_` Skills、
> `mock_*_stdio` 本地 MCP 夹具，以及 `tests/functional/` 下的功能测试，
> 跑通项目重点流程的本地自测手册。
>
> 相关文档：
> [`tests/functional/README.md`](../tests/functional/README.md) ·
> [`docs/dev_plan.md`](./dev_plan.md) ·
> [`docs/technical_design.md`](./technical_design.md) ·
> [`docs/requirements.md`](./requirements.md)

---

## 1. 目标与范围

**目标**：用仓库内确定性夹具在本地跑通 tool-governance 插件的关键流程，
验证以下三条 lane 上的行为与文档描述一致：

- **In-process lane**：直接调用 `hook_handler.handle_*` /
  `mcp_server.*`，速度快、便于定位问题。
- **Stdio subprocess lane**：通过子进程启动 `tg-hook` / `tg-mcp` /
  `mock_*_stdio`，验证 JSON 协议形状与 env-var 接线。
- **Claude Code plugin smoke lane**：在真实的 Claude Code CLI 里加载
  插件，做最小加载 / 重载 / 校验烟雾测试。

**适用范围**：Linux / macOS / Windows，本地开发机环境。

**不适用**：
- Phase 4 的 Langfuse / funnel metrics / 基准测试。
- 需要真实第三方 MCP Server 的集成场景。
- Live Claude Code 端到端跨会话验证（见 §11）。

---

## 2. 依赖的 mock 清单

### 2.1 Mock Skills (`tests/fixtures/skills/mock_*`)

| 目录 | 风险 | 阶段 | `allowed_ops` | 用途 |
|---|---|---|---|---|
| `mock_readonly` | low | 无 | `search`, `read_file` | Happy path / 自动授权 / 撤销 / parity 测试 |
| `mock_stageful` | medium | `analysis`, `execution` | `analyze`, `edit` | `change_stage` 路径（需 reason） |
| `mock_sensitive` | high | 无 | `run` | 高风险 deny 分支（工具 `mock_dangerous` 永不启用） |
| `mock_ttl` | low | 无 | `ping` | TTL 过期回收路径（用 `ttl=0` 构造） |
| `mock_refreshable` | low | 无 | `noop` | `refresh_skills` 可见性测试（测试中间投放到 tmp 树） |
| `mock_malformed` | — | — | — | 无效 YAML，必须被 `_index_one` 跳过 |
| `mock_oversized` | — | — | — | 文件 >100 KB，必须被 size 检查跳过 |

### 2.2 Mock stdio MCP servers (`tests/fixtures/mcp/mock_*_stdio.py`)

| 脚本 | 暴露工具 | 用途 |
|---|---|---|
| `mock_echo_stdio.py` | `echo(text)` | 基础 stdio 握手 `initialize` → `tools/list`，由 `test_functional_stdio.py::TestMockEchoStdioHandshake` 驱动 |
| `mock_sensitive_stdio.py` | `dangerous(target)` | 高风险 deny 链路握手 + 命名空间 deny 证据；由 `test_functional_smoke_subprocess.py::TestMockSensitiveStdioHandshake` 与 `TestNamespacedMcpDenyInSubprocess` 驱动 |
| `mock_stage_stdio.py` | `mock_read` / `mock_glob` / `mock_edit` / `mock_write` | 对齐 `mock_stageful` 的阶段 allowed_tools；保留为 skeleton，暂无 subprocess 测试驱动 |

### 2.3 Policy fixtures (`tests/fixtures/policies/`)

| 文件 | 语义 | 由哪些测试加载 |
|---|---|---|
| `default.yaml` | `low=auto` / `medium=approval` / `high=approval`；空 `blocked_tools` / 空 `skill_policies` | `test_functional_policy_fixtures.py`、`test_functional_policy_e2e.py`（E1 / E2）、`test_functional_policy_e2e_lifecycle.py`（E8） |
| `restrictive.yaml` | `blocked_tools: [mock_sensitive, mock_ping]`（skill-id + tool-name 两条路径）；`mock_readonly.approval_required=true`；`mock_stageful.require_reason=true` | `test_functional_policy_fixtures.py`、`test_functional_policy_e2e.py`（E3 / E5 / E6）、`test_functional_policy_e2e_lifecycle.py`（E7 / E9，以 inline derivative 调整后使用） |

---

## 3. 依赖的测试清单

`tests/functional/` 下 13 个测试文件、45 个用例；`tests/` 全量 167 个。

| 文件 | 用例数 | 覆盖流程 |
|---|---|---|
| `test_functional_fixture_sanity.py` | 1 | 索引器跳过 malformed/oversized，保留 5 个 mock |
| `test_functional_happy_path.py` | 7 | SessionStart → list → read → enable → UserPromptSubmit → run_skill_action → PostToolUse |
| `test_functional_gating.py` | 4 | PreToolUse deny / meta-tool 放行 / `whitelist_violation` 审计 / `mcp__mock_echo__echo` 命名空间 deny |
| `test_functional_stage.py` | 1 | `change_stage` + `stage.change` 审计 |
| `test_functional_ttl.py` | 2 | `ttl=0` 阻断 `run_skill_action`；UserPromptSubmit 扫描发 `grant.expire` |
| `test_functional_refresh.py` | 2 | `mock_refreshable` 投放后 `refresh_skills` 可见；单次 `build_index` 调用 |
| `test_functional_revoke.py` | 2 | `disable_skill` → 工具下线 + 审计顺序 `grant.revoke` → `skill.disable` |
| `test_functional_entrypoint_parity.py` | 2 | MCP vs LangChain `enable_skill` 一致性 + unknown-scope 强制收敛 |
| `test_functional_stdio.py` | 2 | `mock_echo_stdio` MCP 握手 + `tg-hook` SessionStart subprocess stdout 协议形状 |
| `test_functional_smoke_subprocess.py` | 5 | `tg-mcp` 广告 8 个 meta-tool；`mock_sensitive_stdio` 握手；`tg-hook` 对 UserPromptSubmit / PreToolUse deny / `mcp__mock_sensitive__dangerous` 命名空间 deny 的 stdout 契约 |
| `test_functional_policy_fixtures.py` | 7 | `default.yaml` / `restrictive.yaml` 真实进入 `PolicyEngine`：low 自动 / medium 询问 / high 拒绝 / blocked tool 剥离 / skill-specific override 覆盖 risk 默认 |
| `test_functional_policy_e2e.py` | 7 | E1 低风险全链路；E2 中风险询问；E3 高风险拒绝；E4 blocked_tool 剥离 + PreToolUse deny；E5 skill override；E6 require_reason 双分支 |
| `test_functional_policy_e2e_lifecycle.py` | 3 | E7 真实策略下的 `change_stage`；E8 真实策略下的 TTL 扫描；E9 真实策略下的 `disable_skill` 审计顺序 |

**辅助**：`tests/functional/_support/` 下 5 个 helper 模块（`runtime`、
`events`、`audit`、`skills`、`stdio`）。`runtime.py` 支持
`policy_file=` 参数让测试直接加载 `tests/fixtures/policies/*.yaml`；
`stdio.py::mcp_handshake` 支持 `command=` / `args=` 形式以便 `tg-mcp`
可作为 `python -m tool_governance.mcp_server` 启动。

---

## 4. 环境准备

### Step 1. 确认 Python 版本

```
python3 --version
```

**说明**：本项目 `pyproject.toml` 声明 `requires-python = ">=3.10"`，
推荐 3.11+（与 `docs/requirements.md` 一致）。

**预期结果**：输出 `Python 3.10.x` 或更高。

**失败先检查**：
- 若系统无 3.10+，先用 pyenv / asdf / Conda 安装。
- Windows PowerShell 用 `python --version`。

---

### Step 2. 创建并激活虚拟环境

Linux / macOS：

```
cd /path/to/tool-gate
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell：

```
cd C:\path\to\tool-gate
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**说明**：所有后续命令都在此 venv 内执行。

**预期结果**：终端提示符前出现 `(.venv)` 前缀。

**失败先检查**：
- Windows 若报 "禁止脚本执行"，以管理员运行
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`。
- `python` 命令未找到 → 确认 PATH 中有 Python 安装。

---

### Step 3. 安装项目（含 dev 依赖）

```
pip install -e ".[dev]"
```

**说明**：使用 editable 安装，`src/tool_governance/` 任何改动即时生效；
`[dev]` 额外拉取 `pytest` / `pytest-asyncio` / `ruff` / `mypy` 及类型桩。
同时注册 `tg-hook` / `tg-mcp` 两个 console script（见
`pyproject.toml:[project.scripts]`）。

**预期结果**：
- 末尾输出 `Successfully installed ...`。
- `which tg-hook`（Linux/macOS）或 `Get-Command tg-hook`（PowerShell）
  能定位到 venv 下的脚本。

**失败先检查**：
- 缺编译器导致依赖安装失败 → 单独升级 `pip setuptools wheel` 重试。
- 企业代理下 pip 报 SSL → 设置 `PIP_INDEX_URL` 或 `--trusted-host`。

---

## 5. 最短版冒烟流程

只跑 3 条命令，10 秒内确认核心链路未坏：

```
python -m pytest tests/functional/test_functional_fixture_sanity.py -q
python -m pytest tests/functional/test_functional_happy_path.py -q
python -m pytest tests/functional/test_functional_stdio.py -q
```

**说明**：依次验证（1）夹具被正确索引，（2）in-process 8 步链路走通，
（3）stdio lane（MCP 握手 + tg-hook 子进程协议形状）就绪。

**预期结果**：三个命令都以 `X passed` 结束，无红色失败。

**失败先检查**：
- 命令 1 红 → fixtures 被污染或 `SkillIndexer` 行为回退。
- 命令 2 红 → `hook_handler` / `mcp_server` / `tool_rewriter` 有回归。
- 命令 3 红 → venv 中 `tg-hook` 未注册，或 `mcp` SDK 未安装。

---

## 6. 完整自测流程（Linux / macOS）

所有命令默认在仓库根目录、已激活 venv 的状态下执行。

### Step 1. Fixture sanity 自测

```
python -m pytest tests/functional/test_functional_fixture_sanity.py -q
```

**说明**：验证 `SkillIndexer.build_index()` 扫描
`tests/fixtures/skills/` 后返回 5 个有效 `mock_*`，并跳过
`mock_malformed` / `mock_oversized`。

**预期结果**：`1 passed`。

**失败先检查**：
- 断言 "missing valid fixture: mock_xxx" → 对应目录 / `SKILL.md` 被删或改名。
- "mock_malformed in ids" → YAML 被意外修复，重新引入语法错误。
- "mock_oversized in ids" → 文件被截断到 <100 KB。

---

### Step 2. Happy path（8 步链路）自测

```
python -m pytest tests/functional/test_functional_happy_path.py -q
```

**说明**：从 SessionStart 索引到 PostToolUse 回写的完整链路，使用
`mock_readonly`。

**预期结果**：`7 passed`，覆盖 list / read / enable / context refresh /
run_skill_action / last_used_at stamping。

**失败先检查**：
- `additionalContext` 不含 "Mock Readonly" → `PromptComposer` 或
  SessionStart 流程变更。
- `run_skill_action` 返回 error → `skill_executor.dispatch` 未被
  monkeypatch 或 `mock_readonly` 的 `allowed_ops` 被改。

---

### Step 3. Gating / deny 自测

```
python -m pytest tests/functional/test_functional_gating.py -q
```

**说明**：验证 PreToolUse 对未授权工具返 `deny` + 指引文本；meta-tool
走 fast-path；`mcp__mock_echo__echo` 命名空间工具也被拦截。

**预期结果**：`4 passed`。

**失败先检查**：
- meta-tool 返回 deny → `_META_SHORT_NAMES` frozenset 被破坏。
- `whitelist_violation` 审计 bucket 缺失 → `handle_pre_tool_use` 的
  `detail` 字段被改。

---

### Step 4. change_stage 自测

```
python -m pytest tests/functional/test_functional_stage.py -q
```

**说明**：启用 `mock_stageful`（medium，需 `reason`），默认 `analysis`
阶段暴露 `mock_read` / `mock_glob`；`change_stage("execution")` 后换为
`mock_edit` / `mock_write`，并落 `stage.change` 审计。

**预期结果**：`1 passed`。

**失败先检查**：
- enable 返 `granted: false` → policy 的 medium=reason 被改成 denied。
- active_tools 未更新 → `ToolRewriter.recompute_active_tools` 或
  `get_stage_tools` 回归。

---

### Step 5. TTL expiry 自测

```
python -m pytest tests/functional/test_functional_ttl.py -q
```

**说明**：以 `ttl=0` 构造已过期 grant，验证
`run_skill_action` 立即失败、UserPromptSubmit 扫描后从 `skills_loaded`
移除，且只发 `grant.expire` 不发 `grant.revoke`。

**预期结果**：`2 passed`。

**失败先检查**：
- "Grant ... has expired" 不出现 → `is_grant_valid` / `create_grant`
  对 `ttl=0` 的语义变了。
- `grant.revoke` 出现 → `cleanup_expired` 误走了 `revoke_grant()`。

---

### Step 6. refresh_skills 自测

```
python -m pytest tests/functional/test_functional_refresh.py -q
```

**说明**：先拷贝 `mock_readonly` 到 tmp 树，验证 `list_skills` 不含
`mock_refreshable`；拷入后调 `refresh_skills`，断言可见 + `build_index`
恰调用一次（D3 不变式）。

**预期结果**：`2 passed`。

**失败先检查**：
- skill_count ≠ 2 → 索引器扫到了拷贝目录外的内容。
- `build_index` 被调用次数 ≠ 1 → `mcp_server.refresh_skills` 或
  `SkillIndexer.current_index` 发生回退。

---

### Step 7. revoke / disable 自测

```
python -m pytest tests/functional/test_functional_revoke.py -q
```

**说明**：启用 `mock_readonly` → `disable_skill` →
验证 `active_tools` 剔除、审计顺序
`grant.revoke` → `skill.disable`、`reason="explicit"`。

**预期结果**：`2 passed`。

**失败先检查**：
- 审计顺序反了 → `disable_skill` 入口在 `revoke_grant` 之前写了
  `skill.disable`。
- `reason` 不是 `"explicit"` → `revoke_grant` 默认值被改。

---

### Step 8. MCP ↔ LangChain parity 自测

```
python -m pytest tests/functional/test_functional_entrypoint_parity.py -q
```

**说明**：同参数下两个入口应产出等价 Grant（scope / granted_by /
allowed_ops 一致）；unknown scope 在两条路径上都收敛为 `"session"`。

**预期结果**：`2 passed`。

**失败先检查**：
- LangChain path 抛 `pydantic.ValidationError` → `enable_skill_tool`
  的 scope 收敛逻辑缺失。
- `granted_by` 不一致 → 两边对 `decision.decision` 的映射不同步。

---

### Step 9. 本地 stdio mock MCP smoke / handshake 自测

```
python -m pytest tests/functional/test_functional_stdio.py tests/functional/test_functional_smoke_subprocess.py -q
```

**说明**：两组 subprocess smoke，互补覆盖。
- `test_functional_stdio.py`（2 用例）
  - `TestMockEchoStdioHandshake`：用官方 `mcp.client.stdio` 启动
    `mock_echo_stdio.py` 子进程，完成 `initialize` + `tools/list`。
  - `TestHookSubprocessStdoutContract`：以 subprocess 启动
    `python -m tool_governance.hook_handler`，喂 SessionStart 事件，
    验证 stdout 是单一 JSON 对象且含 `additionalContext`。
- `test_functional_smoke_subprocess.py`（5 用例）
  - `TestTgMcpSubprocessMetaTools`：启动
    `python -m tool_governance.mcp_server`，断言 `tools/list` 等于
    8 个 meta-tool 的集合。
  - `TestMockSensitiveStdioHandshake`：启动 `mock_sensitive_stdio.py`，
    断言广告 `dangerous`。
  - `TestTgHookSubprocessUserPromptSubmit`：UserPromptSubmit 事件 →
    stdout 单 JSON 含 `additionalContext`。
  - `TestTgHookSubprocessPreToolUseDeny`：未知 tool 的 PreToolUse →
    `permissionDecision=="deny"` + `permissionDecisionReason` 存在。
  - `TestNamespacedMcpDenyInSubprocess`：以
    `mcp__mock_sensitive__dangerous` 命名驱动 PreToolUse，deny 且
    `additionalContext` 包含 `enable_skill` 引导。

**预期结果**：`7 passed`（2 + 5）。

**失败先检查**：
- 导入 `mcp.client.stdio` 失败 → `mcp` 版本过低，升级到 >=1.2。
- 子进程挂起 → 查看 `stderr_bytes`（helper `run_hook_event` 会把非零
  退出的 stderr 抛出到错误信息中）。
- `additionalContext` 为空 → `PromptComposer.compose_skill_catalog` 对空
  fixtures 返回不同文本。

---

### Step 10. Policy-sensitive in-process + mock E2E 自测

```
python -m pytest tests/functional/test_functional_policy_fixtures.py tests/functional/test_functional_policy_e2e.py tests/functional/test_functional_policy_e2e_lifecycle.py -q
```

**说明**：三组都通过 `runtime_context(tmp_path, policy_file=...)` 从
`tests/fixtures/policies/*.yaml` 真实加载策略（经
`bootstrap.load_policy` → `PolicyEngine`），**未 patch
`PolicyEngine.evaluate`**。
- `test_functional_policy_fixtures.py`（7 用例）：Stage F 基础断言，
  两份 YAML 的 low-auto / medium-ask / high-deny / blocked-tool-strip /
  skill-override 分支都返回不同决策字符串。
- `test_functional_policy_e2e.py`（7 用例）：Stage H 核心 E1–E6。
  E1 是低风险全链路（SessionStart → list → read → enable → 全链）。
- `test_functional_policy_e2e_lifecycle.py`（3 用例）：Stage H E7–E9，
  证明 `change_stage` / TTL 扫描 / `disable_skill` 在真实策略下仍
  保持原本的审计顺序与副作用。

**预期结果**：`17 passed`（7 + 7 + 3）。

**失败先检查**：
- 决策字符串不匹配 → 确认 `tests/fixtures/policies/restrictive.yaml`
  未被手改；policy_engine.py 的决策集合为
  `{auto, reason_required, approval_required, denied}`。
- E7 / E9 失败 → 检查测试内 `_policy_variant` 对
  `mock_stageful.auto_grant` / `skill_policies` 的覆盖是否与
  `src/tool_governance/core/policy_engine.py` 的分支精确对齐。

---

### Step 11. functional tests 全量运行

```
python -m pytest tests/functional/ -q
```

**预期结果**：`45 passed`（耗时 ~3.5s）。

**失败先检查**：哪个 Step 单独跑会红，先回到对应步骤定位。

---

### Step 12. pytest 全量运行

```
python -m pytest -q
```

**预期结果**：`167 passed`（functional 45 + 既有 unit/integration 122）。

**失败先检查**：
- `tests/test_integration.py` 报错 → 回归位于
  `hook_handler` / `mcp_server` 核心路径。
- 仅 functional 失败 → 夹具或 `_support/` 被污染，回到 Step 1 重试。

---

### Step 13.（可选）Ruff + mypy

```
ruff check src tests
mypy src
```

**说明**：dev 依赖自带。`ruff` 做代码风格，`mypy` 做静态类型。

**预期结果**：`All checks passed!` / `no issues found`。若有第三方包
无类型存根，`mypy` 的 "Cannot find implementation" 可忽略或加
`# type: ignore[...]`。

**失败先检查**：
- ruff 报错 → 按提示修正或用 `ruff check --fix` 自动修。
- mypy 对 `langchain_core` / `mcp` 报缺存根 → 确认
  `pyproject.toml` 里相应 `ignore_missing_imports` 配置仍在。

---

## 7. 完整自测流程（Windows PowerShell）

与 §6 基本一致，以下只列差异：

### 7.1 命令差异速查

| §6 中的命令 | PowerShell 等价 |
|---|---|
| `python3 --version` | `python --version` |
| `python3 -m venv .venv` | `python -m venv .venv` |
| `source .venv/bin/activate` | `.\.venv\Scripts\Activate.ps1` |
| `which tg-hook` | `Get-Command tg-hook` |
| `python -m pytest ...` | `python -m pytest ...`（无差异） |

### 7.2 PowerShell 专属注意

- 若 `Activate.ps1` 被 ExecutionPolicy 拦截，用
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` 放开当前用户。
- 子进程测试（Step 9）通过 `sys.executable` 显式启动 Python，
  与 shell 无关，所以 PowerShell 上直接跑 `pytest` 即可。
- 路径分隔符：仓库内测试全部用 `pathlib.Path`，PowerShell 下
  `tests/fixtures/...` 与 `tests\fixtures\...` 均可传给 pytest。

### 7.3 完整一次性执行清单（PowerShell）

```
cd C:\path\to\tool-gate
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m pytest tests/functional/ -q
python -m pytest -q
```

---

## 8. Claude Code 插件 smoke 自测

> 目标：在真实 Claude Code CLI 里把本插件加载起来，确认 `plugin.json` /
> `.mcp.json` / `hooks/hooks.json` 三件套互相能对上，**不做**任何跨会话
> 或 Langfuse 验证。

> 前置：已安装官方 Claude Code CLI（`claude` 命令可用），且仓库已执行
> 过 `pip install -e .` 使 `tg-mcp` / `tg-hook` 在 PATH 中。

### Step 1. 以仓库为插件目录启动 Claude Code

```
cd /path/to/tool-gate
claude --plugin-dir .
```

**说明**：把仓库根目录当作一个本地插件目录直接加载，
`.claude-plugin/plugin.json` 被 Claude Code 识别。

**预期结果**：Claude Code 启动后日志里出现
`tool-governance-plugin v0.1.0 loaded`（措辞随 CLI 版本而异）。

**失败先检查**：
- 报错 "plugin.json not found" → 确认当前目录有
  `.claude-plugin/plugin.json`。
- `tg-mcp` / `tg-hook` not found → venv 未激活或未 `pip install -e .`。

### Step 2. 在 Claude 会话中校验插件清单

在 Claude Code 交互界面依次输入：

```
/help
/plugin validate
/agents
```

**说明**：
- `/help` 确认当前会话能响应 slash commands。
- `/plugin validate` 让 Claude Code 对已加载插件做 schema 校验。
- `/agents` 列出可见 agent（本插件无 agent，应显示 0 或默认集合）。

**预期结果**：`/plugin validate` 返回 validation passed，对
`tool-governance-plugin` 无 error。

**失败先检查**：
- validate 报 "missing field" → `.claude-plugin/plugin.json` 字段不全。
- hooks 字段报错 → `hooks/hooks.json` 与 CLI 版本不兼容（参考
  `docs/technical_design.md` §4.3 的 hook 配置样例）。

### Step 3. 重载插件

```
/reload-plugins
```

**说明**：验证热重载路径不崩溃。

**预期结果**：重新加载信息输出，无异常堆栈。

**失败先检查**：
- 崩溃提示 "MCP server crashed" → 独立跑 `tg-mcp` 看 stderr；或
  在仓库内 `python -m tool_governance.mcp_server` 手动复现。

### Step 4. 触发一次 meta-tool 调用

在 Claude 会话里让模型调用 `list_skills`（最简单：直接问
"call list_skills and show me the output"）。

**预期结果**：返回一个包含 `tool-governance` 插件自带 `governance` skill
的列表。**注意**：此处的 skill 目录是
`skills/governance/`，不是 `tests/fixtures/skills/mock_*`；测试夹具只服务
pytest，不参与 Claude Code 运行时。

**失败先检查**：
- 列表为空 → `GOVERNANCE_SKILLS_DIR` 环境变量未正确解析
  `${CLAUDE_PLUGIN_ROOT}/skills`，查看 `.mcp.json`。
- MCP 连不上 → 查看 Claude Code 日志中的 stdio 通讯错误。

---

## 9. 失败排查

按症状索引：

| 症状 | 优先排查 |
|---|---|
| pytest collection error, "No module named tool_governance" | venv 未激活，或未 `pip install -e .` |
| `tg-hook: command not found` | 同上，或 PATH 未刷新（macOS 重开一个 shell） |
| `test_functional_stdio` 子进程挂起 | 检查 stderr；在终端手动 `python -m tool_governance.hook_handler` 后粘贴事件 JSON |
| `grant.revoke` 与 `grant.expire` 同时出现 | `cleanup_expired` 与 `revoke_grant` 调用路径被交叉，看 `grant_manager.py` |
| SessionStart 返回空 `additionalContext` | SkillIndexer 指向了空目录；查看 `GOVERNANCE_SKILLS_DIR` |
| `active_tools` 里多出意外工具 | `ToolRewriter` 合并逻辑变更；临时打印 `state.skills_loaded` 诊断 |
| `mock_oversized` 被意外索引 | 文件被缩到 <100 KB，重新生成（见 `tests/fixtures/skills/mock_oversized/SKILL.md` 末尾 padding） |
| `mock_malformed` 被意外索引 | YAML 被改成了合法语法；重新破坏它（未闭合字符串或非法列表项） |
| pytest 慢到 >10s | 把 `-x -k <name>` 逐个跑，定位慢用例；一般是子进程 timeout 堆积 |

---

## 10. 建议的执行顺序

**日常最短反馈**：§5 最短版冒烟（3 条命令）。

**改了核心治理逻辑**：
1. §4 环境检查 → §5 冒烟 → §6 Step 11（functional 全量）。

**改了 `skill_indexer` 或 `tool_rewriter`**：
1. §6 Step 1（sanity） → Step 2（happy） → Step 4（stage） → Step 6
   （refresh） → Step 11 / 12。

**改了 hook 入口或 MCP 协议形状**：
1. §6 Step 9（stdio smoke lane，2+5 用例） → Step 12（全量）。

**改了 `policy_engine` 或 `tests/fixtures/policies/*.yaml`**：
1. §6 Step 10（policy fixtures + mock E2E，17 用例） → Step 12（全量）。

**准备发 PR / 合并前**：
1. §6 Step 12（pytest 全量）
2. §6 Step 13（ruff + mypy）
3. §8（Claude Code plugin smoke，可选）

---

## 11. 本轮不覆盖的 backlog

以下项目**不在**本 runbook 目标内，需要时请看对应文档或未来 change：

- `mock_stage_stdio` 深度 round-trip（subprocess `tools/call` 对
  `mock_stageful` 的阶段工具进行真实 invocation）—— 当前仅作为
  skeleton 存在，协议形状已由 `mock_echo_stdio` /
  `mock_sensitive_stdio` 代理证明。
- Live Claude Code 跨会话验证（A12 Langfuse 链路、A13 `/plugin install`
  安装流程）—— 属 Phase 4 范围，见 `docs/dev_plan.md` §3 Phase 4。
- Phase 4 本身：Langfuse 集成、funnel metrics 观测、miscall 分桶、
  性能基准。
- 插件安装分发机制（marketplace / `claude plugin add`）。

如需新增 mock 类型或扩展测试范围，应走 OpenSpec change 流程
（`openspec/changes/`），不要直接修改本 runbook 的目标边界。
