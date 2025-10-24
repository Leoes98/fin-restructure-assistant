from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Iterable

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

    async def generate(self, customer_id: str) -> ReportResult:
        profile, summary = self._scenario_builder.build_summary(customer_id)
        narrative = await self._build_narrative(profile, summary)
        pdf_bytes = self._render_pdf(profile, summary, narrative)
        upload = self._storage.upload(customer_id=customer_id, data=pdf_bytes)
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
        narrative: str,
    ) -> bytes:
        from fpdf import FPDF

        pdf = FPDF("P", "mm", "A4")
        pdf.set_auto_page_break(auto=True, margin=18)
        pdf.add_page()

        pdf.set_text_color(32, 32, 32)
        pdf.set_font("Helvetica", "B", 18)
        pdf.cell(0, 10, "Reporte de Consolidación de Deuda", ln=True)

        pdf.set_font("Helvetica", size=11)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 7, self._sanitize(f"Cliente: {profile.customer_id}"), ln=True)
        pdf.cell(0, 7, self._sanitize(f"Saldo consolidado: {self._format_currency(profile.consolidated_balance)}"), ln=True)
        pdf.cell(0, 7, self._sanitize(f"Fecha de generación: {datetime.now():%d/%m/%Y}"), ln=True)
        pdf.ln(4)

        pdf.set_draw_color(200, 200, 200)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(6)

        self._render_narrative_section(pdf, narrative)
        self._render_scenarios_section(pdf, summary.scenarios)

        return pdf.output(dest="S").encode("latin-1", "ignore")

    def _render_narrative_section(self, pdf: "FPDF", narrative: str) -> None:
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(0, 8, "Resumen narrativo", ln=True)
        pdf.set_font("Helvetica", size=11)
        pdf.set_text_color(50, 50, 50)
        for block in filter(None, (p.strip() for p in narrative.split("\n\n"))):
            lines = block.splitlines() or [block]
            for raw_line in lines:
                line = raw_line.strip()
                if not line:
                    continue
                sanitized = self._sanitize(line.lstrip("- "))
                if raw_line.strip().startswith("-"):
                    pdf.multi_cell(0, 6, f"- {sanitized}")
                else:
                    pdf.multi_cell(0, 6, sanitized)
            pdf.ln(1)
        pdf.ln(2)

    def _render_scenarios_section(
        self,
        pdf: "FPDF",
        scenarios: Iterable[ScenarioResult],
    ) -> None:
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(0, 8, "Detalle de escenarios", ln=True)
        pdf.ln(1)

        for scenario in scenarios:
            title = self._scenario_title(scenario)
            if scenario.scenario_type is ScenarioType.CONSOLIDATION:
                pdf.set_fill_color(230, 238, 253)
            elif scenario.scenario_type is ScenarioType.CONSOLIDATION_SURPLUS:
                pdf.set_fill_color(216, 247, 233)
            else:
                pdf.set_fill_color(240, 240, 240)
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(30, 30, 30)
            pdf.cell(0, 8, self._sanitize(title), ln=True, fill=True)

            pdf.set_font("Helvetica", size=10)
            pdf.set_text_color(60, 60, 60)
            pdf.cell(0, 6, self._sanitize(f"Pago mensual: {self._format_currency(scenario.monthly_payment)}"), ln=True)
            payoff = scenario.payoff_months if scenario.payoff_months is not None else "No definido"
            pdf.cell(0, 6, self._sanitize(f"Meses estimados: {payoff}"), ln=True)
            pdf.cell(0, 6, self._sanitize(f"Total pagado: {self._format_currency(scenario.total_paid)}"), ln=True)
            pdf.cell(0, 6, self._sanitize(f"Interés estimado: {self._format_currency(scenario.interest_cost)}"), ln=True)
            if scenario.savings_vs_minimum is not None:
                pdf.cell(0, 6, self._sanitize(f"Ahorro vs mínimo: {self._format_currency(scenario.savings_vs_minimum)}"), ln=True)
            if scenario.consolidation_offer_id:
                pdf.cell(0, 6, self._sanitize(f"Oferta aplicable: {scenario.consolidation_offer_id}"), ln=True)

            if scenario.notes:
                pdf.set_font("Helvetica", "I", 10)
                pdf.set_text_color(90, 90, 90)
                for note in scenario.notes:
                    pdf.multi_cell(0, 5, self._sanitize(f"· {note}"))
                pdf.set_font("Helvetica", size=10)
                pdf.set_text_color(60, 60, 60)
            pdf.ln(2)

    @staticmethod
    def _format_currency(value: Decimal | str) -> str:
        if isinstance(value, str):
            value = Decimal(value)
        return f"${value:,.2f}"

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
        return text.encode("latin-1", "replace").decode("latin-1")
