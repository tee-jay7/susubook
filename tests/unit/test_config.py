"""Configuration resolution, especially the production connection URL.

Worth testing directly: a mistake here surfaces as a connection failure in a
deployed container, which is the slowest possible place to debug one.
"""

from __future__ import annotations

import pytest

from app.config import LOCAL_DATABASE_URL, Config, resolve_database_url

DB_VARS = ("DATABASE_URL", "DB_PASSWORD", "DB_USER", "DB_HOST", "DB_PORT", "DB_NAME")


@pytest.fixture
def clean_env(monkeypatch):
    """Strip every database variable.

    `load_dotenv()` runs at import and searches upward from app/config.py, so a
    developer's .env is already in os.environ by the time any test runs. Without
    this the production code path is untestable locally — which is precisely how
    a broken deployment configuration reaches production unnoticed.
    """
    for name in DB_VARS:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


class TestDatabaseUrlResolution:
    def test_falls_back_to_local_docker_when_nothing_is_set(self, clean_env):
        assert resolve_database_url() == LOCAL_DATABASE_URL

    def test_explicit_database_url_wins(self, clean_env):
        clean_env.setenv("DATABASE_URL", "postgresql+psycopg://a:b@h:1/d")
        clean_env.setenv("DB_PASSWORD", "ignored")
        assert resolve_database_url() == "postgresql+psycopg://a:b@h:1/d"

    def test_composes_from_parts_when_only_the_password_is_secret(self, clean_env):
        """The production shape: Secret Manager holds the password, and host,
        port, database and role are ordinary service configuration."""
        clean_env.setenv("DB_PASSWORD", "s3cret")
        clean_env.setenv("DB_USER", "susu_app")
        clean_env.setenv("DB_HOST", "10.128.0.6")
        clean_env.setenv("DB_PORT", "5432")
        clean_env.setenv("DB_NAME", "susu_book")

        assert resolve_database_url() == (
            "postgresql+psycopg://susu_app:s3cret@10.128.0.6:5432/susu_book"
        )

    def test_uses_the_psycopg3_driver(self, clean_env):
        """Plain `postgresql://` makes SQLAlchemy reach for psycopg2, which is
        not installed — and the resulting error names the driver, not the
        configuration, which sends you looking in the wrong place."""
        clean_env.setenv("DB_PASSWORD", "x")
        assert resolve_database_url().startswith("postgresql+psycopg://")

    @pytest.mark.parametrize(
        "password,encoded",
        [
            ("p@ssword", "p%40ssword"),
            ("with:colon", "with%3Acolon"),
            ("with/slash", "with%2Fslash"),
            ("with#hash", "with%23hash"),
            ("with?question", "with%3Fquestion"),
        ],
    )
    def test_password_special_characters_are_percent_encoded(
        self, clean_env, password, encoded
    ):
        """A generated password containing URL syntax would otherwise corrupt
        the URL, producing a parse error that looks nothing like a credentials
        problem."""
        clean_env.setenv("DB_PASSWORD", password)
        clean_env.setenv("DB_HOST", "10.128.0.6")
        url = resolve_database_url()
        assert encoded in url
        assert url.endswith("@10.128.0.6:5432/susu_book")

    def test_defaults_match_the_deployed_database(self, clean_env):
        """Only DB_PASSWORD is strictly required; the rest default to the
        deployment described in deploy/README.md."""
        clean_env.setenv("DB_PASSWORD", "x")
        url = resolve_database_url()
        assert "susu_app" in url and "susu_book" in url and ":5432/" in url


class TestConfig:
    def test_secure_cookies_only_in_production(self, monkeypatch):
        monkeypatch.setenv("FLASK_ENV", "development")
        assert Config().SESSION_COOKIE_SECURE is False
        monkeypatch.setenv("FLASK_ENV", "production")
        assert Config().SESSION_COOKIE_SECURE is True

    def test_cookie_hardening_defaults(self):
        cfg = Config()
        assert cfg.SESSION_COOKIE_HTTPONLY is True
        assert cfg.SESSION_COOKIE_SAMESITE == "Lax"

    def test_base_url_is_empty_by_default(self, monkeypatch):
        """Empty means 'derive from the request', which is what lets a first
        deploy produce correct QR cards before the service URL is known."""
        monkeypatch.delenv("BASE_URL", raising=False)
        assert Config().BASE_URL == ""
