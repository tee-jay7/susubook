# 2. Stakeholder Analysis

## 2.1 Stakeholder register

| ID | Stakeholder | Type | Interest in the system | Primary concern |
|---|---|---|---|---|
| S1 | **Client (saver)** | Primary, direct user | Wants a record of their savings that they control and can verify | "Can I prove what I paid?" |
| S2 | **Susu Collector** | Primary, direct user | Records collections in the field; needs speed on a route | "Can I record a payment in seconds while standing in the market?" |
| S3 | **Field Supervisor** | Primary, direct user | Reconciles collectors' recorded collections against cash remitted | "Did the money that was recorded actually reach the branch today?" |
| S4 | **System Administrator** | Secondary, direct user | Manages accounts, roles and institutional policy | "Are the right people able to do only the right things?" |
| S5 | **Rural bank / MFI** | Secondary, indirect | Owns the collection operation and bears the loss on fraud | "Are our client funds and our reputation protected?" |
| S6 | **Regulator (Bank of Ghana)** | External | Oversight of deposit-taking and microfinance conduct | "Is there an auditable record of client funds?" |
| S7 | **Data Protection Commission** | External | Enforces the Data Protection Act 2012 (Act 843) | "Is personal data lawfully collected and minimised?" |
| S8 | **Client's household** | Indirect beneficiary | Depends on the savings maturing intact | "Will the money be there when we need it?" |

## 2.2 Power / interest grid

```
            HIGH  ┌──────────────────────┬──────────────────────┐
                  │  KEEP SATISFIED      │  MANAGE CLOSELY      │
                  │                      │                      │
                  │  S5 Rural bank/MFI   │  S1 Client           │
                  │  S6 Regulator        │  S2 Collector        │
   P              │  S7 Data Protection  │  S3 Supervisor       │
   O              │                      │  S4 Administrator    │
   W              ├──────────────────────┼──────────────────────┤
   E              │  MONITOR             │  KEEP INFORMED       │
   R              │                      │                      │
                  │  (none identified)   │  S8 Client household │
                  │                      │                      │
            LOW   └──────────────────────┴──────────────────────┘
                    LOW                       HIGH
                              INTEREST
```

**Implication for the project.** S1, S2 and S3 are the *manage closely* group and are the
three roles the system implements. Their conflicting needs drive the central design
tension recorded in §2.4.

## 2.3 Elicitation techniques applied

Following Session 2 (Advanced Requirements Elicitation Techniques):

| Technique | How it was applied | Output |
|---|---|---|
| **Artefact analysis** | The existing paper susu card was analysed as the current system's data model: 31 boxes, one per day; client name and daily rate on the header; collector's signature. | The card's structure became the `ContributionCycle` / `Collection` model (FR-11, FR-12). |
| **Process observation (documentary)** | The established susu collection workflow — route visit → cash handed over → box marked → end-of-day remittance to branch → maturity payout less one day — was traced end to end. | Workflow requirements FR-08, FR-17, FR-18, FR-13. |
| **Analysis of failure modes** | The known ways the manual process fails (P1–P4 in `01-problem-definition.md`) were treated as the source of the system's differentiating requirements. | Transparency and audit requirements FR-19 to FR-22. |
| **Expert/analyst judgement** | Applied where stakeholder access was unavailable, and recorded as an assumption rather than a finding. | Default cycle length, commission policy, arrears tolerance. |

### Elicitation limitation (declared)

Primary elicitation with live stakeholders — interviews with collectors and clients,
or a JAD workshop with branch staff — **was not conducted**, because the 48-hour
examination window does not permit field access. The requirements below are therefore
derived from analysis of a well-documented existing manual process, not from primary
data. Every point where a real stakeholder would have been consulted is recorded as a
numbered assumption in §2.5 so that it can be validated later. This limitation is
carried forward into `Limitations` in the final project document.

## 2.4 Conflicting stakeholder needs

Requirements engineering is largely the work of resolving these, and two genuine
conflicts shape the design:

**C1 — Collector speed vs. client verifiability.**
The collector (S2) needs to record a payment in seconds while standing in a market, in
sunlight, on mobile data. The client (S1) needs every collection to be attributable,
timestamped and immutable. Strong controls slow the collector down; weak controls
destroy the client's guarantee.

*Resolution:* the recording action is reduced to a single confirmation on a
pre-populated amount (the client's agreed daily rate), while attribution, timestamping
and audit-logging happen server-side without any additional collector input. Integrity
is obtained without adding a single tap. → NFR-02, NFR-09.

**C2 — Correction of genuine mistakes vs. immutability of the record.**
Collectors will make honest errors — wrong client, wrong date. S2 needs to fix them.
S1, S5 and S6 need the record to be non-repudiable.

*Resolution:* records are never edited or deleted in place. A correction is a new,
linked reversal entry attributed to the user who made it, leaving both the original and
the correction visible. → NFR-04, FR-20.

**C3 — Data minimisation vs. operational usefulness.**
S7 requires that personal data be minimised under Act 843. S2 and S3 want enough detail
to identify a client on a route.

*Resolution:* the system stores name, phone number, business type and market location,
and nothing more — no Ghana Card number, no address, no next of kin. → NFR-06.

## 2.5 Assumptions requiring stakeholder validation

These are the points at which a real stakeholder would have been consulted. Each is
stated so that it can be challenged and corrected without redesigning the system.

| ID | Assumption | Would be validated by | Risk if wrong |
|---|---|---|---|
| A1 | The contribution cycle is 31 days. | Collector, branch manager | Low — cycle length is a configurable institutional setting. |
| A2 | Commission equals exactly one day's contribution. | Branch manager, client | Low — commission policy is configurable. |
| A3 | Clients may pay for several missed days at once ("catch-up"). | Collector | Medium — affects the collection allocation rule (FR-10). |
| A4 | A client belongs to exactly one collector at a time. | Branch manager | Medium — a many-to-many relationship would change the data model. |
| A5 | Clients have a phone capable of accessing a mobile web page, or can view via an agent. | Client | **High** — if false, the client-transparency feature (the system's core value) needs an SMS channel instead. |
| A6 | Early withdrawal before maturity is permitted, at the institution's discretion. | Branch manager | Low — feature is gated behind supervisor approval. |

> **A5 is the assumption on which the value proposition rests** and is treated
> accordingly: the SMS notification channel is specified as the mitigation and is
> carried in the future evolution plan rather than dropped.

## 2.6 Stakeholder-derived quality expectations

| Stakeholder | Expectation | Becomes |
|---|---|---|
| S1 Client | "I can see every payment I made, and who recorded it." | FR-21, FR-22 |
| S1 Client | "The screen is readable in sunlight and easy if I read slowly." | NFR-08 |
| S2 Collector | "Recording is fast and works on a weak network." | NFR-01, NFR-02 |
| S3 Supervisor | "I see today's variance today, not next week." | FR-19 |
| S4 Admin | "A collector cannot see another collector's route." | NFR-03 |
| S5 Bank | "Nothing can be changed without leaving a trace." | NFR-04, NFR-09 |
| S7 DPC | "Only necessary personal data is held." | NFR-06 |
