# 11. Maintenance Strategy and Future Evolution

> Covers sections 15 and 16 of the examination's required document structure, including the technical debt repayment plan
> the paper requires.

---

# PART A: MAINTENANCE STRATEGY

## 11.1 The four maintenance categories, applied

The four categories are those established by Lientz and Swanson and presented in
Sommerville [8] and Tsui, Karam and Bernal [10]. Generic definitions are of
limited value, so what follows is what each category means for *this* system,
with instances already identified.

### Corrective: fixing defects

| | |
|---|---|
| **Trigger** | Defect reported by a user, or surfaced by the audit log |
| **Current capability** | **Weak.** No error aggregation and no alerting (**TD-17**), so a production failure is discovered when a user reports it |
| **Evidence** | Seven of the eight defects found so far (Section 9.8) came from tests or probing; **DEF-06 came from a person clicking through**, and no automated test could have caught it |
| **Improvement** | TD-17's repayment (structured logging, error tracking, uptime checks) moves detection ahead of the user report |

### Adaptive: responding to environmental change

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

### Perfective: improving what already works

Driven by the debt register and by measurement, not by taste:

- **TD-02**, self-host and purge the stylesheet. Measured at 0.52 s of serial
  round trip today (Section 12.6), and the largest single contributor to NFR-01 failing.
- **TD-16**, the N+1 on the route sheet, before client counts make it visible.
- **TD-03, TD-04, TD-05, TD-06**, the convenience features cut under time
  pressure. FR-08 and FR-23 remain *partially* satisfied until these land.

### Preventive: reducing future cost

- **TD-01**, migrations. Every further schema change costs manual DDL until this
  is done, and it blocks TD-09.
- **TD-12**, pin dependencies and commit a lockfile, so a transitive release
  cannot break production without a change in this repository.
- Keep test coverage at its current level (97%) as features are added. Session 3
  names test debt as the classic casualty of delivery pressure; this project has
  none, and that is a position to defend rather than assume.

## 11.2 Defect triage

| Severity | Definition | Response | Example from this project |
|---|---|---|---|
| **S1 Critical** | Client funds misrecorded, or the audit trail compromised | Immediate; roll back if needed | A negative payout (guarded by BR-R9 and `ck_payout_balances`) |
| **S2 High** | A role cannot complete their core task | Same day | DEF-03, DEF-04, every page 500ing |
| **S3 Medium** | Feature impaired, workaround exists | Next release | DEF-06, the stale running total |
| **S4 Low** | Cosmetic or documentation | Scheduled | DEF-01, an incorrect claim in a docstring |

Rollback is a first-class response: Cloud Run retains previous revisions, so
reverting is one command and needs no rebuild (Section 12.9).

## 11.3 Security and dependency maintenance

| Activity | Cadence | Notes |
|---|---|---|
| Dependency vulnerability scan | Monthly, and on every release | Not yet automated; **TD-12** leaves versions unpinned |
| Framework security releases | As published | Flask, SQLAlchemy, psycopg, gunicorn |
| Base image rebuild | Monthly | `python:3.12-slim` accumulates OS-level CVEs even when the application does not change |
| Secret rotation | Annually, and on any suspected exposure | Both live in Secret Manager; rotation is a new version plus a redeploy |
| Audit log review | Weekly | `AUTHORISATION_DENIED` and `LOGIN_FAILED` are the signals that matter, and with **TD-14** unfixed, the log is the *only* defence against brute force |

