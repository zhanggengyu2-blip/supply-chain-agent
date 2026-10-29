#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/runtime-env.sh
case "${1:-}" in
  api) exec .venv/bin/python -m uvicorn src.api_view.web_main:app --host 127.0.0.1 --port 8000 ;;
  mcp) exec .venv/bin/python -m src.mcp_server.server_main ;;
  web) cd frontend; exec pnpm dev --hostname 127.0.0.1 --port 3000 ;;
  *) echo "Usage: ./scripts/start.sh {api|mcp|web}"; exit 2 ;;
esac
