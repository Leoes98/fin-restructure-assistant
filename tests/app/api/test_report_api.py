from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.deps import get_report_generator
from app.models import ScenarioSummary
from app.models.report import ReportResult
from main import app

client = TestClient(app)


class StubReportGenerator:
    async def generate(self, customer_id: str) -> ReportResult:
        return ReportResult(
            customer_id=customer_id,
            run_id="rpt_stub",
            blob_path="fin-restructure/yyyy=2025/mm=10/dd=23/customer_id=CU-001/run=rpt_stub/report.pdf",
            url="https://example.com/report.pdf",
            generated_at=datetime(2025, 10, 23, 12, 0, tzinfo=timezone.utc),
            narrative="Informe de prueba",
            summary=ScenarioSummary(eligibility=None, scenarios=()),  # type: ignore[arg-type]
        )


def test_report_endpoint_returns_payload(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key")
    app.dependency_overrides[get_report_generator] = lambda: StubReportGenerator()
    response = client.post(
        "/v1/report",
        json={"customer_id": "CU-001"},
        headers={"X-API-Key": "test-key"},
    )
    app.dependency_overrides.pop(get_report_generator, None)
    assert response.status_code == 200
    payload = response.json()
    assert payload["customer_id"] == "CU-001"
    assert payload["run_id"] == "rpt_stub"
    assert payload["report_url"] == "https://example.com/report.pdf"
