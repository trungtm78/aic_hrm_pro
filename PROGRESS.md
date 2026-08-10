STATUS: IN_PROGRESS

# PROGRESS
Cập nhật: 2026-08-10 23:59 | Milestone: CP4/10 (aic_hrm_match) | Task: CP4 xong, CP5 tiếp theo

## DỰ ÁN ĐANG CHẠY — addon mới `aic_hrm_match` (Staffing Match)

Plan đã duyệt: `C:\Users\ADMIN\.claude\plans\t-i-mu-n-t-o-1-tingly-allen.md`
(qua `/plan-eng-review` 14 finding + Codex 2 vòng 52 finding — tổng 88, đã fold hết).
Nhánh làm việc: **19.0** (source of truth; 18.0 sinh bằng `tools/backport_18.py`).

### Đã hoàn thành
- [x] CP0a-1 Môi trường: clone Odoo 19.0 CE → `./odoo`, Odoo 18.0 CE → `./odoo18` (cả hai shallow,
      đã gitignore). PostgreSQL 18 chạy sẵn ở 127.0.0.1:5433. `hr_skills` có ở cả hai series.
- [x] CP0a-3 `tools/backport_18.py`: viết lại `_transform_constraints` bằng **AST** thay regex, thêm
      `verify()`. TDD: 15 test ở `tools/tests/test_backport.py`, RED→GREEN.
      Backport thật: 28 file transformed, `verify()` sạch, `compileall` sạch.

- [x] CP0a-2 `LICENSE` (OPL-1 nguyên văn) ở gốc repo + copy y hệt vào **cả 8 module**.
      Gate `test_every_module_ships_its_license` so khớp nội dung, không chỉ sự tồn tại.
- [x] CP0a-4 `tools/build_store_package.py` viết lại: `--series {19.0,18.0}` + `--source` mặc định
      theo series (18.0 ⇒ `build/18.0`, **không** phải `addons_hrm`), `PRICED_APPS`, `check()` nhận
      `is_app`/`series`, kiểm LICENSE + độ dài tên + bundled-không-được-có-giá +
      `defines_ui()` mới đòi `vi.po`. Output vào `dist/<series>/`.
- [x] CP0a-5 Đổi display name **8 listing** về ≤25 ký tự, bỏ tên công ty (bảng bên dưới).
- [x] CP0a-6 `CLAUDE.md`: dependency theo dòng sản phẩm, luật tên store, LICENSE mỗi module,
      môi trường Python 3.12/venv, `--log-level=test`, mục "Release plumbing".
- [x] CP0a-7 **Baseline: 220 test, 0 failed, 0 error** trên Odoo 19 (DB `AIC_BASELINE`).

### Đổi tên listing (CP0a-5)
| Module | Cũ | Mới | Dài |
|---|---|---|---|
| aic_hrm_base | AIConnect HRM Base - Cycles, Scoring & Access (45) | OKR Base | 8 |
| aic_okr_kpi | AIConnect OKR & KPI Engine (26) | OKR KPI Engine | 14 |
| aic_hrm_library | AIConnect HRM Library - Industry OKR/KPI Packs (46) | OKR KPI Library | 15 |
| aic_hrm_review | AIConnect HRM Review - 360, Calibration & 9-Box (47) | Appraisal 360 | 13 |
| aic_hrm_project | AIConnect HRM - Project Bridge (30) | OKR Project Link | 16 |
| aic_hrm_sale | AIConnect HRM - Sales Bridge (28) | OKR Sales Link | 14 |
| aic_hrm_pro | AIConnect HRM Pro - OKR, KPI & Performance Management (53) | OKR KPI Performance | 19 |
| aic_hrm_brand | AIConnect HRM - White Label (27) | HRM White Label | 15 |

- [x] **CP0b** Scaffold 3 module mới + gate packaging mở rộng cho 10 module:
      `aic_hrm_match` (Staffing Match, 25 USD, `application=True`, depends
      `hr,hr_skills,project,mail,web`), `aic_hrm_match_okr`, `aic_hrm_match_timesheet`
      (miễn phí, `auto_install=True`). Icon + banner sinh bằng `tools/make_match_icons.py`
      (generator, không phải PNG mờ ám). `index.html` 10 section theo luật sanitiser của store.
      Test mới: standalone không chạm suite hiệu suất · connector free+auto_install ·
      RST của mọi `description` hợp lệ.
      **Bằng chứng chạy thật**: `aic_hrm_match` cài trên DB TRỐNG Odoo 19 (49 module, suite hiệu
      suất vẫn `uninstalled`) **và** bản backport cài trên **Odoo 18 thật** (44 module).

