# Fin Restructure Assistant

A FastAPI-based decision engine that ingests customer credit exposure, scores available consolidation offers, and produces explainable recommendations alongside AI-generated PDF reports ready for client delivery. The system was designed to support debt consolidation advisors who need an auditable rules engine, scenario analytics, and polished narrative output in Spanish.

## Why It Matters
- **Eligibility & Transparency:** Validates loan and card portfolios against configurable offer rules (balance ceilings, risk limits, product mix) and returns rule-level evidence for audit trails.
- **Scenario Intelligence:** Quantifies minimum-payment, optimized-paydown, and consolidation strategies—including a surplus-paydown variant—to expose payoff times, total cost, and savings.
- **Narrative Automation:** Summarizes scenarios in natural Spanish and renders them into a branded PDF stored via Azure Blob Storage, ready to send to the customer.

## Core Architecture
```
app/
├── api/             # FastAPI routers, dependencies, request/response DTOs
├── ai/              # Azure OpenAI client + report generation pipeline
├── core/            # Configuration, logging utilities
├── models/          # Domain dataclasses (offers, accounts, scenarios, reports)
├── services/        # Data ingestion, eligibility engine, scenario builder, storage
└── schemas/         # Pydantic payload definitions
```
Key data lives in `data/` (sample CSV/JSON). Tests mirror runtime layout under `tests/` and exercise rule parsing, scenario math, API contracts, and report endpoints.

### Processing Flow
1. **Data ingestion:** `DataRepository` reads cards, loans, credit scores, and cashflow from CSV, surfaces typed domain objects.
2. **Eligibility engine:** `DebtConsolidationAnalyzer` enforces product, balance, score, and delinquency constraints and ranks offers deterministically.
3. **Scenario modeling:** `ScenarioBuilder` aggregates debt balances, simulates minimum/optimized strategies, and builds per-offer consolidation plus surplus variants.
4. **Narrative + PDF:** `ReportGenerator` prompts Azure GPT-5, composes a PDF via `fpdf2`, uploads to Azure Blob Storage, and returns a signed URL.

## API Surface
| Endpoint | Method | Description |
| --- | --- | --- |
| `/v1/evaluation` | POST | Returns eligibility verdict, rule explanations, and scenario analytics for a customer. |
| `/v1/report` | POST | Generates the full PDF report, stores it in Azure storage, and returns the SAS URL. |
| `/v1/health` | GET | Simple liveness check. |

Both POST routes require an `X-API-Key` header that matches `API_KEY` from the `.env` file.

### Sample Evaluation Request
```bash
curl -X POST http://localhost:8000/v1/evaluation \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "CU-001"}'
```

### Sample Report Request
```bash
curl -X POST http://localhost:8000/v1/report \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "CU-001"}'
```
The response contains `report_url` (SAS link), `blob_path`, and `run_id` for downstream references.

## Getting Started
### Prerequisites
- Python 3.12
- `uv` package manager or `pip`
- Access to the Azure resources (OpenAI GPT-5 deployment + Blob Storage container)

### Environment Setup
1. Copy the template:
   ```bash
   cp .env.example .env
   ```
2. Populate the following variables:

| Variable | Description |
| --- | --- |
| `API_KEY` | Shared secret for the FastAPI endpoints. |
| `AZURE_GPT5_ENDPOINT` | Azure OpenAI endpoint base URL. |
| `AZURE_GPT5_API_KEY` | API key for the GPT-5 deployment. |
| `AZURE_MODEL_NAME_DEPLOYMENT` | Name of the deployed chat completion model. |
| `AZURE_OPENAI_API_VERSION` | API version string (e.g. `2024-02-15-preview`). |
| `AZURE_STORAGE_ACCOUNT_URL` | Blob storage account endpoint (e.g. `https://<account>.blob.core.windows.net`). |
| `AZURE_STORAGE_ACCOUNT_KEY` | Storage account key for signing SAS tokens. |
| `AZURE_STORAGE_CONTAINER` | Container name where reports will be persisted. |

### Install Dependencies
```bash
uv sync
```
If you rely on `pip`, run `pip install -r requirements.txt` (generate via `uv export` if needed).

### Run Locally
```bash
uv run uvicorn main:app --reload
```
The API is now available at `http://localhost:8000`. Swagger docs can be viewed at `/docs` once authenticated.

## Testing & Quality Gates
- **Unit/API tests:** `python -m pytest --override-ini addopts=` (bypasses coverage flags baked into `pyproject.toml`).
- **Linting:** `uv run ruff check app tests` (formatting with `ruff format`).
- The test suite covers eligibility rules, consolidation math, API schemas, and ensures the report endpoint responds (with Azure integrations stubbed).

## Deployment Notes
A Dockerfile is the next logical step (planned). Current considerations:
- Rehydrate `uv` dependencies via `uv pip sync` or lock into `requirements.txt` for build reproducibility.
- Provide the `.env` values as secrets or environment variables in the container orchestrator.
- Ensure the container is allowed to reach Azure OpenAI and Blob Storage endpoints.

## Roadmap Ideas
- Add a vector store for historical customer interactions to enrich advisor reports.
- Parameterize offer ranking weights (e.g., optimize for APR vs. term depending on customer goals).
- Extend the PDF template with brand assets and charts (matplotlib/Plotly) while keeping file size modest.
- Harden production deployment with Docker + Azure App Service or Kubernetes, including health probes and structured logging sinks.
