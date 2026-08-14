# 4. Software Effort Estimation

> This section answers the examination's required points: why the technique was selected,
> estimated effort, person-hours, development duration, assumptions, constraints, and
> **how the estimation influenced the project scope**.

---

## 4.1 Technique selection and justification

Session 6 sets out five families of estimation technique. Each was assessed against this
project's actual situation — a novel system, no historical project data, a single
developer, and a hard 48-hour ceiling.

| Technique | Suitability here | Decision |
|---|---|---|
| **Expert judgement** | No prior susu-system experience to draw on; single estimator means no Delphi panel and no protection against optimism bias. | Rejected as primary |
| **Estimation by analogy** | Requires similar completed projects with recorded actual effort. None available. | Rejected |
| **Machine-learning estimation** | Requires a sizeable historical dataset. None available; would also be a black box to the examiner. | Rejected |
| **Function Point Analysis** | Countable directly from the SRS *before any code exists*, independent of language, and defensible line by line. | **Selected — sizing** |
| **COCOMO (Basic, organic)** | Converts size into an industry-calibrated effort figure, giving an objective benchmark against the 48-hour budget. | **Selected — effort** |
| **Three-point / PERT (bottom-up over a WBS)** | Produces the operative schedule for the actual window and expresses uncertainty as a range rather than a false-precision number. | **Selected — planning** |
| **Agile story points** | Relative sizing needs a team velocity baseline to convert to time. A solo developer with no sprint history has none. | Rejected |

**Why three techniques rather than one.** Session 6's stated best practice is
triangulation — "use multiple techniques and compare" — and the three chosen answer
different questions:

- **FPA + COCOMO** answers *"what would this system cost to build properly?"* It is the
  objective benchmark. It is deliberately **not** calibrated to a 48-hour student project,
  and that is precisely its value: it establishes the size of the gap.
- **PERT over a WBS** answers *"what can actually be delivered in the hours available?"*
  Session 6 notes bottom-up estimation is "more accurate and defensible" where a detailed
  task breakdown exists — which the SRS provides.

Using only COCOMO would produce a number with no operational meaning. Using only PERT
would let optimism bias set the scope unchallenged. Together, the first exposes the
over-commitment and the second resolves it.

---

## 4.2 Function Point Analysis

### 4.2.1 Weights applied

Weights are taken from the Session 6 table. External Interface Files are not weighted on
that slide; the standard IFPUG values (5 / 7 / 10) are noted for completeness, though the
count is zero here.

| Component | Simple | Average | Complex |
|---|---|---|---|
| External Input (EI) | 3 | 4 | 6 |
| External Output (EO) | 4 | 5 | 7 |
| External Inquiry (EQ) | 3 | 4 | 6 |
| Internal Logical File (ILF) | 7 | 10 | 15 |
| External Interface File (EIF) | 5 | 7 | 10 |

### 4.2.2 Count A — full specified scope (all 38 functional requirements)

**Internal Logical Files**

| Logical file | Complexity | FP |
|---|---|---|
| User (accounts, roles, credentials) | Average | 10 |
| Client (enrolment, daily rate, assignment) | Average | 10 |
| ContributionCycle | Average | 10 |
| Collection | Average | 10 |
| Payout | Simple | 7 |
| RemittanceDeclaration | Simple | 7 |
| AuditLogEntry | Simple | 7 |
| | **Subtotal** | **61** |

**External Interface Files** — none. CO-05 excludes all external system integration. **0**

**External Inputs**

| Input | FR | Complexity | FP |
|---|---|---|---|
| Login | FR-01 | Simple | 3 |
| Enrol client | FR-06 | Complex | 6 |
| Update client details | FR-06 | Average | 4 |
| Reassign client to collector | FR-09 | Simple | 3 |
| Record contribution | FR-11 | Complex | 6 |
| Record catch-up contribution | FR-15 | Complex | 6 |
| Record correction / reversal | FR-33 | Average | 4 |
| Declare cash remittance | FR-24 | Simple | 3 |
| Release payout | FR-20 | Complex | 6 |
| Request early withdrawal | FR-22 | Simple | 3 |
| Approve early withdrawal | FR-22 | Average | 4 |
| Resolve variance with note | FR-27 | Simple | 3 |
| Create / suspend user, assign role | FR-35 | Average | 4 |
| Configure institutional defaults | FR-36 | Simple | 3 |
| | | **Subtotal** | **58** |

