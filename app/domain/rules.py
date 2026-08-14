"""Business rules BR-R1 .. R15 as pure functions.

Every rule in SRS section 3.2 is implemented here and nowhere else. These
functions take and return values only -- no database, no session, no request
context -- so they are unit-testable in milliseconds (NFR-07).

Three of these rules (BR-R2, BR-R5, BR-R10) are additionally enforced by
PostgreSQL partial unique indexes. That duplication is deliberate defence in
depth: a bug in the service layer, or a future direct database write, cannot
corrupt the invariant. See docs/07-system-analysis-and-design.md section 7.11.

Layer 3 (Domain).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, Protocol

from .entities import (
    Contribution,
    ContributionCycle,
    CycleStatus,
    CycleSummary,
    Payout,
)
from .errors import (
    ContributionDateInFuture,
    ContributionDateOutsideCycle,
    CycleAlreadyPaidOut,
    CycleClosed,
    CycleNotMatured,
    DuplicateContribution,
    InvalidContributionAmount,
)
from .money import Money

DEFAULT_CYCLE_LENGTH_DAYS = 31
"""Traditional susu card length -- 31 boxes, one per day.

TODO(TD-13): institutional configuration (FR-36) is deferred, so this is a
  module constant rather than a setting. Cycles snapshot their own length at
  open, so making it configurable later will not disturb existing cycles.
