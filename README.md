# SusuBook

**A Digital Susu Collection and Accountability System**

CSCD602 Advanced Software Engineering — Individual Project-Based Examination
University of Ghana, Department of Computer Science

---

## The problem

*Susu* is Ghana's dominant informal savings mechanism. In the collector model, a susu
collector visits clients — market traders, kiosk operators, artisans — daily, receives a
small fixed contribution, and marks one of 31 boxes on a paper card. At the end of the
cycle the client receives the total, less one day's contribution as commission.

**The card is held and marked by the collector.** The client keeps no independent record.
That single fact produces four failures: clients cannot prove what they paid, collectors
can under-record or abscond with a route's takings, branches cannot reconcile field
collections against cash remitted on the same day, and payouts are computed by hand.

SusuBook replaces the paper card with a shared record that both parties can see and
neither can silently alter.

## What it does

- **Independent client record** — every contribution is visible to the client on their own
  login, with amount, date, time recorded and the identity of the recording collector
- **Same-day reconciliation** — collectors declare cash remitted; the system computes the
  variance against what was recorded in the field and surfaces it to supervisors that day
- **Automated payout** — days paid, total collected, commission and net payout derived by
  the system under one rule for every client
- **Append-only audit trail** — nothing is edited or deleted; corrections are linked
  reversal entries
- **QR client cards** — each client carries a printed QR code; the collector scans it with
  the phone's camera to reach the contribution screen in two interactions

## Architecture

Layered (N-tier), with the dependency rule pointing strictly downward:

```
app/web/             ① Presentation    Flask blueprints, Jinja templates, HTMX
app/services/        ② Application     use-case orchestration, transactions, audit
app/domain/          ③ Domain          entities, Money, business rules — no framework
app/infrastructure/  ④ Infrastructure  SQLAlchemy models, repositories, QR rendering
```

The domain layer imports neither Flask nor SQLAlchemy, so business rules are unit-tested
without a database. Services depend on repository `Protocol`s and receive concrete
implementations by injection.

**Stack:** Python 3.12 · Flask 3 · SQLAlchemy 2 · PostgreSQL 16 · Jinja2 · HTMX · segno ·
pytest. Docker Compose for local Postgres, giving dev/prod parity on the same engine.

## Documentation

| Document | Contents |
|---|---|
| [`docs/01-problem-definition.md`](docs/01-problem-definition.md) | Problem, aim, objectives, users, scope boundary |
| [`docs/02-stakeholder-analysis.md`](docs/02-stakeholder-analysis.md) | Stakeholders, elicitation, conflicts, assumptions |
| [`docs/03-requirements.md`](docs/03-requirements.md) | 40 functional, 10 non-functional, constraints, MoSCoW, traceability |
| [`docs/04-srs.md`](docs/04-srs.md) | Software Requirements Specification (IEEE 830) |
| [`docs/05-effort-estimation.md`](docs/05-effort-estimation.md) | FPA → COCOMO → PERT, and the scope decision |
| [`docs/06-scope.md`](docs/06-scope.md) | Delivered scope, quality reductions, deferrals, Definition of Done |
| [`docs/07-system-analysis-and-design.md`](docs/07-system-analysis-and-design.md) | Architecture, UML, database, SOLID, security |
| [`docs/CHANGELOG-requirements.md`](docs/CHANGELOG-requirements.md) | Formal change control record |

## Running locally

```bash
cp .env.example .env
docker compose up -d          # PostgreSQL 16
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
flask --app app db-init       # create schema
flask --app app seed          # demo accounts and data
flask --app app run --debug
```

## Tests

```bash
pytest                        # all
pytest tests/unit -q          # domain rules only — no database required
pytest --cov=app --cov-report=term-missing
```

## Academic integrity

Submitted as individual work for CSCD602. Third-party frameworks and libraries are
acknowledged in `docs/07-system-analysis-and-design.md` §7.8 and in `requirements.txt`.
