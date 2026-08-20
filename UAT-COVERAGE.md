# UAT COVERAGE — AIC HRM Pro (Phase 1 + Phase 2)

Ma trận phủ 100% màn hình/chức năng theo §9 protocol. "Viết test" = file test tự động
đảm nhiệm; "Chạy" = lần chạy xanh gần nhất (suite 19 + build 18, xem PROGRESS.md).

| ID | Màn hình / Chức năng | Viết test | Chạy test | Kết quả |
|----|----------------------|-----------|-----------|---------|
| U01 | Cycle: tạo, loại kỳ (năm/nửa năm/quý/tháng/tùy chỉnh), state machine, lock bất biến, chỉ xóa draft | test_cycle.py (13 case) | suite 19+18 | PASS |
| U02 | Cycle: parent containment, cùng công ty, RAG profile cùng công ty | test_cycle.py | suite 19+18 | PASS |
| U03 | RAG profile: ngưỡng cấu hình, resolve bands, ràng buộc thứ tự | test_rag.py | suite 19+18 | PASS |
| U04 | Target revision: old/new, reason bắt buộc, approve/reject chỉ từ requested, manager-only, allowlist field, record tồn tại | test_target_revision.py (9) | suite 19+18 | PASS |
| U05 | Metric source: allowlist model, field stored-numeric, aggregate sum/avg/count, bad-domain, admin-gate compute | test_metric_source.py | suite 19+18 | PASS |
| U06 | Phân quyền base: groups implied, user read-only cycle, manager write, multi-company | test_security.py (base) | suite 19+18 | PASS |
| U07 | Objective: form + workflow 7 trạng thái, manager-only approve/finalize, direct-write chặn | test_objective_workflow.py | suite 19+18 | PASS |
| U08 | Objective: weighted roll-up (KR + child), zero-weight, clamp theo cap CỦA CHÍNH cycle | test_objective_scoring.py | suite 19+18 | PASS |
| U09 | Alignment 1A: cùng cycle + quý→năm qua cycle.parent, chặn cycle lạ, contributes-to cùng luật, chống đệ quy | test_objective_scoring.py | suite 19+18 | PASS |
| U10 | KR: 4 metric type × direction, milestones weighted, cap cycle, target≠baseline, RAG theo profile cycle | test_kr_progress.py | suite 19+18 | PASS |
| U11 | Governance sau approve: weight/target/baseline chỉ qua revision (context+manager, không giả mạo được), KR mới bị chặn, move sang cycle locked bị chặn | test_objective_workflow.py + test_kpi_engine.py | suite 19+18 | PASS |
| U12 | Record rules OKR: own/public/manager-chain, private-không-owner chỉ manager, không gán goal cho người khác, không tiêm KR vào goal người khác, milestone theo KR | test_security.py (okr, 10 case) | suite 19+18 | PASS |
| U13 | KPI library: form hồ sơ đầy đủ, unique code, lower-better target>0, template shared (company=False cả create/write) | test_kpi_engine.py | suite 19+18 | PASS |
| U14 | 14 template human-capital seed | test_kpi_engine.py (đếm HCT-%) | suite 19+18 | PASS |
| U15 | KPI target: kế thừa 3A compute-stored (create thuần/import/API), override giữ, đổi kpi_id recompute, unique kể cả NULL-owner, company coherence | test_kpi_engine.py | suite 19+18 | PASS |
| U16 | Achievement matrix: last/average/sum × higher/lower/boolean, draft loại trừ, clamp [0,cap] không âm/không vượt | test_kpi_engine.py | suite 19+18 | PASS |
| U17 | Period results: unique kỳ, ngày hợp lệ, cycle lock chặn create/write/unlink/move | test_kpi_engine.py | suite 19+18 | PASS |
| U18 | Scorecard cá nhân: Σweight=100 gate (submit chặn, rounding 33.33×3), composite, line cùng cycle, unique employee-cycle, manager-only approve | test_assignment.py | suite 19+18 | PASS |
| U19 | Department scorecard SQL view | test_assignment.py | suite 19+18 | PASS |
| U20 | Check-in KR: write-through current/confidence/last-date/snapshot; KPI: draft period result theo tháng (match overlap); XOR parent kể cả vals thiếu; confidence 1-10; validate cycle trước create | test_checkin_monitoring.py | suite 19+18 | PASS |
| U21 | Stale detection (compute + search dual-signature 18/19) + reminder cron | test_checkin_monitoring.py | suite 19+18 | PASS |
| U22 | Alert rules: stale/red/confidence-drop/weight-incomplete, idempotent theo [ALERT-id], escalation manager, cron | test_checkin_monitoring.py | suite 19+18 | PASS |
| U23 | Review meeting: agenda tự sinh (red/stale/blockers), action items lifecycle, states | test_checkin_monitoring.py | suite 19+18 | PASS |
| U24 | Import Excel 3-sheet: preview không side-effect, cảnh báo tên lạ, idempotent, map thuật ngữ VI/EN từ data, không gán nhầm owner (clone target), file hỏng báo lỗi, tạo-employee-thiếu opt-in | test_import_rollover.py | suite 19+18 | PASS |
| U25 | Rollover: copy cấu trúc, reset actuals, remap parent, idempotent re-run, draft-clean | test_import_rollover.py | suite 19+18 | PASS |
| U26 | Cockpit + Alignment tree: action/menu/assets wiring; NaN guard; RAG shape+màu; responsive tokens | test_dashboard.py + tour | suite 19 + Chrome | PASS |
| U27 | Tour demo E2E (menu→Objectives→Cockpit) trên Chrome thật | test_tour.py | run riêng tag tour | PASS |
| U28 | i18n vi: load sạch, menu "Hiệu suất"/"Mục tiêu" verify | shell check + load-language EXIT:0 | 2026-08-02 | PASS |
| U29 | i18n ja: draft có cờ, fallback English lộ rõ | ja.po header + 17 chuỗi | build | PASS |
| U30 | Review cycle: sinh idempotent mỗi nhân viên, goal_score snapshot bất biến, small-team warning | test_review_flow.py | suite 19+18 | PASS |
| U31 | Review: stage progression theo route map, self_score chỉ owner-trong-stage-self, manager-fields server-side, final=calibrated-else-manager | test_review_flow.py | suite 19+18 | PASS |
| U32 | 360: rater thấy đúng phiếu mình (không đọc được identity field), reviewee không thấy phiếu/response, manager chỉ thấy count, create_uid & write_uid = OdooBot, aggregate ≥min_raters, chặn nộp 2 lần, validate câu hỏi thuộc form + rating trong thang | test_feedback_anonymity.py (9) | suite 19+18 | PASS |
| U33 | Calibration: snapshot before, justification bắt buộc khi đổi, apply ghi calibrated + chatter luôn, line applied bất biến với MỌI user, session done chặn apply | test_calibration.py (6) | suite 19+18 | PASS |
| U34 | 9-box: band × potential đủ 9 ô (star ↔ underperformer) | test_talent.py | suite 19+18 | PASS |
| U35 | PIP: tự gợi ý khi final<0.4, sinh 3 checkpoint 30/60/90, idempotent; IDP lifecycle | test_talent.py | suite 19+18 | PASS |
| U36 | Packaging: manifest coherence (OPL-1, version, chỉ app có price), language gate một chiều, demo hư cấu Σ100 | test_packaging.py | demo db | PASS |
| U37 | Perf enterprise: 2.000 NV × 40 line — close-recompute <60s, import 10k <120s, dashboard <3s | test_perf_enterprise.py (tag perf) | run riêng 2026-08-02 | PASS |
| U38 | Cài mới db trống + demo data + toàn suite | fresh install AIC_HRM_Demo | 2026-08-02 | PASS |
| U39 | Dual-version: toàn suite trên Odoo 18 build (7 delta tự động) + branch 18.0 | backport_18.py + suite 18 | mỗi CP | PASS |