- [x] **CP1a** `models/utils.py` — toán chấm điểm, **không import Odoo**: `clamp`,
      `weighted_average`, `normalize` (6 kiểu × 2 hướng, đủ nhánh suy biến theo §4.3 plan),
      `rank_normalize` (**midrank** cho hoà), `half_life_decay`, `inverse_document_frequency`,
      `ancestor_credit`, `tiebreak_salt`.
      TDD RED→GREEN. **35 test, 0 fail; patch coverage `utils.py` = 100%** (`coverage report`).

- [x] **CP1b** Taxonomy: `aic.hrm.match.tag.category`, `aic.hrm.match.tag` (`_parent_store`,
      `ancestor_distance()`, `expand_related()`), `aic.hrm.match.seniority`.
      4 group quyền + `ir.model.access.csv`. i18n **45/45 tiếng Việt**.
      **60 test, 0 fail, coverage models 100%**, xanh trên **cả Odoo 19 và Odoo 18**.

- [x] **CP1c** `aic.hrm.match.skill.compat` — nơi DUY NHẤT biết bản Odoo này lưu hiệu lực kỹ năng
      ở đâu. Dò `_fields` chứ không dò số hiệu series. Field shim `match_valid_from`/`match_valid_to`
      trên `hr.employee.skill` và `match_is_certification` trên `hr.skill.type`.
      **74 test, 0 fail, xanh trên cả 19 và 18**; coverage 99% (2 dòng còn lại chính là nhánh 18,
      được phủ bởi lần chạy trên 18). i18n **54/54**.

- [x] **CP1d+CP1e** `security/aic_hrm_match_rules.xml` lớp **global** (không khai `groups` ⇒ được AND)
      cho `aic.hrm.match.tag` + `tests/test_security.py` (12 case: quyền ghi cấu hình, cô lập đa công ty
      qua `search`/`read`/`read_group`, admin **không** vượt ranh giới công ty).
      **86 test, 0 fail, xanh trên cả 19 và 18.**
      **Fault-seeding đã chạy** (bằng chứng test không rỗng): thêm một rule `[(1,'=',1)]` cho
      `group_match_planner` ⇒ **4/4 test cô lập công ty FAIL đúng như mong đợi**; gỡ fault thì xanh lại.
      (Fault đầu tiên thử — đổi rule global thành group-scoped trên `group_match_user` — **không**
      phải fault thật vì mọi group staffing đều implies `group_match_user`, nên rule vẫn áp. Ghi lại
      để lần sau không tự lừa mình bằng một phép tiêm lỗi vô hiệu.)

- [x] **CP2a** `aic.hrm.match.availability` (AbstractModel service) + `aic.hrm.match.allocation`.
      Toàn bộ tính bằng **đại số khoảng**, quy ra giờ đúng MỘT lần ở cuối:
      `utils.merge_intervals/subtract_intervals/intersect_intervals/interval_hours` (thuần Python,
      100% coverage). `get_gross_intervals` gọi `_work_intervals_batch(..., compute_leaves=False)` —
      tham số này là chỗ chịu lực: để mặc định thì nghỉ phép bị trừ **hai lần**.
      **116 test, 0 fail, xanh trên cả 19 và 18**; coverage 99%. i18n **88/88**.

- [x] **CP2b** Chống double-book: `pg_advisory_xact_lock` namespace riêng `0x41494331`, khoá theo id
      **sắp xếp tăng dần** (chống deadlock), `write` khoá **cả hai đầu** khi chuyển người,
      rồi `flush` → invalidate → **đọc lại** → validate. `_prorated_hours` chia giờ theo **giờ làm việc**
      chứ không theo ngày lịch. Trần vượt công suất là field trên `res.company`.
      **127 test, 0 fail, xanh trên cả 19 và 18**; coverage 99%. i18n **92/92**.

