"""Factories for domain unit tests.

Plain constructors -- no database, no ORM, no fixtures library. This is the
practical dividend of keeping the domain layer framework-free (NFR-07).
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest

from app.domain.entities import (
    Client,
    Contribution,
    ContributionCycle,
    CycleStatus,
)
from app.domain.money import Money
from app.domain.rules import cycle_end_date

TODAY = date(2026, 9, 15)
CYCLE_START = date(2026, 9, 1)
DAILY_RATE = Money.from_cedis("10.00")


def make_cycle(
    *,
    start: date = CYCLE_START,
    length: int = 31,
    status: CycleStatus = CycleStatus.ACTIVE,
    rate: Money = DAILY_RATE,
    cycle_id: int = 1,
    client_id: int = 1,
    cycle_number: int = 1,
) -> ContributionCycle:
    return ContributionCycle(
        id=cycle_id,
        client_id=client_id,
        cycle_number=cycle_number,
        start_date=start,
        end_date=cycle_end_date(start, length),
        status=status,
        daily_rate=rate,
    )


def make_contribution(
    *,
    on: date,
    amount: Money = DAILY_RATE,
    cycle_id: int = 1,
    reference: str | None = None,
    contribution_id: int = 1,
    recorded_by_id: int = 7,
    reversed_by_id: int | None = None,
    is_reversal: bool = False,
) -> Contribution:
    return Contribution(
        id=contribution_id,
        reference=reference or f"SB-{on:%d%m}-{contribution_id:04d}",
        cycle_id=cycle_id,
        contribution_date=on,
        amount=amount,
        recorded_by_id=recorded_by_id,
        reversed_by_id=reversed_by_id,
        is_reversal=is_reversal,
    )


def contributions_for_days(
    n: int, *, start: date = CYCLE_START, rate: Money = DAILY_RATE
) -> list[Contribution]:
    """n consecutive daily contributions from `start`."""
    return [
        make_contribution(on=start + timedelta(days=i), amount=rate, contribution_id=i + 1)
        for i in range(n)
    ]


def make_client(
    *,
    client_id: int = 1,
    collector_id: int = 7,
    rate: Money = DAILY_RATE,
) -> Client:
    return Client(
        id=client_id,
        public_ref=uuid4(),
        user_id=100 + client_id,
        collector_id=collector_id,
        full_name="Kofi Boateng",
        phone="0244000001",
        daily_rate=rate,
        business_type="Kiosk",
        location="Madina Market",
    )


@pytest.fixture
def today() -> date:
    return TODAY


@pytest.fixture
def rate() -> Money:
    return DAILY_RATE


@pytest.fixture
def active_cycle() -> ContributionCycle:
    return make_cycle()