Đối chiếu ngược với spec (docs/superpowers/specs/…): mọi mục trong "Kiến trúc module",
"Vòng PDCA", "Hardening Codex", "Test bổ sung bắt buộc" đều có dòng tương ứng ở trên.
Ngoài phạm vi (NOT in scope của spec): bridge hr_appraisal, backport 17, AI insights,
bonus formula, mobile app — không thuộc UAT này.

| U40 | Project bridge: task gắn KR, chế độ count/percent-done, task hủy loại khỏi mẫu số, manual mode không bị đụng, relink resync, cron safety-net | test_task_progress.py (8) | suite 19+18 2026-08-02 | PASS |
| U41 | Sales bridge: doanh thu đơn xác nhận/số báo giá/hóa đơn theo từng sale, DRAFT chờ manager confirm, cron update-in-place, setting cấp KPI kế thừa mọi staff + override riêng | test_sales_actuals.py (6) | suite 19+18 2026-08-02 | PASS |
| U42 | Luật "tay thắng máy": dòng nhập tay không bao giờ bị cron auto ghi đè (sale + metric source) | test_manual_entry_always_beats_automation | suite 19+18 2026-08-02 | PASS |
| U43 | Diagnosis engine: expected progress theo lịch, pace gap, required run-rate, khuyến nghị từ blocker/confidence/cadence/task thật | test_diagnosis.py (8) | suite 19 2026-08-02 | PASS |
| U44 | Thư viện vai trò × ngành: ≥25 role seed (10 cross + 15 theo ngành), mỗi role có obj+KPI templates + playbook thu thập dữ liệu; lọc theo industry (tagged hiện, khác ngành ẩn, cross luôn hiện) | test_library.py | suite 19 2026-08-02 | PASS |
| U45 | Apply pack: draft objectives+KR+targets cho employee/team/department/company, re-apply không nhân đôi target, perspective truyền từ template | test_library.py | suite 19 2026-08-02 | PASS |
| U46 | Capture knowledge: parse OBJ:/KR:/KPI:, company-scoped, chặn KR mồ côi | test_library.py | suite 19 2026-08-02 | PASS |
| U47 | Actuals import CSV/XLSX: period result source=import chờ confirm, manual thắng, confirmed bất biến, auto-draft bị đè, KR row→check-in, CSV chấm phẩy + thập phân phẩy, code lạ chỉ warn, thiếu cột báo lỗi | test_actuals_import.py (8) | suite 19 2026-08-02 | PASS |
| U48 | 5 cấp mục tiêu: company/branch/department/team/individual + constraint anchor đúng cấp, cascade xuyên cấp, team unique per company | test_levels.py (7) | suite 19 2026-08-02 | PASS |
| U49 | BSC: 4 perspective seed, KSF catalog ≥12 phủ đủ 4 góc, objective drive / KPI measure / target kế thừa perspective, read_group cân bằng danh mục | test_strategy.py | suite 19 2026-08-02 | PASS |
| U50 | Đa framework: BSC/Hoshin/4DX seed kèm dimension, 1 objective đọc qua nhiều framework cùng lúc (m2m tags + group-by) | test_strategy.py | suite 19 2026-08-02 | PASS |
| U51 | Knowledge Guide: ≥10 bài built-in phủ đủ 6 nhóm chủ đề, company article tách khỏi built-in (record rule) | test_library.py | suite 19 2026-08-02 | PASS |
| U52 | Hướng dẫn thu thập: collection_method/guideline trên KPI + tab "How to Collect" trên target (related) | view + related field (U47 gián tiếp) | suite 19 2026-08-02 | PASS |
| U53 | Nút xây kế hoạch tại chỗ: "From Previous Cycle" + "From Library" + "Import Actuals" trên list Objectives/KPI Targets | view header buttons (load qua suite install) | suite 19 2026-08-02 | PASS |
| U54 | TOÀN BỘ màn hình (enumerate từ DB — không sót): 35 menu→action→views→search, Form new-record mọi model, 5 wizard default_get, 2 client action, 5 cron | test_screen_smoke.py (5) | suite 19 2026-08-02 | PASS |
| U55 | Browser walk màn hình lõi (KRs, Targets, Check-ins, Scorecards, Alignment) trên Chrome thật | tour aic_okr_screens | run 2026-08-02 03:40 | PASS |

