"""Client self-service routes — UC-08.

This blueprint is the answer to problem P1: the client's own view of their
record, reached through their own login, independent of the collector.
"""

from __future__ import annotations

from flask import Blueprint, abort, g, render_template

from app.domain.entities import UserRole

from .security import current_user, roles_required

bp = Blueprint("client", __name__, url_prefix="/my")


def _my_client():
    client = g.services.clients.get_by_user_id(current_user().id)
    if client is None:
        abort(404)
    return client


@bp.route("/", methods=["GET"])
@roles_required(UserRole.CLIENT)
def my_card():
    """FR-28, FR-29 — my susu card, balance and projected payout."""
    client = _my_client()
    cycle = g.services.cycles.active_for_client(client.id)
    if cycle is None:
        cycles = g.services.cycles.list_for_client(client.id)
        if not cycles:
            abort(404)
        cycle = cycles[0]

    summary, contributions = g.services.collection.card_for(cycle)
    collectors = {
        c.recorded_by_id: g.services.users.get_by_id(c.recorded_by_id)
        for c in contributions
    }
    return render_template(
        "client/my_card.html",
        client=client,
        cycle=cycle,
        summary=summary,
        contributions=list(reversed(contributions)),
        collectors=collectors,
    )


@bp.route("/history", methods=["GET"])
@roles_required(UserRole.CLIENT)
def history():
    """Every cycle this client has completed."""
    client = _my_client()
    cycles = g.services.cycles.list_for_client(client.id)
    rows = []
    for cycle in cycles:
        summary, _ = g.services.collection.card_for(cycle)
        rows.append(
            {
                "cycle": cycle,
                "summary": summary,
                "payout": g.services.payouts.get_for_cycle(cycle.id),
            }
        )
    return render_template("client/history.html", client=client, rows=rows)
