# 1. Problem Definition

**Project title:** SusuBook — A Digital Susu Collection and Accountability System
**Course:** CSCD602 Advanced Software Engineering
**Assessment:** Individual Project-Based Examination (48 hours)

---

## 1.1 Domain background

*Susu* is a widely used informal savings mechanism in Ghana. In the **collector model**, a
susu collector visits a client daily at their place of business and receives a small,
fixed contribution, commonly the same amount every day. The collector records the
payment by marking one box on a paper **susu card** that typically carries 31 boxes,
one per day of the contribution cycle. At the end of the cycle the client receives the
accumulated sum, less **one day's contribution**, which is retained by the collector as
commission.

The client group consists largely of people excluded from, or poorly served by,
formal banking: market women, kiosk operators, small shop owners, artisans and
transport workers. They deal in cash, earn daily rather than monthly, and save in
amounts too small for a conventional bank account to be worthwhile. Collectors operate
either independently or as mobilisation officers attached to a rural bank or
microfinance institution.

## 1.2 The problem

The mechanism works because of trust, and its record-keeping cannot support that trust.

**The record is held by the party it is meant to hold accountable.** The paper card is
carried and marked by the collector. The client has no independent copy of their own
contribution history. A card can be altered, lost, damaged by weather, or simply
disputed, and when it is, the client has no evidence.

This produces four concrete failures:

**P1: Client has no verifiable record of their savings.**
The client's only proof of months of daily contributions is a paper card that the
collector marks. If the card is lost or the entries are disputed, the client cannot
demonstrate what they paid. The saver carries all the evidentiary risk.

**P2: Collector absconding and misappropriation.**
Because cash is collected in the field and recorded only on paper, a collector can
under-record collections, delay remittance, or disappear with an entire route's takings.
Of the four failure modes identified here, this is the most severe in its
consequences: it removes the savings of people least able to absorb the loss, and
it discourages further participation.

**P3: Supervising institutions cannot reconcile in real time.**
A rural bank employing several collectors learns of a shortfall only when cash is
banked, or later. There is no same-day view of *what was recorded in the field* against
*what was remitted at the branch*, so variances surface late, when recovery is hardest.

**P4: Manual computation of payouts is error-prone and opaque.**
Days paid, days missed, total accumulated, commission deducted and the final payout are
all computed by hand from ticked boxes. Errors are easy, disputes are hard to settle,
and the client cannot independently check the arithmetic.

## 1.3 Problem statement

> Susu collection in Ghana relies on a paper card that is held and marked by the
> collector, leaving the client with no independent record of their own savings.
> This asymmetry enables under-recording and misappropriation of client funds, prevents
> supervising institutions from reconciling field collections against cash remitted on
> the same day, and makes payout computation manual, error-prone and unverifiable.
> The result is financial loss for savers who can least afford it and an erosion of
> trust in the informal savings sector.

## 1.4 Proposed solution

SusuBook replaces the paper card with a shared digital record that **both parties can
see and neither can silently alter**.

1. **An independent client record.** Every collection is recorded against a client and
   is immediately visible to that client on their own login, with the amount, the date,
   the time it was recorded and the identity of the recording collector. The client no
   longer depends on the collector's copy.
2. **Daily float reconciliation.** At the end of each collection day the collector
   declares the cash remitted. The system compares this against the sum of collections
   recorded in the field and raises a variance for supervisor attention the same day.
3. **Automated, transparent payout computation.** Days paid, days missed, total
   collected, the one-day commission and the net payout are derived by the system from
   the collection record, using the same rule for every client.
4. **An append-only audit trail.** Every collection, payout and adjustment is attributed
   to a user and a timestamp and cannot be edited in place; corrections are recorded as
   new, linked entries.

## 1.5 Aim

To design, implement, test and deploy a functional web-based susu collection system that
gives clients an independent and verifiable record of their contributions, and gives
supervising institutions same-day reconciliation of field collections against cash
remitted.

## 1.6 Objectives

| # | Objective |
|---|---|
| O1 | Elicit, analyse, specify and prioritise the requirements of a susu collection system and document them in an SRS. |
| O2 | Estimate the software effort required using an appropriate technique, and use that estimate to define a scope achievable within the 48-hour examination window. |
| O3 | Design a maintainable layered architecture, expressed through appropriate UML artefacts. |
| O4 | Implement the prioritised requirements as a functional, deployed web application with authentication, role-based authorisation, input validation and an audit trail. |
| O5 | Verify the system through unit, integration, system and user acceptance testing, and document the results. |
| O6 | Identify, classify, prioritise and document the technical debt introduced under the time constraint, with a repayment plan. |
| O7 | Define a maintenance strategy and a future evolution plan grounded in software evolution theory. |

## 1.7 Intended users

| User | Description |
|---|---|
| **Client** | A market trader, kiosk operator, shop owner or artisan who contributes a fixed amount daily and needs a trustworthy record of it. |
| **Collector** | A field officer who visits clients daily, records collections and remits cash to the branch. |
| **Supervisor** | A branch or field manager who oversees several collectors, reconciles daily remittances and investigates variances. |
| **Administrator** | Manages user accounts, roles and institutional settings such as cycle length and commission policy. |

## 1.8 Scope boundary

SusuBook digitises the **record of collection**, not the movement of money. Contributions
remain physical cash handed to the collector; the system records that event, computes its
consequences and makes it visible to all parties. Mobile money and bank payment
integration are deliberately excluded: see Appendix A for the reasoning, and §11 for their treatment as future evolution.

---

## 1.9 Basis of the domain description

Sections 1.1 and 1.2 describe the susu collector model and its failure modes
qualitatively, from analysis of the documented manual process rather than from
field data. **No statistic is asserted anywhere in this document**, and the
failure modes P1–P4 are derived by analysing the process structure rather than by
measuring its outcomes.

The structural argument does not depend on quantitative evidence: the record is
held by the party whose conduct it is meant to evidence, and each of P1–P4
follows from that fact alone. Establishing the *prevalence* of these failures
would require published data on participation and losses in Ghana's informal
savings sector, for example from the Bank of Ghana or the Ghana Statistical
Service. No such source was consulted, and none is cited, because citing a source
that was not consulted would be worse than stating the limitation.

This constraint is recorded again at §17.1, alongside the absence of primary
stakeholder elicitation, which arises from the same cause.
