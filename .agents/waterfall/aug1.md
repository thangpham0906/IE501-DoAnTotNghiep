# BÁO CÁO CÔNG VIỆC KỸ SƯ TĂNG CƯỜNG DỮ LIỆU (AUG1) — MÔ HÌNH WATERFALL
## Nhánh: `feat/translation-pipeline`
**Người thực hiện / Vai trò:** Data Augmentation Engineer (aug1)  
**Ngày lập:** 01/11/2026  
**Nhiệm vụ phụ trách:** T14, T15, T16, T17 (Module `src/augmentation/`, sinh tập $U$, bộ lọc QC 5 quy tắc, lấy mẫu đối chứng $N$ và xây dựng các tập thực nghiệm $E1, E2, E1-M, A1, A2$)  
**Trạng thái hoàn thành:** Đã hoàn thành 100% mục tiêu module `src/augmentation/` và sẵn sàng bàn giao cho Eval1 (Evaluation) và Test1 (QA / End-to-End).

---

## PHẦN I: MỤC TIÊU & PHẠM VI NHIỆM VỤ

1. **Xây dựng module `src/augmentation/` hoàn chỉnh:**
   - `src/augmentation/__init__.py`: Export các lớp và hàm giao diện chuẩn.
   - `src/augmentation/back_translation.py`: Lớp `BackTranslator` tiếp nhận ngữ liệu đơn ngữ ở ngôn ngữ đích, gọi mô hình suy luận E0 theo chiều ngược để sinh bản dịch nguồn tương ứng, tạo thành tập song ngữ tổng hợp thô $U$ (Dataset $U$).
   - `src/augmentation/qc_filters.py`: Lớp `QualityControlFilter` (alias `QCFilter`) thực hiện 5 quy tắc sàng lọc chất lượng nghiêm ngặt (R1 đến R5), có cơ chế tắt chọn lọc từng quy tắc (`disabled_rule`) phục vụ nghiên cứu thực nghiệm bóc tách (ablation studies A1, A2).
   - `src/augmentation/sampler.py`: Lớp `AugmentationSampler` và hàm `sample_without_replacement` thực hiện trích xuất tập mẫu ngẫu nhiên không hoàn lại, cố định seed, sắp xếp định danh chuẩn hóa đảm bảo khả năng tái hiện 100% (tiêu chí Q03).
   - `src/augmentation/pipeline.py`: Lớp `AugmentationPipeline` và hàm tiện ích `run_augmentation_pipeline` tích hợp toàn trình luồng dữ liệu, sinh đầy đủ 5 biến thể thực nghiệm và lưu trữ manifest kiểm định.

2. **Đáp ứng các tiêu chí chất lượng và quy tắc nghiên cứu cốt lõi:**
   - **F05 (Dữ liệu tổng hợp có nguồn gốc và truy vết):** Mọi bản ghi trong $U$ đều lưu `source_monolingual_id`, `generation_model`, `generation_direction`, `synthetic_side` và mã hash SHA-256.
   - **F06 (Bộ dữ liệu thực nghiệm chuẩn mực):** Tạo đúng 5 biến thể thực nghiệm:
     + $E1$: Baseline $E0$ + toàn bộ tập $U$ thô.
     + $E2$: Baseline $E0$ + $N$ mẫu tổng hợp vượt qua đầy đủ 5 quy tắc QC.
     + $E1-M$: Baseline $E0$ + $N$ mẫu ngẫu nhiên từ $U$ (đối chứng công bằng với $E2$ cùng kích thước $N$ và cùng seed).
     + $A1$: Baseline $E0$ + $N$ mẫu lọc khi bỏ quy tắc R1 (tỷ lệ độ dài).
     + $A2$: Baseline $E0$ + $N$ mẫu lọc khi bỏ quy tắc R2 (lặp từ/n-gram).
   - **Q02 (Chống rò rỉ dữ liệu - Zero Data Leakage):** Tích hợp kiểm tra tự động phát hiện và loại trừ triệt để bất kỳ câu đơn ngữ nào trùng với tập validation và test trước khi đưa vào dịch ngược.
   - **Q03 (Tính tái hiện tuyệt đối - Reproducibility):** Cố định seed, chuẩn hóa thứ tự sắp xếp danh sách ID trước khi lấy mẫu, ghi manifest đầy đủ danh sách sample IDs và SHA-256 checksum của từng tệp dữ liệu.
   - **Q05 (Vận hành độc lập nền tảng):** Hỗ trợ chế độ suy luận `mock_mode` thông minh giúp chạy toàn bộ pipeline và unit tests tức thì trên môi trường CPU/CI/CD mà không phụ thuộc vào GPU hay việc tải mô hình NLLB dung lượng lớn.

