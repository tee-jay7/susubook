"""End-to-end system tests over HTTP.

Test case identifiers correspond to the testing report (docs/09-testing.md).
"""

from __future__ import annotations

import pytest

from .conftest import PASSWORD, RATE, TODAY, login

pytestmark = pytest.mark.system


class TestAuthentication:
    """TC-AUTH — UC-01."""

    def test_anonymous_root_redirects_to_login(self, client, world):
        response = client.get("/")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_valid_login_redirects_to_the_role_landing_page(self, client, world):
        response = login(client, "0244000101")
        assert response.status_code == 302
        assert "/collector" in response.headers["Location"]

    def test_client_lands_on_their_own_card(self, client, world):
        response = login(client, "0201000202")
        assert "/my" in response.headers["Location"]

    def test_supervisor_lands_on_variances(self, client, world):
        response = login(client, "0244000100")
        assert "/supervisor" in response.headers["Location"]

    def test_wrong_password_is_rejected(self, client, world):
        response = client.post(
            "/login", data={"phone": "0244000101", "password": "wrong"}
        )
        assert response.status_code == 401

    def test_unknown_phone_gives_the_same_message_as_a_wrong_password(
        self, client, world
    ):
        """Distinguishing them would let an attacker enumerate registered
        numbers."""
        unknown = client.post(
            "/login", data={"phone": "0000000000", "password": "whatever"}
        )
        wrong = client.post(
            "/login", data={"phone": "0244000101", "password": "wrong"}
        )
        assert unknown.status_code == wrong.status_code == 401
        assert b"incorrect" in unknown.data and b"incorrect" in wrong.data

    def test_logout_clears_the_session(self, client, world):
        login(client, "0244000101")
        assert client.get("/collector/").status_code == 200
        client.post("/logout")
        assert client.get("/collector/").status_code == 302

    def test_failed_login_is_audited(self, client, world, db):
        from app.infrastructure.models import AuditLogModel

        client.post("/login", data={"phone": "0244000101", "password": "wrong"})
        actions = [a.action for a in db.query(AuditLogModel).all()]
        assert "LOGIN_FAILED" in actions


class TestAuthorisation:
    """TC-AUTHZ — FR-05, NFR-03, BR-R15."""

    def test_unauthenticated_pages_redirect(self, client, world):
        for path in ("/collector/", "/supervisor/", "/my/"):
            assert client.get(path).status_code == 302

    def test_collector_cannot_reach_supervisor_pages(self, client, world):
        login(client, "0244000101")
        assert client.get("/supervisor/").status_code == 403
        assert client.get("/supervisor/payouts").status_code == 403

    def test_client_cannot_reach_collector_pages(self, client, world):
        login(client, "0201000202")
        assert client.get("/collector/").status_code == 403

    def test_collector_cannot_reach_a_clients_self_service_page(self, client, world):
        login(client, "0244000101")
        assert client.get("/my/").status_code == 403

    def test_another_collector_cannot_open_a_scanned_card(self, client, world):
        """BR-R15 — the photographed-card threat.

        Kwame holds Joseph's client reference, as if read off a card
        photographed in the market. It gets him nothing.
        """
        login(client, "0244000102")
        response = client.get(f"/c/{world['public_ref']}")
        assert response.status_code == 403
        assert b"not on your route" in response.data

    def test_another_collector_cannot_record_against_the_client(self, client, world):
        login(client, "0244000102")
        response = client.post(f"/collector/collect/{world['public_ref']}")
        assert response.status_code == 403

    def test_denied_attempt_is_audited(self, client, world, db):
        from app.infrastructure.models import AuditLogModel

        login(client, "0244000102")
        client.get(f"/c/{world['public_ref']}")
        actions = [a.action for a in db.query(AuditLogModel).all()]
        assert "AUTHORISATION_DENIED" in actions