- [x] **CP2c** `aic.hrm.match.profile` (hồ sơ bố trí, rate ẩn bằng **field-level group** vì record rule
      chỉ giấu được hàng chứ không giấu được cột; tạo **lazy** qua `_ensure_profiles`) +
      `aic.hrm.match.request` / `.request.slot` / `.request.slot.skill`.
      **Slot là đơn vị staffing**: `headcount` là compute đếm slot chứ không phải số gõ tay;
      `required_hours` thuộc slot. `task_id` `set null` + snapshot tên; request đã có quyết định thì
      **không xoá được** (phải lưu trữ). Sequence `SR-<năm>-####`.
      **155 test, 0 fail, xanh trên cả 19 và 18**; coverage 99%. i18n **204/204**
      (37 chuỗi tái dùng nguyên văn từ glossary của suite để thuật ngữ không tách đôi).

- [x] **CP2d** `aic.hrm.match.experience` (sổ kinh nghiệm denormalized, khoá duy nhất
      **`(company_id, source, source_key)`** — không phải `(employee, source, task)` vì một người có
      thể giữ hai vai trò trên cùng một task và dòng timesheet không có task ổn định;
      `outcome_score` **để trống** chứ không mặc định; `recency_weight` là field thường + cron)
      và **workflow xác thực chứng chỉ** trên `hr.employee.skill` (`verify_state`, chuyển trạng thái
      cưỡng chế trong `write()`, `verified_by_id` **không nhận từ vals**).
      **175 test, 0 fail, xanh trên cả 19 và 18**; coverage 98%. i18n **236/236**.
      Build store 10 archive/series.

- [x] **CP3a** Danh mục tiêu chí + chính sách chấm điểm có **version**:
      `aic.hrm.match.criterion` (code là khoá registry, `implemented` compute, `param_json` validate,
      `is_sensitive`), `aic.hrm.match.policy` (+`.line`) với `state` draft/active/archived,
      **active VÀ archived đều bất biến**, `action_new_version()` fork kèm trọng số,
      partial unique index "một active per (code, company)" + "một default per company".
      Kích hoạt **fail-closed**: từ chối tiêu chí enabled chưa có scorer, policy rỗng, tổng trọng số 0,
      và `load_balance` trùng tiêu chí `workload_balance`.
      Thêm `match_context.py` (biên chống query trong pha chấm điểm) + `aic.hrm.match.scorer`
      (registry `_score_<code>` / `_prefetch_<code>`) + scorer `availability` đầu tiên.
      **218 test, 0 fail, xanh trên cả 19 và 18**; coverage 98%. i18n **359/359**.

- [x] **CP3b** Engine orchestrator + 5 model: `aic.hrm.match.engine` (13-step pipeline: resolve_policy → build_pool → prefetch → apply_hard_constraints → score → normalize → aggregate → rank + tiebreak_salt) với `run_match()` entry point, `_persist()` batch create candidates + score.line + evidence (KHÔNG silent drop). `aic.hrm.match.run` (reference seq, policy_version, as_of frozen, feature_snapshot + input_hash + parameter_snapshot, state machine) · `aic.hrm.match.candidate` (identity_ref always, employee_id nullable để blind ranking, raw_score + fairness_adjustment, total_score, rank, rejection_code Selection, is_selected compute) · `aic.hrm.match.score.line` (criterion snapshots để survive uninstall, is_missing/is_knockout/passed flags, weighted_score) · `aic.hrm.match.evidence` (One2many cho plural proof/criterion) · `aic.hrm.match.identity` (admin-only ACL, reveal chỉ khi decision chốt). **308 test, 0 fail, xanh trên cả 19 và 18**; coverage 99%. i18n **382/382**. Commit: cdee427 (12 files, 1499 insertions). Bất biến khoá: `len(ranked) + len(excluded) == len(evaluated)` với MỌI persist_mode. Tie-break ổn định theo request.reference + rotation_epoch + employee_id. Pha chấm điểm: 0 query (khoá bằng test).

- [x] **CP4** Hai bridge module mở rộng registry scorer:
      `aic_hrm_match_okr` (depends `aic_okr_kpi`) + `aic_hrm_match_timesheet` (depends `hr_timesheet`, `hr_holidays`).
      Scorers: `performance_score` = trung bình KPI/OKR từ `task.aic_kr_id.score`; `experience_hours` = tổng giờ
      timesheet; `_prefetch_availability` override thêm kỳ nghỉ từ `hr_holidays` vào pool data.
      Pattern: AbstractModel `_inherit = 'aic.hrm.match.scorer'` + `_prefetch_<code>` / `_score_<code>` pair.
      Auto-install: True (kích hoạt sau khi cài `aic_hrm_match`). Commit: c817ad9 (6 files, 124 insertions).
      Backport 18 sạch (không dùng API 19-only). Evidence chain + missing data (None) handling đầy đủ.