---

## PHẦN II: CÔNG VIỆC ĐÃ HOÀN THÀNH TRONG KẾ HOẠCH

### 1. `src/augmentation/qc_filters.py`: Bộ lọc chất lượng 5 quy tắc (R1 đến R5)
Triển khai lớp `QualityControlFilter` và cấu hình `QCFilterConfig`:

- **Quy tắc R1 (Length ratio - Tỷ lệ độ dài ký tự và số từ):**
  - Kiểm tra tỷ lệ độ dài ký tự: $\text{ratio} = \frac{\text{len}(tgt)}{\text{len}(src)}$ nằm trong ngưỡng $[\text{min\_length\_ratio}, \text{max\_length\_ratio}]$ (mặc định $[0.4, 2.5]$).
  - Kiểm tra tỷ lệ số từ: $\text{word\_ratio} = \frac{\text{words}(tgt)}{\text{words}(src)}$ nằm trong ngưỡng $[0.3, 3.0]$.
  - Loại bỏ các trường hợp câu dịch bị cụt ngắt bất thường (under-translation) hoặc sinh thừa độ dài mất kiểm soát (hallucinatory explosion).

- **Quy tắc R2 (Word/n-gram repetition - Lỗi thoái hóa lặp từ/cụm từ NMT):**
  - **Lặp từ liên tiếp:** Phát hiện từ đơn lặp liên tiếp $\ge 3$ lần (ví dụ: `phja phja phja`).
  - **Lặp n-gram liên tiếp:** Thuật toán cửa sổ trượt phân tích chuỗi bigram, trigram, 4-gram liên tiếp. Nếu cùng một cụm n-gram lặp lại liên tiếp $\ge 2$ lần (ví dụ: `chang bản chang bản`), câu dịch bị đánh dấu vi phạm.
  - **Độ đa dạng từ vựng (Type-Token Ratio - TTR):** Đối với các câu có từ 6 từ trở lên, tính tỷ lệ số từ duy nhất trên tổng số từ ($\text{TTR} = \frac{|\text{vocabulary}|}{|\text{tokens}|}$). Nếu $\text{TTR} < 0.4$, đánh dấu loại bỏ do suy giảm độ phong phú từ vựng.

- **Quy tắc R3 (Source copy - Sao chép nguyên xi câu nguồn):**
  - Phát hiện trường hợp mô hình không dịch mà chép nguyên văn câu nguồn sang câu đích (`norm_src.casefold() == norm_tgt.casefold()`).
  - Phân tích chỉ số tương đồng từ vựng Jaccard ($\text{Jaccard} = \frac{|V_{src} \cap V_{tgt}|}{|V_{src} \cup V_{tgt}|}$). Nếu độ chồng chéo $\ge 0.85$ trên các câu có từ 4 từ trở lên, câu dịch bị loại bỏ nhằm ngăn ngừa ô nhiễm dữ liệu nguồn vào đích.

- **Quy tắc R4 (Min/max length - Giới hạn độ dài tuyệt đối):**
  - Giới hạn số từ tối thiểu: $\text{min\_words} = 2$.
  - Giới hạn số từ tối đa: $\text{max\_words} = 200$.
  - Giới hạn số ký tự tối thiểu: $\text{min\_chars} = 3$.
  - Giới hạn số ký tự tối đa: $\text{max\_chars} = 1500$.

