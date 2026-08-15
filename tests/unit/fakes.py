"""In-memory repository fakes.

These satisfy the same Protocols as the SQLAlchemy implementations, so the
service layer cannot tell them apart. That substitution is the practical proof
of Liskov Substitution and Dependency Inversion (design doc section 7.12) --
and the reason service tests need no database.
"""

from __future__ import annotations

import itertools
from datetime import date
from uuid import UUID

from app.domain.entities import (
    Client,
    Contribution,
    ContributionCycle,
    DailyVariance,
    Payout,
    RemittanceDeclaration,
    User,
    UserRole,
)
from app.domain.money import Money


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def flush(self) -> None:
        pass


class FakeUserRepository:
    def __init__(self) -> None:
        self._rows: dict[int, User] = {}
        self._hashes: dict[int, str] = {}
        self._must_change: set[int] = set()
        self._ids = itertools.count(1)

    def get_by_id(self, user_id: int) -> User | None:
        return self._rows.get(user_id)

    def find_credentials(self, phone: str) -> tuple[User, str] | None:
        for user in self._rows.values():
            if user.phone == phone and user.is_active:
                return user, self._hashes[user.id]
        return None

    def add(self, user: User, password_hash: str) -> User:
        user.id = next(self._ids)
        self._rows[user.id] = user
        self._hashes[user.id] = password_hash
        return user

    def set_password(self, user_id: int, password_hash: str) -> None:
        self._hashes[user_id] = password_hash

    def must_change_password(self, user_id: int) -> bool:
        return user_id in self._must_change

    def require_password_change(self, user_id: int) -> None:
        self._must_change.add(user_id)

    def clear_password_change_flag(self, user_id: int) -> None:
        self._must_change.discard(user_id)

    def list_collectors(self) -> list[User]:
        return [u for u in self._rows.values() if u.role is UserRole.COLLECTOR]


class FakeClientRepository:
    def __init__(self) -> None:
        self._rows: dict[int, Client] = {}
        self._ids = itertools.count(1)

    def get_by_id(self, client_id: int) -> Client | None:
        return self._rows.get(client_id)

    def get_by_public_ref(self, public_ref: UUID) -> Client | None:
        return next(
            (c for c in self._rows.values() if c.public_ref == public_ref), None
        )

    def get_by_user_id(self, user_id: int) -> Client | None:
        return next((c for c in self._rows.values() if c.user_id == user_id), None)

    def list_for_collector(self, collector_id: int) -> list[Client]:
        return sorted(
            (
                c
                for c in self._rows.values()
                if c.collector_id == collector_id and c.is_active
            ),
            key=lambda c: c.full_name,
        )

    def add(self, client: Client) -> Client:
        client.id = next(self._ids)
        self._rows[client.id] = client
        return client


class FakeCycleRepository:
    def __init__(self) -> None:
        self._rows: dict[int, ContributionCycle] = {}
        self._ids = itertools.count(1)

    def get_by_id(self, cycle_id: int) -> ContributionCycle | None:
        return self._rows.get(cycle_id)

    def active_for_client(self, client_id: int) -> ContributionCycle | None:
        from app.domain.entities import CycleStatus

        return next(
            (
                c
                for c in self._rows.values()
                if c.client_id == client_id and c.status is CycleStatus.ACTIVE
            ),
            None,
        )

    def list_for_client(self, client_id: int) -> list[ContributionCycle]:
        return [c for c in self._rows.values() if c.client_id == client_id]

    def list_due_for_payout(self, today: date) -> list[tuple[ContributionCycle, Client]]:
        return []  # exercised via the integration suite

    def add(self, cycle: ContributionCycle) -> ContributionCycle:
        cycle.id = next(self._ids)
        self._rows[cycle.id] = cycle
        return cycle

    def set_status(self, cycle_id: int, status: str) -> None:
        from app.domain.entities import CycleStatus

        if cycle_id in self._rows:
            self._rows[cycle_id].status = CycleStatus(status)


