# 14. Limitations, Conclusion and References

> Examination document §17, §18 and §19.

---

# 17. Limitations

Stated as limitations of the delivered system and of the process that produced
it. Anything already reported as satisfied elsewhere is not repeated here;
anything below is a genuine shortfall.

## 17.1 Requirements and validation

**No primary stakeholder elicitation was conducted.** No collector, client,
supervisor or branch officer was interviewed. Requirements were derived from
analysis of a well-documented manual process, and every point where a real
stakeholder would have been consulted is recorded as a numbered assumption
(§2.5). This is the most significant limitation of the requirements work, and it
was declared at the time rather than discovered afterwards.

**Assumption A5 is unvalidated and the value proposition rests on it.** A5 holds
that clients can reach a mobile web page. If false, the client-transparency
feature — the reason the system exists — does not reach the people it is for. The
mitigation (SMS notification, FR-31) is excluded from this release by the same
constraints that make A5 risky: no paid gateway.

**User acceptance testing was not carried out.** Nine UAT scenarios are prepared
(§9.9) and none has been executed with an independent participant. The 55 system
tests exercise complete journeys but were written by the developer, and
presenting them as UAT would misrepresent what they establish.

## 17.2 Verification gaps

| Requirement | Status | Why |
|---|---|---|
| **NFR-01** performance | **Not met** | Measured first render exceeds 1.1 s on a *good* connection against a 2 s budget specified for 3G (§12.6) |
| **NFR-02** ≤3 interactions | **Unverified** | Design achieves two by inspection; never measured with a participant |
| **NFR-08** accessibility | **Partial** | Shape-and-text encoding and 44 px targets implemented; no contrast audit, no screen-reader test, no outdoor-light trial |
| **FR-08** client list | **Partial** | List renders; search and pagination not implemented (TD-03) |
| **FR-23** route sheet | **Partial** | Renders with status; not filtered or route-ordered (TD-05) |

**No testing on real devices or real networks.** All measurement was from a
desktop browser on a fixed connection. The target user is on a low-end Android
handset over mobile data, and that configuration was never tested.

**No one has printed a QR card and scanned it with a phone.** TC-QR verifies the
card renders and the route resolves and authorises correctly. The optical read
off paper — the actual interaction — is untested.

**No load, concurrency, penetration or dependency-vulnerability testing.**

## 17.3 Security

Three debt items are classified **Critical** and remain open (§8.4):

- **TD-14** — no login rate limiting or lockout. Failed attempts are audited, so
  an attack is visible afterwards; nothing prevents one.
- **TD-15** — the collector sets the client's initial password and there is no
  forced change, so a collector can sign in as their client. This weakens the
  independence the system is built to provide.
- **TD-09** — the audit log is append-only by application convention, not by
  database permission.

**The system is not fit to hold real client money until these are closed.** That
is a statement about this release, not a hypothetical.

## 17.4 Scope

Deliberately excluded, with reasons in §6.5: mobile money and bank integration,
offline operation, multi-institution tenancy, native mobile applications. Ten
specified requirements were deferred (§6.4).

Scope was reduced against the estimate before implementation began, and six areas
were knowingly delivered below standard (TD-01…TD-06). The system demonstrates
the lifecycle; it is not a production deployment.

## 17.5 Deployment

**Region.** `us-central1` sits roughly 150–200 ms from Ghana, and measurement
shows that latency dominating every request (§12.6). It was chosen for Compute
Engine free-tier eligibility, not for the users.

**Cold start.** 3.3 s on the first request after idle.

**No migrations** (TD-01), so schema changes require manual DDL. **No structured
logging or alerting** (TD-17), so a production failure is discovered when a user
reports it.

## 17.6 Process

**Effort was not instrumented.** Actuals are reconstructed from commit timestamps
rather than recorded as work occurred, so per-task figures could not be produced
and the effort estimate could not be validated against measured effort (§4.9).
The phase-level distribution finding survives; the magnitude comparison does not.

