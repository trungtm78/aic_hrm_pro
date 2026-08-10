
## QUY TAC SENTINEL - BAT BUOC

Dong dau tien cua `PROGRESS.md` luon la `STATUS: IN_PROGRESS`.
Chi doi thanh:
- `STATUS: ALL_MILESTONES_DONE` khi da het TOAN BO milestone.
- `STATUS: BLOCKED` khi gap blocker thuc su theo dieu kien dung (b).

Ngoai hai truong hop tren, KHONG duoc ket thuc luot de hoi nguoi dung.

# AIC HRM Pro — project instructions

Commercial Odoo addon suite (OKR/KPI performance management) sold on the Odoo
Apps Store. Author AIPOWER CO.,LTD · License OPL-1 · Enterprise segment ·
Dual-version Odoo 19 (primary) + 18 (backport branch `18.0`).

## Source of truth

- Spec (approved plan): `docs/superpowers/specs/2026-08-01-aic-okr-kpi-design.md`
- Execution state: `PROGRESS.md` (read FIRST after any context loss, then resume
  from "BƯỚC TIẾP THEO" without asking)
- Design system: `design.md` + `tokens.css` ("Muc & Thep HRM")
- Execution rules: AUTONOMOUS EXECUTION PROTOCOL (user-provided) — do not stop
  to ask; TDD per task; DoD = acceptance + >=90% patch coverage + full suite
  pass + clean lint + no TODO/dead code + PROGRESS.md updated.

## Hard rules

- **All source code, comments, docstrings, identifiers, constants, test names:
  ENGLISH.** User-facing strings: English in code, translated via `i18n/vi.po`
  (complete) and `i18n/ja.po` (draft — flagged, never silent fallback).
- **Never copy code from `C:\AIConnect\AIC_Sale Pro\addons_aic\aic_mcn_*`**
  (AGPL, unrelated product). Pattern reference only, via notes — do not open
  those files while writing OPL-1 code here.
- Namespace: models `aic.hrm.*`, modules `aic_hrm_*` / `aic_okr_kpi`.
- **Community-only dependencies.** Never Enterprise (no hr_appraisal, survey,
  gamification, and no `gantt` view type). Allowed per product line:
  - performance suite (`aic_hrm_base` and everything above it): `hr`, `mail`, `web`
  - staffing app (`aic_hrm_match`): adds `hr_skills` and `project` — both
    Community. It is a standalone listing and must NEVER depend on the
    performance suite; `tools/tests/test_store_packaging.py` enforces that.
- **Store listing names: at most 25 characters, no company name, no adjective.**
  Odoo Apps vendor guidelines reject longer titles, and the publisher name is
  already shown next to the listing. Enforced by
  `tools/tests/test_store_packaging.py` and by `tools/build_store_package.py`.
- **Every distributed module carries its own `LICENSE`.** The builder archives
  one module directory per zip, so a repo-root LICENSE reaches no customer.
- Every `_compute` batches via `read_group`; no per-record search loops
  (enterprise scale: 2,000 employees / 80k assignment lines; budgets:
  close cycle < 60s, import 10k rows < 120s, dashboard < 3s).
- Status (RAG) UI always uses `--status-*` tokens + shape, never accent color,
  never hue alone.
- **All custom UI must be mobile-responsive** (user directive): verified at
  320/375/414/768 px; no horizontal page scroll; touch targets >= 44px; see
  `design.md` § Responsive for per-surface collapse rules.

## Environment

Nothing below is committed (see `.gitignore`); recreate it on a fresh clone.

- **Python 3.12 via `./.venv`** — NOT the system 3.13. Odoo 19 pins
  `rl-renderPM==4.0.3` for win32/py>=3.12 and that wheel does not build on 3.13,
  so `pip install -r odoo/requirements.txt` aborts before psycopg2.
  Setup: `py -3.12 -m venv .venv` then
  `./.venv/Scripts/python.exe -m pip install -r odoo/requirements.txt`
- Odoo 19.0 CE source at `./odoo` (`git clone --depth 1 --branch 19.0`).
- Odoo 18.0 CE source at `./odoo18` — needed to verify the backport actually
  runs, not merely that the transform completed.
- Suite modules at `./addons_hrm` (committed); generated 18.0 tree at
  `./build/18.0` (produced by `tools/backport_18.py`).
- DB: PostgreSQL 18 @ 127.0.0.1:5433, role `odoo` (LOGIN CREATEDB).
- Configs: `odoo.conf` (19, port 8073) and `odoo18.conf` (18, port 8074,
  `addons_path` points at `build/18.0`).
- Run server: `./.venv/Scripts/python.exe odoo/odoo-bin -c odoo.conf`
- Run tests (note `--log-level=test`: at the default `warn` the result line is
  never printed and a green run is indistinguishable from a silent one):
  ```
  $env:PYTHONUTF8='1'
  ./.venv/Scripts/python.exe odoo/odoo-bin -c odoo.conf -d <db> -u <module> `
      --test-enable --test-tags '<module>,-perf' --log-level=test --stop-after-init
  ```
- Tooling tests need no database: `python -m unittest discover -s tools/tests -t .`
- Git: branch `19.0` primary, `18.0` backport; remote
  `https://github.com/trungtm78/aic_hrm_pro`. Commit per task/checkpoint,
  NEVER push unless the user asks.

## Release plumbing

- `tools/backport_18.py` — rewrites 19 -> 18 (AST-based), then `verify()`
  refuses the build if any Odoo-19-only API survived. A transform without a
  verifier fails silently, which is how 19-only code reaches an 18.0 zip.
- `tools/build_store_package.py --series {19.0|18.0}` — `--series 18.0`
  packages `build/18.0`, never `addons_hrm`.

## Testing conventions

`TransactionCase` + `@tagged('post_install', '-at_install', '<module>')`, one
file per behavior area, `test_security.py` per module, perf tests under tag
`perf`. Fixture factories as private `_make_*(**kw)` helpers.
