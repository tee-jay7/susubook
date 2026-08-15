"""SMS notification — FR-31, added under CR-002.

The most important tests here are the negative ones. The demonstration dataset
uses valid-format Ghanaian numbers that may belong to real people, so the
allowlist is not a convenience: an unguarded send would text strangers every
time a collection was recorded. These tests exist to make that impossible to
reintroduce.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.domain.entities import Contribution
from app.domain.money import Money
from app.services.notifications import (
    NotificationService,
    NullSmsGateway,
    normalise_msisdn,
)


class TestNormaliseMsisdn:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("0244000101", "233244000101"),
            ("233244000101", "233244000101"),
            ("+233244000101", "233244000101"),
            ("+233 244 000 101", "233244000101"),
            ("024-400-0101", "233244000101"),
            ("244000101", "233244000101"),
        ],
    )
    def test_accepts_common_forms(self, raw, expected):
        assert normalise_msisdn(raw) == expected

    @pytest.mark.parametrize("raw", ["", "abc", "12", "0244", "00000000000000000"])
    def test_rejects_unrecognisable(self, raw):
        assert normalise_msisdn(raw) is None

    def test_equivalent_forms_normalise_identically(self):
        """The allowlist compares normalised values, so 024… and +233… must
        resolve to the same key or a permitted number could be refused."""
        assert normalise_msisdn("0201000201") == normalise_msisdn("+233201000201")


class TestAllowlist:
    def test_sends_nothing_by_default(self):
        """The critical default. An empty allowlist means no recipient."""
        service = NotificationService(NullSmsGateway())
        assert service.may_send_to("0244000101") is False

    def test_allows_a_listed_number(self):
        service = NotificationService(
            NullSmsGateway(), allowlist=frozenset({"233244000101"})
        )
        assert service.may_send_to("0244000101") is True

    def test_refuses_a_number_not_listed(self):
        service = NotificationService(
            NullSmsGateway(), allowlist=frozenset({"233244000101"})
        )
        assert service.may_send_to("0201000201") is False

    def test_matches_regardless_of_the_form_supplied(self):
        service = NotificationService(
            NullSmsGateway(), allowlist=frozenset({"233244000101"})
        )
        for form in ("0244000101", "+233244000101", "233244000101", "024 400 0101"):
            assert service.may_send_to(form) is True, form

    def test_refuses_an_unparseable_number_even_when_allowing_all(self):
        service = NotificationService(NullSmsGateway(), allow_all=True)
        assert service.may_send_to("not-a-number") is False

    def test_allow_all_is_opt_in_only(self):
        assert NotificationService(NullSmsGateway(), allow_all=True).may_send_to(
            "0244000101"
        ) is True

    def test_seed_numbers_are_refused_without_configuration(self):
        """Regression guard for the specific harm this gate exists to prevent.

        Every phone number in the demonstration dataset must be refused by a
        default-configured service.
        """
        service = NotificationService(NullSmsGateway())
        seeded = [
            "0244000100", "0244000101", "0244000102", "0244000103", "0244000199",
            "0201000201", "0201000202", "0201000203", "0201000204", "0201000205",
            "0201000206", "0201000207", "0201000208", "0201000209", "0201000210",
        ]
        for number in seeded:
            assert service.may_send_to(number) is False, number


class TestDispatch:
    def _service(self, **kw):
        gateway = NullSmsGateway()
        return gateway, NotificationService(gateway, synchronous=True, **kw)

    def test_nothing_reaches_the_gateway_when_not_allowed(self):
        gateway, service = self._service()
        assert service.notify(phone="0244000101", message="hello") is False
        assert gateway.sent == []

    def test_message_reaches_the_gateway_when_allowed(self):
        gateway, service = self._service(allowlist=frozenset({"233244000101"}))
        assert service.notify(phone="0244000101", message="hello") is True
        assert gateway.sent == [("233244000101", "hello")]

    def test_gateway_receives_the_normalised_number(self):
        gateway, service = self._service(allow_all=True)
        service.notify(phone="0244000101", message="x")
        assert gateway.sent[0][0] == "233244000101"

    def test_a_failing_gateway_never_raises(self):
        """A notification failure must not be able to fail a collection."""

        class ExplodingGateway:
            def send(self, *, to: str, message: str) -> bool:
                raise RuntimeError("gateway down")

        service = NotificationService(
            ExplodingGateway(), allow_all=True, synchronous=True
        )
        assert service.notify(phone="0244000101", message="x") is True


class TestMessages:
    def _contribution(self):
        return Contribution(
            id=1,
            reference="SB-4K2M-7X9P",
            cycle_id=1,
            contribution_date=date(2026, 9, 15),
            amount=Money.from_cedis("10.00"),
            recorded_by_id=7,
        )

    def test_contribution_message_carries_what_a_dispute_needs(self):
        message = NotificationService.contribution_message(
            contribution=self._contribution(),
            collector_name="Joseph Osei",
            cycle_total=Money.from_cedis("110.00"),
        )
        assert "GHS 10.00" in message      # what was taken
        assert "15 Sep" in message          # when
        assert "Joseph Osei" in message     # by whom
        assert "SB-4K2M-7X9P" in message    # quotable reference
        assert "GHS 110.00" in message      # running total confirms the record

    def test_contribution_message_fits_one_sms_segment(self):
        """Over 160 characters bills as two messages and may be split."""
        message = NotificationService.contribution_message(
            contribution=self._contribution(),
            collector_name="Joseph Osei",
            cycle_total=Money.from_cedis("110.00"),
        )
        assert len(message) <= 160, f"{len(message)} chars: {message}"

    def test_payout_message(self):
        message = NotificationService.payout_message(
            net_payout=Money.from_cedis("300.00"), client_name="Ama Serwaa"
        )
        assert "GHS 300.00" in message and "Ama Serwaa" in message

    def test_message_carries_no_credential_or_link(self):
        """A text message is readable by anyone holding the handset."""
        message = NotificationService.contribution_message(
            contribution=self._contribution(),
            collector_name="Joseph Osei",
            cycle_total=Money.from_cedis("110.00"),
        )
        for leak in ("password", "http://", "https://", "token"):
            assert leak not in message.lower()
