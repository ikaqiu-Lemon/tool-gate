# Tasks — harden-demo-workspace-onboarding

严格拆成 4 个 implementation stage(A / B / C / D)+ 归档前文档同步。每个 stage 独立 commit,上下文可在 stage 之间清空重开。

---

## 1. Stage A — 现状盘点与落点确认(只读)

**改哪些文件**
- 仅新增临时产物 `openspec/changes/harden-demo-workspace-onboarding/stageA_inventory.md`(Stage D §4.10 收口时删)

**不改哪些文件**
- `examples/**`、`src/**`、`tests/**`、`docs/**`、`scripts/**`、`hooks/**`、`.claude-plugin/**`、`config/**` 一字不动

**需要执行的命令(只读)**
- `rg -n '^##' examples/README.md examples/0X-*/README.md` 提取章节结构
- `rg -nF 'pip install' examples/` 枚举错误语序出现位置
- `rg -nF 'plugin-dir' examples/` 枚举 wiring 相关散落位置
- `wc -l examples/README.md examples/0X-*/README.md`

**预期产出**
- 一份三列 inventory(来源文件:行号 / 内容摘要 / 归属档 = {QUICKSTART 独有 / workspace 独有 / QUICKSTART 主但 workspace 引用}),覆盖 ≥ 20 条断点段落
- inventory 末尾追加一份 "Scenario → Stage 映射表",显式标注 spec 里 5 条 Requirement × 15 个 Scenario 各由哪个 Stage 验收

**如何避免上下文过大**
- 本 stage 允许读取文件仅限:4 份 README(根 + 三 workspace)、`pyproject.toml`、`.claude-plugin/plugin.json`、`hooks/hooks.json`、三份 `.mcp.json`
- 禁止读 `src/`、`tests/`、`openspec/specs/`、任何 workspace 的 `skills/` / `mcp/` / `schemas/` / `contracts/`
- 输出 inventory 控制在 ~100 行以内,用紧凑三列表格而非长段落

### Tasks

- [x] 1.1 读 `examples/README.md` 并按六类(安装 / 启动 / wiring / verify / reset / troubleshooting)枚举相关段落与行号
- [x] 1.2 读 `examples/01-knowledge-link/README.md`,按相同六类提取段落与行号
- [x] 1.3 读 `examples/02-doc-edit-staged/README.md`,按相同六类提取段落与行号
- [x] 1.4 读 `examples/03-lifecycle-and-risk/README.md`,按相同六类提取段落与行号
- [x] 1.5 对每条段落判定归属档:{QUICKSTART 独有 / workspace 独有 / QUICKSTART 主 workspace 引用}
- [x] 1.6 写 `stageA_inventory.md`:三列表格 + Scenario → Stage 映射表;控制在 100 行以内
- [x] 1.7 对照 `specs/delivery-demo-harness/spec.md` 的 5 条 Requirement × 15 个 Scenario,核验 Stage B/C/D 覆盖完整(无 Scenario 落空)
- [ ] 1.8 Stage A 单独 commit(message: `stage A: onboarding inventory and scenario-to-stage mapping`)

---

## 2. Stage B — 共享 onboarding 骨架(`examples/QUICKSTART.md`)

**改哪些文件**
- 新增 `examples/QUICKSTART.md`(单文件,~200–300 行)

**不改哪些文件**
- 三份 workspace `README.md` 一字不动(等 Stage C)
- 根 `examples/README.md` 不动(等 Stage C §3.20–3.21)
- `scripts/`、`src/`、`tests/`、`docs/`、`hooks/`、`.claude-plugin/`、workspace 下任何 `skills/` / `mcp/` / `schemas/` / `contracts/` / `config/` / `.mcp.json` 不动

**需要执行的命令**
- 写 `examples/QUICKSTART.md` 后:`wc -l examples/QUICKSTART.md`(~200–300 行)
- 自检方式 B happy path:`echo '{"hook_event_name":"SessionStart","session_id":"qs","cwd":"'"$PWD"'"}' | tg-hook` 至少吐一个 `permissionDecision` 或等价决策 JSON
- `python -c "import json, pathlib; print(pathlib.Path('examples/QUICKSTART.md').read_text()[:200])"` 简单读校验

