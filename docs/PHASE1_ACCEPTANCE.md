# 阶段一真实环境验收

更新：2026-10-30（Asia/Shanghai）。结论：**已通过本机现有演示数据范围的真实只读端到端验收**；不是生产上线验收，也没有验收采购写入。

链路已实测：Next.js 工作台 → FastAPI / SSE（流式响应）→ 主 Agent / 采购子 Agent → FastMCP → ERPNext REST API；同一次任务在 Langfuse 中读回模型、工具和 Token 用量。

只通过正常 API 修改了本次授权的专用用户、角色与用户权限配置。没有修改 ERPNext 原目录、Docker 配置或业务数据，没有直接查询/写入 ERP 数据库，没有创建管理员 API 密钥，所有 Agent ERP 写工具继续禁用。

## 当前配置与范围

必要配置**无缺失**。`.env` 为 0600、受 Git 忽略；文档和证据不保存密钥。模型为 DeepSeek 官方 `deepseek-flash`；Langfuse 为美国区 `https://us.cloud.langfuse.com`。`ERP_TRACE_HASH_KEY` 已在本地生成，用户和会话标识使用散列值。

- ERPNext 16.34.1 / Frappe 16.33.0，入口 `http://127.0.0.1:8080`。
- API 用户：`supply-chain-agent-phase1@example.invalid`；专用角色：`Supply Chain Agent Phase1 Reader`。此用户只有 API 接入所需的五类 Read / Select 权限，不拥有管理员角色。
- 公司：现有演示库的 **梦迪恩服饰**；本次不是目标智能照明、小家电企业的业务验收。
- Warehouse / Bin 范围：演示-杭州总仓、上海门店仓、次品仓、生产在制仓，完整 Warehouse.name 均带 ` - Mundane` 后缀。
- Supplier / Item 是共享主数据，范围取决于该 Frappe 用户权限，不能虚构顶层 company 过滤。
- Purchase Order 只查表头，按公司与 Frappe 权限过滤；**尚未实现订单行仓库隔离**。

## 专用账户配置与权限检查

`scripts/configure_erpnext_reader.py` 使用原部署文档中的正常管理登录、CSRF 校验和官方账户/权限 API 完成配置；配置结束后退出管理会话。它不是 Agent/MCP 工具。默认只检查，`--apply` 才修改专用配置；失败时禁用专用账户，不为 Administrator 生成密钥，不覆盖其他用户或角色。

本机首次按 System User 配置时发现自动继承的 Desk User 在 Item 上带 Share 权限，审计立即失败并禁用账户。随后仅关闭本专用角色的 Desk Access，将专用账户设为 **Website User（仅用 API）**，移除该继承链后重新审计通过。没有修改共享 Desk User 角色。

依赖传播链：用户类型 / 角色 Desk Access → Frappe 自动附加 Desk User → 角色权限叠加 → Item.share 意外授权。纠正账户类型与专用角色解决来源问题，未放宽验收标准。

- 配置完成时 9 类 DocType × 8 项写入/授权权限，共 **72 项拒绝**；真实查询后加入五类样本文档检查，共 **112 项拒绝**。
- 权限项：Write、Create、Delete、Submit、Cancel、Amend、Import、Share。未通过实际写请求测试拒绝；这是列明的 DocType 与样本审计，不是全站所有文档权限证明。
- 其他角色的有效权限语义保持一致；配置前后业务记录数量一致：Supplier 5、Item 20、Warehouse 16、Bin 31、Purchase Order 6。这些是配置时的数量核对，不是所有字段逐字节不变的证明。
- 真实负向查询：不存在的 Item 返回空数组；非白名单 Bin 仓库在适配层返回 `warehouse_denied`，没有放宽范围。

证据：[账户配置](evidence/erpnext-reader-configuration.json)、[五类真实查询与 112 项权限](evidence/closeout-erp-authenticated.json)、[空结果及越界检查](evidence/closeout-erp-scope.json)。

