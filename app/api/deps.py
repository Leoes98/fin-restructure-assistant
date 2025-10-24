from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from fastapi import Header, HTTPException, status

from app.core.config import get_settings
from app.services import DataRepository, DebtConsolidationAnalyzer, ScenarioBuilder

if TYPE_CHECKING:  # pragma: no cover
    from app.ai.report_generator import ReportGenerator


@lru_cache
def get_repository() -> DataRepository:
    return DataRepository()


@lru_cache
def get_analyzer() -> DebtConsolidationAnalyzer:
    repository = get_repository()
    return DebtConsolidationAnalyzer(repository.offers)


@lru_cache
def get_scenario_builder() -> ScenarioBuilder:
    repository = get_repository()
    analyzer = get_analyzer()
    return ScenarioBuilder(repository, analyzer)


@lru_cache
def get_report_generator() -> "ReportGenerator":
    from app.ai.report_generator import ReportGenerator  # avoid importing heavy deps unless needed

    return ReportGenerator(get_scenario_builder())


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    settings = get_settings()
    expected = settings.api_key
    if expected is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key not configured",
        )
    if x_api_key is None or x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
