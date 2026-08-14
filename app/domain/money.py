"""Money as an exact integer quantity of pesewas.

Implements BR-R1: all monetary values are stored and computed as integer
pesewas; floating-point arithmetic is never applied to money.

Binary floating point cannot represent 0.1 exactly. Accumulating 29 daily
contributions of GHS 0.10 as floats yields 2.9000000000000004 rather than
2.90. The error is intermittent rather than monotonic -- 31 such additions
happen to round back to exactly 3.10 -- and intermittent is the worse
failure mode, because it survives casual testing and reaches production.

On a savings system a rounding error of a pesewa, compounding across
thousands of clients, is both a correctness defect and a failure of the
trust this system exists to establish -- so float is rejected at the type
boundary rather than merely avoided by convention.

This module imports nothing from Flask, SQLAlchemy or the standard library's
I/O. It is layer 3 (Domain).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Union

PESEWAS_PER_CEDI = 100


@dataclass(frozen=True, order=True)
class Money:
    """An exact amount in pesewas. Immutable and comparable by value."""

    pesewas: int

    def __post_init__(self) -> None:
        # bool is a subclass of int; Money(True) is a bug, not an amount.
        if isinstance(self.pesewas, bool) or not isinstance(self.pesewas, int):
            raise TypeError(
                f"Money requires an int number of pesewas, got "
                f"{type(self.pesewas).__name__}. Use Money.from_cedis() to "
                f"convert a decimal amount."
            )

    # -- construction ----------------------------------------------------

    @classmethod
    def zero(cls) -> Money:
        return cls(0)

    @classmethod
    def from_cedis(cls, amount: Union[str, int, Decimal]) -> Money:
        """Build from a cedi amount given as str, int or Decimal.

        float is rejected deliberately (BR-R1): accepting it would silently
        reintroduce the representation error this class exists to prevent.
        """
        if isinstance(amount, float):
            raise TypeError(
                "Refusing to build Money from float -- binary floating point "
                "cannot represent decimal currency exactly (BR-R1). Pass a "
                "str such as '2.50', an int, or a Decimal."
            )
        value = Decimal(amount)
        pesewas = value * PESEWAS_PER_CEDI
        if pesewas != pesewas.to_integral_value():
            raise ValueError(
                f"GHS {value} is not a whole number of pesewas; "
                f"currency cannot be subdivided further."
            )
        return cls(int(pesewas))

    # -- arithmetic ------------------------------------------------------

    def __add__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        return Money(self.pesewas + other.pesewas)

    def __sub__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        return Money(self.pesewas - other.pesewas)

    def __mul__(self, factor: int) -> Money:
        """Multiply by a whole number of units (e.g. days covered)."""
        if isinstance(factor, bool) or not isinstance(factor, int):
            raise TypeError(
                "Money may only be multiplied by an int; multiplying by a "
                "float would reintroduce representation error (BR-R1)."
            )
        return Money(self.pesewas * factor)

    __rmul__ = __mul__

    def __neg__(self) -> Money:
        return Money(-self.pesewas)

    # -- predicates ------------------------------------------------------

    @property
    def is_zero(self) -> bool:
        return self.pesewas == 0

    @property
    def is_positive(self) -> bool:
        return self.pesewas > 0

    @property
    def is_negative(self) -> bool:
        return self.pesewas < 0

    def divides_evenly_into(self, other: Money) -> bool:
        """True if `other` is a whole multiple of this amount (BR-R7)."""
        if self.pesewas <= 0:
            raise ValueError("Cannot test divisibility by a non-positive rate.")
        return other.pesewas % self.pesewas == 0

    def multiple_of(self, unit: Money) -> int:
        """How many whole `unit`s this amount represents (BR-R7)."""
        if unit.pesewas <= 0:
            raise ValueError("Cannot divide by a non-positive rate.")
        if self.pesewas % unit.pesewas != 0:
            raise ValueError(f"{self} is not a whole multiple of {unit}.")
        return self.pesewas // unit.pesewas

    # -- presentation ----------------------------------------------------

    def to_cedis(self) -> Decimal:
        return (Decimal(self.pesewas) / PESEWAS_PER_CEDI).quantize(Decimal("0.01"))

    def __str__(self) -> str:
        sign = "-" if self.pesewas < 0 else ""
        whole, part = divmod(abs(self.pesewas), PESEWAS_PER_CEDI)
        return f"{sign}GHS {whole}.{part:02d}"

    def __repr__(self) -> str:
        return f"Money({self.pesewas})  # {self}"
