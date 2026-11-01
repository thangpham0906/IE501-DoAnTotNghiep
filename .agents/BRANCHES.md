# Phân công 3 nhánh

**Đã chốt với người dùng ngày 01/11/2026:** dùng 3 nhánh triển khai, mỗi nhánh có một worktree Orca riêng. Các mã Txx là checklist trong nhóm; lịch tuần dùng để theo dõi/bàn giao. `master` là nơi tích hợp.

| Nhóm | Nhánh Git | Workspace Orca | Txx phụ trách | Báo cáo |
| --- | --- | --- | --- | --- |
| translation-pipeline | `feat/translation-pipeline` | `translation-pipeline` | T02, T03, T04, T06, T07, T08, T09, T10, T11, T12, T13, T14, T15, T16, T17, T18 | [translation-pipeline.md](reports/translation-pipeline.md) |
| web-demo | `feat/web-demo` | `web-demo` | T05, T19, T20, T21, T22 | [web-demo.md](reports/web-demo.md) |
| report | `docs/report` | `report` | T23 | [report.md](reports/report.md) |

Các nhóm xuất phát từ `master` chứa bộ phân công này và tích hợp về `master`. Việc có nhánh/báo cáo không có nghĩa các Txx đã bắt đầu hoặc hoàn thành. Trạng thái dự án nằm tại [TASKS.md](../TASKS.md); cách cập nhật bằng chứng tại [README.md](README.md).

## Phạm vi từng nhóm

- **translation-pipeline:** dữ liệu, mô hình, huấn luyện, dịch ngược/QC và đánh giá. Giữ các module `data_pipeline/`, `models/`, `augmentation/`, `evaluation/` riêng; commit và báo cáo theo Txx.
- **web-demo:** backend, frontend, ASR/transcript, tích hợp và đóng gói. Giữ các module riêng trong `src/web_app/`; dùng adapter suy luận của pipeline.
- **report:** báo cáo, slide, trích dẫn và kịch bản bảo vệ; lấy bằng chứng từ hai nhóm kỹ thuật.

T06 do pipeline chủ trì về nền Python/cấu hình chung, phối hợp nhu cầu phụ thuộc của web. T22 do web chủ trì về tích hợp/bàn giao; checkpoint phải có bằng chứng lựa chọn bằng validation từ pipeline. Report phối hợp tài liệu bàn giao.

## Giao tiếp cần thống nhất sớm

- Pipeline cung cấp giao diện suy luận và cách nạp checkpoint/tokenizer/config theo phiên bản; web gọi giao diện này, không tạo một pipeline huấn luyện riêng trong API.
- Hai nhóm kỹ thuật thống nhất trường văn bản, nhãn chiều dịch, kết quả/model metadata, lỗi khi model chưa sẵn sàng và giới hạn đầu vào. Chi tiết được chốt tại [ARCHITECTURE.md](../ARCHITECTURE.md) khi triển khai.
- Web tự thống nhất API/client và adapter ASR bên trong nhánh; chỉ bật ngôn ngữ âm thanh đã kiểm chứng.
- Report nhận số liệu/bản dịch/phiếu chấm/log thật và mô tả giới hạn; không tự điền kết quả khi upstream chưa chạy.

## Thực hiện và review

Có thể phát triển đồng thời cả ba nhóm: pipeline và web kiểm thử bằng fixture/mock được ghi rõ khi chưa đủ đầu vào; report viết phần phương pháp trước. Huấn luyện/đánh giá/nghiệm thu demo thật vẫn theo phụ thuộc và tiêu chí dự án.

Review và merge từng phần ổn định theo Txx; không đợi toàn bộ nhóm hoàn thành. Mỗi nhóm chỉ cập nhật báo cáo của mình; người tích hợp tổng hợp `TASKS.md`. Không tạo thêm nhánh theo từng tuần hoặc từng Txx chỉ vì có checkbox; việc tách thêm nhánh cần thuộc phạm vi công việc được giao.
