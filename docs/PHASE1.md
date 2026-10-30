> 最新收尾状态见 [PHASE1_ACCEPTANCE.md](PHASE1_ACCEPTANCE.md)：DeepSeek 与 Langfuse 已完成真实验证；ERPNext 专用 API 只读用户已自动配置，五类认证查询及 112 项有效写权限检查通过。下文是首次代码交付时的历史记录，能力状态以最新验收文档为准。

# ERPNext 供应链协同 Agent · 阶段一记录

首次代码交付记录（2026-10-30；不代表最新验收状态）。当时结论：基础工程已落地并通过所列验证；真实模型、ERPNext 认证只读联调、真实 Langfuse 入库尚未验收，不能视为全部完成。

## 来源与环境

- 原仓库：https://github.com/wodrake/ERP-AGENT-open-source
- 基线与克隆时最新提交均为 `08ded02cc14228fa36d9b5706caa7bc8144355f6`。工作分支 `codex/erpnext-phase1`。本地原目录为空，直接克隆，未覆盖现有文件。
- 本地未找到《ERP-AGENT → ERPNext 技术迁移差距评估报告》全文。本次以用户列出的问题与基线实际代码核实，不声称已阅读报告。
- 原 ERPNext 目录 `/Users/zhanggengyu/Documents/ChatGPT/AI智能订货/` 仅读取环境说明和部署文件；只读查看现有容器中的版本和 DocType JSON 定义，未执行初始化、数据库查询、业务写入或修改部署。
- 实际：ERPNext 镜像 `frappe/erpnext:v16.34.1`，Frappe 源文件版本 `16.33.0`，入口 `http://127.0.0.1:8080/` HTTP 200。
- 系统默认 Python 为 3.11.0b2，不作为项目环境；使用 Python **3.12.14** 建立本项目 `.venv`。Node **24.22.1** / pnpm **11.25.0**。当前 shell 没有全局 node/npm，验证使用 Codex 随附运行环境。
- 新 Agent 自己的 MongoDB：`mongo:7.0.16`，`127.0.0.1:27018`，Compose 项目 `supply-chain-agent-phase1`，独立卷 `supply-chain-agent-phase1_agent_mongo`。与 ERPNext 容器、数据库无关。
- `requirements.txt` 固定直接依赖，`requirements.lock.txt` 固定本次全部传递依赖（含开发、Langfuse）；`frontend/pnpm-lock.yaml` 从原 package-lock 导入。验证平台为 macOS ARM64；其他系统尚未实测。

## 启动原项目的发现与修复

1. 原 `requirements.txt` 只写下限，FastMCP 自动选到 4.x 并发生解析回溯。收紧为 FastMCP **2.14.7**，DeepAgents **0.7.32**，其余依赖按实际安装固定。`pip check` 通过。
2. 在 `/tmp` 导出不变的基线并尝试创建原主 Agent：缺少模型 Key，初始化直接失败。未用虚构 Key 发起模型请求，也没有运行原 Java ERP 业务验收脚本。
3. **Planning**：实查安装版本 `create_deep_agent` 没有默认注册 TodoListMiddleware；主 Agent 显式注册。测试真实图中 `write_todos` 创建及更新为 completed，SSE 输出真实 todos 状态。
4. **HITL**：前端发送 resume_data，原后端只接收 resume。现在规范为 resume_data，兼容旧 resume；限制为 approve/reject 或补充信息；恢复前核对检查点中的待审批动作及数量，重复恢复返回 409，并在执行锁内再次核对。多独立 interrupt 暂返回 409，当前 UI 支持单 interrupt 的批量动作，全批批准/全批拒绝。
5. **前端审批/SSE**：修复事件跨网络数据块丢失、读取不存在的 event.data、批量审批只提交一个决定、服务端 error 事件未展示。对完整 AIMessage 工具调用补充 tool_start。缺少模型配置现在返回明确的 503，工作台展示中文原因。窄面板隐藏固定宽度历史侧栏，避免挤压聊天及错误信息。
6. **图执行步数**：原 API config 使用 LangGraph 默认 25 步，多中间件、多工具流程可提前触发 recursion limit。配置为 1000，保留模型 50 次和工具 30 次运行限制。
7. **工具安全**：MCP 只注册 5 个只读工具。原 Java ERP 工具不注册，旧 HTTP 客户端所有业务请求直接拒绝。主 Agent、采购子 Agent 及显式覆盖的 general-purpose 子 Agent 共享白名单和执行时阻断；未知工具、写工具、命令执行、下载与安装均被阻止。审批不是业务授权，不解锁写接口。
8. **执行隔离**：移除主链路 Docker 失败后 LocalShell 自动降级。阶段一无条件采用 StateBackend 虚拟文件（写入图状态），不提供宿主机 Shell；不启动沙箱预热。历史 Docker 实现保留但未启用，未声称其已经过安全验收。
9. **MCP 连接**：本机实测默认 localhost HTTP 客户端连接阻塞；切换为 127.0.0.1，显式不走系统/环境代理，增加连接及发现总超时后，实际发现 5 个工具。未把原因武断归为某个代理配置。
10. **项目兼容**：修复旧测试文件的装饰器被 pytest 当作测试收集。环境变量加载不再覆盖调用者环境。Mongo 检查点使用项目数据库名称。CORS 限定本机前端来源，服务仅监听 loopback。

