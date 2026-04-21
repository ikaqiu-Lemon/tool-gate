# Stage A · Onboarding Inventory — `harden-demo-workspace-onboarding`

> 临时产物。Stage D §4.14 归档前删除。

## 1. README 分区表(四份文件 × 六类内容)

| 类别 \ 文件 | `examples/README.md` | `examples/01-*/README.md` | `examples/02-*/README.md` | `examples/03-*/README.md` |
|---|---|---|---|---|
| 安装 | §2.1(一句带过) | §2.1(注释"在仓库根执行") | §2.1 同 | §2.1 同 |
| 启动(方式 A) | §2.2 模板 | §2.2 方式 A | §2.2 方式 A | §2.2 方式 A |
| 启动(方式 B / offline) | §5.1 仅根唯一一处 `echo \| tg-hook` 示例 | §2.2 方式 B(挂起,无用) | §2.2 方式 B 同 | §2.2 方式 B 同 |
| wiring 说明 | 无 | 无 | 无 | 无 |
| env var 说明 | 无 | §2.2 `export GOVERNANCE_*` 无释义 | §2.2 同 | §2.2 同 |
| verify | §3/§4 覆盖矩阵(非 SQL) | §5.1 列期望审计行,未给 SQL | §5.1 同 | §5.1 同 |
| reset | 无 | 无 | 无 | 无 |
| troubleshooting | §5 四条 FAQ(未覆盖 8 类) | §2.3 一行自检提示 | 无独立段 | §2.3 TTL 口头建议 |

---

## 2. 当前 onboarding 断点(按类型)

### 2.1 误导型(让新手直接翻车)

| # | 位置 | 断点 | 根因 |
|---|---|---|---|
| M-1 | 01/02/03 §2.1 → §2.2 语序 | `pip install -e ".[dev]"` 代码块紧接 `cd examples/0X-*/`,"在仓库根执行"仅为注释 | README 结构问题,非文案问题 |
| M-2 | 01/02/03 §2.2 方式 B | `python ./mcp/mock_yuque_stdio.py` 启动一个阻塞在 stdin 的 MCP server,新手不知下一步 | 方式 B 示例未下放;真正可用的 `tg-hook` replay 例孤立在根 §5.1 |
| M-3 | 01/02/03 §2.2 | `claude --plugin-dir ../../ --mcp-config ./.mcp.json` 无一字释义 | 六块拼图(plugin / hooks / MCP / env var / `tg-hook` / `tg-mcp`)零文档 |
| M-4 | 01/02/03 §2.2 | `export GOVERNANCE_DATA_DIR / SKILLS_DIR / CONFIG_DIR` 无用途说明,无"缺失时的失败形态" | 同上 wiring 缺口 |
| M-5 | 03 §2.3 | "临时把 `max_ttl: 5`" 口头建议,无可直接落地的替代配置 / diff / 切换方式 | 加速路径未成形 |

### 2.2 概念缺失(零知识读者无法自行推断)

- **C-1** · plugin 是什么(`.claude-plugin/plugin.json` + `hooks/hooks.json` 组成)
- **C-2** · hooks(SessionStart / UserPromptSubmit / PreToolUse / PostToolUse)各负责什么
- **C-3** · MCP 与 `.mcp.json` 注册关系;workspace 下 4 个 MCP(`tool-governance` + 3 个 mock)分别扮演什么角色
- **C-4** · `tg-hook` / `tg-mcp` 是 `pip install -e .` 注册的 console script(见 `pyproject.toml:33-35`),不是"自带命令"
- **C-5** · 根 `skills/` 与 workspace `skills/` 的作用域差(`GOVERNANCE_SKILLS_DIR` 选的是后者)
- **C-6** · `refresh_skills` 插曲的 `skills_incoming/ → skills/` 手动拷贝机制,文档中作"伪"演示

### 2.3 verify / reset / troubleshooting 缺口

