"""Authentication routes — UC-01."""

from __future__ import annotations

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from .security import current_user, home_for, log_in, log_out

bp = Blueprint("auth", __name__)


@bp.route("/", methods=["GET"])
def index():
    user = current_user()
    if user is not None:
        return redirect(url_for(home_for(user)))
    return redirect(url_for("auth.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    user = current_user()
    if user is not None:
        return redirect(url_for(home_for(user)))

    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")

        authenticated = g.services.auth.authenticate(phone, password)
        g.db.commit()  # persist the audit entry for the attempt, success or not

        if authenticated is None:
            # Deliberately does not distinguish unknown phone from wrong
            # password: telling them apart would let an attacker enumerate
            # which numbers are registered.
            flash("Phone number or password is incorrect.", "error")
            return render_template("login.html", phone=phone), 401

        log_in(authenticated)
        return redirect(url_for(home_for(authenticated)))

    return render_template("login.html", phone="")


# TODO(TD-15): there is no password reset and no forced change at first login.
#   The collector sets the client's initial password at enrolment and therefore
#   knows it — which undercuts the independence of the client's record, the
#   property this whole system exists to establish. Ranked Critical alongside
#   TD-14 in docs/08-technical-debt.md for that reason, not for convenience.


@bp.route("/logout", methods=["POST"])
def logout():
    log_out()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))
