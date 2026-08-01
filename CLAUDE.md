
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
- Community-only dependencies: `hr`, `mail`, `web` (no hr_appraisal, survey,
  gamification — Enterprise-only).
- Every `_compute` batches via `read_group`; no per-record search loops
  (enterprise scale: 2,000 employees / 80k assignment lines; budgets:
  close cycle < 60s, import 10k rows < 120s, dashboard < 3s).
- Status (RAG) UI always uses `--status-*` tokens + shape, never accent color,
  never hue alone.
- **All custom UI must be mobile-responsive** (user directive): verified at
  320/375/414/768 px; no horizontal page scroll; touch targets >= 44px; see
  `design.md` § Responsive for per-surface collapse rules.

## Environment

- Odoo 19.0 CE source at `./odoo` + base addons at `./addons` (NOT committed).
- Suite modules at `./addons_hrm` (committed).
- DB: PostgreSQL 18 @ 127.0.0.1:5433, user `odoo`, db `AIC_HRM_Pro`, port 8073.
- Run server: `python odoo-bin -c odoo.conf`
- Run tests: `$env:PYTHONUTF8='1'; python odoo-bin -c odoo.conf -d AIC_HRM_Pro -u <module> --test-enable --test-tags <module> --stop-after-init`
- Git: branch `19.0` primary, `18.0` backport; remote
  `https://github.com/trungtm78/aic_hrm_pro`. Commit per task/checkpoint,
  NEVER push unless the user asks.

## Testing conventions

`TransactionCase` + `@tagged('post_install', '-at_install', '<module>')`, one
file per behavior area, `test_security.py` per module, perf tests under tag
`perf`. Fixture factories as private `_make_*(**kw)` helpers.
