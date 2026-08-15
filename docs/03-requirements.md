# 3. Requirements Analysis

Requirements are classified using the taxonomy set out in Session 2 [2] and in
Sommerville [8]: business, stakeholder, functional, non-functional, and
constraints.

---

## 3.1 Business requirements (why the system is being built)

| ID | Requirement |
|---|---|
| BR-01 | Reduce loss of client funds through under-recording or misappropriation of field collections. |
| BR-02 | Give every client an independent, verifiable record of their own contributions. |
| BR-03 | Enable same-day reconciliation of field collections against cash remitted to the branch. |
| BR-04 | Eliminate manual arithmetic errors in payout computation. |
| BR-05 | Produce an auditable trail of client funds sufficient for institutional and regulatory oversight. |
| BR-06 | Increase saver confidence in the collector model, supporting client retention and growth. |

## 3.2 Stakeholder requirements (what each group expects)

| ID | Stakeholder | Requirement |
|---|---|---|
| SR-01 | Client | See every contribution recorded against me, with date, amount and recording officer. |
| SR-02 | Client | Know my current balance and what I will receive at maturity, without asking anyone. |
| SR-03 | Client | Be confident that a recorded entry cannot later be silently removed. |
| SR-04 | Collector | Record a client's daily contribution in a few seconds on a phone. |
| SR-05 | Collector | See my route for today and who I have not yet collected from. |
| SR-06 | Collector | Correct an honest mistake without needing a developer. |
| SR-07 | Supervisor | Compare what my collectors recorded today against what they remitted today. |
| SR-08 | Supervisor | Be alerted to a variance on the day it occurs. |
| SR-09 | Supervisor | Authorise payouts and early withdrawals. |
| SR-10 | Administrator | Create, suspend and assign roles to users. |
| SR-11 | Administrator | Ensure a collector can access only their own clients. |

## 3.3 Functional requirements (what the system must do)

### Authentication and authorisation

| ID | Requirement | Priority |
|---|---|---|
| FR-01 | The system shall authenticate users with a phone number or email and a password. | Must |
| FR-02 | The system shall support four roles (Client, Collector, Supervisor, Administrator) and enforce role-based access on every route. | Must |
| FR-03 | The system shall store passwords only as salted one-way hashes. | Must |
| FR-04 | The system shall terminate a session on logout and after a period of inactivity. | Must |
| FR-05 | The system shall restrict a Collector to viewing and modifying only clients assigned to them. | Must |

### Client and enrolment management

| ID | Requirement | Priority |
|---|---|---|
| FR-06 | A Collector shall enrol a client, capturing name, phone number, business type, market/location and agreed daily contribution amount. | Must |
| FR-07 | The system shall assign each client to exactly one Collector at a time. | Must |
| FR-08 | A Collector shall view and search their own client list. | Must |
| FR-09 | A Supervisor shall reassign a client from one Collector to another, recording the change in the audit log. | Should |

### Contribution cycles and collection

| ID | Requirement | Priority |
|---|---|---|
| FR-10 | The system shall open a contribution cycle of the configured length (default 31 days) when a client is enrolled and again after each payout. | Must |
| FR-11 | A Collector shall record a contribution against a client for a given date. | Must |
| FR-12 | The system shall reject a second contribution recorded for the same client on the same date. | Must |
| FR-13 | The system shall reject a contribution dated in the future or before the cycle start date. | Must |
| FR-14 | The system shall reject a contribution recorded against a cycle that is already closed or paid out. | Must |
| FR-15 | The system shall accept a catch-up contribution covering several unpaid days, allocating it to specific dates. | Should |
| FR-16 | The system shall display a digital susu card showing each day of the cycle as paid, missed or pending. | Must |
| FR-17 | The system shall compute, for any cycle, the days paid, days missed, total collected and projected payout. | Must |

### Payout

| ID | Requirement | Priority |
|---|---|---|
| FR-18 | At cycle maturity the system shall compute the payout as total collected less one day's contribution retained as commission. | Must |
| FR-19 | The system shall retain the whole balance as commission and pay zero where the total collected does not exceed one day's contribution. | Must |
| FR-20 | A Supervisor shall release a matured payout, closing the cycle and opening the next. | Must |
| FR-21 | The system shall reject any attempt to release a payout for a cycle already paid out. | Must |
| FR-22 | A Client shall request an early withdrawal before maturity, subject to Supervisor approval. | Should |

### Reconciliation and oversight

