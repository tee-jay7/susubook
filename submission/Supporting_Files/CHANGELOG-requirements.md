# Requirements Change Log

Changes to the requirements baseline are recorded here under the formal change control
process defined in Section 3.8. Nothing is removed from or added to the
baseline silently; each entry records the request, its impact, its cost, the decision
taken and who took it.

---

## CR-001: QR-based client identification

| Field | Value |
|---|---|
| **Raised** | Phase 1 close, before Analysis & Design |
| **Raised by** | Developer |
| **Status** | **Approved and incorporated** |
| **Affects** | Section 3 (Requirements Analysis), the Software Requirements Specification, Section 4 (Software Effort Estimation), Appendix A (Project Scope Definition) |

### 1. Change request

Issue each client a printed QR code. The collector scans it to reach that client's
contribution screen directly, rather than locating the client in a list.

**Stated reason.** Collector throughput. A collector working a market may serve dozens of
clients in a morning; finding each one in a list is the dominant cost of the interaction
and works directly against NFR-02. The paper susu card is already a physical artefact the
client keeps, so a printed QR card preserves a familiar ritual rather than imposing a new
one: a user-centred design argument (Session 5) as much as an efficiency one.

### 2. Options considered

| Option | Description | PERT effort | Assessment |
|---|---|---|---|
| **A** | In-app camera scanner: `getUserMedia`, JS QR-decoding library, live viewfinder | **2.12 h** | Rejected, see Section 3 |
| **B** | **QR encodes a URL; collector uses the phone's native camera app, which opens the client's contribution screen** | **0.92 h** | **Selected** |
| C | Opaque public references only, QR deferred to evolution | ~0.1 h | Rejected, forgoes the throughput benefit that motivated the request |
| D | Reject entirely | 0 h | Rejected, the benefit is real and the cost is modest |

**Why Option B over Option A.** Option A costs 2.3× more, introduces a client-side
JavaScript dependency into a stack deliberately kept JS-light, and requires camera
permission handling. Its field reliability is also the weaker of the two: live camera
decoding on a low-end Android in strong outdoor light, aimed at a printed card subjected
to weeks of market conditions, is a meaningful failure risk (CO-07). Option B delegates
decoding to the operating system's camera application, which every current Android and iOS
device performs natively, and reduces the routine collection to **two interactions** —
better than NFR-02 requires. Both options degrade to the same fallback: the route sheet.

### 3. Impact analysis

Traced through the matrix at Section 3.7.

**Requirements added**

| ID | Requirement | Priority |
|---|---|---|
| FR-39 | The system shall assign each client an opaque, non-sequential public reference and render it as a printable QR code encoding the client's contribution URL. | Should |
| FR-40 | The system shall resolve a scanned client reference to that client's contribution screen, subject to the same authorisation as any other route. | Should |

**Business rules added**

| ID | Rule |
|---|---|
| BR-R14 | Public references exposed in URLs or QR codes shall be opaque and non-sequential (UUIDv4). Sequential database identifiers shall never appear in a URL. |
| BR-R15 | A client reference identifies; it does not authorise. Possession of a reference confers no permission; authorisation remains the collector–client assignment enforced server-side (FR-05). |

**Security analysis.** A QR code on a card carried through a public market must be assumed
to be photographable by anyone. Two consequences follow:

- *Enumeration.* A sequential identifier would let an observer derive every other client's
  reference by incrementing. BR-R14 requires UUIDv4, making references unguessable.
- *Privilege.* The reference must confer no capability. Scanning only reaches the
  contribution screen; recording a contribution still requires an authenticated collector
  to whom that client is assigned. BR-R15 states this explicitly so it is not eroded by a
  later change.
- *Data protection.* The QR encodes a URL containing an opaque reference and nothing else
 , no name, phone number, balance or rate. A photographed card leaks no personal data,
  preserving NFR-06 and Act 843 compliance.

**Requirements affected but not changed**

| Requirement | Effect |
|---|---|
| NFR-02 (three-interaction limit) | Strengthened, scan-and-confirm is two interactions |
| FR-05 (collector restricted to own clients) | Unchanged, and now load-bearing for BR-R15 |
| FR-23 (route sheet) | Unchanged, but becomes the fallback path rather than the primary one |
| NFR-06 (data minimisation) | Preserved by the opaque-reference requirement |

**Design consequence beyond the change itself.** BR-R14 applies to the whole system, not
only to QR codes. Opaque public references replace sequential identifiers in **all**
externally visible URLs, closing an insecure-direct-object-reference exposure that existed
in the original design. This is a security improvement to parts of the system the change
request did not touch.

**Technical debt effect.** TD-05 (route sheet reduced to a static list) is **partially
mitigated**: scanning bypasses the route sheet for the common case, so the degraded list is
exercised less. TD-05 is retained at reduced impact rather than closed, because the
fallback path still matters when a card is lost or damaged.

