#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/runtime-env.sh
.venv/bin/python -m pip check
.venv/bin/python -m pytest tests \
  src/test/test_progressive_skills.py src/test/test_chat_interrupts.py \
  src/test/test_observability.py src/test/test_hybrid_review.py \
  src/test/test_memory_layer.py src/test/test_jev_router.py \
  src/test/test_sandbox_lifecycle.py -q
(cd frontend && pnpm test && pnpm build --webpack)