**Single developer, single estimator.** No Delphi convergence, no independent
function point recount, no code review by a second person. Constraints ES-01 to
ES-04 record the consequences.

## 17.7 Documentation

**Referencing was retrofitted.** Sources are cited in §19 below, but they were
assembled at the end rather than recorded as the work drew on them. One
assumption — AS-01, the 30 LOC per function point used to convert function points
to size — is flagged in §19.6 as requiring verification before submission,
because the specific published table it came from was never recorded.

---

# 18. Conclusion

## 18.1 What was built

A functional, deployed web application that replaces the paper susu card with a
record both the client and the collector can see and neither can silently alter.
Thirty functional requirements across four roles, 3,433 lines of application
code, 226 automated tests at 97% coverage, live at
https://susubook-fdtbppd7sq-uc.a.run.app.

## 18.2 Against the objectives

| | Objective | Outcome |
|---|---|---|
| **O1** | Elicit, analyse, prioritise requirements; produce an SRS | **Met** — 40 requirements, MoSCoW-prioritised, traceability matrix, IEEE 830 SRS. Limited by the absence of primary elicitation (§17.1) |
| **O2** | Estimate effort and use it to define achievable scope | **Met** — FPA → COCOMO → PERT triangulated; the estimate exposed a 23% over-commitment *before* implementation and drove the scope decision |
| **O3** | Design a maintainable layered architecture with UML | **Met** — four layers, eight UML artefacts, SOLID applied at named sites |
| **O4** | Implement the prioritised requirements as a deployed application | **Met** — deployed, with authentication, role-based authorisation, validation and an append-only audit trail |
| **O5** | Verify through unit, integration, system and acceptance testing | **Partially met** — 226 tests across three levels; **UAT not conducted** |
| **O6** | Identify, classify and document technical debt with a repayment plan | **Met** — 17 items, each with cause, impact, priority and resolution; 13 identified before the code carrying them existed |
| **O7** | Define maintenance and evolution grounded in theory | **Met** — four maintenance categories, Lehman's eight laws applied individually, six-release roadmap |

Six of seven met; O5 partially, and the shortfall is named rather than glossed.

## 18.3 What the project demonstrates

**Estimation is worth doing even when the number is wrong.** COCOMO put this at
1,969 person-hours against a 48-hour window — a ratio of no operational use. Its
value was not the figure but what the figure forced: an explicit scope decision,
taken in advance, with a stated basis. The estimate also generated the technical
debt register, because every quality reduction made to fit the budget became a
debt entry with a known cause. The two sections that carry the most marks turned
out to be the same decision documented twice.

**Debt taken knowingly behaves differently from debt taken accidentally.** Of 17
items, 13 were identified before the code carrying them existed. All 13 landed in
the *acceptable* or *scheduled* bands. All three **Critical** items were
discovered later — during implementation and testing — and none was a deliberate
trade-off. The dangerous debt was the debt nobody decided to take on.

**Architecture is a scheduling decision.** Keeping the domain layer free of Flask
and SQLAlchemy reads as purity. It was the reason 129 unit tests run in 0.34
seconds with no database, and therefore the reason a real test suite was
affordable at all inside the window.

**Some defects are only reachable by a person.** DEF-06 — a route row marked
"Paid" above a total still reading GHS 0.00 — was found by clicking through the
interface, not by any of the 226 tests, and could not have been: every test
asserted the *response* to a request and none asserted the state of the page
afterwards. DEF-08 was similar in kind, invisible outside a real deployment.
Lehman's eighth law describes evolution as a feedback system; this project
produced its own evidence for it rather than quoting the law.

**Honest reporting is more useful than favourable reporting.** NFR-01 is recorded
as not met, with arithmetic. UAT is recorded as not done. Two of the developer's
own test assumptions were found wrong and corrected rather than adjusted until
they passed. A flaky security test was fixed and then demonstrated stable over
five runs rather than assumed. Each of these could have been quietly omitted, and
the document would have been weaker for it — a claim nobody can check is worth
less than a limitation anyone can verify.