### 4. Cost, schedule and risk assessment

**Function point impact**

| | Component | Complexity | FP |
|---|---|---|---|
| Added | Printable client QR card (External Output) | Average | 5 |
| Added | Client reference resolution (External Inquiry) | Simple | 3 |
| | | **Subtotal** | **+8 UFP** |

| Measure | Before | After | Δ |
|---|---|---|---|
| UFP (Must scope) | 143 | 151 | +8 |
| AFP (Must scope, VAF 1.10) | 157 | 166 | +9 |
| KLOC | 4.71 | 4.98 | +0.27 |
| COCOMO effort | 12.2 PM | 13.0 PM | +0.8 PM |
| COCOMO person-hours | 1,857 | 1,969 | +112 |

**PERT impact**

New WBS task 17 — QR issuance and scan-to-collect: O = 0.5, M = 0.85, P = 1.6 →
**E = 0.92 h**, σ = 0.18 h.

| Measure | Before | After |
|---|---|---|
| Total expected effort | 24.46 h | **25.38 h** |
| Total σ | 1.22 h | 1.24 h |
| 68% confidence range | 23.2 – 25.7 h | 24.1 – 26.6 h |
| Cone of Uncertainty (0.5×–2×) | 12.2 – 48.9 h | 12.7 – 50.7 h |
| After the 4.1 h of agreed cuts | 20.4 h | **21.3 h** |
| Against the 20 h allocation | +2% | **+6.4%** |

**Risk assessment**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Native camera app does not detect the QR on some device | Low | Low | Route sheet fallback is unchanged and always available |
| Printed card damaged or lost in market conditions | Medium | Low | Fallback to route sheet; reference re-issuance deferred to evolution |
| Task overruns its 0.92 h estimate | Medium | Medium | Feature is Should-priority, it is abandoned if Phase 3 runs late, without affecting any Must requirement |
| Scope creep toward a full in-app scanner | Medium | Medium | Option A is explicitly recorded as rejected here, with its cost |

### 5. Decision

**Approved**, with the schedule overrun accepted and recorded rather than absorbed.

The implementation plan now stands at **21.3 hours against a 20-hour allocation, a 6.4%
overrun**, deliberately accepted. The alternative was to manufacture a further 1.3 hours of
quality cuts so the arithmetic landed on exactly 20.0; that would have produced a tidier
number and a less honest plan. Session 6 identifies external schedule pressure as a
recognised source of estimate distortion, and adjusting an estimate to fit a predetermined
budget is precisely that distortion. The overrun is therefore carried openly and tracked
against actuals in Section 4.8.

**Containment.** FR-39 and FR-40 are **Should**, not Must. If Phase 3 runs behind, this is
the first work abandoned, and abandoning it costs no Must requirement. BR-R14 (opaque
references) is retained regardless of whether the QR feature ships, because it is a
security improvement independent of it.

With no Change Control Board available on an individual assessment, the decision was taken
by the developer and recorded here with its full justification so that it is reviewable —
as specified in Section 3.8 step 4.

### 6. Implementation record

- [x] Section 3 (Requirements Analysis) — FR-39, FR-40 added; MoSCoW counts updated; traceability matrix extended
- [x] the Software Requirements Specification — BR-R14, BR-R15 added; domain model updated with `public_ref`; UC-03 alternate flow 3b added; definitions extended
- [x] Section 4 (Software Effort Estimation) — WBS task 17 added; FPA, COCOMO and PERT figures revised; overrun recorded
- [x] Appendix A (Project Scope Definition) — QR capability added to in-scope table; overrun recorded
- [ ] Implementation in Phase 3
- [ ] Test cases TC-QR-01…03 in Section 9 (Testing and Quality Assurance)

---

## CR-002: SMS notification of recorded contributions

| Field | Value |
|---|---|
| **Raised** | Phase 6, after the submission package was first assembled |
| **Raised by** | Developer |
| **Status** | **Approved and incorporated** |
| **Affects** | Section 3 (Requirements Analysis), Appendix A (Project Scope Definition), Section 8 (Technical Debt), Section 9 (Testing and Quality Assurance), Section 11 (Maintenance and Future Evolution), Section 12 (Deployment), the User Manual, Sections 17–19 (Limitations, Conclusion, References) |

### 1. Change request

Send a client an SMS when a contribution is recorded against them, so they learn
of it without signing in.

**Stated reason.** FR-31 was classified **Won't (this release)** because it needs
a paid SMS gateway (CO-04) with an account lead time that did not fit CO-01. An
Arkesel account subsequently became available, removing both obstacles.

