# Domain Pack — AIC HRM Pro (OKR/KPI performance suite)

Authority Brief: nguồn chân lý nghiệp vụ, mỗi rule có 2 neo (nguồn + vị trí code).
Domain: quản trị hiệu suất doanh nghiệp (không thuộc nhóm regulated pháp lý;
nhạy cảm: ẩn danh 360°, bất biến audit). Research đợt đầu + nguồn ghi tại
`Docs/library-sources.md` và spec `docs/superpowers/specs/2026-08-01-aic-okr-kpi-design.md`.

## Oracle table (rule_id → nguồn → neo code)

| rule_id | Quy tắc (nguồn chân lý) | Nguồn | Neo code |
|---|---|---|---|
| SCORE-01 | Điểm chuẩn hóa 0.0–1.0, clamp [0, score_cap của CHÍNH cycle]; không bao giờ âm/vượt cap | Google re:Work OKR | `aic_hrm_base/models/utils.py` (clamp/progress/achievement), KR/objective/target compute |
| SCORE-02 | Lower-better: achievement tuyến tính `2 − actual/target`, target bắt buộc > 0 | KPI Institute + spec §scoring | `aic_okr_kpi/models/aic_hrm_kpi.py._check_lower_target`, `utils.achievement` |
| SCORE-03 | Aggregation kỳ: last/average/sum CHỈ trên period results đã confirmed | spec §scoring | `aic_hrm_kpi_target._compute_actuals` + `_load_actuals_map` |
| WEIGHT-01 | Scorecard cá nhân chỉ submit khi Σweight = 100 (float_compare, dung sai rounding) | spec §assignment | `aic_hrm_kpi_assignment` submit gate |
| ALIGN-1A | Alignment chỉ trong cùng cycle hoặc cycle cha (quý→năm); mọi quan hệ khác bị chặn | eng-review quyết định 1A | `aic_hrm_objective._check_alignment_cycle` |
| LEVEL-01 | 5 cấp mục tiêu; mỗi cấp phải gắn đúng anchor (branch/dept/team/employee) | user directive 2026-08-02 | `aic_hrm_objective._check_level_anchor` |
| GOV-01 | Sau approve, field trọng yếu chỉ đổi qua target revision có lý do + manager duyệt; context flag không giả mạo được qua RPC | SuccessFactors audit pattern + codex CP2/CP3 | `_revision_write_allowed()` owner mixin; state validate trong write() |
| GOV-02 | Cycle lock = bất biến business fields; kỳ đã confirm không ai sửa ngầm | spec §cycle | `aic_hrm_cycle.ensure_editable`, period result write guards |
| DATA-01 | "Tay thắng máy": collector tự động/import KHÔNG BAO GIỜ đè manual; import không đụng confirmed | user directive | sale/project bridge upsert guard; `aic_hrm_actuals_import_wizard.action_import` |
| ANON-360 | 360°: danh tính rater không suy ra được (kể cả create_uid/write_uid), aggregate chỉ khi ≥ min_raters | CCL/DecisionWise chuẩn 360 | `aic_hrm_feedback` with_user(SUPERUSER_ID), field-level groups |
| CAL-01 | Calibration: đổi điểm bắt buộc justification; line đã applied bất biến với MỌI user | Lattice/SF calibration | `aic_hrm_calibration` |
| DIAG-01 | Khuyến nghị chỉ trích từ dữ liệu thật (blocker/confidence/cadence/task), pace = so với lịch đã trôi | spec CHECK layer | `aic_hrm_diagnosis.py` |
| LIB-01 | Thư viện: built-in cập nhật theo module, tri thức công ty tách riêng theo company; apply là DRAFT để tùy biến; re-apply không nhân đôi | spec + design library | `aic_hrm_library` models/wizards + record rules |
| BSC-01 | Danh mục đọc được theo 4 góc BSC + đa framework (Hoshin/4DX) đồng thời | Kaplan–Norton; Hoshin; 4DX | `aic_hrm_perspective.py`, `framework_dimension_ids` |
| I18N-01 | UI string tiếng Anh trong code; VI đầy đủ; JA draft phải lộ rõ, không silent fallback | Apps Store + user directive | language gate test + po files |

## Personas × Journeys (WEB backend duy nhất — xem `_platform.json`)

| Persona | Journey chính | E2E |
|---|---|---|
| Nhân viên (group_hrm_user) | Xem mục tiêu của mình → check-in KR (value+confidence+blocker) → xem điểm | Tour `aic_okr_demo` (Chrome) |
| Quản lý (group_hrm_manager) | Duyệt objective/scorecard → cockpit → review meeting → confirm period | Tour + suite security tests |
| HR admin (group_hrm_admin) | Cấu hình cycle/RAG/metric source → import Excel/actuals → thư viện/capture | Import + library tests (LIVE suite) |

