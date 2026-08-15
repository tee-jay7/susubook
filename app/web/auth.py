"""Authentication routes — UC-01."""

from __future__ import annotations

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from .security import current_user, home_for, log_in, log_out, login_required

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


@bp.route("/password", methods=["GET", "POST"])
@login_required
def change_password():
    """TD-15 — forced first change, and voluntary change thereafter.

    The collector types a client's first password at enrolment and therefore
    knows it. Until the client replaces it, their record is not independent of
    the collector, which contradicts BR-02 — the property the system exists to
    provide. The guard in the application factory redirects here and permits
    nothing else until the change is made.
    """
    user = current_user()
    forced = g.services.users.must_change_password(user.id)

    if request.method == "POST":
        g.services.passwords.change_password(
            user=user,
            current_password=None if forced else request.form.get("current", ""),
            new_password=request.form.get("new_password", ""),
        )
        flash("Your password has been changed.", "success")
        return redirect(url_for(home_for(user)))

    return render_template("password/change.html", forced=forced)


@bp.route("/forgot", methods=["GET", "POST"])
def forgot_password():
    """Request a reset code by SMS (TD-15).

    Became possible only once CR-002 delivered an SMS channel — the debt
    register named the absent gateway as the blocker.
    """
    if current_user() is not None:
        return redirect(url_for("auth.change_password"))

    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        g.services.passwords.request_reset(phone=phone)
        # Always the same response. Confirming whether an account exists would
        # let anyone enumerate registered numbers.
        flash(
            "If that number is registered, a reset code has been sent to it.",
            "info",
        )
        return redirect(url_for("auth.reset_password", phone=phone))

    return render_template("password/forgot.html")


@bp.route("/reset", methods=["GET", "POST"])
def reset_password():
    if current_user() is not None:
        return redirect(url_for("auth.change_password"))

    if request.method == "POST":
        g.services.passwords.complete_reset(
            phone=request.form.get("phone", "").strip(),
            code=request.form.get("code", ""),
            new_password=request.form.get("new_password", ""),
        )
        flash("Your password has been reset. Please sign in.", "success")
        return redirect(url_for("auth.login"))

    return render_template(
        "password/reset.html", phone=request.args.get("phone", "")
    )


@bp.route("/logout", methods=["POST"])
def logout():
    log_out()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))
