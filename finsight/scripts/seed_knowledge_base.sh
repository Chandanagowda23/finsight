#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"
export LLM_PROVIDER="${LLM_PROVIDER:-mock}"
export LIGHTWEIGHT_MODE="${LIGHTWEIGHT_MODE:-true}"
export QDRANT_IN_MEMORY="${QDRANT_IN_MEMORY:-true}"
python -m retrieval.ingest --reset
