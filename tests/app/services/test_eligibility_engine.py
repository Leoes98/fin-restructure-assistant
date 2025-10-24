from datetime import date
from decimal import Decimal

from app.models import CreditScoreRecord, CustomerProfile, LoanAccount, Offer, ProductType
from app.services import DebtConsolidationAnalyzer


def _build_offer() -> Offer:
    return Offer.from_dict(
        {
            "offer_id": "OF-TEST-DPD",
            "product_types_eligible": ["personal"],
            "max_consolidated_balance": 30000,
            "new_rate_pct": 12.5,
            "max_term_months": 24,
            "conditions": "Score >= 650 y sin mora activa",
        }
    )


def _build_customer(*, days_past_due: int) -> CustomerProfile:
    loan = LoanAccount(
        account_id="L-1",
        customer_id="CU-XYZ",
        balance=Decimal("12000"),
        days_past_due=days_past_due,
        product_type=ProductType.PERSONAL,
        annual_rate_pct=Decimal("25.0"),
        remaining_term_months=18,
        collateral=False,
    )
    return CustomerProfile(
        customer_id="CU-XYZ",
        requested_term_months=18,
        loans=(loan,),
        credit_history=(CreditScoreRecord(score=680, recorded_on=date(2025, 1, 1)),),
    )


def test_offer_rejected_when_customer_has_active_delinquency():
    offer = _build_offer()
    analyzer = DebtConsolidationAnalyzer([offer])
    customer = _build_customer(days_past_due=45)

    result = analyzer.evaluate(customer)

    assert result.is_eligible is False
    dpd_rule = next(rule for rule in result.rejected_offers[0].rule_results if rule.rule == "max_days_past_due")
    assert dpd_rule.passed is False
    assert "45" in (dpd_rule.detail or "")


def test_offer_passes_when_customer_is_current():
    offer = _build_offer()
    analyzer = DebtConsolidationAnalyzer([offer])
    customer = _build_customer(days_past_due=0)

    result = analyzer.evaluate(customer)

    assert result.is_eligible is True
    best_offer = result.best_offer
    assert best_offer is not None
    dpd_rule = next(rule for rule in best_offer.rule_results if rule.rule == "max_days_past_due")
    assert dpd_rule.passed is True
