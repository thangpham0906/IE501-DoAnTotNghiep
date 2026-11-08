# BÁO CÁO CÔNG VIỆC KỸ SƯ DỮ LIỆU (DATA1) — MÔ HÌNH WATERFALL
## Nhánh: `feat/translation-pipeline`
**Người thực hiện / Vai trò:** Data Engineer (data1)  
**Ngày lập:** 01/11/2026  
**Nhiệm vụ phụ trách:** T03, T07, T08 (và chuẩn bị cho T09, T10)  
**Trạng thái hoàn thành:** Đã hoàn thành 100% mục tiêu giai đoạn 1 và sẵn sàng bàn giao cho Dev1 (Models & Suy luận).

---

## PHẦN I: MỤC TIÊU & PHẠM VI NHIỆM VỤ

1. **Giải quyết nút thắt T03 và T08:**
   - Xây dựng công cụ dòng lệnh `src/data_pipeline/curate_cli.py` phục vụ người bản ngữ và chuyên gia ngôn ngữ thẩm định, kiểm duyệt ngữ liệu Tày – Việt.
   - Hỗ trợ xem xét cả dữ liệu thô (`data/raw`) và dữ liệu ứng viên tiền xử lý (`data/interim`).
   - Cung cấp cơ chế gắn trạng thái kiểm định chi tiết: Chấp thuận (`approved`), Từ chối (`rejected`) kèm danh mục lý do phân loại chuẩn, ghi nhận danh tính người duyệt (`reviewed_by`), thời điểm duyệt UTC (`reviewed_at_utc`), bằng chứng kiểm định (`review_evidence`) và mã băm toàn vẹn SHA-256 (`checksum`).
   - Cập nhật siêu dữ liệu trực tiếp vào `data/manifests/source_registry.json` nhằm thỏa mãn 100% điều kiện kiểm định nghiêm ngặt của `src/data_pipeline/clean_dedup.py`.

2. **Xây dựng bộ dữ liệu mẫu (Synthetic Fixtures) chuẩn:**
   - Tạo bộ song ngữ chuẩn tại `src/tests/fixtures/sample_bilingual.jsonl` (28 cặp câu Tày – Việt chuẩn ngữ pháp, đủ trường `vi`, `tay`, `tay_text`, `vi_text`, `ty`, `document_id`, `domain`).
   - Tạo bộ đơn ngữ sạch tại `src/tests/fixtures/sample_monolingual.jsonl` (25 câu đơn ngữ Tày và Việt hoàn toàn độc lập).
   - Tạo manifest `src/tests/fixtures/sample_registry.json` giúp toàn bộ nhóm agent (Dev1, Aug1, Eval1, Test1) có thể chạy kiểm thử tức thì không cần tải corpus thô lớn hoặc vi phạm dữ liệu gốc.

---

## PHẦN II: CÔNG VIỆC ĐÃ THỰC HIỆN TRONG KẾ HOẠCH

### 1. Module `src/data_pipeline/curate_cli.py`
Xây dựng module công cụ hoàn chỉnh với các hàm chức năng cốt lõi:

- **`review_batch(...)`**:
  - Đọc `source_registry.json`, tìm nguồn theo `source_id`.
  - Đối chiếu mã băm SHA-256 của tệp với dữ liệu đăng ký trong registry, phát hiện ngay nếu dữ liệu nguồn bị thay đổi trái phép.
  - Kiểm tra tính hợp lệ của danh sách số thứ tự duyệt `approved_numbers` (1-indexed, không vượt quá tổng số bản ghi).
  - Cập nhật chuẩn hóa các trường bắt buộc của `clean_dedup.py`:
    - `training_approved: True`
    - `content_origin_status: "verified"`
    - `language_review_status: "approved"`
    - `translation_review_status: "approved"`
    - `usage_permission_status: "confirmed"`
    - `reviewed_by`: Tên chuyên gia / người bản ngữ
    - `review_evidence`: Danh sách bằng chứng kiểm duyệt
    - `approved_record_numbers`: Danh sách số thứ tự được phê duyệt
    - `reviewed_at_utc`: Thời gian kiểm duyệt chuẩn UTC
    - `curation_summary`: Thống kê tổng số, số bản ghi duyệt/từ chối, mã băm đối chiếu.
  - Hỗ trợ ghi đè an toàn vào registry hiện tại hoặc xuất ra file registry mới.

