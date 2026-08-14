"""Domain error hierarchy.

Every rule violation raises a specific subclass carrying enough context for
the presentation layer to render an intelligible message without inspecting
strings. Layer 3 (Domain) -- no framework imports.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for every business rule violation.

    The web layer catches this one type and renders `.message`, so a new rule
    does not require a new except-clause anywhere (Open/Closed).
    """

    rule: str = ""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


# -- contribution recording (UC-03) --------------------------------------


class CycleClosed(DomainError):
    """BR-R6: no contribution against a MATURED or PAID_OUT cycle."""

    rule = "BR-R6"


class ContributionDateOutsideCycle(DomainError):
    """BR-R3: contribution date must fall within the cycle."""

    rule = "BR-R3"


class ContributionDateInFuture(DomainError):
    """BR-R4: a contribution may not be dated in the future."""

    rule = "BR-R4"


class DuplicateContribution(DomainError):
    """BR-R5: one effective contribution per client per date."""

    rule = "BR-R5"

    def __init__(self, message: str, existing_reference: str | None = None) -> None:
        super().__init__(message)
        self.existing_reference = existing_reference


class InvalidContributionAmount(DomainError):
    """BR-R7: amount must be a positive whole multiple of the daily rate."""

    rule = "BR-R7"


# -- payout (UC-07) -------------------------------------------------------


class CycleNotMatured(DomainError):
    """A payout was attempted before the cycle matured."""

    rule = "BR-R12"


class CycleAlreadyPaidOut(DomainError):
    """BR-R10: a cycle may be paid out at most once."""

    rule = "BR-R10"


# -- authorisation --------------------------------------------------------


class NotAuthorised(DomainError):
    """FR-05 / BR-R15: actor may not operate on this client."""

    rule = "FR-05"
