## Context

`add-delivery-demo-workspaces` change 已产出三份 workspace 的结构性资产(`SKILL.md` 骨架、mock MCP、JSON Schema、契约、`demo_policy.yaml`、`.mcp.json`、`README.md`)。结构完备,但**零知识读者**按 workspace `README.md §2` 逐行执行时会在**第二步**就翻车:

```
$ cd examples/01-knowledge-link/
$ pip install -e ".[dev]"          # ← 在错误目录执行
ERROR: file:///home/zh/tool-gate/examples/01-knowledge-link
       does not appear to be a Python project
```

根因是**文档结构问题**:README §2.1 一句"在仓库根执行"被紧随其后的 `cd examples/0X-*/` 视觉覆盖;copy-paste 顺序一错即炸。进一步地,一条看似简单的启动命令

```
claude --plugin-dir ../../ --mcp-config ./.mcp.json
```

背后有**六块无形拼图**(plugin 清单、`hooks/hooks.json` 路由、4 个 MCP server 注册、3 个 `GOVERNANCE_*` env var、root 与 workspace `skills/` 作用域差、`tg-hook`/`tg-mcp` 作为 console script 由 `pip install -e .` 注册),**当前 workspace README 一字未提**。

本 change 的设计边界:**只修文档与辅助产物,不改任何治理核心**。`src/`、`tests/`、`hooks/`、`.claude-plugin/`、workspace 下既有 `skills/SOP`、`mcp/*.py`、`schemas/*.json`、`contracts/*.md`、`.mcp.json`、`demo_policy.yaml` 主文件全部冻结。本 design 的职责仅是就**五个具体问题**给出可施工决策:

1. 共性 onboarding 内容归哪篇文档
2. workspace README 骨架瘦到什么程度
3. preflight helper 是否存在、落在哪里
4. 03 的 TTL 加速用什么呈现方式
5. verify / reset / troubleshooting 在 QUICKSTART 与 workspace README 之间如何划分

## Goals / Non-Goals

**Goals**

- 让一名 Level 2 beginner(懂 Python、没用过 Claude Code CLI / MCP / plugin wiring)**无需问人**即可按 `examples/QUICKSTART.md` + 任一 workspace README 跑通,且能在**不挂任何 API key、不联网**的前提下观察到至少一次 allow/deny 决策
- 杜绝"workspace cwd 下执行 `pip install`"的路径陷阱,既靠文档语序,也靠 troubleshooting catalog 兜底
- 让 plugin / hooks / MCP / env var 的连接关系在 QUICKSTART 单处被讲清,workspace README 只做引用,不重复
- 保留既有资产的所有语义(`.mcp.json` 相对路径、三 workspace 主题边界、操作三列表时间戳、双覆盖矩阵、契约速览、代码依据)

**Non-Goals**

- 不重构治理核心任何模块
- 不新增元工具 / 新 hook / 新 policy 字段 / 新 skill / 新 mock / 新 schema / 新 contract
- 不收尾 `add-delivery-demo-workspaces` 的 §10.9(实测 stdout 回填)与 §10.10(6 份 SKILL.md SOP 正文)
- 不写新 pytest;本 change 的验收靠"按 QUICKSTART 走一遍"加 workspace README 内嵌的可 grep 不变量
- 不改 workspace README §3 操作三列表的任何一行时间戳或事件语义
- 不做跨平台完美兼容;preflight 脚本只承诺 Linux / macOS 下的 `bash ≥ 3.2` + `python ≥ 3.11`,Windows 留到下一轮

## Decisions

### D1 · 当前 pip install 误导路径 — 用三重冗余消除

**问题**:workspace README §2.1 口头说"在仓库根执行",§2.2 立刻 `cd examples/0X-*/`,顺序一错即炸。

**决策**:三重冗余。

