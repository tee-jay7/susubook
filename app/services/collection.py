"""Contribution recording, correction and the collector route sheet.

UC-02, UC-03, UC-09. Layer 2 (Application): orchestrates, authorises, audits
and commits. Every business decision is delegated to app/domain/rules.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable
from uuid import UUID, uuid4

from app.domain.entities import (
    Client,
    Contribution,
    ContributionCycle,
    CycleStatus,
    CycleSummary,
    User,
)
from app.domain.errors import DomainError, NotAuthorised
from app.domain.money import Money
from app.domain.rules import (
    DEFAULT_CYCLE_LENGTH_DAYS,
    compute_cycle_summary,
    cycle_end_date,
    validate_contribution,
)

from .protocols import (
    AuditRepository,
    ClientRepository,
    ContributionRepository,
    CycleRepository,
    UnitOfWork,
    UserRepository,
)


class ClientNotFound(DomainError):
    pass


class NoActiveCycle(DomainError):
    pass


@dataclass(frozen=True)
class RouteEntry:
    """One row of the collector's daily route sheet (FR-23)."""

    client: Client
    collected_today: bool
    cycle: ContributionCycle | None


class CycleService:
    """Opening and maturing contribution cycles (FR-10, BR-R2, BR-R12)."""

    def __init__(
        self,
        cycles: CycleRepository,
        *,
        clock: Callable[[], date] = date.today,
        cycle_length: int = DEFAULT_CYCLE_LENGTH_DAYS,
    ) -> None:
        self._cycles = cycles
        self._clock = clock
        self._length = cycle_length

    def open_for(
        self,
        *,
        client_id: int,
        daily_rate: Money,
        start: date | None = None,
        cycle_number: int = 1,
    ) -> ContributionCycle:
        """Open a cycle.

        Takes the client id and rate rather than a whole Client, because the
        payout path opens the next cycle knowing only what the closing cycle
        carried. Requiring a full entity there would mean constructing a
        half-populated one purely to satisfy the signature.
        """
        start = start or self._clock()
        return self._cycles.add(
            ContributionCycle(
                id=None,
                client_id=client_id,
                cycle_number=cycle_number,
                start_date=start,
                end_date=cycle_end_date(start, self._length),
                status=CycleStatus.ACTIVE,
                # Snapshot: a later rate change must not alter this cycle.
                daily_rate=daily_rate,
            )
        )

    def next_cycle_number(self, client_id: int) -> int:
        existing = self._cycles.list_for_client(client_id)
        return 1 + max((c.cycle_number for c in existing), default=0)


class EnrolmentService:
    """UC-02 — enrol a client, create their login and open cycle 1 atomically."""

    def __init__(
        self,
        *,
        users: UserRepository,
        clients: ClientRepository,
        cycles: CycleService,
        audit: AuditRepository,
        uow: UnitOfWork,
        clock: Callable[[], date] = date.today,
    ) -> None:
        self._users = users
        self._clients = clients
        self._cycles = cycles
        self._audit = audit
        self._uow = uow
        self._clock = clock

    def enrol(
        self,
        *,
        actor: User,
        full_name: str,
        phone: str,
        daily_rate: Money,
        password_hash: str,
        business_type: str | None = None,
        location: str | None = None,
    ) -> tuple[Client, ContributionCycle]:
        from app.domain.entities import UserRole

        if not daily_rate.is_positive:
            raise DomainError("The agreed daily contribution must be more than zero.")

        # The client's own login is created here, not later: without it the
        # client cannot see their own record, which is the system's whole
        # purpose (BR-02). clients.user_id is NOT NULL for that reason.
        user = self._users.add(
            User(
                id=None,
                public_ref=uuid4(),
                full_name=full_name.strip(),
                phone=phone.strip(),
                role=UserRole.CLIENT,
            ),
            password_hash,
        )

        client = self._clients.add(
            Client(
                id=None,
                public_ref=uuid4(),  # BR-R14 — opaque QR reference
                user_id=user.id,
                collector_id=actor.id,
                full_name=full_name.strip(),
                phone=phone.strip(),
                daily_rate=daily_rate,
                business_type=business_type,
                location=location,
            )
        )

        cycle = self._cycles.open_for(
            client_id=client.id,
            daily_rate=client.daily_rate,
            start=self._clock(),
            cycle_number=1,
        )

        self._audit.append(
            actor_id=actor.id,
            action="ENROL_CLIENT",
            target_type="CLIENT",
            target_id=str(client.public_ref),
            detail={"daily_rate_pesewas": daily_rate.pesewas, "cycle_id": cycle.id},
        )
        self._uow.commit()
        return client, cycle


