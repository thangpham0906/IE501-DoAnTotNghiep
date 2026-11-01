# Phân công và báo cáo theo nhánh

Thư mục này quản lý giao việc và bằng chứng của từng nhánh. Danh sách đầy đủ nằm tại [BRANCHES.md](BRANCHES.md); mỗi nhiệm vụ có một phiếu trong `tasks/Txx.md`, gồm phạm vi cố định và phần báo cáo được cập nhật khi làm việc.

## Bắt đầu một nhiệm vụ

1. Đọc [AGENTS.md](../AGENTS.md), [PROJECT_CONTEXT.md](../PROJECT_CONTEXT.md), [TASKS.md](../TASKS.md), sau đó mở phiếu ứng với nhánh trong [danh sách phân công](BRANCHES.md).
2. Kiểm tra nhánh/worktree thực tế. Ghi người nhận việc, ngày bắt đầu, commit đầu vào, phần sẽ sửa và phụ thuộc còn thiếu vào phiếu của mình. Nếu đang ở nhánh khác, mở worktree đúng; không đổi nhánh của workspace có người/agent đang làm.
3. Đọc file và log hiện có trước khi triển khai. Các đường dẫn dự kiến trong phiếu không chứng minh thành phần đã tồn tại; chỉ tạo phần cần thiết. Tái sử dụng công cụ có sẵn.
4. Làm trong phạm vi nhiệm vụ, mỗi nhánh một đầu ra rõ ràng. Có thể phát triển khung/fixture/mock trong lúc chờ phụ thuộc; ghi rõ giới hạn, không chuyển thành bằng chứng thực nghiệm thật.
5. Sau mỗi mốc có ý nghĩa, cập nhật phần **Báo cáo thực hiện** của chính `tasks/Txx.md`. Khi bàn giao, nêu kết quả, file/commit/run ID, lệnh kiểm tra và phần còn thiếu.

Tạo worktree và khởi tạo phiếu không có nghĩa đã triển khai nhiệm vụ. T06/T07/T08 đã có một phần công việc trước đợt này; trạng thái nền được giữ riêng trong từng phiếu.

## Phân biệt các nơi ghi thông tin

- `tasks/Txx.md`: nhiệm vụ, diễn biến và bằng chứng của nhánh Txx; đây là nơi agent cập nhật thường xuyên.
- `BRANCHES.md`: danh sách tên nhánh/workspace và liên kết phiếu; không dùng làm nhật ký chung của mọi nhánh.
- [TASKS.md](../TASKS.md): tiến độ toàn dự án; người tích hợp tổng hợp từ phiếu sau review/merge hoặc mốc báo cáo. Không để mọi nhánh sửa lại toàn bộ bảng tiến độ.
- [PROJECT_CONTEXT.md](../PROJECT_CONTEXT.md), [ARCHITECTURE.md](../ARCHITECTURE.md), [PROJECT_REQUIREMENTS.md](../PROJECT_REQUIREMENTS.md): quyết định, giao tiếp và nghiệm thu theo đúng trách nhiệm; phiếu dẫn tới các nội dung này, không thay thế tài liệu chính.
- Manifest/log: bằng chứng máy đọc và dữ liệu thực tế. Phiếu chỉ liên kết và giải thích, không chép corpus, khóa truy cập hoặc checkpoint vào Markdown.

Mọi nhánh đều nhận cùng bộ phiếu lúc khởi tạo; mỗi nhánh chỉ cập nhật phiếu của mình. Khi merge, các báo cáo ở đường dẫn khác nhau được tập hợp về `master`. Reviewer có thể bổ sung kết quả review vào phiếu tương ứng, giữ lại bằng chứng/nhật ký đã có.

## Quy tắc khi làm song song