### Đang làm dở
Task: CP4 — hai bridge module (aic_hrm_match_okr, aic_hrm_match_timesheet)
Đã làm: CP3b xong; engine + 5 model + test suite đã commit.
BƯỚC TIẾP THEO: Viết 2 bridge module:
  - `aic_hrm_match_okr`: scorer `performance_score` dùng `task.aic_kr_id.score` từ `aic_okr_kpi`
  - `aic_hrm_match_timesheet`: scorer `experience_hours` từ `hr.timesheet` + `_prefetch_availability` override
Depends: `aic_hrm_match` + product-specific (`aic_okr_kpi`, `hr_timesheet`). Auto-install: True.
File liên quan: plan §5.4 (registry), §5.2 (bridge pattern từ `aic_hrm_project`/`aic_hrm_sale`)

### Hàng đợi task kế tiếp
1. CP4 hai bridge (okr, timesheet)
2. CP5 composition nhiều slot (headcount > 1, gán tối ưu)
3. CP6 decision log, waiver, erasure, audit chain

## Quyết định kiến trúc
| Ngày | Quyết định | Lý do | Ảnh hưởng |
|---|---|---|---|
| 2026-08-10 | `backport_18.py` dùng AST thay regex, kèm `verify()` bắt buộc | Regex cũ (`CONSTRAINT_RE`) chỉ khớp đúng 1 hình dạng 4 dòng nháy đơn; message xuống dòng hoặc nháy kép bị **bỏ qua trong im lặng** và `backport()` vẫn báo thành công ⇒ có thể đẩy API 19 vào zip 18.0 bán cho khách | `tools/backport_18.py`, `tools/tests/test_backport.py` |
| 2026-08-10 | Dùng `sql.create_unique_index(...)` thay `sql.create_index(..., unique=True)` | Tham số `unique` **chỉ có ở Odoo 19**; trên 18 gọi thế ném `TypeError` ngay lúc tạo bảng ⇒ module **không cài được**. `create_unique_index` cùng chữ ký ở cả hai series. Đây là **delta thứ 8** giữa 19 và 18, đã ghi vào `Docs/backport-notes.md`; không transform được nên phải viết code di động | `aic_hrm_match_tag.py`, `Docs/backport-notes.md` |
| 2026-08-10 | Kiểm trùng mã thẻ chạy **trước** `super().create()`, không dùng `@api.constrains` | Odoo chạy constrains **sau** khi hàng đã xuống DB, nên unique index luôn nổ trước và user nhận traceback psycopg thay vì một câu tiếng Việt. Index vẫn giữ làm bảo đảm thật khi hai transaction chèn cùng lúc | `aic_hrm_match_tag.py` |
| 2026-08-10 | Quyền trên model chỉ có ở một series cấp qua `post_init_hook`, không qua `ir.model.access.csv` | Odoo 18 có `hr.employee.skill.log` (ghi mỗi lần đổi skill line, đòi quyền HR officer); Odoo 19 đã bỏ model này. Một dòng CSV trỏ tới model không tồn tại làm **hỏng cài đặt** ở series kia. Đây là **delta thứ 10** | `aic_hrm_match_skill_compat.py`, `__init__.py` |
| 2026-08-10 | Không imply `hr.group_hr_user`; cấp ACL + record rule của riêng module trên `hr.employee.skill` | Core 18 đòi HR officer mới ghi được skill line, core 19 cho nhân viên tự quản lý. Mượn nhóm HR sẽ cho planner quyền ghi **toàn bộ hồ sơ nhân sự** — quá rộng cho việc chỉ cần xác thực một chứng chỉ | `ir.model.access.csv`, `aic_hrm_match_rules.xml` |
| 2026-08-10 | Fixture test **không được hard-code số giờ**, phải tính từ capacity thật | Lịch làm việc mặc định của Odoo 18 và 19 đặt giờ nghỉ trưa khác nhau ⇒ cửa sổ 08:00-12:00 cho 4 giờ ở 19 nhưng 3 giờ ở 18. Fixture ghi cứng "4 giờ" xanh ở 19 và vỡ ở 18 vì lý do chẳng liên quan gì tới thứ đang kiểm | `test_allocation_concurrency.py` |
| 2026-08-10 | Bỏ hẳn constraint chống chu trình cho tag | `_parent_store` của Odoo dựng lại `parent_path` trong lúc write và ném `UserError` trước khi mọi model constraint có lượt ⇒ constraint tự viết là **code chết**, đọc vào tưởng có bảo vệ | `aic_hrm_match_tag.py` |
| 2026-08-10 | Trên Odoo 18, lịch sử hiệu lực chứng chỉ **không** lưu vào `hr.employee.skill` mà vào model riêng của addon | Xác minh source: `odoo18/addons/hr_skills/models/hr_employee_skill.py:24-26` có `_sql_constraints unique(employee_id, skill_id)` ⇒ **cấm** 2 kỳ hiệu lực cho cùng skill. Odoo 19 ngược lại cho phép (`hr_individual_skill_mixin.py:68-87` miễn trừ certification khỏi luật overlap) | `skill.compat` (§3.3 plan) |

