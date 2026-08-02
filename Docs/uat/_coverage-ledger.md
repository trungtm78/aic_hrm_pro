# Coverage + Effectiveness Ledger — AIC HRM Pro suite (UAT §9, 2026-08-02)

Nguyên tắc: coverage% TÍNH từ bảng, không tự nhận. TC = test method tự động
(TransactionCase/HttpCase, Postgres thật, 0 mock nội bộ) — đúng định vị UAT
"LIVE, real DB". Ma trận màn hình/chức năng gốc: `UAT-COVERAGE.md` U01–U53;
ledger này nối U-row → coverage item → test → oracle.

## TC_min ensemble (chống lười)

| Mã | Phương pháp | Giá trị | Ghi chú |
|---|---|---|---|
| M1 | Spec coverage items | ≈ 53 U-rows: 106 (AC×2) + EP/BVA/state/decision liệt kê dưới ≈ 187 | đếm từ bảng dưới |
| M2 | ΣV(G) hàm logic dưới test | ≈ 165 (ước lượng inspection: utils 14, scoring chain 38, wizards 52, guards/rules 41, bridges 20 — lizard không có trong venv, đã ghi hạn chế) | sàn branch |
| M3 | FP^1.2 | không ước được FP tin cậy → N/A | |
| M4 | Risk-tier CRITICAL (sản phẩm thương mại, dữ liệu đánh giá con người) | 120 | |
| **TC_min = MAX** | | **≈187** | |

**TC thực tế = 223 method (19.0) — vượt sàn bằng coverage thật, 0 padding.**
Phân bố: base 44 · okr 128 · review 24 · library 10 · project 8 · sale 6 · pro 3.

## Ledger (cov_id → U-row → kỹ thuật → TC → rule_ref)

