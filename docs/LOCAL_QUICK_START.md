# 本地启动速查

只看页面时，直接执行下面的「终端 3」。要自测聊天和 ERP 查询，打开 Docker Desktop，确认现有 ERPNext 已启动，再按顺序执行下列命令。ERPNext 地址以项目 `.env` 的 `ERPNEXT_BASE_URL` 为准，本地通常是 `http://127.0.0.1:8080`。

## 启动

**终端 1 · MongoDB 和 MCP**

```bash
cd "$HOME/Documents/供应链协同Agent" && docker compose up -d mongo && ./scripts/start.sh mcp
```

**终端 2 · FastAPI 后端**

```bash
cd "$HOME/Documents/供应链协同Agent" && ./scripts/start.sh api
```

**终端 3 · 前端工作台**

```bash
cd "$HOME/Documents/供应链协同Agent" && ./scripts/start.sh web
```

三个终端保持打开。已经在运行的服务可跳过对应命令。

## 自测

1. 打开 [工作台](http://127.0.0.1:3000/)，确认页面能加载。
2. 打开 [后端健康检查](http://127.0.0.1:8000/health)，看到 JSON 表示 API 能响应。
3. 在工作台发送「查询前 5 条供应商记录，列出供应商名称」，把返回结果与 ERPNext 对照。

| 遇到的问题 | 先检查 |
| --- | --- |
| 页面能打开，发消息显示 `Failed to fetch` | 打开后端健康检查。打不开就查看终端 2，确认 FastAPI 在 `8000` 启动。 |
| 聊天能回复，但查不到 ERP 工具 | 确认 MCP 在 `9000` 启动。如果第一次发消息时 MCP 还没启动，启动 MCP 后重启 FastAPI，再发一次。 |
| 终端提示 `No such file or directory` | 复制上面的完整命令，目录名是 `供应链协同Agent`。 |

## 停止

在三个终端分别按 `Ctrl+C`。需要停止本项目的 MongoDB 时，在项目目录运行 `docker compose stop mongo`，数据卷会保留。

首次安装依赖或配置 `.env` 时，见 [完整启动说明](START_PHASE1.md)。