## Assumption đã tự quyết
| Điểm mơ hồ | Diễn giải đã chọn | Căn cứ |
|---|---|---|
| Canonical store của kỳ hiệu lực chứng chỉ | **Odoo 19 = hàng lõi** (`valid_from`/`valid_to` trên mixin); **Odoo 18 = hàng của addon** vì lõi cấm. Engine chỉ đọc qua `aic.hrm.match.skill.compat`, không bao giờ đọc thẳng field lõi | 19 là bản bán chính (PROGRESS 2026-08-02, §QUYẾT ĐỊNH USER); tái dùng lõi ở nơi lõi làm được là phương án chuyên nghiệp nhất, fallback chỉ ở nơi lõi không làm được |
| `skill.compat` phân biệt series thế nào | Dò `_fields` (`'valid_to' in env['hr.employee.skill']._fields`), **không** đọc số hiệu series | Bản vá nhỏ giữa các release có thể đổi; dò khả năng thì đúng ở mọi bản |

## Bằng chứng xác minh CP0 (đã chạy, không phải suy đoán)
```
odoo/addons/hr_skills/models/hr_individual_skill_mixin.py:56  valid_from = fields.Date(...)
odoo/addons/hr_skills/models/hr_individual_skill_mixin.py:57  valid_to   = fields.Date(...)
odoo/addons/hr_skills/models/hr_skill_type.py:24              is_certification = fields.Boolean(...)
odoo18/addons/hr_skills/...                                   (none of the three exist)
odoo18/addons/hr_skills/models/hr_employee_skill.py:24-26     unique (employee_id, skill_id)
```

## Trạng thái test
- Tooling: **43/43 PASS**
- `aic_hrm_match` trên **Odoo 19**: **218/218 PASS**, coverage `models/` = **98%**
- `aic_hrm_match` trên **Odoo 18** (từ `build/18.0`): **218/218 PASS**
- Suite Odoo 19 baseline: **220 test, 0 failed, 0 error**. Lệnh tái lập:
  ```
  ./.venv/Scripts/python.exe odoo/odoo-bin -c odoo.conf -d AIC_BASELINE \
    -u aic_hrm_base,aic_okr_kpi,aic_hrm_review,aic_hrm_library,aic_hrm_project,aic_hrm_sale,aic_hrm_pro,aic_hrm_brand \
    --test-enable --test-tags 'aic_hrm_base,aic_okr_kpi,aic_hrm_review,aic_hrm_library,aic_hrm_project,aic_hrm_sale,aic_hrm_pro,aic_hrm_brand,-perf,-aic_okr_kpi_tour' \
    --log-level=test --stop-after-init
  ```
- Đóng gói: `build_store_package.py --series 19.0` và `--series 18.0` đều ra **7 archive**, sạch.
  (Trước CP0a, lệnh 18.0 fail 100% module vì `'19.0.'` hard-code ở dòng 50-51.)

## Nợ kỹ thuật / rủi ro
- `gstack-review-log` từ chối JSON hợp lệ trên Git-Bash/Windows ⇒ dashboard review không ghi được.
  Chỉ là bookkeeping, không chặn. Chưa điều tra.
