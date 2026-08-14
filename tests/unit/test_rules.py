"""Unit tests for business rules BR-R3 .. BR-R13.

Each test names the rule it exercises so the testing report can be traced
back to the SRS. No database is involved.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.domain.entities import CycleStatus
from app.domain.errors import (
    ContributionDateInFuture,
    ContributionDateOutsideCycle,
    CycleAlreadyPaidOut,
    CycleClosed,
    CycleNotMatured,
    DuplicateContribution,
    InvalidContributionAmount,
)
from app.domain.money import Money
from app.domain.rules import (
    OneDayRatePolicy,
    compute_cycle_summary,
    compute_payout,
    compute_variance,
    cycle_end_date,
    effective_contributions,
    validate_contribution,
)

from .conftest import (
    CYCLE_START,
    DAILY_RATE,
    TODAY,
    contributions_for_days,
    make_contribution,
    make_cycle,
)


class TestCycleDates:
    def test_31_day_cycle_is_inclusive(self):
        """A 31-box card starting 1 Sep ends 1 Oct, not 2 Oct."""
        assert cycle_end_date(date(2026, 9, 1), 31) == date(2026, 10, 1)

    def test_single_day_cycle(self):
        assert cycle_end_date(date(2026, 9, 1), 1) == date(2026, 9, 1)

    def test_rejects_zero_length(self):
        with pytest.raises(ValueError):
            cycle_end_date(date(2026, 9, 1), 0)

    def test_length_in_days(self):
        assert make_cycle(length=31).length_in_days == 31


class TestValidateContributionHappyPath:
    def test_accepts_valid_contribution(self, active_cycle, today):
        validate_contribution(
            cycle=active_cycle,
            contribution_date=today,
            amount=DAILY_RATE,
            existing=[],
            today=today,
        )

    def test_accepts_contribution_on_first_day(self, active_cycle):
        validate_contribution(
            cycle=active_cycle,
            contribution_date=CYCLE_START,
            amount=DAILY_RATE,
            existing=[],
            today=TODAY,
        )

    def test_accepts_contribution_on_last_day(self, active_cycle):
        validate_contribution(
            cycle=active_cycle,
            contribution_date=active_cycle.end_date,
            amount=DAILY_RATE,
            existing=[],
            today=active_cycle.end_date,
        )


class TestBR_R6_CycleMustBeOpen:
    @pytest.mark.parametrize("status", [CycleStatus.MATURED, CycleStatus.PAID_OUT])
    def test_rejects_contribution_to_closed_cycle(self, status, today):
        cycle = make_cycle(status=status)
        with pytest.raises(CycleClosed):
            validate_contribution(
                cycle=cycle,
                contribution_date=today,
                amount=DAILY_RATE,
                existing=[],
                today=today,
            )


class TestBR_R4_NoFutureDates:
    def test_rejects_tomorrow(self, active_cycle, today):
        with pytest.raises(ContributionDateInFuture):
            validate_contribution(
                cycle=active_cycle,
                contribution_date=today + timedelta(days=1),
                amount=DAILY_RATE,
                existing=[],
                today=today,
            )

    def test_accepts_today(self, active_cycle, today):
        validate_contribution(
            cycle=active_cycle,
            contribution_date=today,
            amount=DAILY_RATE,
            existing=[],
            today=today,
        )


class TestBR_R3_DateWithinCycle:
    def test_rejects_date_before_cycle_start(self, active_cycle, today):
        with pytest.raises(ContributionDateOutsideCycle):
            validate_contribution(
                cycle=active_cycle,
                contribution_date=CYCLE_START - timedelta(days=1),
                amount=DAILY_RATE,
                existing=[],
                today=today,
            )

    def test_rejects_date_after_cycle_end(self, active_cycle):
        after = active_cycle.end_date + timedelta(days=1)
        with pytest.raises(ContributionDateOutsideCycle):
            validate_contribution(
                cycle=active_cycle,
                contribution_date=after,
                amount=DAILY_RATE,
                existing=[],
                today=after,
            )


class TestBR_R5_NoDuplicatePerDay:
    def test_rejects_second_contribution_same_day(self, active_cycle, today):
        existing = [make_contribution(on=today, reference="SB-EXISTING")]
        with pytest.raises(DuplicateContribution) as excinfo:
            validate_contribution(
                cycle=active_cycle,
                contribution_date=today,
                amount=DAILY_RATE,
                existing=existing,
                today=today,
            )
        assert excinfo.value.existing_reference == "SB-EXISTING"

    def test_allows_contribution_on_a_different_day(self, active_cycle, today):
        existing = [make_contribution(on=today - timedelta(days=1))]
        validate_contribution(
            cycle=active_cycle,
            contribution_date=today,
            amount=DAILY_RATE,
            existing=existing,
            today=today,
        )

    def test_reversed_contribution_does_not_block_a_replacement(
        self, active_cycle, today
    ):
        """BR-R11: a reversed entry is not effective, so the day is free again.

        This is the whole point of correcting by reversal rather than by edit.
        """
        reversed_entry = make_contribution(on=today, reversed_by_id=99)
        validate_contribution(
            cycle=active_cycle,
            contribution_date=today,
            amount=DAILY_RATE,
            existing=[reversed_entry],
            today=today,
        )

    def test_reversal_entry_itself_does_not_block(self, active_cycle, today):
        reversal = make_contribution(on=today, is_reversal=True)
        validate_contribution(
            cycle=active_cycle,
            contribution_date=today,
            amount=DAILY_RATE,
            existing=[reversal],
            today=today,
        )


class TestBR_R7_AmountMustMatchRate:
    def test_rejects_zero(self, active_cycle, today):
        with pytest.raises(InvalidContributionAmount, match="positive"):
            validate_contribution(
                cycle=active_cycle,
                contribution_date=today,
                amount=Money.zero(),
                existing=[],
                today=today,
            )

    def test_rejects_negative(self, active_cycle, today):
        with pytest.raises(InvalidContributionAmount, match="positive"):
            validate_contribution(
                cycle=active_cycle,
                contribution_date=today,
                amount=Money(-500),
                existing=[],
                today=today,
            )

    def test_rejects_amount_that_is_not_a_multiple_of_the_rate(
        self, active_cycle, today
    ):
        with pytest.raises(InvalidContributionAmount, match="whole multiple"):
            validate_contribution(
                cycle=active_cycle,
                contribution_date=today,
                amount=Money.from_cedis("7.50"),
                existing=[],
                today=today,
            )

    def test_rejects_multiple_days_worth_on_a_single_day(self, active_cycle, today):
        """days_covered defaults to 1, so 2x the rate is not valid for one day."""
        with pytest.raises(InvalidContributionAmount):
            validate_contribution(
                cycle=active_cycle,
                contribution_date=today,
                amount=DAILY_RATE * 2,
                existing=[],
                today=today,
            )

    def test_accepts_multiple_when_days_covered_is_declared(self, active_cycle, today):
        """Forward compatibility with FR-15 (catch-up), deferred from v1."""
        validate_contribution(
            cycle=active_cycle,
            contribution_date=today,
            amount=DAILY_RATE * 3,
            existing=[],
            today=today,
            days_covered=3,
        )


class TestEffectiveContributions:
    def test_excludes_reversed_and_reversals(self, today):
        good = make_contribution(on=today, contribution_id=1)
        reversed_one = make_contribution(
            on=today - timedelta(days=1), contribution_id=2, reversed_by_id=3
        )
        reversal = make_contribution(
            on=today - timedelta(days=1), contribution_id=3, is_reversal=True
        )
        assert effective_contributions([good, reversed_one, reversal]) == [good]


class TestCycleSummary:
    def test_counts_days_paid_missed_and_pending(self):
        """Cycle starts 1 Sep, today is 15 Sep (day 15). 10 days paid."""
        cycle = make_cycle()
        summary = compute_cycle_summary(
            cycle=cycle,
            contributions=contributions_for_days(10),
            today=TODAY,
        )
        assert summary.days_in_cycle == 31
        assert summary.days_elapsed == 15
        assert summary.days_paid == 10
        assert summary.days_missed == 5
        assert summary.days_pending == 16

    def test_totals_and_projected_payout(self):
        cycle = make_cycle()
        summary = compute_cycle_summary(
            cycle=cycle, contributions=contributions_for_days(10), today=TODAY
        )
        assert summary.total_collected == Money.from_cedis("100.00")
        assert summary.commission == DAILY_RATE
        assert summary.projected_payout == Money.from_cedis("90.00")

    def test_empty_cycle(self):
        cycle = make_cycle()
        summary = compute_cycle_summary(cycle=cycle, contributions=[], today=TODAY)
        assert summary.days_paid == 0
        assert summary.days_missed == 15
        assert summary.total_collected.is_zero
        assert summary.commission.is_zero
        assert summary.projected_payout.is_zero

    def test_before_cycle_starts_nothing_has_elapsed(self):
        cycle = make_cycle(start=date(2026, 12, 1))
        summary = compute_cycle_summary(cycle=cycle, contributions=[], today=TODAY)
        assert summary.days_elapsed == 0
        assert summary.days_missed == 0
        assert summary.days_pending == 31

    def test_after_cycle_ends_elapsed_is_capped(self):
        cycle = make_cycle()
        summary = compute_cycle_summary(
            cycle=cycle,
            contributions=contributions_for_days(31),
            today=cycle.end_date + timedelta(days=10),
        )
        assert summary.days_elapsed == 31
        assert summary.days_paid == 31
        assert summary.days_missed == 0
        assert summary.days_pending == 0

    def test_reversed_contributions_are_excluded_from_the_total(self):
        cycle = make_cycle()
        entries = contributions_for_days(10)
        entries[0].reversed_by_id = 999
        summary = compute_cycle_summary(
            cycle=cycle, contributions=entries, today=TODAY
        )
        assert summary.days_paid == 9
        assert summary.total_collected == Money.from_cedis("90.00")

    def test_card_state_per_day(self):
        """FR-16: each box is paid, missed or pending."""
        cycle = make_cycle()
        summary = compute_cycle_summary(
            cycle=cycle, contributions=contributions_for_days(3), today=TODAY
        )
        assert summary.state_of(CYCLE_START, TODAY) == "paid"
        assert summary.state_of(CYCLE_START + timedelta(days=5), TODAY) == "missed"
        assert summary.state_of(CYCLE_START + timedelta(days=20), TODAY) == "pending"


class TestPayout:
    MATURED_DAY = date(2026, 10, 2)  # cycle ends 1 Oct

    def test_computes_commission_and_net(self):
        """BR-R8: payout = total - one day's rate."""
        cycle = make_cycle()
        payout = compute_payout(
            cycle=cycle,
            contributions=contributions_for_days(31),
            released_by_id=3,
            today=self.MATURED_DAY,
        )
        assert payout.total_collected == Money.from_cedis("310.00")
        assert payout.commission == Money.from_cedis("10.00")
        assert payout.net_payout == Money.from_cedis("300.00")

    def test_partial_cycle_still_pays_out(self):
        cycle = make_cycle()
        payout = compute_payout(
            cycle=cycle,
            contributions=contributions_for_days(20),
            released_by_id=3,
            today=self.MATURED_DAY,
        )
        assert payout.total_collected == Money.from_cedis("200.00")
        assert payout.net_payout == Money.from_cedis("190.00")

    def test_single_day_client_receives_nothing(self):
        """BR-R9, the edge case: one day's contribution *is* the commission."""
        cycle = make_cycle()
        payout = compute_payout(
            cycle=cycle,
            contributions=contributions_for_days(1),
            released_by_id=3,
            today=self.MATURED_DAY,
        )
        assert payout.total_collected == DAILY_RATE
        assert payout.commission == DAILY_RATE
        assert payout.net_payout == Money.zero()
        assert not payout.net_payout.is_negative

    def test_client_who_paid_nothing_receives_nothing_and_owes_nothing(self):
        """BR-R9 boundary: commission cannot exceed what was collected."""
        cycle = make_cycle()
        payout = compute_payout(
            cycle=cycle,
            contributions=[],
            released_by_id=3,
            today=self.MATURED_DAY,
        )
        assert payout.total_collected.is_zero
        assert payout.commission.is_zero
        assert payout.net_payout.is_zero

    def test_payout_is_never_negative_across_the_whole_range(self):
        """The invariant BR-R9 exists to protect, checked exhaustively."""
        cycle = make_cycle()
        for days in range(0, 32):
            payout = compute_payout(
                cycle=cycle,
                contributions=contributions_for_days(days),
                released_by_id=3,
                today=self.MATURED_DAY,
            )
            assert not payout.net_payout.is_negative, f"negative at {days} days"
            assert (
                payout.net_payout + payout.commission == payout.total_collected
            ), f"money not conserved at {days} days"

    def test_rejects_second_payout(self):
        """BR-R10."""
        cycle = make_cycle(status=CycleStatus.PAID_OUT)
        with pytest.raises(CycleAlreadyPaidOut):
            compute_payout(
                cycle=cycle,
                contributions=contributions_for_days(31),
                released_by_id=3,
                today=self.MATURED_DAY,
            )

    def test_rejects_payout_when_already_paid_flag_is_set(self):
        cycle = make_cycle()
        with pytest.raises(CycleAlreadyPaidOut):
            compute_payout(
                cycle=cycle,
                contributions=[],
                released_by_id=3,
                today=self.MATURED_DAY,
                already_paid=True,
            )

    def test_rejects_payout_before_maturity(self):
        """BR-R12."""
        cycle = make_cycle()
        with pytest.raises(CycleNotMatured):
            compute_payout(
                cycle=cycle,
                contributions=contributions_for_days(10),
                released_by_id=3,
                today=TODAY,
            )

    def test_allows_payout_when_explicitly_marked_matured(self):
        cycle = make_cycle(status=CycleStatus.MATURED)
        payout = compute_payout(
            cycle=cycle,
            contributions=contributions_for_days(5),
            released_by_id=3,
            today=TODAY,
        )
        assert payout.net_payout == Money.from_cedis("40.00")

    def test_excludes_reversed_contributions(self):
        cycle = make_cycle()
        entries = contributions_for_days(31)
        entries[0].reversed_by_id = 999
        payout = compute_payout(
            cycle=cycle,
            contributions=entries,
            released_by_id=3,
            today=self.MATURED_DAY,
        )
        assert payout.total_collected == Money.from_cedis("300.00")
        assert payout.net_payout == Money.from_cedis("290.00")


