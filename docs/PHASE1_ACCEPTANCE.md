# 阶段一真实环境验收（收尾）

日期：2026-10-30（Asia/Shanghai）。总体结论：**尚未通过完整真实 ERP 业务验收**。
本轮仅修复、验证阶段一能力；ERP 写工具继续禁用，未修改 ERPNext 原目录、部署、数据库或业务数据。

## 当前配置

- 已配置并实测：DeepSeek 官方 Key，地址 `https://api.deepseek.com`，模型 `deepseek-flash`；账户模型列表 API HTTP 200。
- 已配置并实测：用户提供的 Langfuse 美国区项目，地址 `https://us.cloud.langfuse.com`，追踪开关已开启。
- 已在本地生成 `ERP_TRACE_HASH_KEY`，不上传原始用户/会话标识。`.env` 保持 Git 忽略且仅当前用户可读写；本记录不包含任何密钥。
- **仍缺少**：`ERPNEXT_API_KEY`、`ERPNEXT_API_SECRET`、`ERPNEXT_API_USER`、`ERPNEXT_COMPANY`、`ERPNEXT_WAREHOUSES`。用户已确认尚未准备专用只读用户。
- 本机 Next.js、FastAPI、MCP、Agent MongoDB 均已启动；ERPNext 公共入口 HTTP 200 不代表认证或业务查询通过。

准备方法见 [只读账户与 Langfuse 配置说明](CONFIGURE_READONLY_AND_LANGFUSE.md)。当前只需准备 ERPNext 一节，Langfuse 无需重复创建。

## 已验证

| 检查 | 类型 | 结果与证据 |
|---|---|---|
| DeepSeek 普通调用 | 真实模型 | 正确回复验收标记 |
| Tool Calling 与结果使用 | 真实模型 + 本地无副作用工具 | 真实模型产生工具调用，执行后正确使用工具返回值；非 ERP 业务查询 |
| Token 用量 | 真实接口 | 首次未开启追踪时 464 Token；开启追踪后重跑为 463 Token，均来自接口 usage |
| Langfuse 入库读回 | 真实服务 | 追踪 `a04aa73372bba4a9aa4ff0c0771e4852`：5 条 Observation、3 次 Generation、1 次本地探针工具调用；读回 Token 合计 463，与接口一致；无业务 input/output 正文 |
| Review 评分器 | 真实模型 | 修复后通过 ToolStrategy 返回结构化评分，verdict=satisfied；见 closeout-review.json |
| MCP 注册与本地网络连接 | 真实服务 | 实际发现 5 个 ERPNext 只读工具；没有注册写工具 |
| 工作台调查 | 真实模型 + 主/子 Agent + MCP + Review | 已在页面执行计划、委派 procurement-order、加载 Skill、单次调用采购查询并返回 configuration_required；真实 Review=satisfied，表格渲染正确。**这是失败路径验证，不是 ERP 数据验收** |
| 工作台任务追踪 | 真实 Langfuse 读回 | 同一会话读回 126 条 Observation、9 次 Generation、6 次工具调用、58,028 Token；包含 tool.erpnext_purchase_orders，所有 Generation 都有用量，无业务正文 |
| MongoDB 检查点/记忆 | 真实 Agent MongoDB | 独立测试 1 passed；不接触 ERP 数据库 |
| 自动化回归 | 单元/模拟数据/脚本模型 | 150 passed、2 skipped、17 subtests passed；2 个 skip 为需显式开启的真实 ERP 与 Agent Mongo 集成。前端 2 项 SSE 测试、类型检查和生产构建通过 |