**External Outputs**

| Output | FR | Complexity | FP |
|---|---|---|---|
| Digital susu card with computed day states | FR-16 | Complex | 7 |
| Cycle summary (days paid/missed, total, projected payout) | FR-17 | Complex | 7 |
| Daily collection sheet per collector | FR-23 | Average | 5 |
| Daily variance report | FR-25, FR-26 | Complex | 7 |
| Client statement (balance, maturity, net payout) | FR-29 | Average | 5 |
| Supervisor dashboard | FR-37 | Complex | 7 |
| CSV cycle export | FR-38 | Average | 5 |
| Payout advice | FR-18 | Average | 5 |
| | | **Subtotal** | **48** |

**External Inquiries**

| Inquiry | FR | Complexity | FP |
|---|---|---|---|
| Client list / search | FR-08 | Average | 4 |
| Client detail view | FR-08 | Simple | 3 |
| Contribution history list | FR-28 | Average | 4 |
| Audit trail view | FR-34 | Average | 4 |
| User list | FR-35 | Simple | 3 |
| Contribution reference lookup | FR-30 | Simple | 3 |
| | | **Subtotal** | **21** |

**Unadjusted Function Points (full scope)**

```
UFP = ILF 61 + EIF 0 + EI 58 + EO 48 + EQ 21 = 188
```

### 4.2.3 Value Adjustment Factor

Fourteen General System Characteristics, each rated 0 (no influence) to 5 (strong):

| # | Characteristic | Rating | Reasoning |
|---|---|---|---|
| 1 | Data communications | 4 | Web application, users distributed across field and branch |
| 2 | Distributed data processing | 1 | Single application server, single database |
| 3 | Performance | 4 | NFR-01 mandates 2 s render on a 3G-class connection |
| 4 | Heavily used configuration | 2 | Free-tier hosting, modest concurrent load |
| 5 | Transaction rate | 3 | Collection activity concentrated in the morning route window |
| 6 | Online data entry | 5 | All data entry is online and field-based |
| 7 | End-user efficiency | 5 | NFR-02 caps a routine collection at three interactions |
| 8 | Online update | 5 | Internal files updated in real time by field users |
| 9 | Complex processing | 3 | Commission rule, day allocation, variance computation |
| 10 | Reusability | 2 | Single institution; domain layer reusable |
| 11 | Installation ease | 2 | Containerised, environment-variable configuration |
| 12 | Operational ease | 3 | Audit logging, minimal routine administration |
| 13 | Multiple sites | 2 | Branch structure modelled, single deployment |
| 14 | Facilitate change | 4 | Layered architecture (NFR-07), configurable cycle and commission |
| | **ΣGSC** | **45** | |

```
VAF = 0.65 + (0.01 × 45) = 0.65 + 0.45 = 1.10
```

**Adjusted Function Points (full scope)**

```
AFP = UFP × VAF = 188 × 1.10 = 206.8 ≈ 207 FP
```

### 4.2.4 Count B — Must-have scope only (28 functional requirements)

Removing the Should/Could/Won't items from §3.6:

| Component | Removed | Subtotal |
|---|---|---|
| ILF | none — all seven files are required by Must requirements | 61 |
| EI | reassign (3), catch-up (6), request withdrawal (3), approve withdrawal (4), resolve variance (3), user admin (4), configure defaults (3) = **−26** | 32 |
| EO | supervisor dashboard (7), CSV export (5) = **−12** | 36 |
| EQ | audit trail view (4), user list (3) = **−7** | 14 |
| EIF | — | 0 |

```
UFP (Must) = 61 + 32 + 36 + 14 + 0 = 143
AFP (Must) = 143 × 1.10 = 157.3 ≈ 157 FP
```

Cutting ten requirements removes 50 adjusted function points — **24% of the system**.

---

## 4.3 COCOMO Basic (organic mode)

### 4.3.1 Size conversion

Function points are converted to KLOC using a language productivity figure.

