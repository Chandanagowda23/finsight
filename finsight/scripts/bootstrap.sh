#!/usr/bin/env bash
# FinSight one-command local bootstrap (no Docker required for demo mode)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "◇ FinSight bootstrap"
echo "  root: $ROOT"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "  created .env from .env.example"
fi

python3.11 -m venv .venv 2>/dev/null || python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -e .

export LLM_PROVIDER="${LLM_PROVIDER:-mock}"
export LIGHTWEIGHT_MODE="${LIGHTWEIGHT_MODE:-true}"
export QDRANT_IN_MEMORY="${QDRANT_IN_MEMORY:-true}"
export USE_SQLITE="${USE_SQLITE:-true}"
export PYTHONPATH="$ROOT"

echo "  ingesting knowledge base…"
python -m retrieval.ingest --reset

echo "  running unit smoke tests…"
pytest -q tests/unit --tb=line || true

echo ""
echo "✅ Bootstrap complete"
echo ""
echo "Start API:       uvicorn api.main:app --reload --port 8000"
echo "Customer UI:     streamlit run frontend/customer_app.py --server.port 8501"
echo "Staff console:   streamlit run frontend/staff_console.py --server.port 8502"
echo ""
echo "Demo logins:"
echo "  customer / demo1234"
echo "  staff    / staff1234"
echo ""
echo "Docker (full stack): docker compose up --build"
