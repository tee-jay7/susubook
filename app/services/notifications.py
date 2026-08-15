"""Client notification — FR-31. Layer 2 (Application).

Added under change request CR-002. SMS mitigates assumption **A5**: that clients
can reach a mobile web page. If A5 is false, the client's independent record —
the reason this system exists — never reaches them. A text message reaches a
handset that cannot open a browser.

Three properties this module is built to guarantee:

1. **A notification failure can never fail a contribution.** The ledger is the
   source of truth; the message is best-effort. Every path here swallows its
   errors and reports them to the log, never to the caller.
2. **Nothing is sent unless explicitly allowed.** The allowlist defaults to
   empty, so tests, local development and any misconfiguration send nothing. The
   demonstration data contains valid-format Ghanaian numbers that may belong to
   real people; an accidental broadcast to them would be a real harm, not a
   inconvenience.
3. **Sending is off the collector's critical path.** The HTTP call runs on a
   daemon thread so a slow gateway cannot stall the route sheet (NFR-01, NFR-02).
"""

from __future__ import annotations

import logging
import re
import threading
from typing import Protocol

from app.domain.entities import Client, Contribution
from app.domain.money import Money

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Phone numbers
# ---------------------------------------------------------------------------


def normalise_msisdn(raw: str) -> str | None:
    """Ghanaian number to international form, or None if unrecognisable.

    Accepts 0244000101, 233244000101, +233 244 000 101 and spaced variants.
    """
    if not raw:
        return None
    digits = re.sub(r"[^\d]", "", raw)
    if digits.startswith("233") and len(digits) == 12:
        return digits
    if digits.startswith("0") and len(digits) == 10:
        return "233" + digits[1:]
    if len(digits) == 9:
        return "233" + digits
    return None


# ---------------------------------------------------------------------------
# Gateway contract
# ---------------------------------------------------------------------------


class SmsGateway(Protocol):
    def send(self, *, to: str, message: str) -> bool:
        """Deliver one message. Returns success; never raises."""
        ...


class NullSmsGateway:
    """Sends nothing, records what it was asked to send.

    The default everywhere except a correctly configured production service, so
    the failure mode of a missing API key is silence rather than an exception —
    and tests can assert on intent without a network.
    """

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send(self, *, to: str, message: str) -> bool:
        self.sent.append((to, message))
        log.info("sms suppressed (no gateway configured): to=%s", to)
        return True


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class NotificationService:
    def __init__(
        self,
        gateway: SmsGateway,
        *,
        allowlist: frozenset[str] | None = None,
        allow_all: bool = False,
        synchronous: bool = False,
    ) -> None:
        self._gateway = gateway
        self._allowlist = allowlist or frozenset()
        self._allow_all = allow_all
        # Tests set this so a send is observable without joining a thread.
        self._synchronous = synchronous

    # -- policy ----------------------------------------------------------

    def may_send_to(self, phone: str) -> bool:
        """FR-31 safety gate.

        Defaults to refusing. The demonstration dataset uses valid-format
        Ghanaian numbers, so an unguarded send would text real strangers
        repeatedly — every time an examiner recorded a collection.
        """
        number = normalise_msisdn(phone)
        if number is None:
            return False
        if self._allow_all:
            return True
        return number in self._allowlist

    # -- messages --------------------------------------------------------

    @staticmethod
    def contribution_message(
        *, contribution: Contribution, collector_name: str, cycle_total: Money
    ) -> str:
        """Short enough for a single SMS segment, and self-verifying.

        Carries the reference so a client can quote it in a dispute, and the
        running total so the message confirms the record rather than merely
        announcing an event.
        """
        return (
            f"SusuBook: {contribution.amount} recorded for "
            f"{contribution.contribution_date:%d %b} by {collector_name}. "
            f"Ref {contribution.reference}. Cycle total {cycle_total}."
        )

    @staticmethod
    def payout_message(*, net_payout: Money, client_name: str) -> str:
        return (
            f"SusuBook: {client_name}, your susu cycle is complete. "
            f"Payout {net_payout} is ready for collection."
        )

    # -- dispatch --------------------------------------------------------

    def notify(self, *, phone: str, message: str) -> bool:
        """Best-effort send. Returns whether it was dispatched, never raises."""
        if not self.may_send_to(phone):
            log.info("sms not sent: recipient not on allowlist")
            return False

        number = normalise_msisdn(phone)
        assert number is not None  # may_send_to already validated it

        def _deliver() -> None:
            try:
                self._gateway.send(to=number, message=message)
            except Exception:  # noqa: BLE001 — never propagate to the caller
                log.exception("sms delivery failed for %s", number)

        if self._synchronous:
            _deliver()
        else:
            # Off the collector's critical path: a slow gateway must not stall
            # the route sheet.
            threading.Thread(target=_deliver, daemon=True).start()
        return True

    def notify_contribution(
        self,
        *,
        client: Client,
        contribution: Contribution,
        collector_name: str,
        cycle_total: Money,
    ) -> bool:
        return self.notify(
            phone=client.phone,
            message=self.contribution_message(
                contribution=contribution,
                collector_name=collector_name,
                cycle_total=cycle_total,
            ),
        )