- **Quy tắc R5 (Target language heuristic - Đặc trưng bảng chữ cái & tính toàn vẹn ngôn ngữ):**
  - **Ký tự lạ/ngoại lai:** Quét biểu thức chính quy loại bỏ văn bản chứa ký tự chữ Hán (CJK ideographs `一-鿿`), Kana/Hiragana, chữ Cyrillic, chữ Ả Rập, chữ Thái, ký tự Hangul.
  - **Lỗi mã hóa/ký tự hỏng:** Phát hiện ký tự thay thế Unicode lỗi (`�`), ký tự null (`\x00`).
  - **Thẻ định dạng lạ:** Phát hiện và loại bỏ thẻ HTML/XML (`<[^>]+>`).
  - **Tỷ lệ chữ cái (Alpha ratio):** Tính tỷ lệ giữa ký tự chữ cái so với tổng ký tự phi khoảng trắng. Nếu tỷ lệ $< 0.60$ (chuỗi chứa quá nhiều dấu câu, số hoặc ký hiệu vô nghĩa), câu bị loại.

- **Khả năng bóc tách linh hoạt (Ablation support):**
  - Phương thức `evaluate_pair(src, tgt, disabled_rule=None, disabled_rules=None)` hỗ trợ bỏ qua bất kỳ quy tắc nào (ví dụ `disabled_rule="R1"` hoặc `disabled_rule="R2"`).
  - Phương thức `filter_records(records, disabled_rule=None)` lọc toàn bộ lô và tổng hợp thống kê chi tiết theo từng mã quy tắc vi phạm (R1..R5).

---

### 2. `src/augmentation/back_translation.py`: Lớp `BackTranslator` sinh tập $U$
- Nhận danh sách câu đơn ngữ đích (hoặc đường dẫn tệp JSONL).
- Xác định chiều suy luận của mô hình ngược:
  + Đối với mục tiêu huấn luyện mô hình thuận ($Vi \to Tay$): dùng ngữ liệu đơn ngữ Tày, mô hình E0 ngược thực hiện dịch $Tay \to Vi$ để tạo câu tiếng Việt tổng hợp. Cặp song ngữ thu được là $(Vi_{synth}, Tay_{real})$.
  + Đối với mục tiêu huấn luyện mô hình ngược ($Tay \to Vi$): dùng ngữ liệu đơn ngữ Việt, mô hình E0 thuận thực hiện dịch $Vi \to Tay$ để tạo câu tiếng Tày tổng hợp. Cặp song ngữ thu được là $(Tay_{synth}, Vi_{real})$.
- Truy vết thông tin bản ghi toàn diện:
  + `u_id`: Định danh duy nhất theo cú pháp `u_{index:06d}_{hash[:8]}`.
  + `synthetic: True` và `source_type: "back_translation"`.
  + `source_monolingual_id`: Khóa tài liệu đơn ngữ gốc.
  + `synthetic_side`: Ghi rõ phía nào là văn bản sinh tổng hợp (`vi` hoặc `ty`).
  + `generation_model` & `generation_direction`: Mô hình và chiều dịch đã sinh.
  + `hash`: SHA-256 fingerprint của cặp câu đã chuẩn hóa NFC.
- Xuất tệp JSONL `u_synthetic.jsonl` và manifest `back_translation_manifest.json`.

---

### 3. `src/augmentation/sampler.py`: Trích xuất mẫu đối chứng & Tái hiện 100%
- **Hàm `sample_without_replacement(records, n_samples, seed=42)`:**
  - Chuẩn hóa thứ tự danh sách bản ghi trước khi bốc thăm bằng khóa sắp xếp canonical (`hash`, `u_id`). Điều này loại trừ hoàn toàn sự khác biệt về thứ tự nạp file giữa các hệ điều hành/hệ thống tập tin khác nhau.
  - Khởi tạo bộ sinh số ngẫu nhiên cô lập `random.Random(seed)`, lấy mẫu không hoàn lại.
  - Lưu danh sách `sampled_ids` vào manifest.