- Listing `aic_hrm_pro` đã publish trên store; đổi display name cần xác nhận với Odoo trước khi submit.
- **Hai venv riêng** (`.venv` cho Odoo 19, `.venv18` cho Odoo 18): Odoo 18 cần `decorator`, 19 đã bỏ.
  Dùng chung một venv sẽ hỏng một trong hai. Đã ghi vào `CLAUDE.md`.
- Warning `<string>:38: (ERROR/3) Unexpected indentation` trong mọi log cài đặt đến từ **module lõi
  `mail` của Odoo**, không phải code của dự án (đã quét toàn bộ 631 module lõi + 11 module nhà: đúng
  1 hit, là `mail`). Không sửa được từ phía ta; ghi lại để lần sau không chẩn đoán nhầm.

---

# LỊCH SỬ — sản phẩm AIC HRM Pro (đã bàn giao trước đợt này)

Cập nhật: 2026-08-02T10:35:00+07:00 | Milestone: POST-DELIVERY EXTENSIONS HOÀN TẤT + UAT §9 PASS 100%

## ĐỢT GIAO DIỆN & TÀI LIỆU KHÁCH HÀNG (2026-08-02 chiều)
- [x] i18n: ~70 nhãn UI phổ dụng + vi.po đầu tiên cho aic_hrm_review (commit a23ec81; 18.0 sync b1e52a0 SẠCH sau sự cố rò rỉ đã xử lý).
- [x] Theme: rà toàn bộ C:\AIConnect — bản Spiffy mới nhất là **aic_sale_pro_theme 19.0.1.9.7** (AIC_Sale Pro, kế thừa Spiffy 1.9.7 + style Executive) → đã gỡ spiffy 1.9 và cài bản này vào addons_third/ (GITIGNORE, không commit vì proprietary).
- [x] Nhận diện: logo wordmark "AIC HRM Pro / OKR · KPI · Performance Suite" thay logo Spiffy trên sidebar; PWA + tên công ty + màu #274690/#1c2a4a; 3 icon module vẽ lại (commit a8144af).
- [x] Redesign cockpit + alignment tree theo design system (page head, thẻ số liệu tabular, heatmap chip bo tròn tách mã/điểm, risk rail 2 dòng, cây liên kết có card + hairline) — test dashboard xanh, commit a8144af.
- [~] ĐANG CHẠY: chụp lại 51 ảnh (task beh800xd7) với UI mới → cập nhật Docs/Gioi-thieu-he-thong-AIC-HRM-Pro.html (đã có flow toàn hệ + 11 flow nghiệp vụ + dữ liệu mức bản ghi + bằng chứng E2E) → gửi khách.
- [x] REDESIGN TOÀN HỆ THỐNG (yêu cầu user "không chỉ phần giới thiệu"): gắn class `o_aic_hrm_view` vào 50 view gốc (list/form/wizard) của 6 module + stylesheet mới `aic_okr_kpi/static/src/scss/aic_hrm_views.scss` áp design.md "Mực & Thép" cho MỌI màn hình nghiệp vụ (số tabular mono, list nhịp hàng + kẻ mảnh, badge RAG dùng token dữ liệu, form sheet viền mảnh, tab gạch chân, nút 40px, focus ring tức thì, empty state hướng dẫn, sàn mobile 768). Sửa 2 lỗi phát sinh: view `search` không nhận `class` (gỡ 4 chỗ), thẻ `<header>` chưa đóng trong alignment_tree làm vỡ bundle JS.
- [x] Tour sản phẩm: thêm guard `_skip_if_backend_theme()` — theme bên thứ ba thay app-menu bằng sidebar nên tour tự bỏ qua CÓ THÔNG BÁO trên DB có theme (theme không thuộc sản phẩm bán), vẫn chạy đủ trên môi trường chuẩn.
- [x] Redesign toàn hệ thống đã commit + push (19.0 `40f12cc`, 18.0 `c90c56d`), chụp lại 51 ảnh với UI mới.
- [x] i18n đợt 2: nhãn trường còn tiếng Anh (Giá trị gốc/đích/thực tế, nguồn số liệu, chẩn đoán tiến độ…) — 19.0 `8c1b60e`, 18.0 `d3161da`, đã push.
- [x] i18n đợt 3: hai module cầu nối chưa có thư mục i18n (Sales Source / Manual figures lộ trên form chỉ tiêu KPI) — 19.0 `f8948ff`, 18.0 `660d331`, đã push.

