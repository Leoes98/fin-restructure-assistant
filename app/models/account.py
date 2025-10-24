from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Self

from .common import ProductType


@dataclass(frozen=True)
class Account:
    account_id: str
    customer_id: str
    balance: Decimal
    days_past_due: int
    product_type: ProductType

    @classmethod
    def _parse_decimal(cls, value: str, field: str) -> Decimal:
        try:
            return Decimal(value)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"invalid decimal for {field}: {value}") from exc


@dataclass(frozen=True)
class CardAccount(Account):
    annual_rate_pct: Decimal
    min_payment_pct: Decimal
    payment_due_day: int

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        account_id = row["card_id"].strip()
        customer_id = row["customer_id"].strip()
        balance = cls._parse_decimal(row["balance"], "balance")
        annual_rate_pct = cls._parse_decimal(row["annual_rate_pct"], "annual_rate_pct")
        min_payment_pct = cls._parse_decimal(row["min_payment_pct"], "min_payment_pct")
        payment_due_day = int(row["payment_due_day"])
        days_past_due = int(row["days_past_due"])
        return cls(
            account_id=account_id,
            customer_id=customer_id,
            balance=balance,
            annual_rate_pct=annual_rate_pct,
            min_payment_pct=min_payment_pct,
            payment_due_day=payment_due_day,
            days_past_due=days_past_due,
            product_type=ProductType.CARD,
        )


@dataclass(frozen=True)
class LoanAccount(Account):
    annual_rate_pct: Decimal
    remaining_term_months: int
    collateral: bool

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        account_id = row["loan_id"].strip()
        customer_id = row["customer_id"].strip()
        principal = cls._parse_decimal(row["principal"], "principal")
        annual_rate_pct = cls._parse_decimal(row["annual_rate_pct"], "annual_rate_pct")
        remaining_term = int(row["remaining_term_months"])
        collateral = row.get("collateral", "false").strip().lower() in {"true", "1", "yes"}
        days_past_due = int(row["days_past_due"])
        product_type = ProductType.from_raw(row.get("product_type", "loan"))
        if product_type is ProductType.OTHER:
            raise ValueError(f"unsupported loan product type: {row.get('product_type')}")
        return cls(
            account_id=account_id,
            customer_id=customer_id,
            balance=principal,
            annual_rate_pct=annual_rate_pct,
            remaining_term_months=remaining_term,
            collateral=collateral,
            days_past_due=days_past_due,
            product_type=product_type,
        )