> **Assumption AS-01:** 30 source lines of code per function point for Python with an
> ORM and server-side templating. This is a published-average figure for the language
> class; a sensitivity analysis at 25 and 40 LOC/FP is given in §4.3.4 because the choice
> materially affects the result. *The specific productivity table used must be cited in
> `References` in the final document.*

```
KLOC (Must scope) = 157 FP × 30 LOC/FP ÷ 1000 = 4.71 KLOC
```

### 4.3.2 Mode selection

| Mode | a | b | Applies when |
|---|---|---|---|
| **Organic** | **2.4** | **1.05** | Small, familiar team; flexible requirements |
| Semi-detached | 3.0 | 1.12 | Medium size and complexity, mixed experience |
| Embedded | 3.6 | 1.20 | Complex, tightly constrained (safety, hardware) |

**Organic** is selected: the system is small (< 5 KLOC), built by a single developer with
full domain familiarity, using well-understood web technology, with no hardware, safety
or real-time constraints. Semi-detached would be defensible if the mobile-money and SMS
integrations of the full vision were in scope; they are excluded by CO-05 and FR-31.

### 4.3.3 Effort and duration

```
Effort = a × (KLOC)^b
       = 2.4 × (4.71)^1.05
       = 2.4 × 5.09
       = 12.2 person-months
```

Converting at the COCOMO standard of 152 hours per person-month:

```
Person-hours = 12.2 × 152 = 1,857 person-hours
```

Schedule, using Boehm's organic schedule equation `TDEV = 2.5 × (Effort)^0.38`
(this extends beyond the Session 6 slide, which stops at the effort equation):

```
TDEV = 2.5 × (12.2)^0.38 = 2.5 × 2.59 = 6.5 months
Average staffing = 12.2 ÷ 6.5 ≈ 1.9 developers
```

Applying instead the simplified division used in the Session 6 worked example, a single
developer would need **12.2 months** — the schedule equation's 6.5 months assumes roughly
two people working in parallel.

### 4.3.4 Sensitivity to the LOC/FP assumption

| LOC/FP | KLOC | Effort (PM) | Person-hours |
|---|---|---|---|
| 25 (optimistic) | 3.92 | 10.1 | 1,533 |
| **30 (adopted)** | **4.71** | **12.2** | **1,857** |
| 40 (pessimistic) | 6.28 | 16.5 | 2,511 |

The estimate is **not** sensitive enough for the conclusion to change: across the entire
range the requirement is over 1,500 person-hours against a 48-hour budget.

### 4.3.5 Full-scope comparison

| Scope | AFP | KLOC | Effort (PM) | Person-hours |
|---|---|---|---|---|
| Full specified (38 FRs) | 207 | 6.21 | 16.3 | 2,482 |
| Must-have only (28 FRs) | 157 | 4.71 | 12.2 | 1,857 |
| | | | **Saving** | **625 person-hours** |

---

## 4.4 The gap, stated honestly

```
COCOMO estimate (Must scope):        1,857 person-hours
Available window:                       48 hours (single developer)
Implementation allocation (Phase 3):    20 hours
                                     ─────────────────
Ratio of required to available:          ~93 : 1
```

A ratio of 93:1 is not a usable planning number, and it would be dishonest to present it
as one. It requires explanation rather than presentation:

**Why COCOMO overstates this project.**

1. **It prices the whole lifecycle.** The 1,857 hours include requirements engineering,
   design, integration, formal QA and documentation. Those activities are being performed
   here, but they are budgeted separately across Phases 1–2 and 4–6, not inside the
   20-hour implementation window.
2. **It predates framework leverage.** COCOMO's constants were calibrated on projects
   where authentication, ORM persistence, routing, templating, session management and CSRF
   protection were all hand-written. Flask, SQLAlchemy and Jinja supply these as
   configuration. The LOC/FP figure accounts for language, not for framework scaffolding.
3. **Basic COCOMO ignores team and tool factors entirely.** It has no effort multipliers —
   that is what COCOMO II's cost drivers exist for. Modern tooling, high developer
   familiarity and mature libraries are invisible to the Basic model.
