"""Service-layer tests against in-memory fakes — no database.

Covers orchestration, authorisation (FR-05, BR-R15) and the audit trail
(NFR-09), which the pure-rule tests in test_rules.py do not reach.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest

from app.domain.entities import CycleStatus, User, UserRole
from app.domain.errors import (
    CycleAlreadyPaidOut,
    DuplicateContribution,
    NotAuthorised,
)
from app.domain.money import Money
from app.services.collection import (
    ClientNotFound,
    CollectionService,
    CycleService,
    EnrolmentService,
    NoActiveCycle,
)
from app.services.payout import PayoutService
from app.services.reconciliation import ReconciliationService
from app.services.security import AuthService, hash_password

from .fakes import (
    FakeAuditRepository,
    FakeClientRepository,
    FakeContributionRepository,
    FakeCycleRepository,
    FakePayoutRepository,
    FakeRemittanceRepository,
    FakeUnitOfWork,
    FakeUserRepository,
)

TODAY = date(2026, 9, 15)
RATE = Money.from_cedis("10.00")


def a_user(role: UserRole, user_id: int = 1, name: str = "J. Osei") -> User:
    return User(
        id=user_id,
        public_ref=uuid4(),
        full_name=name,
        phone=f"024400{user_id:04d}",
        role=role,
    )


class Harness:
    """Wires the services with fakes. Mirrors the app factory's real wiring."""

    def __init__(self, today: date = TODAY):
        # Mutable so a test can advance the calendar and simulate a real
        # collection run across several days.
        self.now = today
        self.clock = lambda: self.now
        self.users = FakeUserRepository()
        self.clients = FakeClientRepository()
        self.cycles = FakeCycleRepository()
        self.contributions = FakeContributionRepository()
        self.payouts = FakePayoutRepository()
        self.remittances = FakeRemittanceRepository()
        self.audit = FakeAuditRepository()
        self.uow = FakeUnitOfWork()

        self.cycle_service = CycleService(self.cycles, clock=self.clock)
        self.enrolment = EnrolmentService(
            users=self.users,
            clients=self.clients,
            cycles=self.cycle_service,
            audit=self.audit,
            uow=self.uow,
            clock=self.clock,
        )
        self.collection = CollectionService(
            clients=self.clients,
            cycles=self.cycles,
            contributions=self.contributions,
            audit=self.audit,
            uow=self.uow,
            clock=self.clock,
        )
        self.payout = PayoutService(
            cycles=self.cycles,
            contributions=self.contributions,
            payouts=self.payouts,
            cycle_service=self.cycle_service,
            audit=self.audit,
            uow=self.uow,
            clock=self.clock,
        )
        self.reconciliation = ReconciliationService(
            remittances=self.remittances,
            contributions=self.contributions,
            audit=self.audit,
            uow=self.uow,
            clock=self.clock,
        )
        self.auth = AuthService(self.users, self.audit)

    def enrol(self, collector: User, name="Kofi Boateng", rate: Money = RATE):
        return self.enrolment.enrol(
            actor=collector,
            full_name=name,
            phone="0201234567",
            daily_rate=rate,
            password_hash="x",
            business_type="Kiosk",
            location="Madina Market",
        )


@pytest.fixture
def h() -> Harness:
    return Harness()


@pytest.fixture
def collector() -> User:
    return a_user(UserRole.COLLECTOR, 1)


@pytest.fixture
def supervisor() -> User:
    return a_user(UserRole.SUPERVISOR, 2, "M. Adjei")


class TestEnrolment:
    def test_creates_client_login_and_first_cycle_together(self, h, collector):
        client, cycle = h.enrol(collector)
        assert client.id is not None
        assert client.user_id is not None
        assert client.collector_id == collector.id
        assert cycle.cycle_number == 1
        assert cycle.status is CycleStatus.ACTIVE
        assert cycle.length_in_days == 31

    def test_client_gets_an_opaque_public_reference(self, h, collector):
        """BR-R14 — never a sequential id in a URL."""
        client, _ = h.enrol(collector)
        assert client.public_ref is not None
        assert str(client.public_ref) != str(client.id)
        assert len(str(client.public_ref)) == 36

    def test_cycle_snapshots_the_daily_rate(self, h, collector):
        _, cycle = h.enrol(collector, rate=Money.from_cedis("7.00"))
        assert cycle.daily_rate == Money.from_cedis("7.00")

    def test_rejects_zero_daily_rate(self, h, collector):
        with pytest.raises(Exception, match="more than zero"):
            h.enrolment.enrol(
                actor=collector,
                full_name="X",
                phone="0200000000",
                daily_rate=Money.zero(),
                password_hash="x",
            )

    def test_writes_audit_entry(self, h, collector):
        h.enrol(collector)
        assert "ENROL_CLIENT" in h.audit.actions()

    def test_commits_once(self, h, collector):
        h.enrol(collector)
        assert h.uow.commits == 1


