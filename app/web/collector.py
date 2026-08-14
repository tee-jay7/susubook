"""Collector routes — UC-02, UC-03, UC-04, UC-05, UC-10."""

from __future__ import annotations

from uuid import UUID

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from app.domain.entities import UserRole
from app.domain.errors import NotAuthorised
from app.domain.money import Money
from app.infrastructure.qrcodes import collection_url, qr_svg
from app.services.security import hash_password

from .security import current_user, login_required, roles_required

bp = Blueprint("collector", __name__, url_prefix="/collector")

COLLECTOR_ROLES = (UserRole.COLLECTOR, UserRole.SUPERVISOR, UserRole.ADMIN)


def _parse_amount(raw: str) -> Money:
    """Cedis from a form field, as an exact decimal string (BR-R1)."""
    from app.domain.errors import DomainError

    try:
        return Money.from_cedis(raw.strip())
    except (ValueError, ArithmeticError) as exc:
        raise DomainError(f"'{raw}' is not a valid amount in cedis.") from exc


@bp.route("/", methods=["GET"])
@roles_required(*COLLECTOR_ROLES)
def route_sheet():
    """FR-23 — today's clients and their collection status."""
    user = current_user()
    entries = g.services.collection.route_sheet(collector_id=user.id)
    position = g.services.reconciliation.my_position(actor=user)
    return render_template("collector/route_sheet.html", entries=entries, position=position)


@bp.route("/enrol", methods=["GET", "POST"])
@roles_required(*COLLECTOR_ROLES)
def enrol():
    """UC-02 — enrol a client, create their login, open cycle 1."""
    if request.method == "POST":
        amount = _parse_amount(request.form.get("daily_rate", ""))
        password = request.form.get("password", "").strip()
        if len(password) < 6:
            from app.domain.errors import DomainError

            raise DomainError("The client's password must be at least 6 characters.")

        client, _cycle = g.services.enrolment.enrol(
            actor=current_user(),
            full_name=request.form.get("full_name", "").strip(),
            phone=request.form.get("phone", "").strip(),
            daily_rate=amount,
            password_hash=hash_password(password),
            business_type=request.form.get("business_type", "").strip() or None,
            location=request.form.get("location", "").strip() or None,
        )
        flash(f"{client.full_name} enrolled. Print their susu card.", "success")
        return redirect(url_for("collector.card", public_ref=client.public_ref))

    return render_template("collector/enrol.html")


@bp.route("/client/<uuid:public_ref>", methods=["GET"])
@roles_required(*COLLECTOR_ROLES)
def client_detail(public_ref: UUID):
    """UC-04 — the client's digital susu card as the collector sees it."""
    client, cycle, summary, contributions = _load_card(public_ref)
    return render_template(
        "collector/client_detail.html",
        client=client,
        cycle=cycle,
        summary=summary,
        contributions=list(reversed(contributions)),
    )


@bp.route("/collect/<uuid:public_ref>", methods=["POST"])
@roles_required(*COLLECTOR_ROLES)
def collect(public_ref: UUID):
    """UC-03 — record a contribution. The critical-path interaction."""
    raw = request.form.get("amount", "").strip()
    amount = _parse_amount(raw) if raw else None

    contribution = g.services.collection.record(
        public_ref=public_ref, actor=current_user(), amount=amount
    )

    if request.headers.get("HX-Request"):
        # HTMX: swap the row in place so the collector keeps their position
        # on the route sheet (TD-06 — applied here, not everywhere).
        entry = next(
            (
                e
                for e in g.services.collection.route_sheet(
                    collector_id=current_user().id
                )
                if e.client.public_ref == public_ref
            ),
            None,
        )
        return render_template(
            "partials/route_row.html", entry=entry, just_recorded=contribution
        )

    flash(
        f"Recorded {contribution.amount} — reference {contribution.reference}.",
        "success",
    )
    return redirect(url_for("collector.route_sheet"))


@bp.route("/declare", methods=["GET", "POST"])
@roles_required(*COLLECTOR_ROLES)
def declare():
    """UC-05 — declare cash remitted to the branch (FR-24)."""
    user = current_user()
    if request.method == "POST":
        variance = g.services.reconciliation.declare(
            actor=user, amount=_parse_amount(request.form.get("amount", ""))
        )
        if variance.variance.is_zero:
            flash("Remittance declared and reconciled.", "success")
        else:
            flash(
                f"Declared. Variance of {variance.variance} recorded for "
                f"supervisor review.",
                "warning",
            )
        return redirect(url_for("collector.route_sheet"))

    return render_template(
        "collector/declare.html",
        position=g.services.reconciliation.my_position(actor=user),
    )


@bp.route("/card/<uuid:public_ref>", methods=["GET"])
@roles_required(*COLLECTOR_ROLES)
def card(public_ref: UUID):
    """UC-10 — printable QR susu card (FR-39)."""
    client = g.services.clients.get_by_public_ref(public_ref)
    if client is None:
        abort(404)
    _assert_on_route(client)

    base = current_app.config["BASE_URL"]
    return render_template(
        "collector/qr_card.html",
        client=client,
        qr=qr_svg(base, client.public_ref, scale=6),
        url=collection_url(base, client.public_ref),
    )


def _assert_on_route(client) -> None:
    """FR-05 / BR-R15 — the reference identifies, it does not authorise.

    A denial is audited here as well as in the service layer. Someone
    presenting a client reference they should not hold is exactly the signal a
    supervisor needs, and it arrives on the GET — before any write is
    attempted — so auditing only the write path would miss it entirely.
    """
    user = current_user()
    if user.is_supervisor or client.is_collected_by(user.id):
        return

    g.services.audit.append(
        actor_id=user.id,
        action="AUTHORISATION_DENIED",
        target_type="CLIENT",
        target_id=str(client.public_ref),
        detail={"attempted": request.endpoint},
    )
    g.db.commit()
    raise NotAuthorised("This client is not on your route.")


def _load_card(public_ref: UUID):
    client = g.services.clients.get_by_public_ref(public_ref)
    if client is None:
        abort(404)
    _assert_on_route(client)
    cycle = g.services.cycles.active_for_client(client.id)
    if cycle is None:
        cycles = g.services.cycles.list_for_client(client.id)
        cycle = cycles[0] if cycles else None
    if cycle is None:
        abort(404)
    summary, contributions = g.services.collection.card_for(cycle)
    return client, cycle, summary, contributions


# ---------------------------------------------------------------------------
# Scan entry point (FR-40).
#
# Mounted at the root as /c/<ref> rather than under /collector, so the encoded
# URL stays short. A shorter URL produces a lower-density QR symbol, and a
# lower-density symbol scans more reliably off a card that has spent three
# weeks in a market stall (CO-07).
# ---------------------------------------------------------------------------

scan_bp = Blueprint("scan", __name__)


@scan_bp.route("/c/<uuid:public_ref>", methods=["GET"])
@login_required
def scanned(public_ref: UUID):
    """Landing page after scanning a QR card — the confirm screen.

    Authorisation is the collector-client assignment, never the reference
    itself (BR-R15): _load_card raises NotAuthorised for anyone else.
    """
    client, cycle, summary, contributions = _load_card(public_ref)
    today = g.services.collection.today()
    return render_template(
        "collector/confirm.html",
        client=client,
        cycle=cycle,
        summary=summary,
        already_today=any(
            c.contribution_date == today and c.is_effective for c in contributions
        ),
    )