| U56 | Find Best Fit entry point: task -> modal -> create request + slot | test_wizards.py (16) | suite 19+18 | PASS |
| U57 | Criterion engine: 12 criteria, 6 normalisation types, all directions | test_normalization.py (12) + test_ranking.py (33) | suite 19+18 | PASS |
| U58 | Policy versioning: code+version unique, active locked, fork creates v2 | test_scoring_policy.py (22) | suite 19+18 | PASS |
| U59 | Ranking: stable tie-break, re-rank creates new run, invariant check | test_ranking.py (33) | suite 19+18 | PASS |
| U60 | Composition multi-slot: optimal assignment, alternatives, capacity | test_composition.py (12) | suite 19+18 | PASS |
| U61 | Availability: DST, split shifts, leaves, cross-night shifts | test_availability.py (22) | suite 19+18 | PASS |
| U62 | Allocation concurrency: advisory lock, serial safety, re-read after lock | test_allocation_concurrency.py (6) | suite 19+18 | PASS |
| U63 | Experience ledger: unique key, watermark pointer, tombstone, reconciliation | test_experience_ledger.py (14) | suite 19+18 | PASS |
| U64 | Skill compat 18 vs 19: field detection, shim fields, upgrade safe | test_skill_compat.py (10) | suite 19+18 | PASS |
| U65 | Certification: expiry gates work, verify workflow, NV cannot self-verify | test_skill_scoring.py (24) | suite 19+18 | PASS |
| U66 | Registry and fail-closed: missing scorer rejected, hard scorer failure | test_match_context.py (6) + test_scoring_policy.py (22) | suite 19+18 | PASS |
| U67 | Engine swap: alternate engine callable, fallback logged, snapshot aware | test_policy_switches.py (3 of 14) | suite 19+18 | PASS |
| U68 | Fairness: score adjustment clamped, load balance XOR workload balance | test_policy_switches.py (4 of 14) | suite 19+18 | PASS |
| U69 | Decision log: mail.thread, allocation chain, snapshots, confirmed immutable | test_decision_waiver_erasure.py (11) | suite 19+18 | PASS |
| U70 | Waiver: hard gate exception, immutable record, sensitive admin-only | (see U69) | suite 19+18 | PASS |
| U71 | Erasure GDPR Art17: pseudonymize, null employee, archive identity | (see U69) | suite 19+18 | PASS |
| U72 | Audit chain immutable: set null snapshots, unlink guards, vacuum logs | test_decision_waiver_erasure.py (11) + test_request_workflow.py (9) | suite 19+18 | PASS |
| U73 | Security (22 case): peer isolation, own candidacy, sensitive criteria | test_security.py (22) | suite 19+18 | PASS |
| U74 | Multi-company and cross-company: isolation, rejection codes | test_security.py (22) | suite 19+18 | PASS |
| U75 | Full screens (21 view + 4 wizard + 2 action): responsive 320-768px | test_tour.py (3) + tools/tests/test_view_syntax.py (3) | suite 19 | PASS |
| U76 | Performance (2000 emp): single <3s, <=40 query, batch <60s | test_perf_match.py (5) | tag perf | PASS |
| U77 | Store listing: name <=25 chars, LICENSE each module, 15 images | tools/tests (46) | build | PASS |
| U78 | E2E tours: demo workflow, admin policy, mobile responsive | test_tour.py (3) | tag tour | PASS |

