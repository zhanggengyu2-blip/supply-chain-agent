# 本地启动

工程路径：`/Users/zhanggengyu/Documents/供应链协同Agent`。

本机已安装 `.venv`、前端依赖，并在 Git 忽略的 `.env` 配齐 DeepSeek、专用 ERPNext 只读账户和 Langfuse。Agent 使用独立 MongoDB，无需更改 ERPNext 原目录。

## 直接启动

在当前工程的终端执行：

```bash
cd '/Users/zhanggengyu/Documents/供应链协同Agent'
docker compose up -d mongo
```

分别开三个终端，每个终端都先进入上面的工程目录：

```bash
./scripts/start.sh mcp
```

```bash
./scripts/start.sh api
```

```bash
./scripts/start.sh web
```

- 工作台：http://127.0.0.1:3000/
- FastAPI 文档：http://127.0.0.1:8000/docs
- 进程存活：http://127.0.0.1:8000/health （只证明 API 存活，不代表模型/ERP 已配置）
- MCP SSE：http://127.0.0.1:9000/sse （事件长连接，不是普通网页）
- Agent MongoDB：`mongodb://127.0.0.1:27018`
- 原 ERPNext：http://127.0.0.1:8080/ （本工程不启动、不重建 ERPNext）

已有同端口服务时不要重复启动。前端 dev 可热更新；生产模式为 `cd frontend && pnpm build --webpack && pnpm start --hostname 127.0.0.1`。本次交付时运行的是已验证生产构建。

## 填写配置

编辑本工程 `.env`。该文件已被 Git 忽略；不要把密钥提交到仓库或粘贴到聊天。

| 配置 | 用途 |
|---|---|
| DEEPSEEK_API_KEY、LLM_MODEL、LLM_BASE_URL | 主 Agent、Review 路由和评分模型；模型名需确认为账户实际可用 |
| ERPNEXT_BASE_URL | 默认 http://127.0.0.1:8080 |
| ERPNEXT_API_KEY / ERPNEXT_API_SECRET | 已配置的专用只读账户 token；不使用 Administrator |
| ERPNEXT_API_USER | 实际 API 用户名，用 get_logged_user 进行一致性校验 |
| ERPNEXT_COMPANY | 公司完整名称，与 ERPNext 中一致 |
| ERPNEXT_WAREHOUSES | 允许的仓库完整 name，逗号分隔 |
| MONGODB_URI / MONGODB_DB_NAME | 当前已设为本工程独立 MongoDB |
| MCP_SERVER_URL | 默认 http://127.0.0.1:9000 |
| ERP_LANGFUSE_ENABLED | 默认 false，凭据齐备后改为 true |
| LANGFUSE_BASE_URL / PUBLIC_KEY / SECRET_KEY | 分别填写 LANGFUSE_BASE_URL、LANGFUSE_PUBLIC_KEY、LANGFUSE_SECRET_KEY |
| ERP_TRACE_HASH_KEY | 已在本地生成的随机伪匿名化密钥，用来散列用户/会话标识 |

修改 `.env` 后重启 API 和 MCP。DeepSeek、Langfuse 和 ERPNext 专用只读账户已配置；五类 ERPNext 认证查询、REST/MCP 比对及有效业务写权限审计已通过。最新端到端结果见 [验收记录](PHASE1_ACCEPTANCE.md)。账户维护方法见 [配置说明](CONFIGURE_READONLY_AND_LANGFUSE.md)。
所有聊天会话共享一个固定 ERP 用户；当前 Web API 没有生产登录鉴权，只允许本机开发访问。
当前授权公司为既有演示库“梦迪恩服饰”，允许 4 个演示仓库。采购订单只读能力目前是表头查询，公司范围生效；订单行及严格仓库级采购隔离尚未实现。

## 重新安装环境

版本：Python 3.12.14、Node 24.22.1、pnpm 11.25.0、Docker Compose。优先使用正常安装的运行工具；本机缺少 node/pnpm 时启动脚本会使用 Codex 已有的随附环境，不修改全局安装。

```bash
# 新机器须先提供 Python 3.12；已有 .venv 时不需要重复创建。
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
source scripts/runtime-env.sh
(cd frontend && pnpm install --frozen-lockfile --store-dir ../.pnpm-store)
```

本机也可用现有 Python 路径创建环境：
`/Users/zhanggengyu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`。
`frontend/pnpm-workspace.yaml` 固定相对 `storeDir`，使安装、测试、启动共用工程内缓存。移动工程后需重新执行上述锁文件安装；Python 虚拟环境如因绝对路径失效则按锁文件重建。
首次新建配置时从 `.env.example` 复制，**不要覆盖已填写的 .env**。
锁文件目前在 macOS ARM64 验证；其他平台需要单独复核二进制依赖兼容性。

## 检查与关闭

```bash
./scripts/check.sh
RUN_AGENT_MONGO_TEST=1 .venv/bin/python -m pytest tests/test_mongo_persistence.py -q
```

运行前后端/MCP 的终端按 Ctrl+C 停止对应服务。

```bash
# 仅停止本工程 MongoDB，保留数据卷。
docker compose stop mongo
```

不执行原 ERPNext 的部署命令，也不删除其卷或数据库。
测试分类、未完成验证、阶段二待办见 [PHASE1.md](PHASE1.md)。
