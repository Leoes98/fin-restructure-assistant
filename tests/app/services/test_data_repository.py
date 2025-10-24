from decimal import Decimal

from app.models import ProductType
from app.services import DataRepository, DebtConsolidationAnalyzer


def test_repository_loads_expected_entities():
    repo = DataRepository()

    offers = repo.offers
    assert len(offers) == 2
    assert {offer.offer_id for offer in offers} == {"OF-CONSO-24M", "OF-CONSO-36M"}

    profile = repo.build_customer_profile("CU-001")

    assert profile.customer_id == "CU-001"
    assert profile.product_types_owned == {ProductType.CARD, ProductType.PERSONAL}
    assert profile.consolidated_balance == Decimal("21500")

    risk = profile.risk_indicators
    assert risk.latest_credit_score == 720
    assert risk.max_days_past_due == 0
    assert risk.has_active_delinquency is False


def test_analyzer_with_real_customer_data():
    repo = DataRepository()
    analyzer = DebtConsolidationAnalyzer(repo.offers)

    customer = repo.build_customer_profile("CU-001")
    result = analyzer.evaluate(customer)

    assert result.is_eligible is True
    assert result.best_offer is not None
    assert result.best_offer.offer.offer_id == "OF-CONSO-36M"

    # Ensure offer that requires higher score/term still passes due to better rate
    assert [evaluation.offer.offer_id for evaluation in result.eligible_offers] == ["OF-CONSO-36M", "OF-CONSO-24M"]

    other_customer = repo.build_customer_profile("CU-002")
    other_result = analyzer.evaluate(other_customer)

    assert [evaluation.offer.offer_id for evaluation in other_result.eligible_offers] == ["OF-CONSO-24M"]
    assert [evaluation.offer.offer_id for evaluation in other_result.rejected_offers] == ["OF-CONSO-36M"]
