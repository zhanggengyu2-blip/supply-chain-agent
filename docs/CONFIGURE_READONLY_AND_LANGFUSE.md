# 准备 ERPNext 只读用户与 Langfuse 项目

本机已经完成三类凭据配置：DeepSeek 模型、ERPNext 专用只读用户、Langfuse 美国区项目。必要配置无缺失；密钥仅保存在本项目 `.env`（权限 0600、Git 忽略），不在文档中记录。

ERPNext 专用用户为 `supply-chain-agent-phase1@example.invalid`，角色为 `Supply Chain Agent Phase1 Reader`。这是本地 API 服务身份，不发送欢迎邮件、不用于收邮件。公司为已有演示数据的“梦迪恩服饰”，仓库为演示-杭州总仓、上海门店仓、次品仓、生产在制仓（完整 name 带 ` - Mundane` 后缀）。这不是目标智能照明企业的正式业务库。

账户通过现有部署文档中的正常管理登录、CSRF 校验及 Frappe 官方 API 配置；没有创建或使用管理员 API 密钥，没有直接写数据库或修改 ERPNext 工程文件。管理会话在配置完成后退出，Agent 只使用专用用户自己的 token。

以下为后续维护与其他环境的准备方法，本机无需重复创建账户或 Langfuse 项目。

## 1. ERPNext：建立一个只读服务身份

在 http://127.0.0.1:8080/ 登录你有权限管理用户的 ERPNext 账户。管理账户用于下面的账户配置操作；Agent 最终使用的是另外的非管理员用户。

1. 在界面搜索 `Role`（角色），新建一个专用角色，例如 `Supply Chain Agent Reader`，关闭 Desk Access（桌面访问）。不要复用已有采购/库存业务角色，以免附带写权限。
2. 搜索 `Role Permission Manager`（角色权限管理）。为该角色逐一配置下列 DocType 的 **Read（读取）** 权限：
   - Supplier（供应商）
   - Item（物料）
   - Warehouse（仓库）
   - Bin（库存）
   - Purchase Order（采购订单）
3. 不授予 Write、Create、Delete、Submit、Cancel、Amend、Import、Share 等修改或授权权限。权限是角色叠加的，所以不要同时分配 `System Manager`、`Purchase User`、`Purchase Manager`、`Stock User`、`Stock Manager` 等角色。
4. 搜索 `User`（用户），新建专用非管理员账户，使用你控制的邮箱，用户类型选择 `Website User`（本阶段只用 API、不需要 Desk 工作台）；只分配上述无 Desk Access 的专用只读角色。**本机 System User 会自动继承 Desk User，而既有 Desk User 在 Item 上带 Share 权限**；不要为了接入 Agent 修改共享角色。不要为 Administrator 生成给 Agent 使用的 API Key。若显示发送欢迎邮件选项，可按你自己的需要决定，本地 API 接入不依赖欢迎邮件。
5. 搜索 `User Permission`（用户权限），为这个用户指定允许的 **Company（公司）**。按需要逐条增加允许的 **Warehouse（仓库）**。记录 ERPNext 中完整的公司名称与仓库 **name**，不要只复制仓库显示简称。
6. 打开刚创建的那个用户，在 `API Access`（API 访问）中执行 `Generate Keys`（生成密钥），保存 API Key 和 API Secret。界面可能将这一区域放在用户设置中；Secret 应立即保存在本地密码管理器或本项目 `.env`。
7. 把下面五个值填入 **本项目已有的 `.env`**，不要覆盖其他已配置项：

```dotenv
ERPNEXT_API_USER=这里填专用用户的实际用户名或邮箱
ERPNEXT_API_KEY=这里填该用户自己的API_Key
ERPNEXT_API_SECRET=这里填该用户自己的API_Secret
ERPNEXT_COMPANY=这里填公司完整名称
ERPNEXT_WAREHOUSES=这里填仓库完整name,多个仓库用逗号分隔
```