**预期产出**
- `examples/QUICKSTART.md` 含 7 节:§1 概念 + wiring / §2 零知识安装 / §3 双路径启动(方式 B 在前) / §4 verify 套路 / §5 reset 套路 / §6 troubleshooting 矩阵 / §7 preflight 入口
- §3 方式 B 的示例命令作者本人亲自跑过一次,期望 stdout 已写入文档

**如何避免上下文过大**
- 本 stage 允许读取文件仅限:Stage A 的 `stageA_inventory.md`、本 stage 自己写的 `QUICKSTART.md`
- 禁止读 workspace README 细节、`src/`
- QUICKSTART 内不复述 workspace README §3 操作三列表内容

### Tasks

- [x] 2.1 `examples/QUICKSTART.md` §1:三分钟概念(plugin / hooks / MCP / skill / grant / audit 各一句话) + ASCII wiring 图(命名 plugin 清单 / `hooks/hooks.json` / `.mcp.json` 四个 MCP 注册 / 三个 `GOVERNANCE_*` env var)
- [x] 2.2 §2 零知识安装:从仓库根执行 `pip install -e ".[dev]"` 的唯一权威代码块,附绝对路径变体与一句"为什么不能在 workspace 下执行"说明
- [x] 2.3 §3 方式 B(子进程 replay)happy path:2–3 条 `echo ... | tg-hook` / `tg-mcp <<<...` 示例,每条附期望 stdout 片段
- [x] 2.4 §3 方式 A(Claude Code CLI)进阶:`claude --plugin-dir ../../ --mcp-config ./.mcp.json` 的解释性命令 + 显式标注"需 Anthropic API key"
- [x] 2.5 §4 verify 套路:`sqlite3 $GOVERNANCE_DATA_DIR/governance.db "SELECT created_at, event, subject, meta FROM audit ORDER BY created_at;"` 通用形状,末尾一句"具体期望行见各 workspace README verify 段"
- [x] 2.6 §5 reset 套路:`rm -rf <workspace>/.demo-data` 通用形状 + "只删 `.demo-data`,不触碰其它路径"安全口径
- [x] 2.7 §6 troubleshooting 矩阵:按 spec `Single Troubleshooting Catalog` 枚举的 8 类症状,四列(症状 / 根因 / 验证命令 / 修复动作)
- [x] 2.8 §7 preflight 入口:一句指向 `scripts/check-demo-env.sh`(占位,Stage D 决定是否降级)
- [x] 2.9 Stage B 自检:作者本人按 §3 方式 B 手打一次,观察 stdout 含 `permissionDecision`;失败即修 §3
- [x] 2.10 `wc -l examples/QUICKSTART.md` 落在 200–300 行区间(超出则考虑拆 primer 到附录)
- [x] 2.11 Stage B 单独 commit(message: `stage B: add examples/QUICKSTART.md onboarding entry`)

---

## 3. Stage C — 迁移各 workspace README(按 01 → 02 → 03 → root 顺序)

**改哪些文件**
- `examples/01-knowledge-link/README.md`
- `examples/02-doc-edit-staged/README.md`
- `examples/03-lifecycle-and-risk/README.md`
- `examples/README.md`(轻量追加 §2 顶部 + §5 末尾回指)

**不改哪些文件**
- 任一 workspace 下 `skills/**`、`mcp/**`、`schemas/**`、`contracts/**`、`config/demo_policy.yaml`、`.mcp.json` 一字不动
- 任一 workspace README §3 操作三列表的时间戳、事件语义、§4 系统内部行为、§5.1 审计行形状、§6 契约速览、§7 代码依据内容**不动**,只允许重排前后章节与新增引用
- `QUICKSTART.md` 在本 stage 内**不动**
- `src/`、`tests/`、`docs/`、`hooks/`、`.claude-plugin/`、`scripts/` 不动

