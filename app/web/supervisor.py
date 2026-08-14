"""Supervisor routes — UC-06, UC-07, UC-09."""

from __future__ import annotations

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from app.domain.entities import UserRole
from app.domain.errors import DomainError

from .security import current_user, roles_required

bp = Blueprint("supervisor", __name__, url_prefix="/supervisor")

SUPERVISOR_ROLES = (UserRole.SUPERVISOR, UserRole.ADMIN)


@bp.route("/", methods=["GET"])
@roles_required(*SUPERVISOR_ROLES)
def variances():
    """UC-06 — today's reconciliation position for every collector (FR-26)."""
    rows = g.services.reconciliation.variances(actor=current_user())
    outstanding = [r for r in rows if not r.is_reconciled]
    total_unaccounted = sum((r.variance.pesewas for r in outstanding), 0)
    return render_template(
        "supervisor/variances.html",
        rows=rows,
        outstanding=outstanding,
        total_unaccounted=total_unaccounted,
    )


@bp.route("/payouts", methods=["GET"])
@roles_required(*SUPERVISOR_ROLES)
def payouts():
    """UC-07 — matured cycles awaiting release (FR-18)."""
    return render_template("supervisor/payouts.html", due=g.services.payout.list_due())


@bp.route("/payouts/<int:cycle_id>/release", methods=["POST"])
@roles_required(*SUPERVISOR_ROLES)
def release_payout(cycle_id: int):
    payout = g.services.payout.release(cycle_id=cycle_id, actor=current_user())
    if payout.net_payout.is_zero:
        flash(
            f"Cycle closed. Net payout is {payout.net_payout}: the total collected "
            f"({payout.total_collected}) did not exceed one day's contribution, "
            f"which is retained as commission.",
            "warning",
        )
    else:
        flash(
            f"Payout of {payout.net_payout} released "
            f"({payout.total_collected} collected less {payout.commission} "
            f"commission). A new cycle has been opened.",
            "success",
        )
    return redirect(url_for("supervisor.payouts"))


@bp.route("/reverse", methods=["GET", "POST"])
@roles_required(*SUPERVISOR_ROLES)
def reverse():
    """UC-09 — correct an erroneous contribution by linked reversal (BR-R11).

    TODO(TD-04): a bare reference-and-reason form. A guided workflow with
      reason codes, and a link straight from the contribution row, was cut
      from the 48-hour scope.
    """
    if request.method == "POST":
        reference = request.form.get("reference", "").strip().upper()
        reason = request.form.get("reason", "").strip()
        if not reason:
            raise DomainError("A reason is required to reverse a contribution.")

        reversal = g.services.collection.reverse(
            reference=reference, actor=current_user(), reason=reason
        )
        flash(
            f"Contribution {reference} reversed by {reversal.reference}. "
            f"Both entries remain on the client's record.",
            "success",
        )
        return redirect(url_for("supervisor.reverse"))

    return render_template("supervisor/reverse.html")


@bp.route("/audit/<target_type>/<target_id>", methods=["GET"])
@roles_required(*SUPERVISOR_ROLES)
def audit_trail(target_type: str, target_id: str):
    """FR-34 — audit trail for one target."""
    entries = g.services.audit.list_for_target(target_type.upper(), target_id)
    return render_template(
        "supervisor/audit.html",
        entries=entries,
        target_type=target_type,
        target_id=target_id,
    )
