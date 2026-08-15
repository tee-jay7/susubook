# 6. Project Scope Definition

> Required by examination Part A §3.7 — "Define the scope of the system to be completed
> within the 48-hour period." This scope is a **consequence** of the estimation in
> `05-effort-estimation.md`, not a precursor to it.

---

## 6.1 How this scope was arrived at

1. All 38 functional requirements were specified without regard to the time budget
   (`03-requirements.md`).
2. They were MoSCoW-prioritised against a single test: *does this protect or make
   verifiable the client's funds?* (§3.6).
3. The Must subset was sized at 157 adjusted function points and estimated at
   **1,857 person-hours** by COCOMO, and at **24.5 hours** by PERT bottom-up
   (`05-effort-estimation.md`).
4. PERT's 24.5 hours exceeded the 20-hour implementation allocation by 23%, and the Cone
   of Uncertainty's upper bound (49 hours) would consume the entire examination window.
5. **4.1 hours of implementation quality** were therefore removed in advance, in areas
   that do not touch BR-01 or BR-02, giving a 20.4-hour plan.
6. Change request **CR-001** subsequently added QR-based client identification at +0.92 h,
   taking the plan to **21.3 hours against the 20-hour allocation — a 6.4% overrun,
   deliberately accepted and logged** rather than absorbed by manufacturing further cuts.

The scope below is the output of that process.

## 6.2 In scope — will be built and deployed

| Area | Delivered capability | FRs |
|---|---|---|
| **Authentication & authorisation** | Login with hashed passwords, four roles, server-side route authorisation, collector restricted to own clients, session timeout | FR-01…05 |
| **Client management** | Enrol client with daily rate, assign to collector, list clients | FR-06…08 |
| **Contribution cycles** | Auto-open 31-day cycle on enrolment and after payout; maturity transition | FR-10 |
| **Contribution recording** | Record contribution with full validation — duplicate, date range, future date, closed cycle, rate multiple | FR-11…14 |
| **Digital susu card** | 31-day grid showing paid / missed / pending; computed days paid, total, projected payout | FR-16, FR-17 |
| **Payout** | Commission computation, zero-payout edge case, supervisor release, double-payout prevention | FR-18…21 |
| **Reconciliation** | Daily route sheet, remittance declaration, variance computation, supervisor variance list | FR-23…26 |
| **Client transparency** | Client login showing every contribution with amount, date, time, recording collector and reference; balance and projected payout | FR-28…30 |
| **Audit** | Append-only audit log of every state change; reversal instead of edit or delete | FR-32, FR-33 |
| **Client identification** *(CR-001)* | Opaque UUID public reference per client; printable QR card encoding the contribution URL; scan-to-collect via the phone's native camera | FR-39, FR-40 |
| **Client notification** *(CR-002)* | SMS to the client when a contribution is recorded, carrying amount, date, collector and reference. Recipients restricted to a configured allowlist; disabled entirely without an API key | FR-31 |

**30 functional requirements · 10 non-functional requirements.**

> FR-39 and FR-40 entered scope after the baseline, under CR-001. They are **Should**
> priority: if Phase 3 runs behind they are the first work abandoned, costing no Must
> requirement. The opaque-reference rule BR-R14 is retained either way, being a security
> improvement independent of the QR feature.

## 6.3 Reduced in quality — built, but knowingly below standard

These are delivered but deliberately degraded to recover the 4.1 hours. Each is a
technical debt entry, not an omission.

| Area | Delivered as | Full implementation would be | Debt ID |
|---|---|---|---|
| Schema management | `create_all()` plus seed script | Alembic versioned migrations | TD-01 |
| Styling | Tailwind via CDN, minimal custom CSS | Built and purged stylesheet | TD-02 |
| Client list | Plain table | Search, filter and pagination | TD-03 |
| Correction workflow | Minimal supervisor-only reversal form | Guided correction with reason codes | TD-04 |
| Route sheet | Static list | Filtered to "not yet collected", ordered by route | TD-05 † |
| Interaction model | HTMX on three key interactions, full page loads elsewhere | Consistent partial updates throughout | TD-06 |

FR-08 and FR-23 are therefore **partially** satisfied, and are reported as such in
`09-testing.md` rather than claimed as complete.

† **TD-05 is partially mitigated by CR-001.** QR scanning bypasses the route sheet for the
common case, so the degraded static list is exercised far less than originally assumed. The
debt is retained at reduced impact rather than closed, because the fallback path still
matters whenever a card is lost, damaged or left at home.

## 6.4 Out of scope — specified but not built

| Deferred | Priority | Why | Where it goes |
|---|---|---|---|
| FR-09 Client reassignment | Should | Not needed to demonstrate the core loop | Evolution plan |
| FR-15 Catch-up contribution | Should | Real and common, but the allocation logic is a meaningful build | Evolution plan |
| FR-22 Early withdrawal | Should | Requires an approval workflow beyond the core cycle | Evolution plan |
| FR-27 Variance resolution notes | Could | Detection is the value; resolution workflow is secondary | Evolution plan |
| FR-34 Audit trail viewer | Should | Log is written and complete; only the UI is deferred | Evolution plan |
| FR-35 User administration UI | Should | Accounts seeded directly; no UI within budget | Evolution plan |
| FR-36 Configurable defaults | Could | Cycle length and commission are constants for now | Evolution plan |
| FR-37 Supervisor dashboard | Could | Variance list carries the essential signal | Evolution plan |
| FR-38 CSV export | Could | Not required to demonstrate any principle | Evolution plan |

## 6.5 Explicitly excluded from the product vision

Not deferred — outside what this system is:

- **Mobile money / bank integration** — no merchant credentials obtainable (CO-05). SusuBook records cash movement; it does not effect it. Note that this is not merely a missing integration: client self-payment would remove the collector the entire system is built around, and is analysed as a strategic question in `11-maintenance-evolution.md` §11.8.1 rather than carried as a backlog item.
- **Variable contribution amounts** — the fixed daily rate is what makes the susu card, days-paid and the one-day commission coherent. Relaxing it replaces a card of days with a ledger of amounts (§11.8.2).
- **Offline operation** — a genuine field requirement given mobile-data coverage, but a service worker and conflict-resolved sync is a project in itself.
- **Multi-institution tenancy** — the data model assumes one institution.
- **Native mobile applications** — a responsive web application meets CO-07 at a fraction of the cost.

## 6.6 What protects this scope

The four items below were ring-fenced during the cut and are delivered at full quality,
because they are the reason the system exists:

| Protected | Hours | Carries |
|---|---|---|
| Domain layer with all business rules BR-R1…R13 | 2.58 | Correctness of every computation |
| Contribution recording with complete validation | 2.58 | BR-01 — prevention of under-recording |
| Append-only audit log | 1.08 | BR-05 — non-repudiation |
| Client self-service views | 1.08 | BR-02 — the independent client record |

If the schedule slips further, quality is reduced elsewhere again. These four are not
available to be cut, because without them the system no longer addresses the problem in
`01-problem-definition.md`.

## 6.7 Definition of Done

A requirement counts as delivered only when all of the following hold:

1. The business rule is implemented in the domain layer and unit-tested.
2. The route enforces role-based authorisation server-side.
3. Input is validated and errors are returned to the user intelligibly.
4. The state change is written to the audit log.
5. A test case exists in `09-testing.md` with a recorded actual result.
6. It works against the deployed instance, not only locally.

Anything falling short of all six is reported as partial in the testing document.