## 18.4 If the work continued

The order is already fixed by §11.6: migrations, rate limiting, forced password
change, audit enforcement — 8 to 11 hours — before the system touches real client
money. Then SMS notification, which mitigates the one assumption the value
proposition depends on.

The system as delivered demonstrates that the problem is solvable. It does not
yet solve it for anyone.

---

# 19. References

## 19.1 Course materials

1. Mensah, S. (2025) *CSCD602 Session 1: Introduction to Software Engineering*. Department of Computer Science, University of Ghana.
2. Mensah, S. (2025) *CSCD602 Session 2: Requirements Engineering*. Department of Computer Science, University of Ghana.
3. Mensah, S. (2025) *CSCD602 Session 3: Technical Debt*. Department of Computer Science, University of Ghana.
4. Mensah, S. (2025) *CSCD602 Session 4: Program Evolution Dynamics*. Department of Computer Science, University of Ghana.
5. Mensah, S. (2025) *CSCD602 Session 5: Software Design and Architecture*. Department of Computer Science, University of Ghana.
6. Mensah, S. (2025) *CSCD602 Session 6: Software Effort Estimation*. Department of Computer Science, University of Ghana.
7. Mensah, S. (2025) *CSCD602 Advanced Software Engineering: Course Syllabus, First Semester 2025/2026*. Department of Computer Science, University of Ghana.

## 19.2 Books

8. Sommerville, I. (2016) *Software Engineering*. 10th edn. Harlow: Pearson Education.
9. Farley, D. (2021) *Modern Software Engineering: Doing What Works to Build Better Software Faster*. Boston: Addison-Wesley.
10. Tsui, F., Karam, O. and Bernal, B. (2022) *Essentials of Software Engineering*. Burlington: Jones & Bartlett Learning.
11. Boehm, B.W. (1981) *Software Engineering Economics*. Englewood Cliffs: Prentice Hall.
12. Boehm, B.W., Abts, C., Brown, A.W., Chulani, S., Clark, B.K., Horowitz, E., Madachy, R., Reifer, D.J. and Steece, B. (2000) *Software Cost Estimation with COCOMO II*. Upper Saddle River: Prentice Hall.
13. Brooks, F.P. (1975) *The Mythical Man-Month: Essays on Software Engineering*. Reading: Addison-Wesley.
14. Lehman, M.M. and Belady, L.A. (1985) *Program Evolution: Processes of Software Change*. London: Academic Press.
15. Martin, R.C. (2003) *Agile Software Development: Principles, Patterns, and Practices*. Upper Saddle River: Prentice Hall.
16. Fowler, M. (2002) *Patterns of Enterprise Application Architecture*. Boston: Addison-Wesley.
17. Evans, E. (2003) *Domain-Driven Design: Tackling Complexity in the Heart of Software*. Boston: Addison-Wesley.
18. Gamma, E., Helm, R., Johnson, R. and Vlissides, J. (1994) *Design Patterns: Elements of Reusable Object-Oriented Software*. Reading: Addison-Wesley.

## 19.3 Papers and articles

19. Lehman, M.M. (1980) 'Programs, life cycles, and laws of software evolution', *Proceedings of the IEEE*, 68(9), pp. 1060–1076.
20. Albrecht, A.J. (1979) 'Measuring application development productivity', *Proceedings of the IBM Applications Development Symposium*, pp. 83–92.
21. Cunningham, W. (1992) 'The WyCash portfolio management system', *OOPSLA '92 Experience Report*.
22. Brooke, J. (1996) 'SUS: A quick and dirty usability scale', in Jordan, P.W. et al. (eds) *Usability Evaluation in Industry*. London: Taylor & Francis, pp. 189–194.

## 19.4 Online sources

