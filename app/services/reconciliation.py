"""Daily remittance declaration and variance detection.

UC-05, UC-06 — the answer to problem P3. Layer 2 (Application).
"""

from __future__ import annotations

from datetime import date
from typing import Callable

from app.domain.entities import DailyVariance, RemittanceDeclaration, User
from app.domain.errors import DomainError, NotAuthorised
from app.domain.money import Money

from .protocols import (
    AuditRepository,
    ContributionRepository,
    RemittanceRepository,
    UnitOfWork,
)


class ReconciliationService:
    def __init__(
        self,
        *,
        remittances: RemittanceRepository,
        contributions: ContributionRepository,
        audit: AuditRepository,
        uow: UnitOfWork,
        clock: Callable[[], date] = date.today,
    ) -> None:
        self._remittances = remittances
        self._contributions = contributions
        self._audit = audit
        self._uow = uow
        self._clock = clock

    def declare(
        self, *, actor: User, amount: Money, on: date | None = None
    ) -> DailyVariance:
        """UC-05 — a collector declares the cash banked for a day (FR-24)."""
        if amount.is_negative:
            raise DomainError("Cash declared cannot be negative.")

        on = on or self._clock()
        if on > self._clock():
            raise DomainError("Cannot declare a remittance for a future date.")

        self._remittances.save(
            RemittanceDeclaration(
                id=None,
                collector_id=actor.id,
                declaration_date=on,
                amount_declared=amount,
            )
        )

        recorded = self._contributions.total_recorded_by(actor.id, on)
        variance = DailyVariance(
            collector_id=actor.id,
            collector_name=actor.full_name,
            on_date=on,
            total_recorded=recorded,
            amount_declared=amount,
        )

        self._audit.append(
            actor_id=actor.id,
            action="DECLARE_REMITTANCE",
            target_type="REMITTANCE",
            target_id=f"{actor.id}:{on.isoformat()}",
            detail={
                "declared_pesewas": amount.pesewas,
                "recorded_pesewas": recorded.pesewas,
                "variance_pesewas": variance.variance.pesewas,
            },
        )
        self._uow.commit()
        return variance

    def variances(self, *, actor: User, on: date | None = None) -> list[DailyVariance]:
        """UC-06 — every collector's position for a day (FR-25, FR-26)."""
        if not actor.is_supervisor:
            raise NotAuthorised("Only a supervisor may review variances.")
        return self._remittances.variances_for(on or self._clock())

    def my_position(self, *, actor: User, on: date | None = None) -> DailyVariance:
        """A collector's own recorded-vs-declared position for the day."""
        on = on or self._clock()
        declaration = self._remittances.get(actor.id, on)
        return DailyVariance(
            collector_id=actor.id,
            collector_name=actor.full_name,
            on_date=on,
            total_recorded=self._contributions.total_recorded_by(actor.id, on),
            amount_declared=declaration.amount_declared if declaration else None,
        )