4. **It assumes a team, and therefore communication cost.** A solo developer with complete
   domain knowledge incurs no coordination overhead, no handover, and no specification
   ambiguity between people.

**What the number is genuinely worth.** It is evidence that the *specified* system is an
industrial-scale build, and that anything deliverable in 48 hours is a deliberately
reduced subset. It converts "I ran out of time" into a scoping decision made in advance
with a stated basis. That is the reason it is retained rather than discarded.

---

## 4.5 Three-point (PERT) bottom-up estimate — the operative plan

`E = (O + 4M + P) / 6`, in hours, over the implementation WBS.

| # | Task | O | M | P | E |
|---|---|---|---|---|---|
| 1 | Project skeleton, config, Docker Postgres, app factory | 0.5 | 1.0 | 2.0 | 1.08 |
| 2 | Domain layer: entities, money type, business rules | 1.5 | 2.5 | 4.0 | 2.58 |
| 3 | Database schema, SQLAlchemy models | 1.0 | 1.5 | 3.0 | 1.67 |
| 4 | Repository layer | 0.5 | 1.0 | 2.0 | 1.08 |
| 5 | Authentication: hashing, sessions, role decorators | 1.0 | 2.0 | 3.5 | 2.08 |
| 6 | Client enrolment, list and search | 1.0 | 1.5 | 2.5 | 1.58 |
| 7 | Cycle open/close logic | 0.5 | 1.0 | 2.0 | 1.08 |
| 8 | Record contribution with all validation rules | 1.5 | 2.5 | 4.0 | 2.58 |
| 9 | Digital susu card view (31-box grid) | 1.0 | 1.5 | 3.0 | 1.67 |
| 10 | Payout computation and release | 1.0 | 1.5 | 2.5 | 1.58 |
| 11 | Remittance declaration and variance | 1.0 | 1.5 | 2.5 | 1.58 |
| 12 | Client self-service views | 0.5 | 1.0 | 2.0 | 1.08 |
| 13 | Append-only audit log and reversal | 0.5 | 1.0 | 2.0 | 1.08 |
| 14 | Collector route sheet | 0.5 | 1.0 | 2.0 | 1.08 |
| 15 | UI, HTMX interactions, mobile layout | 1.0 | 2.0 | 3.5 | 2.08 |
| 16 | Seed data and demo accounts | 0.25 | 0.5 | 1.0 | 0.54 |
| | **Total expected effort** | | | | **24.5 h** |

**Uncertainty.** Per-task `σ = (P − O)/6`; total `σ = √Σσ² = 1.22 h`.

| Confidence | Range |
|---|---|
| 68% (±1σ) | 23.2 – 25.7 h |
| 95% (±2σ) | 22.0 – 26.9 h |

> **Caveat on that range.** PERT assumes tasks vary independently. They do not: a single
> developer who is slow on the domain layer will likely be slow on the service layer too,
> because the cause is shared. The true variance is therefore wider than ±1.22 h, and the
> range above should be read as a lower bound on uncertainty, not a guarantee.

**Cone of Uncertainty.** Session 6 places a project with requirements defined but design
incomplete in the **0.5× – 2× band**. Applied to 24.5 h, the honest interval is
**12 – 49 hours**. The upper bound consumes the entire examination window on
implementation alone, leaving nothing for testing, deployment or documentation — 30 of
the 50 marks. This is the finding that forces the scope decision below.

---

## 4.6 How the estimation influenced the project scope

**The finding.** Bottom-up expected effort for the Must scope is **24.5 hours** against a
**20-hour** implementation allocation — a 23% over-commitment at the *expected* value,
before any allowance for the upper half of the cone.

**The decision.** Rather than begin and hope, 4.1 hours were removed in advance by
deliberately reducing implementation quality in areas that do not touch BR-01 or BR-02
(protection and verifiability of client funds).

