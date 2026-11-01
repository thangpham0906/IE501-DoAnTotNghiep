# Báo cáo nhóm translation-pipeline

## Phân công

- Nhánh: `feat/translation-pipeline`; workspace Orca: `translation-pipeline`.
- Base / đích merge: `master` / `master`.
- Người/agent nhận việc: Chưa ghi nhận.
- Commit đầu vào: Ghi hash thực tế khi bắt đầu.
- Ngày khởi tạo báo cáo: 01/11/2026.
- Phạm vi: Pipeline nghiên cứu dịch Việt–Tày.
- Đọc [phân công chung](../BRANCHES.md), [quy định báo cáo](../README.md), [TASKS.md](../../TASKS.md) và [yêu cầu dự án](../../PROJECT_REQUIREMENTS.md).

## Nhiệm vụ và ranh giới

- Nguồn, kiểm duyệt, làm sạch, chia tập và manifest trong `src/data_pipeline/`.
- Mô hình, tokenizer, loader, huấn luyện và suy luận trong `src/models/`; dịch ngược/QC trong `src/augmentation/`; metric/chấm người/phân tích lỗi trong `src/evaluation/`.
- T06 về nền Python và cấu hình dùng chung; phối hợp nhóm web-demo khi phụ thuộc thay đổi. Tái sử dụng pipeline dữ liệu có sẵn.

Đường dẫn thành phần chưa tồn tại là dự kiến, không phải bằng chứng đã triển khai. Chi tiết giao tiếp và cách nạp mô hình thống nhất tại [ARCHITECTURE.md](../../ARCHITECTURE.md).

## Đầu ra cần bàn giao

- Corpus đủ điều kiện và validation/test cố định, có bằng chứng nguồn/duyệt và kiểm tra rò rỉ.
- Pipeline huấn luyện, U/QC/đối chứng, kết quả E0/E1/E2/E1-M/A1/A2 có manifest/run ID khi đã chạy thật.
- Adapter suy luận và gói checkpoint/tokenizer/config có phiên bản để web-demo tích hợp; kết quả đánh giá và giới hạn để report viết báo cáo.

**Có thể bắt đầu:** Rà nguồn/biểu mẫu, khảo sát khả thi, hoàn thiện công cụ và kiểm thử bằng fixture/mock. Mọi kiểm định ngôn ngữ, huấn luyện dài và đánh giá thật phải có đầu vào/nhân lực/ngân sách đúng yêu cầu.

**Kiểm tra trọng tâm:**

- Nguồn/duyệt gắn hash; đúng chiều dịch, token đặc biệt, padding và checkpoint/tokenizer; không rò rỉ train/validation/test.
- Cùng U, N/seed/ID mẫu và điều kiện huấn luyện; không chọn checkpoint/QC theo test; không bịa metric hoặc phiếu chấm.

## Tiến độ từng Txx

Cột trạng thái nền chụp từ `TASKS.md` khi khởi tạo. Nhóm cập nhật tiến độ/kết quả mới của từng Txx; công cụ có sẵn không đồng nghĩa đã chạy với dữ liệu/mô hình thật.