本机 ERPNext 地址 `ERPNEXT_BASE_URL=http://127.0.0.1:8080` 已设置，无需重建部署。
供应商和物料是共享主数据，它们没有可直接照搬的顶层公司字段；实际隔离范围以 Frappe 权限测试为准。
采购订单当前仅查询表头；不能因设置了仓库白名单，就认为订单行已完成仓库级隔离。

本机已先校验专用身份，并完成 9 类 DocType 和五类样本文档共 112 项有效权限检查，Write/Create/Delete/Submit/Cancel/Amend/Import/Share 均拒绝；五类直接 REST 与 MCP 返回值一致。审计不代表全站所有 DocType 的权限证明，也没有尝试真实写请求。

官方依据：[角色权限](https://docs.frappe.io/erpnext/permissions)、[Token 认证](https://docs.frappe.io/framework/user/en/guides/integration/how_to_set_up_token_based_auth)。

## 2. Langfuse：准备一个项目

你可以使用已有 Langfuse 服务，或者自行注册 [Langfuse](https://langfuse.com/)。本阶段不要求你在本机另行部署一套服务。

1. 登录后创建一个专用于本 Agent 的项目，例如 `Supply Chain Agent Phase 1`。
2. 进入项目的 `Settings → API Keys`（设置 → API 密钥），创建项目级凭据。凭据需要允许追踪写入和 Observation（执行记录）读回，才能核实轨迹确实入库；不要使用组织级管理凭据。
3. 将项目的 Public Key、Secret Key，以及该服务/区域对应的 **Base URL** 填入 `.env`。地址必须与项目所在区域一致，不要把项目控制台的完整页面地址填进去。
4. 配置齐备后开启开关：

```dotenv
LANGFUSE_BASE_URL=这里填该项目所在服务的基础地址
LANGFUSE_PUBLIC_KEY=这里填项目Public_Key
LANGFUSE_SECRET_KEY=这里填项目Secret_Key
ERP_LANGFUSE_ENABLED=true
```

`ERP_TRACE_HASH_KEY` 已安全生成，保留现有值即可。它用于将用户/会话标识散列化，不是 Langfuse 登录凭据。

本项目默认只上报模型、工具、执行状态和 Token 等元数据，不上传 ERP 业务请求正文或查询结果。
只有从 Langfuse API 读回真实 Trace、Generation、Tool 及 Token 用量后，才会标记追踪验收通过。SDK 初始化成功或本地回调测试通过均不足以证明入库。

官方依据：[项目 API Key](https://langfuse.com/faq/all/where-are-langfuse-api-keys)、[API 与区域地址](https://langfuse.com/docs/api-and-data-platform/features/public-api)。

## 3. 本机账户维护与复核

一次性配置脚本为 `scripts/configure_erpnext_reader.py`，不会注册为 Agent/MCP 工具。默认只生成检查计划；显式 `--apply` 才修改专用账户、角色和用户权限。脚本不会修改业务 DocType 数据，不为 Administrator 生成密钥，失败时禁用专用账户；已有可用凭据不自动轮换。

本机已经执行成功，无需反复运行 `--apply`。后续更换公司或仓库前先确认目标范围及现有用户权限，不直接沿用演示清单。凭据失效时从该专用用户重新生成并更新本地配置，然后重启 API/MCP。

```bash
# 不调用模型、不写业务数据；认证后审计权限并比较五类真实 REST/MCP 查询
.venv/bin/python -m evals.phase1_acceptance --erp \
  --output docs/evidence/closeout-erp-authenticated.json
RUN_ERPNEXT_INTEGRATION=1 .venv/bin/python -m pytest tests/test_live_erpnext.py -q
```

完整验收状态、真实 Trace 和仍未验证的边界见 [阶段一验收记录](PHASE1_ACCEPTANCE.md)。全部 ERP 业务写工具继续禁用。
