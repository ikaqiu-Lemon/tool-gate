# Tool-Gate 演示样例 · 新手快速上手(QUICKSTART)

> 面向**从没用过 Claude Code CLI / MCP / 本项目**的读者。读完这一篇 + 任一 workspace 的 README,可在**不挂 API key、不联网**的前提下跑通一次完整的 tool-gate 演示。

---

## §0 · 这份文档是写给谁的

- 你会用 `pip` / `venv`,读得懂 `pyproject.toml`
- 你**没用过** Claude Code CLI,也不清楚 MCP / hooks / plugin 这几件东西在本项目里各扮演什么
- 你**可能没有** Anthropic API key —— 没关系,本文档推荐的首跑路径**完全离线**

> 免责:本项目用 Yuque 风格的 mock 工具仅作稳定演示载体,**不绑定语雀领域**。`mock_shell_stdio.py` 是"混杂变量工具",非主业务能力。

---

## §1 · 三分钟概念 + wiring 图

### 1.1 六个名词一句话

| 名词 | 一句话 |
|---|---|
| **plugin** | 一个 Claude Code 插件包;本项目的 plugin 清单在 `.claude-plugin/plugin.json`,入口文件是 `hooks/hooks.json` |
| **hooks** | Claude Code 在每次会话开始 / 每轮用户提问 / 每次工具调用前后,都会把事件转发给外部程序决策;本项目的 4 个 hook 全部指向 `tg-hook` 这条 CLI |
| **MCP** | Model Context Protocol;每个 workspace 的 `.mcp.json` 注册若干 stdio MCP server(本项目的 `tool-governance` + 若干 mock) |
| **skill** | 一套"做某件事"的 SOP + 允许调用的工具白名单(`allowed_tools`) + 风险等级;每个 `skills/*/SKILL.md` 一个 |
| **grant** | 技能启用后产生的授权凭据,带 `ttl` / `stage`;treasury 放在 `governance.db` |
| **audit** | 每一次 `skill.read` / `skill.enable` / `tool.call allow|deny` / `grant.expire` / `grant.revoke` 都会落到 `governance.db` 的 `audit` 表 |

### 1.2 `claude --plugin-dir ../../ --mcp-config ./.mcp.json` 背后在做什么

```
   cd examples/0X-*/  &&  claude --plugin-dir ../../  --mcp-config ./.mcp.json
                                         │                       │
                                         │                       └── 注册 4 个 MCP server:
                                         │                            ┌──────────────────┐
                                         │                            │ tool-governance  │ ◀── pip install -e . 注册的
                                         │                            │ mock-yuque       │     console script:tg-mcp
                                         │                            │ mock-web-search  │
                                         │                            │ mock-internal-doc│
                                         │                            └──────────────────┘
                                         │                           (具体谁被注册依 workspace `.mcp.json` 而定)
                                         │
                                         └── 加载 plugin 目录(仓库根):
                                              ┌─────────────────────────────────────┐
                                              │ .claude-plugin/plugin.json          │ ── 标识这是本项目的 plugin
                                              │ hooks/hooks.json                    │ ── 4 个 hook 全部路由到:
                                              │    ├ SessionStart    ─┐             │        ┌────────────┐
                                              │    ├ UserPromptSubmit ─┼─── 每次触发 ─┼──▶──▶ │  tg-hook   │
                                              │    ├ PreToolUse      ─┤             │        └────────────┘
                                              │    └ PostToolUse     ─┘             │         (pip console script)
                                              │ skills/ (根目录)                     │
                                              └─────────────────────────────────────┘

   tg-hook / tg-mcp 如何产生?
     pip install -e ".[dev]"  →  pyproject.toml `[project.scripts]` 注册两条 console script
```

### 1.3 三个 `GOVERNANCE_*` 环境变量

