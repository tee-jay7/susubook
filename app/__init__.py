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
from app.infrastructure.db import (
    apply_manual_migrations,
    init_schema,
    make_engine,
    make_session_factory,
)
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

    # SMS notification (FR-31, CR-002). Built once at startup rather than per
    # request. Without an API key this is a gateway that sends nothing, so the
    # failure mode of missing configuration is silence, not an exception.
    from app.services.notifications import NotificationService, NullSmsGateway

    if cfg.sms_enabled:
        from app.infrastructure.arkesel import ArkeselSmsGateway

        gateway = ArkeselSmsGateway(
            cfg.SMS_API_KEY,
            sender_id=cfg.SMS_SENDER_ID,
            **({"endpoint": cfg.SMS_API_URL} if cfg.SMS_API_URL else {}),
        )
        app.logger.info(
            "sms enabled; allowlist holds %d number(s)%s",
            len(cfg.sms_allowlist),
            " — ALLOW-ALL IS SET" if cfg.sms_allow_all else "",
        )
    else:
        gateway = NullSmsGateway()
        app.logger.info("sms disabled: no API key configured")

    notifications = NotificationService(
        gateway,
        allowlist=cfg.sms_allowlist,
        allow_all=cfg.sms_allow_all,
    )
    app.extensions["notifications"] = notifications

    # -- request-scoped session and services ------------------------------

    @app.before_request
    def _open_unit_of_work() -> None:
        g.db = session_factory()
        g.services = build_services(g.db, clock=clock, notifications=notifications)
        from app.web.security import load_current_user

        load_current_user()

    @app.before_request
    def _require_password_change() -> None:
        """TD-15 — nothing is shown until a forced password change is made.

        Enforced here rather than per-route: a guard that must be remembered on
        every new route is a guard that will eventually be forgotten.
        """
        from flask import redirect, url_for

        from app.web.security import current_user

        user = current_user()
        if user is None:
            return None
        allowed = {"auth.change_password", "auth.logout", "static", "health"}
        if request.endpoint in allowed:
            return None
        if g.services.users.must_change_password(user.id):
            return redirect(url_for("auth.change_password"))
        return None

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

    @app.get("/health")
    def health():
        """Liveness and database reachability.

        Mounted at /health, not /healthz: Google Front End intercepts /healthz
        on Cloud Run and answers it with its own 404 before the request reaches
        the container. Verified empirically — the identical image serves
        /healthz correctly when run locally, and requests to it never appear in
        Cloud Run's request log at all. /health and every other candidate path
        pass through untouched.

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

    @app.cli.command("db-upgrade")
    def db_upgrade() -> None:
        """Apply schema changes create_all() cannot (TD-01).

        Needed because there are no versioned migrations: adding a column to a
        populated table is manual DDL. Run before deploying a release that
        changes the schema.
        """
        apply_manual_migrations(engine)
        print("Schema upgrade complete.")

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
