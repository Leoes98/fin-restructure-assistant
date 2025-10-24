from __future__ import annotations

import csv
import json
from datetime import date
from decimal import Decimal
from functools import cached_property
from pathlib import Path
from typing import Iterable

from app.models import (
    CardAccount,
    CashflowSummary,
    CreditScoreRecord,
    CustomerProfile,
    LoanAccount,
    Offer,
)


class DataRepository:
    def __init__(self, data_dir: str | Path = "data") -> None:
        self.data_dir = Path(data_dir)
        if not self.data_dir.exists():
            raise FileNotFoundError(f"data directory not found: {self.data_dir}")

    @cached_property
    def offers(self) -> tuple[Offer, ...]:
        path = self.data_dir / "bank_offers.json"
        with path.open("r", encoding="utf-8") as handle:
            raw_offers = json.load(handle)
        return tuple(Offer.from_dict(item) for item in raw_offers)

    @cached_property
    def cards(self) -> tuple[CardAccount, ...]:
        path = self.data_dir / "cards.csv"
        return tuple(CardAccount.from_csv_row(row) for row in _read_csv(path))

    @cached_property
    def loans(self) -> tuple[LoanAccount, ...]:
        path = self.data_dir / "loans.csv"
        return tuple(LoanAccount.from_csv_row(row) for row in _read_csv(path))

    @cached_property
    def credit_scores(self) -> dict[str, tuple[CreditScoreRecord, ...]]:
        path = self.data_dir / "credit_score_history.csv"
        history: dict[str, list[CreditScoreRecord]] = {}
        for row in _read_csv(path):
            record = CreditScoreRecord(
                score=int(row["credit_score"]),
                recorded_on=date.fromisoformat(row["date"]),
            )
            history.setdefault(row["customer_id"], []).append(record)
        return {customer: tuple(sorted(records, key=lambda r: r.recorded_on)) for customer, records in history.items()}

    @cached_property
    def cashflows(self) -> dict[str, CashflowSummary]:
        path = self.data_dir / "customer_cashflow.csv"
        summaries: dict[str, CashflowSummary] = {}
        for row in _read_csv(path):
            summaries[row["customer_id"]] = CashflowSummary(
                monthly_income_avg=_to_decimal(row["monthly_income_avg"]),
                income_variability_pct=_to_decimal(row["income_variability_pct"]),
                essential_expenses_avg=_to_decimal(row["essential_expenses_avg"]),
            )
        return summaries

    def get_cards(self, customer_id: str) -> tuple[CardAccount, ...]:
        return tuple(card for card in self.cards if card.customer_id == customer_id)

    def get_loans(self, customer_id: str) -> tuple[LoanAccount, ...]:
        return tuple(loan for loan in self.loans if loan.customer_id == customer_id)

    def get_credit_history(self, customer_id: str) -> tuple[CreditScoreRecord, ...]:
        return self.credit_scores.get(customer_id, ())

    def get_cashflow(self, customer_id: str) -> CashflowSummary | None:
        return self.cashflows.get(customer_id)

    def build_customer_profile(
        self, customer_id: str, requested_term_months: int | None = None
    ) -> CustomerProfile:
        return CustomerProfile(
            customer_id=customer_id,
            requested_term_months=requested_term_months,
            cards=self.get_cards(customer_id),
            loans=self.get_loans(customer_id),
            cashflow=self.get_cashflow(customer_id),
            credit_history=self.get_credit_history(customer_id),
        )


def _read_csv(path: Path) -> Iterable[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if not any(row.values()):
                continue
            yield {key: (value or "").strip() for key, value in row.items()}


def _to_decimal(value: str) -> Decimal:
    try:
        return Decimal(value)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"invalid decimal value: {value}") from exc