| env var | 作用 | 缺失时的症状 |
|---|---|---|
| `GOVERNANCE_DATA_DIR` | `governance.db`(审计 / 授权状态)落盘目录 | 首跑时在默认位置建库;多 workspace 之间审计串扰 |
| `GOVERNANCE_SKILLS_DIR` | 指向本 workspace 的 `skills/` | 使用**根** `skills/`,演示看不到 workspace 限定的技能 |
| `GOVERNANCE_CONFIG_DIR` | 指向本 workspace 的 `config/`(含 `demo_policy.yaml`) | 使用根 `config/default_policy.yaml`,策略不匹配 demo 预期(TTL / blocked_tools / require_reason 全不对) |

> 三个都是 workspace 限定的软隔离。每份 workspace 的 README §2 都给了 `export GOVERNANCE_*` 的完整模板。

---

## §2 · 零知识安装(唯一权威步骤)

**从仓库根执行**,一次就够:

```bash
# 绝对路径样板 —— 无论你当前 shell 在哪个目录都能跑
cd /home/<you>/path/to/tool-gate   # 替换成仓库实际路径
pip install -e ".[dev]"

# 安装完自检(两条都应有输出)
which tg-hook
which tg-mcp
```

**安装完成后,才能** `cd examples/0X-*/` 进入某个 workspace。

### 2.1 为什么不能在 workspace 目录下执行 `pip install`

仓库根有 `pyproject.toml`,examples 下每个 workspace 目录**没有**。如果你在 workspace 目录执行 `pip install -e ".[dev]"`,会看到这条错误:

```
ERROR: file:///home/<you>/tool-gate/examples/01-knowledge-link
       does not appear to be a Python project:
       neither 'setup.py' nor 'pyproject.toml' found.
```

**修复**:`cd` 回仓库根(`cd ../..`),再执行 `pip install -e ".[dev]"`。

---

## §3 · 两条首跑路径

> **推荐先跑方式 B**:不需要 API key,不需要联网,输出直接肉眼可见。方式 A 是需要 Claude Code CLI + API key 的完整交互演示,作为进阶路径。

### 3.1 方式 B · 子进程 replay(**首推**,离线 / 免 API key)

核心思路:把 Claude Code 在 hook 点会发送的 JSON 事件,用 `echo` 直接灌给 `tg-hook`,观察 stdout 里返回的 `permissionDecision`。

**示例 1 · SessionStart**

```bash
cd /home/<you>/tool-gate/examples/01-knowledge-link   # 替换路径
export GOVERNANCE_DATA_DIR="$PWD/.demo-data"
export GOVERNANCE_SKILLS_DIR="$PWD/skills"
export GOVERNANCE_CONFIG_DIR="$PWD/config"

echo '{"event":"SessionStart","session_id":"qs-demo","cwd":"'"$PWD"'"}' | tg-hook
```

**期望 stdout 形状(实测)**:

```json
{"additionalContext":"[Tool Governance] Skills:\n  - Yuque Knowledge Link (low): 演示用 · Yuque 风格知识关联:..."}
```

关键字段 `additionalContext` 把当前可见技能目录注入 Claude 上下文。

**示例 2 · PreToolUse 被拦(白名单外工具)**

```bash
echo '{"event":"PreToolUse","session_id":"qs-demo","tool_name":"search_web","tool_input":{}}' | tg-hook
```

**期望 stdout 形状(实测)**:

```json
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Tool 'search_web' is not in active_tools. Please use read_skill and enable_skill to authorize the required skill first.","additionalContext":"To use this tool, first discover available skills with list_skills, then read_skill to understand the workflow, then enable_skill to authorize."}}
```

看到 `permissionDecision: "deny"` 即代表 tool-gate 的拦截链路已跑通。**此时你还没有用过 Claude 模型一次**。

> ⚠️ **诚实划界**:`tg-hook` 子进程 replay 产出 **stdout 决策**,但**不会把事件写入** `governance.db` 的审计表(schema 初始化由 `tg-mcp` / Claude CLI harness 驱动,不在 hook 重放路径内)。要看到完整审计链,走方式 A(§3.2)。§4 verify 的 SQL 在只跑方式 B 的环境下会看到空表或仅文件存在,这是预期。
>
> **字段名**:`tg-hook` 读的是 `"event"`,不是 Claude Code harness 默认的 `"hook_event_name"`。如果你把示例命令复制到别处,务必保留 `event` 键;错用 `hook_event_name` 时 `tg-hook` 会返回 `{}` —— 见 §6 T-9。

