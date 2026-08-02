# Kịch bản demo DLSP — "Từ Excel sang hệ quản trị" (~25 phút)

## Chuẩn bị trước buổi demo (5 phút, làm sẵn)

1. `python odoo-bin -c odoo.conf` → mở `http://127.0.0.1:8073`, đăng nhập admin,
   ngôn ngữ **Tiếng Việt**.
2. Data DLSP thật đã import sẵn (cycle "DLSP 2026": 6 objectives Σ100%, 28 KR,
   47 KPI, 8 bảng điểm).
3. Mở cycle DLSP 2026 → bấm **Mở** (state Đang mở) để cảnh báo/check-in hoạt động.
4. Tạo sẵn 2-3 check-in trên vài KR (một cái có blocker) để cockpit có dữ liệu sống.
5. Điện thoại kết nối cùng mạng, mở sẵn trang cockpit (màn responsive).

## HỒI 1 — "Đây là file của anh chị" (5 phút): tạo lòng tin

| Bước | Màn hình | Nói gì |
|---|---|---|
| 1.1 | Mở file Excel DLSP quen thuộc | "Đây là file anh chị đang dùng — 3 sheet, mỗi quý tổng hợp tay." |
| 1.2 | **Cấu hình → Nhập từ Excel** → chọn đúng file đó → Xem trước | "Hệ thống đọc đúng ngôn ngữ file của mình: 'càng thấp càng tốt', 'lũy kế', 'cuối kỳ'… Không phải đổi cách làm việc." |
| 1.3 | Màn **Mục tiêu** nhóm theo cycle | "6 Objective, tổng trọng số đúng 100%, 28 KR đã có chủ trì — 30 giây thay vì một buổi họp nhập liệu." |

**Chốt hồi 1:** "Chi phí chuyển đổi bằng 0 — file cũ import 1 lần là thành hệ thống."

## HỒI 2 — "Những gì Excel không bao giờ nói với anh chị" (12 phút): tạo khao khát

| Bước | Màn hình | Hiệu quả chứng minh |
|---|---|---|
| 2.1 | **Bảng điểm cá nhân** bất kỳ | Chỉ vào dòng đỏ **"Σ = 7% ✗"**: "File khai 100% nhưng cộng thật chỉ 7% — hệ thống bắt ngay lỗi phương pháp mà Excel giấu suốt 2 quý. Đây là lý do điểm cuối năm hay cãi nhau." |
| 2.2 | **Bàn điều hành** (Cockpit) | "Trưởng phòng mở 1 màn: điểm tổng, mục tiêu cam kết, tỷ lệ check-in tươi, cột phải là danh sách cần-chú-ý. Không đợi ai nộp báo cáo." |
| 2.3 | **Cây liên kết mục tiêu** | "Từ mục tiêu năm của phòng drill xuống KR từng người. Mục tiêu quý Q2 nối thẳng vào mục tiêu năm — điểm quý tự chảy lên năm." |
| 2.4 | Mở 1 KR → tạo **Check-in** (nhập giá trị + độ tự tin 6/10 + blocker) | "Nhân viên mất 30 giây mỗi tuần. Điểm đổi ngay lập tức trên cockpit — không có 'cuối quý mới biết chết'." Nhập blocker: "vướng API đối tác". |
| 2.5 | **Họp rà soát** → Tạo chương trình họp | "Agenda tự gom: KR đỏ, KR lâu không check-in, blocker vừa nhập ở bước trước. Đây chính là KR6.2 '16 báo cáo/năm' của phòng — nhưng tự động." |
| 2.6 | Sửa target 1 KPI đã confirm → hệ chặn → tạo **Phiếu điều chỉnh** → duyệt | "Giữa kỳ muốn đổi chỉ tiêu phải có lý do + người duyệt, lịch sử giữ vĩnh viễn. Cuối năm không còn 'ai sửa số lúc nào'." |
| 2.7 | Rút **điện thoại** mở cockpit | "Lãnh đạo đứng ở hành lang vẫn xem được." |

**Chốt hồi 2:** "Excel lưu số liệu. Cái này *quản trị* số liệu: phát hiện — nhắc việc — kiểm soát thay đổi."

## HỒI 3 — "Cuối năm và năm sau" (5 phút): khép vòng đời

| Bước | Màn hình | Nói gì |
|---|---|---|
| 3.1 | **Chu kỳ đánh giá** → sinh review cho cả phòng | "Điểm mục tiêu tự chảy vào phiếu đánh giá — chụp tại thời điểm sinh, sau này số liệu đổi cũng không sửa được lịch sử." |
| 3.2 | 360 ẩn danh + **Calibration** | "Đồng nghiệp góp ý ẩn danh thật sự (kể cả admin không truy ra ai viết); hội đồng đổi điểm phải ghi lý do, biên bản bất biến." |
| 3.3 | **9-box** + PIP | "Kết quả năm thành bản đồ nhân tài; ai dưới ngưỡng tự có kế hoạch cải thiện 30-60-90 ngày." |
| 3.4 | **Nhân bản sang kỳ mới** (demo với cycle Acme 2025→2026 có sẵn) | "Tháng 1 năm sau: 1 nút, cấu trúc giữ nguyên, số liệu về 0. Không còn 'copy file rồi xóa tay'." |

## Câu chốt

> "Anh chị không đổi phương pháp — vẫn Objective, KR, KPI, trọng số như file này.
> Thứ thay đổi là: lỗi lộ ra ngay thay vì cuối kỳ, việc nhắc tự động thay vì đòi
> báo cáo, và mọi con số có lịch sử. File Excel này nghỉ hưu được rồi."

## Q&A dự phòng

- **"Team tôi quen Excel"** → import + rollover: Excel vẫn là cửa nhập, hệ thống là cửa quản.
- **"Odoo bản nào?"** → Community đủ, chạy cả Odoo 18 lẫn 19; không cần Enterprise.
- **"Nhiều người thì chậm không?"** → đã kiểm chứng 2.000 nhân sự × 40 KPI: đóng kỳ <60s, mở dashboard <3s.
- **"Bảo mật điểm số?"** → phân quyền theo chuỗi quản lý; mục tiêu private chỉ quản lý thấy; 360 ẩn danh ở mức cơ sở dữ liệu.
- **"Trọng số 7% kia sửa sao?"** → hai lựa chọn: nhập lại trọng số cá nhân đúng nghĩa (khuyến nghị — trọng số cá nhân ≠ trọng số phòng), hoặc chúng tôi thêm nút chuẩn hóa tỷ lệ về 100%.
