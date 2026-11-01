# Phương án phân chia nhánh

**Trạng thái: đề xuất 8 nhánh triển khai; chưa tạo.** Đợt 22 nhánh `task/T02-...` đến `task/T23-...` đã được xóa theo yêu cầu người dùng ngày 01/11/2026.

## Cách chia đề xuất

Gom theo thành phần sở hữu code và đầu ra, giữ các bước dùng chung pipeline trong một nhóm. Các mã Txx vẫn giữ nguyên để quản lý tiến độ chi tiết trong [TASKS.md](../TASKS.md).

| Nhóm / tên báo cáo | Nhánh đề xuất | Txx phụ trách chính | Phạm vi |
| --- | --- | --- | --- |
| `data` | `feat/data-pipeline` | T03, T07, T08, T09, T10 | Nguồn, kiểm định, làm sạch, chia tập và manifest |
| `model` | `feat/model-training` | T02, T06, T11, T12, T16, T17 | Khảo sát mô hình, nền Python, pipeline train, E0 và các lượt thực nghiệm |
| `augmentation` | `feat/data-augmentation` | T14, T15 | Đơn ngữ, dịch ngược U, QC và các tập đối chứng |
| `evaluation` | `feat/evaluation` | T04, T13, T18 | Protocol, metric, chấm người và phân tích lỗi |
| `backend` | `feat/backend` | T19, T22 | API dịch, tích hợp hệ thống và đóng gói vận hành |
| `frontend` | `feat/frontend` | T20 | Giao diện dịch văn bản và API client |
| `speech` | `feat/speech` | T05, T21 | Khảo sát ASR, transcript và luồng giọng nói |
| `report` | `docs/report` | T23 | Báo cáo, slide và kịch bản bảo vệ |

Báo cáo của mỗi nhóm khi triển khai đặt tại `.agents/reports/<nhom>.md`, dùng [mẫu chung](REPORT_TEMPLATE.md). Các file báo cáo nhóm chưa được tạo ở giai đoạn xem lại phương án.

## Vì sao 8 nhóm

- Dữ liệu dùng chung quy trình nguồn → duyệt → làm sạch → chia tập; tách từng bước thành nhánh dài hạn làm tăng giao tiếp và sửa trùng.
- Khảo sát model, tokenizer, loader và các lượt train dùng cùng lõi huấn luyện, nên cùng một nhóm.
- Dịch ngược/QC và metric/đánh giá có code, đầu vào/đầu ra riêng nên có thể phát triển song song với nhóm mô hình.
- Backend, frontend và giọng nói có phạm vi riêng; thống nhất API/adapter trước để làm độc lập bằng fixture/mock.
- Báo cáo có thể viết phần phương pháp từ sớm và cập nhật bằng chứng khi thực nghiệm xong.

Đây là phương án tổ chức cho cấu trúc hiện tại, không phải con số bắt buộc. Tách thêm nhánh nhỏ khi có công việc độc lập cụ thể và người phụ trách; không tạo hàng loạt theo số lượng checkbox.

## Ranh giới cần thống nhất

- `model` chủ trì T06 về môi trường Python/cấu hình nền; các nhóm phối hợp phụ thuộc và giao tiếp, không tự ghi đè cấu hình chung.
- `backend` chủ trì T22 về tích hợp/đóng gói; cần đầu ra của model, frontend và speech. `report` phối hợp tài liệu bàn giao.
- `model` sở hữu adapter suy luận/checkpoint; `backend` sở hữu API văn bản; `speech` sở hữu adapter ASR và phần âm thanh; `frontend` sở hữu UI văn bản.
- `augmentation` xuất U và các tập QC/đối chứng; `model` dùng chúng để train. `evaluation` không chỉnh mô hình hoặc QC theo kết quả test.
- Các nhóm có thể viết khung/kiểm thử đồng thời; chạy thực nghiệm thật và nghiệm thu vẫn phải có dữ liệu, model, người duyệt/chấm theo yêu cầu dự án.

`master` là nơi tích hợp, không tính trong 8 nhánh. Lịch tuần là mốc bàn giao; không cần duy trì thêm một nhánh riêng cho mỗi tuần. Quy trình báo cáo/review nằm tại [README.md](README.md).
