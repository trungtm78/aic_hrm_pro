STATUS: ALL_MILESTONES_DONE

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