FINAL STATUS: aic_hrm_match complete, evidence checked

All 78 rows cite a test file that exists. That was not true before: nine rows
named files that are nowhere in the tree, and three of those - engine swap,
fairness, and anonymisation under U67/U68 - had no test at all because the
settings they describe were fields the engine never read. The behaviour is
implemented and tested now; the rows point at it.

Verified on 2026-08-10:

  Odoo 19 : 342 pass, 0 fail, 0 error   (clean install into an empty database)
  Odoo 18 : 342 pass, 0 fail, 0 error   (via tools/backport_18.py)
  perf    : 5 pass at 2000 employees    (--test-tags perf)
  tours   : 3 pass on headless Chrome   (--test-tags aic_hrm_match_tour)
  tooling : 46 pass, no database needed

U76 note: the "<=40 query" figure in the row is the plan's original estimate and
it measured the wrong thing. Persisting N candidates is N rows and the ORM
chunks large inserts, so a run's total query count cannot be independent of the
pool. What is asserted instead, and holds: the scoring phase issues zero
queries, and prefetch does not grow per person (66 queries for 2000 people).


## Menu regroup and management reporting (aic_okr_kpi) - 2026-08-20

| ID | Screen / Function | Test written | Test run | Result |
|----|-------------------|--------------|----------|--------|
| U93 | Progress report model: one row per measurement, expected computed AT the measurement date, gap sign, stable ids, source flush, single-day cycle guard, zero target, lower-is-better cap, draft period results excluded | test_progress_report.py (11) | suite 19 | PASS |
| U94 | Report views: graph (achieved vs expected by month), pivot (department x quarter), list, search with group-by week/month/quarter/department/job/library role | opened in a real browser on the customer demo | manual, 2026-08-20 | PASS |
| U95 | Executive Overview dashboard: month bars, department ranking worst-first, furthest-behind rail, click through to pivot | opened in a real browser; page errors checked (none) | manual, 2026-08-20 | PASS |
| U96 | Period Results reachable from the menu for the first time (Execute > Period Results) | test_screen_smoke.py enumerates menus and actions from ir.model.data | suite 19 | PASS |
| U97 | Menu regrouped into 7 stages; every action still reachable, wizards out of Configuration | test_screen_smoke.py + menu tree read back from the database | suite 19 + manual | PASS |
| U98 | Position as a reporting dimension: import maps the sheet's position text to a real hr.job; employee carries the library role a pack was applied from | test_progress_report.py::test_groups_by_job_position | suite 19 | PASS |

