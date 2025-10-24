from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import FrozenSet

from .common import ProductType


@dataclass(frozen=True)
class OfferRuleConfig:
    min_credit_score: int | None = None
    max_days_past_due: int | None = None
    disallow_active_delinquencies: bool = False
    notes: str | None = None

    @classmethod
    def from_conditions(cls, conditions: str) -> "OfferRuleConfig":
        text = (conditions or "").lower()
        min_score = _extract_min_score(text)
        max_dpd = _extract_max_dpd(text)
        disallow_delinquencies = "sin mora activa" in text or "no mora activa" in text
        if "sin mora activa" in text and max_dpd is None:
            max_dpd = 0
        return cls(
            min_credit_score=min_score,
            max_days_past_due=max_dpd,
            disallow_active_delinquencies=disallow_delinquencies,
            notes=conditions or None,
        )


@dataclass(frozen=True)
class Offer:
    offer_id: str
    product_types_eligible: FrozenSet[ProductType]
    max_consolidated_balance: Decimal
    new_rate_pct: Decimal
    max_term_months: int
    conditions: str
    rule_config: OfferRuleConfig

    @classmethod
    def from_dict(cls, data: dict) -> "Offer":
        offer_id = data.get("offer_id")
        if not offer_id:
            raise ValueError("offer_id is required")

        raw_types = data.get("product_types_eligible") or []
        if not raw_types:
            raise ValueError(f"offer {offer_id} must define product_types_eligible")
        product_types = frozenset(ProductType.from_raw(value) for value in raw_types)
        if ProductType.OTHER in product_types:
            raise ValueError(f"offer {offer_id} has unsupported product type in {raw_types}")

        max_balance = _to_decimal(data.get("max_consolidated_balance"), field="max_consolidated_balance")
        rate_pct = _to_decimal(data.get("new_rate_pct"), field="new_rate_pct")
        if rate_pct <= 0:
            raise ValueError(f"offer {offer_id} new_rate_pct must be positive")

        max_term = int(data.get("max_term_months"))
        if max_term <= 0 or max_term > 60:
            raise ValueError(f"offer {offer_id} max_term_months must be within 1-60")

        conditions = data.get("conditions", "")
        rule_config = OfferRuleConfig.from_conditions(conditions)

        return cls(
            offer_id=offer_id,
            product_types_eligible=product_types,
            max_consolidated_balance=max_balance,
            new_rate_pct=rate_pct,
            max_term_months=max_term,
            conditions=conditions,
            rule_config=rule_config,
        )

    @property
    def sort_key(self) -> tuple[Decimal, int, str]:
        return (self.new_rate_pct, -self.max_term_months, self.offer_id)


def _to_decimal(value: object, *, field: str) -> Decimal:
    if value is None:
        raise ValueError(f"{field} is required")
    try:
        return Decimal(str(value))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"invalid decimal for {field}: {value}") from exc


def _extract_min_score(text: str) -> int | None:
    match = re.search(r"score\s*[>=]+\s*(\d+)", text)
    if match:
        return int(match.group(1))
    return None


def _extract_max_dpd(text: str) -> int | None:
    if "sin mora" in text and "activa" in text:
        return 0
    match = re.search(r"(\d+)\s*d[ií]as", text)
    if match:
        return int(match.group(1))
    range_match = re.search(r">\s*(\d+)\s*d[ií]as", text)
    if range_match:
        return int(range_match.group(1))
    return None
