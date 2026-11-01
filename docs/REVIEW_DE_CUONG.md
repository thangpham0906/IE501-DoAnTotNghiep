# Rà soát và cập nhật đề cương đồ án

Cập nhật ngày **01/11/2026**, sau review lần 2. [PDF hiện tại](DeCuongDATN_25410304_25410313.pdf) và [bản Markdown](DeCuongDATN_25410304_25410313.md) đã được sửa theo yêu cầu người dùng. Bản mới có 8 trang A4, hai sơ đồ vector, sáu tài liệu tham khảo và kế hoạch 11 tuần từ 05/11/2026 đến 17/01/2027. Đã giữ [PDF gốc trước cập nhật](archive/DeCuongDATN_25410304_25410313_truoc_cap_nhat_2026-11-01.pdf) và [bản 6 trang trước sửa lần 2](archive/DeCuongDATN_25410304_25410313_truoc_review_lan_2_2026-11-01.pdf).

Đây là bản nội dung đã cập nhật theo yêu cầu người dùng, chưa phải xác nhận giảng viên đã duyệt các lựa chọn kỹ thuật. Ngày ký và chỗ ký để trống; không tự thêm lớp khi chưa có thông tin.

## Các mục đã cập nhật trong PDF

| Vị trí bản mới | Nội dung đã sửa | Điểm cần tiếp tục xác minh khi triển khai |
| --- | --- | --- |
| Thông tin đầu đề, trang 1 | Đổi thời gian thành 05/11/2026–17/01/2027; giữ tên đề tài, sinh viên và giảng viên | Điền lớp nếu biểu mẫu thực tế yêu cầu; ngày ký theo thời điểm ký thực tế |
| Mục 1, trang 1 | Làm rõ bài toán nguồn, kiểm định và dữ liệu dịch; dẫn nguồn dịch ngược | Tiếp tục tổng quan tài liệu trong báo cáo |
| Mục 2, trang 1 | Tách mục tiêu tổng quát/cụ thể, nhấn mạnh dữ liệu, QC, tăng cường và khả năng tái hiện | Không coi tăng điểm số là kết quả đã có |
| Mục 3, trang 2 | Xác định phạm vi văn bản/web/giọng nói; NLLB là hướng khảo sát, cấu hình chốt sau thử nghiệm | D01–D04 vẫn mở; chưa kết luận mô hình/ASR phù hợp |
| Mục 4.1, trang 2 | Nguồn ưu tiên, cách tạo song ngữ; mốc xác nhận người duyệt, rà thử và chốt quy mô | Nguồn/người duyệt phải xác nhận thực tế; cuối tuần 2 chốt số mẫu từng tập |
| Mục 4.2, trang 3 | Sơ đồ có nhánh đơn ngữ → dịch ngược → U → QC, chống rò rỉ và cố định mô hình sinh | Thực hiện trên dữ liệu đủ điều kiện |
| Mục 4.3, trang 4 | Ma trận E0/E1/E2/E1-M/A1/A2, đối chứng cùng N, giới hạn số cấu hình và ngân sách | R1/R2, mô hình/phần cứng và N chưa chốt; chưa có kết quả chạy |
| Mục 4.4, trang 4 | Metric có nguồn; mẫu chấm dự kiến, ẩn tên, thang 1–5, chấm độc lập một phần và giới hạn | Chốt nhân lực/số mẫu chính thức, thử hướng dẫn trên validation |
| Mục 4.5–4.6, trang 5 | Sơ đồ demo, transcript/lỗi và rủi ro–ứng phó gắn với mốc tuần 1–2 | Kiểm chứng âm thanh và khả năng vận hành |
| Mục 5, trang 6 | Sản phẩm và bằng chứng bao gồm đối chứng, seed/ID mẫu, chi phí và phiếu chấm | Đối chiếu với kế hoạch sau khảo sát, không coi đề cương là kết quả |
| Mục 6, trang 6–7 | 11 tuần công việc, cập nhật E1-M, hai ablation và các mốc chốt; tuần cuối 4 ngày | Theo dõi tiến độ thực tế tại TASKS |
| Mục 7, trang 8 | Sáu tài liệu gốc về dịch ngược, NLLB, Whisper, SacreBLEU, chrF, COMET; liên kết bấm được | Trích dẫn cơ sở phương pháp không chứng minh mô hình phù hợp với tiếng Tày |

