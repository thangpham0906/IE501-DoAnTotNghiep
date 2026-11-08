# Quy trình xây dựng và kiểm định dữ liệu Việt–Tày

Cập nhật ngày **01/11/2026**. Tài liệu giải thích từng bước tạo, kiểm tra và sử dụng các file trong `data/`, kèm lệnh và bằng chứng để trình bày tiến độ với giảng viên.

## 1. Kết quả đã xác minh

| Giai đoạn | Trạng thái thực tế | Bằng chứng |
| --- | --- | --- |
| Tiếp nhận dữ liệu đầu vào | Có 8 file thô, tổng 527 bản ghi; chưa xác minh tất cả nguồn và bản dịch | [Inventory ban đầu](../data/manifests/inventory.json) |
| Thu thập trực tuyến | Có file bài VOV4 và log; chưa crawl lại trong đợt kiểm tra này | `data/raw/vov4/articles.jsonl`, `data/manifests/vov4_crawl.log` |
| Trích xuất tài liệu VOV4 | Đã chạy lại: 106 bài → 97 ứng viên; khớp từng byte với file đối chiếu | [Lần chạy tài liệu](../data/manifests/replay-2026-11-01/documents.json) |
| Tách câu VOV4 | Đã chạy lại: 97 ứng viên → 174 câu đơn ngữ; khớp từng byte với file đối chiếu | [Lần chạy tách câu](../data/manifests/replay-2026-11-01/sentences.json) |
| Kiểm kê và kiểm tra cấu trúc | Đã chạy bằng script; 12 file của snapshot ban đầu vẫn khớp SHA-256 | [Báo cáo kiểm tra lại](../data/manifests/replay-2026-11-01/audit/validation_report.json) |
| Làm sạch dữ liệu được duyệt | Đã chạy kiểm tra đầu vào; 0 bản ghi được duyệt, không tạo file `processed/` | [Lần chạy làm sạch](../data/manifests/replay-2026-11-01/cleaning.json) |
| Chia train/validation/test | Công cụ được kiểm thử bằng fixture; chưa chia corpus chính thức | `src/data_pipeline/split_dataset.py` và unit tests |
| Tăng cường dữ liệu | Chưa chạy sinh mới; đang giữ 100 bản dịch bị loại để phân tích lỗi | `data/quarantine/e1_backtranslation_rejected.jsonl` |

**527 là số bản ghi thô, không phải số cặp câu song ngữ đã kiểm duyệt.** Không cộng 97, 174 và 100 vào 527 để báo cáo quy mô corpus: đây là các tầng xử lý hoặc dữ liệu phát sinh, có liên hệ với nhau.

## 2. Chuẩn bị môi trường và đọc bằng chứng

Chạy lệnh từ thư mục gốc repository. Pipeline dữ liệu hiện chỉ dùng thư viện chuẩn của **Python >= 3.10**, đã kiểm tra trên Python **3.12.3**; chưa cần PyTorch hoặc SentencePiece.

```bash
python3 --version
python3 -m unittest discover -s src/tests -t . -p 'test_*.py'
```

Kết quả kiểm thử của đợt triển khai: **23 tests passed**. Test dùng dữ liệu giả lập trong thư mục tạm, không ghi vào corpus và không gọi mạng. Các trường hợp gồm từ chối dữ liệu chưa duyệt, checksum đổi, thiếu bản dịch, số bản ghi duyệt sai, bảo toàn file có sẵn, nhóm câu trùng giữa các tập, kiểm kê và robots.txt.

Mỗi lần chạy xử lý có manifest ghi lệnh (`argv`), phiên bản Python, SHA-256 mã pipeline, đầu vào, đầu ra và thống kê. Mốc UTC trong manifest tương ứng ngày địa phương UTC+7. Thời điểm chạy kiểm tra không thay thế ngày thu thập khai báo trong bản ghi.