- **Tạo các biến thể thực nghiệm:**
  - `create_e2()`: Áp dụng toàn bộ 5 quy tắc QC $\to$ thu được tập đạt chuẩn $\to$ bốc $N$ mẫu.
  - `create_e1_m()`: Bốc ngẫu nhiên không hoàn lại đúng $N$ mẫu từ tập thô $U$ với **cùng một seed** với $E2$. Đảm bảo so sánh khách quan tác động của bộ lọc QC so với việc bổ sung dữ liệu ngẫu nhiên cùng quy mô.
  - `create_a1()`: Lọc QC khi tắt quy tắc R1 $\to$ bốc $N$ mẫu với cùng seed.
  - `create_a2()`: Lọc QC khi tắt quy tắc R2 $\to$ bốc $N$ mẫu với cùng seed.

---

### 4. `src/augmentation/pipeline.py`: Điều phối toàn trình (Augmentation Pipeline)
- Tích hợp một lần chạy duy nhất: nạp dữ liệu $\to$ sinh dịch ngược (nếu chưa có $U$) $\to$ kiểm tra cách ly chống rò rỉ $\to$ lọc QC $\to$ lấy mẫu đối chứng $\to$ ghép với tập gốc $E0$.
- Tự động sinh ra 5 tập dữ liệu huấn luyện mở rộng:
  + `train_e1.jsonl`: Ghép $E0$ + toàn bộ $U$.
  + `train_e2.jsonl`: Ghép $E0$ + $N$ mẫu $E2$.
  + `train_e1_m.jsonl`: Ghép $E0$ + $N$ mẫu $E1-M$.
  + `train_a1.jsonl`: Ghép $E0$ + $N$ mẫu $A1$.
  + `train_a2.jsonl`: Ghép $E0$ + $N$ mẫu $A2$.
- Xuất manifest tổng hợp `augmentation_manifest.json` ghi nhận số lượng mẫu, SHA-256 của từng file, tỷ lệ chấp thuận của QC và thời gian chạy.

---

## PHẦN III: NHỮNG ĐIỂM SÁNG TẠO VÀ LÀM NGOÀI KẾ HOẠCH

Bên cạnh các yêu cầu cơ bản trong kế hoạch, vai trò aug1 đã chủ động thiết kế và bổ sung các cơ chế phòng vệ chất lượng cao:

1. **Cơ chế phòng vệ rò rỉ dữ liệu triệt để (Zero Data Leakage Guard - Q02):**
   - Trong `BackTranslator.generate_u_dataset()`, đã bổ sung hàm băm bảo vệ `_extract_eval_sentence_hashes()`: trích xuất toàn bộ câu trong tập validation và test, chuẩn hóa NFC, chuyển sang chữ thường (casefold) và tính mã băm SHA-256.
   - Bất kỳ câu đơn ngữ nào có mã băm trùng với câu trong tập validation hoặc test đều bị cách ly ngay lập tức, không đưa vào mô hình dịch ngược, và ghi vết danh sách câu bị chặn vào mục `anti_leakage` trong manifest.

2. **Thuật toán kiểm soát n-gram repetition thông minh (R2):**
   - Thay vì chỉ kiểm tra từ đơn lặp lại, aug1 xây dựng thuật toán phân tích chuỗi n-gram liên tiếp đa kích thước (2-gram, 3-gram, 4-gram) với cửa sổ trượt không trùng lặp (`j = i + n`), kết hợp kiểm tra độ phong phú từ vựng TTR (Type-Token Ratio) để bắt trọn các dạng thoái hóa suy luận phức tạp của mô hình Seq2Seq.

3. **Cơ chế Canonical Ordering trước khi lấy mẫu (Deterministic Guarantee - Q03):**
   - Nếu chỉ dựa vào hàm `random.sample()` trên một danh sách dict chưa sắp xếp, thứ tự dict phụ thuộc vào cách đọc file từ đĩa có thể khiến kết quả lấy mẫu bị lệch giữa các máy phát triển.
   - Hàm `sample_without_replacement()` luôn ép sắp xếp ổn định danh sách bản ghi theo khóa `hash` hoặc `u_id` trước khi áp dụng seed, bảo đảm tái hiện 100% từng ID bản ghi bất kể nền tảng phần cứng.

4. **Đánh dấu tường minh nguồn gốc bản ghi (Provenance Transparency):**
   - Các bản ghi gốc $E0$ khi ghép vào tập mở rộng được gán cờ `synthetic: False`, còn các bản ghi tăng cường được gán cờ `synthetic: True` kèm `source_type: "back_translation"`. Điều này giúp Trainer và Auditor luôn phân biệt rạch ròi thành phần dữ liệu trong mọi đợt huấn luyện.

