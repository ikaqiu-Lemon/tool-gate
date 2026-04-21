## Why

交付演示 change `add-delivery-demo-workspaces`(Phase A/B 核心项已落地)在 `examples/` 下产出了三份 workspace 及其 mock MCP、契约、Schema、`demo_policy.yaml`、`.mcp.json`。但**一名干净背景的 Level 2 beginner**(懂 Python,没用过 Claude Code CLI / MCP / hook / plugin wiring)按现有 README §2 逐行执行时会在**第二步**就翻车:

```
$ cd examples/01-knowledge-link/
$ pip install -e ".[dev]"
ERROR: file:///home/zh/tool-gate/examples/01-knowledge-link does not appear to
       be a Python project: neither 'setup.py' nor 'pyproject.toml' found.
```

这不是文案问题,是**文档结构问题**:README 先让读者 `cd` 进 workspace,再叫读者"在仓库根执行 pip install" —— copy-paste 顺序一错即炸。

除此之外,现有 workspace README 还隐含了大量零知识读者无法独立推断的前提:

1. `claude --plugin-dir ../../ --mcp-config ./.mcp.json` 背后有**六块无形拼图**(plugin manifest、`hooks/hooks.json`→`tg-hook`、4 个 MCP server、3 个 `GOVERNANCE_*` env var、root vs workspace `skills/` 作用域、`tg-hook` / `tg-mcp` 作为 console script 由 `pip install -e .` 注册),当前 README 一字未提
2. "方式 B · 握手冒烟"只教读者启一个静默等 stdin 的 MCP server,没给 `tg-hook` 子进程 replay 的可落地示例(该示例反而孤立在**根** `examples/README.md` §5.1,未下放)
3. §5 列出了预期审计行形状,却从未告诉读者用哪条 SQL / 去哪里看到它 —— 没有 verify 配方
4. 没有 reset 说明;`.demo-data/governance.db` 在第二次跑时承载上一次状态,新手会误判"演示坏了"
5. 03 的 `max_ttl=120s` 等待对现场极不友好,§2.3 口头建议改文件但没给可直接落地替代配置
6. 没有 preflight 自检;首跑失败常见原因(Python 版本、console script 是否在 PATH、`claude` CLI 是否安装、`.mcp.json` 相对路径解析)靠反复试错才能定位
7. 没有集中的排障矩阵,零散 FAQ 分布在**根** README 与三份 workspace README 之间

交付窗口逼近,"任何阅读者都能自助跑通"的交付承诺与当前 README 的隐含门槛脱节。本 change **只修文档与辅助脚本**,不碰治理核心逻辑,不做新功能,不做旧 change 的 10.9 / 10.10 收尾。

## What Changes

- **新增 `examples/QUICKSTART.md`**,作为三份 workspace 共用的**单一概念入口**:概念图、零知识安装、双路径启动、verify/reset 配方、集中排障矩阵
- **重写三份 workspace README 为 thin 骨架**:只保留本 workspace 局部的操作三列表、契约速览、代码依据链接,共性内容一律用"详见 QUICKSTART §X"回指
- **根 `examples/README.md` §2 顶部追加指引**,把 QUICKSTART 与可选 preflight 脚本放在读者最容易看到的位置
- **[可选]新增 `scripts/check-demo-env.sh`** preflight 脚本(Python 版本 / console script / `claude` CLI / `.mcp.json` 合法性 四态自检)
- **[可选]新增 `examples/03-lifecycle-and-risk/config/demo_policy.fast.yaml`**(max_ttl 120→5 的现场加速变体,不替换主 `demo_policy.yaml`)
- **同步 `docs/dev_plan.md`** 末尾 Addendum 小段指向本 change

## 目标用户

**Level 2 beginner**。具体画像:

- 懂 Python 基本工具链(会 `pip`、会 `venv`、知道 `pyproject.toml` 是什么)
- **未用过** Claude Code CLI
- **未用过** MCP,不知道 stdio MCP server 如何握手
- **未读过**本项目 `src/` 任何文件,不理解 plugin / hooks / skills / grants / audit 的内部关系
- 可能没有 Anthropic API key,或首跑时刻意不挂 API key 以避免网络 / 凭证变量

**直接推论**:文档必须假设读者**从未** `tg-hook` / `tg-mcp` 过,且必须**默认提供一条零凭证、零网络、可完全离线**验证的首跑路径。

## 文档组织

```
examples/
├── README.md                    ← 仍是顶层入口,但瘦身到"导航 + 免责 + 矩阵"
├── QUICKSTART.md                ← 新增,本 change 的主产物,~200-300 行
│   ├ §1 三分钟概念(plugin / hooks / MCP / skill / grant / audit + ASCII wiring 图)
│   ├ §2 零知识安装(绝对路径样板,禁 cd 顺序错误)
│   ├ §3 两条首跑路径(方式 B 在前,方式 A 在后)
│   ├ §4 Verify 配方(sqlite3 audit 表查询样本)
│   ├ §5 Reset 配方(rm -rf .demo-data)
│   └ §6 排障矩阵(症状 → 原因 → 验证命令 → 修复动作)
├── 01-knowledge-link/README.md  ← thin 骨架:跳转 QUICKSTART + 本 workspace 局部步骤
├── 02-doc-edit-staged/README.md ← thin 骨架
└── 03-lifecycle-and-risk/README.md ← thin 骨架 + §2 加速说明
```