| cov_id | U-row | Kỹ thuật | TC (file::vùng) | rule_ref | Loại |
|---|---|---|---|---|---|
| COV-CYCLE-STATE | U01 | State transition (0-switch + sneak: illegal jump, direct write) | test_cycle.py (13) | GOV-02 | STATE/RED |
| COV-CYCLE-TREE | U02 | EP (parent hợp lệ/không), decision company | test_cycle.py | GOV-02 | RED |
| COV-RAG | U03 | BVA ngưỡng 0≤amber<green≤1 | test_rag.py | SCORE-01 | BOUNDARY |
| COV-REVISION | U04, U11 | State + decision (approve/reject/forged context) | test_target_revision.py (9), test_objective_workflow, test_kpi_engine | GOV-01 | STATE/SECURITY |
| COV-METRICSRC | U05 | EP model allowlist, RED bad-domain, admin gate | test_metric_source.py | DATA-01 | SECURITY/RED |
| COV-SEC-BASE | U06 | AuthZ matrix nhóm × thao tác | test_security.py (base) | GOV-01 | SECURITY |
| COV-OBJ-FLOW | U07 | State machine 7 trạng thái + manager gates | test_objective_workflow.py | GOV-01 | STATE |
| COV-OBJ-SCORE | U08 | Decision weighted rollup, EP zero-weight, clamp | test_objective_scoring.py | SCORE-01 | GREEN/EDGE |
| COV-ALIGN | U09 | EP cùng-cycle/cha/lạ + đệ quy (sneak) | test_objective_scoring.py | ALIGN-1A | RED |
| COV-KR-MATRIX | U10 | EP 4 metric × 2 direction, milestone weighted, BVA target=baseline | test_kr_progress.py | SCORE-01/02 | EP/BOUNDARY |
| COV-SEC-OKR | U12 | AuthZ own/public/manager-chain/private (10) | test_security.py (okr) | GOV-01, ANON-360 | SECURITY |
| COV-KPI-DEF | U13, U14 | EP direction, RED lower target≤0, template share | test_kpi_engine.py | SCORE-02 | RED |
| COV-KPI-INHERIT | U15 | Decision CX#7 (create thuần/override/switch kpi), unique NULL-owner | test_kpi_engine.py | GOV-01 | DECISION |
| COV-ACHIEVE | U16 | Decision matrix 3 aggregation × 3 direction; draft excluded; clamp | test_kpi_engine.py | SCORE-03 | DECISION |
| COV-PERIOD | U17 | Unique kỳ, BVA ngày, lock guards | test_kpi_engine.py | GOV-02 | RED |
| COV-ASSIGN | U18, U19 | BVA Σ=100 (float_compare), composite, SQL view | test_assignment.py | WEIGHT-01 | BOUNDARY |
| COV-CHECKIN | U20, U21 | XOR parent (sneak vals-thiếu), write-through, stale dual-signature 18/19 | test_checkin_monitoring.py | DATA-01 | STATE/RED |
| COV-ALERT | U22 | Decision rule matrix + escalation + idempotent key | test_checkin_monitoring.py | DIAG-01 | DECISION |
| COV-MEETING | U23 | Agenda tự sinh + action item lifecycle | test_checkin_monitoring.py | DIAG-01 | STATE |
| COV-IMPORT | U24 | EP file hỏng/sheet thiếu/tên lạ, idempotent, no-side-effect preview | test_import_rollover.py | DATA-01 | RED/DATA |
| COV-ROLLOVER | U25 | Idempotent copy + remap alignment | test_import_rollover.py | LIB-01 | GREEN/EDGE |
| COV-DASH | U26 | Wiring + NaN guard | test_dashboard.py | — (Product oracle) | GREEN |
| COV-E2E-TOUR | U27 | E2E journey employee (menu→objectives→cockpit) Chrome thật | test_tour.py (HttpCase, tag aic_okr_kpi_tour) | Personas J1 | E2E |
| COV-I18N | U28, U29 | vi load + ja draft lộ rõ | merge tool + load-language + test_packaging | I18N-01 | DATA |
| COV-REVIEW | U30, U31 | Route-map states + snapshot bất biến | test_review_flow.py | GOV-01 | STATE |
| COV-360 | U32 | AuthZ + anonymity (create_uid/write_uid, aggregate ≥min) (9) | test_feedback_anonymity.py | ANON-360 | SECURITY |
| COV-CALIB | U33 | Justification bắt buộc, applied bất biến mọi user | test_calibration.py (6) | CAL-01 | SECURITY/STATE |
| COV-9BOX | U34 | Decision band×potential 9 ô | test_talent.py | — (Comparable GE) | DECISION |
| COV-PIP | U35 | BVA ngưỡng <0.4, idempotent 30/60/90 | test_talent.py | — (Claim spec) | BOUNDARY |
| COV-PACKAGING | U36 | Manifest coherence + language gate một chiều | test_packaging.py | I18N-01 | AUDIT |
| COV-PERF | U37 | Ngân sách 60s/120s/3s @ 2.000 NV × 80k line | test_perf_enterprise.py (tag perf) | — (spec budget) | PERFORMANCE |
| COV-INSTALL | U38 | Fresh install + demo | AIC_HRM_Demo run | LIB-01 | INSTALL |
| COV-DUAL | U39 | Toàn suite trên build 18 | suite18_run.log | — | COMPAT |
| COV-PROJECT | U40 | Decision count/percent mode, cancelled loại mẫu số | test_task_progress.py (8) | DATA-01 | DECISION |
| COV-SALE | U41, U42 | EP 3 nguồn sale, manual-beats-auto | test_sales_actuals.py (6) | DATA-01 | GREEN/RED |
| COV-DIAG | U43 | BVA pace (behind/on/ahead), khuyến nghị từ data thật | test_diagnosis.py (8) | DIAG-01 | EDGE |
| COV-LIB-SEED | U44 | Đếm ≥25 role×templates×playbook, industry filter EP | test_library.py | LIB-01 | DATA |
| COV-LIB-APPLY | U45 | EP 4 scope (emp/team/dept/company), idempotent, perspective carry | test_library.py | LIB-01, BSC-01 | GREEN/EDGE |
| COV-LIB-CAPTURE | U46 | Parser EP + RED orphan KR | test_library.py | LIB-01 | RED |
| COV-ACTUALS-IMP | U47 | Decision manual/confirmed/auto-draft; CSV EP (delimiter, decimal); RED cột thiếu/code lạ (8) | test_actuals_import.py | DATA-01, GOV-02 | DECISION/RED |
| COV-LEVELS | U48 | EP 5 level × anchor; cascade; unique team (7) | test_levels.py | LEVEL-01 | EP/RED |
| COV-BSC-KSF | U49 | Seed đủ, liên kết 2 chiều, read_group cân bằng | test_strategy.py | BSC-01 | GREEN |
| COV-FRAMEWORK | U50 | Đa framework đồng thời (m2m 2 framework) | test_strategy.py | BSC-01 | GREEN |
| COV-KNOWLEDGE | U51 | Đếm ≥10 bài, phủ 6 category, company scope | test_library.py | LIB-01 | DATA |
| COV-COLLECT | U52 | Related guideline hiển thị trên target | (gián tiếp qua U47 + view load toàn suite) | DATA-01 | GREEN |
| COV-BUTTONS | U53 | Header buttons load (view validate khi install) | suite install validation | — (Product) | GREEN |
| COV-UX | U26/U27 | Design system: RAG shape+màu, 44px touch, responsive 320–768, reduced-motion | design.md gates + slop-test CP7 + tour Chrome | — (ISO 9241/WCAG) | UX |

**Coverage tính từ bảng: 53/53 U-row có ≥1 cov_id; 0 TC mồ côi (mọi test file
xuất hiện ≥1 dòng); GAP: 0.**

### ISO 25010 áp dụng
Functional suitability (toàn bảng) · Security (COV-SEC-*, COV-360) · Performance
(COV-PERF) · Compatibility (COV-DUAL) · Usability (COV-UX, tour) · Reliability
(idempotent crons/imports) · Maintainability (language gate, packaging) ·
Portability (dual-version) — Interaction capability = COV-UX. N/A: Safety
(không điều khiển thiết bị vật lý).

### Mobile-only categories
N/A toàn bộ (lý do trong `_platform.json`: không có platform mobile; app
native bị hủy theo chỉ đạo user 2026-08-02; responsive web đã phủ ở COV-UX).

## Effectiveness — Fault seeding (spec-level, thực thi LIVE)

Xem kết quả chạy tại `docs/uat/_uat-run-report.md` §Fault-seeding: 4 fault
gieo vào 4 rule trọng yếu (SCORE-01 clamp, WEIGHT-01 gate, DATA-01
manual-wins, ANON-360 superuser-write) — kỳ vọng mỗi fault ≥1 TC FAIL; fault
không bị bắt = oracle trang trí → phải sửa TC.