- Base và đích merge của các nhánh trong đợt này là `master`; công việc triển khai có thể bắt đầu cùng lúc. Chỉ nghiệm thu phần phụ thuộc khi đầu vào đã đủ điều kiện.
- Phạm vi file trong phiếu là phân công dự kiến. Các chỗ giao nhau phải được trao đổi trong báo cáo/phần giao tiếp trước khi đổi; tránh hai nhánh tự chọn hai schema/API khác nhau.
- T06 tổng hợp phụ thuộc Python, cấu hình nền và giao tiếp dùng chung. T11 sở hữu adapter mô hình/checkpoint; T19 sở hữu API dịch văn bản; T05 sở hữu adapter ASR; T21 nối phần âm thanh; T20 sở hữu UI văn bản.
- T07 ghi nguồn/metadata thu thập; T08 ghi bằng chứng/quyết định duyệt; T09 xuất corpus sạch; T10 cố định split. Không tự đổi quyết định của nguồn upstream để bỏ qua bước kiểm định.
- T04 định nghĩa protocol; T13 triển khai metric; T18 thực hiện đánh giá cuối/chấm người. T14 tạo U; T15 tạo tập QC/đối chứng; T12/T16/T17 chạy thực nghiệm. Không sửa cùng file cấu hình/run của nhau.
- Đồng bộ thay đổi đã tích hợp, review diff và kiểm tra phần bị ảnh hưởng trước khi merge. Xử lý conflict theo nội dung của cả hai nhánh; Git không báo conflict chưa chứng minh tương thích.
- Raw/model/env bị Git bỏ qua không tự xuất hiện ở worktree mới. Xác định đầu vào cục bộ bằng cấu hình hoặc bản sao có hash; đầu vào chung chỉ đọc, đầu ra mỗi nhánh/run riêng. Không tự crawl hay tải model lớn chỉ để lấp chỗ thiếu.
- Giữ ngày thực hiện thật; lịch 11 tuần là mốc báo cáo, không phải ngày giả để điền log.

## Cách ghi báo cáo

Trạng thái nhánh: **Chưa bắt đầu**, **Đang làm**, **Bị chặn**, **Sẵn sàng review**, **Đã tích hợp**. Trạng thái nghiệm thu công việc trong `TASKS.md` vẫn theo quy tắc của dự án.

Mỗi lần cập nhật ghi rõ:

- Việc đã thực hiện, đầu ra nằm ở đâu và phần nào chỉ là mock/fixture.
- Commit/PR hoặc diff chưa commit; phiên bản dữ liệu/model/run ID nếu có.
- Lệnh kiểm tra đã chạy, môi trường, kết quả đạt/lỗi và đường dẫn log. Không ghi “đạt” cho kiểm tra chưa chạy.
- Phụ thuộc còn thiếu, vấn đề chưa giải quyết và bước tiếp theo.
- Với nghiệm thu từng phần, nêu phạm vi đủ bằng chứng và phạm vi chưa đạt; không đánh dấu cả Txx hoàn thành chỉ vì code khung chạy được.

Phần **Nhiệm vụ và phạm vi** không phải nhật ký: chỉ điều chỉnh khi phạm vi được thống nhất, ghi lý do trong báo cáo. Không xóa lỗi/giới hạn cũ để tạo cảm giác kết quả đã hoàn thiện.

## Review một nhánh

Mở phiếu trong worktree tương ứng để xem cả thay đổi chưa commit. Từ `master`, có thể đọc báo cáo đã commit mà không checkout nhánh:

```bash
git show task/T19-backend:.agents/tasks/T19.md
git diff master...task/T19-backend
```

`git show` không hiển thị chỉnh sửa chưa commit. File phiếu trong `master` chỉ chứa báo cáo đã được tích hợp, không phải trạng thái trực tiếp của các worktree đang làm.

Reviewer đối chiếu:

1. Phạm vi thay đổi với nhiệm vụ, yêu cầu F/Q và phụ thuộc.
2. Diff/file thực tế với phần “Đã làm”; không dùng checkbox làm bằng chứng.
3. Lệnh/log, dữ liệu đầu vào, output và giao tiếp với các thành phần khác.
4. Lỗi còn lại, giới hạn mock/chưa có corpus/checkpoint/người duyệt và điều kiện nghiệm thu.
5. Kết luận **Đạt / Cần sửa / Chưa đủ bằng chứng**, kèm người/ngày review và điểm phải xử lý.

Sau tích hợp, cập nhật phiếu và `TASKS.md` bằng commit merge/PR, chỉ đánh dấu hoàn thành phần đáp ứng tiêu chí. Không tự push/merge hoặc chạy nhiệm vụ chỉ vì đọc file này; thực hiện theo công việc đã được giao.