## ERPNext API 契约与权限

调用链：Agent → LangChain MCP Adapter → FastMCP Tool → ERPNextAdapter → ERPNextClient → Frappe REST API。

- Client 仅提供固定 DocType 的 GET；没有 POST/PUT/PATCH/DELETE 业务方法，也不提供任意业务方法或数据库入口。
- 配置必须同时提供 base_url、API Key/Secret、预期 API 用户、公司全名和 Warehouse.name 白名单。拒绝 Administrator/Guest，先 GET `frappe.auth.get_logged_user` 校验实际身份。除了本机开发地址外要求 HTTPS，禁止认证重定向。
- 401/403/404/429、其他 HTTP 错误、ERP exception、非 JSON、超时、网络异常及非法文档均返回清晰错误类型；不返回 ERP 堆栈和认证信息。MCP 对外返回经过清理的错误码及 HTTP 状态，掩盖未预期的内部异常详情。
- Supplier/Item 是共享主数据，无顶层公司字段；以固定 Frappe API 用户权限为准，不能虚构 company 过滤。需要跨公司共享主数据隔离时，须先配置 Frappe 用户权限并验证。
- Warehouse 按 company + Warehouse.name 白名单；Bin 在此本地版本有 company 字段，按 company + warehouse 过滤，并先验证仓库所属公司。响应再次检查公司和仓库范围。
- Purchase Order 当前为**表头列表**，按公司和 Frappe 用户权限过滤；未读取/校验订单行仓库，不声称仓库级采购订单隔离。严格仓库级采购权限需要 ERP 侧用户权限与后续订单行适配。
- 查询字段使用 Supplier.name/supplier_name、Item.item_code、Warehouse.name/company、Bin.actual_qty/projected_qty、Purchase Order.name/status/docstatus 等真实字段。业务状态 status 为字符串；docstatus 是 Frappe 的 0/1/2 文档提交状态，两者不混用。
- 分页输入 limit 1～100 / offset，服务请求多一条决定 has_more；无数据返回空数组。未获取数据不能视为全量或不存在。
- 当前是本机单服务身份开发环境：聊天 user_id 用于会话隔离，**不是已验证的登录身份**；所有会话共享同一个最小权限 ERP API 用户。尚无面向外部用户的登录认证和逐人 ERP 授权映射，不应对外网开放。

## 能力状态

