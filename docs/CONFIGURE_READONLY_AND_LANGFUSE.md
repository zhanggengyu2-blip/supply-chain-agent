# 准备 ERPNext 只读用户与 Langfuse 项目

DeepSeek 已在本项目配置，并完成真实调用与 Tool Calling 验证。Langfuse 美国区项目也已按你提供的凭据配置，真实模型/工具轨迹与 Token 已从服务端读回核实。`ERP_TRACE_HASH_KEY` 已在本地生成。**当前只需完成第 1 节的 ERPNext 专用只读用户准备；第 2 节保留作后续参考，无需重复创建 Langfuse 项目。**
以下两类凭据需要你在自己的系统内准备；不要把 DeepSeek Key 当作 ERP 或 Langfuse 的 Key。
只编辑当前 Agent 工程的 `.env`，不要改 ERPNext Docker 文件，不需要接触数据库。

## 1. ERPNext：建立一个只读服务身份

在 http://127.0.0.1:8080/ 登录你有权限管理用户的 ERPNext 账户。管理账户用于下面的账户配置操作；Agent 最终使用的是另外的非管理员用户。

1. 在界面搜索 `Role`（角色），新建一个专用角色，例如 `Supply Chain Agent Reader`。不要复用已有采购/库存业务角色，以免附带写权限。
2. 搜索 `Role Permission Manager`（角色权限管理）。为该角色逐一配置下列 DocType 的 **Read（读取）** 权限：
   - Supplier（供应商）
   - Item（物料）
   - Warehouse（仓库）
   - Bin（库存）
   - Purchase Order（采购订单）
3. 不授予 Write、Create、Delete、Submit、Cancel、Amend、Import、Share 等修改或授权权限。权限是角色叠加的，所以不要同时分配 `System Manager`、`Purchase User`、`Purchase Manager`、`Stock User`、`Stock Manager` 等角色。
4. 搜索 `User`（用户），新建专用非管理员账户，使用你控制的邮箱，用户类型选择 `System User`；只分配专用只读角色以及系统自动添加的基础角色。不要为 Administrator 生成给 Agent 使用的 API Key。若显示发送欢迎邮件选项，可按你自己的需要决定，本地 API 接入不依赖欢迎邮件。
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

配置后，我会先校验真实登录身份、检查相关 DocType 的有效写权限；发现写权限则验收失败，绝不通过尝试创建单据来测试。随后再验证五类只读查询和样本文档权限。

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

## 3. 填好后继续验收

告诉我“ERPNext 和 Langfuse 已在本地配置好”即可，不需要把密钥发到聊天里。我会重启当前 Agent 的 API 和 MCP 读取配置，继续完成：

- 非管理员身份与有效权限审计；公司、仓库范围检查。
- 五类工具真实只读查询，并比较直接 REST 与 MCP 返回值。
- 工作台真实采购调查、主/子 Agent、Planning、Review、SSE 与历史回放。
- Langfuse 入库读回，核实真实模型、工具轨迹与 Token 用量。

在此之前，整体阶段一验收仍为未通过；已有真实模型验证与模拟测试分别保留。