| ID | Requirement | Priority |
|---|---|---|
| FR-23 | The system shall produce a daily collection sheet per Collector listing clients due and their collection status. | Must |
| FR-24 | A Collector shall declare the total cash remitted to the branch for a given day. | Must |
| FR-25 | The system shall compute the variance between contributions recorded and cash declared for each Collector each day. | Must |
| FR-26 | The system shall present a Supervisor with all non-zero variances for the current day. | Must |
| FR-27 | A Supervisor shall record the resolution of a variance, with a note. | Could |

### Client transparency

| ID | Requirement | Priority |
|---|---|---|
| FR-28 | A Client shall log in and view their own digital card, showing every contribution with amount, date, time recorded and recording Collector. | Must |
| FR-29 | A Client shall view their running balance, cycle maturity date and projected net payout. | Must |
| FR-30 | The system shall issue a unique reference for every recorded contribution. | Must |
| FR-31 | The system shall notify a Client by SMS on each recorded contribution. | Should *(CR-002)* |

### Audit and correction

| ID | Requirement | Priority |
|---|---|---|
| FR-32 | The system shall record every contribution, payout, reassignment and adjustment in an append-only audit log with actor, action, target and timestamp. | Must |
| FR-33 | The system shall never edit or delete a contribution in place; a correction shall be recorded as a new linked reversal entry. | Must |
| FR-34 | A Supervisor shall view the audit trail for any client or collector. | Should |

### Administration

| ID | Requirement | Priority |
|---|---|---|
| FR-35 | An Administrator shall create, suspend and assign roles to user accounts. | Should |
| FR-36 | An Administrator shall configure institutional defaults, cycle length and commission policy. | Could |
| FR-37 | The system shall provide a Supervisor dashboard summarising active clients, today's collections and outstanding variances. | Could |
| FR-38 | The system shall export a collector's cycle report as CSV. | Could |

### Credential management *(added while repaying TD-15)*

These describe capability the system now has. They arose from repaying a
documented debt rather than from a change request, and are recorded here so the
specification matches the delivered system.

| ID | Requirement | Priority |
|---|---|---|
| FR-41 | The system shall require a client to replace the password set for them at enrolment before displaying any of their record. | Must |
| FR-42 | The system shall allow a user to reset a forgotten password by a single-use code sent to their registered phone number, expiring after 10 minutes. | Should |

### Client identification *(added by CR-001)*

| ID | Requirement | Priority |
|---|---|---|
| FR-39 | The system shall assign each client an opaque, non-sequential public reference and render it as a printable QR code encoding the client's contribution URL. | Should |
| FR-40 | The system shall resolve a scanned client reference to that client's contribution screen, subject to the same authorisation as any other route. | Should |

## 3.4 Non-functional requirements (how well it must perform)

| ID | Category | Requirement | Verification |
|---|---|---|---|
| NFR-01 | Performance | Any page shall render within 2 seconds on a 3G-class mobile connection. | Timed page-load test on throttled connection |
| NFR-02 | Usability | A Collector shall be able to record a routine contribution in no more than three interactions from the route sheet. | Task-based usability test, interaction count |
| NFR-03 | Security | Authorisation shall be enforced server-side on every route; passwords hashed; CSRF protection on all state-changing forms. | Security test cases, forced-browsing attempts |
| NFR-04 | Data integrity | All monetary values shall be stored and computed as integer pesewas; floating-point arithmetic shall not be used for money. | Unit tests, schema inspection |
| NFR-05 | Availability | The deployed system shall be available during collection hours (06:00–20:00 GMT). | Deployment verification |
| NFR-06 | Compliance | Only name, phone, business type and location shall be stored as client personal data, per the Data Protection Act 2012 (Act 843) [30]. | Schema review |
| NFR-07 | Maintainability | The domain layer shall have no dependency on Flask or SQLAlchemy and shall reach at least 70% unit-test coverage. | Coverage report, import inspection |
| NFR-08 | Accessibility | Interface shall meet WCAG 2.1 [29] AA contrast, use touch targets of at least 44×44 px, and remain legible in outdoor light. | Contrast audit, device check |
| NFR-09 | Auditability | Every state change shall be attributable to an authenticated user and a timestamp. | Audit log inspection |
| NFR-10 | Portability | The application shall run against the same PostgreSQL engine in development and production, configured only by environment variable. | Docker parity, deploy verification |

## 3.5 Constraints

