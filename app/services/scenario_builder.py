from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, getcontext
from typing import Sequence

from app.models import (
    CardAccount,
    CustomerProfile,
    EligibilityResult,
    LoanAccount,
    ScenarioResult,
    ScenarioSummary,
    ScenarioType,
)

from .data_loader import DataRepository
from .eligibility_engine import DebtConsolidationAnalyzer

getcontext().prec = 28

ZERO = Decimal("0")
TWOPLACES = Decimal("0.01")


@dataclass
class _Debt:
    name: str
    balance: Decimal
    monthly_rate: Decimal
    min_payment: Decimal

    def copy(self) -> "_Debt":
        return _Debt(self.name, self.balance, self.monthly_rate, self.min_payment)


class ScenarioBuilder:
    def __init__(self, repository: DataRepository, analyzer: DebtConsolidationAnalyzer) -> None:
        self._repository = repository
        self._analyzer = analyzer

    def build_summary(
        self, customer_id: str, requested_term_months: int | None = None
    ) -> tuple[CustomerProfile, ScenarioSummary]:
        profile = self._repository.build_customer_profile(customer_id, requested_term_months)
        eligibility = self._analyzer.evaluate(profile)
        scenarios = self._build_scenarios(profile, eligibility)
        return profile, ScenarioSummary(eligibility=eligibility, scenarios=scenarios)

    def _build_scenarios(
        self, profile: CustomerProfile, eligibility: EligibilityResult
    ) -> tuple[ScenarioResult, ...]:
        debts = self._build_debts(profile.cards, profile.loans)
        if not debts:
            notes = ("No se detectaron deudas activas para analizar",)
            empty = ScenarioResult(
                scenario_type=ScenarioType.MINIMUM_PAYMENT,
                monthly_payment=ZERO,
                payoff_months=0,
                total_paid=ZERO,
                interest_cost=ZERO,
                savings_vs_minimum=ZERO,
                notes=notes,
            )
            return (empty,)

        minimum_budget = sum(debt.min_payment for debt in debts)
        min_result = self._simulate_scenario(
            debts,
            monthly_budget=minimum_budget,
            scenario_type=ScenarioType.MINIMUM_PAYMENT,
            base_notes=("Solo se pagan los mínimos contractuales en todas las cuentas",),
        )

        optimized_budget = self._optimized_budget(profile, minimum_budget)
        optimized_result = self._simulate_scenario(
            debts,
            monthly_budget=optimized_budget,
            scenario_type=ScenarioType.OPTIMIZED_PLAN,
            base_notes=("El excedente de caja prioriza saldos con mayor tasa primero",),
            baseline_interest=min_result.interest_cost,
        )

        consolidation_results = self._build_consolidation_scenarios(
            profile,
            eligibility,
            baseline_interest=min_result.interest_cost,
            optimized_budget=optimized_budget,
        )

        return (min_result, optimized_result, *consolidation_results)

    def _build_debts(self, cards: Sequence[CardAccount], loans: Sequence[LoanAccount]) -> list[_Debt]:
        debts: list[_Debt] = []
        for card in cards:
            monthly_rate = (card.annual_rate_pct / Decimal("100")) / Decimal("12")
            min_payment = (card.balance * (card.min_payment_pct / Decimal("100"))).quantize(TWOPLACES)
            interest_only = (card.balance * monthly_rate).quantize(TWOPLACES)
            min_payment = max(min_payment, interest_only)
            debts.append(
                _Debt(
                    name=f"card:{card.account_id}",
                    balance=card.balance,
                    monthly_rate=monthly_rate,
                    min_payment=min_payment,
                )
            )
        for loan in loans:
            monthly_rate = (loan.annual_rate_pct / Decimal("100")) / Decimal("12")
            min_payment = self._amortized_payment(loan.balance, monthly_rate, loan.remaining_term_months)
            debts.append(
                _Debt(
                    name=f"loan:{loan.account_id}",
                    balance=loan.balance,
                    monthly_rate=monthly_rate,
                    min_payment=min_payment,
                )
            )
        return debts

    def _optimized_budget(self, profile: CustomerProfile, minimum_budget: Decimal) -> Decimal:
        cashflow = profile.cashflow
        if cashflow is None:
            return minimum_budget
        disposable_income = cashflow.monthly_income_avg - cashflow.essential_expenses_avg
        buffer = cashflow.monthly_income_avg * (cashflow.income_variability_pct / Decimal("100")) * Decimal("0.5")
        budget = disposable_income - buffer
        if budget < minimum_budget:
            return minimum_budget
        return budget.quantize(TWOPLACES)

    def _simulate_scenario(
        self,
        debts: Sequence[_Debt],
        monthly_budget: Decimal,
        scenario_type: ScenarioType,
        base_notes: tuple[str, ...],
        baseline_interest: Decimal | None = None,
    ) -> ScenarioResult:
        if monthly_budget <= ZERO:
            notes = base_notes + ("Insufficient budget to service debts",)
            return ScenarioResult(
                scenario_type=scenario_type,
                monthly_payment=ZERO,
                payoff_months=None,
                total_paid=ZERO,
                interest_cost=ZERO,
                savings_vs_minimum=None,
                notes=notes,
            )

        months, total_interest, total_paid = self._simulate_payoff(debts, monthly_budget)
        payoff_months = months if months is not None else None
        savings = None
        if baseline_interest is not None and total_interest is not None:
            savings = (baseline_interest - total_interest).quantize(TWOPLACES)
        elif baseline_interest is None:
            savings = Decimal("0.00")

        notes = base_notes
        if payoff_months is None:
            notes = base_notes + ("El presupuesto no alcanza para amortizar dentro del horizonte modelado",)

        return ScenarioResult(
            scenario_type=scenario_type,
            monthly_payment=monthly_budget.quantize(TWOPLACES),
            payoff_months=payoff_months,
            total_paid=total_paid.quantize(TWOPLACES),
            interest_cost=total_interest.quantize(TWOPLACES),
            savings_vs_minimum=savings,
            notes=notes,
        )

    def _simulate_payoff(
        self, debts: Sequence[_Debt], monthly_budget: Decimal, max_months: int = 600
    ) -> tuple[int | None, Decimal, Decimal]:
        working = [debt.copy() for debt in debts]
        balances = [debt.balance for debt in working]
        total_interest = ZERO
        total_paid = ZERO
        months = 0

        for _ in range(max_months):
            if all(balance <= ZERO for balance in balances):
                return months, total_interest, total_paid

            months += 1
            month_interest = ZERO
            for idx, debt in enumerate(working):
                balance = balances[idx]
                if balance <= ZERO:
                    continue
                interest = balance * debt.monthly_rate
                interest = interest.quantize(TWOPLACES)
                balances[idx] = balance + interest
                month_interest += interest

            payments = [ZERO] * len(working)
            active_indices = [idx for idx, balance in enumerate(balances) if balance > ZERO]
            for idx in active_indices:
                balance = balances[idx]
                min_payment = working[idx].min_payment
                payment = min(min_payment, balance)
                payments[idx] = payment

            required_payment = sum(payments)
            budget = monthly_budget
            if required_payment > budget:
                budget = required_payment

            extra = budget - required_payment
            while extra > ZERO and active_indices:
                idx = max(active_indices, key=lambda i: working[i].monthly_rate)
                balance = balances[idx]
                remaining = balance - payments[idx]
                if remaining <= ZERO:
                    active_indices.remove(idx)
                    continue
                add_payment = min(extra, remaining)
                payments[idx] += add_payment
                extra -= add_payment

            month_paid = ZERO
            for idx, payment in enumerate(payments):
                balance = balances[idx]
                if balance <= ZERO:
                    continue
                actual_payment = min(payment, balances[idx])
                balances[idx] = balance - actual_payment
                month_paid += actual_payment

            total_interest += month_interest
            total_paid += month_paid

            if all(balance <= ZERO for balance in balances):
                return months, total_interest, total_paid

        return None, total_interest, total_paid

    def _build_consolidation_scenarios(
        self,
        profile: CustomerProfile,
        eligibility: EligibilityResult,
        baseline_interest: Decimal,
        optimized_budget: Decimal,
    ) -> tuple[ScenarioResult, ...]:
        consolidated_balance = profile.consolidated_balance
        if not eligibility.eligible_offers:
            return (
                ScenarioResult(
                    scenario_type=ScenarioType.CONSOLIDATION,
                    monthly_payment=ZERO,
                    payoff_months=None,
                    total_paid=ZERO,
                    interest_cost=ZERO,
                    savings_vs_minimum=None,
                    notes=("No hay ofertas de consolidación aplicables",),
                    consolidation_offer_id=None,
                ),
            )

        results: list[ScenarioResult] = []
        for evaluation in eligibility.eligible_offers:
            offer = evaluation.offer
            term = offer.max_term_months
            if profile.requested_term_months is not None:
                term = min(profile.requested_term_months, offer.max_term_months)

            monthly_rate = (offer.new_rate_pct / Decimal("100")) / Decimal("12")
            payment = self._amortized_payment(consolidated_balance, monthly_rate, term)
            total_paid = payment * term
            interest_cost = total_paid - consolidated_balance
            savings = (baseline_interest - interest_cost).quantize(TWOPLACES)

            notes = (
                f"Consolida {len(profile.cards) + len(profile.loans)} cuentas en una sola obligación",
                f"Oferta {offer.offer_id} con tasa {offer.new_rate_pct}% a {term} meses",
            )
            if profile.requested_term_months and profile.requested_term_months > offer.max_term_months:
                notes += ("El plazo solicitado se ajusta al máximo permitido por la oferta",)

            results.append(
                ScenarioResult(
                    scenario_type=ScenarioType.CONSOLIDATION,
                    monthly_payment=payment.quantize(TWOPLACES),
                    payoff_months=term,
                    total_paid=total_paid.quantize(TWOPLACES),
                    interest_cost=interest_cost.quantize(TWOPLACES),
                    savings_vs_minimum=savings,
                    notes=notes,
                    consolidation_offer_id=offer.offer_id,
                )
            )

            surplus_budget = optimized_budget
            if surplus_budget > payment:
                accel_months, accel_interest, accel_paid = self._simulate_single_loan(
                    balance=consolidated_balance,
                    monthly_rate=monthly_rate,
                    monthly_payment=surplus_budget,
                    max_months=offer.max_term_months,
                )
                if accel_months is not None:
                    accel_savings = (baseline_interest - accel_interest).quantize(TWOPLACES)
                    base_interest = interest_cost
                    incremental_savings = (base_interest - accel_interest).quantize(TWOPLACES)
                    accel_notes = (
                        f"Consolida {len(profile.cards) + len(profile.loans)} cuentas",
                        f"Oferta {offer.offer_id} aplicando excedente mensual",
                        f"Ahorro adicional vs consolidación base: {self._format_currency(incremental_savings)}",
                    )
                    results.append(
                        ScenarioResult(
                            scenario_type=ScenarioType.CONSOLIDATION_SURPLUS,
                            monthly_payment=surplus_budget.quantize(TWOPLACES),
                            payoff_months=accel_months,
                            total_paid=accel_paid.quantize(TWOPLACES),
                            interest_cost=accel_interest.quantize(TWOPLACES),
                            savings_vs_minimum=accel_savings,
                            notes=accel_notes,
                            consolidation_offer_id=offer.offer_id,
                        )
                    )

        return tuple(results)

    @staticmethod
    def _format_currency(value: Decimal) -> str:
        return f"S/. {value:,.2f}"

    @staticmethod
    def _simulate_single_loan(
        balance: Decimal,
        monthly_rate: Decimal,
        monthly_payment: Decimal,
        max_months: int,
    ) -> tuple[int | None, Decimal, Decimal]:
        if monthly_payment <= ZERO:
            return None, ZERO, ZERO

        months = 0
        total_interest = ZERO
        total_paid = ZERO
        remaining = balance

        for _ in range(max_months * 2):
            if remaining <= ZERO:
                return months, total_interest, total_paid
            months += 1
            interest = (remaining * monthly_rate).quantize(TWOPLACES)
            principal_payment = monthly_payment - interest
            if principal_payment <= ZERO:
                return None, total_interest, total_paid
            if principal_payment > remaining:
                principal_payment = remaining
            payment = interest + principal_payment
            total_interest += interest
            total_paid += payment
            remaining -= principal_payment

        return None, total_interest, total_paid

    @staticmethod
    def _amortized_payment(balance: Decimal, monthly_rate: Decimal, term_months: int) -> Decimal:
        if term_months <= 0:
            raise ValueError("term_months must be positive")
        if balance <= ZERO:
            return ZERO
        if monthly_rate == ZERO:
            return (balance / Decimal(term_months)).quantize(TWOPLACES)
        factor = (Decimal("1") + monthly_rate) ** term_months
        payment = balance * monthly_rate * factor / (factor - Decimal("1"))
        return payment.quantize(TWOPLACES)