Corpus và log được lưu cục bộ, chưa đưa lên Git trong khi xác minh nguồn/điều kiện sử dụng. Bản clone chỉ có code và manifest chưa đủ chạy lại nếu thiếu các file dữ liệu được tham chiếu.

## 3. Bước 1 — Tiếp nhận và kiểm kê dữ liệu thô

Giữ nguyên nội dung các file đầu vào; ghi kích thước, SHA-256, số bản ghi và schema để có thể đối chiếu khi xử lý tiếp.

| File dưới `data/raw/` | Bản ghi | Diễn giải hiện tại |
| --- | ---: | --- |
| `vov4/articles.jsonl` | 106 | Bài viết có URL, tiêu đề, mô tả và các khối nội dung; nhãn Tày/Nùng chưa kiểm duyệt |
| `glosbe/dictionary_pairs.jsonl` | 150 | Ứng viên mục từ/cặp văn bản, nguồn chưa xác minh |
| `scripture/tay_scripture.jsonl` | 80 | Ứng viên cặp văn bản, nguồn chưa xác minh |
| `textbook/sgk_tay.jsonl` | 22 | Ứng viên cặp văn bản; nhãn `gold_standard` chưa có đủ bằng chứng kiểm duyệt |
| `jw/tay_jw.jsonl` | 50 | Ứng viên cặp văn bản, nguồn chưa xác minh |
| `local_news/articles.jsonl` | 30 | Bản ghi có hai trường văn bản; chưa xác nhận là bài báo/bản dịch được thu thập thực tế |
| `folk_songs/tay_folk_songs.jsonl` | 30 | Ứng viên cặp văn bản, cần tài liệu và vị trí trích dẫn |
| `dictionary/tay_vi_dict.jsonl` | 59 | Mẫu giao tiếp/từ điển, cần xác minh cách tạo và bản dịch |
| **Tổng** | **527** | **106 bài và 421 bản ghi có hai trường văn bản** |

Bảy bộ ngoài VOV4 đều thiếu `source_url` ở từng bản ghi. Cần bổ sung URL hoặc tên tài liệu, ấn bản, trang/vị trí, phương pháp tạo và người kiểm duyệt. Tên thư mục hoặc `source_domain` chỉ là thông tin khai báo.

Kiểm tra nguồn gốc được ghi trong [source registry](../data/manifests/source_registry.json): 148/150 cặp Glosbe, 80/80 cặp Scripture và 22/22 cặp SGK trùng danh sách literal đã được kiểm tra trong script sinh corpus. Đây là dấu hiệu cần xác minh nguồn, không tự chứng minh tác giả, tính đúng của bản dịch hoặc việc đã crawl từ website. Script sinh đó không thuộc pipeline hiện tại; lần audit mới chỉ giữ lại bằng chứng đã ghi khi hash dữ liệu không đổi, không tuyên bố đã thực hiện lại phép đối chiếu literal.

## 4. Bước 2 — Thu thập VOV4 khi cần bổ sung

`src/data_pipeline/crawl_vov4.py` đọc HTML của mục Tày–Nùng, lấy metadata, mô tả và khối nội dung bài; chỉ lưu URL media, không tải âm thanh/video. Crawler kiểm tra `robots.txt`, giới hạn số bài và giữ delay tối thiểu 1 giây.

Ví dụ cho **một đợt thu thập mới**, chưa chạy trong đợt này:

```bash
python3 src/data_pipeline/crawl_vov4.py \
  --max-pages 100 --delay 1.0 \
  --output data/raw/vov4/batch-YYYYMMDD.jsonl \
  --errors data/interim/crawl-errors-YYYYMMDD.jsonl \
  --manifest data/manifests/crawl-YYYYMMDD.json
```

