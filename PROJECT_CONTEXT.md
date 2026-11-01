# Bối cảnh dự án

## Bài toán

Dự án phục vụ môn **Đồ án tốt nghiệp (IE501)**, nghiên cứu xây dựng dữ liệu và phương pháp tăng cường dữ liệu cho dịch máy **Việt ↔ Tày**. Bài toán đặt ra trong đề cương là thiếu dữ liệu số và dữ liệu song ngữ cho ngôn ngữ ít tài nguyên.

Hướng nghiên cứu gồm thu thập và kiểm định dữ liệu, xây dựng baseline, bổ sung dữ liệu bằng back-translation, lọc chất lượng và đo ảnh hưởng tới chất lượng dịch. Ứng dụng web phục vụ minh họa kết quả nghiên cứu.

Thông tin thành viên và giảng viên nằm tại [README.md](README.md). Tiến độ được quản lý riêng tại [TASKS.md](TASKS.md).

## Mục tiêu

1. Xây dựng bộ dữ liệu Việt–Tày có nguồn rõ ràng và quy trình xử lý có thể kiểm tra.
2. Thiết lập baseline và thực nghiệm tăng cường dữ liệu có điều kiện so sánh nhất quán.
3. Phân tích ảnh hưởng của lọc chất lượng bằng đối chứng cùng số mẫu, hai ablation được chọn và phân tích lỗi dịch.
4. Minh họa dịch văn bản và thử nghiệm giọng nói theo phạm vi đã thống nhất.
5. Hoàn thiện báo cáo, slide và tài liệu tái hiện thực nghiệm.

## Phạm vi nghiên cứu

| Trong phạm vi | Giới hạn |
| --- | --- |
| Dịch Việt ↔ Tày | Câu, đoạn văn ngắn; không cam kết bao phủ mọi phương ngữ |
| Ngữ liệu tin tức, văn hóa, đời sống | Kiểm định từng nguồn trước khi sử dụng |
| Dữ liệu song ngữ và tăng cường dữ liệu | Phân biệt dữ liệu thu thập, nhập tay và tổng hợp |
| Huấn luyện, đánh giá và phân tích lỗi | Kết luận dựa trên thực nghiệm có bằng chứng |
| Web demo và giọng nói | Phục vụ minh họa; giọng nói ở mức proof of concept |

Đề tài không đặt mục tiêu thương mại hoặc dịch hội thoại thời gian thực ở quy mô sản phẩm. TTS và các tính năng ngoài đề cương chưa thuộc phạm vi triển khai hiện tại.

## Đề cương và quyết định còn mở

[Đề cương PDF](docs/DeCuongDATN_25410304_25410313.pdf) đã được cập nhật ngày 01/11/2026, nhấn mạnh dữ liệu và tăng cường dữ liệu. NLLB là hướng khảo sát ban đầu; mô hình/tokenizer/phương pháp fine-tune được chốt sau thử nghiệm khả thi. Whisper là hướng khảo sát ASR; PoC ưu tiên xem xét âm thanh Việt → transcript Việt → dịch Tày. Đánh giá dùng BLEU qua SacreBLEU và chrF; COMET chỉ dùng sau khi xác minh mức phù hợp. Đây là nội dung đề xuất trong bản sửa, không phải xác nhận công nghệ đã triển khai hoặc giảng viên đã duyệt.

| Mã | Nội dung cần xác định | Trạng thái |
| --- | --- | --- |
| D01 | Mô hình baseline, khả năng xử lý Việt–Tày, phương pháp fine-tune và tài nguyên tính toán | Chưa chốt; tuần 2 đo chi phí cho kế hoạch 6 cấu hình, 6 hoặc 12 lượt huấn luyện ban đầu tùy cách tổ chức hai chiều |
| D02 | Nguồn dữ liệu đủ điều kiện, chuẩn biểu diễn tiếng Tày, người/quy trình kiểm duyệt và quy mô khả thi | Đã kiểm kê cấu trúc; nguồn, ngôn ngữ và bản dịch còn chờ kiểm định |
| D03 | Cấu hình chỉ số đánh giá, mức phù hợp của COMET với Việt–Tày và cách đánh giá thủ công | Đã có phương án chấm thủ công đề xuất; cấu hình, số mẫu chính thức và nhân sự chưa chốt |
| D04 | Ngôn ngữ đầu vào âm thanh có thể minh họa, giới hạn Whisper và tập mẫu thử nghiệm | Chưa xác minh |

Khi có quyết định, cập nhật trạng thái kèm ngày, lý do và bằng chứng. Nếu điều chỉnh nội dung đăng ký, ghi rõ phần thay đổi và tình trạng thống nhất với giảng viên; không tự coi một đề xuất là quyết định đã duyệt.

### Bản sửa sau review lần 2 — 01/11/2026

Theo yêu cầu người dùng, bổ sung E1-M lấy ngẫu nhiên cùng số mẫu với E2 từ cùng tập dịch ngược; giới hạn ablation vào A1/A2, bỏ riêng hai quy tắc được chọn từ dữ liệu phát triển. Kế hoạch chính có 6 cấu hình; ưu tiên lặp đối sánh E2/E1-M nếu ngân sách cho phép. Đây là thiết kế đề xuất trong PDF, chưa phải kết quả thử nghiệm hoặc xác nhận GVHD đã duyệt.