- **结构级**:QUICKSTART 的"安装"章节作为**唯一**写 `pip install -e ".[dev]"` 的地方;workspace README 不得出现独立的 `pip install` 代码块(spec `Installation Origin Anchored at Repository Root` 第 2 个 Scenario 为可 grep 不变量)
- **语序级**:QUICKSTART 安装章节中的 `pip install` 代码块**必须**在该文档内所有 `cd examples/` 之前出现(spec 第 1 个 Scenario 的不变量)
- **排障级**:troubleshooting catalog 必须收录 `does not appear to be a Python project` 这条错误信息的完整原文 + 一行修复动作(spec 第 3 个 Scenario)

**替代方案**:让脚本 `scripts/check-demo-env.sh` 强行检测 `cwd == repo_root` 再允许安装。**否决**,因为 pip 本身不是脚本调用的,读者是在 shell 里手打的,检测脚本无法拦在前面。

### D2 · wiring 对新手不可见 — 用"单一 wiring 图 + 四元素命名"根治

**问题**:`claude --plugin-dir ../../ --mcp-config ./.mcp.json` 背后的六块拼图零文档。

**决策**:

- QUICKSTART 有且只有一节"运行时组成"(spec `Runtime Composition Explained Once, in One Place`),包含**一张 ASCII wiring 图 + 四个元素各一句话定位**:plugin 清单 / hooks 配置 / 各 workspace MCP 注册 / `GOVERNANCE_*` env var
- 图里**不画**内部模块(`HookHandler` / `SkillIndexer` / `GrantManager` 等实现名不出现),只画读者在命令行与文件系统上能看到的面(`--plugin-dir` 指向什么、`--mcp-config` 指向什么、env var 被谁读)
- workspace README 引用该节而非重画,spec 第 2 个 Scenario 保证可 grep 验证
- 读者测试:看完该节能对照 `claude --plugin-dir ../../ --mcp-config ./.mcp.json` 每一部分对上号(spec 第 3 个 Scenario)

### D3 · 文档组织 70/30 — QUICKSTART 承担共性,workspace README 承担本地步骤

**问题**:共性内容(安装、wiring、verify、reset、troubleshooting)在三个 workspace README 里要不要各写一遍?

**决策**:**不要**。70% 共性 → QUICKSTART 单处;30% 本地 → 各 workspace README。

职责切分:

| 内容 | 归属 | 原因 |
|---|---|---|
| 概念图 / 安装 / 启动双路径 / verify 通用形状 / reset 通用形状 / 共性 troubleshooting 矩阵 | `examples/QUICKSTART.md` | 对三份 workspace 相同,重复会漂 |
| 操作三列表(§3)、系统内部行为说明(§4)、审计行形状(§5.1)、契约速览(§6)、代码依据(§7) | 各 workspace README | 本地步骤,语义已稳定 |
| verify 的**期望审计行**、reset 的**具体路径**、workspace 专属 troubleshooting(01 的 refresh / 02 的 stage / 03 的 TTL) | 各 workspace README | 参数化差异 |
| 共性 troubleshooting(pip 错目录、console script 缺失、MCP 路径断裂等) | QUICKSTART | 读者都会碰到,集中维护 |

**替代方案 A**:完全自包含的三份厚 README。**否决**,维护成本 3x,漂移无法遏制。
**替代方案 B**:全部塞到 QUICKSTART。**否决**,读者跑 01 不想读 02/03 的专属步骤。
70/30 是唯一在"可读性"与"可维护性"之间同时够用的切法。

### D4 · 方式 B 作 happy path,方式 A 作进阶 — 不只是排序

**问题**:QUICKSTART §启动 里两条路径谁在前?

**决策**:**方式 B(离线子进程 replay)在前**,原因四条,缺一不可:

1. **零凭证**:不需要 Anthropic API key,新手不必先折腾 `~/.anthropic/` 或环境变量
2. **零网络**:演示可在无外网环境(评审机、气闸内网)复现
3. **确定性输出**:`tg-hook` 吃 JSON 吐 JSON,每条 `permissionDecision` 字节级稳定,读者肉眼就能和 §5.1 审计行对上
4. **失败面极小**:只能在 Python / PATH / env var 三类出问题,troubleshooting 定位快

