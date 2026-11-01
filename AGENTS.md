# Hướng dẫn làm việc với repo

## Đọc đúng tài liệu

Đọc [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) và [TASKS.md](TASKS.md) để nắm bối cảnh và trạng thái trước khi bắt đầu. Chỉ mở thêm tài liệu liên quan đến nhiệm vụ:

| Khi cần | Đọc |
| --- | --- |
| Thành phần, luồng xử lý, tổ chức mã nguồn | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Chức năng, quy tắc dữ liệu, thực nghiệm, nghiệm thu | [PROJECT_REQUIREMENTS.md](PROJECT_REQUIREMENTS.md) |
| Xử lý dữ liệu, manifest, lệnh tái hiện và báo cáo tiến độ | [Quy trình xây dựng dữ liệu](docs/QUY_TRINH_XAY_DUNG_DU_LIEU.md) |
| Giới thiệu và hướng dẫn chạy | [README.md](README.md) |
| Đối chiếu nội dung đăng ký | [Đề cương PDF](docs/DeCuongDATN_25410304_25410313.pdf) |

## Quy tắc làm việc

1. Kiểm tra `git status`, giữ nguyên thay đổi đang có của người dùng. Chỉ chỉnh sửa trong phạm vi nhiệm vụ và sửa nguyên nhân gốc.
2. Kiểm tra file, mã nguồn và log thực tế trước khi kết luận trạng thái. Không coi kế hoạch, placeholder hoặc checkbox là bằng chứng tính năng đã hoạt động.
3. Thực hiện các bước cần thiết trong phạm vi đã được yêu cầu; chỉ hỏi khi thiếu thông tin ảnh hưởng đáng kể tới hướng thực hiện.
4. Dùng đường dẫn tương đối hoặc cấu hình. Khai báo thư viện phục vụ công việc thực tế và xác minh môi trường trước khi chạy.
5. Chạy kiểm tra phù hợp với thay đổi. Ưu tiên lỗi có thể làm sai kết quả: rò rỉ dữ liệu, nhãn chiều dịch, token đặc biệt, padding và checkpoint/tokenizer không khớp. Không ghi “tests pass” nếu chưa chạy.
6. Tuân thủ quy tắc dữ liệu và thực nghiệm trong `PROJECT_REQUIREMENTS.md`. Không bịa số liệu, log, trích dẫn, bản dịch chuẩn hoặc kết luận cải thiện.
7. Không commit thông tin xác thực, môi trường ảo, cache, checkpoint lớn hoặc dữ liệu bị hạn chế chia sẻ. Thiết lập `.gitignore` khi bổ sung các thành phần tương ứng.
8. Không chạy huấn luyện dài, tải checkpoint lớn hay crawl diện rộng chỉ để kiểm tra thay đổi tài liệu. Khi crawl, giữ tốc độ phù hợp, kiểm tra điều kiện truy cập và `robots.txt`; không tự mở rộng quy mô ngoài nhiệm vụ.
9. Khi được yêu cầu sửa đề cương, cập nhật bản Markdown và xuất PDF bằng `scripts/build_proposal.py`; giữ bản trước sửa để đối chiếu, theo hướng dẫn tại `docs/REVIEW_DE_CUONG.md`. Ghi đề xuất thay đổi phạm vi hoặc mô hình vào `PROJECT_CONTEXT.md`; không tự coi đề xuất đã được giảng viên chấp thuận.
10. Dùng tiếng Việt trong tài liệu và trao đổi mặc định. Khi bàn giao, nêu thay đổi, cách kiểm tra và giới hạn còn lại.

## Làm việc theo nhánh tuần