| Mã | Công việc | Phụ thuộc nghiệm thu | Trạng thái nền | Tiến độ trong đợt này / bằng chứng |
| --- | --- | --- | --- | --- |
| T02 | Kiểm tra mô hình/tokenizer và đo phần cứng; cuối tuần 2 chốt cấu hình, giới hạn bước/giờ cho 6 cấu hình hoặc ghi điều chỉnh | — | Chưa làm | Chưa bắt đầu; chưa có bằng chứng mới |
| T03 | Tuần 1 xác nhận nguồn, chuẩn tiếng Tày, người duyệt và lô rà thử; cuối tuần 2 chốt quy mô/lịch duyệt | — | Chưa làm | Chưa bắt đầu; chưa có bằng chứng mới |
| T04 | Xác minh metric; cuối tuần 2 chốt số mẫu/người chấm, thang điểm 1–5, lấy mẫu/ẩn tên và xử lý bất đồng | T02, T03 | Chưa làm | Chưa bắt đầu; chưa có bằng chứng mới |
| T06 | Tổ chức mã nguồn, phụ thuộc, cấu hình, `.gitignore` và kiểm thử nền; đã có phần dữ liệu, còn phần mô hình | T02 | Đang làm | Chưa bắt đầu; chưa có bằng chứng mới |
| T07 | Hoàn thiện thu thập/nhập dữ liệu, metadata và danh mục nguồn; bổ sung bằng chứng còn thiếu sau kiểm kê | T03, T06, T24 | Đang làm | Chưa bắt đầu; chưa có bằng chứng mới |
| T08 | Audit nguồn, phân loại cách tạo và kiểm duyệt ngôn ngữ/bản dịch; đã kiểm tra cấu trúc và cách ly đầu ra bị loại | T07 | Đang làm | Chưa bắt đầu; chưa có bằng chứng mới |
| T09 | Chuẩn hóa, căn chỉnh, khử trùng lặp; xuất thống kê và mẫu kiểm duyệt | T08 | Chưa làm | Chưa bắt đầu; chưa có bằng chứng mới |
| T10 | Chia tập theo tài liệu, kiểm tra rò rỉ và cố định manifest | T09 | Chưa làm | Chưa bắt đầu; chưa có bằng chứng mới |
| T11 | Hoàn thiện tokenizer, loader, huấn luyện và suy luận hai chiều; kiểm thử bằng dữ liệu nhỏ | T06, T10 | Chưa làm | Chưa bắt đầu; chưa có bằng chứng mới |
| T12 | Chạy baseline E0, lưu cấu hình/log/checkpoint và kết quả validation | T11 | Chưa làm | Chưa bắt đầu; chưa có bằng chứng mới |
| T13 | Hoàn thiện bộ đánh giá tự động, xuất bản dịch và xác minh cách tính metric | T04, T12 | Chưa làm | Chưa bắt đầu; chưa có bằng chứng mới |
| T14 | Chuẩn bị đơn ngữ tách khỏi validation/test; cố định checkpoint E0 chiều ngược để sinh tập U dùng chung | T10, T12 | Chưa làm | Chưa bắt đầu; chưa có bằng chứng mới |
| T15 | Chốt ngưỡng QC bằng validation, tạo E1/E2/E1-M, chọn R1/R2; lưu seed/ID mẫu và báo cáo lọc | T14 | Chưa làm | Chưa bắt đầu; chưa có bằng chứng mới |
| T16 | Huấn luyện E1/E2/E1-M cùng điều kiện; lưu validation và chi phí, đối chứng E2/E1-M cùng N | T12, T15 | Chưa làm | Chưa bắt đầu; chưa có bằng chứng mới |
| T17 | Chạy A1/A2 cùng N; ưu tiên lặp E2/E1-M nếu đủ ngân sách; ghi cấu hình/chi phí và giới hạn số seed | T16 | Chưa làm | Chưa bắt đầu; chưa có bằng chứng mới |
| T18 | Đánh giá test cố định; chấm ẩn tên E0/E1/E2/E1-M trên cùng mẫu, lưu điểm gốc và phân tích lỗi | T13, T17 | Chưa làm | Chưa bắt đầu; chưa có bằng chứng mới |

## Việc đã làm và đầu ra thực tế

Chưa có kết quả triển khai mới của nhóm trong đợt này. Khởi tạo phân công/báo cáo không được tính thành kết quả các Txx bên trên.

| Ngày | Txx / việc đã thực hiện | File / commit / run ID | Kết quả và giới hạn |
| --- | --- | --- | --- |
| — | Chưa thực hiện | — | Chưa xác minh |

## Kiểm tra đã chạy

| Ngày | Lệnh / môi trường | Kết quả thực tế | Log / giới hạn |
| --- | --- | --- | --- |
| — | Chưa chạy kiểm tra nhiệm vụ | Chưa xác minh | — |

## Vướng mắc và bước tiếp theo

- Phụ thuộc còn thiếu: Kiểm tra từng Txx và đầu vào thực tế khi nhận việc; không suy ra đã đủ từ kế hoạch.
- Thay đổi giao tiếp cần phối hợp: Chưa đề xuất.
- Bước tiếp theo: Nhận việc, ghi commit đầu vào, chọn Txx và kiểm tra phạm vi file.

## Review và tích hợp

- Trạng thái nhóm: **Chưa bắt đầu**.
- Kết luận review: **Chưa review**.
- Người / ngày review: Chưa ghi nhận.
- Điểm cần sửa / chưa đủ bằng chứng: Chưa review.
- Commit/PR triển khai đã tích hợp: **Chưa merge**.
- Txx đủ điều kiện cập nhật trong `TASKS.md`: Chưa có kết luận mới.

## Nhật ký

| Ngày | Người | Nội dung | Bằng chứng |
| --- | --- | --- | --- |
| 01/11/2026 | Codex | Khởi tạo phân công và báo cáo nhóm; chưa thực hiện các nhiệm vụ triển khai | File báo cáo này |