原则:**共性概念只出现在 QUICKSTART 一处**;workspace README 不得复述 QUICKSTART 内容,只能引用 + 补充本 workspace 特有步骤(例如 01 的 refresh_skills 插曲、02 的 stage 切换、03 的 TTL 等待)。

## 运行路径优先级

**方式 B(离线子进程 replay)= 首推路径**。原因:

- 零凭证、零网络、确定性输出
- 不依赖 Claude Code CLI 是否装了 / 装对版本
- 新手首次接触 tool-gate 的决策信号(`permissionDecision` 的 allow / deny / ask JSON)直接从 stdout 肉眼可见
- 失败时排查面极小(只可能是 Python / PATH / env var 三类)

具体落地是 `echo '{"hook_event_name":"...","session_id":"..."}' | tg-hook` 系列 one-liner。

**方式 A(Claude Code CLI 全交互)= 进阶路径**。QUICKSTART §3 明确标注:"装了 Claude Code CLI 且有 API key 的读者可直接跳到此节;否则先读方式 B 走通再回来。"

workspace README 中的操作三列表属于方式 A 叙事,但每一行都必须能用方式 B 子进程 replay 重现 —— 这是 QUICKSTART §3 的验证口径。

## 可选配套(in scope 但可被 design 降为 stretch)

- **`scripts/check-demo-env.sh`**:preflight 辅助脚本。若 design.md 判断排障矩阵已足够覆盖环境问题,可降级为文档中的手动步骤;但**首选是作为脚本落地**
- **`examples/03-lifecycle-and-risk/config/demo_policy.fast.yaml`**:03 的 TTL 加速变体。若 design.md 判断 inline diff 示例已足够,可降级为 QUICKSTART / 03 README 里的一段 "diff 复制即可" 文案;但**首选是作为文件落地**

两项都以"优先作为独立产物、必要时可降级为文档段"的弹性定位进入 scope,由 design.md 锁定最终形态。

## In Scope

- `examples/QUICKSTART.md` 新增与撰写
- `examples/01-knowledge-link/README.md` / `02-doc-edit-staged/README.md` / `03-lifecycle-and-risk/README.md` 的**重排**(保留原有 §3 操作三列表、§4 系统行为说明、§5.1 审计行形状、§6 契约速览、§7 代码依据的语义,重排前置步骤并引用 QUICKSTART)
- `examples/README.md` 顶部追加 QUICKSTART / preflight 指引;末尾 §5 回指 QUICKSTART 排障矩阵
- [可选]`scripts/check-demo-env.sh` 新增
- [可选]`examples/03-lifecycle-and-risk/config/demo_policy.fast.yaml` 新增
- `docs/dev_plan.md` 末尾 Addendum 追加 1 小段指向本 change

## Out of Scope

- **核心治理逻辑的任何重构**:`src/tool_governance/**` 一字不动
- **任何新功能开发**:不引入新 MCP 元工具、新 hook、新 policy 字段
- **旧 change 的 10.9 / 10.10 收尾**:
  - 10.9(实测 stdout / audit 回填)属每轮交付前的现场 rehearsal,节奏独立
  - 10.10(6 份 SKILL.md SOP 正文)与"新手可跑通"这一目标正交,留给下一轮
- **workspace 下既有"深度"资产不改**:`skills/**/SKILL.md`(骨架保留)、`mcp/*.py`、`schemas/*.json`、`contracts/*.md`、`.mcp.json`、`config/demo_policy.yaml` 主文件
- 不改 `hooks/hooks.json` / `.claude-plugin/plugin.json` / 根 `config/default_policy.yaml`
- 不新增 pytest 用例;本 change 的验收靠"读者按 QUICKSTART 走一遍"而非自动化
- 不改 workspace README §3 操作三列表的时间戳与事件语义(已通过既有矩阵验收)

## Capabilities

### New Capabilities

(无。本 change 不引入新抽象能力面。)

### Modified Capabilities

- `delivery-demo-harness`:追加"beginner-runnability"族需求 —— QUICKSTART 单一概念入口、离线子进程 replay 为首推路径、verify/reset 配方、排障矩阵、(可选)preflight 脚本、(可选)`demo_policy.fast.yaml`、workspace README 瘦身骨架。**不修改**既有 7 类资产最小集、`.mcp.json` 相对路径规则、三工作区主题边界、操作三列表格式、双覆盖矩阵语义 —— 这些 SHALL 保留,本次叠加"零知识可复现"附加 SHALL。