class TestCollectionFlow:
    """TC-COL — UC-03."""

    def test_route_sheet_lists_only_own_clients(self, client, world):
        login(client, "0244000101")
        response = client.get("/collector/")
        assert response.status_code == 200
        assert b"Kofi Boateng" in response.data

        client.post("/logout")
        login(client, "0244000102")
        assert b"Kofi Boateng" not in client.get("/collector/").data

    def test_scan_landing_page_shows_the_pre_filled_amount(self, client, world):
        login(client, "0244000101")
        response = client.get(f"/c/{world['public_ref']}")
        assert response.status_code == 200
        assert b"GHS 10.00" in response.data
        assert b"Confirm collection" in response.data

    def test_record_a_contribution(self, client, world, db):
        from app.infrastructure.models import ContributionModel

        login(client, "0244000101")
        response = client.post(f"/collector/collect/{world['public_ref']}")
        assert response.status_code == 302

        rows = db.query(ContributionModel).all()
        assert len(rows) == 1
        assert rows[0].amount_pesewas == RATE.pesewas
        assert rows[0].reference.startswith("SB-")

    def test_duplicate_same_day_is_refused_with_422(self, client, world):
        """BR-R5 through the full stack."""
        login(client, "0244000101")
        client.post(f"/collector/collect/{world['public_ref']}")
        response = client.post(f"/collector/collect/{world['public_ref']}")
        assert response.status_code == 422
        assert b"already recorded" in response.data

    def test_htmx_duplicate_returns_a_fragment_not_a_full_page(self, client, world):
        """The collector keeps their place on the route sheet."""
        login(client, "0244000101")
        client.post(f"/collector/collect/{world['public_ref']}")
        response = client.post(
            f"/collector/collect/{world['public_ref']}",
            headers={"HX-Request": "true"},
        )
        assert response.status_code == 422
        assert b"<html" not in response.data.lower()
        assert b"Not recorded" in response.data

    def test_htmx_collect_updates_the_running_total_out_of_band(self, client, world):
        """DEF-06 regression.

        Swapping only the route row left the day's total stale until a manual
        refresh, so a row marked Paid sat above a total reading GHS 0.00. Two
        figures disagreeing on one screen is worse than a figure that does not
        update, because it makes the collector distrust both.
        """
        login(client, "0244000101")
        response = client.post(
            f"/collector/collect/{world['public_ref']}",
            headers={"HX-Request": "true"},
        )
        assert response.status_code == 200
        body = response.data.decode()

        assert 'id="recorded-today"' in body, "total must be in the response"
        assert 'hx-swap-oob="true"' in body, "and marked for an out-of-band swap"
        assert "Recorded GHS 10.00" in body, "and carry the new total, not the old"

    def test_route_sheet_total_reflects_recorded_contributions(self, client, world):
        login(client, "0244000101")
        assert b"Recorded GHS 0.00" in client.get("/collector/").data
        client.post(f"/collector/collect/{world['public_ref']}")
        assert b"Recorded GHS 10.00" in client.get("/collector/").data

    def test_amount_must_be_a_multiple_of_the_rate(self, client, world):
        login(client, "0244000101")
        response = client.post(
            f"/collector/collect/{world['public_ref']}", data={"amount": "7.50"}
        )
        assert response.status_code == 422
        assert b"whole multiple" in response.data

    def test_unparseable_amount_is_rejected(self, client, world):
        login(client, "0244000101")
        response = client.post(
            f"/collector/collect/{world['public_ref']}", data={"amount": "abc"}
        )
        assert response.status_code == 422

    def test_unknown_client_reference_is_404_or_422(self, client, world):
        import uuid

        login(client, "0244000101")
        response = client.get(f"/c/{uuid.uuid4()}")
        assert response.status_code in (404, 422)


class TestEnrolment:
    """TC-ENR — UC-02."""

    def test_enrol_creates_client_login_and_cycle(self, client, world, db):
        from app.infrastructure.models import (
            ClientModel,
            ContributionCycleModel,
            UserModel,
        )

        login(client, "0244000101")
        response = client.post(
            "/collector/enrol",
            data={
                "full_name": "Ama Serwaa",
                "phone": "0201000201",
                "daily_rate": "5.00",
                "password": "susu5678",
                "business_type": "Provisions stall",
                "location": "Madina Market",
            },
        )
        assert response.status_code == 302

        created = db.query(ClientModel).filter_by(full_name="Ama Serwaa").one()
        assert created.daily_rate_pesewas == 500
        assert db.query(UserModel).filter_by(phone="0201000201").one() is not None
        assert (
            db.query(ContributionCycleModel).filter_by(client_id=created.id).one().status
            == "ACTIVE"
        )

    def test_the_new_client_can_sign_in_immediately(self, client, world):
        login(client, "0244000101")
        client.post(
            "/collector/enrol",
            data={
                "full_name": "Ama Serwaa",
                "phone": "0201000201",
                "daily_rate": "5.00",
                "password": "susu5678",
            },
        )
        client.post("/logout")
        response = client.post(
            "/login", data={"phone": "0201000201", "password": "susu5678"}
        )
        assert response.status_code == 302
        assert "/my" in response.headers["Location"]

    def test_short_password_is_rejected(self, client, world):
        login(client, "0244000101")
        response = client.post(
            "/collector/enrol",
            data={
                "full_name": "X",
                "phone": "0201000299",
                "daily_rate": "5.00",
                "password": "123",
            },
        )
        assert response.status_code == 422


