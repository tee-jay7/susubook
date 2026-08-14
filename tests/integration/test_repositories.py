"""Repository behaviour against real PostgreSQL.

Covers the entity/record mapping (TD-07) and the queries the unit suite's
in-memory fakes deliberately stub out — chiefly the variance report, which is
a three-way outer join and cannot be meaningfully faked.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.domain.entities import Contribution, RemittanceDeclaration
from app.domain.money import Money
from app.infrastructure.models import ContributionCycleModel, ContributionModel
from app.infrastructure.repositories import (
    SqlAuditRepository,
    SqlClientRepository,
    SqlContributionRepository,
    SqlCycleRepository,
    SqlRemittanceRepository,
    new_reference,
)

from .conftest import CYCLE_START, RATE, TODAY

pytestmark = pytest.mark.integration


class TestReferenceGeneration:
    def test_format(self):
        ref = new_reference()
        assert ref.startswith("SB-")
        assert len(ref) == 12  # SB- + 4 + - + 4

    def test_excludes_ambiguous_characters(self):
        """A client reads this aloud over the phone; I/L/O/U must not appear."""
        body = "".join(new_reference()[3:].split("-"))
        assert not (set(body) & set("ILOU"))

    def test_references_do_not_collide(self):
        assert len({new_reference() for _ in range(2000)}) == 2000


class TestMoneyRoundTrip:
    def test_money_survives_the_mapping_exactly(self, session, cycle_row, collector):
        """TD-07's risk is silent drift between model and mapper. This is the
        assertion that would catch it for the money columns."""
        repo = SqlContributionRepository(session)
        saved = repo.add(
            Contribution(
                id=None,
                reference="",
                cycle_id=cycle_row.id,
                contribution_date=CYCLE_START,
                amount=Money.from_cedis("12.34"),
                recorded_by_id=collector.id,
            )
        )
        session.commit()

        fetched = repo.get_by_reference(saved.reference)
        assert fetched.amount == Money.from_cedis("12.34")
        assert fetched.amount.pesewas == 1234
        assert isinstance(fetched.amount.pesewas, int)

    def test_daily_rate_survives_the_mapping(self, session, client_row):
        client = SqlClientRepository(session).get_by_id(client_row.id)
        assert client.daily_rate == RATE


class TestClientRepository:
    def test_get_by_public_ref(self, session, client_row):
        repo = SqlClientRepository(session)
        found = repo.get_by_public_ref(client_row.public_ref)
        assert found is not None
        assert found.full_name == "Kofi Boateng"

    def test_unknown_public_ref_returns_none(self, session, client_row):
        import uuid

        assert SqlClientRepository(session).get_by_public_ref(uuid.uuid4()) is None

    def test_list_for_collector_excludes_other_routes(
        self, session, client_row, collector, supervisor
    ):
        from app.infrastructure.models import ClientModel, UserModel

        other_user = UserModel(
            full_name="Not Mine", phone="0207777777", password_hash="x", role="CLIENT"
        )
        session.add(other_user)
        session.flush()
        session.add(
            ClientModel(
                user_id=other_user.id,
                collector_id=supervisor.id,
                full_name="Not Mine",
                phone="0207777777",
                daily_rate_pesewas=500,
            )
        )
        session.commit()

        names = [c.full_name for c in SqlClientRepository(session).list_for_collector(collector.id)]
        assert names == ["Kofi Boateng"]

    def test_inactive_clients_are_excluded(self, session, client_row, collector):
        client_row.is_active = False
        session.commit()
        assert SqlClientRepository(session).list_for_collector(collector.id) == []


class TestCycleRepository:
    def test_active_for_client(self, session, client_row, cycle_row):
        found = SqlCycleRepository(session).active_for_client(client_row.id)
        assert found is not None
        assert found.cycle_number == 1
        assert found.daily_rate == RATE

    def test_no_active_cycle_returns_none(self, session, client_row, cycle_row):
        cycle_row.status = "PAID_OUT"
        session.commit()
        assert SqlCycleRepository(session).active_for_client(client_row.id) is None

    def test_list_due_for_payout_finds_matured_unpaid_cycles(
        self, session, client_row, cycle_row
    ):
        due = SqlCycleRepository(session).list_due_for_payout(
            cycle_row.end_date + timedelta(days=1)
        )
        assert len(due) == 1
        cycle, client = due[0]
        assert cycle.id == cycle_row.id
        assert client.full_name == "Kofi Boateng"

    def test_list_due_excludes_cycles_not_yet_matured(self, session, cycle_row):
        assert SqlCycleRepository(session).list_due_for_payout(CYCLE_START) == []

    def test_list_due_excludes_already_paid_cycles(
        self, session, cycle_row, supervisor
    ):
        from app.infrastructure.models import PayoutModel

        session.add(
            PayoutModel(
                cycle_id=cycle_row.id,
                total_collected_pesewas=1000,
                commission_pesewas=1000,
                net_payout_pesewas=0,
                released_by_id=supervisor.id,
            )
        )
        session.commit()
        assert (
            SqlCycleRepository(session).list_due_for_payout(
                cycle_row.end_date + timedelta(days=1)
            )
            == []
        )


class TestContributionRepository:
    def _add(self, session, cycle_id, collector_id, offset, amount=RATE):
        return SqlContributionRepository(session).add(
            Contribution(
                id=None,
                reference="",
                cycle_id=cycle_id,
                contribution_date=CYCLE_START + timedelta(days=offset),
                amount=amount,
                recorded_by_id=collector_id,
            )
        )

    def test_total_recorded_by_sums_one_day(self, session, cycle_row, collector):
        self._add(session, cycle_row.id, collector.id, 0)
        session.commit()
        total = SqlContributionRepository(session).total_recorded_by(
            collector.id, CYCLE_START
        )
        assert total == RATE

    def test_total_recorded_by_excludes_reversed(self, session, cycle_row, collector):
        repo = SqlContributionRepository(session)
        first = self._add(session, cycle_row.id, collector.id, 0)
        second = self._add(session, cycle_row.id, collector.id, 1)
        session.commit()

        reversal = repo.add(
            Contribution(
                id=None,
                reference="",
                cycle_id=cycle_row.id,
                contribution_date=CYCLE_START,
                amount=RATE,
                recorded_by_id=collector.id,
                is_reversal=True,
            )
        )
        repo.mark_reversed(first.id, reversal.id)
        session.commit()

        assert repo.total_recorded_by(collector.id, CYCLE_START).is_zero
        assert repo.total_recorded_by(
            collector.id, CYCLE_START + timedelta(days=1)
        ) == RATE

    def test_total_is_zero_for_a_day_with_nothing(self, session, collector):
        assert (
            SqlContributionRepository(session)
            .total_recorded_by(collector.id, TODAY)
            .is_zero
        )

    def test_collected_dates_for_collector(self, session, cycle_row, collector, client_row):
        self._add(session, cycle_row.id, collector.id, 0)
        session.commit()
        ids = SqlContributionRepository(session).collected_dates_for_collector(
            collector.id, CYCLE_START
        )
        assert ids == {client_row.id}

    def test_list_for_cycle_is_ordered_by_date(self, session, cycle_row, collector):
        for offset in (3, 1, 2):
            self._add(session, cycle_row.id, collector.id, offset)
        session.commit()
        rows = SqlContributionRepository(session).list_for_cycle(cycle_row.id)
        assert [r.contribution_date for r in rows] == sorted(
            r.contribution_date for r in rows
        )


class TestVarianceReport:
    """FR-25 — the three-way outer join the fakes cannot represent."""

    def test_reconciled_collector_shows_zero(self, session, cycle_row, collector):
        SqlContributionRepository(session).add(
            Contribution(
                id=None,
                reference="",
                cycle_id=cycle_row.id,
                contribution_date=CYCLE_START,
                amount=RATE,
                recorded_by_id=collector.id,
            )
        )
        repo = SqlRemittanceRepository(session)
        repo.save(
            RemittanceDeclaration(
                id=None,
                collector_id=collector.id,
                declaration_date=CYCLE_START,
                amount_declared=RATE,
            )
        )
        session.commit()

        rows = repo.variances_for(CYCLE_START)
        assert len(rows) == 1
        assert rows[0].variance.is_zero
        assert rows[0].is_reconciled

    def test_shortfall_is_surfaced(self, session, cycle_row, collector):
        """BR-01 — the case the system exists to detect."""
        contrib_repo = SqlContributionRepository(session)
        for offset in range(3):
            contrib_repo.add(
                Contribution(
                    id=None,
                    reference="",
                    cycle_id=cycle_row.id,
                    contribution_date=CYCLE_START + timedelta(days=offset),
                    amount=RATE,
                    recorded_by_id=collector.id,
                )
            )
        repo = SqlRemittanceRepository(session)
        repo.save(
            RemittanceDeclaration(
                id=None,
                collector_id=collector.id,
                declaration_date=CYCLE_START,
                amount_declared=Money.from_cedis("3.00"),
            )
        )
        session.commit()

        row = repo.variances_for(CYCLE_START)[0]
        assert row.total_recorded == RATE  # only day 0 falls on this date
        assert row.amount_declared == Money.from_cedis("3.00")
        assert row.variance == Money.from_cedis("7.00")
        assert not row.is_reconciled

    def test_collector_who_never_declared_shows_as_undeclared(
        self, session, cycle_row, collector
    ):
        SqlContributionRepository(session).add(
            Contribution(
                id=None,
                reference="",
                cycle_id=cycle_row.id,
                contribution_date=CYCLE_START,
                amount=RATE,
                recorded_by_id=collector.id,
            )
        )
        session.commit()

        row = SqlRemittanceRepository(session).variances_for(CYCLE_START)[0]
        assert row.amount_declared is None
        assert row.variance == RATE
        assert not row.is_reconciled

    def test_idle_collector_appears_with_zeroes(self, session, collector):
        """A collector who recorded nothing must still appear, otherwise a
        collector who simply stopped working would silently vanish."""
        rows = SqlRemittanceRepository(session).variances_for(TODAY)
        assert len(rows) == 1
        assert rows[0].total_recorded.is_zero

    def test_redeclaring_overwrites_the_same_day(self, session, collector):
        repo = SqlRemittanceRepository(session)
        for amount in ("10.00", "25.00"):
            repo.save(
                RemittanceDeclaration(
                    id=None,
                    collector_id=collector.id,
                    declaration_date=CYCLE_START,
                    amount_declared=Money.from_cedis(amount),
                )
            )
        session.commit()
        assert repo.get(collector.id, CYCLE_START).amount_declared == Money.from_cedis(
            "25.00"
        )


class TestAuditRepository:
    def test_append_and_retrieve(self, session, collector):
        repo = SqlAuditRepository(session)
        repo.append(
            actor_id=collector.id,
            action="RECORD_CONTRIBUTION",
            target_type="CONTRIBUTION",
            target_id="SB-TEST-0001",
            detail={"amount_pesewas": 1000},
        )
        session.commit()

        entries = repo.list_for_target("CONTRIBUTION", "SB-TEST-0001")
        assert len(entries) == 1
        assert entries[0]["action"] == "RECORD_CONTRIBUTION"
        assert entries[0]["detail"]["amount_pesewas"] == 1000
        assert entries[0]["occurred_at"] is not None

    def test_anonymous_actor_is_permitted(self, session):
        """A failed login against an unknown phone number has no known actor,
        but the attempt must still be recorded (NFR-09)."""
        from app.infrastructure.models import AuditLogModel

        SqlAuditRepository(session).append(
            actor_id=None,
            action="LOGIN_FAILED",
            target_type="USER",
            detail={"reason": "unknown_account"},
        )
        session.commit()

        stored = session.query(AuditLogModel).one()
        assert stored.actor_id is None
        assert stored.action == "LOGIN_FAILED"
        assert stored.detail["reason"] == "unknown_account"
        assert stored.occurred_at is not None

    def test_entries_are_returned_newest_first(self, session, collector):
        repo = SqlAuditRepository(session)
        for action in ("RECORD_CONTRIBUTION", "REVERSE_CONTRIBUTION"):
            repo.append(
                actor_id=collector.id,
                action=action,
                target_type="CONTRIBUTION",
                target_id="SB-TEST-0001",
            )
        session.commit()

        entries = repo.list_for_target("CONTRIBUTION", "SB-TEST-0001")
        assert len(entries) == 2
        assert entries[0]["occurred_at"] >= entries[1]["occurred_at"]
