# Skill-Hub 运行时治理框架
这个项目，我会把它定义成一个**以 Skills 为抽象的 Agent 运行时治理层**。  
S： 它解决的核心矛盾是，Agent 工具一多，模型每轮都要在大候选集合里做选择，  
所以系统必须控制‘什么时候看见什么能力、什么时候真正拿到它、以及之后怎么收住’。

A：我主要做了两件事：  
一是把项目从工具过滤收敛成知识披露加执行授权的统一机制，也就是整体架构收敛；  
二是核心机制落地，尤其是 `before_agent`、`wrap_model_call`、`read_skill / enable_skill`、  
`active_tools` 重算、会话态管理、Redis 续跑和 Langfuse 观测审计这条主链。  

R： 最后形成的价值是，能力暴露会跟着 Skill 启用状态和会话状态动态收敛，模型不会一上来面对所有工具，  
同时这套机制还能恢复、续跑、回放和审计。

## 项目定义与问题背景
这个项目，我会把它定义成一个**<font style="color:#DF2A3F;">以 Skills 为抽象的 Agent 运行时治理层</font>**，而不只是一个 Skills 功能或者一个简单的工具路由层。  

<u>S：它最初要解决的真实问题是</u>：**<font style="color:#DF2A3F;">Agent 在真实任务里一旦接了很多工具之后，模型就会越来越难稳定地把事情做对。</font>**  
因为系统如果把太多能力一次性暴露给模型，模型每一轮都要在一个很大的候选集里做选择，这时候链路会变慢、变乱，而且很容易误选工具。  
这个本质上不是单个模型聪不聪明的问题，而是 **Agent 运行时怎么暴露能力** 的问题。  

> 这不是我主观猜的，而是有证据支撑的。  
有一篇做 RAG MCP 的论文证明了 skill 库一旦变大，且能力之间语义接近，就会出现 semantic confusability，模型的选择准确率会下降；
>
> LiveMCPBench 在 70 个 servers、500 多个 tools 的大规模 MCP 环境里也发现，retrieval error 是最主要的失败来源之一，接近一半失败都出在这里，说明这不是小概率问题；
>

<u>T： 我当时要解决的核心矛盾是</u>：**<font style="color:#DF2A3F;">怎么让模型在正确的时机，只看到正确的能力；既能先理解某类能力，又不会一上来就拿到整包工具。</font>**  
所以我做的不是简单的工具接入，而是把它收敛成一个 **以 Skills 为抽象的 Agent 运行时治理层**。 

**<u><font style="color:#DF2A3F;">A：在这个项目中我主要做了四件事</font></u>****<font style="color:#DF2A3F;">：</font>**

1.  把项目从最初简单的“工具过滤”收敛成“知识披露 + 执行授权”的统一机制。 
2.  把 Skill 拆成 **Knowledge Plane** 和 **Execution Plane**，通过 `read_skill` 和 `enable_skill` 分离“理解能力”和“启用能力”。 
3.  把治理点放到 Middleware，尤其是 `before_agent` 和 `wrap_model_call`，把 prompt 重写、tools 重写、state 管理、policy 校验、审计观测统一收进一个控制面。 
4.  把整条链路做成 **发现 Skill → 读取 Skill → 启用 Skill → 重算 active_tools → 工具执行 → 观测与回写** 的闭环。

<u>R： 最后落出来的，不是一个普通的 Skills loader，也不是一个简单的 tool filter，而是一套真正运行在会话态上的能力治理机制</u>

+ **<font style="color:#DF2A3F;">模型不会一上来面对所有工具，能力暴露跟着 Skill 启用状态变化 </font>**
+ **<font style="color:#DF2A3F;">会话态可以恢复、续跑、回放 ，审计和观测能解释“这轮为什么这么跑”</font>**

