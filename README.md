# BANKING / FinSight

FinSight is a production-shaped multi-agent RAG platform for banking. It combines a customer assistant, a staff co-pilot, retrieval-grounded answers, guardrails, and evaluation checks in one repository.

## What this project does

- Helps customers with product and policy questions, account lookup, and dispute intake
- Gives staff a co-pilot for compliance lookup, fraud/risk triage, and regulatory search
- Uses retrieval-grounded answers with citations and a groundedness check
- Applies guardrails for PII redaction, compliance, and safe abstention
- Includes automated tests and an evaluation gate for quality assurance

## Verified build status

The current repository state has been verified locally with fresh runs:

- 12/12 unit tests passed
- 6/6 integration tests passed
- RAGAS evaluation gate passed
- Adversarial refusal rate reached 100%

## Quick start for a new user

### 1. Prerequisites

Make sure you have:

- Python 3.11+
- Git
- Optional: Docker Desktop if you want the full containerized stack

### 2. Clone and enter the project

```bash
git clone https://github.com/Chandanagowda23/finsight.git
cd finsight
```

### 3. Bootstrap the environment

```bash
bash scripts/bootstrap.sh
```

This creates a virtual environment, installs dependencies, seeds the knowledge base, and prepares the app for local use.

### 4. Run the services

Open three terminals and run:

```bash
source .venv/bin/activate
export PYTHONPATH=.
uvicorn api.main:app --reload --port 8000
```

```bash
source .venv/bin/activate
export PYTHONPATH=.
streamlit run frontend/customer_app.py --server.port 8501
```

```bash
source .venv/bin/activate
export PYTHONPATH=.
streamlit run frontend/staff_console.py --server.port 8502
```

### 4. Use the demo accounts

- Customer login: customer / demo1234
- Staff login: staff / staff1234

### 5. Open the app

- API docs: http://localhost:8000/docs
- Customer UI: http://localhost:8501
- Staff UI: http://localhost:8502

## Docker option

If you want the full stack in containers:

```bash
cd finsight
cp .env.example .env
docker compose up --build
```

## Project docs

- [finsight/README.md](./finsight/README.md)
- [finsight/ARCHITECTURE.md](./finsight/ARCHITECTURE.md)

## Development and testing

Run tests locally:

```bash
cd finsight
pytest tests/unit tests/integration
python eval/run_ragas_eval.py
```

## Contributing

Contributions are welcome. Please run the relevant tests and evaluation checks before opening a pull request.

## License

MIT