方式 A(Claude Code CLI 全交互)退到进阶位,QUICKSTART 明确标注"装了 Claude Code CLI 且有 API key 再用"。workspace README §3 操作三列表属于方式 A 叙事,但每一行都可用方式 B 子进程 replay 重现(这是 spec `Credential-Free Happy Path Is the First-Run Default` 的第 2 个 Scenario)。

**副作用**:方式 A 不再是"默认推荐",但**不降级其地位** —— 它仍然是完整交互演示唯一路径,只是现在读者必须先被告知"没有 API key 也能看到决策"。这对评审现场是净增益。

### D5 · preflight helper — 落 `scripts/check-demo-env.sh`,但作为**可降级**产物

**问题**:preflight 是作为脚本还是作为 QUICKSTART 里的手动步骤段落?

**决策**:**首选作为脚本**落 `scripts/check-demo-env.sh`;只做环境探测,不做任何"修复"动作。

职责边界(严格):

- **做**:检查 Python ≥ 3.11、`tg-hook` / `tg-mcp` 是否在 PATH、`claude` 是否在 PATH(缺席降级为 ⚠️ 而非 ❌)、每个 `examples/0X-*/.mcp.json` 是否 JSON 合法且路径不出 workspace、每个 `examples/0X-*/mcp/*.py` 是否语法可解析
- **不做**:自动 `pip install`、自动创建 env var、自动启动 MCP、自动修复 `.mcp.json` —— 一旦自动修复,出问题读者反而更难诊断
- **不做**:Windows 兼容(下一轮)、容器内 shell / busybox sh 兼容
- 输出三态 `✅ / ⚠️ / ❌`,退出码仅在 `❌` 时非零;`⚠️` 不阻断读者

**降级策略(本 change 内)**:若实施时发现脚本维护成本高于收益,可降级为 QUICKSTART §Preflight 里的"手动五步自检"段落,不改 QUICKSTART 其它章节。design 在此显式给该降级入口以免 scope 在 tasks 阶段失控。

### D6 · 03 fast policy — 落独立文件 `demo_policy.fast.yaml`,不改主文件

**问题**:03 的 TTL 加速呈现 — (a)临时编辑 `demo_policy.yaml`;(b)独立 `demo_policy.fast.yaml`;(c)只在 README 里写 diff 段让读者自行粘贴。

**决策**:**(b)独立 `demo_policy.fast.yaml`**,主文件不动。

权衡:

| 方案 | 可复现 | 可教机制 | 维护成本 | 采用? |
|---|---|---|---|---|
| (a)直接改 `demo_policy.yaml` | 高 | 低(读者看不到原始 TTL) | 低(单文件) | ❌ 失去主线演示 |
| (b)独立 `demo_policy.fast.yaml` | 高 | 中(读者要切文件) | 中(双文件,字段同步) | ✅ **采用** |
| (c)README 里贴 diff 让读者粘贴 | 中(易手抖) | 高(读者一行一行看) | 低(纯文档) | ❌ 现场演示太脆 |

**字段同步约束**:`demo_policy.fast.yaml` 必须是主文件的**最小 diff**:仅改 `default_ttl` 与对 `yuque-knowledge-link` 的 `max_ttl`,其余字段(`blocked_tools`、`yuque-bulk-delete.approval_required` 等)**从主文件继承**。tasks 阶段加一条"fast 变体只允许触碰 TTL 相关字段"的 grep 不变量。

**降级策略(本 change 内)**:若 03 README 经评审觉得"两个 policy 文件让读者疑惑",可降级为方案 (c) 纯 diff 段,同时保留独立文件为注释块。回滚成本可控。

### D7 · verify / reset / troubleshooting 的组织 — QUICKSTART 给"做法",workspace README 给"期望"

**verify**:

