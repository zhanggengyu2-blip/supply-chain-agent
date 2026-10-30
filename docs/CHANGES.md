# 阶段一文件修改清单

基于 08ded02cc14228fa36d9b5706caa7bc8144355f6。

运行环境中的 `.venv/`、`node_modules/`、`.next/`、`.pnpm-store/` 和含真实凭据的本地 `.env` 不纳入 Git。

- `.env.example`
- `.gitignore`
- `.python-version`
- `README.md`
- `THIRD_PARTY_NOTICES.md`
- `compose.yaml`
- `docs/CHANGES.md`
- `docs/PHASE1.md`
- `docs/START_PHASE1.md`
- `docs/evidence/check.txt`
- `docs/evidence/mongo.txt`
- `docs/evidence/workbench-config-required.jpg`
- `frontend/.node-version`
- `frontend/package.json`
- `frontend/pnpm-lock.yaml`
- `frontend/pnpm-workspace.yaml`
- `frontend/src/app/page.tsx`
- `frontend/src/components/chat/ChatArea.tsx`
- `frontend/src/components/chat/InputBar.tsx`
- `frontend/src/components/chat/WelcomeScreen.tsx`
- `frontend/src/components/interrupt/ApprovalCard.tsx`
- `frontend/src/components/sidebar/Sidebar.tsx`
- `frontend/src/hooks/useChat.ts`
- `frontend/src/lib/api.ts`
- `frontend/src/lib/sse-parser.ts`
- `frontend/src/lib/types.ts`
- `frontend/tests/sse-parser.test.cjs`
- `pytest.ini`
- `requirements-dev.txt`
- `requirements.lock.txt`
- `requirements.txt`
- `scripts/check.sh`
- `scripts/runtime-env.sh`
- `scripts/start.sh`
- `src/agent/config.py`
- `src/agent/env_utils.py`
- `src/agent/main_agent.py`
- `src/agent/memory/prompts.py`
- `src/agent/observability.py`
- `src/agent/phase1_guide.md`
- `src/agent/schema.py`
- `src/agent/subagents/configs/procurement_analyst.yaml`
- `src/agent/subagents/configs/procurement_order.yaml`
- `src/agent/tool_policy.py`
- `src/agent/tools/mcp_client.py`
- `src/api_view/agent_loader.py`
- `src/api_view/api/chat.py`
- `src/api_view/web_main.py`
- `src/mcp_server/erpnext/__init__.py`
- `src/mcp_server/erpnext/adapter.py`
- `src/mcp_server/erpnext/client.py`
- `src/mcp_server/erpnext/models.py`
- `src/mcp_server/http_base.py`
- `src/mcp_server/server_config.py`
- `src/mcp_server/server_main.py`
- `src/mcp_server/tools/erpnext_tools.py`
- `src/skills/erpnext/read-procurement/SKILL.md`
- `src/test/test_memory_layer.py`
- `tests/test_erpnext.py`
- `tests/test_live_erpnext.py`
- `tests/test_mongo_persistence.py`
- `tests/test_runtime.py`

## 真实环境收尾追加

保留只读边界，修复真实模型与 UI 兼容问题，新增验收及凭据准备说明。当前 ERP 认证验收仍阻塞。

- `README.md`
- `conftest.py`
- `docs/CONFIGURE_READONLY_AND_LANGFUSE.md`
- `docs/PHASE1.md`
- `docs/PHASE1_ACCEPTANCE.md`
- `docs/START_PHASE1.md`
- `docs/evidence/closeout-check.txt`
- `docs/evidence/closeout-dependency-audit.json`
- `docs/evidence/closeout-live.json`
- `docs/evidence/closeout-mongo.txt`
- `docs/evidence/closeout-review.json`
- `docs/evidence/closeout-services.json`
- `docs/evidence/closeout-trace-link.json`
- `docs/evidence/closeout-traced-live.json`
- `docs/evidence/closeout-workbench.jpg`
- `docs/evidence/closeout-workbench.json`
- `evals/phase1_acceptance.py`
- `frontend/package-lock.json`
- `frontend/package.json`
- `frontend/pnpm-lock.yaml`
- `frontend/src/app/page.tsx`
- `frontend/src/components/chat/MessageBubble.tsx`
- `scripts/check.sh`
- `src/agent/config.py`
- `src/api_view/api/chat.py`
- `tests/test_model_configuration.py`
- `tests/test_phase1_acceptance.py`
- `tests/test_stream_formatting.py`


## 专用只读用户与真实 ERP 端到端验收

仅账户/角色/用户权限配置通过官方 API 修改，业务写入仍禁用。修复真实超时失败状态、待办状态契约及移动目录后的 pnpm 缓存配置；最新结论见 PHASE1_ACCEPTANCE.md。

- `scripts/configure_erpnext_reader.py`
- `tests/test_reader_configuration.py`
- `src/api_view/api/chat.py`
- `tests/test_stream_formatting.py`
- `frontend/src/hooks/useChat.ts`
- `frontend/src/lib/types.ts`
- `frontend/src/lib/todo-status.ts`
- `frontend/src/components/chat/TodoListPanel.tsx`
- `frontend/tests/todo-status.test.cjs`
- `frontend/package.json`
- `frontend/pnpm-workspace.yaml`
- `README.md`
- `docs/CONFIGURE_READONLY_AND_LANGFUSE.md`
- `docs/PHASE1.md`
- `docs/START_PHASE1.md`
- `docs/PHASE1_ACCEPTANCE.md`
- `docs/CHANGES.md`
- `docs/evidence/erpnext-reader-configuration.json`
- `docs/evidence/closeout-erp-authenticated.json`
- `docs/evidence/closeout-erp-scope.json`
- `docs/evidence/closeout-erp-pytest.txt`
- `docs/evidence/closeout-erp-workbench.json` / `.jpg`
- `docs/evidence/closeout-erp-workbench-failed.json` / `.jpg`
- `docs/evidence/closeout-todo-ui.json` / `.jpg`
- `docs/evidence/closeout-check.txt`
- `docs/evidence/closeout-mongo.txt`