class TestRecordContribution:
    def test_records_with_the_agreed_rate_by_default(self, h, collector):
        client, _ = h.enrol(collector)
        contribution = h.collection.record(
            public_ref=client.public_ref, actor=collector
        )
        assert contribution.amount == RATE
        assert contribution.contribution_date == TODAY
        assert contribution.recorded_by_id == collector.id

    def test_assigns_a_reference(self, h, collector):
        """FR-30 — every contribution gets a quotable receipt reference."""
        client, _ = h.enrol(collector)
        contribution = h.collection.record(
            public_ref=client.public_ref, actor=collector
        )
        assert contribution.reference.startswith("SB-")

    def test_rejects_duplicate_for_the_same_day(self, h, collector):
        client, _ = h.enrol(collector)
        h.collection.record(public_ref=client.public_ref, actor=collector)
        with pytest.raises(DuplicateContribution):
            h.collection.record(public_ref=client.public_ref, actor=collector)

    def test_unknown_reference_is_rejected(self, h, collector):
        with pytest.raises(ClientNotFound):
            h.collection.record(public_ref=uuid4(), actor=collector)

    def test_writes_audit_entry_with_client_and_amount(self, h, collector):
        client, _ = h.enrol(collector)
        h.collection.record(public_ref=client.public_ref, actor=collector)
        entries = [
            e for e in h.audit.entries if e["action"] == "RECORD_CONTRIBUTION"
        ]
        assert len(entries) == 1
        assert entries[0]["detail"]["amount_pesewas"] == RATE.pesewas
        assert entries[0]["detail"]["client_ref"] == str(client.public_ref)

    def test_no_active_cycle_is_reported_clearly(self, h, collector):
        client, cycle = h.enrol(collector)
        h.cycles.set_status(cycle.id, CycleStatus.PAID_OUT.value)
        with pytest.raises(NoActiveCycle, match="no open cycle"):
            h.collection.record(public_ref=client.public_ref, actor=collector)


class TestAuthorisation:
    """FR-05 and BR-R15 — the reference identifies, it does not authorise."""

    def test_collector_cannot_record_against_another_collectors_client(
        self, h, collector
    ):
        client, _ = h.enrol(collector)
        intruder = a_user(UserRole.COLLECTOR, 99, "Other Collector")
        with pytest.raises(NotAuthorised, match="not on your route"):
            h.collection.record(public_ref=client.public_ref, actor=intruder)

    def test_possession_of_the_reference_confers_nothing(self, h, collector):
        """A photographed QR card gains an outsider no capability."""
        client, _ = h.enrol(collector)
        stolen_ref = client.public_ref  # as if read off a photographed card
        outsider = a_user(UserRole.COLLECTOR, 77)
        with pytest.raises(NotAuthorised):
            h.collection.record(public_ref=stolen_ref, actor=outsider)

    def test_denied_attempt_is_audited(self, h, collector):
        client, _ = h.enrol(collector)
        intruder = a_user(UserRole.COLLECTOR, 99)
        with pytest.raises(NotAuthorised):
            h.collection.record(public_ref=client.public_ref, actor=intruder)
        assert "AUTHORISATION_DENIED" in h.audit.actions()

    def test_supervisor_may_act_across_routes(self, h, collector, supervisor):
        client, _ = h.enrol(collector)
        contribution = h.collection.record(
            public_ref=client.public_ref, actor=supervisor
        )
        assert contribution.recorded_by_id == supervisor.id