**需要执行的命令**
- 每改完一个 workspace:`rg -nF 'pip install' examples/0X-*/README.md` 应无命中
- `rg -nF 'plugin-dir' examples/0X-*/README.md` 所有命中附近应出现 "QUICKSTART" 字样
- 每改完一个 workspace 单独 commit

**预期产出**
- 三份 workspace README 骨架统一:`§0 一句话定位` → `§1 Preflight(引 QUICKSTART)` → `§2 启动(双路径简化,指向 QUICKSTART)` → `§3 操作三列表(原样)` → `§4 系统行为(原样)` → `§5 审计行形状(原样)+ verify 段(新增)` → `§6 契约速览(原样)` → `§7 代码依据(原样)` → `§8 Reset + 本地 troubleshooting(新增)`
- 根 `examples/README.md` §2 顶部含 QUICKSTART / preflight 指引;§5 末尾含排障矩阵回指

**如何避免上下文过大**
- **一次只打开一个 workspace**:01 改完 commit 并清除上下文后再做 02,以此类推
- 单次打开文件:当前目标 workspace README + QUICKSTART + Stage A inventory;禁止读其它 workspace README
- 禁止改动 §3 / §4 / §5.1 / §6 / §7 的既有行文 —— 超出范围立即收手

### Tasks

- [x] 3.1 Workspace 01 · 骨架重排:保留 §3/§4/§5.1/§6/§7 原文,前置 `§1 Preflight` 段指向 QUICKSTART,`§2` 改为精简双路径块并指向 QUICKSTART §3
- [x] 3.2 Workspace 01 · 清理 §2.1 / §2.2 / §2.3 / §2.4 中与 QUICKSTART 重复的内容;保留本 workspace 特有的 `GOVERNANCE_*` env var 导出与启动命令
- [x] 3.3 Workspace 01 · 新增 verify 段:列出 §5.1 期望审计行(`skill.read` / `skill.enable auto` / `tool.call allow × N` / `whitelist_violation search_web` / `whitelist_violation yuque_update_doc` / `skills.index.refresh`),引用 QUICKSTART §4 命令形状
- [x] 3.4 Workspace 01 · 新增 reset 段:`rm -rf ./.demo-data` 与安全口径一句
- [x] 3.5 Workspace 01 · 新增本 workspace 专属 troubleshooting 段:`refresh_skills 插曲未生效` / `skills_incoming 拷贝后未重算` 等 01 独有条目;共性症状只回指 QUICKSTART §6
- [x] 3.6 Workspace 01 · 核验 `rg -nF 'pip install' examples/01-knowledge-link/README.md` 无命中;`rg -nF 'plugin-dir' examples/01-knowledge-link/README.md` 命中行附近含 "QUICKSTART";commit(message: `stage C-01: migrate 01-knowledge-link README`)
- [x] 3.7 Workspace 02 · 骨架重排(同 3.1)
- [x] 3.8 Workspace 02 · 清理共性段(同 3.2)
- [x] 3.9 Workspace 02 · 新增 verify 段:覆盖 §5.1 期望的 `skill.enable denied reason=reason_missing` / `stage.change analysis → execution` / `whitelist_violation stage=analysis` / `tool.call run_command decision=deny reason=blocked` 关键行
- [x] 3.10 Workspace 02 · 新增 reset 段
- [x] 3.11 Workspace 02 · 新增本 workspace 专属 troubleshooting 段:`stage 未切换导致 yuque_update_doc 被拦` / `run_command 被 blocked_tools 兜底` / `enable 无 reason 被拒` 等 02 独有条目
- [x] 3.12 Workspace 02 · 核验 grep 不变量;commit(message: `stage C-02: migrate 02-doc-edit-staged README`)
- [x] 3.13 Workspace 03 · 骨架重排(同 3.1)
- [x] 3.14 Workspace 03 · 清理共性段(同 3.2)
- [x] 3.15 Workspace 03 · 新增 verify 段:覆盖 §5.1 期望的 `grant.expire` / `grant.revoke` / `skill.disable`(严格顺序)/ `skill.enable decision=denied reason=approval_required` / `tool.call yuque_delete_doc decision=deny reason=blocked` / `skills.index.refresh` 关键行
- [x] 3.16 Workspace 03 · 新增 reset 段
- [x] 3.17 Workspace 03 · 新增本 workspace 专属 troubleshooting 段:`TTL 等待 / refresh 附录位置` / `两层防线现象分不清` 等 03 独有条目
- [x] 3.18 Workspace 03 · §2 追加 fast policy 切换说明占位(单行:"加速现场演示改用 `config/demo_policy.fast.yaml`,详见 Stage D");本 stage 不落文件
- [x] 3.19 Workspace 03 · 核验 grep 不变量;commit(message: `stage C-03: migrate 03-lifecycle-and-risk README`)
- [ ] 3.20 根 `examples/README.md` §2 顶部追加:"新手先读 [`QUICKSTART.md`](./QUICKSTART.md)" + "可先跑 `bash scripts/check-demo-env.sh` 做环境自检(Stage D 产出,可能降级)"
- [ ] 3.21 根 `examples/README.md` §5 末尾追加:"更完整的排障矩阵见 QUICKSTART §6";commit(message: `stage C-root: wire examples/README to QUICKSTART`)

