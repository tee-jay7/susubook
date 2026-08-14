"""Payout release — UC-07. Layer 2 (Application)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from app.domain.entities import Client, ContributionCycle, CycleStatus, Payout, User
from app.domain.errors import DomainError, NotAuthorised
from app.domain.rules import compute_payout
from app.domain.money import Money

from .collection import CycleService
from .protocols import (
    AuditRepository,
    ContributionRepository,
    CycleRepository,
    PayoutRepository,
    UnitOfWork,
)


@dataclass(frozen=True)
class DuePayout:
    """A matured cycle awaiting release, with its computed settlement."""

    cycle: ContributionCycle
    client: Client
    total_collected: Money
    commission: Money
    net_payout: Money
    days_paid: int


class PayoutService:
    def __init__(
        self,
        *,
        cycles: CycleRepository,
        contributions: ContributionRepository,
        payouts: PayoutRepository,
        cycle_service: CycleService,
        audit: AuditRepository,
        uow: UnitOfWork,
        clock: Callable[[], date] = date.today,
    ) -> None:
        self._cycles = cycles
        self._contributions = contributions
        self._payouts = payouts
        self._cycle_service = cycle_service
        self._audit = audit
        self._uow = uow
        self._clock = clock

    def list_due(self) -> list[DuePayout]:
        """Matured, unpaid cycles with their settlement pre-computed (FR-18)."""
        from app.domain.rules import effective_contributions, DEFAULT_COMMISSION_POLICY

        today = self._clock()
        due: list[DuePayout] = []
        for cycle, client in self._cycles.list_due_for_payout(today):
            entries = effective_contributions(
                self._contributions.list_for_cycle(cycle.id)
            )
            total = Money.zero()
            for entry in entries:
                total = total + entry.amount
            commission = DEFAULT_COMMISSION_POLICY.commission_for(total, cycle.daily_rate)
            due.append(
                DuePayout(
                    cycle=cycle,
                    client=client,
                    total_collected=total,
                    commission=commission,
                    net_payout=total - commission,
                    days_paid=len(entries),
                )
            )
        return due

    def release(self, *, cycle_id: int, actor: User) -> Payout:
        """Release a matured payout, close the cycle and open the next.

        The settlement is recomputed here from the contribution record rather
        than trusting anything displayed earlier: the figure on the supervisor's
        screen is advisory, the figure written to the ledger is derived at the
        moment of release.
        """
        if not actor.is_supervisor:
            raise NotAuthorised("Only a supervisor may release a payout.")

        cycle = self._cycles.get_by_id(cycle_id)
        if cycle is None:
            raise DomainError("That cycle no longer exists.")

        existing = self._payouts.get_for_cycle(cycle_id)

        payout = compute_payout(
            cycle=cycle,
            contributions=self._contributions.list_for_cycle(cycle_id),
            released_by_id=actor.id,
            today=self._clock(),
            already_paid=existing is not None,  # BR-R10
        )

        saved = self._payouts.add(payout)
        self._cycles.set_status(cycle_id, CycleStatus.PAID_OUT.value)

        # A payout ends one cycle and begins the next; the client keeps saving.
        # The new cycle inherits the closing cycle's rate, so a rate change
        # takes effect at a cycle boundary rather than mid-cycle.
        new_cycle = self._cycle_service.open_for(
            client_id=cycle.client_id,
            daily_rate=cycle.daily_rate,
            start=self._clock(),
            cycle_number=self._cycle_service.next_cycle_number(cycle.client_id),
        )

        self._audit.append(
            actor_id=actor.id,
            action="RELEASE_PAYOUT",
            target_type="CYCLE",
            target_id=str(cycle_id),
            detail={
                "total_collected_pesewas": saved.total_collected.pesewas,
                "commission_pesewas": saved.commission.pesewas,
                "net_payout_pesewas": saved.net_payout.pesewas,
                "next_cycle_id": new_cycle.id,
            },
        )
        self._uow.commit()
        return saved
