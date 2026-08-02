STATUS: IN_PROGRESS

# PROGRESS
Cập nhật: 2026-08-02T10:35:00+07:00 | Milestone: POST-DELIVERY EXTENSIONS HOÀN TẤT + UAT §9 PASS 100%

## ĐỢT GIAO DIỆN & TÀI LIỆU KHÁCH HÀNG (2026-08-02 chiều)
- [x] i18n: ~70 nhãn UI phổ dụng + vi.po đầu tiên cho aic_hrm_review (commit a23ec81; 18.0 sync b1e52a0 SẠCH sau sự cố rò rỉ đã xử lý).
- [x] Theme: rà toàn bộ C:\AIConnect — bản Spiffy mới nhất là **aic_sale_pro_theme 19.0.1.9.7** (AIC_Sale Pro, kế thừa Spiffy 1.9.7 + style Executive) → đã gỡ spiffy 1.9 và cài bản này vào addons_third/ (GITIGNORE, không commit vì proprietary).
- [x] Nhận diện: logo wordmark "AIC HRM Pro / OKR · KPI · Performance Suite" thay logo Spiffy trên sidebar; PWA + tên công ty + màu #274690/#1c2a4a; 3 icon module vẽ lại (commit a8144af).
- [x] Redesign cockpit + alignment tree theo design system (page head, thẻ số liệu tabular, heatmap chip bo tròn tách mã/điểm, risk rail 2 dòng, cây liên kết có card + hairline) — test dashboard xanh, commit a8144af.
- [~] ĐANG CHẠY: chụp lại 51 ảnh (task beh800xd7) với UI mới → cập nhật Docs/Gioi-thieu-he-thong-AIC-HRM-Pro.html (đã có flow toàn hệ + 11 flow nghiệp vụ + dữ liệu mức bản ghi + bằng chứng E2E) → gửi khách.
- [x] REDESIGN TOÀN HỆ THỐNG (yêu cầu user "không chỉ phần giới thiệu"): gắn class `o_aic_hrm_view` vào 50 view gốc (list/form/wizard) của 6 module + stylesheet mới `aic_okr_kpi/static/src/scss/aic_hrm_views.scss` áp design.md "Mực & Thép" cho MỌI màn hình nghiệp vụ (số tabular mono, list nhịp hàng + kẻ mảnh, badge RAG dùng token dữ liệu, form sheet viền mảnh, tab gạch chân, nút 40px, focus ring tức thì, empty state hướng dẫn, sàn mobile 768). Sửa 2 lỗi phát sinh: view `search` không nhận `class` (gỡ 4 chỗ), thẻ `<header>` chưa đóng trong alignment_tree làm vỡ bundle JS.
- [x] Tour sản phẩm: thêm guard `_skip_if_backend_theme()` — theme bên thứ ba thay app-menu bằng sidebar nên tour tự bỏ qua CÓ THÔNG BÁO trên DB có theme (theme không thuộc sản phẩm bán), vẫn chạy đủ trên môi trường chuẩn.
BƯỚC TIẾP THEO: đợi full suite (log scratchpad/suite_redesign.log) → xanh thì commit redesign + guard tour → backport 18 + sync 18.0 (LUÔN `git checkout 19.0 -- .gitignore` TRƯỚC khi add) → push 2 nhánh → chụp lại 51 ảnh với UI mới → cập nhật + gửi tài liệu khách.

