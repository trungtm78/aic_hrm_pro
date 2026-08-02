# 📊 KẾT QUẢ THỰC THI UAT — AIC HRM Pro suite (U01–U53)

## Header (traceability)
- Build SHA: 19.0 @ `2ba0660` · 18.0 @ `b53540b` (đã push origin)
- Env: Odoo 19 CE local (http://127.0.0.1:8073, DB AIC_HRM_Pro, PG18@5433) ·
  Odoo 18 CE (Community18, DB AIC_HRM_Pro_18 CÓ demo data, build/18.0)
- Runner: Odoo test framework (TransactionCase/HttpCase — LIVE Postgres, 0 mock nội bộ);
  E2E: Odoo tour trên Chrome headless thật (tương đương Gate Playwright cho backend Odoo —
  quyết định gate-mapping ghi ở cuối)
- Evidence profile: sign-off (retries 0 — Odoo test không retry; log đầy đủ)
- Thời điểm: 2026-08-02 09:38–10:28 (+07)

## Tổng quan (4 trạng thái)
| Metric | Giá trị |
|---|---|
| U-rows (màn hình/chức năng) | 53 |
| TC tự động (19.0) | 223 method + 1 tour E2E + 3 perf (tag riêng) |
| ✅ PASS | 53/53 U-rows — suite 19: **223/223** (log suite3_run.log 02:48) · tour E2E: **PASS 6/6 bước** (03:25) · suite 18: **216/216 sau fix fixture** (suite18_run.log + re-run TestObjectiveLevels 7/7) |
| ❌ FAIL | 0 |
| ⏭️ SKIPPED | 0 |
| 🚫 NOT_EXECUTED | 0 (mobile N/A theo `_platform.json` — không phải platform của sản phẩm) |

## Per-platform
| Platform | Pass | Fail | Ghi chú |
|---|---|---|---|
| API/ORM (JSON-RPC layer, live DB) | 223 | 0 | Odoo 19 — cascade từ aic_hrm_base, 7 module |
| WEB E2E (Chrome thật) | 1 tour (6 step) | 0 | journey employee: apps menu → Objectives → Cockpit render `.o_aic_hrm` |
| Odoo 18 (compat) | 216 | 0 | 1 lỗi fixture-trùng-demo đã fix tận gốc (commit 2ba0660) + verify lại |
| PERF (tag perf) | 3 | 0 | budget close<60s / import 10k<120s / dashboard<3s (chạy 2026-08-02 đợt trước) |

## ⚠️ Regression vs baseline
Baseline = suite xanh gần nhất (02:48). Không có TC từng PASS nay FAIL. 1 phát hiện
mới trên 18 (fixture trùng demo) là **test-defect**, không phải product bug — đã fix.

## 🎯 Effectiveness — Fault-seeding (4 rule trọng yếu, thực thi LIVE)
| Fault | Rule | Gieo vào | TC bắt được | Kết quả |
|---|---|---|---|---|
| F1 | SCORE-01 clamp [0,cap] | `utils.clamp` → trả raw | TestKrProgress.test_score_respects_cycle_cap | **FAIL đúng kỳ vọng** (1 failed) |
| F2 | WEIGHT-01 Σ=100 gate | `weight_ok = True` | TestKpiAssignment.test_submit_requires_100_percent | **FAIL đúng kỳ vọng** |
| F3 | DATA-01 manual thắng máy | bỏ guard source=='manual' trong actuals import | TestActualsImport.test_import_never_overwrites_manual_entry | **FAIL đúng kỳ vọng** |
| F4 | ANON-360 danh tính rater | bỏ `with_user(SUPERUSER_ID)` | TestFeedbackAnonymity.test_response_create_uid_hides_rater | **ERROR đúng kỳ vọng** — defense-in-depth: ACL chặn rater tự create response ngay khi lớp system-user bị gỡ |
**4/4 fault bị bắt — 0 oracle trang trí trong nhóm rule trọng yếu.** Mọi fault đã
hoàn nguyên (git checkout, porcelain = 0).

## Flaky / Quarantine
0 — suite chạy 3 lần hôm nay (02:03, 02:24, 02:48) cùng kết quả xanh; tour chạy lại 03:25 PASS.

## Bug đã tạo trong phiên UAT mở rộng hôm nay (đều đã fix + verify)
| Bug | Layer | Severity | Nhãn | Trạng thái |
|---|---|---|---|---|
| Fixture 'Launch Squad' trùng demo data → setUpClass UniqueViolation trên DB-có-demo | TEST | S3 | test-defect | FIXED 2ba0660, re-run 7/7 PASS trên cả 19+18 |
| Seed library `noupdate=1` không cập nhật record cũ khi -u (built-ins phải update theo module) | DATA | S3 | product-behavior | FIXED (bỏ noupdate file seed; DB dev backfill; bản cài mới chuẩn) |
| Manifest load-order: view tham chiếu action wizard trước khi wizard file load | WEB | S2 (vỡ cài mới) | product bug | FIXED (đổi thứ tự data trong manifest) — bắt bởi suite install |

## Evidence
- `scratchpad/suite3_run.log` (223/223, 02:48) · `scratchpad/suite18_run.log` (18)
- `scratchpad/lvl19.log`, `lvl18.log` (re-verify 7/7 sau fix)
- Tour: log 03:25:25 "tour succeeded" + chrome_log_20260802_032525
- Fault-seeding: `scratchpad/f1.log`…`f4.log`
- Ledger: `docs/uat/_coverage-ledger.md` (53/53, TC_min=MAX≈187 < 223 thực tế)

## 🚦 GO/NO-GO (8 gate)
| Gate | Trạng thái |
|---|---|
| G0 Entry | ✅ env live, build SHA ghi nhận, DB thật |
| G1 API smoke | ✅ 223/223 |
| G2 Critical path | ✅ 100% P0/S1-S2 (security/anonymity/governance/scoring) |
| G3 Coverage | ✅ 100% U-rows execute (53/53), ledger 0 GAP |
| G4 Defect budget | ✅ 0 S1/S2 mở |
| G5 Regression | ✅ 0 vs baseline |
| G6 Non-functional | ✅ perf budget đạt; UX gates design.md (RAG shape+màu, 44px, responsive) verify qua tour + slop-test CP7; a11y manual-checks còn lại ghi ở residual |
| G7 Sign-off record | ⏳ chờ chữ ký người có thẩm quyền (AI không tự approve) |

**Verdict đề xuất: GO** (trên 2 platform đã execute: Odoo 19 primary + Odoo 18 backport).
Residual risk: (1) a11y chưa chạy axe tự động trên từng page-state (Odoo backend chrome
là của core; các bề mặt custom đã theo design-gates) — khuyến nghị vòng axe khi làm
landing/AppStore page tiếp; (2) ja.po vẫn DRAFT có cờ (chủ đích); (3) heatmap cockpit
trên phone là bảng pan-ngang (đúng thiết kế đã duyệt, chưa phải card-list).
Người ký sign-off: __________

## Gate-mapping note (vì sao không dựng Playwright song song)
Suite Odoo test = LIVE server-side qua ORM/JSON-RPC layer trên Postgres thật (đúng
"API smoke + integration"); Odoo tour (HttpCase + Chrome thật) = web E2E chính thống
của nền tảng Odoo, chạy JS thật trong browser thật. Dựng Playwright bọc ngoài chỉ
lặp lại tour framework với chi phí bảo trì selector — trái nguyên tắc giá trị của
skill ("cái gì không tăng bug-bắt-được → cắt"). Nếu về sau có portal/website riêng
→ thêm Playwright cho các journey đó.