| ID | Constraint | Source |
|---|---|---|
| CO-01 | Development must be completed within a 48-hour examination window. | Examination rules |
| CO-02 | The system must be developed by a single developer. | Examination rules (individual assessment) |
| CO-03 | The application must be deployed and publicly accessible for grading. | Examination rules 8, 9 |
| CO-04 | Hosting is limited to free-tier services. | Project resources |
| CO-05 | No integration with mobile money or banking APIs is possible, no merchant credentials are available. | Technical/commercial access |
| CO-06 | Client personal data must comply with the Data Protection Act 2012 (Act 843) [30]. | Ghanaian law |
| CO-07 | Field users operate on low-end Android phones over mobile data. | Target user context |

## 3.6 Prioritisation (MoSCoW)

Prioritisation is driven by one test: **does this requirement serve BR-01/BR-02, the
protection and verifiability of client funds?** Anything that does is a *Must*; anything
that merely improves convenience is deferred.

| Priority | Count | Requirements |
|---|---|---|
| **Must** | 29 | FR-01…08, FR-10…14, FR-16…21, FR-23…26, FR-28…30, FR-32, FR-33, FR-41 |
| **Should** | 9 | FR-09, FR-15, FR-22, FR-31, FR-34, FR-35, FR-39, FR-40, FR-42 |
| **Could** | 4 | FR-27, FR-36, FR-37, FR-38 |
| **Won't** | 0 | — |
| **Total** | **42** | FR-01 … FR-42 |

> FR-39 and FR-40 were added after the baseline was set, under change request **CR-001**
> (Appendix B). They are **Should**, so that abandoning them under
> schedule pressure costs no Must requirement.

**FR-31 was originally *Won't*, and was reinstated under CR-002.** SMS notification is the
mitigation for assumption A5, the risk that clients cannot reach a web page, and is
arguably the single most valuable feature for the real user. It was excluded because it
required a paid SMS gateway (CO-04) with an account lead time that did not fit CO-01. Once
a gateway became available that constraint no longer applied, and it was reinstated as
**Should** through the change control process (Appendix B, CR-002).

## 3.7 Requirements traceability matrix

| Business req. | Stakeholder req. | Functional req. | Verified by |
|---|---|---|---|
| BR-01 | SR-07, SR-08 | FR-23, FR-24, FR-25, FR-26 | TC-REC-01…04 |
| BR-02 | SR-01, SR-02 | FR-28, FR-29, FR-30 | TC-CLI-01…03 |
| BR-03 | SR-07 | FR-24, FR-25, FR-26 | TC-REC-02 |
| BR-04 | SR-02 | FR-17, FR-18, FR-19 | TC-PAY-01…05 |
| BR-05 | SR-03, SR-11 | FR-32, FR-33, FR-34, FR-05 | TC-AUD-01…03 |
| BR-06 | SR-01, SR-03 | FR-28, FR-32, FR-33 | UAT-01…03 |
| BR-01, BR-06 | SR-04 | FR-39, FR-40 *(CR-001)* | TC-QR-01…03 |
| BR-02 | SR-01, SR-03 | FR-41, FR-42 *(TD-15 repayment)* | TC-PWD-01…13 |
| BR-02, BR-06 | SR-01 | FR-31 *(CR-002)* | TC-SMS-01…10 |

*Test case identifiers are defined in Section 9 (Testing and Quality Assurance).*

## 3.8 Change management

Following Session 2's formal change control process, and scaled to a single-developer
project:

1. **Change request logging**, any scope change during the 48 hours is recorded as a
   dated entry in `docs/CHANGELOG-requirements.md` with the reason.
2. **Impact analysis**, the traceability matrix (§3.7) identifies which business
   requirements and test cases a change touches.
3. **Cost/schedule assessment**, the change is re-estimated against the remaining hours
   in the window.
4. **Approval**, with no Change Control Board available, the developer records the
   decision and its justification explicitly, so it is reviewable.
5. **Implementation**, design, code, tests and documentation are updated together.

Any requirement dropped after this point is recorded there rather than silently removed,
so that the delivered scope can be compared against the specified scope.

**Changes raised to date:**

- **CR-001** — QR-based client identification. Approved, adding FR-39, FR-40 and business
  rules BR-R14 and BR-R15.
- **CR-002** — SMS notification. Approved, reinstating FR-31 from *Won't* to *Should*.

See Appendix B for impact analysis, cost and decision record in each case.