- **`curate_candidate_file(...)`**:
  - Dành cho việc thẩm định trực tiếp các tệp ứng viên từ `data/interim` hoặc các tệp JSONL rời rạc.
  - Tách lọc và xuất tệp JSONL đã làm giàu metadata kiểm định, tự động gán `source_doc_id` / `document_id` hợp lệ để sẵn sàng nạp vào `split_dataset.py`.

- **`interactive_curate_cli(...)`**:
  - Giao diện TUI tương tác dòng lệnh trực quan cho người bản ngữ.
  - Duyệt tuần tự từng cặp câu, hiển thị ngữ cảnh tài liệu, tiếng Tày, tiếng Việt.
  - Phím tắt tiện lợi:
    - `[A]` Chấp thuận (Approve).
    - `[R]` Từ chối (Reject) kèm danh mục lý do phân loại.
    - `[S]` Bỏ qua (Skip).
    - `[Q]` Lưu tiến trình và thoát (Quit & Save).
  - Tích hợp kiểm thử giả lập dòng nhập qua luồng `input_stream` / `output_stream`.

- **`inspect_candidate_pairs(...)`**:
  - Cho phép xem trước danh sách cặp câu, tự động phân tích tỷ lệ độ dài từ vựng Tày/Việt (`token_ratio_imbalance`) và cảnh báo câu rỗng hoặc trùng lặp nguồn-đích.

- **`parse_number_ranges(...)`**:
  - Hỗ trợ cú pháp chuỗi linh hoạt cho người dùng (ví dụ: `"1,2,5-8,12"` -> `[1, 2, 5, 6, 7, 8, 12]`), có kiểm tra biên an toàn.

### 2. Bộ dữ liệu mẫu chuẩn (Fixtures) tại `src/tests/fixtures/`

| Tệp fixture | Số lượng mẫu | Đặc điểm cấu trúc | Mục đích sử dụng |
| :--- | :--- | :--- | :--- |
| `sample_bilingual.jsonl` | 28 cặp câu | 6 nhóm tài liệu độc lập (`doc_culture_01`, `doc_culture_02`, `doc_agri_01`, `doc_agri_02`, `doc_daily_01`, `doc_folklore_01`). Đủ các trường `vi`, `tay`, `tay_text`, `vi_text`, `ty`, `document_id`, `domain`. | Phục vụ kiểm thử tiền xử lý, huấn luyện mô hình (Dev1), tính metric BLEU/chrF (Eval1) và E2E (Test1). |
| `sample_monolingual.jsonl` | 25 câu đơn ngữ | Gồm 9 câu Tày và 16 câu Việt đơn ngữ thuộc 8 tài liệu khác nhau. | Phục vụ kiểm thử dịch ngược (Aug1) và kiểm tra rò rỉ dữ liệu (Q02). |
| `sample_registry.json` | 1 nguồn đăng ký | Khai báo chuẩn schema version 1, gắn SHA-256 thực tế của `sample_bilingual.jsonl`. | Phục vụ kiểm thử tự động hóa quy trình quản lý nguồn và làm sạch. |

---

## PHẦN III: NHỮNG GÌ LÀM NGOÀI KẾ HOẠCH (TÍNH NĂNG BỔ SUNG & PHÒNG NGỪA RỦI RO)

Nhằm nâng cao chất lượng kỹ thuật của hệ thống và giải quyết triệt để các rủi ro tiềm ẩn, Data1 đã chủ động bổ sung các cơ chế sau:

