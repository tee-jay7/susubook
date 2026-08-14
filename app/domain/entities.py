"""Domain entities as plain dataclasses.

These are deliberately *not* SQLAlchemy models. Keeping them framework-free is
what allows every business rule to be unit-tested without a database (NFR-07),
which in turn is what makes a real test suite affordable inside the
examination window.

The cost of that separation is hand-written mapping at the repository
boundary -- recorded as TD-07.

Layer 3 (Domain).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from uuid import UUID

from .money import Money


class UserRole(str, Enum):
    CLIENT = "CLIENT"
    COLLECTOR = "COLLECTOR"
    SUPERVISOR = "SUPERVISOR"
    ADMIN = "ADMIN"


class CycleStatus(str, Enum):
    ACTIVE = "ACTIVE"
    MATURED = "MATURED"
    PAID_OUT = "PAID_OUT"


@dataclass
class User:
    id: int | None
    public_ref: UUID
    full_name: str
    phone: str
    role: UserRole
    is_active: bool = True
    email: str | None = None
    created_at: datetime | None = None

    @property
    def is_collector(self) -> bool:
        return self.role is UserRole.COLLECTOR

    @property
    def is_supervisor(self) -> bool:
        return self.role in (UserRole.SUPERVISOR, UserRole.ADMIN)


@dataclass
class Client:
    """A saver. `public_ref` is the opaque QR reference (BR-R14)."""

    id: int | None
    public_ref: UUID
    user_id: int
    collector_id: int
    full_name: str
    phone: str
    daily_rate: Money
    business_type: str | None = None
    location: str | None = None
    is_active: bool = True

    def is_collected_by(self, collector_id: int) -> bool:
        """FR-05 / BR-R15 -- authorisation never consults the QR reference."""
        return self.collector_id == collector_id


@dataclass
class ContributionCycle:
    id: int | None
    client_id: int
    cycle_number: int
    start_date: date
    end_date: date
    status: CycleStatus
    daily_rate: Money  # snapshot at open: a later rate change must not
    # retroactively alter an in-flight cycle's arithmetic

    @property
    def length_in_days(self) -> int:
        return (self.end_date - self.start_date).days + 1

    def covers(self, on: date) -> bool:
        """BR-R3."""
        return self.start_date <= on <= self.end_date

    def is_mature_on(self, today: date) -> bool:
        """BR-R12: maturity is reached once the end date has passed."""
        return today > self.end_date

    @property
    def accepts_contributions(self) -> bool:
        """BR-R6."""
        return self.status is CycleStatus.ACTIVE

    def days_elapsed_on(self, today: date) -> int:
        """Days of this cycle that have already occurred, capped at its length."""
        if today < self.start_date:
            return 0
        last = min(today, self.end_date)
        return (last - self.start_date).days + 1


@dataclass
class Contribution:
    id: int | None
    reference: str
    cycle_id: int
    contribution_date: date
    amount: Money
    recorded_by_id: int
    recorded_at: datetime | None = None
    reversed_by_id: int | None = None
    is_reversal: bool = False

    @property
    def is_effective(self) -> bool:
        """Counts toward the balance: neither reversed nor itself a reversal."""
        return self.reversed_by_id is None and not self.is_reversal


@dataclass
class Payout:
    id: int | None
    cycle_id: int
    total_collected: Money
    commission: Money
    net_payout: Money
    released_by_id: int
    released_at: datetime | None = None


@dataclass
class RemittanceDeclaration:
    id: int | None
    collector_id: int
    declaration_date: date
    amount_declared: Money
    declared_at: datetime | None = None


@dataclass(frozen=True)
class CycleSummary:
    """Derived view of a cycle. Computed, never stored (see TD-11)."""

    days_in_cycle: int
    days_elapsed: int
    days_paid: int
    days_missed: int
    days_pending: int
    total_collected: Money
    commission: Money
    projected_payout: Money
    paid_dates: frozenset[date] = field(default_factory=frozenset)

    def state_of(self, day: date, today: date) -> str:
        """Render state for one box on the susu card (FR-16)."""
        if day in self.paid_dates:
            return "paid"
        return "missed" if day <= today else "pending"


@dataclass
class DailyVariance:
    """BR-R13 -- one collector, one day."""

    collector_id: int
    collector_name: str
    on_date: date
    total_recorded: Money
    amount_declared: Money | None

    @property
    def variance(self) -> Money:
        declared = self.amount_declared or Money.zero()
        return self.total_recorded - declared

    @property
    def is_reconciled(self) -> bool:
        return self.amount_declared is not None and self.variance.is_zero