class TestReconciliation:
    """TC-REC — UC-05, UC-06."""

    def test_declaring_matching_cash_reconciles(self, client, world):
        login(client, "0244000101")
        client.post(f"/collector/collect/{world['public_ref']}")
        response = client.post("/collector/declare", data={"amount": "10.00"})
        assert response.status_code == 302

        client.post("/logout")
        login(client, "0244000100")
        page = client.get("/supervisor/").data
        assert b"GHS 0.00" in page

    def test_shortfall_appears_on_the_supervisor_screen(self, client, world):
        """BR-01 end to end — the failure the system exists to detect."""
        login(client, "0244000101")
        client.post(f"/collector/collect/{world['public_ref']}")
        client.post("/collector/declare", data={"amount": "3.00"})
        client.post("/logout")

        login(client, "0244000100")
        page = client.get("/supervisor/").data
        assert b"GHS 7.00" in page
        assert b"unreconciled" in page

    def test_undeclared_collector_is_flagged(self, client, world):
        login(client, "0244000101")
        client.post(f"/collector/collect/{world['public_ref']}")
        client.post("/logout")

        login(client, "0244000100")
        assert b"NOT DECLARED" in client.get("/supervisor/").data


class TestPayoutFlow:
    """TC-PAY — UC-07.

    A cycle is due for payout when its end date has passed (BR-R12), not when
    a status flag says so, so these tests move the cycle genuinely into the
    past rather than flipping `status`. Contributions are inserted directly
    because the collection route always dates a contribution today — there is
    deliberately no way to backdate one over HTTP.
    """

    def _matured_cycle(self, db, world, *, days_paid: int = 1):
        from datetime import timedelta

        from app.infrastructure.models import ContributionCycleModel, ContributionModel
        from app.infrastructure.repositories import new_reference

        cycle = db.get(ContributionCycleModel, world["cycle_id"])
        cycle.start_date = TODAY - timedelta(days=40)
        cycle.end_date = TODAY - timedelta(days=10)
        db.flush()

        for offset in range(days_paid):
            db.add(
                ContributionModel(
                    reference=new_reference(),
                    cycle_id=cycle.id,
                    contribution_date=cycle.start_date + timedelta(days=offset),
                    amount_pesewas=RATE.pesewas,
                    recorded_by_id=world["collector"].id,
                )
            )
        db.commit()
        return cycle

    def test_matured_cycle_appears_for_release(self, client, world, db):
        self._matured_cycle(db, world)
        login(client, "0244000100")
        page = client.get("/supervisor/payouts").data
        assert b"Kofi Boateng" in page

    def test_release_computes_commission_and_opens_the_next_cycle(
        self, client, world, db
    ):
        from app.infrastructure.models import ContributionCycleModel, PayoutModel

        self._matured_cycle(db, world, days_paid=10)

        login(client, "0244000100")
        response = client.post(f"/supervisor/payouts/{world['cycle_id']}/release")
        assert response.status_code == 302

        db.expire_all()  # the app committed in its own session
        payout = db.query(PayoutModel).one()
        assert payout.total_collected_pesewas == 10_000
        assert payout.commission_pesewas == 1_000  # BR-R8, one day's rate
        assert payout.net_payout_pesewas == 9_000
        assert (
            payout.net_payout_pesewas + payout.commission_pesewas
            == payout.total_collected_pesewas
        )

        cycles = (
            db.query(ContributionCycleModel)
            .order_by(ContributionCycleModel.cycle_number)
            .all()
        )
        assert [c.status for c in cycles] == ["PAID_OUT", "ACTIVE"]
        assert cycles[1].daily_rate_pesewas == RATE.pesewas  # rate inherited

    def test_single_day_client_receives_nothing(self, client, world, db):
        """BR-R9 through the full stack: one day's contribution is the
        commission, so the client nets zero — and never a negative."""
        from app.infrastructure.models import PayoutModel

        self._matured_cycle(db, world, days_paid=1)

        login(client, "0244000100")
        client.post(f"/supervisor/payouts/{world['cycle_id']}/release")

        db.expire_all()
        payout = db.query(PayoutModel).one()
        assert payout.total_collected_pesewas == 1_000
        assert payout.commission_pesewas == 1_000
        assert payout.net_payout_pesewas == 0

    def test_second_release_is_refused(self, client, world, db):
        self._matured_cycle(db, world, days_paid=5)

        login(client, "0244000100")
        client.post(f"/supervisor/payouts/{world['cycle_id']}/release")
        response = client.post(f"/supervisor/payouts/{world['cycle_id']}/release")
        assert response.status_code == 422
        assert b"already been paid out" in response.data

    def test_collector_cannot_release(self, client, world, db):
        self._matured_cycle(db, world)
        login(client, "0244000101")
        response = client.post(f"/supervisor/payouts/{world['cycle_id']}/release")
        assert response.status_code == 403

    def test_release_is_audited(self, client, world, db):
        from app.infrastructure.models import AuditLogModel

        self._matured_cycle(db, world, days_paid=5)
        login(client, "0244000100")
        client.post(f"/supervisor/payouts/{world['cycle_id']}/release")

        db.expire_all()
        actions = [a.action for a in db.query(AuditLogModel).all()]
        assert "RELEASE_PAYOUT" in actions