"""


# ---------------------------------------------------------------------------
# Commission policy -- Strategy pattern, the Open/Closed extension point
# for FR-36 (configurable commission), which is deferred.
# ---------------------------------------------------------------------------


class CommissionPolicy(Protocol):
    def commission_for(self, total_collected: Money, daily_rate: Money) -> Money: ...


class OneDayRatePolicy:
    """BR-R8 / BR-R9: commission is one day's contribution.

    Where the total collected does not exceed one day's rate, the whole
    balance is retained and the client receives nothing. Expressing this as
    `min(rate, total)` makes a negative payout unrepresentable rather than
    merely unlikely -- the defect BR-R9 exists to prevent.
    """

    def commission_for(self, total_collected: Money, daily_rate: Money) -> Money:
        return min(daily_rate, total_collected)


DEFAULT_COMMISSION_POLICY: CommissionPolicy = OneDayRatePolicy()


# ---------------------------------------------------------------------------
# Cycle lifecycle
# ---------------------------------------------------------------------------


def cycle_end_date(start: date, length_days: int = DEFAULT_CYCLE_LENGTH_DAYS) -> date:
    """Inclusive end date of a cycle beginning on `start`."""
    if length_days < 1:
        raise ValueError("A cycle must be at least one day long.")
    return start + timedelta(days=length_days - 1)


def effective_contributions(
    contributions: Iterable[Contribution],
) -> list[Contribution]:
    """BR-R11: reversed entries and the reversals themselves do not count."""
    return [c for c in contributions if c.is_effective]


# ---------------------------------------------------------------------------
# BR-R3 .. BR-R7 -- validating a contribution before it is recorded
# ---------------------------------------------------------------------------


def validate_contribution(
    *,
    cycle: ContributionCycle,
    contribution_date: date,
    amount: Money,
    existing: Iterable[Contribution],
    today: date,
    days_covered: int = 1,
) -> None:
    """Raise a DomainError if this contribution may not be recorded.

    Returns None on success. Rules are checked in the order that produces the
    most useful message: state first, then date, then duplication, then amount.

    `days_covered` is 1 for an ordinary daily contribution. FR-15 (catch-up
    payment covering several missed days) is deferred from this release, but
    the rule is parameterised so that enabling it needs no change here -- only
    an allocation step in the service layer.
    """
    # BR-R6 -- cycle must be open
    if not cycle.accepts_contributions:
        raise CycleClosed(
            f"This cycle is {cycle.status.value.replace('_', ' ').lower()} and "
            f"no longer accepts contributions."
        )

    # BR-R4 -- not in the future
    if contribution_date > today:
        raise ContributionDateInFuture(
            f"Cannot record a contribution dated {contribution_date:%d %b %Y}; "
            f"that date has not yet arrived."
        )

    # BR-R3 -- within the cycle
    if not cycle.covers(contribution_date):
        raise ContributionDateOutsideCycle(
            f"{contribution_date:%d %b %Y} falls outside this cycle "
            f"({cycle.start_date:%d %b} to {cycle.end_date:%d %b %Y})."
        )

    # BR-R5 -- no duplicate for the day
    for existing_contribution in effective_contributions(existing):
        if existing_contribution.contribution_date == contribution_date:
            raise DuplicateContribution(
                f"A contribution for {contribution_date:%d %b %Y} was already "
                f"recorded (reference {existing_contribution.reference}).",
                existing_reference=existing_contribution.reference,
            )

    # BR-R7 -- positive whole multiple of the daily rate
    if not amount.is_positive:
        raise InvalidContributionAmount(
            f"A contribution must be a positive amount; got {amount}."
        )
    expected = cycle.daily_rate * days_covered
    if amount != expected:
        raise InvalidContributionAmount(
            f"Expected {expected} for {days_covered} day(s) at a daily rate of "
            f"{cycle.daily_rate}, but got {amount}. Contributions must be a "
            f"whole multiple of the agreed daily rate."
        )


# ---------------------------------------------------------------------------
# BR-R12, BR-R17 -- summarising a cycle (FR-17)
# ---------------------------------------------------------------------------


def compute_cycle_summary(
    *,
    cycle: ContributionCycle,
    contributions: Iterable[Contribution],
    today: date,
    policy: CommissionPolicy = DEFAULT_COMMISSION_POLICY,
) -> CycleSummary:
    """Derive days paid/missed/pending and the projected payout.

    FIXME(TD-11): recomputed from the full contribution list on every render.
      Bounded at 31 rows per cycle so it is not a present problem, but it is
      an O(n) read where a denormalised running total would be O(1). Revisit
      if cycle length ever becomes configurable beyond a month.
    """
    effective = effective_contributions(contributions)
    paid_dates = frozenset(c.contribution_date for c in effective)

    total = Money.zero()
    for contribution in effective:
        total = total + contribution.amount

    days_in_cycle = cycle.length_in_days
    days_elapsed = cycle.days_elapsed_on(today)
    days_paid = len(paid_dates)
    days_missed = max(0, days_elapsed - days_paid)
    days_pending = max(0, days_in_cycle - days_elapsed)

    commission = policy.commission_for(total, cycle.daily_rate)
    projected = total - commission

    return CycleSummary(
        days_in_cycle=days_in_cycle,
        days_elapsed=days_elapsed,
        days_paid=days_paid,
        days_missed=days_missed,
        days_pending=days_pending,
        total_collected=total,
        commission=commission,
        projected_payout=projected,
        paid_dates=paid_dates,
    )


# ---------------------------------------------------------------------------
# BR-R8, BR-R9, BR-R10 -- payout (UC-07)
# ---------------------------------------------------------------------------


def compute_payout(
    *,
    cycle: ContributionCycle,
    contributions: Iterable[Contribution],
    released_by_id: int,
    today: date,
    already_paid: bool = False,
    policy: CommissionPolicy = DEFAULT_COMMISSION_POLICY,
) -> Payout:
    """Compute the settlement for a matured cycle.

    Raises rather than returning a sentinel, because every failure here is a
    business rule violation the user must be told about, not a value to branch
    on.
    """
    # BR-R10 -- at most one payout
    if already_paid or cycle.status is CycleStatus.PAID_OUT:
        raise CycleAlreadyPaidOut(
            "This cycle has already been paid out; a second payout cannot be "
            "released."
        )

    # BR-R12 -- must have matured
    if not cycle.is_mature_on(today) and cycle.status is not CycleStatus.MATURED:
        raise CycleNotMatured(
            f"This cycle matures on {cycle.end_date:%d %b %Y}. Use an early "
            f"withdrawal request to release funds before then."
        )

    total = Money.zero()
    for contribution in effective_contributions(contributions):
        total = total + contribution.amount

    commission = policy.commission_for(total, cycle.daily_rate)
    net = total - commission

    # Guard the invariant the whole rule exists to protect. If this ever
    # trips, the policy is wrong -- fail loudly rather than pay a negative.
    if net.is_negative:
        raise AssertionError(
            f"Computed a negative payout ({net}) from total {total} and "
            f"commission {commission}; commission policy is invalid."
        )

    return Payout(
        id=None,
        cycle_id=cycle.id,
        total_collected=total,
        commission=commission,
        net_payout=net,
        released_by_id=released_by_id,
    )


# ---------------------------------------------------------------------------
# BR-R13 -- daily reconciliation (FR-25)
# ---------------------------------------------------------------------------


def compute_variance(*, total_recorded: Money, amount_declared: Money | None) -> Money:
    """Recorded in the field minus cash declared at the branch.

    Positive means the collector recorded more than they banked -- the case
    that matters (BR-01). Negative means they banked more than they recorded,
    which is also a discrepancy worth a supervisor's attention.
    """
    return total_recorded - (amount_declared or Money.zero())
