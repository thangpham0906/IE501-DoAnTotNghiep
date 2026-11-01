# Công việc và tiến độ

Cập nhật: **01/11/2026**.

**Thời gian thực hiện:** 05/11/2026–17/01/2027. Lịch dưới đây là mục tiêu triển khai; trạng thái thực tế vẫn được theo dõi riêng bằng các mã T01–T27.

## Trạng thái hiện tại

- Đã có đề cương PDF, tài liệu tham khảo về giảng viên và bộ tài liệu quản lý dự án tại thư mục gốc.
- Đã nhập 8 file dữ liệu thô: 106 bài VOV4 và 421 bản ghi ứng viên song ngữ (mục từ/câu), tổng 527 bản ghi. Chưa xác nhận bản ghi nào đủ điều kiện huấn luyện.
- Đã có 97 ứng viên tài liệu, 174 câu đơn ngữ ở `interim/`, log crawl và 100 bản dịch ngược bị loại ở `quarantine/`. Không cộng các tầng này thành số mẫu độc lập.
- Đã có pipeline dữ liệu dùng Python standard library, 23 kiểm thử đạt; đã chạy lại trích xuất và kiểm kê. Chưa có dữ liệu `processed/`, train/validation/test, checkpoint hoặc môi trường huấn luyện.
- Đã có hướng dẫn từng bước với lệnh, đầu vào/đầu ra và bằng chứng để báo cáo giảng viên. Hai file tái tạo tại `interim/replay-2026-11-01/` là bản kiểm tra, không làm tăng số mẫu độc lập.
- Chưa có thực nghiệm hoặc ứng dụng demo được xác minh.

Đọc phạm vi và các quyết định D01–D04 tại [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md), tiêu chí F/Q tại [PROJECT_REQUIREMENTS.md](PROJECT_REQUIREMENTS.md), thiết kế tại [ARCHITECTURE.md](ARCHITECTURE.md).

Phương án gom T02–T23 vào 8 nhóm nằm tại [.agents/BRANCHES.md](.agents/BRANCHES.md), hiện là đề xuất và chưa tạo các nhánh mới. Mỗi nhóm khi triển khai dùng báo cáo `.agents/reports/<nhom>.md`, theo dõi từng Txx bên trong; xem [cách cập nhật/review](.agents/README.md). Đợt 22 nhánh đã hủy không thay đổi trạng thái triển khai dưới đây.

## Cách theo dõi

- Trạng thái: **Chưa làm**, **Đang làm**, **Bị chặn**, **Hoàn thành**.
- Chỉ đánh dấu hoàn thành khi có đầu ra và bằng chứng đáp ứng yêu cầu liên quan. Có code hoặc có tài liệu chưa đồng nghĩa đã chạy thành công.
- Khi bắt đầu một việc, ghi người thực hiện, mã Txx, phạm vi file/thành phần, đầu vào/đầu ra, nhánh/worktree thực tế, base/đích merge và mốc tuần dự kiến vào báo cáo `.agents/reports/<nhom>.md`. Khi bị chặn, ghi nguyên nhân và điều kiện tiếp tục; khi bàn giao, thêm liên kết file, kết quả kiểm tra hoặc run ID. Người tích hợp cập nhật trạng thái trong file này theo từng Txx sau review/merge hoặc mốc tổng hợp.
- Khi bàn giao tuần, ghi mã việc đã hoàn thành/chưa hoàn thành, nhánh, kiểm tra và giới hạn. Ghi commit merge hoặc liên kết PR khi đã tích hợp; nếu chưa thì ghi **Chưa merge**. Việc chuyển tuần giữ mã Txx và trạng thái thực tế, bổ sung phần còn lại và tuần tiếp tục. Có thể ghi tại dòng công việc hoặc phần bằng chứng bên dưới, không cần lặp lại toàn bộ kế hoạch.
- Cột phụ thuộc xác định điều kiện hoàn tất trước khi nghiệm thu. Các nhiệm vụ ở nhiều tuần có thể phát triển song song: viết khung và kiểm thử bằng fixture/mock được ghi rõ trong lúc chờ đầu vào thật; không dùng kết quả giả thay cho phụ thuộc còn thiếu. Ghi riêng phần đã kiểm thử độc lập và phần còn chờ tích hợp.
- Tách công việc thành dòng mới khi quá lớn; giữ mã hiện có để các tài liệu vẫn tham chiếu đúng.

