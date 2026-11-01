# Hướng dẫn làm việc với repo

## Đọc đúng tài liệu

Đọc [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) và [TASKS.md](TASKS.md) để nắm bối cảnh và trạng thái trước khi bắt đầu. Chỉ mở thêm tài liệu liên quan đến nhiệm vụ:

| Khi cần | Đọc |
| --- | --- |
| Nhận nhiệm vụ trên nhánh và ghi báo cáo để review | [Quy định trong .agents](.agents/README.md), [phương án nhánh](.agents/BRANCHES.md) và báo cáo `.agents/reports/<nhom>.md` khi nhóm được triển khai |
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

## Nhánh và worktree

Nhánh chính của repo là **`master`**. Trong Orca, **mỗi nhóm công việc có phạm vi rõ ràng dùng một nhánh và một worktree riêng**; các mã Txx là checklist bên trong nhóm. Có thể triển khai đồng thời các nhiệm vụ thuộc nhiều tuần; [lịch tuần](TASKS.md#kế-hoạch-theo-tuần) là mốc theo dõi/bàn giao, không buộc các nhánh phải chờ hết tuần trước mới được bắt đầu.

Trước khi triển khai, phải đọc [quy định báo cáo](.agents/README.md) và xác định nhóm được giao trong [phương án phân công](.agents/BRANCHES.md). Mỗi nhóm cập nhật `.agents/reports/<nhom>.md` theo từng Txx sau các mốc thực hiện/kiểm tra/bàn giao; người tích hợp tổng hợp vào `TASKS.md`. Phương án chưa chốt không tự tạo nhánh; không ghi “đã làm” chỉ vì có nhánh hoặc kế hoạch.

1. Trước khi sửa, kiểm tra `git status --short --branch`, các nhánh local/remote và worktree hiện có. Xác định mã Txx, người phụ trách, file/thành phần được sửa, đầu vào/đầu ra, phụ thuộc và nhánh nhận kết quả. Tiếp tục trong worktree phù hợp đã có, không tự mở rộng ngoài nhiệm vụ được giao.
2. Trong Orca, đọc skill `orca-cli` và dùng CLI đúng phiên để tạo worktree. Nhóm độc lập mặc định tạo từ `master` đã cập nhật, dùng `--branch` đặt tên theo phân công đã chốt trong `.agents/BRANCHES.md`. Sửa riêng tài liệu dùng `docs/<noi-dung>`. Khi được giao công việc phụ thuộc một nhánh chưa merge, chọn base là nhánh đó và ghi rõ thứ tự tích hợp. Xác minh nhánh, đường dẫn và ID Orca trả về; quan hệ cha/con trong Orca không thay thế Git base.
3. Có thể mở đồng thời các nhánh đã xác định nhiệm vụ, kể cả thuộc tuần sau. Nhánh `week-XX-...` hiện có hoặc trong kế hoạch dùng để tổng hợp theo tuần khi cần; không bắt buộc mọi nhiệm vụ đi qua nhánh tuần. Nếu giao việc trong nhánh tuần, nhánh `task/week-XX-Txx-<noi-dung>` có thể tách từ và merge về nhánh tuần đó. Ghi rõ base/đích merge để tránh tích hợp nhầm.
4. Giữ worktree của `master` để tích hợp. Không dùng `git switch` thay nhánh của workspace đang có người/agent làm việc, không ép checkout cùng một nhánh ở hai worktree và không viết lại lịch sử nhánh dùng chung. Mỗi nhánh tập trung một đầu ra; commit nêu mã Txx nếu có.
5. Trước khi các phần liên quan phát triển song song, thống nhất schema dữ liệu, nhãn chiều dịch, giao diện suy luận, request/response API và quy ước checkpoint/tokenizer có liên quan tại `ARCHITECTURE.md`. Chỉ sửa mục của mình trong file chung; phối hợp người tổng hợp khi nhiều nhánh cần đổi cùng mục. Xử lý conflict theo ý nghĩa thay đổi, không chọn toàn bộ một phía chỉ để Git hết báo lỗi.
6. Có thể viết khung, dùng fixture/mock được ghi rõ và kiểm thử thành phần trong lúc chờ phụ thuộc. Huấn luyện, tăng cường trên corpus thật, đánh giá và nghiệm thu tích hợp vẫn cần đầu vào đủ điều kiện trong `PROJECT_REQUIREMENTS.md` và `TASKS.md`. Không ghi kết quả mô phỏng thành kết quả nghiên cứu hoặc tính năng đã chạy với mô hình thật.
7. Tích hợp từng phần ổn định khi đầu ra trong phạm vi đã đạt và phụ thuộc đã sẵn sàng, không cần chờ cuối tuần hoặc toàn nhóm hoàn thành. Review diff, đồng bộ thay đổi mới từ nhánh đích, xử lý xung đột và chạy kiểm tra phù hợp theo [README](README.md#bắt-đầu), kể cả giao tiếp giữa các thành phần khi bị ảnh hưởng. Merge không báo conflict chưa phải bằng chứng hệ thống hoạt động đúng. Merge qua PR hoặc tại worktree của nhánh đích; ghi commit merge/PR và bằng chứng vào báo cáo nhóm, sau đó người tích hợp cập nhật `TASKS.md` theo từng Txx.
8. Khi bàn giao tuần, tổng hợp các nhánh đã tích hợp và việc còn lại; ưu tiên merge commit khi cần giữ mốc tổng hợp, có thể gắn tag `week-XX-done`. Việc chưa xong tiếp tục trên nhánh nhiệm vụ hiện có, giữ đúng trạng thái **Đang làm/Bị chặn**, không đổi nhánh chỉ vì sang tuần mới. Tag/merge không thay thế trạng thái nghiệm thu từng việc.
9. Worktree mới không tự có dữ liệu, checkpoint hoặc môi trường cục bộ bị `.gitignore` loại khỏi Git. Trước khi chạy pipeline, xác định đầu vào bằng cấu hình hoặc bản sao đã đối chiếu hash; giữ đầu vào dùng chung chỉ đọc và đầu ra từng worktree riêng. Tuân thủ mục **Quy tắc làm việc**; chỉ dọn worktree sau khi đã bảo toàn thay đổi và đầu ra cần giữ, kể cả file bị Git bỏ qua.
10. Thực hiện commit, push, merge hoặc tạo tag theo phạm vi công việc đã được người dùng giao; việc đọc quy trình này không tự khởi chạy các thao tác đó. Khi bàn giao, nêu nhánh, worktree/đường dẫn, mã việc, kiểm tra đã chạy, trạng thái merge và phần cần tiếp tục.

## Cập nhật đúng nơi

- Bối cảnh, phạm vi, quyết định: `PROJECT_CONTEXT.md`.
- Thiết kế, giao tiếp giữa các thành phần: `ARCHITECTURE.md`.
- Yêu cầu và tiêu chí nghiệm thu: `PROJECT_REQUIREMENTS.md`.
- Tiến độ toàn dự án: `TASKS.md`; phân công và báo cáo nhóm: `.agents/BRANCHES.md`, `.agents/reports/<nhom>.md` theo `.agents/README.md`.
- Cách cài đặt và vận hành đã kiểm chứng: `README.md`.
- Quy tắc dành cho agent: `AGENTS.md`.

Không chép lại nội dung chi tiết giữa các file; dùng liên kết và mã yêu cầu/công việc. Cập nhật tài liệu khi có thay đổi liên quan, không cần ghi nhật ký chỉ vì đã đọc repo. Lệnh kiểm thử chuẩn nằm tại README. Khi thay đổi pipeline hoặc chạy thêm bước xử lý, cập nhật tài liệu quy trình dữ liệu và manifest để người đọc biết bước nào đã thực hiện, đầu vào/đầu ra và giới hạn kiểm chứng.
