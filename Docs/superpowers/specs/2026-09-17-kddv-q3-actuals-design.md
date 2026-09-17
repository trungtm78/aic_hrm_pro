# KDDV Q3/2026 actuals through accounting — design

Status: approved 2026-09-17 (revised the same day: revenue goes through invoices, costs through
journal entries, and OKR/KPI read the ledger). Follows `2026-09-17-kddv-q3-operational-dataset-design.md`.

## Goal

Keep the Sales & Services department's real revenue and costs where they belong — Odoo
accounting — and have the Q3 OKRs and monthly KPIs pull their actuals from the ledger, then hand
the customer an evaluation that states exactly what was scored and what could not be.

## Sources (customer files, never committed)

- Receipts register `Template_PhieuThu_2026_20260917.xlsx`: seven sections × partner × month;
  invoiced and delivered-not-invoiced amounts before VAT, VAT, after VAT. January–August filled.
- Cost ledger `chi_phi_2026.xlsx`: one sheet per month of debit postings on detailed accounts
  (242/622/627/635/642 families). January–July filled.

## Decisions (owner, 2026-09-17)

1. Accounting moves to the Vietnamese localization (VND, Vietnam, `l10n_vn` chart, VAT 8%) while the
   ledger is still empty.
2. Invoiced amounts → posted customer invoices, one per partner/section/month, dated the month's
   last day, VAT 8% computed by Odoo; a file VAT other than 8% is noted on the invoice.
3. Delivered-not-invoiced amounts → one posted accrual entry per month (receivable 1388 against
   the stream's revenue account).
4. Costs → one posted entry per month, each ledger line on its own account, against clearing
   account 3388.
5. All of 2026 in the files goes into accounting; OKR/KPI score Q3 (July, August).
6. Actual revenue = invoiced + accrued, before VAT. Streams: II → Telco/ISP (51131),
   IV → VTVshop MG (51132), I + V + VI + VII → content services (51133), III → FAST & special pages
   (51134), digital services (51135) = 0.
7. Cost and gross profit are department tracking indicators with no weight. Only data-covered lines
   are scored; coverage is shown next to the score.

## Product changes

| # | Change |
|---|---|
| M1 | Metric source `multiplier`: pulled value = aggregate × multiplier (sign and unit, e.g. credit balance in VND → billions). |
| M2 | "Pull actuals from source" on KPI targets (form and list selection): every month of the target's cycle up to today, upserting draft `auto` period results; manual entries still win; locked cycles refused. |
| M3 | Confirm / reset-to-draft on period results, from a list selection (managers). |
| M4 | Scorecard line `has_actual`; scorecard `data_coverage` and `score_covered`; the same for objectives from key results with a check-in or a completed milestone. `score` unchanged. |
| M5 | `is_tracking` on KPI targets: actual shown, no achievement or RAG, refused on a weighted scorecard line. |

## Data flow

`tools/extract_kddv_actuals.py` reads both workbooks into `uat/data/kddv_actuals_q3_2026.json`: the
accounting documents (96 invoices, the August accrual, seven cost entries, accounts, products,
partners), stream totals, irregularities and the expected KPI actuals. Playwright specs enter the
accounting documents through the UI, create the metric sources and tracking indicators, pull and
confirm the actuals, and read every figure and score back from the system.

## Out of scope

KPIs whose actuals are not in the files (MAU, merchants, SOPs, CAC, receivables, milestones) — the
evaluation lists them as missing. Allocating the cost clearing account to real counterparts
(payroll, suppliers) is the accountant's job.
