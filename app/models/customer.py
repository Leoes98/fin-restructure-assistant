from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Iterable, Sequence

from .account import CardAccount, LoanAccount
from .common import ProductType


@dataclass(frozen=True)
class CashflowSummary:
    monthly_income_avg: Decimal
    income_variability_pct: Decimal
    essential_expenses_avg: Decimal


@dataclass(frozen=True)
class CreditScoreRecord:
    score: int
    recorded_on: date


@dataclass(frozen=True)
class RiskIndicators:
    latest_credit_score: int | None
    credit_score_date: date | None
    max_days_past_due: int
    has_active_delinquency: bool


@dataclass(frozen=True)
class CustomerProfile:
    customer_id: str
    requested_term_months: int | None = None
    cards: Sequence[CardAccount] = field(default_factory=tuple)
    loans: Sequence[LoanAccount] = field(default_factory=tuple)
    cashflow: CashflowSummary | None = None
    credit_history: Sequence[CreditScoreRecord] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.requested_term_months is not None and self.requested_term_months <= 0:
            raise ValueError("requested_term_months must be positive when provided")

    @property
    def product_types_owned(self) -> frozenset[ProductType]:
        types: set[ProductType] = set()
        if self.cards:
            types.add(ProductType.CARD)
        types.update(loan.product_type for loan in self.loans)
        return frozenset(types)

    @property
    def consolidated_balance(self) -> Decimal:
        card_balance = sum((card.balance for card in self.cards), Decimal("0"))
        loan_balance = sum((loan.balance for loan in self.loans), Decimal("0"))
        return card_balance + loan_balance

    @property
    def risk_indicators(self) -> RiskIndicators:
        scores = sorted(self.credit_history, key=lambda record: record.recorded_on, reverse=True)
        latest = scores[0] if scores else None
        max_dpd = _max_days_past_due(self.cards, self.loans)
        return RiskIndicators(
            latest_credit_score=latest.score if latest else None,
            credit_score_date=latest.recorded_on if latest else None,
            max_days_past_due=max_dpd,
            has_active_delinquency=max_dpd > 0,
        )


def _max_days_past_due(cards: Iterable[CardAccount], loans: Iterable[LoanAccount]) -> int:
    dpd_values = [card.days_past_due for card in cards]
    dpd_values.extend(loan.days_past_due for loan in loans)
    return max(dpd_values) if dpd_values else 0