class TestReversal:
    """TC-REV — UC-09, BR-R11."""

    def _record(self, client, world, db):
        from app.infrastructure.models import ContributionModel

        login(client, "0244000101")
        client.post(f"/collector/collect/{world['public_ref']}")
        client.post("/logout")
        return db.query(ContributionModel).one().reference

    def test_supervisor_reverses_and_the_original_survives(self, client, world, db):
        from app.infrastructure.models import ContributionModel

        reference = self._record(client, world, db)
        login(client, "0244000100")
        response = client.post(
            "/supervisor/reverse",
            data={"reference": reference, "reason": "wrong client"},
        )
        assert response.status_code == 302

        db.expire_all()
        rows = db.query(ContributionModel).all()
        assert len(rows) == 2, "original must not be deleted"
        original = next(r for r in rows if r.reference == reference)
        assert original.reversed_by_id is not None

    def test_reversal_frees_the_day_for_a_replacement(self, client, world, db):
        reference = self._record(client, world, db)
        login(client, "0244000100")
        client.post(
            "/supervisor/reverse", data={"reference": reference, "reason": "wrong"}
        )
        client.post("/logout")

        login(client, "0244000101")
        response = client.post(f"/collector/collect/{world['public_ref']}")
        assert response.status_code == 302

    def test_reason_is_required(self, client, world, db):
        reference = self._record(client, world, db)
        login(client, "0244000100")
        response = client.post(
            "/supervisor/reverse", data={"reference": reference, "reason": ""}
        )
        assert response.status_code == 422

    def test_collector_cannot_reverse(self, client, world, db):
        reference = self._record(client, world, db)
        login(client, "0244000101")
        response = client.post(
            "/supervisor/reverse", data={"reference": reference, "reason": "x"}
        )
        assert response.status_code == 403


