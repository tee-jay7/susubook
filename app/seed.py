"""Demo data for grading and user acceptance testing.

Builds a realistic branch: one supervisor, three collectors, nine clients with
partial contribution histories, one cycle already matured and awaiting payout,
and one collector with an unreconciled variance today — so every screen has
something meaningful on it the moment the examiner signs in.

Credentials are listed in Deployment_and_Source_Links.txt.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.rules import DEFAULT_CYCLE_LENGTH_DAYS, cycle_end_date
from app.infrastructure.models import (
    ClientModel,
    ContributionCycleModel,
    ContributionModel,
    RemittanceDeclarationModel,
    UserModel,
)
from app.infrastructure.repositories import new_reference
from app.services.security import hash_password

DEMO_PASSWORD = "susu1234"

COLLECTORS = [
    ("Joseph Osei", "0244000101"),
    ("Kwame Tetteh", "0244000102"),
    ("Abena Mensah", "0244000103"),
]

# (name, phone, business, location, daily rate in pesewas, collector index,
#  days paid out of the elapsed cycle)
CLIENTS = [
    ("Ama Serwaa", "0201000201", "Provisions stall", "Madina Market", 500, 0, 20),
    ("Kofi Boateng", "0201000202", "Kiosk", "Madina Market", 1000, 0, 18),
    ("Akosua Darko", "0201000203", "Fabric trader", "Makola Market", 500, 0, 12),
    ("Yaw Owusu", "0201000204", "Barber", "Adenta", 2000, 1, 21),
    ("Efua Asante", "0201000205", "Food vendor", "Nima", 1000, 1, 9),
    ("Kojo Nkrumah", "0201000206", "Phone repairs", "Circle", 1500, 1, 21),
    ("Adwoa Yeboah", "0201000207", "Hairdresser", "Tema Station", 1000, 2, 15),
    ("Kwaku Addo", "0201000208", "Vegetable seller", "Agbogbloshie", 500, 2, 21),
    ("Mavis Quaye", "0201000209", "Tailor", "Osu", 2000, 2, 3),
]


def _user(
    session: Session, name: str, phone: str, role: str, *, must_change: bool = False
) -> UserModel:
    m = UserModel(
        public_ref=uuid.uuid4(),
        full_name=name,
        phone=phone,
        password_hash=hash_password(DEMO_PASSWORD),
        role=role,
        must_change_password=must_change,
    )
    session.add(m)
    session.flush()
    return m


def seed(session: Session, *, today: date | None = None) -> None:
    today = today or date.today()

    if session.scalar(select(UserModel).limit(1)) is not None:
        print("Database already seeded; nothing to do.")
        return

    _user(session, "Mariama Adjei", "0244000100", "SUPERVISOR")
    _user(session, "System Administrator", "0244000199", "ADMIN")
    collectors = [_user(session, n, p, "COLLECTOR") for n, p in COLLECTORS]

    # -- current cycles, started 21 days ago so they are mid-flight ---------
    current_start = today - timedelta(days=21)

    for name, phone, business, location, rate, ci, days_paid in CLIENTS:
        collector = collectors[ci]
        # One client is left with the forced-change flag set, so the TD-15
        # first-login flow is demonstrable without enrolling a new client.
        # Everyone else signs in straight through, keeping grading unobstructed.
        client_user = _user(
            session, name, phone, "CLIENT", must_change=(phone == "0201000209")
        )

        client = ClientModel(
            public_ref=uuid.uuid4(),
            user_id=client_user.id,
            collector_id=collector.id,
            full_name=name,
            phone=phone,
            business_type=business,
            location=location,
            daily_rate_pesewas=rate,
        )
        session.add(client)
        session.flush()

        cycle = ContributionCycleModel(
            client_id=client.id,
            cycle_number=1,
            start_date=current_start,
            end_date=cycle_end_date(current_start, DEFAULT_CYCLE_LENGTH_DAYS),
            status="ACTIVE",
            daily_rate_pesewas=rate,
        )
        session.add(cycle)
        session.flush()

        # Pay the first `days_paid` days, leaving gaps for the rest — a real
        # card is rarely complete.
        for offset in range(days_paid):
            session.add(
                ContributionModel(
                    reference=new_reference(),
                    cycle_id=cycle.id,
                    contribution_date=current_start + timedelta(days=offset),
                    amount_pesewas=rate,
                    recorded_by_id=collector.id,
                )
            )

    # -- one matured cycle awaiting payout (UC-07 has something to show) ----
    matured_start = today - timedelta(days=40)
    payout_user = _user(session, "Grace Amoah", "0201000210", "CLIENT")
    payout_client = ClientModel(
        public_ref=uuid.uuid4(),
        user_id=payout_user.id,
        collector_id=collectors[0].id,
        full_name="Grace Amoah",
        phone="0201000210",
        business_type="Cosmetics stall",
        location="Kaneshie Market",
        daily_rate_pesewas=1000,
    )
    session.add(payout_client)
    session.flush()

    matured = ContributionCycleModel(
        client_id=payout_client.id,
        cycle_number=1,
        start_date=matured_start,
        end_date=cycle_end_date(matured_start, DEFAULT_CYCLE_LENGTH_DAYS),
        status="MATURED",
        daily_rate_pesewas=1000,
    )
    session.add(matured)
    session.flush()

    for offset in range(28):  # 28 of 31 days paid
        session.add(
            ContributionModel(
                reference=new_reference(),
                cycle_id=matured.id,
                contribution_date=matured_start + timedelta(days=offset),
                amount_pesewas=1000,
                recorded_by_id=collectors[0].id,
            )
        )

    # -- today's reconciliation position -----------------------------------
    # Osei declares exactly what he recorded; Tetteh is GHS 35.00 short, so the
    # supervisor's variance screen has a real case to act on (problem P3).
    osei_today = sum(
        rate
        for _, _, _, _, rate, ci, days in CLIENTS
        if ci == 0 and days >= 22  # nobody yet — declaration is simply zero
    )
    session.add(
        RemittanceDeclarationModel(
            collector_id=collectors[0].id,
            declaration_date=today,
            amount_declared_pesewas=osei_today,
        )
    )
    session.add(
        RemittanceDeclarationModel(
            collector_id=collectors[1].id,
            declaration_date=today,
            amount_declared_pesewas=0,
        )
    )

    print(
        f"Seeded: 1 supervisor, 1 admin, {len(COLLECTORS)} collectors, "
        f"{len(CLIENTS) + 1} clients, 1 matured cycle awaiting payout."
    )
    print(f"All accounts use the password: {DEMO_PASSWORD}")
    print("Mavis Quaye (0201000209) must set her own password at first login.")