> <u>比如很常见的一个开发场景，用户说：‘帮我排查线上数据库连接异常，并给出处理建议。’</u>  
如果系统一上来就把 SQL、日志、慢查询分析、Shell、工单系统这些能力全暴露给模型，它很容易先做错动作，甚至在还没明确问题边界的时候就去调用高风险工具。但如果先把能力收住，只给它看技能目录，让它先判断这是个数据库排障任务，再去读对应 SOP，再显式申请授权，最后只拿到 `sql_query`、`logs_search`、`slow_query_analysis` 这一小组工具，模型的动作就会稳定很多。这就是这个项目的现实价值。 
>
> <u>然后还有一点，在语雀生态里，有‘知识关联’这种 Skill</u>，官方描述是分析知识库文档之间的隐藏联系、建议交叉引用，会结合 `get_repo_docs`、`get_doc`、`update_doc` 这类工具来完成任务。问题在于，真实 Agent 环境里通常还会额外挂很多 MCP 工具，尤其是各种 search / retrieval 类工具。模型一上来如果同时看到语雀域内文档能力、外部网页 search、别的知识库 search、代码仓 search，它很容易选偏搜索的工具。语雀生态本身就是多工具协作场景，而我的项目解决的就是这种‘工具多了以后怎么控暴露面’的问题。  
>

---

### 三层边界
这个项目里我把 MCP、Skills、Middleware 这三层边界分得很清楚。

**第一层是 MCP。**<font style="color:#DF2A3F;">解决的是供给层问题</font>，也就是外部能力怎么被标准化成可调用的 tools，它更像能力接入层。

**第二层是 Skills。**<font style="color:#DF2A3F;">解决的是任务方法组织的问题</font>。它把 SOP、适用边界和执行边界组织成一个可复用的运行时单元。

**第三层是 Middleware。****<font style="color:#DF2A3F;">Middleware 是我这个项目真正的治理层。它不只是打日志或者加 hook，而是在请求真正发给模型之前，统一控制这轮 prompt 怎么写、tools 怎么下发、state 怎么读写、policy 怎么生效、审计怎么记录。</font>**

> 在知识关联这个场景里，MCP 负责把 `get_repo_docs`（获取知识库文档列表）、`get_doc`（获取单篇文档内容）、`update_doc`（更新文档内容）、`search`（检索文档）这些能力标准化接进来；Skills 负责把这类任务的方法组织起来，并给出这个 Skill 对应的 `allowed_tools`（该 Skill 允许使用的工具列表）；Middleware 负责的是，当知识关联这个 Skill 被启用以后，怎么把这个 Skill 对应的工具集合和当前会话里其他已启用 Skills 一起，重新收敛成最新的 `active_tools`（当前会话真正可见的工具集合）。  
>

---

## 核心运行链路
这套系统真正让我觉得有工程价值的地方，是它不是静态配置，而是一条完整的运行时链路。

比如用户说：“帮我排查数据库异常，并给出处理建议。”

