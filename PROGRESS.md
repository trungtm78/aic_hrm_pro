STATUS: ALL_MILESTONES_DONE

# PROGRESS

Deliberately short, English, and plain ASCII. This file is read by tooling that
opens it without naming an encoding, which on Windows means cp1252 - and cp1252
cannot decode Vietnamese. The full working log, every byte of it, lives in
`Docs/progress-log-vi.md`. See `Docs/stop-hook-encoding.md` for the diagnosis.

Keep the status keyword on line 1 and nowhere else, and keep this file
ASCII-only.

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