Thay `YYYYMMDD` bằng ngày/lần chạy mới và chọn phạm vi phù hợp. Mặc định công cụ từ chối ghi đè; `--append` chỉ dùng khi chủ động muốn nối thêm và chấp nhận thay đổi checksum của snapshot. Không dùng số `max-pages` trong ví dụ làm bằng chứng rằng lệnh đó đã tạo ra 106 bài hiện có. Web có thể thay đổi nên một lần crawl mới không bảo đảm tái tạo cùng nội dung.

File raw mới phải được bổ sung vào danh mục nguồn và kiểm định trước khi dùng. Công cụ làm sạch từ chối JSONL chưa có trong registry.

## 5. Bước 3 — Từ bài VOV4 sang ứng viên tài liệu

Đầu vào: `data/raw/vov4/articles.jsonl`.

Thuật toán trong `build_vov_candidates.py`:

1. Chuẩn hóa Unicode NFC và khoảng trắng của `summary_taynung_candidate`.
2. Bỏ bài có mô tả ngắn hơn 40 ký tự: đợt hiện tại loại **9/106** bài theo điều kiện này.
3. Dùng các từ gợi ý để chọn khối văn bản có vẻ là tiếng Việt trong `body_blocks`; đây chỉ là heuristic, không phải mô hình xác định ngôn ngữ đã kiểm chứng.
4. Tạo ID từ URL và lưu cờ như chưa tách Tày/Nùng, chưa xác nhận quyền sử dụng, chưa căn chỉnh câu hoặc thiếu ngữ cảnh tiếng Việt.

**Kết quả:** 97 ứng viên tài liệu. Trong đó 2 có ngữ cảnh Việt được heuristic chọn, 95 chỉ có phía Tày/Nùng ứng viên. Hai bản ghi có ngữ cảnh Việt cũng chưa phải hai cặp dịch đúng nghĩa.

Lệnh đã chạy, tạo bản kiểm tra riêng để giữ file ban đầu:

```bash
python3 src/data_pipeline/build_vov_candidates.py \
  --input data/raw/vov4/articles.jsonl \
  --output data/interim/replay-2026-11-01/vov4_document_candidates.jsonl \
  --manifest data/manifests/replay-2026-11-01/documents.json \
  --compare-to data/interim/vov4_document_candidates.jsonl
```

Manifest ghi `comparison.byte_identical: true`: kết quả tạo lại khớp byte với file đối chiếu. Điều này chứng minh tái hiện được bước trích xuất từ raw hiện có, không chứng minh các câu đã đúng ngôn ngữ hoặc căn chỉnh.

## 6. Bước 4 — Tách câu đơn ngữ ứng viên

`build_vov_sentences.py` tách **phần mô tả ứng viên** theo dấu kết câu `.`, `!`, `?`; với đoạn dài, thử tách tiếp theo dấu phẩy/chấm phẩy/hai chấm quanh mốc 300 ký tự. Mốc này không phải giới hạn cứng nếu đoạn không có vị trí tách. Script loại đoạn quá ngắn theo quy tắc hiện có và khử trùng lặp bằng hash câu sau casefold.

Giữ ID tài liệu nguồn và cờ kiểm tra; đặt `vi_text` thành chuỗi rỗng. **Kết quả 174 câu là đơn ngữ ứng viên**, chưa phải 174 cặp câu dịch. Đầu ra này cũng không đại diện cho việc đã tách toàn bộ thân bài.

```bash
python3 src/data_pipeline/build_vov_sentences.py \
  --input data/interim/replay-2026-11-01/vov4_document_candidates.jsonl \
  --output data/interim/replay-2026-11-01/vov4_sentence_candidates.jsonl \
  --manifest data/manifests/replay-2026-11-01/sentences.json \
  --compare-to data/interim/vov4_sentence_candidates.jsonl
```

Đã chạy và khớp byte với file đối chiếu. Các lệnh ở bước 3–4 sẽ từ chối chạy vào cùng đường dẫn lần nữa; khi muốn kiểm tra lại, đổi **cả đường dẫn output, manifest và input nối tiếp** sang một tên lần chạy mới.

