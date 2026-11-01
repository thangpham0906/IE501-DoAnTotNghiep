# Yêu cầu dự án

Tài liệu này xác định chức năng, chất lượng và tiêu chí nghiệm thu. [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) quản lý phạm vi và quyết định; [ARCHITECTURE.md](ARCHITECTURE.md) mô tả thiết kế; [TASKS.md](TASKS.md) theo dõi triển khai theo mã yêu cầu.

Các tiêu chí dưới đây là mục tiêu triển khai, chưa phải kết quả đã đạt. Thay đổi liên quan nội dung đăng ký cần được ghi nhận theo các quyết định D01–D04 trong bối cảnh dự án.

## Yêu cầu chức năng

| Mã | Yêu cầu | Tiêu chí nghiệm thu |
| --- | --- | --- |
| F01 | Thu thập và quản lý dữ liệu Việt–Tày | Có danh mục nguồn, cách thu thập, metadata và dữ liệu thô có thể đối chiếu; phân biệt đơn ngữ/song ngữ và cách tạo |
| F02 | Kiểm định, làm sạch và căn chỉnh | Có quy tắc Unicode, kiểm tra thiếu trường, trùng, căn chỉnh và chất lượng; xuất số lượng trước/sau, mẫu kiểm tra và lý do loại/cách ly |
| F03 | Tạo train/validation/test | Có phiên bản dữ liệu, seed, nhóm theo tài liệu và báo cáo kiểm tra trùng/gần trùng giữa các tập; cố định validation/test cho các cấu hình so sánh |
| F04 | Huấn luyện baseline và dịch hai chiều | Chạy được trên dữ liệu đủ điều kiện, lưu cấu hình/checkpoint/tokenizer và loss; chọn checkpoint bằng validation; có mẫu suy luận Việt → Tày và Tày → Việt |
| F05 | Sinh dữ liệu bằng back-translation và lọc QC | Truy được bản ghi tới nguồn đơn ngữ và mô hình sinh; đúng chiều dịch, có cấu hình lọc, số lượng giữ/loại và lý do |
| F06 | Thực nghiệm E0/E1/E2/E1-M/A1/A2 | Có đối chứng E1-M cùng số mẫu với E2 và hai ablation; lưu seed/ID mẫu, cấu hình, chi phí và kết quả từng chiều trên cùng test; ghi rõ yếu tố thay đổi và giới hạn số seed |
| F07 | Đánh giá và phân tích lỗi | Có bản dịch/reference, metric đúng cấu hình; cùng mẫu chấm ẩn tên hệ thống cho 4 cấu hình chính, phiếu điểm từng tiêu chí và phân tích lỗi; ghi số người, cách lấy mẫu, bất đồng nếu có; COMET được xác minh hoặc ghi nhận điều chỉnh |
| F08 | Web demo dịch văn bản | Nhập văn bản, chọn chiều, nhận bản dịch; xử lý đầu vào không hợp lệ, trạng thái chờ và lỗi mô hình; có phiên bản checkpoint và hướng dẫn chạy |
| F09 | Minh họa giọng nói theo đề cương | Có pipeline âm thanh → văn bản → bản dịch trên ngôn ngữ đầu vào đã kiểm chứng; hiển thị transcript và giới hạn; có mẫu demo và đánh giá lỗi nhận dạng riêng |
| F10 | Báo cáo và bàn giao | Có báo cáo, slide, hướng dẫn môi trường/chạy/tái hiện, mô tả dữ liệu và vị trí lưu mô hình; kết luận truy được tới bằng chứng |

F09 là yêu cầu proof of concept trong đề cương, chưa được coi là hỗ trợ nhận dạng tiếng Tày. Nếu không khả thi hoặc cần giảm phạm vi, ghi nhận tại D04 thay vì tự đánh dấu hoàn thành hoặc tự loại bỏ.

## Yêu cầu chất lượng