## MỞ RỘNG SAU BÀN GIAO (2026-08-02, theo loạt yêu cầu mới của user)
- [x] Đợt 1 — commit 76987c7 (214 test xanh): diagnosis engine (pace/run-rate/khuyến nghị); module MỚI aic_hrm_library (13 vai trò × 4 ngành, 26 obj templates + 78 KR + 52 KPI, playbook thu thập dữ liệu/vai trò, wizard Apply + Capture); nút "From Previous Cycle"/"From Library" trên list Objectives & KPI Targets; collection_method/guideline trên KPI + tab "How to Collect" trên target; wizard Import Actuals (CSV/XLSX, manual thắng, không đụng confirmed); 5 cấp mục tiêu (company/branch/department/team/individual) + model aic.hrm.team + constraint anchor theo level.
- [x] Đợt 2 — commit c06a071 (221 test xanh): BSC perspectives (model + 4 seed, tag toàn bộ thư viện, related stored trên target); KSF catalog (13 yếu tố seed, objective drive / KPI measure); Knowledge Guide (11 bài phương pháp luận, menu riêng).
- [~] Đợt 3 — ĐANG CHẠY SUITE (task bzl6gczki): multi-framework (aic.hrm.framework: BSC/Hoshin/4DX + 5 dimension mới, m2m framework_dimension_ids trên objective); 6 ngành mới từ agent research (F&B, Xây dựng, Logistics, Y tế, Giáo dục, TMĐT — 12 vai trò; seed giờ 10 ngành/25 vai trò/50 obj/150 KR/100 KPI); vi.po cập nhật (~385 chuỗi dịch cả 3 module, gồm 11 bài Knowledge Guide dịch full).

- [x] Đợt 3 — commit 486fbd4 (223 test xanh) + fix 2ba0660: multi-framework BSC/Hoshin/4DX, 6 ngành mới (10 ngành/25 vai trò/50 obj/150 KR/100 KPI), vi.po ~385 chuỗi; backport 18 verify (216/216 sau fix fixture-trùng-demo); nhánh 18.0 sync b53540b; ĐÃ PUSH cả 2 nhánh.
- [x] UAT §9 theo /uat-test-writer + /uat-test-runner: `docs/uat/` (_domain-pack, _platform.json, _coverage-ledger 53/53 U-row 0 GAP, _uat-run-report). Execute LIVE: suite 19 223/223 + tour E2E Chrome PASS + suite 18 216/216 + perf 3/3. Fault-seeding 4/4 rule trọng yếu bị bắt (clamp, Σ=100, manual-thắng-máy, ẩn danh 360). Verdict đề xuất: GO (chờ chữ ký).

BƯỚC TIẾP THEO (nếu có phiên mới): dự án ở trạng thái HOÀN TẤT + đã push. Việc kế tiếp chỉ khi user yêu cầu (gợi ý: chữ ký sign-off UAT, Apps Store submission, demo DLSP với thư viện mới, vòng axe a11y cho landing page).
LƯU Ý DB DEV: noupdate đã clear cho aic_hrm_library + aic_okr_kpi (perspective/ksf/framework); 4 perspective BSC đã backfill framework_id bằng SQL (file noupdate="1" không update record cũ ở chế độ -u — bản cài mới không bị).
SỰ CỐ 2026-08-02 (ĐÃ KHẮC PHỤC): sync 18.0 lần 3 (fae2cd9) lỡ commit + push tài liệu walkthrough chứa DATA THẬT KHÁCH (tên nhân sự DLSP + 51 ảnh) vì nhánh 18.0 chưa có .gitignore guard tại thời điểm add -A. Khắc phục trong ~3 phút: reset --hard về ebaa35f, sync .gitignore TRƯỚC khi staging, commit sạch b1e52a0, push --force-with-lease thay thế tip; verify remote 0 file gioi-*. Rủi ro tồn dư: object cũ có thể còn truy được bằng SHA trực tiếp trên GitHub tới khi GC (repo riêng, không collaborator). QUY TẮC MỚI CHO MỌI LẦN SYNC 18.0: bước 1 luôn là `git checkout 19.0 -- .gitignore`; và grep "gioi" trong staged trước commit.
QUYẾT ĐỊNH USER 2026-08-02: **Odoo 19 là version bán chính** — dev/test/demo/marketing ưu tiên 19; 18.0 chỉ là backport phụ, không để vấn đề 18 chặn giao hàng 19.

Spec gốc: `C:\Users\Than Minh Trung\.claude\plans\t-i-mu-n-t-o-1-noble-moler.md` (plan đã duyệt qua brainstorming + eng-review + codex + hallmark).
Protocol: AUTONOMOUS EXECUTION PROTOCOL (user cung cấp 2026-08-02) — không dừng hỏi, TDD, DoD 6 mục, UAT 100% cuối.

