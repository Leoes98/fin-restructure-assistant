from decimal import Decimal

from app.models import ScenarioType
from app.services import DataRepository, DebtConsolidationAnalyzer, ScenarioBuilder


def _build_builder() -> ScenarioBuilder:
    repo = DataRepository()
    analyzer = DebtConsolidationAnalyzer(repo.offers)
    return ScenarioBuilder(repo, analyzer)


def test_scenario_builder_generates_all_scenarios_for_primary_customer():
    builder = _build_builder()

    profile, summary = builder.build_summary("CU-001")

    assert profile.customer_id == "CU-001"
    assert summary.eligibility.is_eligible is True

    scenario_types = {scenario.scenario_type for scenario in summary.scenarios}
    assert scenario_types == {
        ScenarioType.MINIMUM_PAYMENT,
        ScenarioType.OPTIMIZED_PLAN,
        ScenarioType.CONSOLIDATION,
        ScenarioType.CONSOLIDATION_SURPLUS,
    }

    minimum = next(s for s in summary.scenarios if s.scenario_type is ScenarioType.MINIMUM_PAYMENT)
    optimized = next(s for s in summary.scenarios if s.scenario_type is ScenarioType.OPTIMIZED_PLAN)
    consolidations = [s for s in summary.scenarios if s.scenario_type is ScenarioType.CONSOLIDATION]
    surplus_consolidations = [
        s for s in summary.scenarios if s.scenario_type is ScenarioType.CONSOLIDATION_SURPLUS
    ]

    assert len(consolidations) == len(summary.eligibility.eligible_offers)
    assert len(surplus_consolidations) == len(summary.eligibility.eligible_offers)

    top_offer = next(s for s in consolidations if s.consolidation_offer_id == "OF-CONSO-36M")
    surplus_for_top = next(
        s for s in surplus_consolidations if s.consolidation_offer_id == "OF-CONSO-36M"
    )

    assert minimum.monthly_payment > Decimal("0")
    assert optimized.savings_vs_minimum is not None
    assert optimized.savings_vs_minimum >= Decimal("0")
    assert all(c.savings_vs_minimum is not None for c in consolidations)
    assert all(c.savings_vs_minimum is not None for c in surplus_consolidations)
    assert top_offer.payoff_months == 36
    assert surplus_for_top.payoff_months < top_offer.payoff_months


def test_consolidation_scenario_absent_for_ineligible_customer():
    builder = _build_builder()

    profile, summary = builder.build_summary("CU-002")

    assert summary.eligibility.is_eligible is True
    consolidation = [s for s in summary.scenarios if s.scenario_type is ScenarioType.CONSOLIDATION]
    surplus = [s for s in summary.scenarios if s.scenario_type is ScenarioType.CONSOLIDATION_SURPLUS]
    assert len(consolidation) == 1
    assert len(surplus) == 1
    assert consolidation[0].consolidation_offer_id == "OF-CONSO-24M"
    assert surplus[0].consolidation_offer_id == "OF-CONSO-24M"
    assert consolidation[0].savings_vs_minimum is not None
    assert surplus[0].savings_vs_minimum is not None
    assert surplus[0].payoff_months < consolidation[0].payoff_months
