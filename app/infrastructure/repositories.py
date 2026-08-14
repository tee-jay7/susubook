"""SQLAlchemy implementations of the repository Protocols — layer 4.

Also the translation boundary between persistence records and domain
entities.

TODO(TD-07): the _to_* mapping functions below are hand-written, so every
  schema change must be made in two places (model and mapper) and they can
  drift silently. This is the acknowledged cost of keeping the domain layer
  framework-free (NFR-07); the alternative — SQLAlchemy imperative mapping
  onto the dataclasses — was not affordable in the examination window.
  See docs/08-technical-debt.md.
"""

from __future__ import annotations

import secrets
from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.entities import (
    Client,
    Contribution,
    ContributionCycle,
    CycleStatus,
    DailyVariance,
    Payout,
    RemittanceDeclaration,
    User,
    UserRole,
)
from app.domain.money import Money

from .models import (
    AuditLogModel,
    ClientModel,
    ContributionCycleModel,
    ContributionModel,
    PayoutModel,
    RemittanceDeclarationModel,
    UserModel,
)

# ---------------------------------------------------------------------------
# Mapping: persistence record -> domain entity  (TD-07)
# ---------------------------------------------------------------------------


def _to_user(m: UserModel) -> User:
    return User(
        id=m.id,
        public_ref=m.public_ref,
        full_name=m.full_name,
        phone=m.phone,
        email=m.email,
        role=UserRole(m.role),
        is_active=m.is_active,
        created_at=m.created_at,
    )


def _to_client(m: ClientModel) -> Client:
    return Client(
        id=m.id,
        public_ref=m.public_ref,
        user_id=m.user_id,
        collector_id=m.collector_id,
        full_name=m.full_name,
        phone=m.phone,
        daily_rate=Money(m.daily_rate_pesewas),
        business_type=m.business_type,
        location=m.location,
        is_active=m.is_active,
    )


def _to_cycle(m: ContributionCycleModel) -> ContributionCycle:
    return ContributionCycle(
        id=m.id,
        client_id=m.client_id,
        cycle_number=m.cycle_number,
        start_date=m.start_date,
        end_date=m.end_date,
        status=CycleStatus(m.status),
        daily_rate=Money(m.daily_rate_pesewas),
    )


def _to_contribution(m: ContributionModel) -> Contribution:
    return Contribution(
        id=m.id,
        reference=m.reference,
        cycle_id=m.cycle_id,
        contribution_date=m.contribution_date,
        amount=Money(m.amount_pesewas),
        recorded_by_id=m.recorded_by_id,
        recorded_at=m.recorded_at,
        reversed_by_id=m.reversed_by_id,
        is_reversal=m.is_reversal,
    )


def _to_payout(m: PayoutModel) -> Payout:
    return Payout(
        id=m.id,
        cycle_id=m.cycle_id,
        total_collected=Money(m.total_collected_pesewas),
        commission=Money(m.commission_pesewas),
        net_payout=Money(m.net_payout_pesewas),
        released_by_id=m.released_by_id,
        released_at=m.released_at,
    )


def _to_declaration(m: RemittanceDeclarationModel) -> RemittanceDeclaration:
    return RemittanceDeclaration(
        id=m.id,
        collector_id=m.collector_id,
        declaration_date=m.declaration_date,
        amount_declared=Money(m.amount_declared_pesewas),
        declared_at=m.declared_at,
    )


def new_reference() -> str:
    """Human-quotable receipt reference (FR-30).

    Crockford-ish alphabet: no I, L, O or U, so a client reading a reference
    over the phone cannot confuse it with 1, 0 or produce an unintended word.
    """
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    body = "".join(secrets.choice(alphabet) for _ in range(8))
    return f"SB-{body[:4]}-{body[4:]}"


# ---------------------------------------------------------------------------
# Repositories
# ---------------------------------------------------------------------------


class SqlUserRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get_by_id(self, user_id: int) -> User | None:
        m = self._s.get(UserModel, user_id)
        return _to_user(m) if m else None

    def find_credentials(self, phone: str) -> tuple[User, str] | None:
        m = self._s.scalar(select(UserModel).where(UserModel.phone == phone))
        if m is None or not m.is_active:
            return None
        return _to_user(m), m.password_hash

    def add(self, user: User, password_hash: str) -> User:
        m = UserModel(
            public_ref=user.public_ref,
            full_name=user.full_name,
            phone=user.phone,
            email=user.email,
            password_hash=password_hash,
            role=user.role.value,
            is_active=user.is_active,
        )
        self._s.add(m)
        self._s.flush()
        return _to_user(m)

    def list_collectors(self) -> list[User]:
        rows = self._s.scalars(
            select(UserModel)
            .where(UserModel.role == UserRole.COLLECTOR.value)
            .order_by(UserModel.full_name)
        ).all()
        return [_to_user(m) for m in rows]


class SqlClientRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get_by_id(self, client_id: int) -> Client | None:
        m = self._s.get(ClientModel, client_id)
        return _to_client(m) if m else None

    def get_by_public_ref(self, public_ref: UUID) -> Client | None:
        m = self._s.scalar(
            select(ClientModel).where(ClientModel.public_ref == public_ref)
        )
        return _to_client(m) if m else None

    def get_by_user_id(self, user_id: int) -> Client | None:
        m = self._s.scalar(select(ClientModel).where(ClientModel.user_id == user_id))
        return _to_client(m) if m else None

    def list_for_collector(self, collector_id: int) -> list[Client]:
        rows = self._s.scalars(
            select(ClientModel)
            .where(
                ClientModel.collector_id == collector_id,
                ClientModel.is_active.is_(True),
            )
            .order_by(ClientModel.full_name)
        ).all()
        return [_to_client(m) for m in rows]

    def add(self, client: Client) -> Client:
        m = ClientModel(
            public_ref=client.public_ref,
            user_id=client.user_id,
            collector_id=client.collector_id,
            full_name=client.full_name,
            phone=client.phone,
            business_type=client.business_type,
            location=client.location,
            daily_rate_pesewas=client.daily_rate.pesewas,
            is_active=client.is_active,
        )
        self._s.add(m)
        self._s.flush()
        return _to_client(m)


class SqlCycleRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get_by_id(self, cycle_id: int) -> ContributionCycle | None:
        m = self._s.get(ContributionCycleModel, cycle_id)
        return _to_cycle(m) if m else None

    def active_for_client(self, client_id: int) -> ContributionCycle | None:
        m = self._s.scalar(
            select(ContributionCycleModel).where(
                ContributionCycleModel.client_id == client_id,
                ContributionCycleModel.status == CycleStatus.ACTIVE.value,
            )
        )
        return _to_cycle(m) if m else None

    def list_for_client(self, client_id: int) -> list[ContributionCycle]:
        rows = self._s.scalars(
            select(ContributionCycleModel)
            .where(ContributionCycleModel.client_id == client_id)
            .order_by(ContributionCycleModel.cycle_number.desc())
        ).all()
        return [_to_cycle(m) for m in rows]

    def list_due_for_payout(self, today: date) -> list[tuple[ContributionCycle, Client]]:
        """Cycles past their end date with no payout yet (UC-07).

        BR-R12 maturity is evaluated here rather than by a scheduled job
        (TD-10): free-tier hosting provides no scheduler, so a cycle becomes
        visible as matured when a supervisor looks, not at midnight.
        """
        rows = self._s.execute(
            select(ContributionCycleModel, ClientModel)
            .join(ClientModel, ClientModel.id == ContributionCycleModel.client_id)
            .outerjoin(PayoutModel, PayoutModel.cycle_id == ContributionCycleModel.id)
            .where(
                ContributionCycleModel.end_date < today,
                ContributionCycleModel.status != CycleStatus.PAID_OUT.value,
                PayoutModel.id.is_(None),
            )
            .order_by(ContributionCycleModel.end_date)
        ).all()
        return [(_to_cycle(c), _to_client(cl)) for c, cl in rows]

    def add(self, cycle: ContributionCycle) -> ContributionCycle:
        m = ContributionCycleModel(
            client_id=cycle.client_id,
            cycle_number=cycle.cycle_number,
            start_date=cycle.start_date,
            end_date=cycle.end_date,
            status=cycle.status.value,
            daily_rate_pesewas=cycle.daily_rate.pesewas,
        )
        self._s.add(m)
        self._s.flush()
        return _to_cycle(m)

    def set_status(self, cycle_id: int, status: str) -> None:
        m = self._s.get(ContributionCycleModel, cycle_id)
        if m is not None:
            m.status = status
            self._s.flush()


class SqlContributionRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def list_for_cycle(self, cycle_id: int) -> list[Contribution]:
        rows = self._s.scalars(
            select(ContributionModel)
            .where(ContributionModel.cycle_id == cycle_id)
            .order_by(ContributionModel.contribution_date)
        ).all()
        return [_to_contribution(m) for m in rows]

    def get_by_reference(self, reference: str) -> Contribution | None:
        m = self._s.scalar(
            select(ContributionModel).where(ContributionModel.reference == reference)
        )
        return _to_contribution(m) if m else None

    def add(self, contribution: Contribution) -> Contribution:
        m = ContributionModel(
            reference=contribution.reference or new_reference(),
            cycle_id=contribution.cycle_id,
            contribution_date=contribution.contribution_date,
            amount_pesewas=contribution.amount.pesewas,
            recorded_by_id=contribution.recorded_by_id,
            reversed_by_id=contribution.reversed_by_id,
            is_reversal=contribution.is_reversal,
        )
        self._s.add(m)
        self._s.flush()
        return _to_contribution(m)

    def mark_reversed(self, contribution_id: int, reversal_id: int) -> None:
        m = self._s.get(ContributionModel, contribution_id)
        if m is not None:
            m.reversed_by_id = reversal_id
            self._s.flush()

    def total_recorded_by(self, collector_id: int, on: date) -> Money:
        """Sum of effective contributions recorded by a collector on a date."""
        total = self._s.scalar(
            select(func.coalesce(func.sum(ContributionModel.amount_pesewas), 0)).where(
                ContributionModel.recorded_by_id == collector_id,
                ContributionModel.contribution_date == on,
                ContributionModel.reversed_by_id.is_(None),
                ContributionModel.is_reversal.is_(False),
            )
        )
        return Money(int(total or 0))

    def collected_dates_for_collector(self, collector_id: int, on: date) -> set[int]:
        rows = self._s.execute(
            select(ContributionCycleModel.client_id)
            .join(
                ContributionModel,
                ContributionModel.cycle_id == ContributionCycleModel.id,
            )
            .where(
                ContributionModel.recorded_by_id == collector_id,
                ContributionModel.contribution_date == on,
                ContributionModel.reversed_by_id.is_(None),
                ContributionModel.is_reversal.is_(False),
            )
        ).all()
        return {r[0] for r in rows}


class SqlPayoutRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get_for_cycle(self, cycle_id: int) -> Payout | None:
        m = self._s.scalar(select(PayoutModel).where(PayoutModel.cycle_id == cycle_id))
        return _to_payout(m) if m else None

    def add(self, payout: Payout) -> Payout:
        m = PayoutModel(
            cycle_id=payout.cycle_id,
            total_collected_pesewas=payout.total_collected.pesewas,
            commission_pesewas=payout.commission.pesewas,
            net_payout_pesewas=payout.net_payout.pesewas,
            released_by_id=payout.released_by_id,
        )
        self._s.add(m)
        self._s.flush()
        return _to_payout(m)


class SqlRemittanceRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get(self, collector_id: int, on: date) -> RemittanceDeclaration | None:
        m = self._s.scalar(
            select(RemittanceDeclarationModel).where(
                RemittanceDeclarationModel.collector_id == collector_id,
                RemittanceDeclarationModel.declaration_date == on,
            )
        )
        return _to_declaration(m) if m else None

    def save(self, declaration: RemittanceDeclaration) -> RemittanceDeclaration:
        m = self._s.scalar(
            select(RemittanceDeclarationModel).where(
                RemittanceDeclarationModel.collector_id == declaration.collector_id,
                RemittanceDeclarationModel.declaration_date
                == declaration.declaration_date,
            )
        )
        if m is None:
            m = RemittanceDeclarationModel(
                collector_id=declaration.collector_id,
                declaration_date=declaration.declaration_date,
                amount_declared_pesewas=declaration.amount_declared.pesewas,
            )
            self._s.add(m)
        else:
            # Re-declaring the same day overwrites; the audit log retains both.
            m.amount_declared_pesewas = declaration.amount_declared.pesewas
        self._s.flush()
        return _to_declaration(m)

    def variances_for(self, on: date) -> list[DailyVariance]:
        """One row per collector: recorded in the field vs cash declared (FR-25)."""
        recorded = (
            select(
                ContributionModel.recorded_by_id.label("collector_id"),
                func.sum(ContributionModel.amount_pesewas).label("total"),
            )
            .where(
                ContributionModel.contribution_date == on,
                ContributionModel.reversed_by_id.is_(None),
                ContributionModel.is_reversal.is_(False),
            )
            .group_by(ContributionModel.recorded_by_id)
            .subquery()
        )

        rows = self._s.execute(
            select(
                UserModel.id,
                UserModel.full_name,
                func.coalesce(recorded.c.total, 0),
                RemittanceDeclarationModel.amount_declared_pesewas,
            )
            .select_from(UserModel)
            .outerjoin(recorded, recorded.c.collector_id == UserModel.id)
            .outerjoin(
                RemittanceDeclarationModel,
                (RemittanceDeclarationModel.collector_id == UserModel.id)
                & (RemittanceDeclarationModel.declaration_date == on),
            )
            .where(UserModel.role == UserRole.COLLECTOR.value)
            .order_by(UserModel.full_name)
        ).all()

        return [
            DailyVariance(
                collector_id=cid,
                collector_name=name,
                on_date=on,
                total_recorded=Money(int(total or 0)),
                amount_declared=None if declared is None else Money(int(declared)),
            )
            for cid, name, total, declared in rows
        ]


class SqlAuditRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def append(
        self,
        *,
        actor_id: int | None,
        action: str,
        target_type: str,
        target_id: str | None = None,
        detail: dict | None = None,
    ) -> None:
        self._s.add(
            AuditLogModel(
                actor_id=actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                detail=detail,
            )
        )
        self._s.flush()

    def list_for_target(self, target_type: str, target_id: str) -> list[dict]:
        rows = self._s.scalars(
            select(AuditLogModel)
            .where(
                AuditLogModel.target_type == target_type,
                AuditLogModel.target_id == target_id,
            )
            .order_by(AuditLogModel.occurred_at.desc())
        ).all()
        return [
            {
                "actor_id": r.actor_id,
                "action": r.action,
                "target_type": r.target_type,
                "target_id": r.target_id,
                "detail": r.detail,
                "occurred_at": r.occurred_at,
            }
            for r in rows
        ]