### 3.2 方式 A · Claude Code CLI(**进阶**,需 Anthropic API key + 联网)

如果你装了 [Claude Code CLI](https://docs.anthropic.com/claude/docs/claude-code) **且**已配置 Anthropic API key:

```bash
cd /home/<you>/tool-gate/examples/01-knowledge-link
export GOVERNANCE_DATA_DIR="$PWD/.demo-data"
export GOVERNANCE_SKILLS_DIR="$PWD/skills"
export GOVERNANCE_CONFIG_DIR="$PWD/config"

claude --plugin-dir ../../ --mcp-config ./.mcp.json
```

具体交互剧本见各 workspace `README.md §3` 的"操作步骤"三列表。方式 A 每一步在系统侧发生的事件都可以用方式 B 的 `tg-hook` replay 独立重现 —— 如果读完 workspace §3 还不确定,回到方式 B 拿单条 JSON 重放即可。

---

## §4 · verify 通用套路

所有 workspace 的 `governance.db` 都在 `$GOVERNANCE_DATA_DIR` 下。通用查询命令:

```bash
sqlite3 "$GOVERNANCE_DATA_DIR/governance.db" \
  "SELECT created_at, event, subject, meta FROM audit ORDER BY created_at;"
```

输出一张按时间递增的表。**具体每个 workspace 期望看到哪几行**,见各自 `README.md §5.1` 的"Audit 行形状"表格;workspace README 的 verify 段会指向本节并列出该 workspace 期望行。

> ⚠️ **verify 的作用域**:本节 SQL 只对**方式 A(§3.2,Claude Code CLI 完整会话)**有效。方式 B 的 `tg-hook` replay **不写审计**(只产出 stdout 决策);在只跑过方式 B 的环境下跑这条 SQL 通常看到空库或空表,这是预期,不是"演示坏了"。

---

## §5 · reset 通用套路

两次连续演示之间,`governance.db` 会残留上一次状态,导致第二次的 verify 与期望行对不上。**清理只需一条命令**,精确作用在**当前 workspace 的** `.demo-data/`:

```bash
cd /home/<you>/tool-gate/examples/0X-*/   # 具体 workspace
rm -rf ./.demo-data
```

> 安全口径:**只删** `.demo-data/`,它只包含本次演示建的 `governance.db`;不要删 workspace 下任何其它目录(`skills/` / `mcp/` / `schemas/` / `contracts/` / `config/` / `.mcp.json` 都是演示资产本身)。

---

## §6 · Troubleshooting(8 类常见启动失败)

| # | 症状 | 根因 | 验证命令 | 修复动作 |
|---|---|---|---|---|
| T-1 | `ERROR: ... does not appear to be a Python project: neither 'setup.py' nor 'pyproject.toml' found` | `pip install` 在 workspace 目录执行,不在仓库根 | `ls ./pyproject.toml`(空输出就是错位了) | `cd` 回仓库根再跑 §2 的 `pip install` |
| T-2 | `tg-hook: command not found` 或 `tg-mcp: command not found` | 没装 / 没激活 venv / 不在 PATH | `which tg-hook` | 在仓库根执行 `pip install -e ".[dev]"`;若用 venv 先 `source venv/bin/activate` |
| T-3 | `claude: command not found` | 没装 Claude Code CLI,或不在 PATH | `claude --version` | 装 Claude Code CLI(见官网)**或**改走方式 B,不强制装 |
| T-4 | 启动 Claude 后看不到 mock MCP 注册,或 `tools/list` 空 | 未从 workspace 根启动;`.mcp.json` 里的 `./mcp/*.py` 相对路径解析到错位置 | `pwd` 是否在 workspace 根 | `cd examples/0X-*/` 后重启动 |
| T-5 | 演示里权限判断与预期不同(例如 `yuque-doc-edit` 无 reason 也通过) | `GOVERNANCE_CONFIG_DIR` / `GOVERNANCE_SKILLS_DIR` 未 export,走了根默认 | `echo "$GOVERNANCE_CONFIG_DIR"` 为空 | 重新 `export GOVERNANCE_*`(见 §1.3 三项) |
| T-6 | `python ./mcp/mock_*_stdio.py` 启动时非零退出,报 `sample for <tool> violates output schema` | 硬编码样本漂移,与 `schemas/*.schema.json` 不一致(正常 Phase B 产出不会出现) | 重新 `git status` 看 `mcp/` 或 `schemas/` 是否被手动改过 | 回滚本地改动;若确需改动,两端同步 |
| T-7 | 03 演示卡在"等 TTL 到期",120s 太久 | 03 的 `max_ttl=120`,实地演示不友好 | 读 `examples/03-*/config/demo_policy.yaml` 看 `max_ttl` | 切 Stage D 提供的 `demo_policy.fast.yaml`(`max_ttl: 5`);见 03 README §2 切换说明 |
| T-8 | 01 附录 `refresh_skills` 插曲后,`list_skills` 仍看不到新技能 | `skills_incoming/` 只是文档约定,必须**手动** `cp -r skills_incoming/yuque-comment-sync skills/`,再调 `refresh_skills()` | `ls examples/01-*/skills/` 是否含 `yuque-comment-sync` | 拷贝目录 → 再调 `refresh_skills`;两步顺序不能反 |
| T-9 | `tg-hook` 对合法事件返回 `{}` 而非 `permissionDecision` | 用了 `hook_event_name` 而不是 `event`。`tg-hook` 源码明确读 `"event"`;Claude Code harness 默认 envelope 是 `"hook_event_name"`,子进程 replay 需要**重命名字段** | 复制 §3.1 示例 1 的命令,把 JSON 中的 `"event"` 改回 `"hook_event_name"` 再重放 —— 应看到 `{}` | 把 JSON 键改回 `"event": "SessionStart"` 等 |

> ⚠️ **对根 `examples/README.md §5.1` 的警示**:该节给出的子进程 replay 示例使用了 `hook_event_name` 字段名,**未经实测**(该节也自述"Phase B 会追加实测 stdout 段"未兑现)。其 stdout 形状承诺不应作为 tool-gate 可观察 deny/allow 的基线。以本 QUICKSTART §3.1 实测形状为准。该问题属于 `add-delivery-demo-workspaces` change 的产物,本 change 范围内不修改根 README §5.1。

---

## §7 · Preflight 自检

仓库根提供一个轻量环境自检脚本:

```bash
bash scripts/check-demo-env.sh
```

输出 `✅ / ⚠️ / ❌` 三态;仅 `❌` 时退出非零。它**只探测**,不自动修复 —— 修复动作请按 §6 对照执行。

> **若该脚本在你的环境下不可用**(例如纯 POSIX sh / 非常老的 bash / Windows Git Bash 未适配),可按以下五步手动自检,效果等价:
>
> 1. `python --version` → ≥ 3.11
> 2. `which tg-hook && which tg-mcp` → 两条都有输出
> 3. `claude --version`(可选;没装就跳过,走方式 B)
> 4. `python -c "import json; json.load(open('examples/01-knowledge-link/.mcp.json'))"` → 无报错
> 5. `python -c "import ast; ast.parse(open('examples/01-knowledge-link/mcp/mock_yuque_stdio.py').read())"` → 无报错

---

## 相关入口

- [`examples/README.md`](./README.md):演示总览 + 两张覆盖矩阵 + 免责声明
- [`examples/01-knowledge-link/`](./01-knowledge-link/):首次发现 + 低风险自动授权 + 混杂工具拦截 + `refresh_skills` 插曲
- [`examples/02-doc-edit-staged/`](./02-doc-edit-staged/):`require_reason` + 两阶段 `change_stage` + `blocked_tools` 全局红线
- [`examples/03-lifecycle-and-risk/`](./03-lifecycle-and-risk/):TTL 过期 + `disable_skill` + 高风险 `approval_required` + 审计闭环
