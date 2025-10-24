from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Sequence

from app.models import (
    CustomerProfile,
    EligibilityResult,
    Offer,
    OfferEvaluation,
    RiskIndicators,
    RuleEvaluation,
)


class DebtConsolidationAnalyzer:
    def __init__(self, offers: Sequence[Offer]) -> None:
        self.offers = tuple(sorted(offers, key=lambda offer: offer.sort_key))

    def evaluate(self, customer: CustomerProfile) -> EligibilityResult:
        eligible: list[OfferEvaluation] = []
        rejected: list[OfferEvaluation] = []
        balance = customer.consolidated_balance
        risk = customer.risk_indicators
        for offer in self.offers:
            rule_results = tuple(self._evaluate_offer(offer, customer, balance, risk))
            passed = all(rule.passed for rule in rule_results)
            evaluation = OfferEvaluation(offer=offer, passed=passed, rule_results=rule_results)
            if passed:
                eligible.append(evaluation)
            else:
                rejected.append(evaluation)
        eligible.sort(key=lambda evaluation: evaluation.offer.sort_key)
        rejected.sort(key=lambda evaluation: evaluation.offer.sort_key)
        return EligibilityResult(
            customer_id=customer.customer_id,
            requested_term_months=customer.requested_term_months,
            eligible_offers=tuple(eligible),
            rejected_offers=tuple(rejected),
        )

    def _evaluate_offer(
        self,
        offer: Offer,
        customer: CustomerProfile,
        balance: Decimal,
        risk: RiskIndicators,
    ) -> Iterable[RuleEvaluation]:
        owned_types = customer.product_types_owned
        type_match = bool(owned_types & offer.product_types_eligible)
        yield RuleEvaluation(
            rule="product_type_match",
            passed=type_match,
            detail=(
                f"products owned {sorted(t.value for t in owned_types)} match eligible {sorted(t.value for t in offer.product_types_eligible)}"
                if type_match
                else f"missing eligible product types {sorted(t.value for t in offer.product_types_eligible)}"
            ),
        )

        balance_pass = balance <= offer.max_consolidated_balance
        yield RuleEvaluation(
            rule="max_consolidated_balance",
            passed=balance_pass,
            detail=(
                f"balance {balance:.2f} <= {offer.max_consolidated_balance:.2f}"
                if balance_pass
                else f"balance {balance:.2f} exceeds {offer.max_consolidated_balance:.2f}"
            ),
        )

        if customer.requested_term_months is not None:
            term_pass = customer.requested_term_months <= offer.max_term_months
            yield RuleEvaluation(
                rule="max_term_months",
                passed=term_pass,
                detail=(
                    f"term {customer.requested_term_months} <= {offer.max_term_months}"
                    if term_pass
                    else f"term {customer.requested_term_months} exceeds {offer.max_term_months}"
                ),
            )

        min_score = offer.rule_config.min_credit_score
        latest_score = risk.latest_credit_score
        if min_score is not None:
            if latest_score is None:
                yield RuleEvaluation(
                    rule="min_credit_score",
                    passed=False,
                    detail="missing credit score data",
                )
            else:
                score_pass = latest_score >= min_score
                yield RuleEvaluation(
                    rule="min_credit_score",
                    passed=score_pass,
                    detail=(
                        f"score {latest_score} >= {min_score}"
                        if score_pass
                        else f"score {latest_score} < {min_score}"
                    ),
                )

        max_dpd = offer.rule_config.max_days_past_due
        if max_dpd is not None:
            dpd_pass = risk.max_days_past_due <= max_dpd
            yield RuleEvaluation(
                rule="max_days_past_due",
                passed=dpd_pass,
                detail=(
                    f"max DPD {risk.max_days_past_due} <= {max_dpd}"
                    if dpd_pass
                    else f"max DPD {risk.max_days_past_due} > {max_dpd}"
                ),
            )

        if offer.rule_config.disallow_active_delinquencies:
            delinquency_pass = not risk.has_active_delinquency
            yield RuleEvaluation(
                rule="no_active_delinquencies",
                passed=delinquency_pass,
                detail="no active delinquencies" if delinquency_pass else "active delinquency present",
            )