**Why it matters more than an ordinary feature.** Assumption **A5** holds that
clients can reach a mobile web page. The entire value proposition, an
independent record the client controls, depends on it, and A5 is unvalidated
(Section 2.5, Section 17.1). SMS is the stated mitigation: a text message reaches a handset
that cannot open a browser. This is the highest-value deferred item in the
project, and it was ranked first in the evolution roadmap for that reason.

### 2. Options considered

| Option | Description | Assessment |
|---|---|---|
| **A** | Full integration, sending restricted to an allowlist of numbers the developer controls | **Selected** |
| B | Build the gateway seam and wire it, with a logging-only adapter | Rejected, demonstrates the architecture but leaves A5 unmitigated, which was the point |
| C | Full integration, re-seeding the demonstration data with numbers under the developer's control | Rejected, changes a dataset already documented and screenshotted, for no additional safety over A |
| D | Leave deferred | Rejected, the blocking constraint no longer applies |

### 3. Impact analysis

**Requirement changed**

| ID | Before | After |
|---|---|---|
| FR-31 | The system shall notify a Client by SMS on each recorded contribution — **Won't (this release)** | Unchanged text — **Should** |

**A safety risk identified during analysis, and the reason for the allowlist.**

The demonstration dataset uses **valid-format Ghanaian mobile numbers**:
`0201000201` is a well-formed Telecel number and `0244000101` a well-formed MTN
number. These were invented for seed data, but nothing prevents them belonging to
real subscribers.

An unguarded rollout would therefore have sent a text message to a real stranger
**every time an examiner recorded a collection**, repeatedly, at the project's
expense, to people with no relationship to the system. That is a real harm, not
an inconvenience.

The mitigation is an **allowlist that defaults to empty**. No recipient is
permitted unless explicitly configured. Tests assert that every number in the
seed dataset is refused by a default-configured service, so the guard cannot be
removed without a test failing.

**Design constraints adopted**

| Constraint | Reason |
|---|---|
| Notification dispatched **after** the database commit | The contribution is the record of truth and must be durable before anything else is attempted |
| Every failure swallowed and logged, never raised | A notification failure must not be able to fail, delay or roll back a collection |
| Delivery on a daemon thread | A slow gateway must not stall the collector's route sheet (NFR-01, NFR-02) |
| Gateway behind a `Protocol`, defaulting to a no-op | Tests and local development can never send a message; a missing API key produces silence, not an exception |
| Message carries no link, credential or balance beyond the cycle total | A text is readable by anyone holding the handset |
| Every dispatch audited (`SMS_DISPATCHED`) | A later dispute about notification has an answer (NFR-09) |

**Architectural note.** `SmsGateway` is the second worked example of the
dependency inversion the design claims (Section 7.12): the service depends on a
Protocol, production injects the Arkesel adapter, tests inject a null adapter,
and neither knows the difference. The seam existed before the feature did.

### 4. Cost and risk

| Item | Estimate |
|---|---|
| Gateway Protocol, null adapter, service, message construction | 0.6 h |
| Arkesel adapter (stdlib `urllib`, no new dependency) | 0.4 h |
| Configuration, Secret Manager, deployment wiring | 0.4 h |
| Tests (27 unit, 3 system) | 0.5 h |
| Documentation | 0.6 h |
| **Total** | **~2.5 h** |

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Message reaches a real stranger | **Was high** | **High** | Allowlist defaults to empty; asserted by test against every seed number |
| API key exposure | Low | High | Secret Manager, never logged, never in the repository |
| Gateway latency degrades the route sheet | Medium | Medium | Dispatch on a daemon thread, after commit |
| Provider API changes | Medium | Low | Endpoint and sender configurable; failure is silent and logged |
| Cost of messages | Low | Low | Allowlist bounds volume to numbers the developer controls |

### 5. Decision

**Approved.** The blocking constraint (no gateway) no longer applies, and the
requirement mitigates the project's most significant unvalidated assumption.

Classified **Should**, not **Must**: the system is fully functional without it,
and it must remain abandonable if the gateway proves unreliable.

**FR-31 is delivered but not fully realised.** With the allowlist bounded to
developer-controlled numbers, real clients still do not receive messages.
Assumption A5 is therefore **mitigated in mechanism but not yet in practice** —
recorded at Section 17.1 rather than claimed as closed.

### 6. Implementation record

- [x] `app/services/notifications.py` — Protocol, null adapter, service, allowlist
- [x] `app/infrastructure/arkesel.py` — Arkesel v2 adapter
- [x] `app/config.py`, `app/__init__.py`, `app/services/container.py`, wiring
- [x] `app/services/collection.py`, dispatch after commit, audited
- [x] `deploy/deploy.sh`, optional secret, allowlist environment variable
- [x] 27 unit tests, 3 system tests
- [x] Documentation updated across eight files
- [ ] Live verification with a real handset, pending an allowlisted number