- **V-1** · §5.1 列出期望审计行,但无任何 README 教读者如何 `sqlite3 governance.db` 看到它们
- **V-2** · 无统一 SQL 模板(`SELECT created_at, event, subject, meta FROM audit ORDER BY created_at`)
- **R-1** · 无 reset 说明;`.demo-data/governance.db` 在第二次跑时残留第一次状态,读者会误判"坏了"
- **R-2** · 无安全口径(只删 `.demo-data`,不触其它)
- **T-1** · 共性排障矩阵只在根 §5 部分覆盖(4 条 FAQ),spec 要求的 8 类常见启动失败零集中收录
- **T-2** · M-1 的 pip 错目录错误消息原文无任何 catalog 收录
- **T-3** · workspace 专属卡点(01 的 refresh / 02 的 stage / 03 的 TTL)无 troubleshooting 段收纳

---

## 3. QUICKSTART vs workspace README 职责切分(基于 design.md D3 的 70/30 原则)

| 内容 | 归属 | 备注 |
|---|---|---|
| 概念(plugin / hooks / MCP / skill / grant / audit) | QUICKSTART §1 | 一张 ASCII wiring 图,对应 C-1 ~ C-6 |
| 安装(`pip install -e ".[dev]"` 唯一权威代码块) | QUICKSTART §2 | 先出现,再谈 `cd`(闭 M-1) |
| 方式 B happy path(`echo \| tg-hook` 示例) | QUICKSTART §3 | 在前,闭 M-2 |
| 方式 A(`claude --plugin-dir ...`) | QUICKSTART §3 | 在后,显式标"需 API key"(闭 M-3) |
| env var 表(`GOVERNANCE_*` 三项 + 失败形态) | QUICKSTART §1/§2 交叉 | 闭 M-4 |
| verify 通用 SQL 模板 | QUICKSTART §4 | 闭 V-1/V-2 |
| reset 通用命令 + 安全口径 | QUICKSTART §5 | 闭 R-1/R-2 |
| 共性 troubleshooting 8 类 | QUICKSTART §6 | 闭 T-1/T-2 |
| preflight 入口 | QUICKSTART §7 | 指向 `scripts/check-demo-env.sh`(Stage D 决定是否降级) |
| **workspace 一句话定位** | workspace §0 | 保留 |
| **§3 操作三列表(时间戳 + 三列)** | workspace §3 | **原样保留**,不改 |
| **§4 系统内部行为说明** | workspace §4 | 原样保留 |
| **§5.1 期望审计行形状** | workspace §5.1 | 原样保留;verify 段引用 QUICKSTART §4 后给本 workspace 期望行 |
| **§6 契约速览 / §7 代码依据** | workspace §6/§7 | 原样保留 |
| **本 workspace 专属 troubleshooting** | workspace §8(新增) | 01=refresh / 02=stage / 03=TTL |
| **03 fast policy 切换说明** | 03 README §2 + Stage D 产物 | `demo_policy.fast.yaml` 独立文件或降级 diff |

---

## 4. Scenario → Stage 映射(spec 5 条 Requirement × 15 Scenario)

| Scenario | 验收 Stage | 实现任务锚点 |
|---|---|---|
| R1.1 install 先于任何 `cd examples/` | Stage B | 2.2 |
| R1.2 workspace README 无独立 pip 代码块 | Stage C + Stage D | 3.2/3.8/3.14 + 4.7 |
| R1.3 pip-wrong-cwd 错误消息原文收录 | Stage B | 2.7 |
| R2.1 QUICKSTART 含 wiring 图 | Stage B | 2.1 |
| R2.2 workspace README 不复制 wiring 图 | Stage C + Stage D | 3.2/3.8/3.14 + 4.8 |
| R2.3 读者能对照命令指出四元素 | Stage B | 2.1(自检) |
| R3.1 方式 B 先于方式 A | Stage B | 2.3/2.4 |
| R3.2 方式 B 产出可见决策 | Stage B + Stage D | 2.9 + 4.11 |
| R3.3 方式 A 明标"需 API key" | Stage B | 2.4 |
| R4.1 workspace verify 段存在且具体 | Stage C | 3.3/3.9/3.15 |
| R4.2 workspace reset 段存在且安全 | Stage C | 3.4/3.10/3.16 |
| R4.3 reset 后 rerun 可复现 | Stage D | 4.11 |
| R5.1 QUICKSTART 8 类 troubleshooting | Stage B | 2.7 |
| R5.2 每条 entry 含 symptom/cause/verify/fix | Stage B | 2.7 |
| R5.3 workspace README 引用共享 catalog | Stage C + Stage D | 3.5/3.11/3.17 + 4.8 |

