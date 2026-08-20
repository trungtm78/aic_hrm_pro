# UAT run report — AIConnect HRM Pro

**Run:** 2026-08-20 · dataset build + gate orchestrator
**Verdict: GO, with three findings recorded below.**

Supersedes the run of 2026-08-02 (U01–U55, Odoo tours mapped onto Gate 2).
That report is preserved in git history; this one covers the same product plus
everything added since — the regrouped menu, the management reporting, the two
access-control fixes, and the staffing line — and it runs through a real
browser rather than a tour.

## Header

| | |
|---|---|
| Build | 19.0 branch, working tree at the commits listed under *Changes* |
| Environment | Odoo 19 CE, PostgreSQL 18 @ 127.0.0.1:5433, database **AIC_HRM_UAT**, server on **:8075** |
| Database isolation | `dbfilter = ^AIC_HRM_UAT$`, `list_db = False` — the selector cannot reach the customer database from this server |
| Dataset | 26 named fixtures from `aic_hrm_uat_data`, reset and re-seeded before every run |
| Runners | Odoo test framework (unit/integration, live PostgreSQL, no internal mocks) · Playwright 1.62 Chromium (API smoke, browser E2E, 320px) |
| Evidence profile | sign-off — `retries: 0`, `trace: on`, video on failure. A pass on retry would be reported as flake, not as a pass |
| Evidence location | `uat/test-results/` (traces, videos, screenshots), `uat/playwright-report/` |

## Gates

| Gate | Scope | Result |
|---|---|---|
| 0 · ENV | PostgreSQL 18 reachable, database present, server answering, dataset seeded | PASS |
| 1 · API smoke | 5 checks: server identity, catalogue fully applied, three personas authenticate, fourteen models read, report reconciles with its sources | **5/5 PASS** |
| 2 · WEB E2E | 13 checks across navigation, the weight gate, reporting and anonymity | **13/13 PASS** |
| 2b · RESPONSIVE | 7 checks at 320px | **7/7 PASS** |
| 3 · MOBILE | N/A — `_platform.json` carries no mobile label; the product is responsive web. Not a skip: there is no native app to run | N/A |
| 4 · REPORT | this document | — |

Browser total: **25 executed, 25 passed, 0 failed, 0 skipped, 0 not-executed.**
Test-case file: `Docs/uat/dataset-2026-08/test-cases.json` — 47 cases, every one
naming the automated check that executes it.

## Unit and integration

| Suite | Result |
|---|---|
| `aic_hrm_uat_data` (the dataset's own tests) | 27 passed |
| Full suite, eleven modules, on a clean database | see *Regression* below |

## The dataset

26 fixtures, `<entity>.<state>.<lifecycle>.<shape>`, covering every state in the
product's state maps and the three collection shapes that break things:

* **cycle** — draft · open (mid-flight, D-45) · review · closed · **locked** · one-day
* **objective** — draft · approved (four metric types) · done (five levels nested) · empty
* **key result** — three check-ins over a month · stale since D-30
* **kpi target** — confirmed · draft results · lower-is-better · cap 1.2
* **scorecard** — 100 · **80 (must refuse)** · thirds
* **review** — two of three raters · three of three · external rater with no login
* **calibration** — an applied, immutable line
* **library** — a pack before and after it is applied
* **org** — HR admin, manager, member, three peers, and four awkward people: no
  login, archived leaver, no department, no job position

Each carries a ledger of every record it created, so cleanup restores the exact
row counts of eleven models — proven, not assumed.

## Enterprise scale

2,000 employees · 40 departments · 40 KPIs · **80,000 assignment lines** ·
24,000 confirmed period results. Seeding took 249s.

| Budget (CLAUDE.md) | Measured | Verdict |
|---|---|---|
| Close a cycle < 60s | 0.02s | PASS |
| Dashboard grouping < 3s | 0.10s (0.90s cold) | PASS |
| Score roll-up < 60s | 2.73s | PASS |

Read the first row with care: closing a cycle is a state transition, so 0.02s
says the transition is cheap, not that the product is fast. The number that
carries weight is the roll-up — 2.73s to recompute every scorecard across
80,000 lines. An earlier version of this measurement reported 0.08s because it
read a stored field instead of recomputing it; that was fixed before this run.

## Fault seeding

Four deliberate defects, each reverted immediately after:

| Fault | Caught by |
|---|---|
| Score cap loses its upper bound | two cases |
| Scorecard weight gate always open | `test_underweight_scorecard_cannot_be_submitted` |
| Authorisation skipped for a rater with no login (the `/cso` hole restored) | `test_external_rater_cannot_be_spoken_for` |
| Applied calibration line becomes deletable | `test_applied_calibration_line_is_immutable_and_undeletable` |

**4 seeded, 4 caught.** The first attempt reported two as surviving; that was a
flaw in the experiment, not the product — it updated the module carrying the
fault, and Odoo only runs the tests of the modules it updates.

## Findings

### F-01 · `aic_hrm_match` could not be installed on an empty database — S1, fixed

`views/aic_hrm_match_config_views.xml` places two menu items under parents
defined in `views/aic_hrm_match_menus.xml`, which the manifest loaded
afterwards. On a fresh install the parents do not exist yet and the install
aborts with `External ID not found: aic_hrm_match.menu_aic_hrm_match_request`.

An **update** never showed it, because by then the xmlids were already in the
database. The only person who meets this is somebody installing the app for the
first time — which is every buyer. Fixed by loading the menus file first; the
menus file defines its own actions and depends on nothing loaded after it.

### F-02 · The executive overview opened on an empty cycle — S2, fixed

It selected the cycle with the most recent start date. Create next quarter's
cycle a week early — an ordinary thing to do — and from that moment the
leadership dashboard greets everyone with *"Nothing measured in this cycle
yet"* while the current period is full of data. It now prefers the most recent
cycle that actually holds a measurement, and falls back to the newest so a
genuinely empty database still shows the empty state.

### F-03 · `last_checkin_date` is still not refreshed on edit or delete — S3, open

Reported in the previous session and deliberately not fixed here. Editing or
deleting a check-in leaves the stored date pointing at the old value, so
staleness and the alert rules that read it can be wrong. No fixture claims
correct behaviour for it, and no test asserts it. Roughly ten lines in the
check-in `write` and `unlink`; it is the user's call.

## Environment notes

* This machine's Odoo core has been edited: `addons/web/controllers/home.py`
  redirects the backend to `/aic`. The suite ships that entry point in
  `aic_hrm_brand` as an *addition*; here it is the default. `addons/` is not
  committed, so this is a local difference — but it means URLs on this machine
  are not the URLs a buyer sees, and the harness accepts either prefix rather
  than pretending otherwise.
* The harness blocks Odoo's long-polling endpoints in the browser. The UAT
  server runs threaded (`workers = 0`, the only mode Windows supports) and held
  bus connections starve the pool after a few specs, producing a "connection
  lost" dialog that fails tests for an environmental reason. Nothing under test
  is mocked.

## What this run does not cover

Declared in full in `Docs/uat/dataset-2026-08/_coverage-ledger.md`: the
spreadsheet import is covered at unit level with real files rather than through
a browser upload; the cockpit and alignment tree are checked for rendering and
console cleanliness rather than for their figures; and the Odoo 18 backport of
the dashboard fix is tracked separately.
