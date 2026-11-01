# Báo cáo nhóm report

## Phân công

- Nhánh: `docs/report`; workspace Orca: `report`.
- Base / đích merge: `master` / `master`.
- Người/agent nhận việc: Chưa ghi nhận.
- Commit đầu vào: Ghi hash thực tế khi bắt đầu.
- Ngày khởi tạo báo cáo: 01/11/2026.
- Phạm vi: Báo cáo, slide và kịch bản bảo vệ.
- Đọc [phân công chung](../BRANCHES.md), [quy định báo cáo](../README.md), [TASKS.md](../../TASKS.md) và [yêu cầu dự án](../../PROJECT_REQUIREMENTS.md).

## Nhiệm vụ và ranh giới

- Tài liệu báo cáo/slide/kịch bản bảo vệ trong `docs/`, bảng dẫn chứng và trích dẫn.
- Phối hợp hai nhóm kỹ thuật lấy log/manifest/phiếu chấm và bằng chứng demo; không sửa code thực nghiệm để khớp câu chuyện báo cáo.
- Đề cương chỉ chỉnh theo yêu cầu riêng và quy trình xuất PDF; không tự thay đổi phạm vi nghiên cứu.

Đường dẫn thành phần chưa tồn tại là dự kiến, không phải bằng chứng đã triển khai. Chi tiết giao tiếp và cách nạp mô hình thống nhất tại [ARCHITECTURE.md](../../ARCHITECTURE.md).

## Đầu ra cần bàn giao

- Báo cáo trình bày dữ liệu, phương pháp, thực nghiệm, demo và giới hạn với bằng chứng truy được.
- Slide và kịch bản bảo vệ nhất quán với phần đã chạy; phân biệt số liệu thực với mục tiêu kế hoạch.

**Có thể bắt đầu:** Viết tổng quan/phương pháp và cấu trúc báo cáo từ nguồn đáng tin cậy. Phần kết quả chờ T18/T22; để rõ chỗ chưa có bằng chứng.

**Kiểm tra trọng tâm:**

- Mọi số liệu truy tới log/manifest/run ID; không cộng lặp các tầng dữ liệu hoặc bịa cải thiện.
- Trích dẫn, ngày thực hiện và giới hạn nhất quán với code, dữ liệu và demo.

## Tiến độ từng Txx

Cột trạng thái nền chụp từ `TASKS.md` khi khởi tạo. Nhóm cập nhật tiến độ/kết quả mới của từng Txx; công cụ có sẵn không đồng nghĩa đã chạy với dữ liệu/mô hình thật.

| Mã | Công việc | Phụ thuộc nghiệm thu | Trạng thái nền | Tiến độ trong đợt này / bằng chứng |
| --- | --- | --- | --- | --- |
| T23 | Hoàn thiện báo cáo, bảng kết quả, trích dẫn, slide và kịch bản bảo vệ | T18, T22 | Chưa làm | Chưa bắt đầu; chưa có bằng chứng mới |

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