## ĐỢT WHITE-LABEL + DỊCH TRỌN (2026-08-02 tối) — yêu cầu user: "bỏ hết thông tin odoobot, không muốn user demo biết đây là giải pháp của odoo"
- [x] Module mới **`aic_hrm_brand`** (OPL-1, depends web + aic_hrm_base): tiêu đề tab và favicon theo sản phẩm; chân trang đăng nhập thay dòng quảng bá + gỡ link "Manage Databases"; gỡ mục "Help"/"My Odoo.com Account" khỏi menu người dùng (JS registry); lối vào riêng **`/aic`** giữ nguyên đường dẫn con; đổi tên tài khoản tự động thành **"AIC HRM"** bằng data XML (ship theo module, không phải thao tác tay từng DB); 2 placeholder đăng nhập không có bản dịch trong gói core được khai lại ở module này để i18n/vi.po mang được.
- [x] Trên DB demo: avatar tài khoản tự động = logo thương hiệu, logo công ty, và **154 tin nhắn hệ thống** đã lưu ("Key Result created"…) viết lại sang tiếng Việt.
- [x] 5 test `aic_hrm_brand` xanh — khẳng định từng bề mặt (không còn "Powered by"/"www.odoo.com", tiêu đề mặc định, `/aic` chuyển hướng đúng kể cả có đường dẫn con, tên tài khoản tự động).
- [x] Dịch TRỌN 5 module: 320 chuỗi một dòng + 95 chuỗi nhiều dòng (gồm toàn bộ bài viết cẩm nang tri thức và đoạn khuyến nghị chẩn đoán) + 182 chuỗi module đánh giá → cả 5 module đạt 100% chuỗi dịch được.
- [x] Chụp lại trọn 51 ảnh; trang đăng nhập chụp với `Accept-Language: vi-VN` nên hiện đúng tiếng Việt như người dùng Việt sẽ thấy.
- [x] Tài liệu khách: 6 chỗ nhắc tên nền tảng thay bằng cách diễn đạt theo sản phẩm (bản phát hành 19/18, "nền tảng lõi", địa chỉ `/aic`). Ghi chú trung thực: chỉ thay phần HIỂN THỊ — header bản quyền trong mã, LICENSE và ghi chú bên thứ ba giữ nguyên vì gỡ là vi phạm giấy phép và chúng không hiện với người dùng ứng dụng.

- [x] Toàn bộ test xanh sau đợt này: **303 test / 0 lỗi** (base 56, okr_kpi 166, review 32, pro 12, library 12, project 10, sale 8, brand 7). Test hiệu năng (`perf`) chạy riêng theo đúng quy ước — Odoo tự gán tên module làm thẻ nên phải loại tường minh bằng `-perf`, nếu không nó dựng 2.000 nhân viên/80.000 dòng ngay giữa vòng test thường (đây chính là "treo hạ tầng" đã chẩn đoán nhầm hai lần trước).
- [x] Bài học i18n quan trọng: Odoo **hợp nhất mỗi `.po` với `.pot`** và LOẠI BỎ mục nào `.pot` không khai. Dịch trong `.po` mà quên `.pot` thì màn hình vẫn tiếng Anh, không báo lỗi gì. Ba tiêu đề OWL viết trong đợt redesign rơi đúng bẫy này.
- [x] 20 bản ghi minh họa từ gói thư viện ngành đổi sang tên tiếng Việt (thư viện gốc vẫn tiếng Anh — dịch trọn thư viện là hạng mục bản địa hóa riêng).
- [x] Chụp lại trọn bộ 50 ảnh: giao diện + dữ liệu đều tiếng Việt, không còn dấu vết nền tảng.
- [x] Commit + push: 19.0 `b07382f`, 18.0 `cf6d4a9` (kiểm tra rò rỉ dữ liệu khách: 0 tệp ở cả hai nhánh).

TÌNH TRẠNG: đã giao đủ. Tài liệu khách ở `Docs/Gioi-thieu-he-thong-AIC-HRM-Pro.html` (gitignore, chứa dữ liệu thật DLSP — KHÔNG commit).

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
