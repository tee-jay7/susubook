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

Function point analysis follows Albrecht's method [20] as presented in Session 6 [6].

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

### 4.2.5 Revision under CR-001

The counts above are the Phase 1 baseline. Change request CR-001 (QR-based client
identification) subsequently added two components. The baseline is left intact and the
revision recorded separately, so the effect of the change remains visible.

| Added component | Type | Complexity | FP |
|---|---|---|---|
| Printable client QR card | External Output | Average | 5 |
| Client reference resolution | External Inquiry | Simple | 3 |
| | | **Subtotal** | **+8** |

| | Baseline | After CR-001 |
|---|---|---|
| UFP (Must scope) | 143 | **151** |
| AFP (Must scope) | 157 | **166** |
| UFP (full scope) | 188 | 196 |
| AFP (full scope) | 207 | 216 |

All figures in §4.3 below are computed on the **post-CR-001** counts.

---

## 4.3 COCOMO Basic (organic mode)

Constants and equations from Boehm [11]; the effort equation and mode table as
presented in Session 6 [6].

### 4.3.1 Size conversion

Function points are converted to KLOC using a language productivity figure.

> **Assumption AS-01:** 30 source lines of code per function point for Python with an
> ORM and server-side templating. This is a published-average figure for the language
> class; a sensitivity analysis at 25 and 40 LOC/FP is given in §4.3.4 because the choice
> materially affects the result. *The specific productivity table used must be cited in
> `References` in the final document.*

```
KLOC (Must scope, post-CR-001) = 166 FP × 30 LOC/FP ÷ 1000 = 4.98 KLOC
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
       = 2.4 × (4.98)^1.05
       = 2.4 × 5.396
       = 13.0 person-months
```

Converting at the COCOMO standard of 152 hours per person-month:

```
Person-hours = 13.0 × 152 = 1,969 person-hours
```

Schedule, using Boehm's organic schedule equation `TDEV = 2.5 × (Effort)^0.38`
(this extends beyond the Session 6 slide, which stops at the effort equation):

```
TDEV = 2.5 × (13.0)^0.38 = 2.5 × 2.65 = 6.6 months
Average staffing = 13.0 ÷ 6.6 ≈ 2.0 developers
```

Applying instead the simplified division used in the Session 6 worked example, a single
developer would need **13.0 months** — the schedule equation's 6.6 months assumes roughly
two people working in parallel.

### 4.3.4 Sensitivity to the LOC/FP assumption

| LOC/FP | KLOC | Effort (PM) | Person-hours |
|---|---|---|---|
| 25 (optimistic) | 4.15 | 10.7 | 1,626 |
| **30 (adopted)** | **4.98** | **13.0** | **1,969** |
| 40 (pessimistic) | 6.64 | 17.5 | 2,663 |

The estimate is **not** sensitive enough for the conclusion to change: across the entire
range the requirement is over 1,600 person-hours against a 48-hour budget.

### 4.3.5 Full-scope comparison

| Scope | AFP | KLOC | Effort (PM) | Person-hours |
|---|---|---|---|---|
| Full specified (40 FRs) | 216 | 6.48 | 17.1 | 2,595 |
| Must + CR-001 (30 FRs) | 166 | 4.98 | 13.0 | 1,969 |
| | | | **Saving** | **626 person-hours** |

For reference, the Phase 1 baseline before CR-001: full scope 207 AFP / 16.3 PM /
2,482 hours; Must scope 157 AFP / 12.2 PM / 1,857 hours. CR-001 added 0.8 person-months
(112 person-hours) to the delivered scope under COCOMO.

---

## 4.4 The gap, stated honestly

```
COCOMO estimate (Must scope):        1,969 person-hours
Available window:                       48 hours (single developer)
Implementation allocation (Phase 3):    20 hours
                                     ─────────────────
Ratio of required to available:          ~98 : 1
```

A ratio of 98:1 is not a usable planning number, and it would be dishonest to present it
as one. It requires explanation rather than presentation:

**Why COCOMO overstates this project.**

1. **It prices the whole lifecycle.** The 1,969 hours include requirements engineering,
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
| 17 | QR issuance and scan-to-collect *(CR-001)* | 0.5 | 0.85 | 1.6 | 0.92 |
| | **Total expected effort** | | | | **25.4 h** |

**Uncertainty.** Per-task `σ = (P − O)/6`; total `σ = √Σσ² = 1.24 h`.