- QUICKSTART §verify 给**命令形状**(`sqlite3 $GOVERNANCE_DATA_DIR/governance.db "SELECT ..."`)与**比对套路**
- 各 workspace README 的 verify 段**只列本 workspace 期望的审计行**,并用一句 "运行 QUICKSTART §verify 的命令,应看到下列行" 收口
- 这与现有 workspace README §5.1 的"Audit 行形状"表格**直接复用**,不重写

**reset**:

- QUICKSTART §reset 给**单一命令形状**(`rm -rf <workspace>/.demo-data`)与**安全口径**(只删 `.demo-data`,不删任何其它东西)
- 各 workspace README 的 reset 段**只填具体路径**(例如 `rm -rf ./.demo-data`,紧接启动命令下方)
- spec `Per-Workspace Verify and Reset Recipes` 第 3 个 Scenario("reset 后 rerun 结果可复现")由 tasks 阶段一次手动跑通覆盖

**troubleshooting**:

- QUICKSTART §troubleshooting 为**跨 workspace 共性矩阵**(至少 8 类,由 spec 枚举)
- workspace README 的 troubleshooting 段**仅收录本 workspace 专属症状**(01 的 refresh_skills 未生效、02 的 stage 未切换、03 的 TTL 等待)
- 共性症状在 workspace README 出现时,只回指 QUICKSTART,不重写条目

### D8 · 归档顺序 — 本 change 在 `add-delivery-demo-workspaces` 归档之后归档

**问题**:`delivery-demo-harness` 目前仅存在于旧 change 的 delta 里,未进入 `openspec/specs/`。本 change 的 delta 也对 `delivery-demo-harness` 做 ADDED。两者并发写时,归档顺序不决定会有冲突风险。

**决策**:本 change 的归档**必须**排在 `add-delivery-demo-workspaces` 归档之后。tasks.md 最后一步加一条"确认旧 change 已进入 `openspec/changes/archive/`"的前置检查,不满足则本 change 停在 `/opsx:apply` 不进 `/opsx:archive`。

**实施者顺序不受此约束** —— 本 change 的文档实施可以与旧 change 的 `/opsx:archive` 并行,只是**结题归档**这一步排队。

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| QUICKSTART 与 workspace README 语义漂移(共性改一处没跟另一处) | tasks 加"workspace README 不得出现 `pip install`、完整 wiring 图、通用 troubleshooting 条目"的 grep 不变量,CI 不上但归档前人工 grep 过一遍 |
| 方式 B 示例 stdout 过期(`tg-hook` 协议微调后断) | QUICKSTART §启动 每条命令下附 "期望 stdout 开头字段",tasks 要求归档前手工跑一遍并录入期望 |
| preflight 脚本 POSIX 兼容性翻车(macOS bash 3.2 / 不同 coreutils) | 脚本只用 POSIX 子集 + `python -c` 做实质检查;用 `set -u` + `command -v`;不相信 `[[ ... ]]` / `${var,,}` 这类 bash-4 特性 |
| `demo_policy.fast.yaml` 与主文件双维护漂移 | 字段同步不变量(tasks 阶段 grep + diff);未来策略字段扩展时由下一个 change 同步两文件 |
| 读者按 QUICKSTART 走完仍卡住 | 本 change 归档前请一名组外同事走一遍,卡点回灌 QUICKSTART §troubleshooting;放弃追求"首版完美",承认这是迭代文档 |
| 归档顺序与旧 change 并发冲突 | D8 的顺序锁,`/opsx:archive` 前置检查 |

## Migration Plan

文档迁移无数据库 / 接口变更,全部是新增文件 + 重排既有 README。分 5 阶段按顺序施工;每阶段都必须能独立 commit 并通过"人工走一遍 QUICKSTART"自检。

### 阶段 1 · 梳理共性 onboarding 内容(无文件变更)

- 列出三份 workspace README 中**相同或近似**的段落(§2.1 安装、§2.2 启动、§2.3 自检、§2.4 Phase B 状态),形成一份清单
- 标注每段是"拆到 QUICKSTART"还是"留在 workspace 但引用 QUICKSTART"
- 产出:一份临时清单(可以是 tasks.md 里的清单,或临时 `design-notes.md`,不强制落文件)