---

## PHẦN IV: KẾT QUẢ THỬ NGHIỆM VỚI DỮ LIỆU FIXTURE

Module đã được kiểm thử toàn diện thông qua bộ test `src/tests/augmentation/test_augmentation.py` với 16 ca kiểm thử chuyên sâu:

```
src.tests.augmentation.test_augmentation:
  TestAugmentationPipelineEndToEnd
    test_convenience_function_run_augmentation_pipeline ... ok
    test_full_pipeline_run ................................. ok
  TestAugmentationSampler
    test_create_a1_and_a2_ablations ....................... ok
    test_create_e2_and_e1_m ................................ ok
    test_sample_without_replacement_reproducibility ........ ok
  TestBackTranslator
    test_generate_u_dataset_tay_to_vi ...................... ok
    test_generate_u_dataset_vi_to_tay ...................... ok
    test_zero_data_leakage_protection ...................... ok
  TestQualityControlFilter
    test_ablation_disabled_rule_r1 ......................... ok
    test_ablation_disabled_rule_r2 ......................... ok
    test_filter_records_statistics ......................... ok
    test_r1_length_ratio ................................... ok
    test_r2_repetition ..................................... ok
    test_r3_source_copy .................................... ok
    test_r4_length_bounds .................................. ok
    test_r5_target_heuristics .............................. ok
```

### Kết quả tích hợp toàn trình (End-to-End Pipeline) trên fixtures:
- **Đầu vào:**
  + Tập train gốc ($E0$): 28 cặp song ngữ kiểm định từ `src/tests/fixtures/sample_bilingual.jsonl`.
  + Ngữ liệu đơn ngữ: 20 câu từ `src/tests/fixtures/sample_monolingual.jsonl`.
  + Chiều dịch mục tiêu: `vi-tyz` (mô hình dịch ngược $Tay \to Vi$ sinh nguồn tiếng Việt).
- **Tham số thực nghiệm:** $N = 5$, $\text{seed} = 42$.
- **Đầu ra sinh ra:**
  + `train_e1.jsonl`: 48 bản ghi (28 gốc + 20 tổng hợp $U$).
  + `train_e2.jsonl`: 33 bản ghi (28 gốc + 5 mẫu qua đầy đủ QC).
  + `train_e1_m.jsonl`: 33 bản ghi (28 gốc + 5 mẫu ngẫu nhiên từ $U$).
  + `train_a1.jsonl`: 33 bản ghi (28 gốc + 5 mẫu qua QC bỏ R1).
  + `train_a2.jsonl`: 33 bản ghi (28 gốc + 5 mẫu qua QC bỏ R2).
  + `augmentation_manifest.json`: Lưu trữ đầy đủ SHA-256 của từng file, tỷ lệ lọc, và danh sách IDs mẫu.
- **Toàn bộ 67 tests trong repository** (`src/tests/`) chạy thành công 100% trong 4.02 giây.

---

## PHẦN V: BÀN GIAO & KẾ HOẠCH BƯỚC TIẾP THEO

1. **Bàn giao cho Eval1 (Evaluation Engineer):**
   - Cung cấp các tập dữ liệu thực nghiệm chuẩn định dạng JSONL tại các đường dẫn quy ước để tiến hành đánh giá tự động và sinh mẫu chấm thủ công 400 câu ẩn danh (T18).
2. **Bàn giao cho Test1 (QA / End-to-End Engineer):**
   - Mã nguồn module `src/augmentation/` đã sẵn sàng, tương thích hoàn toàn với `src/models/` và `src/data_pipeline/`.
   - Có thể chạy kiểm thử độc lập mà không cần GPU thông qua cờ `mock_mode=True`.
3. **Kế hoạch tiếp theo:**
   - Phối hợp với Dev1 và Leader khi nạp trọng số mô hình NLLB thật để giám sát chi phí thời gian sinh dịch ngược trên tập ngữ liệu đơn ngữ quy mô lớn.
