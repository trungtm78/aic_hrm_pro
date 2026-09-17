# Operational dataset for the first customer department — design

Date: 2026-09-17 · Branch: `19.0` · Status: approved (brainstorming session)

## Purpose

The production instance `okr.aipower.vn` held a trial dataset (the earlier DLSP
import). The customer — the Digital Platform & Services Centre of Vietnam
Television — will now run the product for real, starting with its Sales &
Services department. The trial data is removed and replaced with the customer's
own Q3/2026 plan.

Sources (customer documents, never committed — `Docs/OKR/` is git-ignored):

| File | Content |
|---|---|
| Staff workbook | 6 departments; 21 Sales & Services employees with code, e-mail, title |
| Q3/2026 OKR decision (PDF) | Appendix 5: 4 objectives, 10 key results with weights and criteria |
| Monthly KPI workbook | 13 positions; per position two KPI groups (revenue / management) with group weights, per-KPI weight in group, a target for each of July, August, September, measurement method and the KR it serves |

## Decisions (taken with the user)

1. Close the product gaps first so the plan is represented one-to-one.
2. Every Sales & Services employee gets a login immediately; random password
   per person; an account sheet (XLSX) is produced for the customer.
3. Plan data only — no invented actuals.
4. All six departments are created; only Sales & Services is staffed in detail.
5. **Data is created and deleted through the UI (Playwright), never by
   writing to the database.** Read-only RPC is used to look before writing and
   to verify afterwards.
6. Any E2E failure is root-caused (`/investigate`) and fixed where it lives —
   product or script — then re-run.
7. When everything is done, the whole profile is re-run and an independent
   acceptance spec checks production against the source documents.

## Product gaps closed

| # | Gap | Change |
|---|---|---|
| F0 | An opened cycle emptied of all records could never be deleted: the guard tested *state*, and there is no way back to draft | `aic.hrm.cycle.unlink` refuses locked cycles and cycles that still hold records (discovered from the registry: every stored restricting many2one to the cycle); anything else may go. ACL keeps deletion admin-only |
| F0b | Review forms (questionnaires) had ACLs but no screen: created inline from a template, never listed, edited or deleted | Configuration › Review Forms (sections and questions inline). Regression: every root model a manager may create is reachable from a suite menu |
| F1 | A KPI could not reference the key result it serves; a monthly target could not reference a quarterly objective | `kr_id` on `aic.hrm.kpi.target`; objective and KR may sit in the target's cycle or any ancestor cycle; the objective follows the KR |
| F2 | Scorecards were flat; group weights (revenue 80 % / management 20 %) had nowhere to live | `aic.hrm.kpi.assignment.group` (group, weight) on the scorecard; lines carry `group_id` and `weight_in_group`; effective line weight = group weight × weight in group. Submit gate: groups total 100 and each group's lines total 100. Scorecards without groups behave as before. Configuration › KPI Groups |
| F3 | "0 incidents" KPIs could not be expressed (lower-is-better required a target > 0) | Lower-is-better with target 0 is zero tolerance: actual ≤ 0 scores 100 %, anything above scores 0 %. Negative targets stay invalid |
| F4 | Milestone targets ("LIVE 7/9", "draft 3 processes") are text | `target_note` on the KPI target, shown next to the number |
| F5 | The spreadsheet import ignored groups and had no KR column | `KPI_CHI_TIET` reads group weight, weight in group, KR code, target note; older files import unchanged |

Out of scope (YAGNI): annual quarter weights (recorded in the year cycle's
description), KPI templates per `hr.job`.

## Data mapping

- Cycles: Year 2026 › Q3/2026 › July, August, September.
- OKR: department-level objectives in Q3, owner = head of department.
- KPIs: one KPI per position line (`KDDV.<position>.<line>`), one target per
  person per month, scorecards per person per month in draft for the head of
  department to submit and approve.
- Numeric targets: `≥ x` → higher, `≤ x` → lower, `0` → zero tolerance,
  Vietnamese number format (`2.600`, `49,15`). Wording → pass/fail with the text
  in `target_note`. The verbatim cell is always kept in `target_note`.
- A KPI marked `—` for a month is not assigned that month; the other lines of
  its group are rescaled proportionally to 100.
- Driver (no KPI); the employee who joined on 1 September gets September only.
- Scorecards: 19 (July) + 19 (August) + 20 (September) = 58.

## Harness

- `tools/extract_kddv.py` → `uat/data/kddv_q3_2026.json` (git-ignored), tested
  against the signed PDF wording and the revenue plan total (150,56 bn VND).
- `uat/playwright.prod.config.ts`, `uat/fixtures/prod.ts` (database guard,
  query-only RPC), `uat/pages/prod.ts` (field-name locators; each write waits for
  its own RPC answer and fails with Odoo's message).
- Specs `uat/specs/prod/01_purge` … `07_verify`, `99_acceptance`; each looks
  before it writes, so a re-run changes nothing. The purge only targets records
  created before the pre-cleanup backup, so re-running it cannot touch customer
  data.

## Safety

- Backup before any change: `pg_dump` + filestore under `/home/ubuntu/backups/`.
- No outgoing mail server: queued invitations (carrying sign-up tokens) are
  deleted.
- Passwords live only in git-ignored files.
- Open item for the user: the published documentation advertises the admin
  password of this instance, which now holds real people's data.

## Verification

Tooling tests; full Odoo suite (19, and 18 build); E2E profile run twice with
no record-count change on the second run; independent acceptance spec; 21 real
logins; access check (a member sees only their own scorecards); server log free
of errors.