## 7. Bước 5 — Kiểm định nguồn và dữ liệu tổng hợp

Kiểm tra cấu trúc hiện đã có: đọc JSONL, kiểm tra trường, thống kê nguồn, cặp trùng sau NFC/khoảng trắng/casefold, câu có hai phía giống nhau và checksum. Đây chưa phải đánh giá đúng nghĩa bản dịch. Hai ngôn ngữ có thể dùng chung từ nên không tự loại mọi cặp giống nhau.

File `quarantine/e1_backtranslation_rejected.jsonl` chứa **100 bản ghi**, tất cả mang `filter_status: rejected_automatic`. Giữ lại `generation`, `generator`, URL, ID và `quality_flags` để phân tích lỗi. Các cờ có thể gồm đầu ra quá ngắn, tỷ lệ độ dài bất thường, không khớp số hoặc ký tự không hợp lệ.

Đợt này không sinh lại bản dịch, không chạy mô hình và không xác nhận cấu hình/model khai báo đã tạo đúng file. Dữ liệu này không được dùng làm E0 hoặc kết quả chứng minh tăng cường dữ liệu thành công. Chi tiết cờ bị loại nằm trong [báo cáo kiểm kê ban đầu](../data/manifests/validation_report.json).

## 8. Bước 6 — Làm sạch dữ liệu được duyệt

`clean_dedup.py` đọc raw theo source registry, xác minh hash và chỉ xử lý những số thứ tự bản ghi đã được duyệt rõ ràng. Nhãn trong raw như `manually_curated` hoặc `gold_standard` không tự cho phép huấn luyện.

Một nguồn muốn được sử dụng cần có đủ thông tin sau, được điền dựa trên kiểm duyệt thực tế:

| Trường registry | Điều kiện |
| --- | --- |
| `sha256` | Khớp file raw được kiểm duyệt |
| `training_approved` | Boolean `true` sau khi đủ điều kiện |
| `content_origin_status` | `verified` |
| `language_review_status`, `translation_review_status` | `approved` |
| `usage_permission_status` | `confirmed` |
| `reviewed_by`, `review_evidence` | Người kiểm duyệt và danh sách bằng chứng có nội dung |
| `approved_record_numbers` | Danh sách số thứ tự **bản ghi JSONL không rỗng**, bắt đầu từ 1 |

Việc điền các trường này ghi nhận kết quả kiểm duyệt, không thay thế kiểm duyệt. Không bật hàng loạt chỉ để công cụ chạy được.

Các bản ghi được duyệt phải có đủ hai phía văn bản và tài liệu nguồn. Script chuẩn hóa NFC/khoảng trắng, khử trùng lặp cặp câu theo casefold, giữ tham chiếu về mọi bản ghi/tài liệu đã gộp. Dữ liệu synthetic phải đi theo luồng tăng cường riêng.

```bash
python3 src/data_pipeline/clean_dedup.py \
  --manifest data/manifests/replay-2026-11-01/cleaning.json
```

Đã chạy với registry hiện tại: **527 bản ghi đầu vào, 0 được duyệt, 0 cặp đầu ra**, trạng thái `no_approved_data`. Script ghi manifest nhưng không tạo file hay thư mục `processed/`. Đây là xác nhận điều kiện sử dụng chưa đạt, không phải đã làm sạch thành công một corpus huấn luyện.

## 9. Bước 7 — Chia train/validation/test sau kiểm duyệt

Chưa chạy trên corpus chính thức. Công cụ `split_dataset.py` đã được kiểm thử và tăng cường hoàn chỉnh:

