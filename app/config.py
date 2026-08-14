"""Environment-driven configuration.

The only thing that differs between development and production is the values
here (NFR-10). Same code, same PostgreSQL engine, different DATABASE_URL.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()

LOCAL_DATABASE_URL = (
    "postgresql+psycopg://susubook:susubook_dev@localhost:5434/susubook"
)


def resolve_database_url() -> str:
    """Build the connection URL, preferring composed parts over a whole URL.

    In production only the password is a secret; host, port, database and role
    are ordinary configuration. Keeping them separate means Secret Manager holds
    exactly one value that needs protecting, and the rest stays readable in the
    service definition where an operator can see it.

    The password is percent-encoded: an unescaped `@`, `:`, `/` or `#` in a
    generated password would otherwise corrupt the URL and produce a parse
    error that looks nothing like a credentials problem.
    """
    explicit = os.environ.get("DATABASE_URL")
    if explicit:
        return explicit

    password = os.environ.get("DB_PASSWORD")
    if not password:
        return LOCAL_DATABASE_URL

    user = os.environ.get("DB_USER", "susu_app")
    host = os.environ.get("DB_HOST", "127.0.0.1")
    port = os.environ.get("DB_PORT", "5432")
    name = os.environ.get("DB_NAME", "susu_book")
    return (
        f"postgresql+psycopg://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{name}"
    )


@dataclass
class Config:
    SECRET_KEY: str = field(
        default_factory=lambda: os.environ.get("SECRET_KEY", "dev-only-not-for-production")
    )
    DATABASE_URL: str = field(default_factory=resolve_database_url)
    # Optional. When unset, the request's own origin is used (see
    # app/web/collector.py::_base_url). That avoids a chicken-and-egg on first
    # deploy — a Cloud Run URL is not known until the service exists — and means
    # QR cards stay correct if the application later moves to a custom domain,
    # with no configuration change and no reissued cards.
    BASE_URL: str = field(default_factory=lambda: os.environ.get("BASE_URL", ""))
    ENV: str = field(default_factory=lambda: os.environ.get("FLASK_ENV", "development"))

    # Session cookie hardening (NFR-03)
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"
    PERMANENT_SESSION_LIFETIME: int = 60 * 60 * 8  # FR-04 idle timeout

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"

    @property
    def SESSION_COOKIE_SECURE(self) -> bool:
        # Secure cookies require HTTPS; enabling in local dev would break login.
        return self.is_production

    def as_flask_mapping(self) -> dict:
        return {
            "SECRET_KEY": self.SECRET_KEY,
            "SESSION_COOKIE_HTTPONLY": self.SESSION_COOKIE_HTTPONLY,
            "SESSION_COOKIE_SAMESITE": self.SESSION_COOKIE_SAMESITE,
            "SESSION_COOKIE_SECURE": self.SESSION_COOKIE_SECURE,
            "PERMANENT_SESSION_LIFETIME": self.PERMANENT_SESSION_LIFETIME,
            "BASE_URL": self.BASE_URL,
        }
