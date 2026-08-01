# Kế hoạch: AIC HRM Pro — Suite OKR/KPI Performance cho Odoo 19 (Apps Store)

## Bối cảnh (Context)

Xây suite addon thương mại `aic_hrm_pro` cho Odoo 19 Community, bán trên Odoo Apps Store (author AIPOWER CO.,LTD, license OPL-1). Đợt 1 tập trung **quản lý hiệu suất OKR/KPI full-suite**: OKR + KPI engine + check-in + review cycle + 360 feedback + calibration + 9-box + dashboard. Khách demo đầu tiên: phòng DLSP (~12 nhân sự) với data thật tại `Docs/Requirements/2026.05.31_OKR_KPI_Phong DLSP.xlsx` (3 sheet: OKR_2026 gồm 6 Objectives trọng số 100% → KR; KPI_CHI_TIET gồm 44 KPI có chiều đo/cách tổng hợp/trọng số/nguồn đo; PHAN_CONG gán KPI cá nhân tổng trọng số 100%).

**Research đã chốt khoảng trống thị trường:** chưa addon Odoo nào hợp nhất OKR + KPI engine đúng nghĩa + review cycle; rất ít addon đã port lên Odoo 19. Chuẩn áp dụng: Google OKR (điểm 0.0–1.0, RAG, committed/aspirational, check-in confidence), KPI Institute (hồ sơ KPI đầy đủ), ISO 30414 (thư viện KPI HR), SuccessFactors patterns (route map, calibration, snapshot/version, audit trail). Nguyên tắc: mọi cấu hình là dữ liệu, không hard-code.

## Quyết định đã chốt với user

1. **Phạm vi v1: Full performance suite** (OKR + KPI + check-in + review + 360 + calibration + 9-box).
2. **Community-first** — chỉ depend `hr`, `mail`, `web`; KHÔNG dùng hr_appraisal/survey/gamification (Enterprise/vắng mặt).
3. **Tích hợp Odoo HR**: dùng `hr.employee`, `hr.department`, manager chain làm nền nhân sự/phòng ban.
4. **Nhập liệu 4 đường**: wizard import Excel 3-sheet + nhập trực tiếp form + **nhân bản từ kỳ/năm cũ (rollover wizard)** + demo data đóng gói.
5. **Kiến trúc suite độc lập nhiều module — TÁCH BIỆT HOÀN TOÀN khỏi `aic_mcn_*`** (quyết định user tại eng-review: "aic_mcn không liên quan gì đến aic_hrm_pro"). Không depend, không port code (aic_mcn là AGPL + comment tiếng Việt — port thực chất đắt ngang viết mới và mang rủi ro provenance vì cùng repo có code OCA). Kế thừa chỉ 2 nguồn: (a) Odoo core `hr`/`mail`/`web`: depend + `_inherit` chuẩn (tab OKR/KPI trên hr.employee, chatter làm audit trail); (b) addon bên thứ ba (Viindoo/Kaizen/Cybrosys/OCA): chỉ làm benchmark tính năng. Toàn bộ foundation (cycle, mixins, state machine, revision) viết mới trong `aic_hrm_base`, tiếng Anh, OPL-1, provenance sạch 100%.
6. **Toàn bộ source code, comment, docstring, hằng số, tên test: TIẾNG ANH 100%** (điều kiện bán Apps Store quốc tế). UI string viết tiếng Anh trong code, **đa ngôn ngữ 3 thứ tiếng qua i18n**: `i18n/vi.po` (đầy đủ — thị trường chính), `i18n/ja.po` (có, nhưng đánh dấu chất lượng draft — dịch máy tiếng Nhật cho sản phẩm quản trị là rủi ro, cần người bản ngữ duyệt trước khi công bố JA support chính thức; trạng thái "chưa đủ" phải hiện rõ, không lặng lẽ fallback). Namespace mới `aic.hrm.*` (tránh đụng `aic.mcn.kpi.*`).

## Truy vết tính năng ← chuẩn thế giới (kết quả deep research)

Mỗi năng lực trong thiết kế đều lấy từ benchmark cụ thể, chia 6 layer:

