"""SQLAlchemy ORM models — layer 4 (Infrastructure).

These are persistence records, not domain entities. Business rules live in
app/domain/rules.py and never import this module. The repositories translate
between the two (TD-07).

Three business invariants are enforced here a second time, by PostgreSQL
partial unique indexes:

  BR-R2   one ACTIVE cycle per client
  BR-R5   one effective contribution per client per date
  BR-R10  at most one payout per cycle

That duplication is deliberate defence in depth. The domain layer already
checks all three; the database makes them survive a service-layer bug or a
direct write. Partial indexes are the specific reason PostgreSQL was chosen
over MySQL — a reversed contribution must be allowed to coexist with its
replacement on the same date, which a plain unique constraint cannot express.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_ref: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4
    )
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('CLIENT','COLLECTOR','SUPERVISOR','ADMIN')", name="ck_user_role"
        ),
    )


class ClientModel(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    # BR-R14: opaque, non-sequential. This is the QR reference (FR-39) and the
    # only client identifier that ever appears in a URL.
    public_ref: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), unique=True, nullable=False
    )
    collector_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    business_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    daily_rate_pesewas: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("daily_rate_pesewas > 0", name="ck_client_rate_positive"),
    )


class ContributionCycleModel(Base):
    __tablename__ = "contribution_cycles"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="ACTIVE")
    # Snapshot at open: a later change to the client's rate must not
    # retroactively alter an in-flight cycle's arithmetic.
    daily_rate_pesewas: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("client_id", "cycle_number", name="uq_cycle_number"),
        CheckConstraint(
            "status IN ('ACTIVE','MATURED','PAID_OUT')", name="ck_cycle_status"
        ),
        CheckConstraint("end_date >= start_date", name="ck_cycle_dates"),
        # BR-R2 — at most one ACTIVE cycle per client.
        Index(
            "ux_active_cycle_per_client",
            "client_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
        Index("ix_cycle_client_status", "client_id", "status"),
    )


class ContributionModel(Base):
    __tablename__ = "contributions"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    cycle_id: Mapped[int] = mapped_column(
        ForeignKey("contribution_cycles.id"), nullable=False, index=True
    )
    contribution_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_pesewas: Mapped[int] = mapped_column(Integer, nullable=False)
    recorded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # BR-R11 — corrections are linked reversals, never edits or deletes.
    reversed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("contributions.id"), nullable=True
    )
    is_reversal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        CheckConstraint("amount_pesewas > 0", name="ck_contribution_positive"),
        # BR-R5 — one *effective* contribution per cycle per date. Partial, so a
        # reversed entry and its replacement may share a date.
        Index(
            "ux_effective_contribution_per_day",
            "cycle_id",
            "contribution_date",
            unique=True,
            postgresql_where=text("reversed_by_id IS NULL AND is_reversal = false"),
        ),
        # Daily variance computation (FR-25).
        Index("ix_contribution_collector_day", "recorded_by_id", "contribution_date"),
    )


class PayoutModel(Base):
    __tablename__ = "payouts"

    id: Mapped[int] = mapped_column(primary_key=True)
    # BR-R10 — unique, so a second payout is impossible at the storage layer.
    cycle_id: Mapped[int] = mapped_column(
        ForeignKey("contribution_cycles.id"), unique=True, nullable=False
    )
    total_collected_pesewas: Mapped[int] = mapped_column(Integer, nullable=False)
    commission_pesewas: Mapped[int] = mapped_column(Integer, nullable=False)
    net_payout_pesewas: Mapped[int] = mapped_column(Integer, nullable=False)
    released_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    released_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("net_payout_pesewas >= 0", name="ck_payout_not_negative"),
        CheckConstraint("commission_pesewas >= 0", name="ck_commission_not_negative"),
        # Money is conserved: what was collected is either paid out or retained.
        CheckConstraint(
            "net_payout_pesewas + commission_pesewas = total_collected_pesewas",
            name="ck_payout_balances",
        ),
    )


class RemittanceDeclarationModel(Base):
    __tablename__ = "remittance_declarations"

    id: Mapped[int] = mapped_column(primary_key=True)
    collector_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    declaration_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_declared_pesewas: Mapped[int] = mapped_column(Integer, nullable=False)
    declared_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "collector_id", "declaration_date", name="uq_declaration_per_day"
        ),
        CheckConstraint(
            "amount_declared_pesewas >= 0", name="ck_declaration_not_negative"
        ),
    )


class AuditLogModel(Base):
    """Append-only record of every state change (BR-05, NFR-09).

    HACK(TD-09): append-only is enforced by convention — nothing in the
      application updates or deletes rows here — rather than by revoking
      UPDATE and DELETE from the application role, or by a rule/trigger.
      A compromised application account could therefore rewrite history.
      See docs/08-technical-debt.md.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    target_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    __table_args__ = (Index("ix_audit_target", "target_type", "target_id"),)