class TestClientSelfService:
    """TC-CLI — UC-08. The answer to problem P1."""

    def test_client_sees_their_own_contributions_with_the_recording_collector(
        self, client, world, db
    ):
        login(client, "0244000101")
        client.post(f"/collector/collect/{world['public_ref']}")
        client.post("/logout")

        login(client, "0201000202")
        page = client.get("/my/").data
        assert b"My susu card" in page
        assert b"Joseph Osei" in page, "the recording collector must be named"
        assert b"You will receive" in page

    def test_card_renders_every_day_of_the_cycle(self, client, world):
        login(client, "0201000202")
        page = client.get("/my/").decode() if hasattr(client.get("/my/"), "decode") else client.get("/my/").data.decode()
        assert page.count('role="listitem"') == 31

    def test_history_page_renders(self, client, world):
        login(client, "0201000202")
        assert client.get("/my/history").status_code == 200

    def test_reversed_entries_remain_visible_to_the_client(self, client, world, db):
        from app.infrastructure.models import ContributionModel

        login(client, "0244000101")
        client.post(f"/collector/collect/{world['public_ref']}")
        client.post("/logout")
        reference = db.query(ContributionModel).one().reference

        login(client, "0244000100")
        client.post(
            "/supervisor/reverse", data={"reference": reference, "reason": "wrong"}
        )
        client.post("/logout")

        login(client, "0201000202")
        page = client.get("/my/").data
        assert b"REVERSED" in page
        assert b"REVERSAL" in page


class TestQrCard:
    """TC-QR — FR-39, FR-40, CR-001."""

    def test_card_page_renders_an_inline_svg(self, client, world):
        login(client, "0244000101")
        response = client.get(f"/collector/card/{world['public_ref']}")
        assert response.status_code == 200
        assert b"<svg" in response.data

    def test_card_discloses_no_personal_data_beyond_the_name(self, client, world):
        """NFR-06 — the encoded payload is a URL and an opaque reference."""
        login(client, "0244000101")
        page = client.get(f"/collector/card/{world['public_ref']}").data
        assert b"0201000202" not in page, "phone number must not appear on the card"

    def test_another_collector_cannot_print_the_card(self, client, world):
        login(client, "0244000102")
        assert client.get(f"/collector/card/{world['public_ref']}").status_code == 403


class TestSecurityControls:
    """TC-SEC — NFR-03."""

    def test_csrf_token_is_required_on_state_changing_posts(self, csrf_app, world):
        """With CSRF enforcement on, a POST without a token must be rejected."""
        test_client = csrf_app.test_client()
        test_client.post("/login", data={"phone": "0244000101", "password": PASSWORD})
        response = test_client.post(f"/collector/collect/{world['public_ref']}")
        assert response.status_code == 400

    def test_password_is_never_rendered(self, client, world):
        login(client, "0244000101")
        assert PASSWORD.encode() not in client.get("/collector/").data

    def test_password_is_stored_hashed(self, world, db):
        from app.infrastructure.models import UserModel

        stored = db.query(UserModel).filter_by(phone="0244000101").one()
        assert stored.password_hash.startswith("$argon2")
        assert PASSWORD not in stored.password_hash

    def test_urls_expose_opaque_references_not_sequential_ids(self, client, world):
        """BR-R14 — no enumerable identifier reaches the client.

        The negative assertion matches a *complete* path segment of digits.
        Substring matching was wrong here: `/collector/client/1` is a substring
        of `/collector/client/1a2b3c…`, so the test failed whenever a randomly
        generated UUID happened to start with the digit 1 — roughly one run in
        sixteen, and only ever in a full-suite run. A flaky security test is
        worse than none, because it trains you to ignore it.
        """
        import re

        login(client, "0244000101")
        page = client.get("/collector/").data.decode()

        assert f"/collector/client/{world['public_ref']}" in page

        numeric_links = re.findall(r"/collector/client/(\d+)(?=[\"'/?\s>])", page)
        assert numeric_links == [], (
            f"sequential ids leaked into URLs: {numeric_links} — these are "
            f"enumerable and violate BR-R14"
        )

    def test_unknown_page_returns_404(self, client, world):
        login(client, "0244000101")
        assert client.get("/collector/nonexistent").status_code == 404


class TestOperational:
    """TC-OPS — deployment support endpoints."""

    def test_health_endpoint_is_public_and_reports_database(self, client, db):
        """Cloud Run probes cannot authenticate, so this must be open."""
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json == {"status": "ok", "database": "ok"}

    def test_health_endpoint_discloses_nothing_useful_to_an_attacker(
        self, client, db
    ):
        """Open by necessity, so it must not leak version, host or error text."""
        body = client.get("/healthz").data.decode().lower()
        for leak in ("postgres", "flask", "python", "traceback", "10.128", "version"):
            assert leak not in body, f"health endpoint leaked '{leak}'"