class TestReversal:
    def test_supervisor_can_reverse_and_original_survives(self, h, collector, supervisor):
        client, _ = h.enrol(collector)
        original = h.collection.record(public_ref=client.public_ref, actor=collector)

        reversal = h.collection.reverse(
            reference=original.reference, actor=supervisor, reason="wrong client"
        )

        assert reversal.is_reversal
        assert reversal.amount == original.amount
        stored = h.contributions.get_by_reference(original.reference)
        assert stored is not None, "BR-R11: original must not be deleted"
        assert stored.reversed_by_id == reversal.id
        assert not stored.is_effective

    def test_collector_cannot_reverse(self, h, collector):
        client, _ = h.enrol(collector)
        original = h.collection.record(public_ref=client.public_ref, actor=collector)
        with pytest.raises(NotAuthorised, match="Only a supervisor"):
            h.collection.reverse(
                reference=original.reference, actor=collector, reason="oops"
            )

    def test_cannot_reverse_twice(self, h, collector, supervisor):
        client, _ = h.enrol(collector)
        original = h.collection.record(public_ref=client.public_ref, actor=collector)
        h.collection.reverse(
            reference=original.reference, actor=supervisor, reason="first"
        )
        with pytest.raises(Exception, match="already been reversed"):
            h.collection.reverse(
                reference=original.reference, actor=supervisor, reason="second"
            )

    def test_reversal_frees_the_day_for_a_replacement(self, h, collector, supervisor):
        """The point of correcting by reversal rather than by edit."""
        client, _ = h.enrol(collector)
        original = h.collection.record(public_ref=client.public_ref, actor=collector)
        h.collection.reverse(
            reference=original.reference, actor=supervisor, reason="wrong amount"
        )
        replacement = h.collection.record(
            public_ref=client.public_ref, actor=collector
        )
        assert replacement.is_effective

    def test_reversal_is_audited_with_reason(self, h, collector, supervisor):
        client, _ = h.enrol(collector)
        original = h.collection.record(public_ref=client.public_ref, actor=collector)
        h.collection.reverse(
            reference=original.reference, actor=supervisor, reason="duplicate entry"
        )
        entry = next(
            e for e in h.audit.entries if e["action"] == "REVERSE_CONTRIBUTION"
        )
        assert entry["detail"]["reason"] == "duplicate entry"


class TestPayout:
    def test_release_closes_cycle_and_opens_the_next(self, h, collector, supervisor):
        client, cycle = h.enrol(collector)
        # Five consecutive collection days, with the calendar advancing.
        for offset in range(5):
            h.now = cycle.start_date + timedelta(days=offset)
            h.collection.record(public_ref=client.public_ref, actor=collector)
        h.now = cycle.end_date + timedelta(days=1)
        h.cycles.set_status(cycle.id, CycleStatus.MATURED.value)

        payout = h.payout.release(cycle_id=cycle.id, actor=supervisor)

        assert payout.total_collected == Money.from_cedis("50.00")
        assert payout.commission == RATE
        assert payout.net_payout == Money.from_cedis("40.00")
        assert h.cycles.get_by_id(cycle.id).status is CycleStatus.PAID_OUT
        assert h.cycles.active_for_client(client.id).cycle_number == 2

    def test_collector_cannot_release(self, h, collector):
        _, cycle = h.enrol(collector)
        h.cycles.set_status(cycle.id, CycleStatus.MATURED.value)
        with pytest.raises(NotAuthorised, match="Only a supervisor"):
            h.payout.release(cycle_id=cycle.id, actor=collector)

    def test_second_release_is_refused(self, h, collector, supervisor):
        """BR-R10, enforced in the service as well as by a unique constraint."""
        client, cycle = h.enrol(collector)
        h.collection.record(public_ref=client.public_ref, actor=collector)
        h.cycles.set_status(cycle.id, CycleStatus.MATURED.value)
        h.payout.release(cycle_id=cycle.id, actor=supervisor)
        with pytest.raises(CycleAlreadyPaidOut):
            h.payout.release(cycle_id=cycle.id, actor=supervisor)

    def test_new_cycle_inherits_the_rate(self, h, collector, supervisor):
        client, cycle = h.enrol(collector, rate=Money.from_cedis("25.00"))
        h.cycles.set_status(cycle.id, CycleStatus.MATURED.value)
        h.payout.release(cycle_id=cycle.id, actor=supervisor)
        assert h.cycles.active_for_client(client.id).daily_rate == Money.from_cedis(
            "25.00"
        )

    def test_release_is_audited_with_the_settlement(self, h, collector, supervisor):
        client, cycle = h.enrol(collector)
        h.collection.record(public_ref=client.public_ref, actor=collector)
        h.cycles.set_status(cycle.id, CycleStatus.MATURED.value)
        h.payout.release(cycle_id=cycle.id, actor=supervisor)
        entry = next(e for e in h.audit.entries if e["action"] == "RELEASE_PAYOUT")
        assert entry["detail"]["net_payout_pesewas"] == 0  # BR-R9: one day only