| Layer | Tính năng trong aic_hrm_pro / aic_okr_kpi | Học từ đâu |
|---|---|---|
| **(a) Goal Management** | Objective đa cấp company→dept→team→individual; parent tree + đồ thị "contributes-to" mềm xuyên cấp; committed vs aspirational; tách OKR (thay đổi) vs KPI (vận hành/BAU) | SAP SuccessFactors (align bất kể cấp), Betterworks (cascade real-time), Perdoo ("KPI giữ sức khỏe, OKR tạo thay đổi"), Google (committed/aspirational) |
| **(b) Measurement & Scoring** | Điểm 0.0–1.0, sweet-spot 0.7, RAG 0.4/0.7 cấu hình được; KR 4 kiểu metric; hồ sơ KPI đầy đủ (định nghĩa, công thức, nguồn đo, tần suất, chiều tốt, leading/lagging, baseline/target); trọng số + composite; thư viện KPI ISO 30414 (69 chỉ số/11 nhóm); auto-pull số liệu từ model Odoo | Google re:Work (thang điểm), KPI Institute/KPI.org (KPI documentation form), Kaplan-Norton BSC (leading/lagging, weight), ISO 30414:2025, WorkBoard/Profit.co/Tability (data connector — 100+ connector) |
| **(c) Cadence & Rituals** | Check-in tuần/tháng (value + confidence 1–10 + blocker), nhắc tự động, phát hiện stale goals, chấm điểm + retrospective cuối kỳ, rollover kỳ mới | 15Five (weekly check-in nhẹ), Perdoo (OKR quý → check-in tuần), Adobe Check-in (thay annual review), chống anti-pattern "set-and-forget" |
| **(d) Review & Talent** | Review cycle theo template + route map nhiều stage (self→manager→peer→calibration→sign-off); 360 ẩn danh min-3-raters; calibration bắt buộc justification; 9-box performance×potential; IDP | SAP SuccessFactors (route map, form template, khóa chữ ký), Lattice/Leapsome (calibration kéo-thả, 9-box), CCL/DecisionWise (chuẩn 360: rater đề xuất-duyệt, ẩn danh ≥3), GE (9-box gốc) |
| **(e) Governance & Admin** | Cycle first-class multi-cycle song song; snapshot/version target giữa kỳ có lý do + phê duyệt; audit trail chatter; phân quyền manager-chain; multi-company; mọi ngưỡng/workflow là dữ liệu cấu hình | SuccessFactors (audit trail pháp lý, route map cấu hình), Workday (multi-cycle), nguyên tắc "config as data" giúp các nền tảng lớn scale |
| **(f) Analytics & Intelligence** | Alignment tree OWL màu RAG; heatmap tiến độ phòng/cá nhân; histogram phân bố điểm (phát hiện lệch/bias); confidence trend cảnh báo sớm KR rủi ro | Betterworks (visibility real-time), Lattice (phân tích phân phối điểm giữa manager), Quantive (strategy execution dashboards) |

Ba nguyên tắc rút ra chi phối thiết kế: (1) tách OKR khỏi bonus (chống sandbagging — bonus gắn KPI/committed), (2) mọi cấu hình là dữ liệu không hard-code, (3) nhịp check-in + audit trail là xương sống chống "set-and-forget".

## Kiến trúc module

```
hr, mail, web → aic_hrm_base → aic_okr_kpi → aic_hrm_review → aic_hrm_pro (meta, application=True, price)
```

- **`aic_hrm_base`**: cycle (chu kỳ — first-class, **đăng ký tự do: loại năm/nửa năm/quý/tháng/tùy chỉnh với start–end bất kỳ**; dùng cho cả KỲ KẾ HOẠCH (gắn OKR/KPI) lẫn KỲ ĐÁNH GIÁ (review cycle của aic_hrm_review trỏ về một perf cycle); nhiều kỳ chạy song song, lồng nhau qua parent_id; states draft→open→review→closed→locked, lock chặn write xuống children), RAG profile cấu hình được (mặc định 0.4/0.7), metric source (auto-pull số liệu từ model Odoo bất kỳ: model+domain+field+aggregate), target revision (snapshot đổi target giữa kỳ có lý do + phê duyệt), mixins (owner, scoring), utils (hàm chuẩn hóa điểm thuần — unit-test không cần ORM), security groups user < manager < admin + record rules theo manager chain (`child_of` trên hr.employee), menu gốc "Performance", sequences.
- **`aic_okr_kpi`** (giá trị thương mại lõi): 
  - `aic.hrm.objective` (level company/department/team/individual, weight %, committed/aspirational, parent tree `_parent_store` + M2m `contributes_to_ids` đồ thị mềm, workflow draft→…→done, score = Σ KR có trọng số); **alignment xuyên chu kỳ (eng-review 1A)**: parent/contributes-to chấp nhận objective CÙNG chu kỳ hoặc thuộc CHU KỲ CHA (quý→năm, tháng→quý theo `cycle.parent_id`) — roll-up điểm xử lý cả 2 nhóm con, cấm mọi quan hệ chu kỳ khác;
  - `aic.hrm.key.result` (metric_type number/percent/milestone/boolean, direction higher/lower, baseline/current/target, weight, metric_source, milestones, progress chuẩn hóa 0–1, confidence, stale detection);
  - `aic.hrm.kpi` (định nghĩa/thư viện theo form KPI Institute + template ISO 30414, `is_template`), `aic.hrm.kpi.target` (KPI trong chu kỳ: aggregation last/average/sum ~ cuối kỳ/bình quân/lũy kế, achievement theo chiều đo; **direction/aggregation/unit kế thừa từ kpi_id bằng compute stored + readonly=False — KHÔNG dùng onchange (eng-review 3A), để import/API/rollover đều tự điền đúng và vẫn override được từng target**), `aic.hrm.kpi.period.result` (kết quả tháng/quý);
  - `aic.hrm.kpi.assignment` + lines (scorecard cá nhân, ràng buộc Σweight=100 khi submit, composite score);
  - `aic.hrm.checkin` (chung cho KR và KPI line: value, RAG snapshot, confidence 1–10, blocker; cron nhắc lịch + stale + auto-pull);
  - wizards: `aic_hrm_import_wizard` (Excel 3-sheet, map thuật ngữ Việt → giá trị hệ thống, preview + error report, savepoint; **manifest khai `external_dependencies: {'python': ['openpyxl']}` + try/except ImportError hiện hướng dẫn thay vì traceback — eng-review 4A**), `aic_hrm_rollover_wizard` (copy cấu trúc từ kỳ cũ, reset actuals, giữ target chỉnh được, remap alignment);
  - OWL: alignment tree client action, RAG badge widget; SQL view `aic.hrm.department.scorecard`.
