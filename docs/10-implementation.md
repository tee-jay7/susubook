# 10. Implementation

> Examination document §10. What was built, the decisions taken while building
> it, and where the implementation departed from the design.

---

## 10.1 Delivered system

A functional, deployed web application implementing 30 functional requirements
across four roles, with 226 automated tests at 97% coverage.

| | |
|---|---|
| **Live** | https://susubook-fdtbppd7sq-uc.a.run.app |
| **Source** | https://github.com/tee-jay7/susubook |
| **Stack** | Python 3.12 · Flask 3 · SQLAlchemy 2 · PostgreSQL 16 · Jinja2 · HTMX · segno |
| **Tests** | 226 (129 unit, 42 integration, 55 system) |
| **Coverage** | 97% overall; 99–100% on the domain layer |

## 10.2 Structure as built

The folder tree is the architecture diagram. Dependencies point downward only.

| Layer | Path | Lines | Contents |
|---|---|---|---|
| ① Presentation | `app/web/` | 430 | 4 blueprints, session handling, role decorators |
| — templates | `app/web/templates/` | 757 | 18 Jinja templates, shared macros |
| ② Application | `app/services/` | 725 | Use-case orchestration, repository Protocols |
| ③ Domain | `app/domain/` | 484 | Entities, `Money`, business rules BR-R1…R15 |
| ④ Infrastructure | `app/infrastructure/` | 700 | ORM models, repositories, QR rendering |
| — root | `app/` | 337 | Factory, config, seed |
| | **Application total** | **3,433** | |
| | Test code | 2,634 | |

Test code is **77% the size of the application**. That ratio is the practical
consequence of the architectural decision described below.

## 10.3 The decision that shaped everything else

**The domain layer imports neither Flask nor SQLAlchemy.**

This looks like architectural purity. It was a scheduling decision.

Business rules expressed as pure functions can be tested with no database, no
fixtures and no HTTP client. The 129 unit tests run in **0.34 seconds**. Under an
implementation budget of roughly 20 hours, an Active-Record design — rules living
on ORM models — would have required a live database for every rule test, and
those tests would not have been written at all. Testing carries 5 marks and had
no lecture deck behind it; the architecture is what made the suite affordable.

The cost is real and recorded: hand-written mapping between domain entities and
ORM records (**TD-07**), which must be updated in two places on any schema
change. An integration test asserts that money round-trips the mapping exactly,
which is the specific drift that would matter most.

## 10.4 Implementation decisions worth defending

### Money is an integer count of pesewas

```python
@dataclass(frozen=True, order=True)
class Money:
    pesewas: int
```

`float` is rejected at construction *and* at multiplication, rather than merely
avoided by convention:

```python
if isinstance(amount, float):
    raise TypeError(
        "Refusing to build Money from float -- binary floating point "
        "cannot represent decimal currency exactly (BR-R1)."
    )
```

Testing this produced **DEF-01**, and the correction is more interesting than the
rule. The original test asserted that 31 × GHS 0.10 accumulates to
3.0000000000000004 in floating point. It does not — that sum happens to round
back to exactly 3.1. The error is real but **intermittent**: 29 × 0.10 gives
2.9000000000000004, and 3 × 0.10 gives 0.30000000000000004.

Intermittent is worse than consistently wrong, because it survives casual testing
and reaches production. The test now asserts exactness across the whole 1–31 day
range rather than at a single sample that could pass by luck.

### The zero-payout edge case is made unrepresentable

BR-R9 states that where total collected does not exceed one day's rate, the
client receives nothing and the whole balance is retained. The naive
implementation — `payout = total - rate` — produces a **negative payout** for a
client who contributed on only one day.

```python
def commission_for(self, total_collected: Money, daily_rate: Money) -> Money:
    return min(daily_rate, total_collected)
```

Expressed as `min`, a negative payout becomes unrepresentable rather than merely
unlikely. It is then guarded three further times: an assertion in the domain
layer, a `CHECK (net_payout_pesewas >= 0)`, and a `CHECK` asserting
`net + commission = total_collected` so money is conserved. A test exercises all
32 possible completion levels rather than sampling.

### Three invariants are enforced twice

BR-R2, BR-R5 and BR-R10 are checked in the domain layer *and* again by PostgreSQL
partial unique indexes:

```sql
CREATE UNIQUE INDEX ux_effective_contribution_per_day
  ON contributions (cycle_id, contribution_date)
  WHERE reversed_by_id IS NULL AND is_reversal = false;
```

The index is **partial**, and that is the point. A reversed contribution, its
reversal, and the replacement must coexist on one date — a plain
`UNIQUE(cycle_id, contribution_date)` would make correction by reversal
impossible. This is the specific reason PostgreSQL was chosen over MySQL.

The integration suite writes **through the ORM, bypassing the service layer**, to
demonstrate the guarantee does not depend on application code being correct.

### Correction is reversal, never deletion

A contribution is never edited or deleted. A correction is a new linked entry, so
both remain visible on the client's record. This resolves conflict **C2** from the
stakeholder analysis — the collector can fix an honest mistake without weakening
the non-repudiation the client relies on.

The client-facing screenshot in `docs/screenshots/05-client-card.png` captures
this working: a REVERSED entry and its REVERSAL both visible, days paid correctly
reduced, and the affected day returned to "missed" on the card.

### Authorisation never consults the QR reference