## Các điểm đã xử lý sau review lần 2

1. **Khả thi dữ liệu:** tuần 1 xác nhận nguồn/người duyệt, rà thử tối đa 30 cặp có nguồn; tuần 2 chốt quy mô từng tập và lịch duyệt từ năng suất/nguồn thực tế. Nếu thiếu điều kiện, trao đổi GVHD trước mốc đóng băng tuần 3. Chưa tự ghi số corpus đạt được hay tên người duyệt.
2. **Đối chứng QC:** thêm E1-M, lấy ngẫu nhiên không hoàn lại từ U đúng N mẫu của E2 theo từng chiều; cùng khởi tạo và ngân sách huấn luyện. A1/A2 cũng giữ N mẫu để phân tích hai quy tắc đã chọn.
3. **Đánh giá thủ công:** dự kiến 50 câu/chiều, cùng câu cho 4 cấu hình chính, tương ứng 400 bản dịch; ẩn tên, đảo thứ tự và lưu seed. Chấm riêng ba tiêu chí 1–5; dự kiến chấm độc lập ít nhất 20% mẫu nếu có người thứ hai. Các con số là mức lập kế hoạch, cần chốt theo nhân lực cuối tuần 2.
4. **Sơ đồ nghiên cứu:** bổ sung đơn ngữ, checkpoint E0 chiều ngược cố định, tập U, QC đầy đủ/bỏ R1 hoặc R2 và nhánh E1-M. Validation/test không được dùng làm nguồn sinh train.
5. **Giới hạn thực nghiệm:** 6 cấu hình ban đầu; 6 hoặc 12 lượt huấn luyện tùy dùng chung hay tách mô hình theo chiều. Đo chi phí ở tuần 2; lặp E2/E1-M khi đủ ngân sách và công bố giới hạn nếu chỉ một seed.
6. **Cơ sở học thuật:** đã đối chiếu thông tin tác giả, năm, tên bài, định danh và trang xuất bản trên [ACL Anthology](https://aclanthology.org/P16-1009/), [bài NLLB trên arXiv](https://arxiv.org/abs/2207.04672), [bài Whisper trên arXiv](https://arxiv.org/abs/2212.04356) và các trang nguồn liên kết ở mục 7. Không suy ra hỗ trợ tiếng Tày từ tên mô hình đa ngôn ngữ.

Đã đồng bộ thiết kế với PROJECT_CONTEXT, PROJECT_REQUIREMENTS, ARCHITECTURE và TASKS. Trạng thái dữ liệu, thực nghiệm và ứng dụng vẫn theo bằng chứng thực tế, không thay đổi thành hoàn thành vì sửa tài liệu.

## Cách chỉnh tiếp và xuất PDF

- Nội dung: `docs/DeCuongDATN_25410304_25410313.md`.
- Bộ xuất và hai sơ đồ vector: `scripts/build_proposal.py`.
- Phụ thuộc riêng cho tài liệu: `requirements-docs.txt`; không thuộc môi trường huấn luyện.
- Font đã kiểm tra: FreeSerif thường/đậm/nghiêng tại `/usr/share/fonts/truetype/freefont`. Có thể chỉ định thư mục khác bằng `--font-dir` chứa các file cùng tên.

Chạy từ thư mục gốc, xuất bản xem trước:

```bash
python3 -m venv /tmp/ie501-docs-env
/tmp/ie501-docs-env/bin/python -m pip install -r requirements-docs.txt
/tmp/ie501-docs-env/bin/python scripts/build_proposal.py --output /tmp/ie501-proposal-preview.pdf
```

Sau khi kiểm tra bố cục, cập nhật file chính bằng `--output docs/DeCuongDATN_25410304_25410313.pdf --overwrite`. Khi tạo bản sửa mới, lưu PDF hiện tại bằng tên riêng trong `archive/` trước khi ghi đè; không ghi đè các bản lưu đã có. Các dấu `<!-- pagebreak -->`, `<!-- diagram:... -->` và `<!-- signatures -->` trong Markdown là chỉ dẫn cho bộ xuất PDF. Liên kết Markdown dạng `[tên bài](https://...)` được xuất thành liên kết PDF.

Đã xem bố cục 8 trang, đối chiếu nội dung trích xuất với Markdown, kiểm tra 11 khoảng tuần liên tiếp (74 ngày) khớp TASKS và 6 URL tham khảo bấm được trong PDF. Chữ trích xuất nằm trong lề và không chạm footer; bản lưu trước review lần 2 khớp byte với PDF đầu vào. Các kiểm tra này xác nhận tài liệu xuất đúng, không xác nhận chất lượng corpus hoặc mô hình.

## Nhận xét đối chiếu ban đầu

Phần dưới ghi lại các điểm phát hiện **trong bản PDF trước sửa** và cơ sở của việc cập nhật. Số trang trong bảng R01–R11 là số trang bản cũ, không phải bản PDF hiện tại.

## Tài liệu đối chiếu

- [Đề cương Việt–Tày trước sửa của Phạm Quốc Thắng và Lê Minh Thiện](archive/DeCuongDATN_25410304_25410313_truoc_cap_nhat_2026-11-01.pdf).
- [Đề cương hệ thống mô phỏng phỏng vấn AI của Nguyễn Văn Hiền và Chu Văn Thơm](/mnt/c/Users/thangpham/Downloads/DeCuongDATN_25410208_NguyenVanHien_25410314_ChuVanThom.pdf).
- Đối chiếu thêm trạng thái triển khai tại [PROJECT_CONTEXT.md](../PROJECT_CONTEXT.md) và [quy trình dữ liệu](QUY_TRINH_XAY_DUNG_DU_LIEU.md). Nội dung phù hợp đã được chắt lọc vào bản PDF mới; chi tiết vận hành tiếp tục nằm trong repo.

Đề cương tham khảo là một ví dụ trình bày, không phải mẫu quy định hoặc rubric chấm điểm của trường. Hai đề tài có trọng tâm khác nhau: một bên là ứng dụng tương tác AI, một bên là nghiên cứu dữ liệu và tăng cường dữ liệu cho dịch máy.

## Nhận xét tổng thể

Đề cương Việt–Tày đã có lý do, mục tiêu, đối tượng/phạm vi, phương pháp, sản phẩm bàn giao, kế hoạch và phân công. Không cần thêm thật nhiều đầu mục; cần làm các mục hiện có cụ thể hơn, nhất quán hơn và thể hiện cách kiểm chứng đóng góp nghiên cứu.

Đề cương tham khảo trình bày rõ phạm vi đầu vào/chức năng, hai sơ đồ xử lý và sử dụng, việc của từng thành viên theo từng tuần, kết quả đầu ra mỗi tuần và bước thử nghiệm công nghệ sớm. Đề cương Việt–Tày có mục sản phẩm bàn giao riêng và đã giới hạn giọng nói ở mức proof of concept, đây là các nội dung nên giữ.

## Những điểm cần sửa theo mức ưu tiên

| Mã | Ưu tiên | Vị trí trong đề cương Việt–Tày | Nhận xét và ảnh hưởng | Đề xuất |
| --- | --- | --- | --- | --- |
| R01 | Cao | Trang 1: thời gian; mục 6.1 trang 3 | PDF cũ ghi 15/07–15/10/2026 nhưng kế hoạch 18 tuần, không khớp; đã thống nhất khung thay thế | Đã sửa dòng thời gian và bảng kế hoạch PDF theo 05/11/2026–17/01/2027, 11 tuần công việc |
| R02 | Cao | Tên đề tài, mục 2, mục 4 và mục 5 | Tên nhấn mạnh dữ liệu/tăng cường dữ liệu nhưng mục tiêu và sản phẩm khóa vào NLLB; chưa nêu rõ câu hỏi nghiên cứu và đóng góp cần đo | Nêu đóng góp dữ liệu, QC và so sánh thực nghiệm; thêm bước kiểm chứng mô hình trước khi chốt cấu hình |
| R03 | Cao | Mục 2 và giai đoạn 1–3 ở mục 4 | Có thu thập, làm sạch và căn chỉnh nhưng thiếu kế hoạch xác minh nguồn, tạo bản dịch chuẩn và người kiểm duyệt. Chưa cho biết đường đi từ bài đơn ngữ tới cặp song ngữ đáng tin cậy | Bổ sung nguồn dự kiến, trạng thái đơn ngữ/song ngữ, phương pháp căn chỉnh/dịch, người/quy trình kiểm duyệt, metadata và điều kiện sử dụng |
| R04 | Cao | Giai đoạn 4–6, 9 ở mục 4 | Đã nêu baseline, augmentation, ablation và đánh giá thủ công nhưng chưa định nghĩa cấu hình so sánh, yếu tố thay đổi hoặc cách tránh rò rỉ | Thêm ma trận E0/E1/E2, ablation theo quy tắc lọc, validation/test cố định và tiêu chí đánh giá thủ công |
| R05 | Cao | Mục 2, 3 và giai đoạn 7–8 | Đã ghi giọng nói ở mức PoC nhưng chưa rõ nhận âm thanh ngôn ngữ nào, xử lý trường hợp ASR không phù hợp ra sao | Nêu đầu vào âm thanh, chiều dịch được minh họa, cách hiển thị transcript và đánh giá riêng lỗi nhận dạng; kiểm chứng khả thi sớm |
| R06 | Vừa | Mục 4 | Có chín giai đoạn mô tả bằng chữ nhưng không có sơ đồ pipeline hoặc luồng sử dụng. Bản tham khảo có cả hai sơ đồ ở trang 2–3 | Thêm sơ đồ dữ liệu/huấn luyện/đánh giá và sơ đồ người dùng nhập văn bản/âm thanh → nhận kết quả |
| R07 | Vừa | Mục 3 và giai đoạn 7–8 | Có web demo nhưng chưa mô tả các thao tác và giới hạn đầu vào cụ thể | Nêu chọn chiều dịch, nhập văn bản, xem kết quả, tải/thu âm nếu thuộc PoC, kiểm tra lỗi và giới hạn đầu vào |
| R08 | Vừa | Mục 5 | Đã có danh sách sản phẩm nhưng chưa rõ điều kiện nào được xem là bàn giao đủ | Gắn mỗi sản phẩm với bằng chứng: manifest dữ liệu, cấu hình/log/checkpoint, bảng so sánh, hướng dẫn chạy và kịch bản demo |
| R09 | Vừa | Mục 6.1 và 6.2 | Chia công việc theo cụm 3–5 tuần, phân công thành viên riêng ở cuối; thiếu kết quả kiểm tra ở từng mốc | Dùng bảng tuần/ngày — việc của Thắng/Thiện — đầu ra; thêm mốc chốt nguồn, chốt model, đóng băng test và dự phòng |
| R10 | Vừa | Mục 4 hoặc cuối mục 3 | Chưa có phần rủi ro và phương án ứng phó cụ thể; bản tham khảo có nêu độ trễ, chi phí, quyền riêng tư và thử nghiệm AI sớm | Ghi rủi ro dữ liệu, mô hình/ASR, phần cứng và lịch; mỗi rủi ro có bước kiểm tra và phương án điều chỉnh |
| R11 | Thấp | Thông tin đầu đề | Bản tham khảo có lớp của sinh viên; bản Việt–Tày chưa có. Chưa có tài liệu tham khảo trong cả hai PDF | Bổ sung lớp nếu biểu mẫu yêu cầu; cân nhắc danh mục tài liệu học thuật chính, không xem đây là yêu cầu bắt buộc suy ra từ bản tham khảo |

Người dùng đã chọn lịch **05/11/2026–17/01/2027** của bản tham khảo làm chuẩn. Bảng phân công Việt–Tày theo đúng các khoảng tuần được cập nhật tại [TASKS.md](../TASKS.md). Tuần 11 là 14–17/01, chỉ có 4 ngày. R01 đã được xử lý trong PDF cập nhật; bản trước sửa được lưu riêng.

## Cơ sở cho các nội dung bổ sung

### 1. Câu hỏi nghiên cứu và đóng góp

Đề xuất thêm đoạn sau vào mục tiêu/phương pháp, điều chỉnh câu chữ theo phạm vi thống nhất:

> Đề tài tập trung xây dựng quy trình dữ liệu Việt–Tày có thể truy xuất nguồn gốc và đánh giá ảnh hưởng của tăng cường dữ liệu bằng dịch ngược. Các thực nghiệm so sánh dữ liệu song ngữ ban đầu, dữ liệu có bổ sung dịch ngược chưa lọc và dữ liệu có bổ sung dịch ngược đã lọc. Phân tích ablation được dùng để xem xét đóng góp của từng quy tắc kiểm soát chất lượng đối với chất lượng dịch.

Các câu hỏi có thể dùng:

- Bổ sung dữ liệu dịch ngược ảnh hưởng thế nào tới chất lượng dịch theo từng chiều?
- Lọc chất lượng có giúp cải thiện so với dữ liệu dịch ngược chưa lọc không?
- Quy tắc lọc nào hữu ích, quy tắc nào làm mất dữ liệu có giá trị?

Đây là câu hỏi cần thực nghiệm, không phải cam kết rằng điểm số chắc chắn tăng. Không nhận đóng góp “kiến trúc mô hình mới” nếu công việc thực tế là lựa chọn hoặc fine-tune mô hình hiện có.

### 2. Kế hoạch dữ liệu và khả thi

Trong đề cương nên có một bảng ngắn gồm nguồn dự kiến, đơn vị dữ liệu, cách lấy, cách có bản dịch Việt/Tày, phương thức kiểm duyệt và đầu ra. Cần phân biệt bài đơn ngữ, mục từ, cặp câu, cặp đã kiểm duyệt và dữ liệu tổng hợp.

Với trạng thái repo hiện tại, không dùng 527 bản ghi thô hoặc 174 câu đơn ngữ để tuyên bố đã có corpus song ngữ chuẩn. Nếu đưa số liệu khảo sát ban đầu vào PDF, ghi ngày kiểm kê và loại bản ghi. Không nhất thiết đưa toàn bộ thống kê vận hành vào đề cương.

Nên có mục tiêu quy mô dự kiến hoặc mốc khảo sát để chốt quy mô, kèm kế hoạch người có năng lực ngôn ngữ kiểm duyệt. Không tự đặt một số lượng lớn khi chưa có nguồn và nhân lực tương ứng.

### 3. Thiết kế thực nghiệm

| Cấu hình | Train | Điều cần kiểm chứng |
| --- | --- | --- |
| E0 | Dữ liệu song ngữ đã kiểm định | Baseline |
| E1 | E0 + dịch ngược chưa lọc | Tác động của việc thêm dữ liệu |
| E2 | E0 + dịch ngược đã lọc | Tác động của QC |
| Ablation | E0 + biến thể bỏ từng quy tắc lọc | Đóng góp của từng quy tắc |

Nêu rõ cùng tập validation/test, cùng chiều đánh giá, cấu hình mô hình và ngân sách huấn luyện có thể so sánh. Chia theo tài liệu và kiểm tra trùng/gần trùng; không đưa validation/test vào nguồn sinh train. Lưu ý E1/E2 khác số mẫu sau lọc: phải báo cáo lượng dữ liệu và hạn chế suy luận, hoặc thêm đối chứng cùng số mẫu khi khả thi.

Đánh giá thủ công đã được nhắc trong PDF nhưng nên cụ thể hóa: ai đánh giá, chọn mẫu ra sao, tiêu chí đúng nghĩa/đủ ý/tự nhiên, cách ghi nhận và xử lý bất đồng. Các chỉ số tự động cần ghi cấu hình, báo cáo riêng hai chiều; cần kiểm chứng mức phù hợp của chỉ số dựa trên mô hình như COMET.

### 4. Mô hình và giọng nói

Đề cương tham khảo để việc chốt công nghệ sau thử nghiệm khả thi. Với đề tài này, nên bổ sung bước kiểm chứng khả năng xử lý Việt–Tày, tokenizer, tài nguyên và phương pháp fine-tune trước khi cam kết cấu hình cuối cùng.

Nhận xét này không kết luận NLLB hoặc Whisper chắc chắn dùng được/không dùng được. PDF hiện chưa cung cấp bằng chứng đó. Nếu thay đổi hướng mô hình đã đăng ký, cần phản ánh nhất quán ở mục tiêu, phương pháp, sản phẩm và phân công.

Giọng nói cần tách rõ ASR → transcript ngôn ngữ nguồn → dịch văn bản. Một kịch bản có thể xem xét là âm thanh tiếng Việt → transcript Việt → bản dịch Tày, sau khi kiểm chứng. Không tự suy ra demo có khả năng nhận dạng tiếng Tày hoặc dịch giọng nói hai chiều. Phần PoC vẫn đang nằm trong sản phẩm đăng ký; muốn giảm/bỏ cần ghi nhận điều chỉnh phạm vi.

### 5. Sơ đồ, chức năng và tiêu chí bàn giao

Hai hình phù hợp để bổ sung:

1. Pipeline nghiên cứu: thu thập → kiểm định/cách ly → chuẩn hóa/căn chỉnh → chia tập → E0/E1/E2 → đánh giá và phân tích lỗi. Thể hiện test độc lập với dữ liệu huấn luyện/tăng cường.
2. Luồng demo: chọn chiều → nhập văn bản hoặc âm thanh trong phạm vi hỗ trợ → kiểm tra đầu vào/ASR → dịch → hiển thị transcript và bản dịch hoặc thông báo lỗi.

Có thể tóm tắt kiến trúc bằng các khối giao diện, API, suy luận, ASR và lưu trữ mô hình/dữ liệu. Chưa cần đưa hết cấu trúc thư mục, tên script hoặc mọi API vào đề cương.

| Sản phẩm đã nêu trong PDF | Tiêu chí nên bổ sung |
| --- | --- |
| Bộ dữ liệu | Có phiên bản, nguồn, quy trình kiểm duyệt, thống kê và cách chia tập |
| Công cụ xử lý | Có lệnh chạy, điều kiện đầu vào, log/manifest và hướng dẫn tái hiện |
| Mô hình | Có cấu hình, tokenizer, checkpoint, log và kết quả đánh giá hai chiều |
| Thực nghiệm | Có bảng E0/E1/E2/ablation và phân tích kết quả, kể cả khi không cải thiện |
| Web/giọng nói | Có chức năng trong phạm vi đã chốt, xử lý lỗi, mẫu demo và hướng dẫn chạy |
| Báo cáo/slide | Kết luận liên kết tới bằng chứng; nêu giới hạn và việc chưa hoàn thành |

### 6. Kế hoạch và phân công

Giữ hướng phân công hiện có; đã lập bảng từng tuần và đầu ra trong [TASKS.md](../TASKS.md) theo khung 05/11/2026–17/01/2027. Khi đưa vào đề cương có thể trình bày theo ba cột:

| Thời gian | Công việc theo thành viên | Kết quả kiểm tra được |
| --- | --- | --- |
| Tuần 1–11 theo khung đã chọn | Thắng: đầu việc dữ liệu/web/âm thanh; Thiện: đầu việc mô hình/thực nghiệm; cả hai: tích hợp và đánh giá | Một hoặc vài sản phẩm có thể xem, chạy hoặc kiểm tra |

Các mốc cần xuất hiện: chốt phạm vi và công nghệ; xác minh nguồn/quy trình kiểm duyệt; đóng băng validation/test; baseline; sinh/lọc dữ liệu; E1/E2/ablation; demo; đánh giá và hoàn thiện báo cáo. Phân biệt các việc có thể làm song song với việc bắt buộc chờ dữ liệu/mô hình. Dành thời gian sửa lỗi và diễn tập bảo vệ.

## Các việc còn cần chốt trước khi nộp hoặc triển khai

1. Rà soát bản sửa với giảng viên, nhất là cách chọn mô hình, phạm vi âm thanh và tiêu chí đánh giá.
2. Chốt nguồn dữ liệu và người/quy trình kiểm duyệt; không mặc định corpus hiện có đã là dữ liệu chuẩn.
3. Bổ sung thông tin lớp nếu cần và ngày ký thực tế khi hoàn thiện hồ sơ. Không chép ngày ký của nhóm tham khảo.
4. Duy trì và mở rộng tổng quan tài liệu từ sáu nguồn đã kiểm tra ở mục 7; cập nhật nguồn khi chốt mô hình hoặc thay đổi phương pháp.

Kế hoạch, cấu hình kỹ thuật và kết quả triển khai tiếp tục được quản lý trong PROJECT_CONTEXT, ARCHITECTURE, PROJECT_REQUIREMENTS và TASKS. Việc cập nhật đề cương không đánh dấu hoàn thành các thực nghiệm hoặc tính năng chưa triển khai.
