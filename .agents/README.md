# Quy định phân công và báo cáo theo nhóm

Đợt 22 nhánh theo từng Txx đã được hủy theo yêu cầu người dùng. Phương án hiện tại là [8 nhóm công việc](BRANCHES.md), **mới ở mức đề xuất; chưa tạo các nhánh mới**.

Mỗi nhóm nhận một nhánh/worktree và một báo cáo riêng. Các mã Txx là checklist trong nhóm; không mặc định một Txx phải tạo một nhánh.

## Khi bắt đầu triển khai

1. Đọc [AGENTS.md](../AGENTS.md), [PROJECT_CONTEXT.md](../PROJECT_CONTEXT.md), [TASKS.md](../TASKS.md) và phạm vi nhóm trong [BRANCHES.md](BRANCHES.md).
2. Xác minh nhánh/worktree và đầu vào thực tế. Khi nhóm được giao triển khai, tạo báo cáo `reports/<nhom>.md` từ [mẫu báo cáo](REPORT_TEMPLATE.md), ghi người phụ trách, commit đầu vào và các Txx nhận làm.
3. Phối hợp schema dữ liệu, API và adapter trước khi sửa các phần giao nhau. Tái sử dụng công cụ hiện có; đường dẫn dự kiến không chứng minh chức năng đã hoạt động.
4. Sau mỗi mốc, cập nhật báo cáo của nhóm với Txx liên quan, file/commit/run ID, lệnh kiểm tra, kết quả, giới hạn và bước tiếp theo.
5. Người tích hợp đọc báo cáo cùng diff/log rồi cập nhật tiến độ chung trong `TASKS.md`; không để mọi nhóm sửa lại toàn bộ bảng tiến độ.

## Quy tắc báo cáo

- Trạng thái nhóm: **Chưa bắt đầu**, **Đang làm**, **Bị chặn**, **Sẵn sàng review**, **Đã tích hợp**. Mỗi Txx trong nhóm vẫn theo dõi mức hoàn thành riêng.
- Chỉ báo cáo việc đã thực hiện. Tạo nhánh, có kế hoạch hoặc chạy mock không phải bằng chứng đã có corpus, mô hình hay kết quả nghiên cứu.
- Lưu lệnh, môi trường, kết quả quan sát và log; không ghi kiểm tra đạt khi chưa chạy. Giữ lại lỗi/giới hạn đã phát hiện.
- Nhóm chỉ cập nhật báo cáo của mình trong `.agents/reports/`; phân công trong `BRANCHES.md` chỉ đổi khi điều chỉnh phạm vi.
- Quyết định, giao tiếp và tiêu chí vẫn nằm tại tài liệu dự án tương ứng; báo cáo dẫn tới bằng chứng thay vì chép lại toàn bộ nội dung.
- Dữ liệu/model/env bị Git bỏ qua không tự có ở worktree mới. Đầu vào dùng chung chỉ đọc; đầu ra mỗi nhóm/run riêng.

## Review và tích hợp

Review từng phần ổn định khi đủ điều kiện, không đợi toàn bộ nhóm xong mới tích hợp. Mở báo cáo tại worktree để xem cả thay đổi chưa commit. Bản báo cáo trên `master` chỉ có tiến độ đã tích hợp.

Người review đối chiếu phạm vi, các Txx, diff/file thật, kiểm tra đã chạy, phụ thuộc và tính tương thích giữa thành phần. Ghi kết luận **Đạt / Cần sửa / Chưa đủ bằng chứng**, người/ngày review và điểm cần xử lý vào báo cáo nhóm.

Sau merge, ghi commit/PR và cập nhật `TASKS.md` theo từng Txx, không đánh dấu toàn nhóm hoàn thành vì một phần đã đạt. Việc viết phương án này chưa khởi chạy agent hoặc công việc triển khai.
