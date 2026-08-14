"""The database-enforced business invariants (defence in depth).

The domain layer already checks BR-R2, BR-R5 and BR-R10. These tests assert
that the *database* also refuses to hold a violating row — so a bug in the
service layer, or a direct SQL write by an operator, cannot corrupt them.

Each test bypasses the service layer entirely and writes through the ORM, to
prove the guarantee does not depend on application code being correct.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.infrastructure.models import (
    ContributionCycleModel,
    ContributionModel,
    PayoutModel,
)

from .conftest import CYCLE_START, RATE

pytestmark = pytest.mark.integration


class TestBR_R2_OneActiveCyclePerClient:
    def test_second_active_cycle_is_refused(self, session, client_row, cycle_row):
        session.add(
            ContributionCycleModel(
                client_id=client_row.id,
                cycle_number=2,
                start_date=CYCLE_START,
                end_date=CYCLE_START + timedelta(days=30),
                status="ACTIVE",
                daily_rate_pesewas=RATE.pesewas,
            )
        )
        with pytest.raises(IntegrityError, match="ux_active_cycle_per_client"):
            session.commit()

    def test_a_second_cycle_is_allowed_once_the_first_is_paid_out(
        self, session, client_row, cycle_row
    ):
        """The partial index constrains ACTIVE rows only — cycles must succeed
        one another, which is the whole point of making it partial."""
        cycle_row.status = "PAID_OUT"
        session.flush()
        session.add(
            ContributionCycleModel(
                client_id=client_row.id,
                cycle_number=2,
                start_date=CYCLE_START + timedelta(days=31),
                end_date=CYCLE_START + timedelta(days=61),
                status="ACTIVE",
                daily_rate_pesewas=RATE.pesewas,
            )
        )
        session.commit()  # must not raise

    def test_two_clients_may_each_have_an_active_cycle(
        self, session, client_row, cycle_row, collector
    ):
        from app.infrastructure.models import ClientModel, UserModel

        user = UserModel(
            full_name="Ama Serwaa",
            phone="0201000201",
            password_hash="x",
            role="CLIENT",
        )
        session.add(user)
        session.flush()
        other = ClientModel(
            user_id=user.id,
            collector_id=collector.id,
            full_name="Ama Serwaa",
            phone="0201000201",
            daily_rate_pesewas=500,
        )
        session.add(other)
        session.flush()
        session.add(
            ContributionCycleModel(
                client_id=other.id,
                cycle_number=1,
                start_date=CYCLE_START,
                end_date=CYCLE_START + timedelta(days=30),
                status="ACTIVE",
                daily_rate_pesewas=500,
            )
        )
        session.commit()  # must not raise


class TestBR_R5_OneEffectiveContributionPerDay:
    def _contribution(self, cycle_id, on, reference, **kw):
        return ContributionModel(
            reference=reference,
            cycle_id=cycle_id,
            contribution_date=on,
            amount_pesewas=RATE.pesewas,
            recorded_by_id=kw.pop("recorded_by_id"),
            **kw,
        )

    def test_duplicate_on_the_same_day_is_refused(self, session, cycle_row, collector):
        for ref in ("SB-AAAA-0001", "SB-BBBB-0002"):
            session.add(
                self._contribution(
                    cycle_row.id, CYCLE_START, ref, recorded_by_id=collector.id
                )
            )
        with pytest.raises(IntegrityError, match="ux_effective_contribution_per_day"):
            session.commit()

    def test_different_days_are_allowed(self, session, cycle_row, collector):
        for offset, ref in ((0, "SB-AAAA-0001"), (1, "SB-BBBB-0002")):
            session.add(
                self._contribution(
                    cycle_row.id,
                    CYCLE_START + timedelta(days=offset),
                    ref,
                    recorded_by_id=collector.id,
                )
            )
        session.commit()  # must not raise

    def test_a_replacement_may_share_a_day_with_a_reversed_entry(
        self, session, cycle_row, collector
    ):
        """The reason the index is partial rather than plain.

        Correcting by reversal (BR-R11) requires the reversed original, the
        reversal itself, and the replacement to coexist on one date. A plain
        UNIQUE(cycle_id, contribution_date) would make correction impossible.
        """
        original = self._contribution(
            cycle_row.id, CYCLE_START, "SB-ORIG-0001", recorded_by_id=collector.id
        )
        session.add(original)
        session.commit()

        reversal = self._contribution(
            cycle_row.id,
            CYCLE_START,
            "SB-REVL-0002",
            recorded_by_id=collector.id,
            is_reversal=True,
        )
        session.add(reversal)
        session.flush()
        original.reversed_by_id = reversal.id
        session.commit()

        replacement = self._contribution(
            cycle_row.id, CYCLE_START, "SB-REPL-0003", recorded_by_id=collector.id
        )
        session.add(replacement)
        session.commit()  # must not raise

        rows = session.query(ContributionModel).all()
        assert len(rows) == 3, "all three entries must survive; nothing is deleted"
        effective = [r for r in rows if r.reversed_by_id is None and not r.is_reversal]
        assert len(effective) == 1
        assert effective[0].reference == "SB-REPL-0003"

    def test_reference_is_globally_unique(self, session, cycle_row, collector):
        for offset in (0, 1):
            session.add(
                self._contribution(
                    cycle_row.id,
                    CYCLE_START + timedelta(days=offset),
                    "SB-SAME-0001",
                    recorded_by_id=collector.id,
                )
            )
        with pytest.raises(IntegrityError):
            session.commit()


class TestBR_R10_OnePayoutPerCycle:
    def _payout(self, cycle_id, released_by_id, total=31000, commission=1000):
        return PayoutModel(
            cycle_id=cycle_id,
            total_collected_pesewas=total,
            commission_pesewas=commission,
            net_payout_pesewas=total - commission,
            released_by_id=released_by_id,
        )

    def test_second_payout_is_refused(self, session, cycle_row, supervisor):
        session.add(self._payout(cycle_row.id, supervisor.id))
        session.commit()
        session.add(self._payout(cycle_row.id, supervisor.id))
        with pytest.raises(IntegrityError):
            session.commit()

    def test_money_must_balance(self, session, cycle_row, supervisor):
        """ck_payout_balances: net + commission = total.

        A payout row that does not conserve money is unrepresentable, so an
        arithmetic bug cannot silently create or destroy client funds.
        """
        session.add(
            PayoutModel(
                cycle_id=cycle_row.id,
                total_collected_pesewas=31000,
                commission_pesewas=1000,
                net_payout_pesewas=29999,  # 1 pesewa vanishes
                released_by_id=supervisor.id,
            )
        )
        with pytest.raises(IntegrityError, match="ck_payout_balances"):
            session.commit()

    def test_negative_payout_is_refused(self, session, cycle_row, supervisor):
        session.add(
            PayoutModel(
                cycle_id=cycle_row.id,
                total_collected_pesewas=0,
                commission_pesewas=1000,
                net_payout_pesewas=-1000,
                released_by_id=supervisor.id,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


class TestOtherConstraints:
    def test_daily_rate_must_be_positive(self, session, collector):
        from app.infrastructure.models import ClientModel, UserModel

        user = UserModel(
            full_name="X", phone="0209999999", password_hash="x", role="CLIENT"
        )
        session.add(user)
        session.flush()
        session.add(
            ClientModel(
                user_id=user.id,
                collector_id=collector.id,
                full_name="X",
                phone="0209999999",
                daily_rate_pesewas=0,
            )
        )
        with pytest.raises(IntegrityError, match="ck_client_rate_positive"):
            session.commit()

    def test_contribution_amount_must_be_positive(
        self, session, cycle_row, collector
    ):
        session.add(
            ContributionModel(
                reference="SB-ZERO-0001",
                cycle_id=cycle_row.id,
                contribution_date=CYCLE_START,
                amount_pesewas=0,
                recorded_by_id=collector.id,
            )
        )
        with pytest.raises(IntegrityError, match="ck_contribution_positive"):
            session.commit()

    def test_cycle_end_must_not_precede_start(self, session, client_row):
        session.add(
            ContributionCycleModel(
                client_id=client_row.id,
                cycle_number=9,
                start_date=CYCLE_START,
                end_date=CYCLE_START - timedelta(days=1),
                status="MATURED",
                daily_rate_pesewas=RATE.pesewas,
            )
        )
        with pytest.raises(IntegrityError, match="ck_cycle_dates"):
            session.commit()

    def test_role_must_be_a_known_value(self, session):
        from app.infrastructure.models import UserModel

        session.add(
            UserModel(
                full_name="X", phone="0208888888", password_hash="x", role="WIZARD"
            )
        )
        with pytest.raises(IntegrityError, match="ck_user_role"):
            session.commit()

    def test_one_remittance_declaration_per_collector_per_day(
        self, session, collector
    ):
        from app.infrastructure.models import RemittanceDeclarationModel

        for amount in (34000, 25000):
            session.add(
                RemittanceDeclarationModel(
                    collector_id=collector.id,
                    declaration_date=CYCLE_START,
                    amount_declared_pesewas=amount,
                )
            )
        with pytest.raises(IntegrityError, match="uq_declaration_per_day"):
            session.commit()