> **归档顺序依赖**:`delivery-demo-harness` 当前仅存在于 `add-delivery-demo-workspaces/specs/` delta 下,未落到 `openspec/specs/`。若旧 change 先归档,本 change 的 delta 直接落在 `openspec/specs/delivery-demo-harness/` 上;若本 change 先 `/opsx:apply`,则归档时需由 design.md 规定的合并策略处理。具体策略由 design 锁定。

## Impact

**新增**
- `examples/QUICKSTART.md`
- [可选]`scripts/check-demo-env.sh`
- [可选]`examples/03-lifecycle-and-risk/config/demo_policy.fast.yaml`

**重写 / 重排(语义不变,骨架瘦身)**
- `examples/01-knowledge-link/README.md`
- `examples/02-doc-edit-staged/README.md`
- `examples/03-lifecycle-and-risk/README.md`
- `examples/README.md`(轻量追加)

**追加**
- `docs/dev_plan.md`(末尾 Addendum 1 小节)

**不变**(显式锁定,防止 scope 蔓延)
- `src/tool_governance/**`
- `tests/**`
- `hooks/**`、`.claude-plugin/**`、根 `config/**`
- `examples/0X-*/skills/**`、`mcp/**`、`schemas/**`、`contracts/**`、`.mcp.json`、`config/demo_policy.yaml` 主文件

## Risks

| 风险 | 触发场景 | 缓解 |
|---|---|---|
| **QUICKSTART 与 workspace README 语义漂移** | 共性内容两处都写,后续只改一处 | design 锁定"共性仅在 QUICKSTART"为 SHALL;specs 中写成可 grep 验证的不变量(例如"workspace README 不得出现 `pip install`") |
| **方式 B 示例过期** | `tg-hook` stdin JSON 协议变化,示例不再可解析 | QUICKSTART §3 每条命令下附"期望 stdout 前缀"做断言;tasks 中留一项"手工跑一遍录 stdout" |
| **preflight 脚本 POSIX 兼容性** | macOS bash 3.x / Windows Git Bash 差异 | `scripts/check-demo-env.sh` 仅用 POSIX 子集 + `python -c` 做实质检查;脚本头部注明测试过的 shell |
| **`demo_policy.fast.yaml` 与主策略双维护** | 策略字段扩展时漏改 fast 变体 | design 规定 fast 变体 = 主文件的 minimal diff,字段尽量继承;tasks 中加一条"fast 变体只包含 TTL 字段"不变量 |
| **readers 看完 QUICKSTART 仍跑不通** | 本 change 未覆盖的新手卡点 | 验收口径明确"请一名组外新同事按 QUICKSTART 走一次,记录所有卡点并回灌 QUICKSTART §6 排障矩阵";留一轮现场测试再归档 |
| **归档顺序与 `add-delivery-demo-workspaces` 冲突** | 两 change delta 对 `delivery-demo-harness` 并发 | design 锁定"本 change 在旧 change 归档之后才 `/opsx:archive`";tasks 最后一步加"确认旧 change 已归档" |

## Compatibility

- **向后兼容性**:完全向后兼容。所有既有 workspace README §3 操作三列表 / §4 / §5.1 / §6 / §7 语义保留,仅前后增加 preflight 与 verify 章节;既有 `demo_policy.yaml` 不动;既有 `.mcp.json` 不动;既有 skill / mock / schema / contract 不动
- **对 `src/` 代码的兼容性**:零侵入。本 change 不读不写任何源码路径
- **对 `add-delivery-demo-workspaces` 的兼容性**:两 change 的 delta 不冲突 —— 旧 change delta 面向 "结构存在性"(7 类资产、相对路径、三主题边界),本 change delta 面向 "可读性 / 可跑性"。两者相加而非相减
- **对外部读者的兼容性**:已经按旧 README 跑通过的老用户可直接忽略本 change;想第二次跑或介绍给同事的老用户可从 QUICKSTART 入手更省事

## Rollback 策略

本 change 的所有产物都是**新增文件 + 文档重排**,不存在不可逆操作。回滚分两档:

**档 1:全量回滚**(推荐,若本 change 归档后发现结构性问题)
- `git revert` 本 change 的实现 commit
- 三份 workspace README 回到旧形态
- `examples/QUICKSTART.md` / `scripts/check-demo-env.sh` / `demo_policy.fast.yaml` 被删除
- `docs/dev_plan.md` Addendum 小节被回退
- **不需要任何数据迁移**(无 DB schema 变更,无运行时状态)

**档 2:部分回滚**(若只是单个可选产物翻车)
- 删除 `scripts/check-demo-env.sh` 或 `demo_policy.fast.yaml` 单文件
- QUICKSTART / workspace README 中相应引用降级为手动步骤段落
- 不影响主线 QUICKSTART 的可用性

**归档后的验证口径**:若归档一周内无读者反馈卡点、或卡点全都被 QUICKSTART §6 覆盖,视为成功;否则按档 2 修补,档 1 回滚仅在结构性问题时动用。
