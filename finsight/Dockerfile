FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY api ./api
COPY agents ./agents
COPY guardrails ./guardrails
COPY retrieval ./retrieval
COPY tools ./tools
COPY data ./data
COPY eval ./eval
COPY observability ./observability
COPY frontend ./frontend
COPY scripts ./scripts

RUN pip install --no-cache-dir -e . \
    && python -m spacy download en_core_web_sm || true

ENV PYTHONPATH=/app
ENV LIGHTWEIGHT_MODE=true
ENV LLM_PROVIDER=mock

EXPOSE 8000 8501 8502

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
