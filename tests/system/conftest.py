"""System test fixtures — the whole stack, driven over HTTP.

Exercises what neither the unit nor the integration suite reaches: routing,
session handling, CSRF, the role decorators, template rendering, and the
HTMX/422 error path. Runs against the same `susubook_test` database.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import text

from app import create_app
from app.config import Config
from app.domain.money import Money
from app.infrastructure.db import init_schema, make_session_factory
from app.infrastructure.models import (
    Base,
    ClientModel,
    ContributionCycleModel,
    UserModel,
)
from app.services.security import hash_password

from tests.integration.conftest import _test_url

TODAY = date(2026, 9, 15)
CYCLE_START = date(2026, 9, 1)
RATE = Money.from_cedis("10.00")
PASSWORD = "susu1234"


@pytest.fixture(scope="session")
def app():
    cfg = Config()
    cfg.DATABASE_URL = _test_url()
    cfg.SECRET_KEY = "system-test-key"
    cfg.BASE_URL = "http://localhost"

    application = create_app(cfg, clock=lambda: TODAY)
    application.config["TESTING"] = True
    init_schema(application.extensions["engine"])
    return application


@pytest.fixture
def db(app):
    """Clean database per test."""
    factory = make_session_factory(app.extensions["engine"])
    s = factory()
    tables = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    s.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def csrf_app(app):
    """The same app with CSRF enforced, for the security test."""
    app.config["WTF_CSRF_ENABLED"] = True
    yield app
    app.config["WTF_CSRF_ENABLED"] = False


@pytest.fixture(autouse=True)
def _disable_csrf(app):
    """CSRF is off by default so flow tests stay readable; one dedicated test
    turns it back on and asserts it actually blocks."""
    app.config["WTF_CSRF_ENABLED"] = False


@pytest.fixture
def world(db):
    """A branch: supervisor, two collectors, one client with an open cycle."""
    supervisor = UserModel(
        full_name="Mariama Adjei",
        phone="0244000100",
        password_hash=hash_password(PASSWORD),
        role="SUPERVISOR",
    )
    collector = UserModel(
        full_name="Joseph Osei",
        phone="0244000101",
        password_hash=hash_password(PASSWORD),
        role="COLLECTOR",
    )
    other_collector = UserModel(
        full_name="Kwame Tetteh",
        phone="0244000102",
        password_hash=hash_password(PASSWORD),
        role="COLLECTOR",
    )
    client_user = UserModel(
        full_name="Kofi Boateng",
        phone="0201000202",
        password_hash=hash_password(PASSWORD),
        role="CLIENT",
    )
    db.add_all([supervisor, collector, other_collector, client_user])
    db.flush()

    client_row = ClientModel(
        user_id=client_user.id,
        collector_id=collector.id,
        full_name="Kofi Boateng",
        phone="0201000202",
        business_type="Kiosk",
        location="Madina Market",
        daily_rate_pesewas=RATE.pesewas,
    )
    db.add(client_row)
    db.flush()

    cycle = ContributionCycleModel(
        client_id=client_row.id,
        cycle_number=1,
        start_date=CYCLE_START,
        end_date=CYCLE_START + timedelta(days=30),
        status="ACTIVE",
        daily_rate_pesewas=RATE.pesewas,
    )
    db.add(cycle)
    db.commit()

    return {
        "supervisor": supervisor,
        "collector": collector,
        "other_collector": other_collector,
        "client_user": client_user,
        "client": client_row,
        "cycle": cycle,
        "public_ref": str(client_row.public_ref),
        "cycle_id": cycle.id,
    }


def login(client, phone: str, password: str = PASSWORD):
    return client.post(
        "/login", data={"phone": phone, "password": password}, follow_redirects=False
    )