D02 có mốc xác nhận nguồn/người duyệt và rà thử tối đa 30 cặp có nguồn ở tuần 1; cuối tuần 2 chốt quy mô từng tập từ tốc độ duyệt và nguồn thực có. D03 dự kiến chấm 50 câu mỗi chiều trên 4 cấu hình, tương ứng 400 bản dịch, có ẩn tên hệ thống, thang điểm 1–5 và chấm độc lập một phần nếu có người thứ hai. Các mức này phục vụ lập kế hoạch, chưa xác nhận nhân lực hoặc số mẫu đạt được; số chính thức phải chốt sau khảo sát. Quy tắc nghiệm thu nằm tại [PROJECT_REQUIREMENTS.md](PROJECT_REQUIREMENTS.md).

## Thời gian thực hiện

Khung thời gian sử dụng cho dự án: **05/11/2026–17/01/2027**, được người dùng thống nhất ngày **01/11/2026**. Kế hoạch gồm **11 tuần công việc**: 10 tuần đủ 7 ngày và tuần cuối từ 14–17/01/2027 (4 ngày), không phải 11 tuần trọn vẹn.

Lịch theo tuần, phân công và đầu ra nằm tại [TASKS.md](TASKS.md). Các việc đã thực hiện trước ngày 05/11 là công tác chuẩn bị; giữ nguyên ngày trong log/manifest và trạng thái hoàn thành, không chuyển thành công việc đã thực hiện trong kỳ mới.

Ngày 01/11/2026, người dùng thống nhất quản lý triển khai theo một nhánh Git cho mỗi tuần, kiểm tra và merge về nhánh chính `master` khi bàn giao. Trong Orca, mỗi nhánh tuần dùng một worktree với thư mục riêng để mở đồng thời với worktree của `master`, tránh đổi nhánh qua lại trong cùng thư mục. Quy tắc thao tác nằm tại [AGENTS.md](AGENTS.md#làm-việc-theo-nhánh-tuần), tên nhánh gắn với lịch nằm tại [TASKS.md](TASKS.md#kế-hoạch-theo-tuần). Việc merge nhánh không đồng nghĩa mọi công việc của tuần đã hoàn thành.

PDF hiện tại đã sử dụng lịch này ở thông tin đầu đề và bảng kế hoạch. Đã lưu [bản trước cập nhật lần đầu](docs/archive/DeCuongDATN_25410304_25410313_truoc_cap_nhat_2026-11-01.pdf) và [bản trước sửa theo review lần 2](docs/archive/DeCuongDATN_25410304_25410313_truoc_review_lan_2_2026-11-01.pdf) để đối chiếu. [Bản Markdown](docs/DeCuongDATN_25410304_25410313.md) dùng để chỉnh nội dung; [nhật ký review](docs/REVIEW_DE_CUONG.md) ghi các mục đã sửa và cách xuất PDF. Các quyết định kỹ thuật còn mở tiếp tục theo dõi tại D01–D04.

## Ghi nhận về dữ liệu

### Ghi nhận D02 — 01/11/2026

Đã ghi nhận snapshot `intake-2026-11-01-v1`. [Danh mục nguồn](data/manifests/source_registry.json) phân biệt metadata khai báo với kết quả xác minh. VOV4 có URL bài viết nhưng chưa xác minh riêng Tày/Nùng và điều kiện sử dụng; bảy bộ dữ liệu còn lại thiếu URL nguồn ở từng bản ghi. Một số cặp câu trùng danh sách viết sẵn trong script sinh dữ liệu; chi tiết đối chiếu nằm trong danh mục nguồn.

Hiện chưa có bản ghi được xác nhận đủ điều kiện huấn luyện. Dữ liệu đầu vào được giữ nguyên để đối chiếu; các bản dịch ngược mang trạng thái bị loại được cách ly để phân tích lỗi. Kiểm tra cấu trúc không thay thế kiểm duyệt ngôn ngữ, nghĩa bản dịch hoặc nguồn gốc. Số lượng và công việc tiếp theo nằm tại [TASKS.md](TASKS.md).

Đã tái hiện luồng trích xuất VOV4 bằng code và đối chiếu khớp byte, đồng thời kiểm thử công cụ kiểm kê, làm sạch và chia tập. Các bước đã chạy, bước chưa chạy và bằng chứng để báo cáo giảng viên nằm tại [quy trình xây dựng dữ liệu](docs/QUY_TRINH_XAY_DUNG_DU_LIEU.md). Việc có công cụ không thay đổi trạng thái chờ kiểm duyệt của corpus.

## Phân công theo đề cương

| Thành viên | Phần việc chính |
| --- | --- |
| Phạm Quốc Thắng | Khảo sát, thu thập và quản lý dữ liệu; web, xử lý âm thanh và điều phối đánh giá |
| Lê Minh Thiện | Khảo sát mô hình, pipeline huấn luyện, fine-tune, quản lý thực nghiệm và tích hợp mô hình vào backend |

Phân công này định hướng trách nhiệm; trạng thái và công việc cụ thể nằm trong `TASKS.md`.

## Rủi ro cần theo dõi

- Nhãn nguồn hoặc nhãn ngôn ngữ chưa phản ánh đúng dữ liệu; cần bằng chứng và kiểm duyệt trước khi dùng.
- Dữ liệu tổng hợp sai nghĩa hoặc rò rỉ giữa các tập có thể làm sai kết luận thực nghiệm.
- Mô hình, chỉ số đánh giá hoặc ASR có thể không phù hợp với tiếng Tày; cần kiểm tra thay vì suy ra từ khả năng đa ngôn ngữ.
- Khối lượng dữ liệu và phần cứng chưa xác định; quy mô huấn luyện phải dựa trên đo đạc thực tế.

Các yêu cầu kiểm soát cụ thể nằm tại [PROJECT_REQUIREMENTS.md](PROJECT_REQUIREMENTS.md); thiết kế giải quyết nằm tại [ARCHITECTURE.md](ARCHITECTURE.md).
