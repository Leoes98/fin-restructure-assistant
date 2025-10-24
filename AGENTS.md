# Repository Guidelines

## Project Structure & Ownership
- `app/api/` — FastAPI routers (`routes/`), dependency wiring (`deps.py`), and request/response schemas (`schemas/`). Keep every new route versioned under `/v1` until a breaking change is required.
- `app/services/` — Domain services (data ingestion, eligibility engine, scenario builder, report storage). Extend or wrap these services before touching API layers.
- `app/ai/` — Azure GPT and report-generation utilities. Any GenAI prompt or output formatting change belongs here.
- `data/` — Source CSV/JSON files for local simulations. Treat as read-only fixtures.
- `tests/` — Mirrors runtime layout. When adding a module, land a corresponding test module (`tests/<path>/test_*.py`).

## Local Tooling & Commands
- Environment: Python 3.12. Manage dependencies with `uv sync` (preferred).
- Run server: `uv run fastapi dev main.py`.
- Tests: `uv run pytest tests`.
- Lint/format: `uv run ruff check app tests` and `uv run ruff format app tests`.

## Coding Standards
- Follow PEP 8 with type hints on all public functions. Keep business rules in services, not in routers.
- Scenario/offer logic must remain deterministic; document any tie-breaker changes in the service docstrings.
- Keep API responses and report narratives Spanish-first; sanitize user-facing strings before rendering PDFs.

## Testing Expectations
- Unit tests for every new service method and edge-case (e.g., offer parsing, surplus allocation).
- API tests must assert status, payload schema, and critical fields. Stub external services (Azure) via dependency overrides.
- When changing prompts or PDF output, add regression tests that assert narrative structure (no Markdown, Spanish text present).

## Secrets & Configuration
- Copy `.env.example` → `.env`. Never commit real keys.
- Required env vars: `API_KEY`, Azure OpenAI (`AZURE_GPT5_*`), and storage (`AZURE_STORAGE_*`). Missing values should fail fast—don’t add silent fallbacks.

## Git Hygiene
- Conventional commit prefixes (`feat`, `fix`, `chore`, `docs`, `test`). Keep PRs focused and include testing evidence in the description.
- Rebase or merge main before pushing feature branches to avoid data drift in fixtures or scenarios.

## Incident Response & Support
- If report generation fails in production, check Azure credentials first, then inspect `_sanitize` and `_format_currency` helpers for unsupported characters.
- Eligibility discrepancies should be reproduced with the CSV fixtures before touching service logic; document rule changes in the README.