**落空核验**:15 条 Scenario 均有至少一个 Stage 任务锚点,无遗漏。

---

## 5. 受影响文件清单(Stage B/C/D 实际改动)

**新增**
- `examples/QUICKSTART.md`(Stage B)
- `scripts/check-demo-env.sh`(Stage D §4.1,可降级)
- `examples/03-lifecycle-and-risk/config/demo_policy.fast.yaml`(Stage D §4.3,可降级)

**重排 / 轻量改**
- `examples/01-knowledge-link/README.md`(Stage C 3.1–3.6)
- `examples/02-doc-edit-staged/README.md`(Stage C 3.7–3.12)
- `examples/03-lifecycle-and-risk/README.md`(Stage C 3.13–3.19)
- `examples/README.md`(Stage C 3.20–3.21,仅 §2 顶部 + §5 末尾)
- `docs/dev_plan.md`(Stage D §4.5,末尾追加 Addendum)

**不改**(显式锁定)
- `src/**`、`tests/**`、`hooks/**`、`.claude-plugin/**`、根 `config/**`
- workspace 下 `skills/**`、`mcp/**`、`schemas/**`、`contracts/**`、`.mcp.json`、`config/demo_policy.yaml` 主文件
- workspace README §3 / §4 / §5.1 / §6 / §7 既有行文

---

## 6. QUICKSTART 建议骨架(供 Stage B 落地)

```
examples/QUICKSTART.md (~200–300 行)

§0  谁该读这份文档(Level 2 beginner)+ 一句免责
§1  三分钟概念
    ├ plugin / hooks / MCP / skill / grant / audit(各一句话)
    ├ ASCII wiring 图:`claude --plugin-dir ../../ --mcp-config ./.mcp.json`
    │   的六块拼图解剖(plugin 清单 / hooks 配置 / MCP 注册 / GOVERNANCE_* env var /
    │   `tg-hook` / `tg-mcp`)
    └ env var 表(三项 + 各自缺失时的症状)
§2  零知识安装(唯一权威 pip install 代码块)
    ├ 从仓库根执行(绝对路径样板)
    ├ 自检:which tg-hook / which tg-mcp
    └ "为什么不能在 workspace 下执行"(附错误原文,对应 M-1 / R1.3)
§3  两条首跑路径
    ├ 方式 B · 子进程 replay(offline / 无 API key / 首推)
    │   ├ SessionStart 示例
    │   ├ PreToolUse deny 示例
    │   └ 每条附"期望 stdout 片段"
    └ 方式 A · Claude Code CLI(需 API key,进阶)
§4  verify 通用 SQL(sqlite3 $GOVERNANCE_DATA_DIR/governance.db ...)
    └ 一句指向各 workspace §5.1 期望审计行
§5  reset 通用命令(rm -rf <workspace>/.demo-data)+ 安全口径
§6  troubleshooting 矩阵(症状 / 根因 / 验证命令 / 修复)
    至少 8 类(对应 spec R5.1 枚举):
    pip 错目录 / console script 缺失 / claude 缺失 / .mcp.json 相对路径断裂 /
    GOVERNANCE_* 未导出 / mock schema drift / TTL 等待(03)/ refresh_skills 未生效
§7  preflight 入口
    └ 指向 scripts/check-demo-env.sh(Stage D 若降级则替为手动五步)
```

备选降级(Stage D §4.2):若 `check-demo-env.sh` 不落地,§7 改为"手动五步自检"段;不影响 §1–§6。
