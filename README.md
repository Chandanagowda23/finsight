# BANKING / FinSight

FinSight is a production-shaped multi-agent RAG platform for banking that combines customer support, staff co-pilot workflows, guardrails, and evaluation-driven quality checks in one repository.

## What this project includes

- Customer-facing assistance for product and policy questions, account lookups, and dispute intake
- Internal staff workflows for compliance lookup, fraud/risk triage, and regulatory search
- Retrieval-grounded responses with citations and a groundedness check
- Guardrails for PII redaction, compliance, and safe abstention
- Automated tests and an evaluation gate for quality assurance

## Verified build status

The current repository state has been verified locally with fresh runs:

- 12/12 unit tests passed
- 6/6 integration tests passed
- RAGAS evaluation gate passed
- Adversarial refusal rate reached 100%

## Quick start

```bash
cd finsight
bash scripts/bootstrap.sh
```

Then launch the API and UIs:

```bash
source .venv/bin/activate
export PYTHONPATH=.
uvicorn api.main:app --reload --port 8000
streamlit run frontend/customer_app.py --server.port 8501
streamlit run frontend/staff_console.py --server.port 8502
```

## Project docs

- [finsight/README.md](./finsight/README.md)
- [finsight/ARCHITECTURE.md](./finsight/ARCHITECTURE.md)

## Contributing

Contributions are welcome. Please run the relevant tests and evaluation checks before opening a pull request.

## License

MIT