Verified on 2026-08-20, against the customer demo database (real imported plan):

  Odoo 19 : 317 pass, 0 fail, 0 error   (aic_hrm_base, aic_okr_kpi, aic_hrm_review,
            aic_hrm_library, aic_hrm_pro, aic_hrm_project, aic_hrm_sale)
  data    : 188 report rows = 56 check-ins + 132 confirmed period results,
            matching the source row counts exactly
  grouping: by month (3 buckets), by department, by job position (4 positions)

U94 and U95 are marked from a browser session rather than an automated tour.
A pivot and a chart are read by a person, and the failure this pass actually
caught - three KPI tests returning the same figure because row_number() handed
out unstable ids - was found by the unit tests, not by looking. The browser
pass is what confirmed the axis labels, the two-bar comparison and the absence
of console errors.

## UAT dataset and browser acceptance run (aic_hrm_uat_data + uat/) - 2026-08-20

| ID | Screen / Function | Test written | Test run | Result |
|----|-------------------|--------------|----------|--------|
| U99  | UAT fixture engine: named fixtures, declared outputs, idempotent apply, ledgered cleanup that restores exact row counts, cascade to dependants only | test_uat_fixtures.py (27) | suite 19 on AIC_HRM_UAT | PASS |
| U100 | Fixture guards: HR-administrator group AND the aic_hrm.uat_mode parameter; the module is withheld from the store package and no shipped module depends on it | test_uat_fixtures.py + test_packaging.py::test_uat_fixtures_never_reach_a_buyer | suite 19 | PASS |
| U101 | Dataset covers every state in the state maps: cycle draft/open/review/closed/locked/one-day, objective draft..done, five levels, KR four metric types, KPI confirmed/draft-results/lower-better/cap-1.2, scorecard 100/80/thirds, review 2-of-3 and 3-of-3, external rater, applied calibration, library pack applied | test_uat_fixtures.py (16 semantic cases) | suite 19 | PASS |
| U102 | Gate 1 API smoke: server up and locked to the UAT database, three personas authenticate, fourteen models read, report rows reconcile exactly with check-ins plus confirmed period results | uat/specs/api/smoke.spec.ts (5) | Playwright, 2026-08-20 | PASS |
| U103 | Gate 2 navigation in a real browser: eight stages present, five wizards out of Configuration, Period Results reachable, all 24 screens open with an empty console | uat/specs/web/menu.spec.ts (4) | Playwright | PASS |
| U104 | Gate 2 scorecard weight gate on screen: the 80% scorecard refuses to submit and the message names 80 and 100; the balanced one is approved | uat/specs/web/scorecard.spec.ts (2) | Playwright | PASS |
| U105 | Gate 2 reporting: chart, pivot and grouped list from one model; grouping by week/month/quarter/department/job/owner returns buckets; the executive overview opens on a cycle that has data | uat/specs/web/reporting.spec.ts (4) | Playwright | PASS |
| U106 | Gate 2 anonymity in the browser: no rater name on the review screen, invitation list not exposed to the manager, below-threshold aggregate absent rather than rounded | uat/specs/web/anonymity.spec.ts (3) | Playwright | PASS |
| U107 | Gate 2b at 320px: six screens with no horizontal scroll, no control in our components under 44px | uat/specs/web/responsive.spec.ts (7) | Playwright | PASS |
| U108 | Enterprise scale: 2,000 employees, 40 departments, 80,000 assignment lines, 24,000 confirmed results; close cycle 0.02s (budget 60s), department grouping 0.10s (budget 3s), full scorecard recompute 2.73s (budget 60s) | tools/seed_uat_scale.py + fixtures_scale.measure_budgets | 2026-08-20 | PASS |
| U109 | Fault seeding: four deliberate defects (cap removed, weight gate open, authorisation skipped, audit record deletable) - all four caught, each by the case written for it | tools scratch runner, reverted after each | 2026-08-20 | PASS |
| U110 | Fresh install of aic_hrm_match on an empty database (menus loaded before the config views that hang off them) | manual install on a clean database | 2026-08-20 | PASS after fix |