- **`aic_hrm_review`**: review template + stages (route map: self/manager/peer/upward/calibration/final/sign_off), review cycle sinh review theo nhân viên, form/section/question tự xây (không dep survey), 360 feedback ẩn danh (không mail.thread trên request/response, field-level groups che rater, chỉ hiện tổng hợp khi ≥ min_raters=3), calibration session + line (bắt buộc justification khi đổi điểm), 9-box (performance × potential + OWL grid), IDP.
- **`aic_hrm_pro`**: meta-package, demo data đầy đủ **ĐÃ HƯ CẤU HÓA (outside-voice #2)**: cấu trúc giống DLSP (6 objectives Σ100%, ~44 KPI, phân công cá nhân Σ100%, 1 kỳ cũ đã đóng để demo rollover) nhưng tên công ty/nhân sự/mục tiêu là giả định ("Acme Digital Media") — **data thật DLSP KHÔNG đóng gói vào addon, chỉ import vào DB demo local qua wizard**; assets Apps Store.

## Scoring engine (lõi toán)

- Chuẩn hóa 0.0–1.0: number/percent higher `(current−baseline)/(target−baseline)`, lower `(baseline−current)/(baseline−target)`, boolean 0/1, milestone Σweight done; clamp [0, cycle.score_cap] (mặc định 1.0).
- KPI achievement theo kỳ: higher `actual/target`, lower `2−actual/target` (tuyến tính, chặn target>0), pass-fail 0/1; **mọi achievement đều clamp [0, cycle.score_cap] kể cả bản "thô" hiển thị (outside-voice #9 — không bao giờ hiện điểm âm hay 200% vô nghĩa trên cockpit; giá trị actual gốc vẫn hiện bên cạnh)**; tổng hợp cycle theo aggregation (last/average/sum) trên period results đã confirm.
- Roll-up: Objective = Σ(KR.score×weight)/Σweight → điểm phòng/công ty theo trọng số Objective; cá nhân = Σ(line.score×weight)/100. Aspirational tách riêng `committed_score`.
- RAG resolve theo thứ tự: override record → KPI definition → cycle → mặc định 0.4/0.7.
- **Enterprise-grade compute (eng-review 2A)**: stored computed + `@api.depends` cho cả chuỗi NHƯNG mọi `_compute` phải batch bằng `read_group` (cấm search/loop per-record); index composite `(cycle_id, employee_id)`, `(objective_id, state)`; import wizard dùng `create` multi + flush theo lô; perf test fixture 2.000 nhân viên/10.000 KR ở CP4 và CP6 với ngân sách: đóng kỳ < 60s, import 10k dòng < 120s, mở dashboard cycle < 3s. Cron đêm recompute an toàn; SQL view cho scorecard.

## Vòng quản trị mục tiêu khép kín (PDCA) — không chỉ lưu trữ, phải QUẢN TRỊ

Yêu cầu user nhấn mạnh: hệ thống phải quản trị mục tiêu trọn vòng đời — có giám sát liên tục, kiểm soát thay đổi, và quy trình đánh giá — chứ không phải form nhập số. Thiết kế ánh xạ 4 khâu:

**PLAN — Đăng ký & phê duyệt mục tiêu**: Objective/KR/KPI assignment đi qua workflow draft→submitted→approved (manager duyệt, có quyền trả lại kèm lý do); ràng buộc chất lượng ngay từ đầu vào (Σweight=100, objective phải có KR, target≠baseline); khi cycle mở → baseline được chốt (snapshot).

**DO — Thực hiện & check-in**: check-in định kỳ theo tần suất cycle (value + confidence + blocker); auto-pull từ metric source; mọi cập nhật ghi vết chatter.

**CHECK — Giám sát liên tục (mới, thêm vào aic_okr_kpi)**:
- **`aic.hrm.alert.rule`** — engine cảnh báo cấu hình được (rule là dữ liệu, không hard-code): RAG đỏ N kỳ liên tiếp, confidence giảm ≥3 check-in liền, quá hạn check-in (stale), KR không tiến triển sau X% thời gian kỳ, assignment chưa đủ 100% weight sau ngày Y... → sinh activity/notification cho owner, escalate lên manager nếu không xử lý sau Z ngày.
- **`aic.hrm.review.meeting`** — phiên rà soát định kỳ (tháng/quý) là bản ghi first-class: agenda tự sinh từ KR/KPI đỏ + stale + blocker đang mở, danh sách tham dự, biên bản, **action items** có owner/deadline theo dõi đến khi đóng. Khớp trực tiếp KR6.2 của khách DLSP ("duy trì cơ chế báo cáo, rà soát: 16 báo cáo = 12 tháng + 4 quý").
- **Leadership cockpit**: dashboard lãnh đạo (tiến độ theo phòng, KR rủi ro, heatmap RAG, xu hướng confidence) + báo cáo định kỳ tự động gửi manager/lãnh đạo (mail template + cron tuần/tháng).

**ACT — Kiểm soát thay đổi & đánh giá**:
- **Change governance**: mọi thay đổi target/weight/owner/scope giữa kỳ (sau approve) bắt buộc qua `aic.hrm.target.revision` — lý do + người duyệt + lịch sử version đầy đủ, xem được diff các lần đổi; không sửa lùi kỳ đã lock.
- **Đánh giá theo kỳ con (interim evaluation)**: mỗi tháng/quý trong cycle có bước xác nhận kết quả kỳ (nhân viên tự nhận xét → manager confirm period results) chứ không đợi cuối năm; cuối cycle mới vào review cycle chính thức (self→manager→360→calibration→9-box).
- **PIP (Performance Improvement Plan)**: khi composite score dưới ngưỡng cấu hình, hệ thống gợi ý tạo PIP (model trong aic_hrm_review, gắn IDP + mốc kiểm tra 30/60/90 ngày).
- **Retrospective + rollover**: cuối kỳ ghi learnings, carry-forward KR dở dang sang kỳ mới qua rollover wizard.

## Checkpoints thực thi (mỗi CP tự test + commit được, làm liên tục không chờ user)

**Phân phase giao hàng (scope tuyệt đối không đổi — quyết định eng-review D3):**
- **Phase 1 = CP0→CP7**: lõi OKR/KPI + giám sát + import/rollover + dashboard → mốc **DEMO được cho khách DLSP**.
- **Phase 2 = CP8→CP9**: review suite (360/calibration/9-box/PIP) + đóng gói Apps Store — nối liền ngay sau, không chờ lệnh.

**Git repo**: `https://github.com/trungtm78/aic_hrm_pro` — CP0 sẽ `git init` + `remote add origin` repo này; commit theo từng CP (không push trừ khi user yêu cầu).

**Dual-version Odoo 18 + 19 từ v1 (eng-review 5B — quyết định user, mạnh hơn khuyến nghị 5A):**
- Repo theo chuẩn Odoo module: branch `19.0` (primary dev) và `18.0` (backport).
- Dev trên 19 trước; **cuối mỗi phase (sau CP7 và sau CP9) backport sang branch 18.0** và chạy full test trên cả hai — không backport từng CP lẻ để tránh trả phí chuyển đổi 2 lần.
- Kỷ luật code cross-version: tránh API chỉ-có-ở-19 khi có lựa chọn tương đương (khác biệt chính phải cô lập: `res.groups.privilege` chỉ 19 → file security riêng per-branch; OWL/asset khác biệt nhỏ → giữ component thuần); ghi chú khác biệt vào `docs/backport-notes.md` ngay khi gặp.
- CP0 chuẩn bị thêm môi trường Odoo 18 CE (source + DB `AIC_HRM_Pro_18` trên PG18, port 8074) bên cạnh 19 (port 8073).

- **CP0 — Môi trường**: copy source Odoo 19 CE theo layout AIC_Sale Pro sang `C:\AIConnect\AIC_HRM_Pro` (`addons/`, `addons_hrm/`, `odoo.conf` → PG18 @127.0.0.1:5433, user `odoo`, db mới `AIC_HRM_Pro`, port riêng vd 8073), git init + remote `trungtm78/aic_hrm_pro` (branch 19.0 + 18.0), 4 manifest rỗng cài được; **materialize design system: `design.md` + `tokens.css` (Mực & Thép HRM) + `.hallmark/log.json` + spec brainstorming vào `docs/superpowers/specs/`**. Test: server boot + install rỗng.
- **CP1 — aic_hrm_base**: cycle/lock, RAG profile, groups+rules, menu, sequences, target revision, mixins, utils math — **viết mới 100%, không port từ aic_mcn** (chỉ tham khảo pattern qua báo cáo explore, không mở code AGPL khi viết). Tests: test_cycle, test_rag, test_security, unit math.
- **CP2 — OKR core**: objective + KR + milestones, alignment, workflow, roll-up, views. Tests: ma trận metric_type×direction, weighted roll-up, quyền theo workflow.
- **CP3 — KPI engine**: definition/library + ISO 30414 data, kpi.target, period results, achievement (aggregation×direction), target-revision lock. Tests: ma trận đầy đủ.
- **CP4 — Assignment & composite**: Σweight=100 gate, composite cá nhân, department scorecard SQL view, điểm cycle công ty. Tests: rounding float_compare, composite.
- **CP5 — Check-in & giám sát (CHECK layer)**: check-in 2 đường (KR/KPI), crons nhắc + stale + auto-pull metric source; **alert rule engine** (`aic.hrm.alert.rule` + escalation); **review meeting** (agenda tự sinh, action items); báo cáo định kỳ tự động qua mail template + cron; interim evaluation theo kỳ con (confirm period results). Tests: gọi trực tiếp method cron, ma trận rule cảnh báo, vòng đời action item.
- **CP6 — Import & rollover wizards**: parser 3 sheet; **bảng map thuật ngữ ("cuối kỳ/bình quân/lũy kế"→last/average/sum, "Càng cao/thấp càng tốt/Đạt-Không đạt"→direction) là DATA (model `aic.hrm.import.term` + data XML, user mở rộng được cho ngôn ngữ/thuật ngữ khác) chứ KHÔNG hard-code trong source — vừa sạch language gate CP9 vừa mở rộng được (outside-voice #5)**; fuzzy match tên nhân viên có cảnh báo + **tùy chọn "tạo hr.employee/hr.department còn thiếu" ngay trong preview (outside-voice #7 — DB mới import được trọn bộ không cần seed tay)**; preview/error, rollover reset actuals + remap. Tests với fixture .xlsx dựng từ file thật DLSP.
- **CP7 — Dashboards OWL + mốc demo**: alignment tree (expand/collapse, màu RAG), RAG widget, graph/pivot (phân bố điểm theo score_band, confidence trend), **leadership cockpit** (KR rủi ro, heatmap phòng ban, hàng đợi cảnh báo) — **toàn bộ theo Design System "Mực & Thép HRM" (mục Design System phía dưới), load skill dataviz trước khi viết chart, chạy slop-test 58 gates trước khi đóng CP**. Lưu ý Odoo 19: `<list>` thay `<tree>`, không còn `attrs`. **Kèm `vi.po` cho các module Phase 1 ngay tại CP7 (outside-voice #4) — buổi demo DLSP phải chạy giao diện tiếng Việt, không đợi CP9**; CP9 chỉ còn hoàn thiện ja.po + rà soát dịch.
- **CP8 — Review suite (ACT layer)**: template/stage, sinh review, 360 ẩn danh (test leak identity nghiêm ngặt), calibration + justification bắt buộc, 9-box OWL, IDP, **PIP tự gợi ý khi score dưới ngưỡng (mốc 30/60/90 ngày)**. Tests: test_feedback_anonymity là trọng tâm.
- **CP9 — Meta + demo + i18n + đóng gói**: demo data DLSP đầy đủ; **i18n 3 ngôn ngữ**: export .pot chuẩn Odoo → `vi.po` dịch đầy đủ (tự viết tool export/map — không copy tool AGPL của dự án khác) + `ja.po` bản draft (ghi chú cần native review trước khi công bố); static/description Apps Store (EN, có screenshot); test multi-company; full install + upgrade `-u`; kiểm tra tự động không còn chuỗi tiếng Việt hard-code trong source (gate một chiều); chạy UAT demo flow.

Sau mỗi CP: chạy test bằng `PYTHONUTF8=1 python odoo-bin -c odoo.conf -d AIC_HRM_Pro -i <module> --test-enable --stop-after-init`, commit (không push), cập nhật memory resume-point.

## Test bổ sung bắt buộc (eng-review — gap từ quyết định 1A/2A/3A/4A + PDCA)

1. `test_objective_scoring`: thêm ma trận **cross-cycle roll-up** (objective quý contributes vào objective năm; cấm chu kỳ không quan hệ cha-con).
2. `test_kpi_achievement`: thêm case **kế thừa compute stored** — tạo target qua `create()` thuần (giả lập import) phải tự điền direction/aggregation đúng; override tay rồi đổi kpi_id phải recompute.
3. `test_kpi_achievement`: constraint **lower-better yêu cầu target > 0** (case "lỗi = 0" bị chặn với thông báo rõ).
4. `test_import_wizard`: negative cases — file hỏng/sai sheet, mã KPI trùng, Σweight ≠ 100 (báo preview, không commit), **ImportError openpyxl → thông báo hướng dẫn** (mock module vắng).
5. `test_alert_rule` (mới, CP5): ma trận rule (RAG đỏ N kỳ, confidence giảm 3 lần, stale) + escalation lên manager sau Z ngày.
6. `test_target_revision`: sửa weight/target sau approve qua UI path → sinh revision, áp giá trị sau duyệt, chatter ghi vết.
7. `test_perf_enterprise` (mới, CP4+CP6): fixture **đại diện tải thật theo mô hình DLSP nhân rộng (outside-voice #10): 2.000 nhân viên × ~40 KPI assignment lines (~80.000 lines) + 10.000 KR + check-ins** — đóng kỳ < 60s, import 10k dòng < 120s, query dashboard < 3s (đo bằng `time.monotonic`, tag riêng `perf` để không chậm CI thường).
8. Tour E2E (CP7, nâng từ "optional" → bắt buộc 2 tour): (a) tạo cycle→objective→KR→check-in→xem điểm; (b) import Excel→preview→commit→dashboard.
9. `tools/language_gate` (CP9): test tự động quét source không còn chuỗi tiếng Việt hard-code (ngân sách một chiều = 0 ngay từ đầu vì codebase mới).

## Verification tổng thể

1. Toàn bộ test suite pass theo tag từng module.
2. Import file Excel DLSP thật → đối chiếu: 6 objectives tổng weight 100, 44 KPI đúng chiều đo/tổng hợp, phân công mỗi người Σ=100%.
3. Demo flow end-to-end: tạo cycle 2026 → import → check-in vài KR → điểm roll-up đúng tay tính → review cycle → calibration → 9-box → rollover sang cycle mới.
4. Smoke UI qua browser (port 8073) các màn chính + alignment tree.

## Hardening theo Codex review (10 findings — fold toàn bộ, không đổi scope)

1. **Metric source (CX#1)**: thêm `ir.model` allowlist cấu hình (mặc định: model thuộc các app đã cài do HR admin duyệt), chỉ field stored numeric, domain qua `safe_eval` với whitelist operator, `read_group` có limit + timeout; evaluation tôn trọng record rules của người tạo (không sudo mù).
2. **Manager chain (CX#2)**: record rule dùng `child_of` trên `hr.employee.parent_path` + company rule ĐỒNG THỜI; test multi-company + trường hợp employee không có user; dotted-line/acting manager ghi rõ NOT in scope v1.
3. **Chatter leak (CX#3)**: tracking chỉ subtype internal, KHÔNG auto-subscribe ai ngoài owner/manager/HR admin, không email notification cho tracking điểm/blocker/calibration; test follower không được thêm tự do.
4. **Ẩn danh 360 (CX#4)**: response tạo qua system user (`sudo` OdooBot) để `create_uid` không trỏ rater; chặn export/read trực tiếp model response (chỉ đọc qua aggregate compute); tài liệu + UI nói rõ "ẩn danh mức ứng dụng — DBA vẫn có thể truy vấn trực tiếp" (trung thực pháp lý).
5. **Packaging Apps Store (CX#5)**: cả 4 module cùng repo, cùng OPL-1, cùng version; CHỈ `aic_hrm_pro` có `price` (Apps Store tự bundle dependencies cùng repo); các module lõi không bán lẻ trong v1 — nhất quán manifest được test ở CP9.
6. **Dual-version QA (CX#6)**: thêm smoke install + unit test trên Odoo 18 ngay sau CP2 (không đợi cuối phase) để phát hiện lệch API sớm; backport đầy đủ vẫn ở cuối phase (giữ 5B).
7. **Recompute override (CX#7)**: định nghĩa semantics tường minh — đổi `kpi_id` LUÔN ghi đè override (recompute), override chỉ tồn tại khi kpi_id giữ nguyên; test case này đã có ở mục Test bổ sung #2.
8. **Lock scope (CX#8)**: lock chỉ chặn WRITE business fields (target/actual/weight/state/score) qua whitelist field; chatter/attachment/activity/mail vẫn hoạt động; correction sau lock đi qua target.revision với approval của HR admin.
9. **Wizard tạo employee (CX#9)**: option mặc định OFF; employee tạo mới gắn cờ `needs_hr_completion` + company chọn tường minh trong wizard + không có user login; preview hiện danh sách sẽ-tạo để duyệt trước.
10. **ISO 30414 (CX#10)**: thư viện KPI viết wording riêng "inspired by" các nhóm chỉ số chuẩn, không copy nguyên văn definition của tài liệu ISO/vendor.

## Rủi ro & câu hỏi mở (mặc định đã chọn, có thể đổi sau)

- **License**: suite viết mới 100%, KHÔNG chạm code `aic_mcn_*` (quyết định user) — provenance sạch tuyệt đối cho OPL-1/Apps Store; tuyệt đối không copy code AGPL/OPL của bên thứ ba.
- **Ẩn danh 360 trong team nhỏ (outside-voice #10)**: min_raters cấu hình được (mặc định 3) + với nhóm < 6 người hiển thị cảnh báo cho HR rằng ẩn danh số học yếu (suy ngược danh tính dễ), khuyến nghị chỉ dùng aggregate cấp phòng.
- Lower-better với target≈0 ("lỗi = 0"): v1 bắt buộc target>0 hoặc dùng boolean; formula override để v1.1.
- Trọng số Objective: constraint Σ=100 chỉ ở company-level khi đóng cycle; cấp dưới cảnh báo mềm.
- Composite trộn OKR (cap 1.0) và KPI (có thể >100%): composite dùng điểm đã cap, view KPI hiện achievement thô.
- Giá bán từng module trên Apps Store (bán lẻ aic_okr_kpi hay chỉ bundle): quyết ở CP9, không chặn dev.
- Anonymity leak qua `create_uid`/chatter: thiết kế đã né, có test riêng.

## Design System — "Mực & Thép HRM" (Hallmark, custom theme — user đã duyệt)

**Hallmark · v1.1.0**
- **Genre** · modern-minimal (enterprise) · **Tone** · utilitarian-editorial ("hồ sơ đã được kiểm")
- **Theme** · custom (vibe: "ink-on-steel, audited-document, enterprise-calm, no varnish" · paper oklch(98% 0.005 235) · accent oklch(45% 0.14 235) ink-blue · IBM Plex Sans + IBM Plex Mono)
- **Axes** · light / grotesk-sans / cool — khác mọi theme catalog, đồng bộ nhận diện "Mực & Thép" của hệ AIPOWER
- **Enrichment** · none — typography + data thật là nhân vật chính; CẤM glow/gradient/sparkle/glassmorphism/stock-photo
- **Motion** · ≤3 primitive: rag-pulse-once (khi điểm đổi) · row-hover nhấc 1px · focus-ring instant; `prefers-reduced-motion` bắt buộc
- **Slop test** · 58 gates chạy tại build (CP7); honest-copy: KHÔNG bịa metric — mọi con số trên UI/landing đều từ data thật hoặc demo data hư cấu có nhãn

**Token 3 tầng (primitive → semantic → component), OKLCH, materialize thành `tokens.css` + `design.md` tại CP0:**
```
paper 98%/95%/92% + dark-mode paper 16% (tint 235) · ink 20%/40% · rule 88% · muted 50%
accent oklch(45% .14 235) · focus oklch(48% .20 235) · accent-ink = paper
STATUS (semantic, không phải accent): --status-green oklch(60% .13 150) · --status-amber oklch(72% .14 75)
  · --status-red oklch(55% .18 25) · --status-neutral (chưa chấm) — RAG chỉ qua token này, kèm icon/shape
  (không chỉ màu — colorblind-safe), APCA ≥ 3:1 trên paper
Font: IBM Plex Sans (display 600/700 tight -0.02em, body 400) · IBM Plex Mono (mọi con số, tabular-nums)
  · IBM Plex Sans JP cho locale ja — subset VI/JA đầy đủ, không vấp dấu
```

**Áp cho từng bề mặt (Hallmark scope: bề mặt ta kiểm soát trọn; form/list Odoo native chỉ nhận token):**
1. **Leadership cockpit** (OWL client action): bố cục "bàn đọc" — hàng 1: dải sức khỏe cycle (committed score · overall · check-in rate, số bằng Plex Mono cỡ lớn); giữa: heatmap RAG phòng×objective (ô = shape+màu); rail phải: hàng đợi rủi ro (alert + KR ì). Chart theo skill dataviz khi build.
2. **Alignment tree**: cây thụt lề có thanh ray dọc (không bubble-chart), mỗi node: code · tên · owner avatar · RAG dot · score Plex Mono · mini-bar tiến độ; expand/collapse không animation layout (chỉ opacity ≤150ms).
3. **9-box grid**: lưới 3×3 nghiêm, nhãn trục rõ, thẻ nhân viên kéo-thả; thả vào ô khác → modal bắt buộc nhập justification (khớp calibration rule); 8 states đầy đủ cho thẻ kéo.
4. **Check-in flow**: form 1 cột ≤5 trường (giá trị mới · confidence slider 1-10 có nhãn chữ · blocker textarea · RAG preview tự tính), submit = silent success (badge "Đã ghi HH:MM" cạnh nút, không toast pháo hoa).
5. **KPI scorecard cá nhân**: bảng là chính — cột số căn phải Plex Mono, hàng tổng weight có dòng kiểm "Σ = 100% ✓/✗" đỏ khi lệch; progress dùng bar mảnh + số, không donut trang trí.
6. **Trang Apps Store** (`static/description/index.html`): macrostructure **Workbench** (screenshot sản phẩm thật làm hero, không chrome giả), không nav (trang nhúng), footer 1 dòng; copy tiếng Anh, tuân honest-copy.

**8-state bắt buộc** cho mọi widget tương tác (default·hover·focus-visible·active·disabled·loading·error·success) + empty-state có hướng dẫn hành động (không chỉ "No data"). Stamp Hallmark + `.hallmark/log.json` ghi tại CP0; slop-test 58 gates chạy trước khi đóng CP7.

## NOT in scope (đã cân nhắc và hoãn có chủ đích)

- `aic_hrm_appraisal_bridge` (đồng bộ điểm sang hr_appraisal Odoo Enterprise) — backlog sau v1, cần license Enterprise để test (eng-review TODO-A).
- Backport Odoo 17 — chỉ 18+19 trong v1 (quyết định 5B); 17 xét sau theo doanh thu.
- AI insights (tóm tắt check-in, gợi ý viết KR), pulse survey, formula engine tùy biến cho lower-better — v1.1.
- Liên kết bonus/payroll tự động — v1 chỉ export điểm; công thức thưởng để v1.1 (tránh sandbagging OKR, cần thiết kế riêng).
- Mobile app riêng — dùng responsive web Odoo.

## What already exists (tái dùng, không xây lại)

- Odoo core: `hr.employee`/`hr.department`/manager chain (nền nhân sự — theo yêu cầu user), `mail.thread`+`mail.activity.mixin` (audit trail + nhắc việc), graph/pivot view, cron, i18n .po, `res.groups`+record rules.
- `openpyxl` có sẵn trong requirements Odoo (đọc Excel — khai external_dependencies theo 4A).
- Pattern tham khảo (KHÔNG copy code): cấu trúc test `@tagged`, bố cục module, mẫu SQL-view report — học từ báo cáo explore aic_mcn, viết mới toàn bộ.
- KHÔNG tái dùng được (đã xác minh vắng mặt trong Community): hr_appraisal, survey, gamification → 360/check-in/review tự xây là bắt buộc, không phải lựa chọn.

## Ghi chú brainstorming

Spec chi tiết (design doc đầy đủ theo skill brainstorming) sẽ được lưu vào `C:\AIConnect\AIC_HRM_Pro\docs\superpowers\specs\2026-08-01-aic-okr-kpi-design.md` ngay khi bắt đầu thực thi (CP0), trước khi viết code.

## Parallelization (worktree lanes)

| Lane | Bước | Phụ thuộc |
|---|---|---|
| A (chính, tuần tự) | CP0→CP1→CP2→CP3→CP4→CP5 | chuỗi model lõi, cùng module — không tách được |
| B (song song sau CP3) | CP6 wizards (wizard/) | cần model CP2-CP3 ổn định |
| C (song song sau CP4) | CP7 OWL dashboards (static/src/) | cần data model + scoring xong |
| D (sau CP4) | CP8 review suite (aic_hrm_review/) | cần personal score CP4 |

Chạy: A tuần tự; sau CP3 mở B; sau CP4 mở C + D song song (khác module/thư mục, ít conflict); CP9 chờ tất cả. Backport 18.0 ở cuối mỗi phase (5B).

## Implementation Tasks (từ eng-review, đã ghi JSONL cho /autoplan)

- [ ] **T1 (P1)** — Cross-cycle alignment theo `cycle.parent_id` + roll-up 2 nhóm con (1A)
- [ ] **T2 (P1)** — Batch compute read_group + index composite + perf fixture 2.000 NV/80k lines với budget đóng kỳ<60s (2A)
- [ ] **T3 (P1)** — KPI target kế thừa qua compute stored readonly=False, không onchange (3A)
- [ ] **T4 (P2)** — external_dependencies openpyxl + graceful ImportError (4A)
- [ ] **T5 (P1)** — Dual-version: branch 18.0/19.0, backport cuối mỗi phase, cô lập API 19-only, env Odoo 18 port 8074 (5B)
- [ ] **T6 (P1)** — Demo data đóng gói hư cấu hóa; data DLSP thật chỉ import local (OV#2)
- [ ] **T7 (P2)** — Mapping thuật ngữ import thành data model + wizard tạo employee/department thiếu (OV#5, #7)
- [ ] **T8 (P2)** — vi.po Phase-1 giao tại CP7 để demo tiếng Việt (OV#4)
- [ ] **T9 (P2)** — Clamp mọi hiển thị achievement [0, cap], hiện actual gốc bên cạnh (OV#9)
- [ ] **T10 (P3)** — min_raters cấu hình + cảnh báo ẩn danh yếu team <6 (OV#10)
- [ ] **T11 (P3)** — openpyxl read_only=True cho file lớn (perf note)

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex` | Independent 2nd opinion | 2 | DONE (1 Claude subagent + 1 Codex GPT) | Subagent: 10 findings (2 resolved by user decree, 6 folded, 1 → 5B, 1 settled D3). Codex: 10 findings (5 P1), 10/10 folded — mục "Hardening theo Codex review" |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR (PLAN) | 15 issues (5 quyết định 1A/2A/3A/4A/5B + 9 test gaps + 1 perf note), tất cả đã fold vào plan |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

- **CODEX:** 10 findings (metric-source hardening, manager-chain multi-company, chatter/anonymity leak, packaging nhất quán, dual-version QA sớm, recompute semantics, lock theo whitelist field, wizard master-data guard, ISO wording) — 10/10 fold vào mục "Hardening theo Codex review", không finding nào lật kiến trúc.
- **CROSS-MODEL:** 3 hệ (Claude review nội bộ + Claude subagent context sạch + Codex GPT) hội tụ về kiến trúc 4 module + scoring engine; mỗi vòng thêm một lớp: eng-review bắt scale/cascade, subagent bắt data/i18n/sequencing, Codex bắt security-chi-tiết Odoo (chatter, create_uid, safe_eval). Không còn tension mở — mọi disagreement đã thành quyết định (1A/2A/3A/4A/5B) hoặc hardening item.
- **VERDICT:** ENG + CODEX CLEARED — ready to implement (CP0 bắt đầu: chuyển source sang C:\AIConnect\AIC_HRM_Pro, git init repo trungtm78/aic_hrm_pro).

NO UNRESOLVED DECISIONS

## BỔ SUNG SAU DUYỆT (2026-08-02, chỉ thị user)

- Toàn bộ thiết kế UI phải RESPONSIVE chạy được trên điện thoại — chi tiết per-surface tại design.md § Responsive (verify 320/375/414/768px, mốc CP7 + UAT).