1. **Cơ chế kiểm tra rò rỉ đơn ngữ độc lập (`check_monolingual_leakage` — Tiêu chuẩn Q02):**
   - *Rủi ro thực tế:* Tiêu chuẩn Q02 cấm câu đơn ngữ dùng để dịch ngược trùng lặp với tập validation và test. Nếu không kiểm tra, việc rò rỉ câu đơn ngữ vào tập đánh giá sẽ làm sai lệch nghiêm trọng kết quả thực nghiệm.
   - *Giải pháp triển khai:* Tích hợp hàm `check_monolingual_leakage` và cờ lệnh `--check-leakage` trong `curate_cli.py`. Thuật toán chuẩn hóa Unicode NFC, xóa khoảng trắng thừa, chuyển chữ thường (casefold) và kiểm tra giao tập giữa tập đơn ngữ với cả 2 phía nguồn/đích của validation và test. Nếu phát hiện trùng, lập tức cảnh báo và liệt kê chi tiết chỉ mục vi phạm.

2. **Hệ thống phân loại lý do từ chối chuẩn mực (`REJECTION_TAXONOMY`):**
   - Thay vì chỉ ghi nhận lý do từ chối dạng tự do, `curate_cli.py` chuẩn hóa 6 nhóm lỗi ngôn ngữ Tày – Việt:
     - `1. wrong_language`: Không phải tiếng Tày (lẫn tiếng Việt, chữ Hán, ngôn ngữ khác).
     - `2. bad_translation`: Dịch sai lệch nghĩa hoặc dịch máy thô sơ chưa biên tập.
     - `3. incomplete_text`: Câu bị cắt cụt, đứt đoạn, mất ngữ cảnh hoặc thiếu vế.
     - `4. poor_quality`: Lỗi chính tả nặng, ký tự rác, định dạng hỏng.
     - `5. duplicate_or_boilerplate`: Tiêu đề lặp lại, câu rập khuôn không mang giá trị ngữ nghĩa.
     - `6. other`: Ghi chú tự do bổ sung.

3. **Cơ chế ghi file an toàn nguyên tử (`_atomic_write_json`):**
   - *Rủi ro thực tế:* Việc ghi đè trực tiếp `source_registry.json` nếu gặp sự cố dừng chương trình đột ngột có thể làm mất dữ liệu toàn bộ registry.
   - *Giải pháp triển khai:* Triển khai ghi vào file tạm có PID (`.tmp.<pid>`), chỉ khi ghi hoàn tất mới thực hiện hoán đổi nguyên tử (`replace`), bảo vệ an toàn tuyệt đối cho registry.

4. **Bộ công cụ giám sát kiểm toán toàn diện (`--log-path`):**
   - Xuất tệp JSON lưu vết toàn bộ phiên thẩm định: ai là người duyệt, vào thời điểm nào, kiểm tra trên mã băm nào, số lượng chấp thuận/từ chối kèm bản đồ lý do chi tiết cho từng số thứ tự bản ghi.

---

## PHẦN IV: KẾT QUẢ KIỂM TRA THỰC TẾ & BẰNG CHỨNG TÍCH HỢP

### 1. Kiểm thử Unit Test (`src/tests/data_pipeline/test_curate_cli.py`)
Đã triển khai 9 test case chuyên biệt:
- `test_parse_number_ranges`: Kiểm tra phân tích cú pháp dải số hợp lệ và bắt lỗi ngoài phạm vi.
- `test_validate_source_file`: Kiểm tra đọc file, xác minh SHA-256 và bắt lỗi sai lệch checksum.
- `test_review_batch_success`: Kiểm tra cập nhật registry đủ 4 trạng thái kiểm định, lưu lý do từ chối và log kiểm toán.
- `test_review_batch_validation_errors`: Kiểm tra bắt lỗi khi thiếu người duyệt, thiếu bằng chứng hoặc sai ID nguồn.
- `test_curate_candidate_file_directly`: Kiểm tra thẩm định và trích xuất file JSONL ứng viên độc lập.
- `test_inspect_candidate_pairs`: Kiểm tra xem trước dữ liệu và phát hiện bất thường độ dài.
- `test_check_monolingual_leakage`: Kiểm tra phát hiện chính xác rò rỉ đơn ngữ và xác nhận an toàn tuyệt đối khi không rò rỉ.
- `test_interactive_curate_cli_simulation`: Giả lập phiên tương tác người bản ngữ với luồng I/O.
- `test_end_to_end_integration_with_clean_dedup_and_split`: Kiểm thử tích hợp toàn diện từ Fixture -> `curate_cli` -> `clean_dedup` -> `split_dataset`.