| Mã | Yêu cầu | Cách xác nhận |
| --- | --- | --- |
| Q01 | Nguồn gốc và chất lượng dữ liệu có thể kiểm tra | Đối chiếu nguồn/tài liệu, cách tạo và trạng thái kiểm duyệt; không chỉ dựa vào nhãn `source_domain` |
| Q02 | Không rò rỉ dữ liệu đánh giá vào huấn luyện | Kiểm tra ID, hash, tài liệu và gần trùng; kiểm tra cả nguồn đơn ngữ dùng sinh dữ liệu |
| Q03 | Thực nghiệm có thể tái hiện và so sánh | Lưu seed, môi trường, phiên bản dữ liệu, cấu hình và checkpoint; ghi khác biệt và giới hạn tái lập |
| Q04 | Chỉ số và báo cáo phản ánh đúng thực nghiệm | Đối chiếu metric với cách tính, bản dịch và log; không trình bày proxy score như metric dịch máy |
| Q05 | Mã nguồn chạy độc lập với máy phát triển | Khai báo phụ thuộc, dùng đường dẫn cấu hình; chạy kiểm thử và lệnh mẫu được ghi trong README |
| Q06 | Demo xử lý lỗi và giới hạn tài nguyên rõ ràng | Thử đầu vào rỗng, sai chiều, quá dài và mô hình chưa sẵn sàng; đo thời gian suy luận trên cấu hình ghi nhận |
| Q07 | Lưu trữ an toàn và có khả năng đối chiếu | Giữ dữ liệu thô; tách đầu ra xử lý; không commit bí mật/cache/file lớn; ghi điều kiện sử dụng dữ liệu khi có |

## Quy tắc dữ liệu

- Dữ liệu thu thập, nhập tay, sinh bằng template và sinh bởi mô hình phải được phân biệt. “Gold” hoặc “đã kiểm duyệt” cần có quy trình và bằng chứng tương ứng.
- Kiểm tra script sinh dữ liệu và đầu ra crawler; placeholder không chứng minh đã thu thập được dữ liệu.
- Kiểm tra Unicode, trường rỗng, căn chỉnh, lệch nghĩa và ký tự bất thường. Không kết luận sai ngôn ngữ chỉ từ một ký tự hoặc heuristic.
- Nguồn công khai, bao gồm MADLAD-400 `tyz` nếu sử dụng, phải được audit trước khi đưa vào tập chính thức. Bản ghi cách ly cần lý do; chỉ dùng lại sau khi kiểm định.
- Dữ liệu song ngữ để huấn luyện dịch phải có đủ hai phía. Dữ liệu đơn ngữ dùng theo luồng riêng, không gán bản sao câu nguồn làm bản dịch chuẩn.
- Không ghi đè dữ liệu thô trong tiền xử lý. Mỗi tập đầu ra có phiên bản và thống kê để so sánh.
- Việc cho phép một bản ghi vào dữ liệu huấn luyện phải gắn với checksum, số thứ tự bản ghi, người duyệt và bằng chứng nguồn/ngôn ngữ/bản dịch/điều kiện sử dụng. Schema registry và cách thực hiện nằm trong [quy trình dữ liệu](docs/QUY_TRINH_XAY_DUNG_DU_LIEU.md); nhãn tự khai trong raw không thay thế quyết định này.
- Tuần 1 xác nhận nguồn chủ lực, người duyệt và phạm vi chữ viết/ngữ liệu; dự kiến rà thử tối đa 30 cặp có nguồn. Cuối tuần 2 chốt số cặp theo tập, số câu đơn ngữ và lịch kiểm duyệt từ tốc độ duyệt/nguồn thực có. Nếu không đạt mốc, ghi điều chỉnh với GVHD trước khi đóng băng validation/test, không bù bằng dữ liệu chưa duyệt.

## Quy tắc thực nghiệm

| Cấu hình | Dữ liệu train | Câu hỏi cần đánh giá |
| --- | --- | --- |
| E0 | Train song ngữ đã kiểm định | Chất lượng baseline |
| E1 | Train gốc + tập dịch ngược U chưa lọc QC | Tác động của việc thêm dữ liệu tổng hợp |
| E2 | Train gốc + N mẫu U qua đầy đủ QC | Hiệu quả của quy trình lọc |
| E1-M | Train gốc + N mẫu ngẫu nhiên từ U | Đối chứng với E2 cùng số mẫu |
| A1, A2 | Train gốc + N mẫu sau khi bỏ riêng R1 hoặc R2 | Hai ablation so với E2 |