| Confidence | Range |
|---|---|
| 68% (±1σ) | 24.1 – 26.6 h |
| 95% (±2σ) | 22.9 – 27.8 h |

> **Caveat on that range.** PERT assumes tasks vary independently. They do not: a single
> developer who is slow on the domain layer will likely be slow on the service layer too,
> because the cause is shared. The true variance is therefore wider than ±1.22 h, and the
> range above should be read as a lower bound on uncertainty, not a guarantee.

**Cone of Uncertainty.** Session 6 places a project with requirements defined but design
incomplete in the **0.5× – 2× band**. Applied to 25.4 h, the honest interval is
**12.7 – 50.7 hours**. The upper bound consumes the entire examination window on
implementation alone, leaving nothing for testing, deployment or documentation — 30 of
the 50 marks. This is the finding that forces the scope decision below.

---

## 4.6 How the estimation influenced the project scope

**The finding.** Bottom-up expected effort for the Must scope was **24.5 hours** against a
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

### Revision under CR-001

Change request CR-001 subsequently added QR-based client identification (FR-39, FR-40) at
**+0.92 h**, revising the plan:

```
25.4 h − 4.1 h = 21.3 h  vs  20 h allocation  →  +6.4% overrun
```

**The overrun was accepted rather than absorbed.** A further 1.3 hours of quality cuts
could have been manufactured to land the arithmetic on exactly 20.0. That was rejected:
Session 6 identifies external schedule pressure as a recognised source of estimate
distortion, and revising an estimate to fit a predetermined budget *is* that distortion.
The overrun is carried openly and tracked against actuals in §4.8.

It is contained by priority rather than by arithmetic. FR-39 and FR-40 are **Should**, so
if Phase 3 runs behind, task 17 is the first work abandoned and no Must requirement is
affected. The full decision record is in `CHANGELOG-requirements.md`.

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

Session 6's closing best practice is to record actuals and review accuracy
afterwards. Two things can be closed out: the **size** estimate, precisely; and
the **effort** estimate, which cannot — for reasons set out in §4.9, because
knowing when data does not support a conclusion is part of the practice.

### 4.8.1 Size — closed

| | Estimated | Actual | Variance |
|---|---|---|---|
| Adjusted function points | 166 | — | — |
| LOC per function point (AS-01) | 30 | **20.7** | −31% |
| Source size | 4.98 KLOC | **3.43 KLOC** | **−31%** |
| COCOMO organic effort at that size | 12.95 PM | 8.76 PM | −32% |

```
MRE = |3.43 − 4.98| / 3.43 = 0.45
```

Measured over 3,433 non-blank, non-comment lines of application code
(`10-implementation.md` §10.2).

**Assumption AS-01 was wrong, and in a specific direction.** 30 LOC per function
point came from published averages for the language class; actual productivity
was **20.7** — below even the optimistic 25 used in the sensitivity analysis
(§4.3.4). Two causes are consistent with the delivered code: modern frameworks
supply as configuration what those averages assume is hand-written (routing,
sessions, ORM persistence, CSRF, templating), and some function points produce
very little code — the QR card is 5 adjusted function points and roughly 15
lines, because the library does the work.

The sensitivity analysis anticipated this *class* of error but under-bounded it,
setting the range at 25–40. Derived from measurement rather than published
tables, it would have started lower.

**The conclusion of §4.4 is unaffected.** Even at actual size, COCOMO puts the
system at 8.76 person-months — over 1,300 person-hours against a 48-hour window.
The gap narrows and remains of the same order.

### 4.8.2 Effort — actuals against the 48-hour plan

The project is planned in hours within a 48-hour window, so the actuals are
recorded in the same unit: elapsed time per phase, taken from commit timestamps,
against the allocation in the examination's Part B plan.

| Phase | Allocated | Elapsed | Window occupied |
|---|---|---|---|
| 1. Planning & Requirements | 6 h | 0.33 h | h0.00 – h0.33 |
| 2. Analysis & Design | 6 h | 0.12 h | h0.33 – h0.45 |
| 3. Implementation | 20 h | 0.73 h | h0.45 – h1.17 |
| 4. Testing & Refinement | 6 h | **2.34 h** | h1.17 – h3.51 |
| 5. Deployment | 4 h | **2.48 h** | h3.51 – h5.99 |
| 6. Documentation | 6 h | 0.48 h* | h5.99 – h6.47 |
| **Total** | **48 h** | **6.47 h** | |

\* Phase 6 was still in progress at the time of measurement.

### 4.8.3 The finding is the distribution, not the total

