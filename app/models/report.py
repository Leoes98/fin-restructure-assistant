from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .decision import ScenarioSummary


@dataclass(frozen=True)
class ReportResult:
    customer_id: str
    run_id: str
    blob_path: str
    url: str
    generated_at: datetime
    narrative: str
    summary: ScenarioSummary
