from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReportResponse(BaseModel):
    customer_id: str
    report_url: str
    blob_path: str
    run_id: str
    generated_at: datetime