## 自动化与真实验收分别记录

| 检查 | 类型 | 结果 |
|---|---|---|
| 工程单元 / 真实图测试（Planning、委派、HITL、写阻断、SSE、账户防护等） | 30 项单元 / 脚本模型用例 | **30 passed**；不调用真实模型或 ERP |
| ERPNext Client / Adapter / MCP | 23 项 httpx MockTransport / 进程内 MCP 用例 | **23 passed**；模拟数据，不是 ERP 业务验收 |
| 复用上游 Skills / Review / 记忆 / 追踪 / 执行环境回归 | 104 项离线用例 | **104 passed、17 subtests passed** |
| 默认 Python 回归合计 | 上述离线用例及显式集成开关 | **157 passed、2 skipped** |
| 前端 SSE 解析与待办状态契约 | 前端单元测试 | **3 passed**；TypeScript 和生产构建通过 |
| 五类 ERPNext API | 真实专用账户 / ERPNext GET | 独立 pytest **1 passed**；真实 REST 与 MCP 样本返回完全一致 |
| Agent 检查点 / Store 持久化 | 真实独立 Agent MongoDB | 独立 pytest **1 passed**，不接触 ERP 数据库 |
| DeepSeek Tool Calling、主 / 子 Agent、Skill、计划、独立 Review | 真实模型与真实 ERP 查询 | 页面任务通过，采购子 Agent 为 procurement-order，五类各查一次 |
| 页面流式输出与历史 | 真实 Chrome 浏览器 / Next.js 生产构建 | 无页面错误、无 SSE 错误；渲染 6 张表；保存的助手正文与 SSE 原文一致 |
| 完成状态显示修复 | 真实模型 / Supplier GET / 最终前端构建 | 针对性页面检查通过，计划实际 completed 后才显示 2/2，不再用流结束强制完成待办 |
| Langfuse Trace / Tool / Token | 真实云端 API 读回 | 本次任务 165 条 Observation、12 次 Generation、13 次工具执行；全部 Generation 均有用量，共 **98,796 Token** |

默认回归中的两个 skip 是需要显式开启的真实 ERP 与 Agent Mongo 集成；二者已分别开启并通过，不将 skip 改写为默认测试通过。HITL 的批准/拒绝测试只改变本地测试替身，不发送真实 ERP 写请求；本阶段真实只读调查不会触发业务写审批。

## 工作台真实任务

浏览器在工作台新建会话，要求建立并更新计划、委派采购子 Agent、按需加载 Skill，查询五类样本并审查结果。Supplier / Item / Bin / Purchase Order 各 limit=3，Warehouse limit=4，均只调用一次。

| 类别 | 样本行数 | has_more |
|---|---:|---|
| Supplier | 3 | true |
| Item | 3 | true |
| Warehouse | 4 | false |
| Bin | 3 | true |
| Purchase Order | 3 | true |

采购订单样本编号、供应商、状态、金额，以及库存物料、仓库、实际数量，均与独立 GET 返回的样本核对一致。不是全量业务审计，不据此推断补货量或库存缺口。主 Agent 的计划最终全部 completed；独立 Rubric 评分器 verdict=satisfied，并非仅采用助手自述“Review 通过”。

