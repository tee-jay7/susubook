"""Integration test fixtures — real PostgreSQL, no fakes.

These tests exist to cover what the unit suite deliberately cannot: the
SQLAlchemy repositories, the entity/record mapping (TD-07), and above all the
three business invariants enforced by partial unique indexes. Those indexes
are the defence-in-depth claim of the design, and a claim about PostgreSQL
behaviour can only be verified against PostgreSQL.

Runs against a separate `susubook_test` database on the same container, so a
test run can never touch development data.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.domain.money import Money
from app.infrastructure.db import init_schema, make_engine, make_session_factory
from app.infrastructure.models import Base, ClientModel, ContributionCycleModel, UserModel
from app.services.security import hash_password

TEST_DB = "susubook_test"

TODAY = date(2026, 9, 15)
CYCLE_START = date(2026, 9, 1)
RATE = Money.from_cedis("10.00")


def _admin_url() -> str:
    """Connection URL for the maintenance database, to CREATE DATABASE from."""
    base = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://susubook:susubook_dev@localhost:5434/susubook",
    )
    return base.rsplit("/", 1)[0] + "/postgres"


def _test_url() -> str:
    base = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://susubook:susubook_dev@localhost:5434/susubook",
    )
    return base.rsplit("/", 1)[0] + f"/{TEST_DB}"


@pytest.fixture(scope="session")
def engine():
    admin = create_engine(_admin_url(), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": TEST_DB}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{TEST_DB}"'))
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"PostgreSQL unavailable — is `docker compose up -d` running? {exc}")
    finally:
        admin.dispose()

    eng = make_engine(_test_url())
    Base.metadata.drop_all(eng)
    init_schema(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine) -> Session:
    """A clean database for every test.

    Truncating with RESTART IDENTITY rather than rolling back a transaction:
    the partial unique indexes must be exercised against real committed rows,
    and some of these tests deliberately provoke integrity errors, which would
    poison an outer transaction.
    """
    factory = make_session_factory(engine)
    s = factory()
    tables = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    s.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    s.commit()
    yield s
    s.rollback()
    s.close()


# -- builders -------------------------------------------------------------


@pytest.fixture
def collector(session) -> UserModel:
    m = UserModel(
        full_name="Joseph Osei",
        phone="0244000101",
        password_hash=hash_password("susu1234"),
        role="COLLECTOR",
    )
    session.add(m)
    session.commit()
    return m


@pytest.fixture
def supervisor(session) -> UserModel:
    m = UserModel(
        full_name="Mariama Adjei",
        phone="0244000100",
        password_hash=hash_password("susu1234"),
        role="SUPERVISOR",
    )
    session.add(m)
    session.commit()
    return m


@pytest.fixture
def client_row(session, collector) -> ClientModel:
    user = UserModel(
        full_name="Kofi Boateng",
        phone="0201000202",
        password_hash=hash_password("susu1234"),
        role="CLIENT",
    )
    session.add(user)
    session.flush()

    m = ClientModel(
        user_id=user.id,
        collector_id=collector.id,
        full_name="Kofi Boateng",
        phone="0201000202",
        business_type="Kiosk",
        location="Madina Market",
        daily_rate_pesewas=RATE.pesewas,
    )
    session.add(m)
    session.commit()
    return m


@pytest.fixture
def cycle_row(session, client_row) -> ContributionCycleModel:
    m = ContributionCycleModel(
        client_id=client_row.id,
        cycle_number=1,
        start_date=CYCLE_START,
        end_date=CYCLE_START + timedelta(days=30),
        status="ACTIVE",
        daily_rate_pesewas=RATE.pesewas,
    )
    session.add(m)
    session.commit()
    return m
