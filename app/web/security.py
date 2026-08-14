"""Session handling and route authorisation decorators — layer 1.

Authorisation is enforced server-side on every route (NFR-03). Templates hide
links the user cannot use, but hiding a link is presentation, not a control:
the decorators below are the control, and the service layer re-checks
object-level access (FR-05) independently.
"""

from __future__ import annotations

from functools import wraps
from typing import Callable

from flask import abort, g, redirect, session, url_for

from app.domain.entities import User, UserRole

SESSION_USER_KEY = "user_id"


def log_in(user: User) -> None:
    session.clear()  # new session id on privilege change — prevents fixation
    session[SESSION_USER_KEY] = user.id
    session.permanent = True


def log_out() -> None:
    session.clear()


def current_user() -> User | None:
    return getattr(g, "current_user", None)


def load_current_user() -> None:
    """Populate g.current_user from the session, once per request."""
    g.current_user = None
    user_id = session.get(SESSION_USER_KEY)
    if user_id is None:
        return
    user = g.services.users.get_by_id(user_id)
    if user is None or not user.is_active:
        session.clear()
        return
    g.current_user = user


def login_required(view: Callable) -> Callable:
    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapper


def roles_required(*roles: UserRole) -> Callable:
    """Restrict a route to the given roles. ADMIN is never implicitly allowed."""

    def decorator(view: Callable) -> Callable:
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                return redirect(url_for("auth.login"))
            if user.role not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapper

    return decorator


def home_for(user: User) -> str:
    """Role-appropriate landing page."""
    return {
        UserRole.CLIENT: "client.my_card",
        UserRole.COLLECTOR: "collector.route_sheet",
        UserRole.SUPERVISOR: "supervisor.variances",
        UserRole.ADMIN: "supervisor.variances",
    }[user.role]