1. 第一步**<font style="color:#DF2A3F;">初始化</font>**， 先进入`before_agent`，这一步会带着 `session_id` 恢复会话态，检查当前会话里有没有 `skills_metadata`、`skills_loaded` 这些基础状态；如果没有， 也不会直接扫技能仓库，而是先查 metadata cache；  再没有，才去扫描 `base、team、project、user` 这些 source，构建 SkillIndex， 建好的 SkillIndex 最终会写进 **当前会话的 **`**state**`**中**，作为这轮会话实际使用的技能目录快照。  
2. 第二步**<font style="color:#DF2A3F;">注入 SkillIndex 和基础工具</font>**，进入第一次 `wrap_model_call`。这时候还不会直接把一堆数据库工具全给模型，而是通过 PromptComposer 把技能目录注入进去，同时只暴露很小的一组基础工具，比如 `read_skill`、`enable_skill` 和少量通用工具。模型在第一轮做的事情主要是**读取 Skill、理解 Skill，再根据任决定是否启用 Skill**。  
3. 第三步**<font style="color:#DF2A3F;">模型判断问题</font>**，分析出跟数据库排障相关，然后调用 `read_skill("db_ops")`。系统把 `db_ops` 的 SOP、适用场景、边界和注意事项返回给模型，让它先理解这类任务该怎么做。
4. 第四步**<font style="color:#DF2A3F;">授权组装可用工具列表</font>**，模型确认要进入这个 skill 之后，再调用 `enable_skill("db_ops")`。这一步才是真正的授权节点：SkillGate 会先跑 policy，看当前用户、租户、环境能不能开这个 skill；通过以后，系统会把这个 Skill 启用到当前会话里，并把这个 Skill 对应的 `allowed_tools`（该 Skill 允许使用的工具列表）一起带入后续的工具集合重算。
5. 第五步**<font style="color:#DF2A3F;">实际装载工具</font>**，进入下一轮 `wrap_model_call`。系统这时候会根据最新的 `skills_loaded`（当前会话已启用的 Skills）以及这些 Skill 对应的 `allowed_tools`（该 Skill 允许使用的工具列表）一起重算 `active_tools`（当前会话真正可见的工具集合），然后通过重写 Tools 列表把这一轮真正可见的最小工具集下发给模型，比如只给 `sql_query`、`logs_search`、`slow_query_analysis`。
6. 第六步**<font style="color:#DF2A3F;">模型根据最小工具集里发起调用</font>**，比如先查日志、再查慢查询，最后给出分析结论。
7. 第七步**<font style="color:#DF2A3F;">更新当前会话的运行态</font>**，比如 skills_loaded、active_tools、skill_last_used_at 这些数据。  
这些状态我会放在 LangChain state 里，因为它们是强依赖于当前会话的推理和工具重写的，所以必须跟着 Agent 调用链走。这样 before_agent 负责恢复稳定上下文，wrap_model_call 负责按当前状态重写 prompt 和 tools，职责边界会比较清楚。
8. 第八步**<font style="color:#DF2A3F;">把这轮最新的会话快照回写到 Redis</font>**。比如 session:{session_id} 下面会存当前会话的 skills_loaded、最近使用时间、enable 次数这类信息。这样下一次请求即使打到另一台机器，也可以先从 Redis 把会话恢复起来，再继续往后跑。  
与此同时，**<font style="color:#DF2A3F;">我会把这条链路里的关键 observation 打到 Langfuse</font>**，比如 skill.read、skill.enable、tool.call、task.evaluate。所以 Redis 回答的是“这个状态还能不能接着跑”，Langfuse 回答的是“这轮为什么这么跑”。

最终形成的是一条真正运行起来的闭环  ：  
**<font style="color:#DF2A3F;">先恢复会话态，再发现 skill，再读 SOP，再显式授权，再重算最小工具集，最后才执行工具。</font>****  
**这也正是我和直接注册几十个 skills 或者直接暴露一堆 tools 的本质差异：  
**<font style="color:#DF2A3F;">把知识发现、执行授权、状态管理和观测闭环串成一个真正的运行时机制。</font>**

> 举一个例子，比如说：‘帮我查线上一个报警，顺手总结成复盘草稿。’  
这个任务天然跨日志检索、知识归纳和文档生成三个阶段。  
如果没有运行时治理，模型很容易一上来就在日志工具、文档工具、搜索工具之间乱跳。  
但在我这套机制里，它会先判断需要哪类 skill，先读对应 SOP，再逐步拿到那一阶段需要的最小工具集。前半段主要是 logs 和 analysis 的 Skill，后半段才会逐步进入 report 相关。这样既减少误选，也减少无关工具对当前推理的干扰。”
>

---

## 拆知识 / 执行双平面
<u>S：如果这不拆成两个平面，就会有两个问题</u>：  
第一，知识面和执行面混在一起， 模型一旦读到这个 Skill，就很容易默认自己已经拿到了这组能力；  
第二，会话状态会变得不清楚。你很难解释当前这个 Skill 到底只是‘被读过’，还是已经‘被启用了’，后面 `active_tools` 为什么会这样变化，审计和回放也会变得很模糊。  

