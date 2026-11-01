# Báo cáo nhóm web-demo

## Phân công

- Nhánh: `feat/web-demo`; workspace Orca: `web-demo`.
- Base / đích merge: `master` / `master`.
- Người/agent nhận việc: Chưa ghi nhận.
- Commit đầu vào: Ghi hash thực tế khi bắt đầu.
- Ngày khởi tạo báo cáo: 01/11/2026.
- Phạm vi: Ứng dụng demo văn bản và giọng nói.
- Đọc [phân công chung](../BRANCHES.md), [quy định báo cáo](../README.md), [TASKS.md](../../TASKS.md) và [yêu cầu dự án](../../PROJECT_REQUIREMENTS.md).

## Nhiệm vụ và ranh giới

- `src/web_app/`: backend API, frontend, adapter ASR, transcript, xử lý đầu vào và lỗi.
- Cấu hình chạy, đóng gói và kiểm thử tích hợp demo; tách module backend/frontend/ASR trong cùng nhánh.
- T22 chủ trì tích hợp/bàn giao ứng dụng; phối hợp pipeline về checkpoint được chọn bằng validation và report về tài liệu.

Đường dẫn thành phần chưa tồn tại là dự kiến, không phải bằng chứng đã triển khai. Chi tiết giao tiếp và cách nạp mô hình thống nhất tại [ARCHITECTURE.md](../../ARCHITECTURE.md).

## Đầu ra cần bàn giao

- API/UI dịch văn bản hai chiều với model metadata và các trạng thái chờ/lỗi.
- PoC âm thanh → transcript → bản dịch ở ngôn ngữ đã kiểm chứng, hiển thị transcript và giới hạn ASR riêng.
- Hướng dẫn cài/chạy, cấu hình endpoint/model và bằng chứng thử luồng thật khi có checkpoint.

**Có thể bắt đầu:** Thống nhất giao diện suy luận/API, phát triển web và ASR adapter với fixture/mock ghi rõ. Demo với mock chưa phải nghiệm thu mô hình thật; không mặc định ASR hỗ trợ tiếng Tày.

**Kiểm tra trọng tâm:**

- Schema API/client khớp, xử lý rỗng/sai chiều/quá giới hạn/model chưa sẵn sàng và lỗi audio.
- Luồng dùng đúng transcript, model/tokenizer đúng phiên bản, đo phản hồi trên môi trường thực; không huấn luyện trong request.

## Tiến độ từng Txx

Cột trạng thái nền chụp từ `TASKS.md` khi khởi tạo. Nhóm cập nhật tiến độ/kết quả mới của từng Txx; công cụ có sẵn không đồng nghĩa đã chạy với dữ liệu/mô hình thật.

| Mã | Công việc | Phụ thuộc nghiệm thu | Trạng thái nền | Tiến độ trong đợt này / bằng chứng |
| --- | --- | --- | --- | --- |
| T05 | Chốt phạm vi âm thanh và khả năng ASR bằng mẫu thử | — | Chưa làm | Chưa bắt đầu; chưa có bằng chứng mới |
| T19 | Backend suy luận: kiểm tra đầu vào, chiều dịch, phiên bản mô hình và lỗi | T11, T12 | Chưa làm | Chưa bắt đầu; chưa có bằng chứng mới |
| T20 | Giao diện dịch văn bản và kiểm tra tích hợp với backend | T19 | Chưa làm | Chưa bắt đầu; chưa có bằng chứng mới |
| T21 | Tích hợp âm thanh → transcript → bản dịch; ghi phạm vi và mẫu demo | T05, T19, T20 | Chưa làm | Chưa bắt đầu; chưa có bằng chứng mới |
| T22 | Chọn checkpoint theo validation, hoàn thiện demo và hướng dẫn vận hành/tái hiện | T16, T17, T20, T21 | Chưa làm | Chưa bắt đầu; chưa có bằng chứng mới |

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