示例真实追踪：[在 Langfuse 项目中查看](https://us.cloud.langfuse.com/project/cmvub6405005sad0mm6rjufnw/traces/a04aa73372bba4a9aa4ff0c0771e4852)。该追踪是本地安全探针，不能替代 ERP 业务查询轨迹。

最终工作台任务：[真实模型/子 Agent/MCP/Review 追踪](https://us.cloud.langfuse.com/project/cmvub6405005sad0mm6rjufnw/traces/85f6b94e0abb827d0b79b8d9fe73fbd9)。该任务在 API 配置校验处停止，未取得真实 ERP 数据。

## 本轮发现并修复的问题

1. **流式格式丢失**：原 SSE 代码通过 `content.strip()` 过滤纯空白片段，导致真实模型输出的空格、换行被丢弃，标题和表格粘连。改为原样保留非空字符串，并在主/子 Agent 输出切换时分隔 Markdown 文档、隐藏评分器内部消息；增加 SSE、归档内容和子 Agent 边界测试。
2. **表格渲染缺失**：原 react-markdown 没有启用 GFM 表格扩展。增加固定版本 `remark-gfm@4.0.1`，同步 pnpm 和 npm 锁文件；浏览器已确认存在真实 table/row/cell 结构。
3. **Review 真实模型不兼容**：`langchain-deepseek` 的模型能力元数据声称原生结构化输出可用，LangChain 自动选择 ProviderStrategy；DeepAgents Rubric 随之发送 json_schema response_format，实际 DeepSeek 接口返回 400。对非思考评分模型复制并修正能力元数据，改为 ToolStrategy，保留真实结构化评分和单次审查机制，没有关闭 Review。独立真实模型评分已通过。
4. **历史记录重复刷新**：原页面 effect 依赖每次渲染变化的 history 对象，且提前返回前没有复位 wasStreaming，任务结束后持续轮询历史。改用稳定的 refresh 函数依赖，并先更新流状态，只在完成边沿刷新。
5. **测试污染真实追踪**：用户开启 Langfuse 后，部分离线测试会继承真实开关并尝试导出脚本模型轨迹。默认 pytest 用例统一关闭真实导出；回调单测可使用各自假客户端。真实追踪由显式验收命令运行，避免模拟与真实结果混在一起。

上述第 3 项的依赖传播链为：第三方模型能力元数据 → LangChain 输出策略自动选择 → DeepAgents 评分器请求格式 → 真实接口拒绝 → Review grader_error。修复针对能力声明，不改变 ERP 权限或业务执行范围。

## ERP 真实验收仍未完成

Supplier、Item、Warehouse、Bin、Purchase Order 五类真实认证查询均未测试；因此：

- 未验证专用 API 用户身份、实际读取范围和有效写权限。
- 未验证真实公司/仓库过滤、真实空结果、样本文档权限及数据准确性。
- 不能宣称专用账户已经没有写权限；目前只能确认 Agent/MCP 没有业务写入口。
- 不能把配置校验阶段返回 configuration_required 的工具调用称为访问了 ERPNext 数据。

新增验收脚本会先使用 GET `frappe.client.has_permission` 审计相关 DocType 的有效写权限，发现授权即判失败。不会通过创建、调整库存、提交、取消等写操作测试权限。随后才读取五类数据、核验样本文档权限，并对比直接 REST 和实际 MCP 的返回值。审计范围明确列在结果中，不将样本检查夸大为全账户所有文档的权限证明。

当前 Purchase Order 适配只返回表头，公司与 Frappe 用户权限生效；订单行和严格仓库级采购隔离未实现，也不在此次验收中伪称通过。

## 证据与复跑

- `docs/evidence/closeout-live.json`：真实模型、未配置 ERP 的明确阻塞结果。
- `docs/evidence/closeout-traced-live.json`：真实模型/本地工具与 Langfuse 463 Token 对账。
- `docs/evidence/closeout-review.json`：真实结构化 Review 评分结果。
- `docs/evidence/closeout-workbench.json` / `closeout-workbench.jpg`：实际页面调查记录。
- `docs/evidence/closeout-check.txt` / `closeout-mongo.txt`：自动化与真实 Agent Mongo 验证。

```bash
# 离线自动化和构建，不上报脚本模型轨迹
./scripts/check.sh

# 已授权、已配置的真实模型和追踪（会产生少量真实模型用量）
.venv/bin/python -m evals.phase1_acceptance --model --erp \
  --output docs/evidence/closeout-traced-live.json

# 配置好 ERP 后，先做身份/权限与五类只读查询验证，不调用模型
.venv/bin/python -m evals.phase1_acceptance --erp \
  --output docs/evidence/closeout-erp.json

# 指定真实任务 trace ID 做独立 Langfuse 读回核对
.venv/bin/python -m evals.phase1_acceptance --trace-id 这里填写真实TraceID \
  --output docs/evidence/closeout-trace-verification.json
```

历史的 `evals/agent_live.py` 等 Java ERP 验收脚本不运行。禁止通过管理员凭据或 ERP 数据库绕过 API 认证。

## 收尾所需条件与后续技术阻塞

1. 用户完成专用非管理员 ERP 只读账户、角色和公司/仓库授权，将上述 5 项配置填入本地 `.env`。不需要在聊天发送凭据。
2. 重启 Agent API/MCP，完成真实只读权限审计、五类数据比对和含 ERP 结果的工作台调查，再读回同一真实任务的 Langfuse 模型/工具/Token 轨迹。
3. 保留当前本机访问边界。现有 Web API 尚无生产登录认证和逐人 ERP 身份映射，客户端 user_id 不是可信登录身份。
4. 本轮依赖审计发现 20 条安全公告（非 20 个不同包）：5 critical、9 high、5 moderate、1 low，涉及上游固定的 Next.js 16.2.12 及其 PostCSS、Sharp 等依赖。详见 `closeout-dependency-audit.json`。本轮未执行利用测试或无审查的批量升级；公开部署前需单独修补、更新锁文件并回归。此项不应被“构建通过”掩盖。
5. 这次简短调查仍使用 58,028 Token（9 次模型调用）。后续需基于已核实的轨迹优化基础提示、上下文和子 Agent/评分开销；该数值是用量，不等于费用，未凭空计算成本。
6. 本轮不进入采购写入、BOM、MRP 或生产开发。真实 ERP/权限未验收之前，不启用任何写入口。