<u>T： 所以我要把 Skill 拆成 Knowledge Plane 和 Execution Plane</u>。原因很简单：  
**知道这类任务该怎么做，和系统此刻愿不愿意把这组能力真正开放给模型，其实不应该是同一件事。  
****强行拆开，****<font style="color:#DF2A3F;">本质上就是为了把知识获取和能力启用分成两个清晰的运行时动作。  </font>**

<u>A：具体来说，我用 </u>`<u>read_skill</u>`<u>和</u>`<u>enable_skill</u>`<u> 负责这两个平面</u>  
 `read_skill` 让模型先读 Skill 的 SOP、适用边界、常见坑，负责理解。    
 `enable_skill` 决定这个 Skill 是否真正进入当前会话，并把对应的 `allowed_tools` 带入后续工具集重算，负责执行。  

<u>R：这样做的好处是：</u>

把 Agent 的能力暴露从静态配置，变成运行时可控。  
既能了解模型在运行的时候知道了哪些能力，也能解释模型为什么知道这类能力。

> 比如代码改动类任务里，读代码、分析依赖，和真正写文件、跑命令、提交 patch，风险是完全不同的。  
如果只保留一个平面，模型一旦进入 code skill，很可能默认自己已经拥有 edit、shell、git 这些能力。  
但拆成双平面以后，它可以先在 Knowledge Plane 学会这类任务该怎么做，只有在 Execution Plane 通过授权以后，  
才真正获得写和执行相关能力。这个差别在真实工程里非常重要。”
>

### Skill 怎么拆
在我这套框架里，治理的基本单位是 Skill。而`active_tools`是由 Skill 及其对应的 `allowed_tools`算出来的。  
<u>S：所以 Skill 怎么拆，实际上决定了运行时边界长什么样。</u>

拆得太粗，`allowed_tools` 会重新膨胀，工具又会在 Skill 这个粒度上混到一起  
拆得太细，`read_skill` 给模型的更像是几个工具的说明书。模型又要自己重新拼方法链，Knowledge Plane 的价值就没了。**  
**<u>A：所以我给出一个 Skill 的拆分粒度的判断方法，主要看两件事。</u>  
第一，它是不是一个稳定的方法单元；第二，它能不能共用一次 `enable_skill` 的执行边界。  
如果一组能力虽然业务相关，但风险等级、授权条件、policy 边界差很多，那我一般不会硬塞到一个 Skill 里。  

<u>R： 所以我最后的原则就是</u>：**<font style="color:#DF2A3F;">一个 Skill 既要能承载完整 SOP，又要保持执行边界一致。</font>**  
如果一组能力可以共用一份方法说明，也可以共用一次 `enable_skill` 的授权边界，那它们就适合放在一个 Skill 里；  
只要方法链明显不同，或者执行边界差很多，就应该拆开。  
<u>然后还有一点，我默认是先偏保守的拆</u>，宁可一开始窄一点，再靠观测放开，而不是先全给再慢慢收。   
因为太宽的代价是边界失控，太窄的代价是任务完不成，而后者至少更容易从失败链路里被明确看见。

> 比如数据库慢查询优化，如果我把查慢日志、看执行计划、做索引诊断、给优化建议、再到真正执行 DDL 变更，全塞进一个 Skill，那这个 Skill 就拆粗了。前半段是读和分析，后半段已经是高风险执行，执行边界明显不一致。   
但如果我再把“查慢日志”“跑 explain”“看索引建议”各拆成一个 Skill，又拆细了，因为模型读到的只剩工具说明。   
所以更合理的是拆成“慢查询诊断”和“变更执行”两个 Skill：前面负责分析，后面负责执行。
>

> 再比如知识关联，如果我把 `get_repo_docs`（获取知识库文档列表）、`get_doc`（获取单篇文档内容）、`search`（检索文档）、`update_doc`（更新文档内容）全放进一个 Skill，这个 Skill 在知识侧还能讲通，但在执行侧就拆粗了，因为前面是读查分析，后面已经是写入。  
但如果我把每个工具都拆成一个 Skill，又拆细了，模型还得自己重新拼方法链。  
所以更合理的是拆成“知识关联分析”和“关联落库”两个 Skill：前者负责分析方法，后者单独承载写操作边界。
>