Comparing totals is the least informative reading. The **shape** of the plan is
where the error lies, and that comparison is valid regardless of absolute
magnitude:

| Phase | Share of plan | Share of actual | |
|---|---|---|---|
| 1. Planning & Requirements | 12.5% | 5.1% | over-allocated |
| 2. Analysis & Design | 12.5% | 1.9% | over-allocated |
| **3. Implementation** | **41.7%** | **11.3%** | **heavily over-allocated** |
| **4. Testing & Refinement** | **12.5%** | **36.2%** | **heavily under-allocated** |
| **5. Deployment** | **8.3%** | **38.3%** | **heavily under-allocated** |
| 6. Documentation | 12.5% | 7.4%* | in progress |

**Testing and deployment together were allocated 21% of the window and consumed
75% of the time actually spent.** Implementation was allocated 42% and consumed
11%.

This inverts the assumption the whole estimate was built on. §4.5 spent seventeen
WBS tasks decomposing implementation and treated testing and deployment as
comparatively minor. The reverse held:

- **Deployment (2.48 h)** absorbed VPC egress configuration, Secret Manager
  wiring, a Cloud Run Job for schema creation because the database is private,
  and **DEF-08** — Google Front End silently intercepting `/healthz`. None of
  that is application code, and none of it was decomposed in the WBS at all.
- **Testing (2.34 h)** absorbed the integration and system suites, and four of
  the eight defects. Two of those were errors in the developer's own
  assumptions rather than in the code.

**This is the most useful thing the estimate produced.** The magnitude comparison
is contaminated (§4.9); the distribution is not, because both figures come from
the same project. The corrective action for a future estimate is specific: shift
weight out of implementation and into deployment and testing, and decompose
deployment into a WBS rather than treating it as a single 4-hour block.

### 4.8.4 Per-task actuals

The 17-task breakdown below cannot be completed from the record. Commits do not
partition along WBS boundaries — a single commit delivers the domain layer, its
tests and its documentation together — so per-task figures would be invented
rather than measured.

| Task | Estimated (h) | Actual (h) | Variance | Note |
|---|---|---|---|---|

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
| 17 QR issuance & scan *(CR-001)* | 0.92 | — | — | Not separable |
| **Total** | **25.4** | — | — | See §4.8.2 for phase-level actuals |

---

## 4.9 How to read these actuals

Three qualifications, so the figures are not read as more than they are.

**Elapsed time is not pure effort.** Intervals between commits include
infrastructure setup, container builds, deploy waits and review. The 2.48 hours
against Phase 5 covers a period in which much of the work was cloud
configuration — which AS-05 excludes from project effort by definition. The
distribution finding in §4.8.3 survives this, because the same measure is applied
to every phase; the absolute total does not.

**No instrument was in place.** Effort was not tracked as the work happened;
these figures are reconstructed from commit timestamps afterwards. Session 6's
practice is to *record* actuals as work occurs, and reconstruction is inference.
A future project should instrument at the WBS level from the first hour — that
is the specific corrective action, and it is what would have made §4.8.4
completable.

**The magnitude comparison is weaker than the distribution comparison.** The
25.4-hour PERT estimate priced a single developer building this system task by
task. Dividing the elapsed total into it would yield a tidy MRE, and it would be
a number about production method rather than about estimation accuracy. §4.8.3 is
reported instead because a ratio between phases, both measured the same way in
the same project, does not depend on that.

**What the estimate is nonetheless credited with.** It did the job it was built
for. It exposed a 23% over-commitment *before* implementation began, forced the
scope decision in §4.6, and generated the technical debt register in the process.
That value was realised at the time of estimating and does not depend on
retrospective validation.

**What is not claimed.** That the effort estimate was validated against measured
effort. It was not, and §4.8.4 is left incomplete rather than filled with
plausible numbers.

**Closing the loop to ES-01.** Constraint ES-01 recorded that no historical
project data existed to calibrate against. That was true because no earlier
project recorded actuals. §4.8.2 and §4.8.3 are the beginning of that data — the
first entry in a baseline that Lehman's third law
(`11-maintenance-evolution.md` §11.4) says is what eventually makes effort
predictable. Its most useful content is not the total but the finding that
implementation was over-weighted by a factor of roughly four while deployment was
under-weighted by nearly five.

Magnitude of Relative Error will be computed as `MRE = |Actual − Estimated| / Actual`,
and the result — favourable or not — reported as the closure of the estimation process
described in §4.1.