| Cut | Hours saved | What is sacrificed | Debt classification |
|---|---|---|---|
| Schema created via `create_all()` and a seed script instead of Alembic migrations | 0.7 | No versioned schema history; production schema changes need manual intervention | Infrastructure debt |
| Tailwind via CDN with minimal custom CSS instead of a built stylesheet | 1.0 | Render-blocking external stylesheet, no purging, larger payload — works against NFR-01 | Design / infrastructure debt |
| Client list as a plain table, no search or pagination | 0.5 | FR-08 only partially satisfied; degrades past ~50 clients | Usability debt |
| Reversal exposed as a minimal supervisor-only form | 0.6 | Append-only model fully implemented, correction workflow is bare | Code debt |
| Route sheet as a static list without "not yet collected" filtering | 0.5 | FR-23 met literally; collector efficiency (NFR-02) reduced | Usability debt |
| HTMX applied to the three highest-value interactions only, full page loads elsewhere | 0.8 | Inconsistent interaction model across the application | Design debt |
| | **4.1 h** | | |

```
24.5 h − 4.1 h = 20.4 h  ≈  20 h allocation
```

**What was explicitly *not* cut, and why.** The domain layer (2.58 h), contribution
validation (2.58 h), audit log (1.08 h) and client self-service views (1.08 h) were
protected in full. These four carry BR-01, BR-02 and BR-05 — the reason the system exists.
Cutting implementation quality elsewhere to protect them is the whole substance of the
scoping decision.

**The consequence is recorded, not hidden.** Every cut above is a *prudent and deliberate*
entry on Fowler's technical debt quadrant — taken knowingly, for a stated reason, with an
intended repayment. Each one carries forward into the debt register in
`08-technical-debt.md` with its cause, impact, priority and proposed resolution, and into
the repayment plan in `11-maintenance-evolution.md`. The estimation did not merely predict
the work; it generated the debt register.

---

## 4.7 Assumptions and constraints on the estimate

**Assumptions**

| ID | Assumption |
|---|---|
| AS-01 | 30 LOC per function point for Python with ORM and templating (sensitivity tested, §4.3.4). |
| AS-02 | Organic COCOMO mode applies — small system, familiar technology, no hardware constraints. |
| AS-03 | 152 hours per person-month (COCOMO standard). |
| AS-04 | Requirements remain stable through the window; the change control process of §3.8 governs any deviation. |
| AS-05 | Development environment, Docker and deployment accounts are working and not counted as project effort. |
| AS-06 | The developer sustains productive work across the window; sleep and breaks are outside the 20-hour implementation allocation, not inside it. |

**Constraints on the estimate**

| ID | Constraint |
|---|---|
| ES-01 | No historical project data exists, so no analogy-based or ML validation is possible. |
| ES-02 | A single estimator means no Delphi convergence and no protection against optimism bias. Session 6 identifies planning fallacy and optimism bias as the dominant risks here; triangulation across three methods is the only available mitigation. |
| ES-03 | Function point counting was performed once by one person. Independent recounts typically vary by ±10–15%. |
| ES-04 | The 48-hour window is fixed before estimation, which Session 6 identifies as *external pressure* — a known source of estimate distortion. It is mitigated by fixing the deadline and flexing scope, never the reverse. |

---

## 4.8 Estimation accuracy review

Session 6's closing best practice is to record actuals and review accuracy afterwards.
This table is completed in Phase 6 and reported in the final document.

| Task | Estimated (h) | Actual (h) | Variance | Note |
|---|---|---|---|---|
| 1 Project skeleton | 1.08 | | | |
| 2 Domain layer | 2.58 | | | |
| 3 Database schema | 1.67 | | | |
| 4 Repository layer | 1.08 | | | |
| 5 Authentication | 2.08 | | | |
| 6 Client enrolment | 1.58 | | | |
| 7 Cycle logic | 1.08 | | | |
| 8 Record contribution | 2.58 | | | |
| 9 Digital card view | 1.67 | | | |
| 10 Payout | 1.58 | | | |
| 11 Remittance & variance | 1.58 | | | |
| 12 Client views | 1.08 | | | |
| 13 Audit log | 1.08 | | | |
| 14 Route sheet | 1.08 | | | |
| 15 UI & HTMX | 2.08 | | | |
| 16 Seed data | 0.54 | | | |
| **Total** | **24.5** | | | |

Magnitude of Relative Error will be computed as `MRE = |Actual − Estimated| / Actual`,
and the result — favourable or not — reported as the closure of the estimation process
described in §4.1.