#### 改 Stage 粒度
按我当前这版架构，`allowed_tools` 是跟着 `enable_skill` 走的，治理单位是 Skill，不是 Skill 内部的步骤。  
<u>如果要一个 Skill 多个 stage、不同 stage 暴露不同工具，本质上要把运行时状态扩展成‘已启用哪个  Skill 且当前停在哪个 stage’。</u>

具体做法上，我会把 `allowed_tools` 按 stage 分层，在 session state 里新增 `current_stage`，`enable_skill` 只负责启用 Skill 并初始化 stage，再加一个显式的 `change_stage` 动作来切换阶段。之后 `wrap_model_call` 重算 `active_tools` 时，不再取整个 Skill 的 `allowed_tools`，而是取当前 stage 对应的 `allowed_tools`。

## State 管理、缓存与一致性
<u>S：状态和缓存不一致，会直接让知识侧和执行侧裂开</u>。如果会话状态、缓存和全局版本混在一起，最危险的不是“读到旧缓存”，而是同一会话前后读到的知识、白名单和工具视图不属于同一个快照。

<u>T：所以我的目标是</u>，**<font style="color:#DF2A3F;">做一套既能支撑多会话、跨实例续跑，又能保证会话内稳定、不被运行中热更新打散的状态治理方案。</font>**

<u>A：具体来说，我的采用三层存储进行状态管理</u>

第一层<u><font style="color:#DF2A3F;">把</font></u>**<u><font style="color:#DF2A3F;">当前会话的运行态</font></u>**<u><font style="color:#DF2A3F;">放在 LangChain state 里</font></u> ；  
第二层<u><font style="color:#DF2A3F;">用本机缓存来存</font></u>**<u><font style="color:#DF2A3F;">可重建但重复计算很贵</font></u>**<u><font style="color:#DF2A3F;">的东西</font></u>，主要存两类： skill metadata 和`read_skill` 解析 Skill.md 的结果；  
第三层**<u><font style="color:#DF2A3F;">用 Redis 管可恢复，Langfuse 管观测和审计</font></u>**。Redis 回答“状态还能不能接着跑”，Langfuse 回答“这轮为什么这么跑”。  

同时，会话快照要带版本：会话状态里不只记 skill_name，还要记 version，形成 skill snapshot；  
metadata_cache、doc_cache 的 key 也带版本。

默认不追求运行中自动热更新：新会话读新版本，老会话保持当前快照，必要时显式 refresh。我这里优先保证会话内一致性，而不是运行中的全局即时一致；因为对 Agent 来说，最危险的不是缓存稍旧，而是同一会话前后读到的知识和边界不属于同一个快照。

会话态与全局态硬隔离：skills_loaded、active_tools 这类会影响授权边界的运行态必须按 session_id 隔离；metadata cache 这类只影响读取性能的内容才允许共享。

<u>R：这一整套设计带来的结果是：</u>

+ 线程 A 可以稳定用 db_ops@v1，线程 B 用 db_ops@v2，旧 session 不会中途漂到新边界。
+ cache 只负责“快”，不负责“真”；真实会话状态在 Redis，回放与审计在 Langfuse。
+ 会话态和授权边界不会在并发下互相污染。

## 可观测、审计与 Langfuse
S：如果只有能力治理，没有可观测和审计，就只能知道“系统跑了”，  
却回答不了“它为什么这么跑、失败在哪一层、谁在什么时间启用了什么能力”。

T：所以需要把治理链路做成可追踪、可回放、可审计的观测体系。

<u>A：主要采用了 Langfuse</u>

