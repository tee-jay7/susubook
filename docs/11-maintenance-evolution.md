# 11. Maintenance Strategy and Future Evolution

> Examination document §15 and §16, including the technical debt repayment plan
> the paper requires.

---

# PART A — MAINTENANCE STRATEGY

## 11.1 The four maintenance categories, applied

Generic definitions are of little use; what follows is what each category
actually means for *this* system, with instances already identified.

### Corrective — fixing defects

| | |
|---|---|
| **Trigger** | Defect reported by a user, or surfaced by the audit log |
| **Current capability** | **Weak.** No error aggregation and no alerting (**TD-17**), so a production failure is discovered when a user reports it |
| **Evidence** | Seven of the eight defects found so far (`09-testing.md` §9.8) came from tests or probing; **DEF-06 came from a person clicking through**, and no automated test could have caught it |
| **Improvement** | TD-17's repayment — structured logging, error tracking, uptime checks — moves detection ahead of the user report |

### Adaptive — responding to environmental change

The environment this system sits in is unusually active:

| Change | Consequence |
|---|---|
| Data Protection Act amendments | Stored fields, retention, consent at enrolment (NFR-06) |
| Bank of Ghana microfinance directives | Audit and reporting obligations |
| Mobile money displacing cash collection | The system records cash; large-scale MoMo adoption changes the domain, not just the code |
| Python, Flask, PostgreSQL releases | Security patches, deprecations |
| Android browser changes | QR scanning depends on the native camera app's behaviour (FR-40) |

The last is a real dependency worth naming: **CR-001 deliberately delegated QR
decoding to the operating system.** That bought simplicity and reliability, and
it accepted that a change in Android's camera behaviour becomes our problem.

### Perfective — improving what already works

Driven by the debt register and by measurement, not by taste:

- **TD-02** — self-host and purge the stylesheet. Measured at 0.52 s of serial
  round trip today (§12.6), and the largest single contributor to NFR-01 failing.
- **TD-16** — the N+1 on the route sheet, before client counts make it visible.
- **TD-03, TD-04, TD-05, TD-06** — the convenience features cut under time
  pressure. FR-08 and FR-23 remain *partially* satisfied until these land.

### Preventive — reducing future cost

- **TD-01** — migrations. Every further schema change costs manual DDL until this
  is done, and it blocks TD-09.
- **TD-12** — pin dependencies and commit a lockfile, so a transitive release
  cannot break production without a change in this repository.
- Keep test coverage at its current level (97%) as features are added. Session 3
  names test debt as the classic casualty of delivery pressure; this project has
  none, and that is a position to defend rather than assume.

## 11.2 Defect triage

| Severity | Definition | Response | Example from this project |
|---|---|---|---|
| **S1 Critical** | Client funds misrecorded, or the audit trail compromised | Immediate; roll back if needed | A negative payout (guarded by BR-R9 and `ck_payout_balances`) |
| **S2 High** | A role cannot complete their core task | Same day | DEF-03, DEF-04 — every page 500ing |
| **S3 Medium** | Feature impaired, workaround exists | Next release | DEF-06 — the stale running total |
| **S4 Low** | Cosmetic or documentation | Scheduled | DEF-01 — an incorrect claim in a docstring |

Rollback is a first-class response: Cloud Run retains previous revisions, so
reverting is one command and needs no rebuild (§12.9).

## 11.3 Security and dependency maintenance

| Activity | Cadence | Notes |
|---|---|---|
| Dependency vulnerability scan | Monthly, and on every release | Not yet automated; **TD-12** leaves versions unpinned |
| Framework security releases | As published | Flask, SQLAlchemy, psycopg, gunicorn |
| Base image rebuild | Monthly | `python:3.12-slim` accumulates OS-level CVEs even when the application does not change |
| Secret rotation | Annually, and on any suspected exposure | Both live in Secret Manager; rotation is a new version plus a redeploy |
| Audit log review | Weekly | `AUTHORISATION_DENIED` and `LOGIN_FAILED` are the signals that matter — and with **TD-14** unfixed, the log is the *only* defence against brute force |