- 会话：`02b018cb-60d9-492b-b171-959d92dbc7bf`。
- [同一次真实任务的 Langfuse Trace](https://us.cloud.langfuse.com/project/cmvub6405005sad0mm6rjufnw/traces/632dfa47e06630d404e805297a456a6d)。
- [工作台与数据核对证据](evidence/closeout-erp-workbench.json)；[采购结果截图](evidence/closeout-erp-workbench.jpg)。该采购截图摄于待办状态契约修复前，角落的 0/5 属于已定位的前端显示错误；后端计划已经完成。
- [最终前端待办检查](evidence/closeout-todo-ui.json)；[修复后的计划显示](evidence/closeout-todo-ui.jpg)。这项使用新的真实 Supplier 查询，仅复核显示修复，不伪称为再次运行全部五类业务调查。
- Langfuse 只上报执行元数据，没有业务 input/output 正文；所有读回 Observation 正文均为空。Token 用量不等于费用，未自行换算成本。

## 失败记录与本轮修复

本轮第一次真实页面调查成功查到五类数据，但后续主模型连续 120 秒没有产生解析后的内容，触发 StreamChunkTimeoutError。该次未完成主 Agent 最终汇总、计划收尾与独立 Review，**明确判为失败**。Langfuse 有轨迹但失败调用没有完整 Token 用量，也判为追踪验收失败；没有补造用量。没有关闭超时或关闭 Review 来使其通过。另开会话重跑后通过。

失败证据保留在 [真实超时记录](evidence/closeout-erp-workbench-failed.json)，与成功记录分开。更早 `closeout-workbench.json` / `.jpg` 中的 configuration_required 仍是缺 ERP 凭据时的历史失败路径，不代表真实 ERP 数据验收。

这次实际联调另外修复：

1. 后端异常后原先仍发送类似正常结束的 done、且不保存部分对话；现在发送 `failed=true`、保存部分结果与明确未完成说明，前端错误消息不输出原始异常正文。
2. 前端原先收到 done 就把所有待办强制标成 complete；现在只信任检查点发来的真实状态。后端 completed 与前端旧 complete 也已统一，并兼容旧状态。
3. 工程已移至 `/Users/zhanggengyu/Documents/供应链协同Agent`。恢复锁定依赖，并在 `pnpm-workspace.yaml` 固定相对 storeDir，解决安装与运行时缓存路径不一致导致的无终端自动重装失败。依赖版本没有升级。pnpm 11 配置依据：[官方配置说明](https://pnpm.io/cli/config)。

## 本轮发现并修复的问题

1. **流式格式丢失**：原 SSE 代码通过 `content.strip()` 过滤纯空白片段，导致真实模型输出的空格、换行被丢弃，标题和表格粘连。改为原样保留非空字符串，并在主/子 Agent 输出切换时分隔 Markdown 文档、隐藏评分器内部消息；增加 SSE、归档内容和子 Agent 边界测试。
2. **表格渲染缺失**：原 react-markdown 没有启用 GFM 表格扩展。增加固定版本 `remark-gfm@4.0.1`，同步 pnpm 和 npm 锁文件；浏览器已确认存在真实 table/row/cell 结构。
3. **Review 真实模型不兼容**：`langchain-deepseek` 的模型能力元数据声称原生结构化输出可用，LangChain 自动选择 ProviderStrategy；DeepAgents Rubric 随之发送 json_schema response_format，实际 DeepSeek 接口返回 400。对非思考评分模型复制并修正能力元数据，改为 ToolStrategy，保留真实结构化评分和单次审查机制，没有关闭 Review。独立真实模型评分已通过。
4. **历史记录重复刷新**：原页面 effect 依赖每次渲染变化的 history 对象，且提前返回前没有复位 wasStreaming，任务结束后持续轮询历史。改用稳定的 refresh 函数依赖，并先更新流状态，只在完成边沿刷新。
5. **测试污染真实追踪**：用户开启 Langfuse 后，部分离线测试会继承真实开关并尝试导出脚本模型轨迹。默认 pytest 用例统一关闭真实导出；回调单测可使用各自假客户端。真实追踪由显式验收命令运行，避免模拟与真实结果混在一起。

上述第 3 项的依赖传播链为：第三方模型能力元数据 → LangChain 输出策略自动选择 → DeepAgents 评分器请求格式 → 真实接口拒绝 → Review grader_error。修复针对能力声明，不改变 ERP 权限或业务执行范围。


## 复跑与启动

完整启动步骤：[START_PHASE1.md](START_PHASE1.md)；凭据维护：[CONFIGURE_READONLY_AND_LANGFUSE.md](CONFIGURE_READONLY_AND_LANGFUSE.md)。当前本地前后端、MCP 与 Agent MongoDB 正在运行；ERPNext 使用原部署。

```bash
cd '/Users/zhanggengyu/Documents/供应链协同Agent'
# 分别在三个终端运行
./scripts/start.sh mcp
./scripts/start.sh api
./scripts/start.sh web

# 单元、模拟测试及构建，不导出模拟模型轨迹
./scripts/check.sh

# 真实 ERP 身份/权限、五类 REST/MCP 样本比对；不调用模型，不写 ERP
.venv/bin/python -m evals.phase1_acceptance --erp \
  --output docs/evidence/closeout-erp-authenticated.json

# 同一次真实任务的 Langfuse 独立读回
.venv/bin/python -m evals.phase1_acceptance --trace-id 632dfa47e06630d404e805297a456a6d \
  --output docs/evidence/closeout-trace-verification.json
```

工作台：`http://127.0.0.1:3000`；API 文档：`http://127.0.0.1:8000/docs`；MCP：`http://127.0.0.1:9000/sse`。

## 未测试边界与下一阶段阻塞

- **未做**真实采购写入、库存调整、提交、取消或业务审批；所有写工具保持禁用。没有进入 BOM、MRP、生产或数据库迁移。
- 当前 Web API 仍无生产登录鉴权和逐人 ERP 身份映射，客户端 user_id 不可信；仅本机访问，尚不能对外开放。
- 现有前端依赖安全审计有 20 条公告（5 critical、9 high、5 moderate、1 low，非 20 个不同包），涉及固定的 Next.js 16.2.12 及传递依赖；见 `closeout-dependency-audit.json`。本轮没有修补这些公告或进行利用测试，公开部署前须单独升级、回归。
- 现有演示公司是服饰数据；进入智能照明企业正式验证前，需要用户确认正式公司、仓库、样本与共享主数据权限策略。当前凭据没有缺失，无需再提供管理员密钥。
- Purchase Order 仅表头；订单行仓库权限、跨公司负向隔离、全量分页与复杂单据权限组合没有做完整业务验收。
- 本次完整任务用量达到 98,796 Token，且出现过模型流式超时；需要针对基础上下文、子 Agent 输出、Review 与服务超时做独立优化。一次成功不是稳定性或并发性能验收。
- Review 保留上游部分 Java ERP 写入检查模板，本阶段只读任务将其判为不适用；未来受控 ERPNext 写入前必须替换为真实 items / qty / rate / warehouse 契约并重新评测。
- 后续采购闭环需先定义受控草稿契约与业务规则、最小写权限、不可篡改审批记录、幂等和失败恢复；草稿、提交、取消分别授权和测试。不得直接恢复旧 Java ERP 写工具。
- 命令/脚本执行工具仍关闭；若将来需要，先独立验收执行隔离、网络和凭据边界，不能恢复 LocalShell 自动降级。


## 后续维护：MongoDB 配置统一（2026-10-30）

Web 会话、LangGraph 检查点、长期 Store 和旧沙箱映射共用 `src/agent/config.py` 中的 MongoDB 设置，均从现有 `.env` 读取。存储连接与 Agent 的装配关系保持为 AgentLoader 初始化后传入 create_main_agent；没有改变数据库内容或启用执行沙箱。

本次后端回归 **164 passed、2 skipped、17 subtests passed**；包括 7 项新增配置一致性测试。真实独立 Agent MongoDB 持久化测试 **1 passed**，仅使用并清理随机临时测试库。本次不重跑真实模型、ERPNext 或前端验收，前文结果属于原收尾轮次。

证据：[后端回归](evidence/mongo-config-regression.txt)、[真实 MongoDB 测试](evidence/mongo-config-live.txt)。
