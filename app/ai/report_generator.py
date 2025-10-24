from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.ai.openai_client import AzureOpenAIClient
from app.models import (
    CustomerProfile,
    ReportResult,
    ScenarioResult,
    ScenarioSummary,
    ScenarioType,
)
from app.services.report_storage import AzureBlobReportStorage
from app.services.scenario_builder import ScenarioBuilder


class ReportGenerator:
    def __init__(self, scenario_builder: ScenarioBuilder) -> None:
        self._scenario_builder = scenario_builder
        self._openai_client = AzureOpenAIClient()
        self._storage = AzureBlobReportStorage()
        templates_path = Path(__file__).resolve().parent.parent / "templates"
        self._jinja = Environment(
            loader=FileSystemLoader(templates_path),
            autoescape=select_autoescape(["html"]),
        )
        self._template = self._jinja.get_template("report.html")

    async def generate(self, customer_id: str) -> ReportResult:
        profile, summary = self._scenario_builder.build_summary(customer_id)
        narrative = await self._build_narrative(profile, summary)
        parsed_narrative = self._parse_narrative(narrative)
        run_id = f"rpt_{uuid4().hex[:8]}"
        rendered_at = datetime.utcnow()
        pdf_bytes = self._render_pdf(
            profile,
            summary,
            parsed_narrative,
            run_id=run_id,
            generated_at=rendered_at,
        )
        upload = self._storage.upload(customer_id=customer_id, data=pdf_bytes, run_id=run_id)
        return ReportResult(
            customer_id=customer_id,
            run_id=upload.run_id,
            blob_path=upload.blob_path,
            url=upload.url,
            generated_at=upload.generated_at,
            narrative=narrative,
            summary=summary,
        )

    async def _build_narrative(
        self, profile: CustomerProfile, summary: ScenarioSummary
    ) -> str:
        payload = self._build_structured_payload(profile, summary)
        messages = [
            {
                "role": "system",
                "content": (
                    "Eres un analista financiero senior. Analiza el JSON y devuelve un informe breve en español"
                    " usando solo texto plano (sin Markdown, tablas ni símbolos especiales). Sigue exactamente esta"
                    " estructura y no añadas encabezados adicionales:\n"
                    "Resumen ejecutivo:\n- frase1 (máx 20 palabras)\n- frase2 (máx 20 palabras)\n"
                    "Puntos clave por escenario:\n- Escenario 1 ...\n- Escenario 2 ...\n- Escenario 3 (<ID oferta si aplica>) ...\n"
                    "Recomendaciones y riesgos:\n- recomendación 1\n- recomendación 2\n"
                    "Usa frases diferentes a las del detalle numérico y evita repetir datos textuales que ya aparecerán"
                    " en la sección de escenarios. Mantén todo en español neutro y evita palabras en inglés."
                ),
            },
            {
                "role": "user",
                "content": f"Datos del cliente en JSON:\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```",
            },
        ]
        return await self._openai_client.chat_completion(messages, temperature=0.2)

    def _build_structured_payload(
        self, profile: CustomerProfile, summary: ScenarioSummary
    ) -> dict:
        eligibility = summary.eligibility
        scenarios = [self._scenario_to_dict(s) for s in summary.scenarios]
        return {
            "customer_id": profile.customer_id,
            "consolidated_balance": str(profile.consolidated_balance),
            "product_types_owned": sorted(t.value for t in profile.product_types_owned),
            "eligibility": {
                "is_eligible": eligibility.is_eligible if eligibility else False,
                "best_offer_id": eligibility.best_offer.offer.offer_id if eligibility and eligibility.best_offer else None,
            },
            "scenarios": scenarios,
        }

    def _scenario_to_dict(self, scenario: ScenarioResult) -> dict:
        return {
            "scenario_type": scenario.scenario_type.value,
            "label": self._scenario_title(scenario),
            "monthly_payment": str(scenario.monthly_payment),
            "payoff_months": scenario.payoff_months,
            "total_paid": str(scenario.total_paid),
            "interest_cost": str(scenario.interest_cost),
            "savings_vs_minimum": str(scenario.savings_vs_minimum)
            if scenario.savings_vs_minimum is not None
            else None,
            "consolidation_offer_id": scenario.consolidation_offer_id,
            "notes": list(scenario.notes),
        }

    def _render_pdf(
        self,
        profile: CustomerProfile,
        summary: ScenarioSummary,
        narrative_sections: dict[str, list[str]],
        *,
        run_id: str,
        generated_at: datetime,
    ) -> bytes:
        context = {
            "customer_id": profile.customer_id,
            "consolidated_balance": self._format_currency(profile.consolidated_balance),
            "generated_at": generated_at.strftime("%d/%m/%Y"),
            "run_id": run_id,
            "narrative": narrative_sections,
            "scenarios": [
                {
                    "title": self._scenario_title(scenario),
                    "offer_id": scenario.consolidation_offer_id,
                    "monthly_payment": self._format_currency(scenario.monthly_payment),
                    "payoff_months": scenario.payoff_months if scenario.payoff_months is not None else "No definido",
                    "total_paid": self._format_currency(scenario.total_paid),
                    "interest_cost": self._format_currency(scenario.interest_cost),
                    "savings_vs_minimum": self._format_currency(scenario.savings_vs_minimum)
                    if scenario.savings_vs_minimum is not None
                    else None,
                    "notes": [self._sanitize(note) for note in scenario.notes],
                }
                for scenario in summary.scenarios
            ],
        }
        html = self._template.render(**context)
        try:
            from weasyprint import HTML  # delayed import to keep optional dependency lazy
        except ImportError as exc:  # pragma: no cover - runtime guard
            raise RuntimeError(
                "WeasyPrint no está instalado. Ejecuta 'uv add weasyprint' o 'pip install weasyprint' para habilitar la generación de PDF."  # noqa: EM101
            ) from exc

        try:
            return HTML(string=html).write_pdf()
        except OSError as exc:  # pragma: no cover - depends on system libs
            raise RuntimeError(
                "WeasyPrint requiere librerías nativas (cairo, pango, gdk-pixbuf). En macOS instala con 'brew install cairo pango gdk-pixbuf libffi'."  # noqa: EM101
            ) from exc

    @staticmethod
    def _scenario_title(scenario: ScenarioResult) -> str:
        if scenario.scenario_type is ScenarioType.MINIMUM_PAYMENT:
            return "Escenario 1 · Pago mínimo"
        if scenario.scenario_type is ScenarioType.OPTIMIZED_PLAN:
            return "Escenario 2 · Plan optimizado"
        if scenario.scenario_type is ScenarioType.CONSOLIDATION:
            suffix = f" ({scenario.consolidation_offer_id})" if scenario.consolidation_offer_id else ""
            return f"Escenario 3 · Consolidación{suffix}"
        if scenario.scenario_type is ScenarioType.CONSOLIDATION_SURPLUS:
            suffix = f" ({scenario.consolidation_offer_id})" if scenario.consolidation_offer_id else ""
            return f"Escenario 3 · Consolidación con excedente{suffix}"
        return scenario.scenario_type.value

    @staticmethod
    def _sanitize(text: str) -> str:
        replacements = {
            "–": "-",
            "—": "-",
            "‑": "-",  # non-breaking hyphen
            "“": '"',
            "”": '"',
            "‘": "'",
            "’": "'",
            "•": "·",
            "·": "·",
            " ": " ",  # narrow no-break space
            " ": " ",  # no-break space
        }
        for src, dst in replacements.items():
            text = text.replace(src, dst)
        return text

    @staticmethod
    def _format_currency(value: Decimal | str) -> str:
        if isinstance(value, str):
            value = Decimal(value)
        return f"S/. {value:,.2f}"

    def _parse_narrative(self, narrative: str) -> dict[str, list[str]]:
        summary: list[str] = []
        scenarios: list[str] = []
        risks: list[str] = []

        current = None
        for raw_line in narrative.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            lower = line.lower()
            if lower.startswith("resumen ejecutivo"):
                current = summary
                continue
            if lower.startswith("puntos clave"):
                current = scenarios
                continue
            if lower.startswith("recomendaciones") or lower.startswith("riesgos"):
                current = risks
                continue
            if line.startswith("-"):
                text = self._sanitize(line.lstrip("- "))
                (current or summary).append(text)
            else:
                (current or summary).append(self._sanitize(line))

        # Fallbacks to guarantee sections for template
        if not summary:
            summary.append("Se generó el reporte con los datos proporcionados.")
        if not scenarios:
            scenarios.append("Ver detalle numérico en la sección inferior.")
        if not risks:
            risks.append("Revise los supuestos de ingreso y variabilidad antes de avanzar.")

        return {"summary": summary, "scenarios": scenarios, "risks": risks}
