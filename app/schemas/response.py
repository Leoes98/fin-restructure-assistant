from __future__ import annotations

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel

from app.models import ScenarioType


class RuleResultSchema(BaseModel):
    rule: str
    passed: bool
    detail: Optional[str] = None


class OfferEvaluationSchema(BaseModel):
    offer_id: str
    passed: bool
    reasons: list[str]
    rule_results: list[RuleResultSchema]
    new_rate_pct: Decimal
    max_term_months: int


class ScenarioSchema(BaseModel):
    scenario_type: ScenarioType
    monthly_payment: Decimal
    payoff_months: Optional[int]
    total_paid: Decimal
    interest_cost: Decimal
    savings_vs_minimum: Optional[Decimal]
    notes: list[str]
    consolidation_offer_id: Optional[str] = None


class EvaluationResponse(BaseModel):
    customer_id: str
    consolidated_balance: Decimal
    is_eligible: bool
    best_offer_id: Optional[str]
    eligible_offers: list[OfferEvaluationSchema]
    rejected_offers: list[OfferEvaluationSchema]
    scenarios: list[ScenarioSchema]