**Kết quả chạy thực tế:**
```bash
python3 -m unittest src/tests/data_pipeline/test_curate_cli.py
.........
----------------------------------------------------------------------
Ran 9 tests in 0.062s
OK
```

Toàn bộ test suite của dự án (32 tests):
```bash
python3 -m unittest discover -s src/tests
................................
----------------------------------------------------------------------
Ran 32 tests in 0.271s
OK
```

### 2. Bằng chứng tích hợp thông suốt với `clean_dedup.py` và `split_dataset.py`
Trong bài test `test_end_to_end_integration_with_clean_dedup_and_split`:
1. Khi registry chưa duyệt: `clean_dedup.py` báo cáo đúng `status: no_approved_data` (bảo vệ không cho dữ liệu chưa kiểm duyệt lọt vào).
2. Sau khi chạy `review_batch` phê duyệt 28 bản ghi từ fixture:
   - `clean_dedup.py` chuyển trạng thái sang `status: completed`, xử lý thành công 28 bản ghi sạch với đầy đủ provenance và document IDs.
   - `split_dataset.py` thực hiện phân cụm liên thông (`connected_groups`), chia thành công 3 tập độc lập:
     - `train_e0.jsonl`: 20 cặp câu
     - `val.jsonl`: 4 cặp câu
     - `test.jsonl`: 4 cặp câu
3. Kiểm tra rò rỉ đơn ngữ giữa `sample_monolingual.jsonl` với `val.jsonl` và `test.jsonl`:
   - `has_leakage: False`, `leakage_count: 0`. Tiêu chuẩn Q02 đạt tuyệt đối.

---

## PHẦN V: HƯỚNG DẪN SỬ DỤNG `curate_cli.py`

### 1. Xem trước và đánh giá nhanh tệp ứng viên
```bash
python3 src/data_pipeline/curate_cli.py \
  --inspect \
  --input data/interim/vov4_sentence_candidates.jsonl \
  --limit 10 \
  --offset 0
```

### 2. Chạy chế độ thẩm định tương tác từng câu (Người bản ngữ)
```bash
python3 src/data_pipeline/curate_cli.py \
  --interactive \
  --registry data/manifests/source_registry.json \
  --source-id vov4 \
  --reviewer "Nông Văn BảnNgữ" \
  --evidence "Đối chiếu thực địa và từ điển Tày-Việt" \
  --log-path data/manifests/curation_vov4_audit.json
```

### 3. Phê duyệt theo lô số thứ tự (Batch Approval)
```bash
python3 src/data_pipeline/curate_cli.py \
  --registry data/manifests/source_registry.json \
  --source-id vov4 \
  --reviewer "Hội đồng Thẩm định Ngữ liệu Tày" \
  --evidence "Biên bản nghiệm thu đợt 1" \
  --approve-numbers "1-20,25,28-30" \
  --reject-numbers "21-24,26,27" \
  --rejection-reason "bad_translation" \
  --log-path data/manifests/curation_vov4_log.json
```

### 4. Kiểm tra rò rỉ câu đơn ngữ trước khi chạy Back-Translation (Q02)
```bash
python3 src/data_pipeline/curate_cli.py \
  --check-leakage \
  --input data/processed/monolingual_candidates.jsonl \
  --val-file data/processed/splits/val.jsonl \
  --test-file data/processed/splits/test.jsonl
```

---

## PHẦN VI: BÀN GIAO CHO GIAI ĐOẠN TIẾP THEO (DEV1)

Dữ liệu và công cụ đã sẵn sàng 100%:
1. Nút thắt kiểm duyệt dữ liệu đã được tháo gỡ hoàn toàn.
2. Fixture `src/tests/fixtures/sample_bilingual.jsonl` và `src/tests/fixtures/sample_monolingual.jsonl` đã sẵn sàng để Dev1 sử dụng trực tiếp trong `src/models/` (Dataset, Tokenizer, Trainer, InferenceAdapter) mà không cần phụ thuộc vào việc tải checkpoint hoặc dữ liệu ngoài.
3. Chuyển tiếp tiến trình sang Agent tiếp theo: **Dev1 (Kỹ sư Mô hình & Suy luận)**.
