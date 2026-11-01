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

Nhánh chính của repo là **`master`**. Trong Orca, mỗi nhánh tuần có **một worktree với thư mục riêng**, theo tên trong [kế hoạch tuần](TASKS.md#kế-hoạch-theo-tuần). Giữ worktree của `master` để tích hợp; mở workspace của tuần để làm việc, không đổi qua lại các nhánh trong cùng một thư mục.

1. Trước khi sửa, kiểm tra `git status --short --branch`, các nhánh local/remote và worktree hiện có; xác định tuần, mã Txx và phụ thuộc của nhiệm vụ được giao. Trong Orca, đọc skill `orca-cli` và dùng CLI đúng phiên để xem/tạo worktree. Tiếp tục trong worktree phù hợp đã có; không chọn tuần chỉ theo ngày hiện tại hoặc tự mở rộng sang mọi việc trong tuần.
2. Khi bắt đầu tuần mới, tạo worktree qua Orca, chọn `--base-branch master` đã cập nhật và chứa kết quả tuần trước đã merge; dùng `--branch` đặt tên theo `TASKS.md`. Xác minh nhánh, đường dẫn và ID thực tế Orca trả về. Không tạo trước cả 11 worktree. Nếu tuần trước chưa merge, xử lý hoặc ghi rõ phụ thuộc trước khi tạo tuần kế tiếp. Quan hệ cha/con trong Orca không thay thế việc chọn Git base.
3. Không dùng `git switch` để biến workspace đang có người/agent làm việc thành nhánh tuần khác. Nhánh đã có worktree thì mở đúng workspace đó. Việc chuẩn bị trước tuần 1 hoặc sửa riêng tài liệu/quy trình dùng nhánh `docs/<noi-dung>` trong worktree riêng khi tạo mới; không tính thành kết quả đã hoàn thành của tuần 1. Giữ nguyên thay đổi và phiên làm việc đang có.
4. Hai người có thể đồng bộ cùng nhánh tuần trên các máy riêng. Khi cần làm đồng thời trong cùng repo, dùng nhánh `task/week-XX-Txx-<noi-dung>` với worktree riêng từ nhánh tuần, rồi merge trở lại nhánh tuần đó; không ép checkout cùng một nhánh ở hai worktree. Không force-push hoặc viết lại lịch sử nhánh dùng chung. Khi commit, chia theo đầu việc và nêu mã Txx nếu có.
5. Trước khi merge về `master`: review toàn bộ diff, chạy kiểm tra phù hợp theo [README](README.md#bắt-đầu), cập nhật tài liệu liên quan và bằng chứng trong `TASKS.md`. Nếu `master` có thay đổi mới, tích hợp vào nhánh tuần, xử lý xung đột và kiểm tra phần bị ảnh hưởng trước khi merge.
6. Khi kết thúc tuần, merge phần đã ổn định qua PR hoặc tại worktree đang checkout `master`; không chuyển nhánh của worktree tuần để merge. Ưu tiên merge commit (`--no-ff`) để giữ mốc từng tuần. Ghi mã commit merge hoặc liên kết PR tại `TASKS.md`; có thể tạo tag `week-XX-done` tại commit tích hợp. Tag chỉ ghi mốc bàn giao, không thay thế trạng thái nghiệm thu từng việc.
7. Việc chưa xong giữ đúng trạng thái **Đang làm/Bị chặn**, ghi nguyên nhân, phần còn lại và tuần tiếp tục; không đánh dấu hoàn thành để kịp merge. Tiếp tục phần còn làm trong worktree tuần sau, không đưa thay đổi làm hỏng luồng đang hoạt động vào `master`.
8. Worktree mới không tự có dữ liệu, checkpoint hoặc môi trường cục bộ bị `.gitignore` loại khỏi Git. Trước khi chạy pipeline, xác định đầu vào bằng cấu hình hoặc bản sao đã đối chiếu hash; giữ đầu vào dùng chung chỉ đọc và đầu ra từng worktree riêng. Tuân thủ mục **Quy tắc làm việc**; chỉ dọn worktree sau khi đã bảo toàn thay đổi và đầu ra cần giữ, kể cả file bị Git bỏ qua.
9. Thực hiện commit, push, merge hoặc tạo tag theo phạm vi công việc đã được người dùng giao; việc đọc quy trình này không tự khởi chạy các thao tác đó. Khi bàn giao, nêu nhánh, worktree/đường dẫn, mã việc, kiểm tra đã chạy, trạng thái merge và phần cần tiếp tục.

## Cập nhật đúng nơi

- Bối cảnh, phạm vi, quyết định: `PROJECT_CONTEXT.md`.
- Thiết kế, giao tiếp giữa các thành phần: `ARCHITECTURE.md`.
- Yêu cầu và tiêu chí nghiệm thu: `PROJECT_REQUIREMENTS.md`.
- Tiến độ, đầu việc, bằng chứng: `TASKS.md`.
- Cách cài đặt và vận hành đã kiểm chứng: `README.md`.
- Quy tắc dành cho agent: `AGENTS.md`.

Không chép lại nội dung chi tiết giữa các file; dùng liên kết và mã yêu cầu/công việc. Cập nhật tài liệu khi có thay đổi liên quan, không cần ghi nhật ký chỉ vì đã đọc repo. Lệnh kiểm thử chuẩn nằm tại README. Khi thay đổi pipeline hoặc chạy thêm bước xử lý, cập nhật tài liệu quy trình dữ liệu và manifest để người đọc biết bước nào đã thực hiện, đầu vào/đầu ra và giới hạn kiểm chứng.