**The three Critical debt items are security items, and they are maintenance
work, not features.** TD-14 (no rate limiting), TD-15 (the collector knows the
client's password) and TD-09 (audit log mutable) must be closed before the
system holds real client money.

---

# PART B — FUTURE EVOLUTION

## 11.4 Lehman's Laws applied to SusuBook

Session 4's laws [4], formulated by Lehman [19] and developed with Belady [14],
describe how systems behave over time. Each is taken in turn,
with what it predicts *for this system* and what has been done — or must be done —
in response.

### 1. Continuing change

> *A program used in a real-world environment must change, or become
> progressively less useful in that environment.*

Susu is not a static practice. Mobile money is displacing cash collection,
regulation is tightening, and a collector who finds SusuBook slower than a paper
card will return to the card — the fallback is always available and costs
nothing.

**Response.** The deferred requirements are not a wish list, they are the change
pipeline: FR-31 (SMS), FR-15 (catch-up payments), FR-22 (early withdrawal). The
architecture was left open where change is most likely — `CommissionPolicy` is a
Strategy interface precisely because commission policy is the term most likely to
be renegotiated (FR-36).

### 2. Increasing complexity

> *As a program evolves, its structure becomes more complex unless work is done
> explicitly to reduce it.*

Fifteen business rules, four layers, seventeen debt items — at version one. Every
deferred requirement adds branching to the same domain: catch-up payments
complicate contribution allocation, early withdrawal complicates the cycle state
machine, multi-institution complicates every query.

**Response — and this law is the reason for several earlier decisions.** The
domain layer's isolation from Flask and SQLAlchemy, the 256 tests, and the
business rules expressed as pure functions are precisely the "work done
explicitly to reduce complexity" the law demands. They are not architectural
taste; they are the mechanism by which the second law is resisted.

The countermeasure must continue: a standing refactoring budget, and the debt
register kept current rather than allowed to become archaeology.

### 3. Self-regulation

> *Evolution is self-regulating; system attributes such as size and time between
> releases are approximately invariant across releases.*

**This law cannot yet be demonstrated here, and saying otherwise would be
dishonest.** It describes behaviour across many releases; SusuBook has one.

What exists is the beginning of the baseline the law depends on: the estimation
record in `05-effort-estimation.md` §4.8, with estimates against actuals and an
MRE. Session 6's closing advice — record actuals, review accuracy — is exactly
how a team acquires the historical data that makes this law predictive rather
than merely descriptive.

### 4. Conservation of organisational stability

> *The average rate of development is approximately constant and independent of
> the resources devoted to it.*

The debt repayment plan totals 19–24 hours (§11.6). The temptation, facing a
deadline, is to assume two developers would halve it.

**Response.** The law says otherwise — as does Brooks [13] — and the plan is not
built on that assumption. Items 1–4 are sequenced by dependency — TD-01 gates TD-09 — not by
what could be parallelised. Adding people to a system with one person's worth of
context in it would, in the short term, slow it down.

### 5. Conservation of familiarity

> *The incremental change in each release is approximately constant.*

Ten deferred requirements and seventeen debt items constitute a large backlog.
The law warns that discharging it in one release exceeds what users and
maintainers can absorb.

**Response.** Release in increments of comparable size: security debt first, then
one feature area at a time. A release containing SMS notification, catch-up
payments, early withdrawal *and* multi-institution support would be unreviewable
and unlearnable — and collectors, who are the least able to absorb disruption,
would bear the cost.

### 6. Continuing growth

> *Functional content must continually increase to maintain user satisfaction.*

Every stakeholder group already wants more than v1 delivers: clients want SMS
confirmation (FR-31), collectors want catch-up payments (FR-15), supervisors want
a dashboard (FR-37) and variance resolution (FR-27), administrators want user
management (FR-35).

**Response.** MoSCoW prioritisation gave a defensible v1; the same discipline
must govern growth. Note the tension with the second law — growth adds
functionality, which adds complexity — which is why perfective work must be
funded alongside features rather than after them.

### 7. Declining quality

> *Quality will appear to decline unless the system is adapted to changes in its
> operational environment.*

**This law is already operating on SusuBook, with no code change required.**
NFR-01 specifies 2 seconds on a 3G connection. Measurement (§12.6) shows first
render already exceeding 1.1 s on a *good* connection, so the requirement is
probably not met today. As client counts grow, TD-16's N+1 degrades the route
sheet further. Nothing will have changed in the code; the environment will have
moved.

**Response.** Quality attributes need measurement over time, not a one-off
verification at release. The performance figures in §12.6 are a baseline to be
re-measured, and NFR-01 is recorded as *not met* rather than quietly dropped.

### 8. Feedback system

> *Evolution processes are multi-loop, multi-agent feedback systems and must be
> treated as such.*

SusuBook contains three feedback loops by design:

| Loop | Mechanism |
|---|---|
| Collector accountability | Recorded collections → daily variance → supervisor action |
| Client verification | Contribution → immediately visible to the client → dispute raised early |
| Institutional oversight | Audit log → review → policy change |

And the development process has its own, with evidence from this project:
**DEF-06 was found by a user clicking through the interface, not by any of the
256 automated tests — and could not have been, because every test asserted the
*response* to a request and none asserted the state of the page afterwards.**

That is Lehman's eighth law demonstrated inside the project rather than quoted at
it. Automated tests confirm what the developer thought to check; only the user
loop finds what they did not. It is also the clearest argument for closing the
outstanding UAT (§9.9).

## 11.5 Evolution roadmap

| Release | Contents | Rationale |
|---|---|---|
| **v1.1 — Security** | TD-01 migrations, TD-14 rate limiting, TD-09 audit enforcement. ~~TD-15~~ **already repaid** | Everything blocking real client money. Nothing else ships first. Two Critical items remain. |
| **v1.2 — Reach** | ~~FR-31 SMS notification~~ **delivered under CR-002**; remaining: lift the recipient allowlist, TD-18 delivery tracking | FR-31 shipped in this release. The mechanism mitigating **A5** now exists, but recipients are still restricted to an allowlist, so the mitigation is not yet realised for real clients. |
| **v1.3 — Field efficiency** | FR-15 catch-up payments, TD-05 route ordering, TD-03 search, TD-16 N+1 | The collector's daily experience. Domain rules already accept `days_covered`, so FR-15 needs no change to the business rules. |
| **v1.4 — Oversight** | FR-34 audit viewer, FR-37 dashboard, FR-27 variance resolution, FR-35 user admin | Supervisor and administrator capability |
| **v1.5 — Performance** | TD-02 stylesheet build, region relocation, TD-11 denormalised totals | Directly targets NFR-01, which is currently not met |
| **v2.0 — Scale** | Multi-institution tenancy, mobile money integration, offline capability | Each changes the data model or the product's scope, not merely its features |

## 11.6 Technical debt repayment plan

> Required explicitly by the examination. Full analysis in `08-technical-debt.md`.

| Order | Item | Est. | Why here |
|---|---|---|---|
| 1 | **TD-01** migrations | 2 h | Compounds and gates: TD-09 cannot be repaid without it |
| 2 | **TD-14** rate limiting | 2–3 h | Highest severity; independent of everything else |
| ~~3~~ | ~~**TD-15** forced password change~~ | ~~3–4 h~~ | **Repaid.** Both halves closed: forced change on first login, and self-service reset by SMS code |
| 4 | **TD-09** audit log enforcement | 1–2 h | Requires TD-01 |
| 5 | **TD-12** pin dependencies | 0.5 h | Cheap; makes everything after it reproducible |
| 6 | **TD-16** N+1 queries | 1–2 h | Before client counts make it visible |
| 7 | **TD-02** stylesheet build | 1–2 h | Largest measured contributor to NFR-01 failing |
| 8 | **TD-17** logging and monitoring | 2–3 h | Enables corrective maintenance at all |
| 9 | **TD-03…06** convenience features | ~4 h | User-facing polish, no correctness risk |
| | **Total** | **19–24 h** | |

**Items 1, 2 and 4 — around 5 to 7 hours — must complete before the system
handles real client money.** TD-15 is already closed. They are not improvements; they are the difference between a system that
demonstrates the idea and one that can be trusted with savings.

Items TD-07, TD-08, TD-10, TD-11 and TD-13 are classified *acceptable
temporarily* and carry no scheduled repayment. Each is documented with the
condition that would change that assessment — TD-11, for instance, becomes worth
fixing only if cycle length ever exceeds a month.

## 11.7 Evolution risks

| Risk | Law | Mitigation |
|---|---|---|
| Features ship, debt does not | 2, 7 | Repayment plan sequenced ahead of features in v1.1 |
| Backlog discharged in one release | 5 | Roadmap deliberately incremental |
| Quality erodes without anyone noticing | 7 | Re-measure §12.6 baseline each release; NFR-01 already recorded as not met |
| Maintainer changes, context lost | 2 | SATD markers name their register entry; every rule traces to the SRS |
| Feedback loops not closed | 8 | UAT completed and repeated; audit log reviewed weekly |
| MoMo displaces cash collection | 1 | Monitored as a domain shift, not a feature request |