class FakeContributionRepository:
    def __init__(self) -> None:
        self._rows: dict[int, Contribution] = {}
        self._ids = itertools.count(1)

    def list_for_cycle(self, cycle_id: int) -> list[Contribution]:
        return sorted(
            (c for c in self._rows.values() if c.cycle_id == cycle_id),
            key=lambda c: c.contribution_date,
        )

    def get_by_reference(self, reference: str) -> Contribution | None:
        return next(
            (c for c in self._rows.values() if c.reference == reference), None
        )

    def add(self, contribution: Contribution) -> Contribution:
        contribution.id = next(self._ids)
        if not contribution.reference:
            contribution.reference = f"SB-TEST-{contribution.id:04d}"
        self._rows[contribution.id] = contribution
        return contribution

    def mark_reversed(self, contribution_id: int, reversal_id: int) -> None:
        if contribution_id in self._rows:
            self._rows[contribution_id].reversed_by_id = reversal_id

    def total_recorded_by(self, collector_id: int, on: date) -> Money:
        total = Money.zero()
        for c in self._rows.values():
            if (
                c.recorded_by_id == collector_id
                and c.contribution_date == on
                and c.is_effective
            ):
                total = total + c.amount
        return total

    def collected_dates_for_collector(self, collector_id: int, on: date) -> set[int]:
        return set()  # cycle->client join is exercised in the integration suite


class FakePayoutRepository:
    def __init__(self) -> None:
        self._rows: dict[int, Payout] = {}
        self._ids = itertools.count(1)

    def get_for_cycle(self, cycle_id: int) -> Payout | None:
        return next((p for p in self._rows.values() if p.cycle_id == cycle_id), None)

    def add(self, payout: Payout) -> Payout:
        payout.id = next(self._ids)
        self._rows[payout.id] = payout
        return payout


class FakeRemittanceRepository:
    def __init__(self) -> None:
        self._rows: dict[tuple[int, date], RemittanceDeclaration] = {}
        self._ids = itertools.count(1)

    def get(self, collector_id: int, on: date) -> RemittanceDeclaration | None:
        return self._rows.get((collector_id, on))

    def save(self, declaration: RemittanceDeclaration) -> RemittanceDeclaration:
        key = (declaration.collector_id, declaration.declaration_date)
        declaration.id = next(self._ids)
        self._rows[key] = declaration
        return declaration

    def variances_for(self, on: date) -> list[DailyVariance]:
        return []


class FakePasswordResetRepository:
    def __init__(self) -> None:
        self._rows: dict[int, dict] = {}
        self._ids = itertools.count(1)

    def add(self, *, user_id, code_hash, expires_at):
        from app.services.protocols import ResetCode

        rid = next(self._ids)
        self._rows[rid] = {
            "id": rid, "user_id": user_id, "code_hash": code_hash,
            "expires_at": expires_at, "attempts": 0, "used_at": None,
            "requested_at": expires_at,
        }
        r = self._rows[rid]
        return ResetCode(rid, user_id, code_hash, expires_at, 0)

    def outstanding_for(self, user_id, *, at):
        from app.services.protocols import ResetCode

        for r in sorted(self._rows.values(), key=lambda x: -x["id"]):
            if r["user_id"] == user_id and r["used_at"] is None and r["expires_at"] > at:
                return ResetCode(r["id"], user_id, r["code_hash"], r["expires_at"], r["attempts"])
        return None

    def invalidate_outstanding(self, user_id, *, at):
        for r in self._rows.values():
            if r["user_id"] == user_id and r["used_at"] is None:
                r["used_at"] = at

    def record_attempt(self, code_id):
        if code_id in self._rows:
            self._rows[code_id]["attempts"] += 1

    def mark_used(self, code_id, *, at):
        if code_id in self._rows:
            self._rows[code_id]["used_at"] = at

    def recent_request_count(self, user_id, *, since):
        return sum(1 for r in self._rows.values() if r["user_id"] == user_id)


class FakeAuditRepository:
    """Records entries so tests can assert the audit trail was written."""

    def __init__(self) -> None:
        self.entries: list[dict] = []

    def append(
        self,
        *,
        actor_id: int | None,
        action: str,
        target_type: str,
        target_id: str | None = None,
        detail: dict | None = None,
    ) -> None:
        self.entries.append(
            {
                "actor_id": actor_id,
                "action": action,
                "target_type": target_type,
                "target_id": target_id,
                "detail": detail,
            }
        )

    def list_for_target(self, target_type: str, target_id: str) -> list[dict]:
        return [
            e
            for e in self.entries
            if e["target_type"] == target_type and e["target_id"] == target_id
        ]

    def actions(self) -> list[str]:
        return [e["action"] for e in self.entries]
