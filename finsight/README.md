# FinSight

**Multi-Agent RAG Platform for Banking** — customer-facing assistant + internal staff co-pilot, unified under one agent platform.

> Production-oriented reference design · 100% free/open-source stack · Zero real PII · Zero paid APIs required

FinSight is not a toy chatbot. Every answer is retrieval-grounded with citations, every irreversible action requires a human, and every request is audited. Accuracy is CI-gated — not eyeballed once.

---

## What it does

| Audience | Agents |
|----------|--------|
| **Customer** | Knowledge (T&Cs/fees/FAQs + citations) · Account (balances/txns/cards via mock core API) · Dispute Intake (draft → human approve) · Eligibility Pre-Check (informational only) |
| **Staff** | Compliance Lookup (AML/KYC/SOP) · Fraud/Risk Triage · Regulatory Search · Service Co-Pilot (suggested replies; agent stays in control) |

**Non-negotiables:** no claim without evidence · no irreversible action without human confirmation · abstention is a first-class success when confidence is low.

---

## Quick start (no Docker)

```bash
cd finsight
bash scripts/bootstrap.sh

# Terminal 1 — API
source .venv/bin/activate
export PYTHONPATH=.
uvicorn api.main:app --reload --port 8000

# Terminal 2 — Customer UI
streamlit run frontend/customer_app.py --server.port 8501

# Terminal 3 — Staff console
streamlit run frontend/staff_console.py --server.port 8502
```

**Demo logins**

| Role | User | Password |
|------|------|----------|
| Customer | `customer` | `demo1234` |
| Staff | `staff` | `staff1234` |

OpenAPI docs: http://localhost:8000/docs

### Docker (full stack)

```bash
cd finsight
cp .env.example .env
docker compose up --build
```

Brings up Qdrant, Postgres, API (`:8000`), customer UI (`:8501`), staff UI (`:8502`).

---

## Architecture (flow)

```
Customer / Staff
       │
       ▼
 API Gateway (FastAPI: JWT, rate limit, session)
       │
       ▼
 Input Guardrails (PII redaction · injection filter · scope)
       │
       ▼
 LangGraph Orchestrator (intent → route)
       │
       ├── Knowledge / RAG ──► Hybrid Retriever (BM25 + dense + rerank) → Qdrant
       ├── Account Agent ────► Tool Registry → mock core-banking API
       ├── Dispute / Eligibility / Compliance / Fraud / Co-Pilot
       │
       ▼
 Output Guardrails (groundedness · compliance · PII leak)
       │
       ├── low confidence / irreversible ──► HITL queue (human approve)
       └── pass ──► user
       │
       ▼
 Postgres audit log (append-only) · Langfuse traces (optional)
```

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the full design rationale.

---

## Accuracy pipeline

1. Query rewrite from conversation context  
2. Hybrid retrieval: BM25(top20) ∪ dense(top20) → RRF merge → cross-encoder rerank → top5  
3. Confidence gate → abstain + handoff if below threshold  
4. Generate with forced `[chunk_id]` citations  
5. Groundedness verifier (separate LLM/NLI pass) → regenerate once or abstain  
6. Compliance re-check against `guardrails/policies/compliance_rules.yaml`  
7. Full audit trail written

---

## Tech stack (all free / open-source)

| Layer | Choice |
|-------|--------|
| Orchestration | LangGraph |
| LLM | Pluggable: `mock` (CI/demo) · Ollama · Groq free tier · Together free tier |
| Embeddings / Rerank | BAAI/bge-base-en-v1.5 · bge-reranker-base (or lightweight hash/lexical fallback) |
| Vector DB | Qdrant (Docker) or in-memory |
| Sparse | rank_bm25 |
| PII | Microsoft Presidio (+ regex fallback) |
| API | FastAPI |
| UI | Streamlit (customer + staff) |
| Audit | SQLite (demo) / Postgres (Docker) |
| Eval | Golden set (160+ cases) + CI gate |
| Observability | Langfuse (optional, self-hosted) |

Set `LLM_PROVIDER=ollama|groq|together|mock` in `.env`. Default demo mode needs **no API keys**.

---

## Repository layout

```
finsight/
├── api/              # FastAPI gateway, auth, audit
├── agents/           # LangGraph orchestrator + specialists
├── guardrails/       # Input/output policies
├── retrieval/        # Hybrid RAG pipeline + ingest
├── tools/            # Mock core-banking API + registry
├── data/             # Synthetic KB + golden eval set
├── eval/             # RAGAS/offline gate + Locust
├── frontend/         # Customer + staff Streamlit apps
├── tests/            # Unit + integration
└── scripts/          # bootstrap + seed
```

---

## Evaluation & CI

```bash
# Full golden-set gate
python -m eval.run_ragas_eval

# Subset (faster)
python -m eval.run_ragas_eval --limit 40

# Load test
locust -f eval/load_test.py --host http://localhost:8000
```

Thresholds live in `eval/thresholds.yaml`. GitHub Actions runs lint + pytest + eval gate on every PR touching retrieval, agents, or the knowledge base.

---

## Security & compliance posture

- PII redacted before LLM/logs  
- Role-based tool + document access (`customer` never sees `staff` corpus)  
- JWT auth + per-minute rate limits  
- Disallowed claims encoded in YAML (guaranteed returns, credit decisions, tax/legal advice)  
- Local-only mode: `LLM_PROVIDER=ollama` keeps text on-machine  
- Knowledge docs carry `effective_date` + `superseded_by` — date-aware retrieval  

---

## Honest caveats

- “Production-oriented” means production-shaped engineering (guardrails, evals, audit, CI, containers) — not a live bank core integration.  
- Free-tier cloud LLMs have rate limits; heavy load → Ollama or paid tier (one-line config swap).  
- Full embedding/reranker models need disk + RAM; `LIGHTWEIGHT_MODE=true` runs a strong lexical/hash fallback for demos and CI.

---

## License

MIT — built as an open reference architecture for trustworthy banking AI.