---

## 4. Stage D — 辅助文件、收口与一致性检查

**改哪些文件**
- 新增 `scripts/check-demo-env.sh`(或降级:在 `examples/QUICKSTART.md` §7 落手动五步并删除脚本占位)
- 新增 `examples/03-lifecycle-and-risk/config/demo_policy.fast.yaml`(或降级:在 03 README §2 贴 inline diff 并保留文件为注释占位)
- 追加 `docs/dev_plan.md` 末尾 Addendum 一小段(4–6 行)
- 若 4.2 或 4.4 触发降级,微调 `examples/QUICKSTART.md` §7 或 `examples/03-lifecycle-and-risk/README.md` §2 对应段
- 删除 Stage A 临时产物 `openspec/changes/harden-demo-workspace-onboarding/stageA_inventory.md`

**不改哪些文件**
- 任一 workspace README §3 / §4 / §5.1 / §6 / §7 的既有行文
- `src/`、`tests/`、`hooks/`、`.claude-plugin/`、workspace 下 `skills/**`、`mcp/**`、`schemas/**`、`contracts/**`、`.mcp.json`、`config/demo_policy.yaml` 主文件
- `docs/requirements.md`、`docs/technical_design.md`(本 change 不引新需求、不改架构)

**需要执行的命令**
- `bash scripts/check-demo-env.sh` 应全绿或仅 ⚠️ 未命中,退出码 0
- `python -c "import json; [json.load(open(p)) for p in ['examples/01-knowledge-link/.mcp.json','examples/02-doc-edit-staged/.mcp.json','examples/03-lifecycle-and-risk/.mcp.json']]"` 三份 JSON 合法
- 跨文件 grep 不变量(见 4.7–4.10)
- 至少一次人工 walkthrough(QUICKSTART + 任一 workspace README 的方式 B)

**预期产出**
- `scripts/check-demo-env.sh`(~60 行 POSIX shell)或降级记录
- `examples/03-lifecycle-and-risk/config/demo_policy.fast.yaml`(~20–30 行,主文件最小 diff)或降级记录
- `docs/dev_plan.md` Addendum 1 小节
- 一次手工 walkthrough 的卡点回灌记录(若有)

**如何避免上下文过大**
- 本 stage 不再读三份 workspace README 的正文,只读 QUICKSTART + 要新增的产物自身
- `check-demo-env.sh` 参考 `pyproject.toml:33-35` 的 `tg-hook` / `tg-mcp` 入口定义,其它一概不参考
- `demo_policy.fast.yaml` 只 diff 主 `demo_policy.yaml` 的 TTL 字段,严禁复制其它字段