**The three Critical debt items are security items, and they are maintenance
work, not features.** TD-14 (no rate limiting), TD-15 (the collector knows the
client's password) and TD-09 (audit log mutable) must be closed before the
system holds real client money.

---

# PART B: FUTURE EVOLUTION

## 11.4 Lehman's Laws applied to SusuBook

Session 4's laws [4], formulated by Lehman [19] and developed with Belady [14],
describe how systems behave over time. Each is taken in turn,
with what it predicts *for this system*, and what has been done, or must be done,
in response.

### 1. Continuing change

> *A program used in a real-world environment must change, or become
> progressively less useful in that environment.*

Susu is not a static practice. Mobile money is displacing cash collection,
regulation is tightening, and a collector who finds SusuBook slower than a paper
card will return to the card, the fallback is always available and costs
nothing.

**Response.** The deferred requirements are not a wish list, they are the change
pipeline: FR-15 (catch-up payments), FR-22 (early withdrawal). FR-31 (SMS) has
already been delivered under CR-002. The architecture was left open where change
is most likely — `CommissionPolicy` is a Strategy interface precisely because
commission policy is the term most likely to be renegotiated (FR-36).

**Where this law bites hardest.** Mobile money is the change most likely to make
this system less useful, and not by competing with it: client self-payment would
remove the collector the entire product is built around. That is analysed at
Section 11.8.1, because responding to it is a product decision rather than a
development task.

### 2. Increasing complexity

> *As a program evolves, its structure becomes more complex unless work is done
> explicitly to reduce it.*

Fifteen business rules, four layers, seventeen debt items, at version one. Every
deferred requirement adds branching to the same domain: catch-up payments
complicate contribution allocation, early withdrawal complicates the cycle state
machine, multi-institution complicates every query.

**Response.** This law is the reason for several earlier design decisions. The
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
record in Section 4.8 (Estimation accuracy review), with estimates against actuals and an
MRE. Session 6's closing advice (record actuals, review accuracy) is exactly
how a team acquires the historical data that makes this law predictive rather
than merely descriptive.

### 4. Conservation of organisational stability

> *The average rate of development is approximately constant and independent of
> the resources devoted to it.*

The debt repayment plan totals 19–24 hours (Section 11.6). The temptation, facing a
deadline, is to assume two developers would halve it.

**Response.** The law says otherwise, as does Brooks [13], and the plan is not
built on that assumption. Items 1–4 are sequenced by dependency (TD-01 gates TD-09), not by
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
and unlearnable, and collectors, who are the least able to absorb disruption,
would bear the cost.

### 6. Continuing growth

> *Functional content must continually increase to maintain user satisfaction.*

Every stakeholder group already wants more than v1 delivers: clients want SMS
confirmation (FR-31), collectors want catch-up payments (FR-15), supervisors want
a dashboard (FR-37) and variance resolution (FR-27), administrators want user
management (FR-35).

**Response.** MoSCoW prioritisation gave a defensible v1; the same discipline
must govern growth. Note the tension with the second law, growth adds
functionality, which adds complexity, which is why perfective work must be
funded alongside features rather than after them.

### 7. Declining quality

> *Quality will appear to decline unless the system is adapted to changes in its
> operational environment.*

**This law is already operating on SusuBook, with no code change required.**
NFR-01 specifies 2 seconds on a 3G connection. Measurement (Section 12.6) shows first
render already exceeding 1.1 s on a *good* connection, so the requirement is
probably not met today. As client counts grow, TD-16's N+1 degrades the route
sheet further. Nothing will have changed in the code; the environment will have
moved.

**Response.** Quality attributes need measurement over time, not a one-off
verification at release. The performance figures in Section 12.6 are a baseline to be
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

The development process contains a further loop, for which this project provides direct evidence:
**DEF-06 was found by a user clicking through the interface, not by any of the
256 automated tests, and could not have been, because every test asserted the
*response* to a request and none asserted the state of the page afterwards.**

That is Lehman's eighth law demonstrated inside the project rather than quoted at
it. Automated tests confirm what the developer thought to check; only the user
loop finds what they did not. It is also the clearest argument for closing the
outstanding UAT (Section 9.9).

## 11.5 Evolution roadmap

| Release | Contents | Rationale |
|---|---|---|
| **v1.1 — Security** | TD-01 migrations, TD-14 rate limiting, TD-09 audit enforcement. ~~TD-15~~ **already repaid** | Everything blocking real client money. Nothing else ships first. Two Critical items remain. |
| **v1.2 — Reach** | ~~FR-31 SMS notification~~ **delivered under CR-002**; remaining: lift the recipient allowlist, TD-18 delivery tracking | FR-31 shipped in this release. The mechanism mitigating **A5** now exists, but recipients are still restricted to an allowlist, so the mitigation is not yet realised for real clients. |
| **v1.3 — Field efficiency** | FR-15 catch-up payments, TD-05 route ordering, TD-03 search, TD-16 N+1 | The collector's daily experience. Domain rules already accept `days_covered`, so FR-15 needs no change to the business rules. |
| **v1.4 — Oversight** | FR-34 audit viewer, FR-37 dashboard, FR-27 variance resolution, FR-35 user admin | Supervisor and administrator capability |
| **v1.5 — Performance** | TD-02 stylesheet build, region relocation, TD-11 denormalised totals | Directly targets NFR-01, which is currently not met |
| **v2.0 — Reshaping** | Multi-institution tenancy, offline capability, **client self-payment** and **variable contribution amounts** | Each changes the data model or the product's scope, not merely its features. The last two are analysed in Section 11.8: one removes the collector the system is built around, the other replaces the card of days with a ledger of amounts. Neither is additive. |

## 11.6 Technical debt repayment plan

> Required explicitly by the examination. Full analysis at Section 8.

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

**Items 1, 2 and 4, around 5 to 7 hours, must complete before the system
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
| Quality erodes without anyone noticing | 7 | Re-measure Section 12.6 baseline each release; NFR-01 already recorded as not met |
| Maintainer changes, context lost | 2 | SATD markers name their register entry; every rule traces to the SRS |
| Feedback loops not closed | 8 | UAT completed and repeated; audit log reviewed weekly |
| MoMo displaces cash collection | 1 | Monitored as a domain shift, not a feature request. Analysed at Section 11.8.1: self-payment partially obsoletes the product rather than extending it |
| Strategic changes implemented incrementally by accident | 2, 5 | Section 11.8 records self-payment and variable amounts as questions requiring a product decision, so they cannot be absorbed one endpoint at a time |

## 11.8 Two proposed changes, analysed

Both were raised as candidates for future scope. Both are recorded here rather
than in the roadmap above, because neither is a feature: one threatens the
product's reason to exist, and the other changes its data model. Treating them
as ordinary backlog items would misrepresent what they are.

### 11.8.1 Client self-payment

**The proposal.** Let a client pay their contribution directly, by mobile
money, standing order or a payment link: without the collector visiting.

**What it removes.** Not a step. The collector.

The collector is not incidental to SusuBook; the collector is the reason it
exists. Every core mechanism assumes one:

| Mechanism | What it assumes | Under self-payment |
|---|---|---|
| **BR-01**, prevent under-recording | A collector who receives cash and might record less | No collector, no under-recording to prevent |
| **Variance report** (FR-25) | Cash a collector holds and must bank | Nothing to reconcile; the money never enters a collector's hands |
| **QR card** (FR-39, FR-40) | A collector scanning a client's card | The client is not being visited |
| **Commission** (BR-R8) | A fee for the daily visit | No visit occurs, so the entitlement is undefined |
| **FR-05** authorisation | A collector–client assignment | The client is acting on their own behalf |
| **Audit trail** (BR-05) | Attribution *to a collector* | The actor is the client |
| **Problem P1**, no independent record | A paper card held by the collector | Mobile money already issues the client a receipt |

**Assessment.** Self-payment does not extend SusuBook. It
**partially obsoletes it**. If clients pay digitally, the payment rail already
produces the timestamped, attributable, non-repudiable record that this system
was built to supply. The problem stated in Section 1.3 (Problem statement) is a problem
*because* collection is cash-in-hand and the record is a paper card.

This is **Lehman's first law with a specific name on it** (Section 11.4). The adaptive
maintenance table already lists "mobile money displacing cash collection" as an
environmental change; self-payment is what that change looks like when it
arrives.

**Three possible responses, and they are strategic, not technical.**

1. **Become the ledger the payment rail does not provide.** Mobile money records
   a transfer; it does not record a *susu cycle*, days paid, maturity,
   commission, payout, or the relationship with a collector who still services
   the client. SusuBook would move from being the record of collection to being
   the record of the savings agreement. The commission model would have to be
   renegotiated, because it currently prices a visit.
2. **Hybrid, and accept the complexity.** Some clients pay in cash to a
   collector, some pay themselves, some do both within one cycle. This is
   probably what would actually happen, and it is the hardest option: the
   variance report becomes meaningful only for the cash portion, and the audit
   trail needs a second kind of actor.
3. **Decline, and stay a cash-collection system.** Defensible while cash
   dominates, and Lehman's first law says the system becomes progressively less
   useful as that ceases to be true.

**Recommendation.** Not v1.x. It requires answering *what SusuBook is for* once
the collector is optional, and that is a product decision rather than a backlog
item. Recorded here so that the question is asked deliberately rather than
answered by accident, one feature at a time.

### 11.8.2 Variable contribution amounts

**The proposal.** Allow a client to contribute different amounts on different
days, rather than a fixed daily rate.

**What breaks.** Not a validation rule: the model.

BR-R7 requires a contribution to be a whole multiple of the agreed daily rate.
That rule is not arbitrary bookkeeping; it is what makes the rest of the domain
coherent:

- **The susu card** (FR-16) shows 31 boxes as paid, missed or pending. A box
  means "one day's agreed amount". If amounts vary, a filled box no longer says
  how much: the card becomes a calendar, not a record.
- **Days paid** (FR-17) stops being a measure of savings. A client who paid
  GHS 1 on thirty days would show as more complete than one who paid GHS 50 on
  ten.
- **Commission** (BR-R8) is "one day's contribution". With no fixed daily
  amount, that phrase has no referent. It would have to become a percentage, a
  flat fee, or something negotiated, a change to the commercial arrangement,
  not the software.
- **The projected payout** shown to the client throughout the cycle depends on
  knowing what a complete cycle is worth.

**What the design already accommodates.** Some flexibility exists and is not the
same thing: each client has their *own* rate, rates are snapshotted per cycle so
they can be renegotiated between cycles, and `validate_contribution` already
takes a `days_covered` parameter so a catch-up payment of N × rate (FR-15) needs
no change to the rule. What is fixed is the rate *within* a cycle.

**The real change.** Moving from a **card of days** to a **ledger of amounts**.
That is a different product: the client saves toward a target or simply
accumulates, days become irrelevant, and the card metaphor, the thing this
system deliberately preserved because clients already understand it, is
discarded.

**Recommendation.** v2.0 alongside self-payment, and probably the same decision:
both are consequences of the same shift away from a collector arriving daily for
a fixed amount. If either is adopted, the domain model in
Section 7.9 (Domain class diagram) is rewritten, not extended.

### 11.8.3 Why these are recorded and not scheduled

Session 3 warns that a debt register becomes archaeology if it is not worked.
The same is true of a roadmap. Listing "self-payment" and "variable amounts" as
v1.x items would imply they are additive, and a future maintainer reading that
list would begin implementing them one endpoint at a time, discovering only
part-way through that the commission model no longer makes sense and the variance
report has quietly become meaningless for half the payments.

Recording them as analysed strategic questions costs nothing now and prevents
that. It is also the honest position: the project team can see what these changes
would do, and has not decided.