- Kiểm tra checksum và số lượng đầu vào với manifest làm sạch thành công.
- Gom các bản ghi thành nhóm liên thông: liên kết tài liệu nguồn (`source_documents`), trùng chính xác từng phía và **gần trùng (near-duplicate) cả 2 phía ngôn ngữ** (ngưỡng Jaccard từ vựng và 3-gram ký tự >= 0.85). Các câu có độ tương đồng cấu trúc cao bắt buộc phải nằm chung trong cùng một phân vùng.
- Chia nhóm bằng seed 42 và tỷ lệ dự kiến 80/10/10; luôn cần ít nhất ba nhóm độc lập. Tỷ lệ theo số câu có thể lệch vì kích thước nhóm khác nhau.
- **Xác minh không rò rỉ (Zero-Leakage Verification - Q02)**: Trước khi ghi tệp, script tự động quét đối chiếu chéo giữa 3 tập `train_e0`, `val`, `test` để khẳng định 0 ID tài liệu trùng, 0 câu trùng chính xác và 0 câu gần trùng; nếu phát hiện vi phạm lập tức hủy tiến trình.

Ví dụ **chỉ chạy sau khi làm sạch có đầu ra hợp lệ**:

```bash
python3 src/data_pipeline/split_dataset.py \
  --input data/processed/all_sources_cleaned.jsonl \
  --clean-manifest data/manifests/cleaning_run.json \
  --output-dir data/processed/splits \
  --manifest data/manifests/split_run.json \
  --train-ratio 0.8 --val-ratio 0.1 --seed 42
```

`--clean-manifest` phải là manifest của lần làm sạch có dữ liệu thực sự, không dùng lần `no_approved_data` ở bước 6. Chưa có số lượng train/validation/test chính thức để báo cáo.

## 10. Bước 8 — Kiểm kê lại và bảo toàn snapshot

Lệnh đã chạy sau khi tái tạo ứng viên:

```bash
python3 src/data_pipeline/audit_data.py \
  --output-dir data/manifests/replay-2026-11-01/audit \
  --snapshot-id replay-2026-11-01 \
  --expected-inventory data/manifests/inventory.json
```

Script tạo mới `inventory.json`, `source_registry.json`, `validation_report.json` trong thư mục lần chạy. Snapshot ban đầu được giữ nguyên. Khi file raw đổi hash hoặc là file mới, registry tạo lại đặt trạng thái chờ kiểm định và không giữ phê duyệt cũ. Khi nội dung không đổi, bằng chứng và quyết định đã ghi được giữ lại; script không tự cấp phê duyệt.

Đã xác nhận **12/12 file trong snapshot ban đầu còn khớp checksum**. Inventory mới còn có hai file tái tạo ở `interim/replay-2026-11-01/`; đây là bản kiểm tra, không phải mẫu dữ liệu mới. Muốn chạy tiếp, chọn output-dir và snapshot-id mới. Registry sinh ra là bản kiểm tra riêng, không tự thay thế registry đang dùng cho làm sạch.

## 11. Nội dung có thể trình bày với giảng viên

> Nhóm đã tổ chức 527 bản ghi đầu vào, gồm 106 bài thuộc mục Tày–Nùng của VOV4 và 421 bản ghi ứng viên có hai phía văn bản. Nhóm đã tái hiện được quy trình trích xuất từ 106 bài thành 97 ứng viên tài liệu, sau đó thành 174 câu đơn ngữ; kết quả khớp checksum với các file đối chiếu. Nhóm đã bổ sung kiểm kê nguồn, kiểm tra cấu trúc và cách ly 100 bản dịch tổng hợp bị loại. Hiện chưa xác nhận dữ liệu đủ điều kiện huấn luyện, nên chưa công bố corpus song ngữ chuẩn, số lượng train/test hoặc kết quả cải thiện chất lượng dịch. Công việc tiếp theo là xác minh nguồn, kiểm duyệt ngôn ngữ/bản dịch, hoàn thiện dữ liệu rồi mới huấn luyện và đánh giá.

Không dùng tên “Gold Standard”, con số cặp song ngữ chuẩn hoặc kết quả BLEU để thay cho bằng chứng chưa có. Tiến độ chi tiết và các việc còn lại được quản lý tại [TASKS.md](../TASKS.md).