class TestCommissionPolicy:
    def test_one_day_rate_policy(self):
        policy = OneDayRatePolicy()
        assert policy.commission_for(Money(31000), Money(1000)) == Money(1000)

    def test_caps_commission_at_total_collected(self):
        policy = OneDayRatePolicy()
        assert policy.commission_for(Money(400), Money(1000)) == Money(400)


class TestVariance:
    def test_zero_when_declared_matches_recorded(self):
        assert compute_variance(
            total_recorded=Money.from_cedis("340.00"),
            amount_declared=Money.from_cedis("340.00"),
        ).is_zero

    def test_positive_when_collector_banked_less_than_recorded(self):
        """BR-R13, BR-01 -- the case the system exists to surface."""
        variance = compute_variance(
            total_recorded=Money.from_cedis("285.00"),
            amount_declared=Money.from_cedis("250.00"),
        )
        assert variance == Money.from_cedis("35.00")
        assert variance.is_positive

    def test_negative_when_collector_banked_more_than_recorded(self):
        variance = compute_variance(
            total_recorded=Money.from_cedis("250.00"),
            amount_declared=Money.from_cedis("285.00"),
        )
        assert variance.is_negative

    def test_undeclared_counts_the_whole_amount_as_outstanding(self):
        variance = compute_variance(
            total_recorded=Money.from_cedis("340.00"), amount_declared=None
        )
        assert variance == Money.from_cedis("340.00")
