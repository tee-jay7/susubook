"""Unit tests for the Money value object (BR-R1, NFR-04).

No database, no Flask, no fixtures -- the domain layer's independence is what
makes these runnable in milliseconds.
"""

from decimal import Decimal

import pytest

from app.domain.money import Money


class TestConstruction:
    def test_from_cedis_accepts_string(self):
        assert Money.from_cedis("2.50").pesewas == 250

    def test_from_cedis_accepts_int(self):
        assert Money.from_cedis(5).pesewas == 500

    def test_from_cedis_accepts_decimal(self):
        assert Money.from_cedis(Decimal("10.05")).pesewas == 1005

    def test_zero(self):
        assert Money.zero().pesewas == 0

    def test_rejects_float_construction(self):
        """BR-R1: float is refused at the boundary, not merely avoided."""
        with pytest.raises(TypeError, match="floating point"):
            Money.from_cedis(2.50)

    def test_rejects_non_integer_pesewas(self):
        assert Money(250).pesewas == 250
        with pytest.raises(TypeError, match="requires an int"):
            Money(2.5)

    def test_rejects_bool_as_pesewas(self):
        """bool subclasses int; Money(True) is a bug, not an amount."""
        with pytest.raises(TypeError):
            Money(True)

    def test_rejects_fractional_pesewa(self):
        with pytest.raises(ValueError, match="whole number of pesewas"):
            Money.from_cedis("2.505")


class TestArithmetic:
    def test_addition(self):
        assert Money(250) + Money(1000) == Money(1250)

    def test_subtraction(self):
        assert Money(1000) - Money(250) == Money(750)

    def test_subtraction_may_go_negative(self):
        """Negative Money is representable; rules decide where it is legal."""
        assert (Money(100) - Money(250)).pesewas == -150

    def test_multiplication_by_int(self):
        assert Money(500) * 3 == Money(1500)

    def test_reverse_multiplication(self):
        assert 3 * Money(500) == Money(1500)

    def test_rejects_float_multiplication(self):
        with pytest.raises(TypeError, match="only be multiplied by an int"):
            Money(500) * 1.5

    def test_negation(self):
        assert -Money(250) == Money(-250)

    def test_accumulation_is_exact_for_every_day_of_a_cycle(self):
        """Money is exact at every point in a 31-day cycle.

        Asserted across the whole range rather than at one length, because
        float error in this range is intermittent (see the test below) and a
        single sample would pass by luck.
        """
        for days in range(1, 32):
            total = Money.zero()
            for _ in range(days):
                total = total + Money.from_cedis("0.10")
            assert total == Money(days * 10), f"inexact after {days} days"
            assert total.to_cedis() == Decimal(days) / 10

    def test_float_accumulation_is_unreliable_in_the_same_range(self):
        """The defect this class exists to prevent, demonstrated.

        Float error here is intermittent, not monotonic: 31 x 0.10 happens to
        round back to exactly 3.1, while 29 x 0.10 does not. Intermittent is
        worse than consistently wrong -- it is the failure mode that survives
        casual testing and reaches production.
        """
        assert sum(0.10 for _ in range(29)) != 2.90
        assert sum(0.10 for _ in range(3)) != 0.30
        assert sum(0.10 for _ in range(31)) == 3.10  # correct here, by luck

        # Money is exact at all three.
        for days, expected in ((29, 290), (3, 30), (31, 310)):
            total = Money.zero()
            for _ in range(days):
                total = total + Money.from_cedis("0.10")
            assert total == Money(expected)


class TestComparison:
    def test_equality_is_by_value(self):
        assert Money(250) == Money(250)

    def test_ordering(self):
        assert Money(100) < Money(250)
        assert max(Money(100), Money(250)) == Money(250)

    def test_min_underpins_commission_rule(self):
        """BR-R9 is expressed as min(rate, total); ordering must be correct."""
        assert min(Money(500), Money(300)) == Money(300)
        assert min(Money(500), Money(900)) == Money(500)

    def test_is_immutable(self):
        amount = Money(250)
        with pytest.raises(Exception):
            amount.pesewas = 500


class TestPredicates:
    def test_is_zero(self):
        assert Money.zero().is_zero
        assert not Money(1).is_zero

    def test_is_positive_and_negative(self):
        assert Money(1).is_positive
        assert Money(-1).is_negative
        assert not Money.zero().is_positive

    def test_divides_evenly_into(self):
        rate = Money(500)
        assert rate.divides_evenly_into(Money(1500))
        assert not rate.divides_evenly_into(Money(1200))

    def test_multiple_of(self):
        assert Money(1500).multiple_of(Money(500)) == 3

    def test_multiple_of_rejects_non_multiple(self):
        with pytest.raises(ValueError, match="not a whole multiple"):
            Money(1200).multiple_of(Money(500))

    def test_divisibility_by_zero_rate_is_rejected(self):
        with pytest.raises(ValueError):
            Money.zero().divides_evenly_into(Money(100))


class TestPresentation:
    def test_to_cedis(self):
        assert Money(250).to_cedis() == Decimal("2.50")

    def test_str_pads_pesewas(self):
        assert str(Money(205)) == "GHS 2.05"
        assert str(Money(200)) == "GHS 2.00"

    def test_str_handles_negative(self):
        assert str(Money(-250)) == "-GHS 2.50"

    def test_str_handles_zero(self):
        assert str(Money.zero()) == "GHS 0.00"
