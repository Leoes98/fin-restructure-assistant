import os

os.environ.setdefault("API_KEY", "test-key")

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_evaluation_endpoint_success():
    response = client.post(
        "/v1/evaluation",
        json={"customer_id": "CU-001"},
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["customer_id"] == "CU-001"
    assert payload["is_eligible"] is True
    assert payload["best_offer_id"] == "OF-CONSO-36M"
    assert len(payload["scenarios"]) == 6
    scenario_types = {item["scenario_type"] for item in payload["scenarios"]}
    assert "consolidation_surplus" in scenario_types


def test_evaluation_endpoint_ineligible_customer():
    response = client.post(
        "/v1/evaluation",
        json={"customer_id": "CU-002"},
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["is_eligible"] is True
    assert payload["best_offer_id"] == "OF-CONSO-24M"
    consolidation = [
        scenario for scenario in payload["scenarios"] if scenario["scenario_type"] == "consolidation"
    ]
    consolidation_surplus = [
        scenario for scenario in payload["scenarios"] if scenario["scenario_type"] == "consolidation_surplus"
    ]
    assert len(consolidation) == 1
    assert len(consolidation_surplus) == 1
    assert consolidation[0]["consolidation_offer_id"] == "OF-CONSO-24M"
    assert consolidation_surplus[0]["consolidation_offer_id"] == "OF-CONSO-24M"
    assert (
        consolidation_surplus[0]["payoff_months"]
        < consolidation[0]["payoff_months"]
    )


def test_evaluation_endpoint_rejects_missing_key():
    response = client.post(
        "/v1/evaluation",
        json={"customer_id": "CU-001"},
    )
    assert response.status_code == 401
