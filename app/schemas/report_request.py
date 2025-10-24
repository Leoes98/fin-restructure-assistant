from __future__ import annotations

from pydantic import BaseModel, Field


class ReportRequest(BaseModel):
    customer_id: str = Field(..., description="Identificador del cliente a evaluar")
