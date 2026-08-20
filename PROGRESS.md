STATUS: ALL_MILESTONES_DONE

# PROGRESS

Deliberately short, English, and plain ASCII. This file is read by tooling that
opens it without naming an encoding, which on Windows means cp1252 - and cp1252
cannot decode Vietnamese. The full working log, every byte of it, lives in
`Docs/progress-log-vi.md`. See `Docs/stop-hook-encoding.md` for the diagnosis.

Keep the status keyword on line 1 and nowhere else, and keep this file
ASCII-only.

## Current state: UAT dataset and acceptance run - complete

| Check | Result |
|---|---|
| Test suite, Odoo 19, eleven modules on a database built from empty | 624 pass, 0 fail, 0 error |
| Test suite, Odoo 18 backport | 223 pass, 0 fail, 0 error, both tours included |
| Browser harness (Playwright, sign-off profile, retries 0) | 25 pass: 5 API smoke, 13 web E2E, 7 at 320px |
| Dataset | 26 named fixtures, every state in the state maps, ledgered cleanup that restores exact row counts |
| Enterprise scale | 2,000 employees / 80,000 assignment lines; close 0.02s, group 0.10s, full recompute 2.73s - all inside budget |
| Fault seeding | 4 faults introduced and reverted, 4 caught |

Five defects surfaced. Four fixed in this pass:

- `aic_hrm_match` could not be installed on an empty database: the config
  views hang two menus off parents the manifest loaded afterwards. An update
  never showed it, because the xmlids were already there. The only person who
  meets it is a first-time installer, which is every buyer.
- The Odoo 18 build could not load the progress report: the backported SQL
  still joined `hr_version`, a table that exists only in 19. The 18 branch had
  carried an unusable report since the reporting work landed.
- Both browser tours timed out after the menu regroup - they clicked items
  that had moved inside a stage dropdown.
- The executive overview opened on whichever cycle starts latest, so creating
  next quarter early made the leadership dashboard read "nothing measured yet"
  while the current period was full.

One left open by decision: `last_checkin_date` is still not refreshed when a
check-in is edited or deleted. No fixture claims it is correct and no test
covers it up.

Three things worth keeping from this pass:

- Test data is now an asset with names, a ledger and a cleanup recipe, not
  something each test builds and throws away. That is what made the browser
  run possible at all.
- The run happened on a database created from empty. Two of the five findings
  are invisible on a database that already has the product installed.
- The fault-seeding experiment was wrong the first time and said so: it
  updated the module carrying the fault, and Odoo only runs the tests of the
  modules it updates, so nothing had executed. A green result from an
  experiment that never ran is worse than a red one.

## Previous state: aic_okr_kpi menu and management reporting - complete

| Check | Result |
|---|---|
| Test suite, Odoo 19 | 317 pass, 0 fail, 0 error across the seven OKR/KPI modules |
| Menu | 17 flat items regrouped into 7 stages of the operating loop; 26 items moved from a mapping table, not by hand |
| New report | `aic.hrm.progress.report`, a SQL view unioning check-ins with confirmed KPI period results |
| Report views | graph, pivot, list, search, plus an Executive Overview dashboard - all reading the one model |
| Grouping | week, month, quarter, department, job position, library role, goal level, cycle |
| Verified on real data | 188 rows on the customer demo: 56 check-ins + 132 period results, matching the source counts exactly |

Four decisions worth keeping:

- Expected progress is computed in SQL at the date of the measurement. The
  live `expected_progress` field is a non-stored compute a view cannot read,
  and it answers "on pace today" where a report must answer "on pace then".
- Row ids come from the source row, not `row_number()`. Over a non-unique
  ORDER BY, `row_number()` hands out ids that move between executions, and the
  ORM reads a record in a second query after the search.
- The view flushes its source models before reading. Odoo cannot know an
  `_auto=False` model depends on those tables.
- The library role column is contributed by `aic_hrm_library` through a hook,
  because `aic_okr_kpi` sits below it in the dependency graph.

Reporting by position needed the position to exist: the import now maps the
sheet's "position" text to a real `hr.job`, and an employee carries the library
role a pack was applied from.

Open, not blocking: `last_checkin_date` on a key result is a plain stored field
written by the check-in flow, so editing or deleting a check-in leaves it
stale, and staleness plus the alert rules read it.

## Current state: aic_hrm_match (Staffing Match) - complete and verified

| Check | Result |
|---|---|
| Test suite, Odoo 19 | 331 pass, 0 fail, 0 error - clean install into an empty database |
| Test suite, Odoo 18 | 331 pass, 0 fail, 0 error - via `tools/backport_18.py` |
| Coverage | 96% |
| Performance, 2000 employees | one ranking ~1.3s against a 3s budget; scoring phase 0 queries; prefetch 66 queries for 2000 people |
| End-to-end tours | 3 of 3 pass on headless Chrome 151 (demo, admin, mobile at 375x667) |
| Translations | vi.po complete, 618 of 618 |
| Tooling tests | 46 pass, no database needed |
| Store packages | 10 archives per series, both 19.0 and 18.0 |

### How to reproduce

```powershell
$env:PYTHONUTF8='1'
./.venv/Scripts/python.exe odoo/odoo-bin -c odoo.conf -d <db> -u aic_hrm_match `
    --test-enable --test-tags 'aic_hrm_match,-perf' --log-level=test --stop-after-init
```

- Performance: `--test-tags 'perf'`, with `AIC_HRM_MATCH_PERF_EMPLOYEES=2000`.
- Tours: `--test-tags 'aic_hrm_match_tour'`.
- Odoo 18: `./.venv18/Scripts/python.exe odoo18/odoo-bin -c odoo18.conf ...`
  after running `tools/backport_18.py`.

The venv at `./.venv` is Python 3.12, built because Odoo 19 pins a wheel that
will not build on 3.13. Calling the system Python instead produces an import
error that looks like an environment blocker and is not one.

### Two ways this suite can report green having tested nothing

Both were hit and fixed; both are worth remembering.

- Without `websocket-client` installed, `start_tour` returns without driving a
  browser at all, and the tour test passes.
- `browser_size` set inside a test body has no effect, because the browser
  starts first - so a mobile check silently runs at desktop width and passes.

### Outstanding

Nothing blocking. The one open question is not a defect in this module: the
stop hook reads `PROGRESS.md` without an encoding argument and therefore could
never read the Vietnamese original. `Docs/stop-hook-encoding.md` has the
evidence and the one-line fix.
