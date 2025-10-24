from app.models.offer import Offer


def test_offer_rule_config_parses_min_score_and_delinquency():
    offer = Offer.from_dict(
        {
            "offer_id": "OF-TEST-24M",
            "product_types_eligible": ["personal"],
            "max_consolidated_balance": 25000,
            "new_rate_pct": 15.0,
            "max_term_months": 24,
            "conditions": "Score >= 650, sin mora activa y sin reestructuración vigente",
        }
    )

    rules = offer.rule_config

    assert rules.min_credit_score == 650
    assert rules.disallow_active_delinquencies is True
    assert rules.notes is not None and "mora" in rules.notes.lower()
