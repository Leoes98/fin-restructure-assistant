from __future__ import annotations

from pydantic import BaseModel, Field


class EvaluationRequest(BaseModel):
    customer_id: str = Field(..., description="Customer identifier as seen in the source datasets")
