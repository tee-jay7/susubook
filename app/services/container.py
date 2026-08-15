"""Dependency wiring — the composition root.

The single place where abstractions are bound to implementations. Production
binds SQLAlchemy repositories; tests bind in-memory fakes. Nothing in
app/services or app/domain knows which it received (Dependency Inversion).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from sqlalchemy.orm import Session

from app.infrastructure.db import SqlAlchemyUnitOfWork
from app.infrastructure.repositories import (
    SqlAuditRepository,
    SqlClientRepository,
    SqlContributionRepository,
    SqlCycleRepository,
    SqlPasswordResetRepository,
    SqlPayoutRepository,
    SqlRemittanceRepository,
    SqlUserRepository,
)

from .collection import CollectionService, CycleService, EnrolmentService
from .notifications import NotificationService, NullSmsGateway, SmsGateway
from .passwords import PasswordService
from .payout import PayoutService
from .reconciliation import ReconciliationService
from .security import AuthService


@dataclass
class Services:
    auth: AuthService
    passwords: PasswordService
    notifications: NotificationService
    enrolment: EnrolmentService
    collection: CollectionService
    payout: PayoutService
    reconciliation: ReconciliationService
    cycles: SqlCycleRepository
    clients: SqlClientRepository
    contributions: SqlContributionRepository
    payouts: SqlPayoutRepository
    users: SqlUserRepository
    audit: SqlAuditRepository


def build_services(
    session: Session,
    *,
    clock: Callable[[], date] = date.today,
    notifications: NotificationService | None = None,
) -> Services:
    users = SqlUserRepository(session)
    clients = SqlClientRepository(session)
    cycles = SqlCycleRepository(session)
    contributions = SqlContributionRepository(session)
    payouts = SqlPayoutRepository(session)
    remittances = SqlRemittanceRepository(session)
    resets = SqlPasswordResetRepository(session)
    audit = SqlAuditRepository(session)
    uow = SqlAlchemyUnitOfWork(session)

    cycle_service = CycleService(cycles, clock=clock)
    # Defaults to a gateway that sends nothing, so a missing configuration can
    # never result in an accidental message (CR-002).
    notifier = notifications or NotificationService(NullSmsGateway())

    return Services(
        auth=AuthService(users, audit),
        passwords=PasswordService(
            users=users,
            resets=resets,
            audit=audit,
            uow=uow,
            notifications=notifier,
        ),
        notifications=notifier,
        enrolment=EnrolmentService(
            users=users,
            clients=clients,
            cycles=cycle_service,
            audit=audit,
            uow=uow,
            clock=clock,
        ),
        collection=CollectionService(
            clients=clients,
            cycles=cycles,
            contributions=contributions,
            audit=audit,
            uow=uow,
            clock=clock,
            users=users,
            notifications=notifier,
        ),
        payout=PayoutService(
            cycles=cycles,
            contributions=contributions,
            payouts=payouts,
            cycle_service=cycle_service,
            audit=audit,
            uow=uow,
            clock=clock,
        ),
        reconciliation=ReconciliationService(
            remittances=remittances,
            contributions=contributions,
            audit=audit,
            uow=uow,
            clock=clock,
        ),
        cycles=cycles,
        clients=clients,
        contributions=contributions,
        payouts=payouts,
        users=users,
        audit=audit,
    )
