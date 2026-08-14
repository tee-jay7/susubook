"""Engine, session factory and schema creation — layer 4."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


def make_engine(database_url: str, *, echo: bool = False) -> Engine:
    """Engine with a pool sized for a scale-to-zero runtime.

    Cloud Run runs several instances, each with its own pool, against a single
    small PostgreSQL server. The defaults (5 + 10 overflow per process, times
    two gunicorn workers, times N instances) would exhaust the server's
    connection limit well before the application was under any real load, and
    the failure mode is being locked out of your own database.

    A deliberately small pool bounds that: 5 connections per worker at most.
    `pool_recycle` closes connections before an idle server-side timeout can
    hand back a dead one.
    """
    return create_engine(
        database_url,
        echo=echo,
        pool_size=2,
        max_overflow=3,
        pool_timeout=10,
        pool_recycle=1800,
        pool_pre_ping=True,  # a scaled-to-zero gap outlives idle connections
        future=True,
    )


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def init_schema(engine: Engine) -> None:
    """Create all tables and indexes.

    FIXME(TD-01): schema is created with metadata.create_all() and there are no
      versioned migrations. Adding a column in production therefore requires
      manual DDL, and there is no down-path. Alembic was cut from the 48-hour
      scope (docs/05-effort-estimation.md section 4.6); it is the first item in
      the technical debt repayment plan.
    """
    Base.metadata.create_all(engine)


def drop_schema(engine: Engine) -> None:
    """Test and development convenience only."""
    Base.metadata.drop_all(engine)


class SqlAlchemyUnitOfWork:
    """Transaction boundary. One commit per use case, at the service layer."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def commit(self) -> None:
        self._s.commit()

    def rollback(self) -> None:
        self._s.rollback()

    def flush(self) -> None:
        self._s.flush()
