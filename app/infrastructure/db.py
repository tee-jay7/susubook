"""Engine, session factory and schema creation — layer 4."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


def make_engine(database_url: str, *, echo: bool = False) -> Engine:
    return create_engine(
        database_url,
        echo=echo,
        pool_pre_ping=True,  # free-tier Postgres drops idle connections
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