| 能力 | 本次验证 | 边界 |
|---|---|---|
| 主 Agent / 采购子 Agent / Tool Calling | 真实图 + 脚本模型通过 | 未调用真实模型 |
| Planning | 真实 write_todos 创建和更新；SSE todo_update | 非前端标签模拟 |
| Review | 沿用混合路由与 Rubric；原回归通过；主链路模拟 grader 输出 satisfied | 未做真实模型评分验收 |
| Skills 按需加载 | 原渐进披露回归通过；主链路只加载新增 ERPNext Skill | 原 Java ERP Skills 保留但不激活；不执行脚本、不安装 Skill |
| HITL | 真实 LangGraph + FastAPI + SSE 批准/拒绝/重复恢复验证 | 测试工具仅改变本地测试列表，无 ERP 写入 |
| 检查点/记忆 | 真实 MongoDB 两次连接间恢复中断；Store 读回通过 | 测试使用新建的临时 Agent DB，结束后清理 |
| 会话历史 | 实际 HTTP 历史接口 200；沿用 Motor Mongo 存储 | 无真实模型对话归档验收 |
| ERPNext 5 类只读查询 | httpx MockTransport + MCP 进程内往返通过；真实 MCP 网络发现通过 | **未完成 ERP 认证只读联调** |
| Web 工作台 | 生产构建/TypeScript 通过，页面 HTTP 200，浏览器验证入口和缺 Key 提示 | 缺模型与 ERP 凭据，不能宣称已可进行真实业务问答 |
| Langfuse | 元数据回调、父子轨迹、工具错误及脱敏单测通过 | smoke 报 configuration/auth unavailable；**没有真实轨迹入库证据** |

## 验证结果与复跑

默认回归：**139 passed、2 skipped、17 subtests passed**。2 个 skip 分别是真实 ERP API 联调、需显式开启的真实 Agent Mongo 集成。单独开启真实 Mongo 后：**1 passed**。前端 SSE 测试 **2 passed**，生产构建通过。

```bash
# 默认单元 + 模拟 ERP + 复用上游非外部依赖回归
./scripts/check.sh

# 仅看测试分类
.venv/bin/python -m pytest tests -m unit -q
.venv/bin/python -m pytest tests -m mock_erp -q

# 真实 Agent Mongo（与 ERP DB 无关；创建并清理随机临时测试库）
RUN_AGENT_MONGO_TEST=1 .venv/bin/python -m pytest tests/test_mongo_persistence.py -q

# 真实 ERP：只有配置了专用只读凭据后显式开启
RUN_ERPNEXT_INTEGRATION=1 .venv/bin/python -m pytest tests/test_live_erpnext.py -q

# Langfuse 配置后先做合成轨迹；该脚本不调用真实模型和 ERP
.venv/bin/python -m evals.langfuse_smoke
```

历史 `src/test/test_all_tools.py`、`evals/agent_live.py` 等可能访问旧 Java ERP，阶段一不运行。上游历史 Langfuse 报告不属于本次 ERPNext 验收。

## 阶段二待办

1. 用户在本项目 .env 配置模型 Key 和模型名；不需要在聊天发送密钥。
2. 由用户在现有 ERPNext 中准备最小权限**专用只读用户**，提供该用户 API Key/Secret、用户名称、公司全名和允许的仓库 name。由用户完成创建和授权，本阶段不生成管理员密钥。
3. 开启真实只读集成测试，对比真实字段、权限、公司/仓库、分页和空结果；用真实模型完成查询→计划→委派→审查→SSE→历史回放。
4. 配置 Langfuse host/public/secret/hash key，开启 tracing；验证合成轨迹已入库，再验证真实模型/工具/执行轨迹，保存脱敏证据。
5. 若需要多用户，先增加登录验证与 ERP 身份/权限映射、会话/恢复/历史接口鉴权，不能信任客户端 user_id。
6. 采购业务闭环另立阶段：定义 Purchase Order 草稿数据契约（供应商/公司/货币/日期/items.item_code/qty/uom/rate/warehouse），业务规则校验、独立权限检查、不可篡改审批记录、幂等键与失败恢复；先做受控草稿，再分别评审提交/取消权限与测试。写操作必须通过 ERP API，不改数据库。
7. 如需执行图表/脚本，先单独验证隔离、网络访问、凭据隔离、资源上限及故障关闭；不能恢复 LocalShell 静默降级。

## 参考依据

- Frappe REST API：https://docs.frappe.io/framework/user/en/api/rest
- LangChain HITL：https://docs.langchain.com/oss/python/langchain/human-in-the-loop
- Planning 行为以本工程已安装的 DeepAgents 0.7.32 源代码和真实图测试为准。
- pnpm 11 构建白名单配置：https://pnpm.io/blog/releases/11.0
