from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends

from app.api.deps import get_scenario_builder, require_api_key
from app.models import ScenarioSummary
from app.schemas.request import EvaluationRequest
from app.schemas.response import EvaluationResponse, OfferEvaluationSchema, RuleResultSchema, ScenarioSchema
from app.services.scenario_builder import ScenarioBuilder

router = APIRouter(prefix="/v1", tags=["evaluation"], dependencies=[Depends(require_api_key)])


@router.post("/evaluation", response_model=EvaluationResponse, summary="Evaluate consolidation eligibility and scenarios")
def evaluate_customer(
    payload: EvaluationRequest,
    scenario_builder: ScenarioBuilder = Depends(get_scenario_builder),
) -> EvaluationResponse:
    profile, summary = scenario_builder.build_summary(customer_id=payload.customer_id)
    return _to_response(profile.customer_id, summary, profile.consolidated_balance)


def _to_response(
    customer_id: str,
    summary: ScenarioSummary,
    consolidated_balance: Decimal,
) -> EvaluationResponse:
    eligibility = summary.eligibility
    best_offer = eligibility.best_offer.offer.offer_id if eligibility.best_offer else None

    def map_offer(evaluation) -> OfferEvaluationSchema:
        return OfferEvaluationSchema(
            offer_id=evaluation.offer.offer_id,
            passed=evaluation.passed,
            reasons=list(evaluation.reasons),
            rule_results=[
                RuleResultSchema(rule=rule.rule, passed=rule.passed, detail=rule.detail)
                for rule in evaluation.rule_results
            ],
            new_rate_pct=evaluation.offer.new_rate_pct,
            max_term_months=evaluation.offer.max_term_months,
        )

    scenarios = [
        ScenarioSchema(
            scenario_type=scenario.scenario_type,
            monthly_payment=scenario.monthly_payment,
            payoff_months=scenario.payoff_months,
            total_paid=scenario.total_paid,
            interest_cost=scenario.interest_cost,
            savings_vs_minimum=scenario.savings_vs_minimum,
            notes=list(scenario.notes),
            consolidation_offer_id=scenario.consolidation_offer_id,
        )
        for scenario in summary.scenarios
    ]

    return EvaluationResponse(
        customer_id=customer_id,
        consolidated_balance=consolidated_balance,
        is_eligible=eligibility.is_eligible,
        best_offer_id=best_offer,
        eligible_offers=[map_offer(item) for item in eligibility.eligible_offers],
        rejected_offers=[map_offer(item) for item in eligibility.rejected_offers],
        scenarios=scenarios,
    )
