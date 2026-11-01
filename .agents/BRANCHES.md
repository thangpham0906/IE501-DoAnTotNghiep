# Danh sách nhánh và phiếu nhiệm vụ

Đợt phân công: **01/11/2026**. Có **22 nhiệm vụ chưa hoàn thành (T02–T23)**, mỗi nhiệm vụ dùng một nhánh và một worktree Orca. T01/T24/T25/T26/T27 đã hoàn thành theo [TASKS.md](../TASKS.md); bằng chứng cũ được giữ nguyên.

Các nhánh dùng chung base `master` chứa bộ phân công này; đích tích hợp là `master`. Tên workspace được dùng để tìm trong Orca; đường dẫn/ID thực tế xem bằng CLI Orca. Xem [quy định cập nhật và review](README.md) trước khi bắt đầu.

| Mã | Nhánh Git | Workspace Orca | Nhiệm vụ / báo cáo | Phụ thuộc trước nghiệm thu |
| --- | --- | --- | --- | --- |
| T02 | `task/T02-khao-sat-mo-hinh` | `task-t02-khao-sat-mo-hinh` | [Khảo sát mô hình, tokenizer và phần cứng](tasks/T02.md) | — |
| T03 | `task/T03-xac-minh-nguon` | `task-t03-xac-minh-nguon` | [Xác nhận nguồn, chuẩn tiếng Tày và người duyệt](tasks/T03.md) | — |
| T04 | `task/T04-ke-hoach-danh-gia` | `task-t04-ke-hoach-danh-gia` | [Thiết kế metric và đánh giá thủ công](tasks/T04.md) | T02, T03 |
| T05 | `task/T05-khao-sat-asr` | `task-t05-khao-sat-asr` | [Khảo sát ASR và phạm vi âm thanh](tasks/T05.md) | — |
| T06 | `task/T06-nen-tang-du-an` | `task-t06-nen-tang-du-an` | [Môi trường, cấu hình và giao tiếp dùng chung](tasks/T06.md) | T02 |
| T07 | `task/T07-thu-thap-du-lieu` | `task-t07-thu-thap-du-lieu` | [Thu thập, nhập dữ liệu và metadata nguồn](tasks/T07.md) | T03, T06, T24 |
| T08 | `task/T08-kiem-dinh-du-lieu` | `task-t08-kiem-dinh-du-lieu` | [Audit nguồn và kiểm duyệt corpus](tasks/T08.md) | T07 |
| T09 | `task/T09-lam-sach-can-chinh` | `task-t09-lam-sach-can-chinh` | [Chuẩn hóa, căn chỉnh và khử trùng lặp](tasks/T09.md) | T08 |
| T10 | `task/T10-chia-tap-chong-ro-ri` | `task-t10-chia-tap-chong-ro-ri` | [Chia tập và kiểm tra rò rỉ](tasks/T10.md) | T09 |
| T11 | `task/T11-pipeline-mo-hinh` | `task-t11-pipeline-mo-hinh` | [Tokenizer, loader, huấn luyện và suy luận](tasks/T11.md) | T06, T10 |
| T12 | `task/T12-baseline-e0` | `task-t12-baseline-e0` | [Thực nghiệm baseline E0](tasks/T12.md) | T11 |
| T13 | `task/T13-bo-danh-gia` | `task-t13-bo-danh-gia` | [Bộ đánh giá tự động](tasks/T13.md) | T04, T12 |
| T14 | `task/T14-back-translation` | `task-t14-back-translation` | [Đơn ngữ và sinh tập dịch ngược U](tasks/T14.md) | T10, T12 |
| T15 | `task/T15-qc-va-doi-chung` | `task-t15-qc-va-doi-chung` | [Lọc QC và tạo các tập đối chứng](tasks/T15.md) | T14 |
| T16 | `task/T16-huan-luyen-doi-chung` | `task-t16-huan-luyen-doi-chung` | [Huấn luyện E1/E2/E1-M](tasks/T16.md) | T12, T15 |
| T17 | `task/T17-ablation-a1-a2` | `task-t17-ablation-a1-a2` | [Ablation A1/A2 và kiểm tra độ ổn định](tasks/T17.md) | T16 |
| T18 | `task/T18-danh-gia-cuoi` | `task-t18-danh-gia-cuoi` | [Đánh giá test, chấm người và phân tích lỗi](tasks/T18.md) | T13, T17 |
| T19 | `task/T19-backend` | `task-t19-backend` | [API dịch văn bản](tasks/T19.md) | T11, T12 |
| T20 | `task/T20-frontend` | `task-t20-frontend` | [Giao diện dịch văn bản](tasks/T20.md) | T19 |
| T21 | `task/T21-demo-giong-noi` | `task-t21-demo-giong-noi` | [Tích hợp âm thanh → transcript → bản dịch](tasks/T21.md) | T05, T19, T20 |
| T22 | `task/T22-tich-hop-ban-giao` | `task-t22-tich-hop-ban-giao` | [Tích hợp, chọn checkpoint và hướng dẫn vận hành](tasks/T22.md) | T16, T17, T20, T21 |
| T23 | `task/T23-bao-cao-slide` | `task-t23-bao-cao-slide` | [Báo cáo, slide và kịch bản bảo vệ](tasks/T23.md) | T18, T22 |

Mỗi phiếu có phần việc có thể làm ngay và phần phải đợi đầu vào thật. Chỉ định “phụ thuộc” không cấm viết khung/kiểm thử độc lập trước; việc tạo nhánh không tự chạy huấn luyện, crawl, chấm người hoặc khởi động agent.

Nhánh `week-01-khao-sat-nguon` đã có giữ vai trò tổng hợp tuần khi cần, không thay các nhánh nhiệm vụ trong bảng. Các worktree tài liệu cũ giữ nguyên. Khi giao việc, dùng tên nhánh và phiếu Txx để tránh hai người nhận cùng đầu việc mà không biết nhau.

## Tra cứu và bàn giao

- Người triển khai: mở phiếu của đúng nhánh, cập nhật phần báo cáo và log theo [README](README.md#cách-ghi-báo-cáo).
- Người review: xem phiếu tại worktree/nhánh cần review; bản trên `master` có thể chưa có tiến độ chưa merge.
- Người tích hợp: giữ báo cáo từng nhánh tại đường dẫn riêng và tổng hợp trạng thái vào `TASKS.md`; cập nhật danh sách này chỉ khi đổi phân công/tên nhánh.