23. Fowler, M. (2009) *TechnicalDebtQuadrant*. Available at: https://martinfowler.com/bliki/TechnicalDebtQuadrant.html
24. Nielsen, J. (2000) *Why You Only Need to Test with 5 Users*. Nielsen Norman Group. Available at: https://www.nngroup.com/articles/why-you-only-need-to-test-with-5-users/
25. Wiggins, A. (2017) *The Twelve-Factor App*. Available at: https://12factor.net/
26. Google Cloud (2024) *Cloud Run documentation: Connect to a VPC network*. Available at: https://cloud.google.com/run/docs/configuring/vpc-direct-vpc

## 19.5 Standards and legislation

27. IEEE (1998) *IEEE Std 830-1998: Recommended Practice for Software Requirements Specifications*. New York: Institute of Electrical and Electronics Engineers.
28. ISO (2019) *ISO 9241-210:2019 Ergonomics of human-system interaction — Part 210: Human-centred design for interactive systems*. Geneva: International Organization for Standardization.
29. W3C (2018) *Web Content Accessibility Guidelines (WCAG) 2.1*. Available at: https://www.w3.org/TR/WCAG21/
30. Republic of Ghana (2012) *Data Protection Act, 2012 (Act 843)*. Accra: Ghana Publishing Company.

## 19.6 Note on assumption AS-01

**This reference is incomplete and must be resolved before submission.**

§4.3.1 converts function points to source size at **30 lines of code per function
point** for Python with an ORM and server-side templating. That figure was taken
as a published average for the language class, but **the specific table it came
from was not recorded at the time**, and it is not cited here because citing a
source that was not consulted would be worse than admitting the gap.

The figure is not incidental — it drives the KLOC input to COCOMO and therefore
every effort figure in §4.3. Its unreliability is partly demonstrated by the
project's own result: measured productivity was **20.7 LOC/FP** (§4.8.1), below
even the optimistic bound of the sensitivity analysis.

**Action required:** consult a published language-productivity table — Jones's
language levels or the QSM function point languages table are the usual sources —
and either cite it here or restate AS-01 as an unsourced estimate. The
sensitivity analysis in §4.3.4 already shows the conclusion holds across
25–40 LOC/FP, so the argument does not depend on the resolution.

## 19.7 Software and libraries acknowledged

Per examination Rule 6.

| Component | Version | Licence | Use |
|---|---|---|---|
| Python | 3.12 | PSF | Language |
| Flask | ≥3.0 | BSD-3-Clause | Web framework |
| Jinja2 | ≥3.1 | BSD-3-Clause | Templating |
| Flask-WTF | ≥1.2 | BSD-3-Clause | CSRF protection |
| SQLAlchemy | ≥2.0 | MIT | ORM |
| psycopg | ≥3.1 | LGPL-3.0 | PostgreSQL driver |
| PostgreSQL | 16 | PostgreSQL Licence | Database |
| argon2-cffi | ≥23.1 | MIT | Password hashing |
| segno | ≥1.6 | BSD-3-Clause | QR code generation |
| python-dotenv | ≥1.0 | BSD-3-Clause | Configuration |
| gunicorn | ≥21.2 | MIT | WSGI server |
| pytest, pytest-cov | ≥8.0, ≥5.0 | MIT | Testing |
| HTMX | 1.9.12 | BSD-2-Clause | Partial page updates |
| Tailwind CSS | 3.x (CDN) | MIT | Styling |
| Docker, Docker Compose | — | Apache-2.0 | Local database, containerisation |
| Google Cloud Run, Compute Engine, Secret Manager, Artifact Registry, Cloud Build | — | Commercial (free tier) | Hosting and deployment |
| Mermaid CLI | — | MIT | UML diagram rendering |

No third-party code was copied into this project. All application source in
`app/` was written for this examination.

## 19.8 Declaration

Submitted as individual work for CSCD602, in accordance with examination Rules 1
and 13. No previously submitted academic work has been reused, so no disclosure
is required under Rule 12.

**Student:** [STUDENT NAME]
**Student ID:** [STUDENT ID]
