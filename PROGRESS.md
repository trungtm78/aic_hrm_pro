STATUS: IN_PROGRESS

# PROGRESS
Cập nhật: 2026-08-02T00:55:00+07:00 | Milestone: CP0/CP9 | Task: 1/6 của CP0

Spec gốc: `C:\Users\Than Minh Trung\.claude\plans\t-i-mu-n-t-o-1-noble-moler.md` (plan đã duyệt qua brainstorming + eng-review + codex + hallmark).
Protocol: AUTONOMOUS EXECUTION PROTOCOL (user cung cấp 2026-08-02) — không dừng hỏi, TDD, DoD 6 mục, UAT 100% cuối.

## Đã hoàn thành
(chưa có)

## Đang làm dở
Task: CP0 — dựng môi trường
Đã làm: PROGRESS.md khởi tạo.
BƯỚC TIẾP THEO: robocopy odoo/ + addons/ + odoo-bin + requirements.txt từ "C:\AIConnect\AIC_Sale Pro" sang C:\AIConnect\AIC_HRM_Pro (chạy nền); tạo addons_hrm/ 4 module skeleton; tokens.css + design.md + .hallmark/log.json; odoo.conf (PG18 5433, db AIC_HRM_Pro, port 8073); git init + remote https://github.com/trungtm78/aic_hrm_pro (.gitignore loại odoo/, addons/); createdb role odoo; boot + install 4 module rỗng.
File liên quan: C:\AIConnect\AIC_HRM_Pro\*

## Hàng đợi task kế tiếp
1. CP1 aic_hrm_base (TDD: test_cycle → cycle model → RAG → revision → security → utils)
2. CP2 OKR core (kèm smoke Odoo 18 sau CP2 — quyết định CX#6)
3. CP3→CP9 theo plan gốc

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
