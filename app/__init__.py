"""Application factory and composition root.

Session 5 names the Application Factory as the practical form of dependency
injection: production wiring and test wiring differ only in what is passed in
here, and nothing below layer 1 knows the difference.
"""

from __future__ import annotations

from datetime import date
from typing import Callable

from flask import Flask, g, render_template, request
from flask_wtf.csrf import CSRFProtect

from app.config import Config
from app.domain.errors import DomainError, NotAuthorised
from app.infrastructure.db import init_schema, make_engine, make_session_factory
from app.services.container import build_services

csrf = CSRFProtect()


def create_app(
    config: Config | None = None, *, clock: Callable[[], date] = date.today
) -> Flask:
    # Templates and static assets live with the presentation layer (app/web),
    # not at the package root, so the folder tree matches the architecture.
    app = Flask(
        __name__,
        template_folder="web/templates",
        static_folder="web/static",
    )
    cfg = config or Config()
    app.config.update(cfg.as_flask_mapping())
    app.config["SUSUBOOK_CONFIG"] = cfg

    engine = make_engine(cfg.DATABASE_URL)
    session_factory = make_session_factory(engine)
    app.extensions["engine"] = engine
    app.extensions["session_factory"] = session_factory

    csrf.init_app(app)  # NFR-03: CSRF token on every state-changing form

    # -- request-scoped session and services ------------------------------

    @app.before_request
    def _open_unit_of_work() -> None:
        g.db = session_factory()
        g.services = build_services(g.db, clock=clock)
        from app.web.security import load_current_user

        load_current_user()

    @app.teardown_request
    def _close_unit_of_work(exception: BaseException | None) -> None:
        db = g.pop("db", None)
        if db is None:
            return
        if exception is not None:
            db.rollback()
        db.close()

    # -- error handling ---------------------------------------------------

    @app.errorhandler(NotAuthorised)
    def _forbidden(error: NotAuthorised):
        return render_template("error.html", code=403, message=error.message), 403

    @app.errorhandler(DomainError)
    def _rule_violated(error: DomainError):
        """A business rule refused the request.

        422 rather than 400: the request was well-formed, the *domain* rejected
        it. HTMX swaps the fragment in place so the collector sees the reason
        without losing their position.
        """
        if request.headers.get("HX-Request"):
            return render_template("partials/error_banner.html", message=error.message), 422
        return render_template("error.html", code=422, message=error.message), 422

    @app.errorhandler(403)
    def _http_forbidden(_error):
        return render_template(
            "error.html", code=403, message="You do not have access to that page."
        ), 403

    @app.errorhandler(404)
    def _not_found(_error):
        return render_template(
            "error.html", code=404, message="That page does not exist."
        ), 404

    # -- blueprints -------------------------------------------------------

    from app.web import auth, client, collector, supervisor

    app.register_blueprint(auth.bp)
    app.register_blueprint(collector.bp)
    app.register_blueprint(collector.scan_bp)  # /c/<ref> — QR scan entry (FR-40)
    app.register_blueprint(supervisor.bp)
    app.register_blueprint(client.bp)

    # -- operational endpoints --------------------------------------------

    @app.get("/healthz")
    def healthz():
        """Liveness and database reachability.

        Unauthenticated by necessity — a probe cannot log in — so it returns
        only a status, never a version, hostname or error detail that would help
        someone map the deployment.
        """
        from sqlalchemy import text

        try:
            g.db.execute(text("SELECT 1"))
        except Exception:  # noqa: BLE001 — the cause is logged, not disclosed
            app.logger.exception("health check: database unreachable")
            return {"status": "degraded", "database": "unreachable"}, 503
        return {"status": "ok", "database": "ok"}, 200

    # -- template helpers -------------------------------------------------

    from app.web.security import current_user

    from datetime import timedelta

    def cycle_days(cycle) -> list:
        """Every date in a cycle, for rendering the 31-box card (FR-16)."""
        return [
            cycle.start_date + timedelta(days=i) for i in range(cycle.length_in_days)
        ]

    # A Jinja global, not a context processor: macros imported without
    # `with context` do not receive the template context, so a context
    # processor would leave cycle_days undefined inside the card macro.
    app.jinja_env.globals["cycle_days"] = cycle_days

    @app.context_processor
    def _template_globals() -> dict:
        return {"current_user": current_user(), "today": clock()}

    # -- CLI --------------------------------------------------------------

    @app.cli.command("db-init")
    def db_init() -> None:
        """Create the schema (TD-01: no versioned migrations)."""
        init_schema(engine)
        print("Schema created.")

    @app.cli.command("seed")
    def seed_command() -> None:
        """Load demo accounts and a realistic collection history."""
        from app.seed import seed

        session = session_factory()
        try:
            seed(session, today=clock())
            session.commit()
            print("Seed data loaded.")
        finally:
            session.close()

    return app
