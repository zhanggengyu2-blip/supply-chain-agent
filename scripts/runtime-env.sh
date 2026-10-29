#!/usr/bin/env bash
# Use normal user-installed tools first; fall back to the desktop bundled runtime.
agent_runtime="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies"
if ! command -v node >/dev/null 2>&1 && [[ -x "$agent_runtime/node/bin/node" ]]; then
  export PATH="$agent_runtime/node/bin:$PATH"
fi
if ! command -v pnpm >/dev/null 2>&1 && [[ -x "$agent_runtime/bin/fallback/pnpm" ]]; then
  export PATH="$agent_runtime/bin/fallback:$PATH"
fi