**首先定义关键业务节点**：**发现技能、读取 SOP、显式授权、调用工具、完成任务**。然后**再手动埋点**。具体做法是：**<font style="color:#DF2A3F;">一次用户请求先建 root trace，多轮对话挂在同一个 session 下；然后我在 </font>**`**<font style="color:#DF2A3F;">skill.read</font>**`**<font style="color:#DF2A3F;">、</font>**`**<font style="color:#DF2A3F;">skill.enable</font>**`**<font style="color:#DF2A3F;">、</font>**`**<font style="color:#DF2A3F;">tool.call</font>**`**<font style="color:#DF2A3F;">、</font>**`**<font style="color:#DF2A3F;">task.evaluate</font>**`**<font style="color:#DF2A3F;"> 这些节点各包一层 observation/span，把输入、输出、状态变化和失败原因写进去。这样打开一条 trace，不只是看到模型调过一次，而是能顺着 observation 把 Skills 这条链完整回放出来，知道是读错了、授权错了，还是工具用偏了</font>**。  `skill.read` 记读了谁、读了多长、是否命中缓存；`skill.enable` 记启用谁、前后状态怎么变、是 granted 还是 denied；`tool.call` 记调用结果和失败归因；`task.evaluate` 记任务最终完成情况。这样链路是完整可解释的。

### 评测设计与指标可信性
我把运行时治理效果拆成可验证的指标，而不是只看一个笼统的成功率。

1. 漏斗指标：`shown -> read -> enable -> tool -> task`
+ `shown`：技能有没有被看见 、 `read`：模型有没有真正去理解 、`enable`：它有没有被认为值得授权 
+ `tool`：执行有没有跑通 、`task`：最终目标有没有完成  
**<font style="color:#DF2A3F;">这个漏斗最大的价值，是能把问题定位到知识侧、授权侧还是执行侧。</font>**
2. 误调用与失败分布，我把工具误调用拆成三类：   
**<font style="color:#DF2A3F;">白名单外调用 、当前 skill 域内选错工具 、工具选对了但参数 schema 错   
</font>**这样就能区分：到底是边界问题、描述问题，还是抽参 / 执行问题。后续优化方向会非常不一样。
3. 重试与恢复质量，我不只看“重试了几次”，而是看：  
第几次重试、第一次为什么失败 、最后有没有恢复，这样 trace 能解释单次过程，聚合后也能解释整体分布。

<u>R：这样我的指标体系就不只是依赖于一个最简单的“成功率”</u>，而是：

+  漏斗解释链路卡在哪一层 
+  误调用分桶解释失败属于哪类问题 
+  重试恢复解释系统有没有收敛能力 

## Policy
<u>S： 后端鉴权只能回答“最终能不能落地”，回答不了“这轮任务该不该把这组能力暴露给模型”</u>。

> <u>举个例子，用户确实有数据库修改权限，但他这次的诉求只是想分析慢查询，</u>看看瓶颈在哪、索引要不要补、SQL 写法有没有问题。这个时候，如果系统没有运行时 Policy，模型一旦在当前会话里看到了修改类工具，它就可能把“直接改数据库”也当成一个合法候选动作，甚至为了“帮用户更快解决问题”，擅自调用其他工具去执行修改。最后从后端鉴权的角度看，这次调用可能完全合法，因为用户确实有权限；但**<font style="color:#DF2A3F;">从任务语义和运行时边界看，这个动作就是错的，因为用户要的是分析，不是执行变更。</font>**
>

<u>T： 所以我要在最终资源权限之前，再补一层运行时准入控制</u> 。

把后端鉴权和运行时 Policy 分成两层来看。底层服务有最终的权限校验，保证的是“不越权”。  
在这个基础上再加一个 Policy 负责控制 Agent 在这一轮里可以拿到什么能力去规划和选择。

<u>A：具体的实现上来说</u>，  
**<font style="color:#DF2A3F;">Policy 作用在 </font>**`**<font style="color:#DF2A3F;">enable_skills</font>**`**<font style="color:#DF2A3F;"> ，负责运行时授权，判断在当前 user / tenant / env / risk_level 下 Skill 能不能启用 。</font>**  
只有 Policy 通过了，这个 Skill 才会被加入 `skills_loaded`，对应的 `allowed_tools` 才会一起进入会话，参与 `active_tools` 的重算。