class CollectionService:
    """UC-03 record, UC-09 reverse, and the route sheet."""

    def __init__(
        self,
        *,
        clients: ClientRepository,
        cycles: CycleRepository,
        contributions: ContributionRepository,
        audit: AuditRepository,
        uow: UnitOfWork,
        clock: Callable[[], date] = date.today,
    ) -> None:
        self._clients = clients
        self._cycles = cycles
        self._contributions = contributions
        self._audit = audit
        self._uow = uow
        self._clock = clock

    # -- authorisation ---------------------------------------------------

    def _authorised_client(self, public_ref: UUID, actor: User) -> Client:
        """FR-05 / BR-R15.

        The QR reference identifies; it does not authorise. Possession of a
        reference gets you here and no further — the decision below consults
        the collector-client assignment, never the reference.
        """
        client = self._clients.get_by_public_ref(public_ref)
        if client is None:
            raise ClientNotFound("No client matches that reference.")

        if actor.is_supervisor or client.is_collected_by(actor.id):
            return client

        self._audit.append(
            actor_id=actor.id,
            action="AUTHORISATION_DENIED",
            target_type="CLIENT",
            target_id=str(public_ref),
            detail={"attempted": "record_contribution"},
        )
        self._uow.commit()
        raise NotAuthorised("This client is not on your route.")

    # -- UC-03 -----------------------------------------------------------

    def record(
        self,
        *,
        public_ref: UUID,
        actor: User,
        amount: Money | None = None,
        on: date | None = None,
    ) -> Contribution:
        client = self._authorised_client(public_ref, actor)
        today = self._clock()
        on = on or today

        cycle = self._cycles.active_for_client(client.id)
        if cycle is None:
            raise NoActiveCycle(
                f"{client.full_name} has no open cycle. A matured cycle must be "
                f"paid out before a new one opens."
            )

        amount = amount if amount is not None else cycle.daily_rate
        existing = self._contributions.list_for_cycle(cycle.id)

        # Every rule lives in the domain layer; this service only sequences.
        validate_contribution(
            cycle=cycle,
            contribution_date=on,
            amount=amount,
            existing=existing,
            today=today,
        )

        saved = self._contributions.add(
            Contribution(
                id=None,
                reference="",  # repository assigns (FR-30)
                cycle_id=cycle.id,
                contribution_date=on,
                amount=amount,
                recorded_by_id=actor.id,
            )
        )

        self._audit.append(
            actor_id=actor.id,
            action="RECORD_CONTRIBUTION",
            target_type="CONTRIBUTION",
            target_id=saved.reference,
            detail={
                "client_ref": str(client.public_ref),
                "amount_pesewas": amount.pesewas,
                "contribution_date": on.isoformat(),
            },
        )
        self._uow.commit()
        return saved

    # -- UC-09 -----------------------------------------------------------

    def reverse(self, *, reference: str, actor: User, reason: str) -> Contribution:
        """BR-R11 — correct by linked reversal, never by edit or delete.

        Resolves conflict C2 from the stakeholder analysis: the collector can
        fix an honest mistake, and the client's record stays non-repudiable
        because both entries remain visible.
        """
        if not actor.is_supervisor:
            raise NotAuthorised("Only a supervisor may reverse a contribution.")

        original = self._contributions.get_by_reference(reference)
        if original is None:
            raise ClientNotFound(f"No contribution found with reference {reference}.")
        if not original.is_effective:
            raise DomainError("That contribution has already been reversed.")

        reversal = self._contributions.add(
            Contribution(
                id=None,
                reference="",
                cycle_id=original.cycle_id,
                contribution_date=original.contribution_date,
                amount=original.amount,
                recorded_by_id=actor.id,
                is_reversal=True,
            )
        )
        self._contributions.mark_reversed(original.id, reversal.id)

        self._audit.append(
            actor_id=actor.id,
            action="REVERSE_CONTRIBUTION",
            target_type="CONTRIBUTION",
            target_id=original.reference,
            detail={"reversal_reference": reversal.reference, "reason": reason},
        )
        self._uow.commit()
        return reversal

    # -- FR-23 route sheet ------------------------------------------------

    def route_sheet(self, *, collector_id: int, on: date | None = None) -> list[RouteEntry]:
        """The collector's clients for a day, with collection status.

        TODO(TD-05): a flat list, unordered by geography and unfiltered by
          outstanding status. QR scanning (FR-40) bypasses this for the common
          case, which is why the reduced version was acceptable.
        """
        on = on or self._clock()
        clients = self._clients.list_for_collector(collector_id)
        collected = self._contributions.collected_dates_for_collector(collector_id, on)
        return [
            RouteEntry(
                client=c,
                collected_today=c.id in collected,
                cycle=self._cycles.active_for_client(c.id),
            )
            for c in clients
        ]

    # -- FR-16, FR-17 susu card ------------------------------------------

    def card_for(self, cycle: ContributionCycle) -> tuple[CycleSummary, list[Contribution]]:
        contributions = self._contributions.list_for_cycle(cycle.id)
        summary = compute_cycle_summary(
            cycle=cycle, contributions=contributions, today=self._clock()
        )
        return summary, contributions