## Đã hoàn thành
- [x] CP0 — môi trường + skeleton + design system — commit dca69ba, fd24310 — 4 module install sạch
- [x] CP1 — aic_hrm_base foundation — commit e0c119a, 73e5954 — 44 tests green, codex 9 findings fixed
- [x] CP2 — OKR core — commit b51d049, 88b63fd, 21bdc12 — 85 tests green trên CẢ Odoo 19 (native) VÀ Odoo 18 (build qua tools/backport_18.py, 6 delta đã tài liệu hóa docs/backport-notes.md); codex 10 findings fixed (record rules chặt, state machine validate trong write, KR freeze sau approve, clamp cap)

- [x] CP3 — KPI engine — commit 6883ede, cadb1ba — 110 tests xanh trên CẢ 19 & 18; codex 8 findings fixed (revision-context hết giả mạo được: cần flag + manager group — helper `_revision_write_allowed` trên owner mixin áp cho objective/KR/kpi.target; state machine kpi.target validate trong write; rules tách read/write; NULL-owner dup; company coherence; template clears company)

- [x] CP4-CP6 — commit 62a75d0 — suite 19 XANH 117 tests + 3 perf (EXIT:0). 4 bug bắt qua TDD đã fix gốc: (1) Odoo 19 chuẩn hóa boolean search thành operator 'in' → _search_is_stale nhận cả 2 kiểu (ghi backport-notes); (2) KR thiếu mail.activity.mixin; (3) fixture classmethod; (4) @api.constrains KHÔNG fire khi field vắng trong vals → validate exactly-one-parent ngay trong create(). Học được: log qua Select-String -Context bị cắt traceback — debug bằng odoo shell (script scratchpad, chạy qua bash stdin để tránh BOM PowerShell).

- [x] Codex review CP4-CP6 — 8 findings (7 fix, 1 false-positive manager_id đã có từ mixin) — commit 495063e, suite xanh lại.

- [x] CP7 — commit cc322de — MỐC DEMO ĐẠT: cockpit + alignment tree OWL (Mực&Thép, RAG shape+màu, responsive, 44px touch), vi.po 195 chuỗi verify thật, tour E2E PASS Chrome thật, suite xanh 19+18; branch 18.0 populated (ba00f1b, 7 delta tự động).

- [x] CP8 DONE + codex hardening (8 findings fix hết; bài học: audit-immutability KHÔNG dựa cờ su — TransactionCase env.su=True; manager mất quyền đọc từng phiếu 360, chỉ còn aggregate count). Commit c543f92 + hardening commit (đang chạy nền bn2x91hhb kèm full suite 2 version).
- [x] CP8 code+test GREEN (15 tests riêng module): review template/route map, review cycle sinh idempotent + goal_score snapshot bất biến, stage progression, manager-only fields validate trong write, 360 ẩn danh (field-level admin-only + rule rater-own + response ghi bởi with_user(SUPERUSER_ID) — KHÔNG sudo vì sudo giữ uid — + aggregate chỉ khi ≥min_raters + reviewee AccessError), calibration justification bắt buộc (snapshot trong create vals trước super), 9-box map band×potential, IDP/PIP (PIP tự sinh 3 checkpoint 30/60/90 khi final_score<0.4). ĐANG CHẠY NỀN beqi3jceh: full suite 19 (4 module) + build 18. Sau đó: commit "CP8", codex review CP7+CP8 (gộp), CP9.

- [x] CP9 DONE — commit 0809b3a (19.0), 18.0 refreshed 5fc87ea. SỰ CỐ ĐÃ XỬ LÝ: commit here-string fail thầm lặng (2>$null che) làm chuỗi lệnh ghi build-18 đè lên branch 19.0 (671b0bd — đã orphan); khôi phục bằng reset --hard 19f2741 + checkout file non-addons từ 671b0bd + salvage test_packaging/ja từ build. QUY TẮC MỚI: commit qua -F message-file, verify `git log -1` + `git status` sau MỖI commit, checkout branch chỉ khi porcelain rỗng.