### Tasks

- [ ] 4.1 落 `scripts/check-demo-env.sh`:POSIX 子集(`set -eu`、`command -v`、`python -c`),检查 Python ≥ 3.11 / `tg-hook` / `tg-mcp` / `claude`(缺席 ⚠️ 不阻断)/ 三份 `.mcp.json` JSON 合法 / workspace `mcp/*.py` 语法合法;输出 ✅/⚠️/❌ 三态,仅 ❌ 退出非零
- [ ] 4.2 降级判定:若 4.1 在 macOS bash 3.2 下不 work 且修复超过 1 小时,改为在 `examples/QUICKSTART.md` §7 落"手动五步自检"段;在本 tasks.md 末尾追加"4.1 降级"标注并删除占位脚本
- [ ] 4.3 落 `examples/03-lifecycle-and-risk/config/demo_policy.fast.yaml`:相对主 `demo_policy.yaml` 的最小 diff — 仅 `default_ttl: 60` + `skill_policies.yuque-knowledge-link.max_ttl: 5`,其余字段**不复制**
- [ ] 4.4 降级判定:若 4.3 经评审觉得"两文件读者困惑",改为 `examples/03-lifecycle-and-risk/README.md` §2 贴 inline diff 并保留文件为注释占位;追加"4.3 降级"标注
- [ ] 4.5 追加 `docs/dev_plan.md` 末尾 Addendum 小节:标题"Addendum — Demo Workspace Onboarding Hardening",1 段 4–6 行,标注完成日期与本 change 名
- [ ] 4.6 核对 `docs/requirements.md`:本 change 不引新需求,**不改动**,只记录一次"已核对"
- [ ] 4.7 grep 不变量 A:`rg -n 'pip install' examples/0X-*/README.md` 无命中
- [ ] 4.8 grep 不变量 B:`rg -nF 'plugin-dir' examples/0X-*/README.md` 所有命中行 2 行范围内必须出现 `QUICKSTART`
- [ ] 4.9 grep 不变量 C:`rg -niF 'anthropic' examples/QUICKSTART.md` 所有命中行仅属于 §3 方式 A 段
- [ ] 4.10 grep 不变量 D:`rg -n 'default_ttl|max_ttl|skill_policies' examples/03-lifecycle-and-risk/config/demo_policy.fast.yaml` 命中的 key 仅限这三类(字段同步不变量;若 4.4 降级则跳过)
- [ ] 4.11 人工 walkthrough:按 QUICKSTART 从头读一遍,再按 01/02/03 任一 workspace README 跑一次**方式 B**,记录所有卡点
- [ ] 4.12 若 4.11 有卡点,回灌 QUICKSTART §6 troubleshooting 并 re-walk 一次;允许迭代 ≤ 2 次,超限则判定 scope 超支,停手升级决策
- [ ] 4.13 归档前置检查:`ls openspec/changes/archive/ 2>/dev/null | grep -q 'add-delivery-demo-workspaces'`,未命中则本 change 停在 `/opsx:apply` 不进 `/opsx:archive`(D8 顺序锁)
- [ ] 4.14 删除 Stage A 临时产物 `openspec/changes/harden-demo-workspace-onboarding/stageA_inventory.md`
- [ ] 4.15 Stage D 单独 commit(message: `stage D: preflight, fast policy, wrap-up and invariants`)

---

## 5. 归档前文档同步

- [ ] 5.1 核对 `docs/requirements.md` 无需变更(由 4.6 执行记录)
- [ ] 5.2 核对 `docs/technical_design.md` 无需变更(本 change 不改架构,仅文档)
- [ ] 5.3 确认 `docs/dev_plan.md` 末尾 Addendum 已追加(由 4.5 执行)
- [ ] 5.4 `openspec validate harden-demo-workspace-onboarding` 通过
- [ ] 5.5 `/opsx:verify harden-demo-workspace-onboarding` 通过后再执行 `/opsx:archive`