Nhánh chính của repo là **`master`**. Mỗi tuần công việc có một nhánh tích hợp theo tên trong [kế hoạch tuần](TASKS.md#kế-hoạch-theo-tuần); nhánh chính lưu các thay đổi đã được kiểm tra và review.

1. Trước khi sửa, kiểm tra `git status --short --branch` và các nhánh local/remote; xác định tuần, mã Txx và phụ thuộc của nhiệm vụ được giao. Tiếp tục nhánh phù hợp đã có; không chọn tuần chỉ theo ngày hiện tại hoặc tự mở rộng sang mọi việc trong tuần.
2. Khi bắt đầu tuần mới, chỉ tạo nhánh tuần đó từ `master` đã cập nhật và chứa kết quả tuần trước đã merge. Không tạo trước cả 11 nhánh. Nếu tuần trước chưa merge, hoàn tất phần tích hợp hoặc ghi rõ phụ thuộc và hướng xử lý trước khi tạo nhánh kế tiếp.
3. Làm việc triển khai trên nhánh tuần, không sửa trực tiếp trên `master`. Việc chuẩn bị trước tuần 1 hoặc sửa riêng tài liệu/quy trình dùng nhánh `docs/<noi-dung>` từ `master`; không tính thành kết quả đã hoàn thành của tuần 1. Giữ nguyên thay đổi đang có theo quy tắc 1 ở trên.
4. Hai người có thể dùng chung nhánh tuần, đồng bộ trước khi tích hợp. Nếu cần tách việc để review, tạo nhánh `task/week-XX-Txx-<noi-dung>` từ nhánh tuần rồi merge trở lại nhánh tuần đó. Không force-push hoặc viết lại lịch sử nhánh dùng chung. Khi commit, chia theo đầu việc và nêu mã Txx nếu có.
5. Trước khi merge về `master`: review toàn bộ diff, chạy kiểm tra phù hợp theo [README](README.md#bắt-đầu), cập nhật tài liệu liên quan và bằng chứng trong `TASKS.md`. Nếu `master` có thay đổi mới, tích hợp vào nhánh tuần, xử lý xung đột và kiểm tra phần bị ảnh hưởng trước khi merge.
6. Khi kết thúc tuần, merge phần đã ổn định; ưu tiên merge commit (`--no-ff`) để giữ mốc từng tuần. Ghi mã commit merge hoặc liên kết PR tại `TASKS.md`; có thể tạo tag `week-XX-done` tại commit tích hợp. Tag chỉ ghi mốc bàn giao, không thay thế trạng thái nghiệm thu từng việc.
7. Việc chưa xong giữ đúng trạng thái **Đang làm/Bị chặn**, ghi nguyên nhân, phần còn lại và tuần tiếp tục; không đánh dấu hoàn thành để kịp merge. Phần còn làm được tiếp tục trên nhánh tuần sau, không đưa thay đổi làm hỏng luồng đang hoạt động vào `master`. Dữ liệu/checkpoint vẫn theo mục **Quy tắc làm việc** và `.gitignore`; merge nhánh không tự chuyển các file bị bỏ qua.
8. Thực hiện commit, push, merge hoặc tạo tag theo phạm vi công việc đã được người dùng giao; việc đọc quy trình này không tự khởi chạy các thao tác đó. Khi bàn giao, nêu nhánh đang làm, mã việc, kiểm tra đã chạy, trạng thái merge và phần cần tiếp tục.

## Cập nhật đúng nơi

- Bối cảnh, phạm vi, quyết định: `PROJECT_CONTEXT.md`.
- Thiết kế, giao tiếp giữa các thành phần: `ARCHITECTURE.md`.
- Yêu cầu và tiêu chí nghiệm thu: `PROJECT_REQUIREMENTS.md`.
- Tiến độ, đầu việc, bằng chứng: `TASKS.md`.
- Cách cài đặt và vận hành đã kiểm chứng: `README.md`.
- Quy tắc dành cho agent: `AGENTS.md`.

Không chép lại nội dung chi tiết giữa các file; dùng liên kết và mã yêu cầu/công việc. Cập nhật tài liệu khi có thay đổi liên quan, không cần ghi nhật ký chỉ vì đã đọc repo. Lệnh kiểm thử chuẩn nằm tại README. Khi thay đổi pipeline hoặc chạy thêm bước xử lý, cập nhật tài liệu quy trình dữ liệu và manifest để người đọc biết bước nào đã thực hiện, đầu vào/đầu ra và giới hạn kiểm chứng.