## HOÀN TẤT — 2026-08-02
Verification cuối: 19.0 = 167/167 xanh (FINAL19:0, P19:0); 18.0 build = xanh sau fix test version-series (P18:0). UAT-COVERAGE.md 39/39 PASS. Branch 19.0 @ add5f3d, 18.0 @ 5fc87ea (+1 sync pending nếu cần — build đã verify, branch sync sẽ làm khi commit tiếp theo). Chưa push (chờ lệnh user).

## Đang làm dở cũ (CP9 — đã xong, sử liệu)
Task: CP9 đóng gói. Đã làm: demo hư cấu Acme Digital Media (aic_hrm_pro/demo — 6 objectives Σ100, KR có số liệu sống, KPI catalog + targets + period results + 2 scorecards Σ100, cycle 2025 đã có để demo rollover, Q2 cascade 1A), manifest aic_hrm_pro (price 149 USD, support, demo), tests/test_packaging.py (manifest coherence CX#5 + LANGUAGE GATE quét tiếng Việt ngoài i18n/import-terms/tests + demo-fictional check), static/description/index.html (Hallmark typography-led, honest copy), icons 4 module, ja.po DRAFT 17 chuỗi (header ghi rõ chưa native-review, fallback English lộ rõ), merge tool nhận --lang.
ĐANG CHẠY NỀN bo9kkx43x: fresh install AIC_HRM_Demo với demo data + full tests.
BƯỚC TIẾP THEO: (1) nếu demo-install fail → sửa demo XML; xanh → commit "CP9"; (2) python tools/backport_18.py + verify 18 + checkout 18.0 refresh từ build + commit; (3) UAT §9: tạo UAT-COVERAGE.md ma trận mọi màn hình/chức năng (Cycles, Objectives+workflow, KRs+milestones, Check-ins, KPI Library/Targets/Periods, Scorecards Σ100, Dept scorecard, Cockpit, Alignment tree, Review meetings, Alert rules, Import, Rollover, Review cycles, 360, Calibration, 9-box, IDP/PIP, i18n vi, tour) — mỗi dòng ánh xạ test đã có (đa số PASS bằng suite tự động) + bổ sung test thiếu → 100% PASS; (4) báo cáo tổng kết §8(a).

## PHASE 1 XONG — đối chiếu spec: OKR core ✓ KPI engine ✓ assignment Σ100 ✓ check-in/alert/meeting (PDCA CHECK) ✓ import/rollover ✓ dashboards ✓ i18n vi ✓ dual-version ✓ perf budget ✓. Chưa làm (Phase 2): review suite CP8, đóng gói CP9, UAT §9. Codex review CP7 diff chưa chạy — gộp vào codex CP8 (ghi chú).

## Đang làm dở (cũ — đã xong, giữ làm sử liệu)
Task: CP7 — OWL dashboards + vi.po → MỐC DEMO DLSP
Đã làm: tokens SCSS (.o_aic_hrm scope, RAG shape+color, responsive 768/414 collapse) + cockpit client action (health strip 4 stat, heatmap dept×objective, risk rail, chọn cycle) + alignment tree client action (indent rails, toggle opacity, KR leaves) + actions/menus (Cockpit seq 5 manager, Alignment Tree seq 25 user) + assets bundle web.assets_backend + test_dashboard.py (wiring) + vi.po ĐẦY ĐỦ cho aic_hrm_base & aic_okr_kpi (menus/states/buttons/errors/cockpit).
ĐANG CHẠY NỀN: task bgp49z0o6 = upgrade + --load-language=vi_VN + full suite (trừ perf).
TIẾN ĐỘ MỚI: vi.po flow chuẩn hóa (Odoo 19 bỏ --i18n-export → dùng `odoo-bin i18n export`; po viết tay thiếu occurrence metadata làm loader crash → giữ bản dịch ở i18n/vi.draft, tool tools/merge_vi_translations.py merge vào .pot bằng polib → vi.po; 63+132 chuỗi dịch, load vi_VN EXIT:0, verify "Hiệu suất"/"Mục tiêu"). Tour E2E PASS trên Chrome thật (selector chuẩn core .o_app[data-menu-xmlid] + stepUtils; tour = kịch bản demo khách). Slop-test tự audit: fix touch target 44px cho tree toggle. Delta 18 #7: @web_tour/tour_utils → tour_service/tour_utils (đã vào backport tool + notes).
BƯỚC TIẾP THEO: (1) đợi task b1f1m0v16 (18 verify) → xanh thì commit "CP7" (toàn bộ static/, i18n/, tours, test_dashboard, test_tour, tools/merge, pot/draft); (2) codex review diff CP7; (3) CP8 review suite RED trước (aic_hrm_review: test_review_flow/test_feedback_anonymity (sudo OdooBot tạo response, create_uid không lộ rater, aggregate chỉ khi ≥min_raters, chặn export)/test_calibration (justification bắt buộc khi đổi điểm)/test_nine_box/test_idp+PIP; models theo spec data catalog; menus; suite; backport; commit); (4) CP9.
File liên quan: addons_hrm/aic_hrm_review/*
BƯỚC TIẾP THEO: TDD RED — viết addons_hrm/aic_okr_kpi/tests/test_assignment.py: (a) aic.hrm.kpi.assignment (employee+cycle unique, line_ids trỏ kpi_target cùng cycle, total_weight compute, submit yêu cầu float_compare(total,100)==0 — draft cho phép lệch, composite score = Σ(line.score×weight)/100, state draft→submitted→approved→done manager-gated theo pattern _validate_state_change hiện có); (b) line unique (assignment,kpi_target), weight>0, score = kpi_target.achievement (hoặc tính lại theo personal_target nếu set); (c) test_perf_enterprise.py tag 'perf': fixture 2.000 employee × 40 kpi target+assignment lines (~80k), đo close-cycle recompute <60s, search dashboard <3s (time.monotonic, skipTest nếu env PERF không bật? — chạy tag perf riêng). (d) SQL view aic.hrm.department.scorecard (_auto=False: dept, cycle, avg objective score, avg composite, employee_count). Models + views (assignment form với checksum row đỏ khi Σ≠100 — design.md), menus "My Scorecard"/"Assignments". Sau đó suite 19 + backport 18 + codex.
File liên quan: addons_hrm/aic_okr_kpi/models/aic_hrm_kpi_assignment.py, report scorecard

## Hàng đợi task kế tiếp
1. CP4 (đang làm)
2. CP5 check-in/alert/meeting → CP9 theo plan

## Quyết định kiến trúc
| Ngày | Quyết định | Lý do | Ảnh hưởng |
|---|---|---|---|
| 2026-08-02 | Repo git chỉ chứa addons_hrm/ + docs/ + design system; KHÔNG commit odoo/ và addons/ (base) | Repo bán hàng chuẩn Odoo Apps Store = module only; source Odoo là runtime local | .gitignore loại odoo/, addons/, *.log, filestore |
| 2026-08-02 | Hoãn dựng env Odoo 18 (port 8074) đến mốc smoke sau CP2 | CP0–CP2 chưa có code đáng backport; tải source 18 đúng lúc smoke (CX#6 yêu cầu smoke sớm sau CP2, không phải tại CP0) | Ghi vào checklist CP2 |

## Assumption đã tự quyết
| Điểm mơ hồ | Diễn giải đã chọn | Căn cứ trong spec |
|---|---|---|
| "chuyển source qua AIC_HRM_Pro" | COPY (không move) source Odoo 19 CE từ AIC_Sale Pro — giữ env cũ nguyên vẹn | Plan CP0: "copy source Odoo 19 CE theo layout AIC_Sale Pro" |

## Trạng thái test
Full suite: chưa có | Patch coverage: n/a | Test fail: không

## Nợ kỹ thuật / rủi ro
(chưa có)

## Mở rộng sau bàn giao — 2026-08-02 (yêu cầu user)
- [x] aic_hrm_project + aic_hrm_sale (thực tích tự động từ task/báo giá/đơn/hóa đơn theo từng staff; setting 1 lần cấp KPI definition; luật tay-thắng-máy) — 15 test mới xanh trên 19+18 — commit 6eee5ef (19.0), f5bfe95 (18.0), ĐÃ PUSH.
- [x] Import file DLSP thật vào DB local (6 obj Σ100, 47 KPI, 8 scorecard) + demo script Docs/demo-script-dlsp.md (5e50471, đã push).