<u>R：结果上来看</u>，**<font style="color:#DF2A3F;">通过 Policy 可以控制 Skill 和 Tools 能不能进入会话，  
</font>****<font style="color:#DF2A3F;">这样模型看到的就是“这一轮该用的能力”，而不是“用户理论上所有能用的能力”。</font>**

值得一提的是，MCP 社区里之前已经有人提过 Issue，希望能 selectively disable tools，因为工具太多会让 LLM confused。  
整体来看：  
`**<font style="color:#DF2A3F;">SKILL.md</font>**`**<font style="color:#DF2A3F;"> 负责知识说明，</font>**`**<font style="color:#DF2A3F;">allowed_tools</font>**`**<font style="color:#DF2A3F;"> 负责管 Skill 内部边界，Policy 负责管运行时外部准入条件，后端鉴权负责最终兜底。</font>**

这样整个系统的边界才是完整的。

> 放到知识关联这个例子里，逻辑也是一样的。知识关联这个 Skill 能不能在当前会话里启用，先看 Policy；这个 Skill 启用以后，它对应的 `allowed_tools`（该 Skill 允许使用的工具列表）能不能进入当前会话，也先看 Policy 和运行时状态控制；即使这些工具已经进入当前会话了，模型最终真的去调用 `update_doc`（更新文档内容）时，底层服务仍然还要再做最后一道权限校验。
>

---

## 治理点要在 Middleware
## Middleware
<u>S：如果治理点不落在模型调用前，前面的 SkillPack、双平面、显式授权这些设计，很容易停留在概念层。</u>  
因为这些东西本质上都还是“状态”和“规则”，模型最终感知到的，其实还是这一轮 prompt 里有什么、tools 里有什么。

> 举个例子，系统里已经有了 SkillIndex，也有了 `read_skill`、`enable_skill` 这套机制。模型先读了某个 Skill，也成功 enable 了它。  
如果这个时候没有一个位置，在**下一轮模型调用前**真正根据 `skills_loaded` 去重算 `active_tools`，再把新的工具集合下发给模型，那前面的设计其实都没有真正落地。  
最后会出现一种很典型的情况：**<font style="color:#DF2A3F;">系统内部状态里写着“这个 Skill 已启用”，但模型这一轮看到的工具集合根本没变。  
</font>****<font style="color:#DF2A3F;">这样 SkillPack 只是静态材料，双平面只是概念拆分，授权也只是记账动作，而不是运行时边界真的被改写了。  </font>**
>

<u>T：所以我要找到一个真正能把“内部状态”变成“模型这一轮真实输入”的落点。</u>  
这个位置必须同时能读 state、改 prompt、改 tools。只有这样，前面的 SkillPack、双平面和授权结果，才能真正落成运行时边界。

<u>A：具体实现上，我把治理点放在 Middleware，特别是 </u>`<u>wrap_model_call</u>`<u> 这一层。</u>  
**<font style="color:#DF2A3F;">因为它正好卡在请求真正发给模型之前，可以一边把 SkillIndex 注入 prompt，一边根据 </font>**`**<font style="color:#DF2A3F;">skills_loaded</font>**`**<font style="color:#DF2A3F;"> 和 </font>**`**<font style="color:#DF2A3F;">allowed_tools</font>**`**<font style="color:#DF2A3F;"> 重算 </font>**`**<font style="color:#DF2A3F;">active_tools</font>**`**<font style="color:#DF2A3F;">，再通过重写下发这一轮真正可见的工具集合。同时，state 写回、观测、审计也都能挂在这一层。</font>**