```python
if actor.is_supervisor or client.is_collected_by(actor.id):
    return client
self._audit.append(action="AUTHORISATION_DENIED", ...)
raise NotAuthorised("This client is not on your route.")
```

BR-R15 in code: possession of a client reference gets you to the lookup and no
further. A card photographed in a market confers nothing, because the
authorisation decision reads the collector–client assignment rather than the
reference.

### Out-of-band updates on the collector's critical path

**DEF-06**, found by exploratory testing rather than by any of the 226 automated
tests. Recording a contribution swapped the client's row to "Paid" but left the
day's running total stale until a manual refresh — a row marked Paid sitting
above a total reading GHS 0.00.

Two figures disagreeing on one screen is worse than a figure that does not
update: it makes the collector distrust both. Fixed with an HTMX out-of-band
swap, so one request updates both without re-rendering the list.

## 10.5 Where implementation departed from design

Recorded because a design that survived contact with implementation untouched
would be a design nobody followed.

| Change | Reason |
|---|---|
| `CycleService.open_for()` takes `client_id` and `daily_rate` rather than a `Client` | The payout path opens the next cycle knowing only what the closing cycle carried. The original signature forced construction of a half-populated entity purely to satisfy it. |
| `BASE_URL` became optional, falling back to the request origin | A Cloud Run URL is not known until the service exists. Also keeps QR cards correct across a domain change, with no reissue. |
| Boolean and status columns gained `server_default` | **DEF-02.** A direct SQL insert failed on NOT NULL before reaching the partial index — and surviving direct writes is the entire purpose of those indexes. |
| `/healthz` became `/health` | **DEF-08.** Google Front End intercepts `/healthz` on Cloud Run before the request reaches the container. |
| `validate_contribution` gained `days_covered` | FR-15 (catch-up payments) is deferred, but parameterising the rule means enabling it later needs no change to the business rules — only an allocation step in the service layer. |
| A health endpoint was added | Not in the original design; required by the deployment target. |

## 10.6 Self-admitted technical debt in the source

Session 3's SATD convention, used with its conventional force: `TODO` for work
not done, `FIXME` for something that works but is wrong, `HACK` for a knowingly
poor mechanism. Each marker names its register entry, so code and analysis reach
each other.

```
app/domain/rules.py:41               TODO(TD-13)   cycle length is a constant
app/domain/rules.py:174              FIXME(TD-11)  summary recomputed per render
app/infrastructure/db.py:28          FIXME(TD-01)  create_all, no migrations
app/infrastructure/models.py:231     HACK(TD-09)   audit append-only by convention
app/infrastructure/repositories.py:6 TODO(TD-07)   hand-written mapping
app/services/collection.py:338       TODO(TD-05)   static route sheet
app/services/collection.py:344       FIXME(TD-16)  N+1 on the route sheet
app/services/security.py:38          FIXME(TD-14)  no login rate limiting
app/web/auth.py:52                   TODO(TD-15)   no password reset
app/web/client.py:60                 FIXME(TD-16)  N+1 in cycle history
app/web/supervisor.py:65             TODO(TD-04)   bare reversal form
requirements.txt:5                   TODO(TD-12)   unpinned dependencies
```

## 10.7 Development process

Seventeen commits, conventional-commit format, each recording what changed and
why. Notable process facts:

- **CR-001** (QR client identification) was raised mid-project and put through
  the change control process defined in `03-requirements.md` §3.8 — options
  costed, impact traced through the traceability matrix, estimate revised, and a
  6.4% schedule overrun **accepted and logged rather than absorbed** by
  manufacturing further cuts.
- Eight defects were found and closed; five by tests or probing, one by a user,
  two by inspection.
- Two of the developer's own test assumptions were found wrong and corrected
  rather than worked around (`09-testing.md` §9.8).
- Container images are tagged with the git SHA, so any deployed revision is
  traceable to a commit.

## 10.8 Size: estimate against actual

Session 6's closing practice is to record actuals and review estimation accuracy.
The size estimate can be closed out precisely.

| | Estimated | Actual | Variance |
|---|---|---|---|
| Adjusted function points | 166 | — | — |
| LOC per function point (AS-01) | 30 | **20.7** | −31% |
| Source size | 4.98 KLOC | **3.43 KLOC** | **−31%** |
| COCOMO effort at that size | 12.95 PM | 8.76 PM | −32% |

**MRE on size = 0.45.**

**The finding is that assumption AS-01 was wrong, and wrong in a specific
direction.** 30 LOC per function point was taken from published averages for the
language class. The actual figure was **20.7** — below even the optimistic 25
used in the sensitivity analysis (§4.3.4).

Two plausible causes, both consistent with the code as written. Flask, SQLAlchemy
and Jinja supply as configuration what the published averages assume is written
by hand — routing, session handling, ORM persistence, CSRF, templating. And the
function point count included work that produces very little code: the QR card is
5 function points and roughly 15 lines, because `segno` does the work.

The sensitivity analysis in §4.3.4 anticipated this class of error but not its
size, having bounded the range at 25–40. Had the range been set from measurement
rather than from published tables, it would have started lower.

**This does not change the conclusion of §4.4.** Even at the actual size, COCOMO
puts the system at 8.76 person-months — over 1,300 person-hours against a 48-hour
window. The gap is smaller than estimated and remains of the same order.
