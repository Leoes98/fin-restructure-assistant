from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Sequence

from .offer import Offer


class ScenarioType(StrEnum):
    MINIMUM_PAYMENT = "minimum_payment"
    OPTIMIZED_PLAN = "optimized_plan"
    CONSOLIDATION = "consolidation"
    CONSOLIDATION_SURPLUS = "consolidation_surplus"


@dataclass(frozen=True)
class RuleEvaluation:
    rule: str
    passed: bool
    detail: str | None = None


@dataclass(frozen=True)
class OfferEvaluation:
    offer: Offer
    passed: bool
    rule_results: Sequence[RuleEvaluation]

    @property
    def reasons(self) -> tuple[str, ...]:
        positives = [result.detail for result in self.rule_results if result.passed and result.detail]
        negatives = [result.detail for result in self.rule_results if not result.passed and result.detail]
        return tuple(positives + negatives)


@dataclass(frozen=True)
class EligibilityResult:
    customer_id: str
    requested_term_months: int | None
    eligible_offers: tuple[OfferEvaluation, ...]
    rejected_offers: tuple[OfferEvaluation, ...]

    @property
    def best_offer(self) -> OfferEvaluation | None:
        return self.eligible_offers[0] if self.eligible_offers else None

    @property
    def is_eligible(self) -> bool:
        return bool(self.eligible_offers)


@dataclass(frozen=True)
class ScenarioResult:
    scenario_type: ScenarioType
    monthly_payment: Decimal
    payoff_months: int | None
    total_paid: Decimal
    interest_cost: Decimal
    savings_vs_minimum: Decimal | None
    notes: tuple[str, ...]
    consolidation_offer_id: str | None = None


@dataclass(frozen=True)
class ScenarioSummary:
    eligibility: EligibilityResult
    scenarios: tuple[ScenarioResult, ...]