class TestReconciliation:
    def test_declaring_matching_cash_gives_zero_variance(self, h, collector):
        client, _ = h.enrol(collector)
        h.collection.record(public_ref=client.public_ref, actor=collector)
        variance = h.reconciliation.declare(actor=collector, amount=RATE)
        assert variance.variance.is_zero
        assert variance.is_reconciled

    def test_declaring_less_than_recorded_surfaces_a_shortfall(self, h, collector):
        """BR-01 — the case the system exists to detect."""
        client, _ = h.enrol(collector)
        h.collection.record(public_ref=client.public_ref, actor=collector)
        variance = h.reconciliation.declare(
            actor=collector, amount=Money.from_cedis("3.00")
        )
        assert variance.variance == Money.from_cedis("7.00")
        assert not variance.is_reconciled

    def test_undeclared_day_shows_the_whole_amount_outstanding(self, h, collector):
        client, _ = h.enrol(collector)
        h.collection.record(public_ref=client.public_ref, actor=collector)
        position = h.reconciliation.my_position(actor=collector)
        assert position.amount_declared is None
        assert position.variance == RATE

    def test_rejects_negative_declaration(self, h, collector):
        with pytest.raises(Exception, match="cannot be negative"):
            h.reconciliation.declare(actor=collector, amount=Money(-100))

    def test_rejects_future_declaration(self, h, collector):
        with pytest.raises(Exception, match="future date"):
            h.reconciliation.declare(
                actor=collector, amount=RATE, on=TODAY + timedelta(days=1)
            )

    def test_collector_cannot_view_all_variances(self, h, collector):
        with pytest.raises(NotAuthorised, match="Only a supervisor"):
            h.reconciliation.variances(actor=collector)

    def test_declaration_is_audited_with_the_variance(self, h, collector):
        client, _ = h.enrol(collector)
        h.collection.record(public_ref=client.public_ref, actor=collector)
        h.reconciliation.declare(actor=collector, amount=Money.from_cedis("3.00"))
        entry = next(e for e in h.audit.entries if e["action"] == "DECLARE_REMITTANCE")
        assert entry["detail"]["variance_pesewas"] == 700


class TestAuthentication:
    def test_correct_credentials_authenticate(self, h):
        user = a_user(UserRole.COLLECTOR, 1)
        h.users.add(user, hash_password("correct horse"))
        assert h.auth.authenticate(user.phone, "correct horse") is not None

    def test_wrong_password_is_refused(self, h):
        user = a_user(UserRole.COLLECTOR, 1)
        h.users.add(user, hash_password("correct horse"))
        assert h.auth.authenticate(user.phone, "wrong") is None

    def test_unknown_phone_is_refused(self, h):
        assert h.auth.authenticate("0000000000", "anything") is None

    def test_failed_attempts_are_audited(self, h):
        user = a_user(UserRole.COLLECTOR, 1)
        h.users.add(user, hash_password("pw"))
        h.auth.authenticate(user.phone, "wrong")
        h.auth.authenticate("0000000000", "wrong")
        assert h.audit.actions().count("LOGIN_FAILED") == 2

    def test_successful_login_is_audited(self, h):
        user = a_user(UserRole.COLLECTOR, 1)
        h.users.add(user, hash_password("pw"))
        h.auth.authenticate(user.phone, "pw")
        assert "LOGIN" in h.audit.actions()

    def test_password_is_not_stored_in_plaintext(self, h):
        user = a_user(UserRole.COLLECTOR, 1)
        h.users.add(user, hash_password("s3cret"))
        _, stored = h.users.find_credentials(user.phone)
        assert "s3cret" not in stored
        assert stored.startswith("$argon2")
