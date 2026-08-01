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