### 阶段 2 · 设计并撰写 `examples/QUICKSTART.md`(只新增,不改 workspace)

- 按 D1/D2/D4/D5(脚本侧说明)/D6(fast policy 使用说明)/D7 的决策落文:章节 = 概念图 / 零知识安装 / 双路径启动(方式 B 在前)/ verify 套路 / reset 套路 / troubleshooting 矩阵
- 本阶段不触任何 workspace README
- 自检:新建 QUICKSTART 后,自己(或组外一名同事)按它走一遍**方式 B**,能看到至少一次 allow/deny 决策

### 阶段 3 · 迁移三份 workspace README(按 01 → 02 → 03 顺序)

- 每份 README 重排骨架:`§0 一句话定位` → `§1 Preflight(引用 QUICKSTART)` → `§2 启动(双路径简化版,详见 QUICKSTART)` → `§3 操作三列表(原样保留)` → `§4 系统行为(原样保留)` → `§5 审计行形状(原样保留)+ verify 段(新增,指向 QUICKSTART)` → `§6 契约速览(原样保留)` → `§7 代码依据(原样保留)` → `§8 Reset / 本地 troubleshooting(新增)`
- `§2` 的重排**只改前言与跳转**,既有命令和 env var 行不动
- 通用 troubleshooting 条目(pip 错目录、console script 缺失等)从 workspace README 清出,只留专属条目
- 01 完成后在内部 review 一次,02/03 再按相同模板做,减少返工

### 阶段 4 · 补齐可选产物:preflight 脚本 / fast policy 文件

- `scripts/check-demo-env.sh` 按 D5 实施;若实施过程发现维护负担大,按 D5 的降级策略改为 QUICKSTART §Preflight 手动段
- `examples/03-lifecycle-and-risk/config/demo_policy.fast.yaml` 按 D6 的最小 diff 实施;03 README §2 追加一句切换说明 + 一小段 inline diff(教学用途)
- 顺序:先 preflight,再 fast policy;两者独立,互不阻塞

### 阶段 5 · 收口与一致性检查

- 从根 `README.md` / `README_CN.md` 向下巡检,把所有指向 demo 的入口引流到 `examples/README.md` → `examples/QUICKSTART.md`
- `docs/dev_plan.md` 末尾 Addendum 追加一小节指向本 change
- 人工 grep 不变量:
  - `rg -n 'pip install' examples/0X-*/README.md` → **应无命中**(均已下放到 QUICKSTART)
  - `rg -nF 'plugin-dir' examples/0X-*/README.md` 命中行**必须**同时出现"详见 QUICKSTART"引用
  - `rg -nF 'anthropic' examples/QUICKSTART.md` 命中行**必须**属于"方式 A 进阶路径"段
- 请一名组外同事按 QUICKSTART + 01 README 跑一次方式 B,记录卡点;卡点回灌 QUICKSTART §troubleshooting,再重跑一次;两次通过后归档

### Rollback

- **档 1 · 全量回滚**:`git revert` 本 change 的所有 commit。workspace README 回到本 change 前的旧形态;QUICKSTART / preflight / fast policy 文件被删除。**无**数据迁移、**无**运行时状态残留
- **档 2 · 部分回滚**:若只是某个可选产物翻车
  - preflight 脚本翻车 → 删除脚本,QUICKSTART §Preflight 段改用手动步骤叙述
  - fast policy 文件翻车 → 删除文件,03 README §2 改为"按 inline diff 自行编辑 `demo_policy.yaml`"
  - **禁止**把这一档用于 QUICKSTART 主体回退 —— 那不叫部分回滚,叫重开
- 归档后若在一周窗口内读者反馈卡点全都能被 QUICKSTART §troubleshooting 覆盖,视为成功;否则优先走档 2 单点修补,档 1 仅用于结构性问题
