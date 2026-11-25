#!/usr/bin/env bash
# 优先使用用户正常安装的工具，找不到时再使用桌面应用内置的运行环境。
agent_runtime="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies"
if ! command -v node >/dev/null 2>&1 && [[ -x "$agent_runtime/node/bin/node" ]]; then
  export PATH="$agent_runtime/node/bin:$PATH"
fi
if ! command -v pnpm >/dev/null 2>&1 && [[ -x "$agent_runtime/bin/fallback/pnpm" ]]; then
  export PATH="$agent_runtime/bin/fallback:$PATH"
fi