Mỗi nhánh nhóm có phạm vi thành phần và worktree riêng, chứa các Txx liên quan; thống nhất giao tiếp trước khi triển khai. Có thể mở song song các phần dữ liệu, mô hình, tăng cường, đánh giá, backend, frontend, giọng nói và báo cáo. Thứ tự chạy thực nghiệm thật/merge phần phụ thuộc do điều kiện đầu vào quyết định. Quy tắc chi tiết tại [AGENTS.md](AGENTS.md#nhánh-và-worktree).

## Kế hoạch theo tuần

Khung ngày đã được người dùng thống nhất. Phân bổ công việc dưới đây dùng phạm vi Việt–Tày và phân công của nhóm; các đầu ra là mục tiêu, không phải kết quả đã đạt. Đây là mốc tổng hợp/bàn giao; có thể triển khai sớm và song song các nhiệm vụ thuộc nhiều tuần. Tuần 11 chỉ có 4 ngày.

Các tên nhánh tuần dưới đây dùng để tổng hợp khi cần; nhánh nhiệm vụ có thể merge trực tiếp về `master` nếu đó là đích đã xác định. Bảng không phải bằng chứng nhánh/worktree đã tồn tại hoặc công việc đã hoàn thành. Trong Orca, mỗi nhánh được làm trong một worktree có thư mục riêng; đường dẫn và ID lấy từ kết quả tạo thực tế. Cách tạo, tích hợp và bàn giao được quy định tại [AGENTS.md](AGENTS.md#nhánh-và-worktree).

| Tuần | Nhánh tổng hợp khi cần | Thời gian | Phạm Quốc Thắng | Lê Minh Thiện | Kết quả mong đợi / công việc liên quan |
| --- | --- | --- | --- | --- | --- |
| 1 | `week-01-khao-sat-nguon` | 05/11/2026–11/11/2026 | Chọn nguồn chủ lực, xác nhận người duyệt; tổ chức lô rà thử tối đa 30 cặp có nguồn; phác thảo web/giọng nói | Khảo sát mô hình, tokenizer, phần cứng và cách đánh giá | Nguồn, người duyệt, phạm vi chữ viết/ngữ liệu; thời gian và tỷ lệ đạt của lô thử hoặc trở ngại cần xử lý — T02, T03, chuẩn bị T04/T05 |
| 2 | `week-02-chot-du-lieu-mo-hinh` | 12/11/2026–18/11/2026 | Chốt quy mô/lịch duyệt, số mẫu và người chấm thủ công; thử ASR, thiết kế giao diện | Đo chi phí chạy thử, chốt mô hình, ngân sách 6 cấu hình và giao tiếp suy luận | Số mẫu từng tập; nhân lực chấm; phần cứng, giới hạn bước/giờ và phạm vi âm thanh; điều chỉnh với GVHD nếu cần — T02, T04, T05, T06, T07/T08 |
| 3 | `week-03-lam-sach-chia-tap` | 19/11/2026–25/11/2026 | Hoàn thiện lô dữ liệu đã duyệt, làm sạch/căn chỉnh và đối chiếu quy mô | Kiểm tra nhóm tài liệu, trùng/gần trùng, chia tập; hoàn thiện loader/tokenizer | Corpus/manifest đủ điều kiện; validation/test cố định khi đạt kế hoạch đã chốt; code huấn luyện chạy được — T07–T11 |
| 4 | `week-04-baseline` | 26/11/2026–02/12/2026 | Xây dựng giao diện dịch văn bản, kiểm tra đầu vào; kiểm tra mẫu lỗi dữ liệu | Chạy baseline E0, chọn checkpoint bằng validation; xây dựng bộ đánh giá và API suy luận | Baseline có log/checkpoint, kết quả validation; API dịch ban đầu — T12, T13, T19; chuẩn bị T20 |
| 5 | `week-05-tang-cuong-du-lieu` | 03/12/2026–09/12/2026 | Kiểm tra đơn ngữ tách khỏi tập đánh giá, rà lỗi/QC và tích hợp web | Cố định mô hình sinh, tạo U, E1/E2/E1-M; chọn R1/R2 theo dữ liệu phát triển | Manifest U, seed/ID mẫu và số lượng các tập; chốt 2 ablation; web dịch văn bản hoạt động — T13–T15, T19/T20 |
| 6 | `week-06-huan-luyen-doi-chung` | 10/12/2026–16/12/2026 | Kiểm tra mẫu trước/sau lọc, xử lý giao diện; chuẩn bị âm thanh | Huấn luyện E1/E2/E1-M cùng điều kiện; lưu log, chi phí và validation | Checkpoint, bảng đối chứng cùng số mẫu và cấu hình; theo dõi ngân sách đã chốt — T16, chuẩn bị T17/T21 |
| 7 | `week-07-ablation-giong-noi` | 17/12/2026–23/12/2026 | Tích hợp PoC, kiểm tra transcript và lỗi đầu vào | Chạy A1/A2; lặp cặp E2/E1-M với seed khác khi đủ ngân sách; tổng hợp validation | Kết quả 2 ablation, ghi độ ổn định/giới hạn số seed và demo giọng nói — T17, T21 |
| 8 | `week-08-tich-hop-demo` | 24/12/2026–30/12/2026 | Kiểm thử tích hợp web/giọng nói, xử lý lỗi và đo thời gian phản hồi; soạn hướng dẫn | Chốt cấu hình/checkpoint bằng validation, đóng gói suy luận và chuẩn bị đánh giá cuối | Demo tích hợp, cấu hình thực nghiệm đã chốt và hướng dẫn chạy bản nháp — T19–T22; chuẩn bị T18 |
| 9 | `week-09-danh-gia-phan-tich` | 31/12/2026–06/01/2027 | Điều phối chấm ẩn tên hệ thống trên cùng mẫu; tổng hợp lỗi và kiểm thử sử dụng | Đánh giá cuối trên test; tổng hợp E0/E1/E2/E1-M/A1/A2 và phân tích | Kết quả hai chiều, phiếu chấm/seed lấy mẫu, mức nhất trí nếu có hai người, giới hạn và lỗi đã xử lý — T18, T22 |
| 10 | `week-10-bao-cao-slide` | 07/01/2027–13/01/2027 | Hoàn thiện phần báo cáo dữ liệu, web/giọng nói, hướng dẫn và slide | Hoàn thiện phần mô hình/thực nghiệm, kiểm tra log/checkpoint và tài liệu tái hiện | Báo cáo, slide, demo và tài liệu gần hoàn chỉnh; dành thời gian sửa lỗi — T22, T23 |
| 11 | `week-11-ban-giao` | 14/01/2027–17/01/2027 | Rà soát tài liệu, dữ liệu mẫu và trình bày demo | Kiểm tra môi trường, mô hình và phần trình bày thực nghiệm | Cả hai diễn tập, rà soát và hoàn tất bàn giao; không mở thêm hạng mục — T23 |

Các điều kiện cần giữ: tuần 3 chỉ đóng băng tập khi dữ liệu đủ điều kiện; baseline và tăng cường dữ liệu phải chờ bước này. Nếu thiếu dữ liệu hoặc thử mô hình/ASR không đạt, ghi trở ngại và điều chỉnh kế hoạch/phạm vi, không bỏ qua kiểm duyệt để giữ lịch. Có thể viết tổng quan/phương pháp và phát triển khung giao diện song song; không lựa chọn mô hình theo điểm test cuối.

Kiểm tra nguồn/người duyệt vào cuối tuần 1; cuối tuần 2 phải có quy mô từng tập và ngân sách đã khảo sát. Các mức tối đa 30 cặp rà thử và dự kiến 50 câu test/chiều để chấm thủ công là kế hoạch trong đề cương, không phải số mẫu đã có. Nếu không đạt điều kiện, trao đổi GVHD trước mốc đóng băng và ghi điều chỉnh tại D01–D03.

Những việc đã hoàn thành trước 05/11 (T01, T24–T26 và các phần chuẩn bị) được giữ nguyên bằng chứng ngày 01/11; không cần làm lại chỉ để khớp bảng lịch.

## 1. Chuẩn bị

| Mã | Công việc / đầu ra cần có | Liên quan | Phụ thuộc | Trạng thái |
| --- | --- | --- | --- | --- |
| T01 | Tách tài liệu theo bối cảnh, kiến trúc, yêu cầu, công việc và hướng dẫn agent | F10 | — | Hoàn thành |
| T27 | Cập nhật đề cương theo hai lượt review: lịch 11 tuần, sơ đồ tăng cường, E1-M/A1/A2, kế hoạch dữ liệu/chấm thủ công và tài liệu tham khảo; xuất PDF, lưu bản trước sửa | F10 | T01 | Hoàn thành |
| T02 | Kiểm tra mô hình/tokenizer và đo phần cứng; cuối tuần 2 chốt cấu hình, giới hạn bước/giờ cho 6 cấu hình hoặc ghi điều chỉnh | D01, F04 | — | Chưa làm |
| T03 | Tuần 1 xác nhận nguồn, chuẩn tiếng Tày, người duyệt và lô rà thử; cuối tuần 2 chốt quy mô/lịch duyệt | D02, F01, Q01 | — | Chưa làm |
| T04 | Xác minh metric; cuối tuần 2 chốt số mẫu/người chấm, thang điểm 1–5, lấy mẫu/ẩn tên và xử lý bất đồng | D03, F07, Q04 | T02, T03 | Chưa làm |
| T05 | Chốt phạm vi âm thanh và khả năng ASR bằng mẫu thử | D04, F09 | — | Chưa làm |
| T06 | Tổ chức mã nguồn, phụ thuộc, cấu hình, `.gitignore` và kiểm thử nền; đã có phần dữ liệu, còn phần mô hình | Q05, Q07 | T02 | Đang làm |

## 2. Dữ liệu

| Mã | Công việc / đầu ra cần có | Liên quan | Phụ thuộc | Trạng thái |
| --- | --- | --- | --- | --- |
| T24 | Nhập snapshot dữ liệu đầu vào, kiểm tra byte/hash và tạo inventory, source registry, validation report | F01, Q01, Q07 | — | Hoàn thành |
| T25 | Hoàn thiện công cụ dữ liệu, kiểm thử điều kiện duyệt/chia tập và tái hiện ứng viên VOV4 có manifest | F02, F03, Q02, Q05 | T24 | Hoàn thành |
| T26 | Ghi quy trình từng bước, nguồn đầu vào, lệnh đã chạy, kết quả và giới hạn để báo cáo giảng viên | F10, Q04 | T25 | Hoàn thành |
| T07 | Hoàn thiện thu thập/nhập dữ liệu, metadata và danh mục nguồn; bổ sung bằng chứng còn thiếu sau kiểm kê | F01, Q01 | T03, T06, T24 | Đang làm |
| T08 | Audit nguồn, phân loại cách tạo và kiểm duyệt ngôn ngữ/bản dịch; đã kiểm tra cấu trúc và cách ly đầu ra bị loại | F02, Q01 | T07 | Đang làm |
| T09 | Chuẩn hóa, căn chỉnh, khử trùng lặp; xuất thống kê và mẫu kiểm duyệt | F02, Q07 | T08 | Chưa làm |
| T10 | Chia tập theo tài liệu, kiểm tra rò rỉ và cố định manifest | F03, Q02 | T09 | Chưa làm |

T24–T26, phần dữ liệu của T06 và bước kiểm tra cấu trúc của T07/T08 do Codex thực hiện theo yêu cầu người dùng. Người kiểm duyệt ngôn ngữ và bản dịch chưa được phân công. T07/T08 chưa hoàn thành vì cần bằng chứng nguồn và kiểm duyệt nội dung; T09/T10 chỉ thực hiện trên dữ liệu đủ điều kiện. T25 hoàn thành ở mức công cụ và kiểm thử, không có nghĩa đã tạo corpus sạch hoặc chia tập chính thức.

## 3. Mô hình và thực nghiệm

| Mã | Công việc / đầu ra cần có | Liên quan | Phụ thuộc | Trạng thái |
| --- | --- | --- | --- | --- |
| T11 | Hoàn thiện tokenizer, loader, huấn luyện và suy luận hai chiều; kiểm thử bằng dữ liệu nhỏ | F04, Q05 | T06, T10 | Chưa làm |
| T12 | Chạy baseline E0, lưu cấu hình/log/checkpoint và kết quả validation | F04, Q03 | T11 | Chưa làm |
| T13 | Hoàn thiện bộ đánh giá tự động, xuất bản dịch và xác minh cách tính metric | F07, Q04 | T04, T12 | Chưa làm |
| T14 | Chuẩn bị đơn ngữ tách khỏi validation/test; cố định checkpoint E0 chiều ngược để sinh tập U dùng chung | F05, Q02 | T10, T12 | Chưa làm |
| T15 | Chốt ngưỡng QC bằng validation, tạo E1/E2/E1-M, chọn R1/R2; lưu seed/ID mẫu và báo cáo lọc | F05, Q01 | T14 | Chưa làm |
| T16 | Huấn luyện E1/E2/E1-M cùng điều kiện; lưu validation và chi phí, đối chứng E2/E1-M cùng N | F06, Q03 | T12, T15 | Chưa làm |
| T17 | Chạy A1/A2 cùng N; ưu tiên lặp E2/E1-M nếu đủ ngân sách; ghi cấu hình/chi phí và giới hạn số seed | F06, Q03 | T16 | Chưa làm |
| T18 | Đánh giá test cố định; chấm ẩn tên E0/E1/E2/E1-M trên cùng mẫu, lưu điểm gốc và phân tích lỗi | F06, F07, Q04 | T13, T17 | Chưa làm |

## 4. Ứng dụng và bàn giao

| Mã | Công việc / đầu ra cần có | Liên quan | Phụ thuộc | Trạng thái |
| --- | --- | --- | --- | --- |
| T19 | Backend suy luận: kiểm tra đầu vào, chiều dịch, phiên bản mô hình và lỗi | F08, Q05, Q06 | T11, T12 | Chưa làm |
| T20 | Giao diện dịch văn bản và kiểm tra tích hợp với backend | F08, Q06 | T19 | Chưa làm |
| T21 | Tích hợp âm thanh → transcript → bản dịch; ghi phạm vi và mẫu demo | F09, Q06 | T05, T19, T20 | Chưa làm |
| T22 | Chọn checkpoint theo validation, hoàn thiện demo và hướng dẫn vận hành/tái hiện | F08, F09, F10, Q05 | T16, T17, T20, T21 | Chưa làm |
| T23 | Hoàn thiện báo cáo, bảng kết quả, trích dẫn, slide và kịch bản bảo vệ | F10, Q04 | T18, T22 | Chưa làm |

Có thể viết các chương tổng quan/phương pháp và chuẩn bị giao diện trong lúc chờ thực nghiệm; bảng kết quả và kết luận chỉ hoàn thiện khi có bằng chứng tương ứng.

## Bằng chứng hoàn thành

| Công việc | Đầu ra / kiểm tra |
| --- | --- |
| T01 | [README](README.md), [AGENTS](AGENTS.md), [bối cảnh](PROJECT_CONTEXT.md), [kiến trúc](ARCHITECTURE.md), [yêu cầu](PROJECT_REQUIREMENTS.md) và file công việc này |
| T24 | Snapshot `intake-2026-11-01-v1`: [inventory](data/manifests/inventory.json), [danh mục nguồn](data/manifests/source_registry.json), [kiểm tra cấu trúc](data/manifests/validation_report.json). Đã đối chiếu SHA-256 của 12 file; chưa xác minh chất lượng ngôn ngữ hoặc quyền sử dụng |
| T25 | 23 unit tests đạt; [trích xuất tài liệu](data/manifests/replay-2026-11-01/documents.json) và [tách câu](data/manifests/replay-2026-11-01/sentences.json) khớp byte; [làm sạch](data/manifests/replay-2026-11-01/cleaning.json) trả `no_approved_data`; [audit](data/manifests/replay-2026-11-01/audit/validation_report.json) xác nhận 12 file đầu vào giữ nguyên |
| T26 | [Quy trình xây dựng dữ liệu](docs/QUY_TRINH_XAY_DUNG_DU_LIEU.md): phân biệt bước đã chạy, đã kiểm thử và chưa triển khai, có đoạn tổng hợp tiến độ cho giảng viên |
| T27 | [PDF cập nhật](docs/DeCuongDATN_25410304_25410313.pdf), [bản Markdown](docs/DeCuongDATN_25410304_25410313.md), [nhật ký sửa](docs/REVIEW_DE_CUONG.md) và [bản trước review lần 2](docs/archive/DeCuongDATN_25410304_25410313_truoc_review_lan_2_2026-11-01.pdf); đã xem bố cục 8 trang, đối chiếu nội dung với Markdown, 11 khoảng tuần liên tiếp và 6 URL tham khảo trong PDF; bản lưu khớp byte với PDF trước sửa |

Ưu tiên tiếp theo: T03 và phần kiểm định còn lại của T07/T08; T02 và T05 có thể khảo sát song song. Theo dõi chênh lệch tiến độ so với bảng kế hoạch 05/11/2026–17/01/2027 và cập nhật bằng chứng khi hoàn thành.