N tính riêng theo chiều, bằng số mẫu E2 sau lọc. E1-M lấy ngẫu nhiên không hoàn lại từ cùng U; A1/A2 bỏ một quy tắc, giữ ngưỡng còn lại và lấy N mẫu từ tập tương ứng. Lưu seed lấy mẫu và danh sách ID. Chọn R1/R2 ở tuần 5 theo tác động trên dữ liệu phát triển và mẫu lỗi đã kiểm duyệt; không chọn bằng kết quả test. Nếu QC không giữ đủ mẫu để so sánh, ghi nhận giới hạn/cấu hình không chạy và điều chỉnh trên dữ liệu phát triển trước đánh giá test.

- Chỉ fit tokenizer/mô hình trên dữ liệu được phân vào train; có thể sử dụng tokenizer pretrained theo cấu hình đã ghi. Đơn ngữ dùng tăng cường phải được kiểm tra tách biệt với validation/test.
- Không dùng validation/test làm nguồn sinh dữ liệu train. Chọn checkpoint, ngưỡng QC và siêu tham số bằng validation; test dùng đánh giá cuối cùng.
- Dùng cùng validation/test cho E0/E1/E2/E1-M/A1/A2. Nếu đổi tập đánh giá, chạy lại các cấu hình cần so sánh.
- Cố định checkpoint E0 chiều ngược và cấu hình giải mã để tạo cùng tập U cho các biến thể. U vẫn phải qua kiểm tra định dạng, trùng và chống rò rỉ; “chưa lọc” chỉ nói đến QC đang nghiên cứu.
- Ghi rõ chiều dịch ở huấn luyện, sinh dữ liệu và đánh giá; kiểm tra nhãn ngôn ngữ trong batch có nhiều chiều.
- Giữ train gốc, khởi tạo, tokenizer, seed huấn luyện, số bước cập nhật, token/batch và cách chọn checkpoint như nhau; ghi lượng dữ liệu/mức lặp mẫu. Đối sánh QC chính là E2 với E1-M; mọi sai khác ngoài thiết kế phải ghi rõ trong kết luận.
- Kế hoạch ban đầu có 6 cấu hình với một seed chung: 6 lượt nếu mô hình chung hai chiều hoặc 12 lượt nếu tách mô hình. Cuối tuần 2 chốt phần cứng, cấu hình và giới hạn bước/giờ từ đo thử, tính cả chi phí dịch ngược. Ưu tiên lặp E2/E1-M với seed khác khi đủ ngân sách; một seed không đủ để khẳng định độ ổn định.
- Mỗi run lưu cấu hình, phiên bản dữ liệu, model/tokenizer, môi trường, lệnh chạy, log, bản dịch và metric theo từng chiều.
- Phân biệt chrF và chrF++ theo cấu hình thực tế. Ghi cách tính và phiên bản công cụ cho BLEU/SacreBLEU; xác minh mức phù hợp của mô hình đánh giá như COMET.
- Kết luận cần phân biệt kết quả đã chạy, kết quả đọc từ file và kết quả chưa xác minh. Nếu chất lượng không cải thiện, báo cáo kết quả và phân tích nguyên nhân.

## Các ngưỡng chưa chốt

Quy mô corpus, ngưỡng BLEU/chrF, giới hạn đầu vào và tài nguyên chưa chốt. Lô rà thử tối đa 30 cặp và mẫu chấm dự kiến 50 câu/chiều là mức lập kế hoạch, không phải số liệu đã có; số chính thức cần xác định cuối tuần 2 từ dữ liệu và nhân lực thực tế.

Phương án chấm tại mục 4.4 của [đề cương](docs/DeCuongDATN_25410304_25410313.md): lấy mẫu ngẫu nhiên phân tầng theo nguồn/độ dài, dùng cùng mẫu cho E0/E1/E2/E1-M, ẩn tên và đảo thứ tự đầu ra, lưu seed. Mức 50 câu/chiều tương ứng 400 bản dịch; nếu test nhỏ hơn thì dùng toàn bộ và nêu giới hạn. Chấm riêng đúng nghĩa/đủ ý/tự nhiên theo thang 1–5 có hướng dẫn/ví dụ đã thử trên validation. Có ít nhất một người đủ năng lực Việt–Tày; dự kiến người thứ hai chấm độc lập ít nhất 20% mẫu nếu bố trí được, lưu điểm gốc và mức nhất trí. Chỉ có một người phải công bố giới hạn. Không coi kế hoạch này là nhân sự đã được xác nhận.