> 比如知识关联这个 Skill，Middleware 的价值就特别直观。  
假设当前 Agent 同时接了语雀里的 `search`（检索文档），还接了别的 MCP 暴露出来的网页搜索、内部知识库搜索、代码仓搜索。如果没有 Middleware，这些工具会一起出现在模型面前，模型只能靠名字和描述自己猜当前该用哪个。这就是 MCP 的弊端<font style="background-color:#D8DAD9;">（提一下 MCP 的加载方式）</font>  
但有了 `wrap_model_call`（包裹模型调用并重写 prompt / tools 的中间件层），我就可以把当前会话里已经启用的 Skills 以及这些 Skills 对应的 `allowed_tools`（该 Skill 允许使用的工具列表）统一重算，最后只把当前这一轮真正应该看到的 `active_tools`（当前会话真正可见的工具集合）下发下去。  
所以 Middleware 不是单纯打个日志或者加个前置 hook，它是把“本轮模型该看到什么能力”真正做成了会话态驱动的运行时控制。  
>

---

### 项目亮点和价值总结
这个项目最有价值的地方，是**我把知识披露、执行授权、状态管理和观测闭环统一到了一个运行时控制面里。**

它带来的直接收益有三类：

第一类是**稳定性**。  
模型不再一上来面对所有能力，而是根据当前会话已启用的 Skills 计算出来的 `active_tools`，所以误选会更少，推理也会更聚焦。  

第二类是**安全性和边界感**。  
`allowed_tools` 不是一句写在文档里的自然语言文字，而是和 policy、会话态、最小工具集下发、审计记录连起来的实际运行时边界。

第三类是**可观测和可优化**。  
因为 `skill.read`、`skill.enable`、`tool.call`、`task.evaluate` 都在链路里有记录，所以后面不管是做问题定位、回放分析，还是做 skill 路由和授权策略优化，都有数据基础。

所以这个项目的价值，不是在于我给模型‘增加了多少能力’，而是在于我让模型在复杂能力环境里，**更有边界地使用能力**。”

# 实验怎么做的
## Skill-Hub
### 80%怎么测
【Q】@“工具误选率降低 80%”这个指标是怎么定义和测出来的？  
【A】我是按 **首个关键工具是否选对** 来定义误选率的。评测时做了一套离线回放数据集，固定模型版本、prompt、temperature、工具 mock 和超时策略，**<font style="color:#DF2A3F;">只改变工具暴露方式和 Skills 机制。原始全量暴露时，大概 50 次里错了将近 30 次；用了“渐进式披露 + 显式授权”后，只错到五六次</font>**，所以我说的是明显的相对下降趋势。

### 评测集怎么构造
【Q】你是怎么做回放评测来验证这套 Skills 机制有效的？  
【A】我做法比较工程化，分四步。

+ 第一步，先做一套离线回放数据集，本质上就是 50 多条“工具选择题”，每条都标清用户问题、期望工具和为什么选它，而且会刻意混入相似工具干扰项。
+ 第二步，做三组对照：全量工具暴露、只有技能目录和 `SKILL.md`、以及我最终这套“渐进式披露 + 显式授权 + 最小工具集”。
+ 第三步，固定模型版本、prompt、temperature、mock 和重试策略，只改工具暴露方式，统一记录首个工具是否选对、任务是否完成、token、latency、可见工具数。
+ 第四步，不只看误选率，还会看混淆矩阵和错误分桶，分析到底是语义混淆、参数错误，还是没遵循 workflow。

最后结果上，全量暴露时 50 次里错了将近 30 次，最终方案只错了五六次，数字不是绝对值，但趋势很明显，说明真正有效的不是单纯缩小候选集，而是“知识平面 + 执行平面”一起把错误压下来了。

【Q】@你有没有覆盖 no-tool 场景？如果模型本来就不该调用工具，这类误选怎么算？  
【A】严格来说，完整评测里应该覆盖 no-tool 场景，而且这类场景要单独算，不该和“该选哪个工具”混在一起。因为 no-tool 错误反映的是“有没有乱动手”，而 tool 误选反映的是“动手时选没选对”。两者口径不同，我不会混成一个指标讲。

【Q】@你是按 skill 级别评估，还是按最终具体 tool 级别评估？  
【A】我主指标还是按 **最终具体 tool 级别** 看，因为误选最终发生在执行层；但我会同时保留 skill 级视角，看模型有没有先进入对的 skill 域。前者更适合看误选，后者更适合看双平面到底是不是把路由先收窄了。

