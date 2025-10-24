from __future__ import annotations

from enum import StrEnum


class ProductType(StrEnum):
    """Supported product type identifiers for debt products."""

    CARD = "card"
    PERSONAL = "personal"
    MICRO = "micro"
    LOAN = "loan"
    OTHER = "other"

    @classmethod
    def from_raw(cls, raw: str) -> "ProductType":
        value = raw.strip().lower()
        for member in cls:
            if value == member.value:
                return member
        aliases = {
            "personal_loan": cls.PERSONAL,
            "personal-loan": cls.PERSONAL,
            "micro_loan": cls.MICRO,
            "micro-loan": cls.MICRO,
            "credit_card": cls.CARD,
            "credit-card": cls.CARD,
        }
        if value in aliases:
            return aliases[value]
        return cls.OTHER