## Mock-allowlist (D6)

- KHÔNG mock module nội bộ nào. Toàn bộ suite chạy TransactionCase trên Postgres thật.
- Biên ngoài duy nhất: openpyxl vắng mặt (ImportError path) — mô phỏng bằng môi trường, không mock service.

## State-map trọng yếu

- Cycle: draft→open→review→closed→locked (lock một chiều, guard nhóm quyền).
- Objective: draft→submitted→approved→in_progress→self_assessed→manager_review→done (manager-gated tại approved/done).
- KPI target: draft→confirmed→done. Period result: draft→confirmed.
- Assignment: draft→submitted→approved→done (Σ=100 gate tại submit).

## Oracle additions — 2026-08-20 (reporting, menu, dataset)

The rules below cover ground the first pack did not: the management reporting
built in August, the regrouped menu, the two access-control holes the `/cso`
audit found and closed, and the dataset itself. Each keeps the two anchors:
where the truth comes from, and where the code implements it.

| rule_id | Rule (source of truth) | Source | Code anchor |
|---|---|---|---|
| REPORT-01 | Expectation is elapsed time **at the date of the measurement**, not today; a zero-length cycle must not divide by zero | spec CHECK layer + the pace rule in `_compute_pace` | `aic_hrm_progress_report.ELAPSED`, `NULLIF(c.date_end - c.date_start, 0)` |
| REPORT-02 | Progress is answerable by week, month, quarter, department, job position and library role | customer request, 2026-08-20 | `aic_hrm_progress_report` dimension columns; `_extra_select()` hook in `aic_hrm_library` |
| REPORT-03 | A leadership dashboard opens on a cycle that holds measurements, never on an empty one merely because it starts latest | purpose: a dashboard exists to be read at a glance | `report_overview.js.defaultCycleId` |
| MENU-01 | A menu item that creates or changes business data belongs to its stage of the operating loop; only rule-defining items go under Configuration. A wizard is an operation | user directive + PDCA | classification comment in `aic_hrm_base/views/aic_hrm_menus.xml` |
| MENU-02 | Every model holding data a customer asks for must be reachable from the menu | customer request | `aic.hrm.kpi.period.result` action and menu |
| MENU-03 | Every screen opens with an empty browser console | product: a server-rendered screen that throws in the browser is broken for the user | `uat/specs/web/menu.spec.ts` |
| ANON-360b | Authorisation happens **before** any privilege escalation, and a rater with no login can only be transcribed by the HR administrator who invited them | `/cso` audit finding, 2026-08 | `aic_hrm_feedback.submit_feedback` |
| CAL-02 | An applied calibration line cannot be deleted, not only cannot be edited | `/cso` audit finding: an audit record you can delete is not an audit record | `aic_hrm_calibration.unlink` |
| RESPONSIVE-01 | No custom screen scrolls sideways at 320/375/414/768 px | standing user directive | `design.md` responsive rules; verified at 320px in `uat/specs/web/responsive.spec.ts` |
| RESPONSIVE-02 | Touch targets in our own components are at least 44px high | WCAG 2.2 target size + `design.md` | measured in the responsive spec |
| PERF-01..03 | Close a cycle < 60s, dashboard < 3s, roll-up < 60s at 2,000 employees / 80k assignment lines | CLAUDE.md budgets | `tools/seed_uat_scale.py`, `fixtures_scale.measure_budgets` |
| UAT-ENGINE-01..05 | Fixtures are named, reproducible, removable and relative in time | the dataset contract in `aic_hrm_uat_data` | engine docstring + `TestUatFixtures` |
| UAT-GUARD-01/02 | Seeding requires the HR administrator group **and** `aic_hrm.uat_mode`; the module never ships | a seeding RPC on a live database is a hole | `_check_enabled`, `WITHHELD` in `tools/build_store_package.py` |
| INSTALL-01 | A module must install on an empty database, not only update on one that already has its xmlids | Odoo packaging reality: the buyer's install is always a fresh one | data order in `aic_hrm_match/__manifest__.py` |

### Persona × Journey, extended

| Journey | Persona | Where it is exercised |
|---|---|---|
| J-NAV-01..03 navigate the operating loop | HR admin | `menu.spec.ts` (browser) |
| J-REPORT-01..03 read progress, group it, glance at the overview | manager, HR admin | `reporting.spec.ts` (browser) |
| J-REVIEW-01..03 read a review without learning who said what | manager, peer | `anonymity.spec.ts` (browser) + unit |
| J-MOBILE-01 use the product on a phone | manager | `responsive.spec.ts` at 320px |
| J-DATA-01/02 build and remove the acceptance dataset | HR admin | `TestUatFixtures` |
| J-SCALE-01 run an enterprise-sized database | HR admin | `tools/seed_uat_scale.py` |
