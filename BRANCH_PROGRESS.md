# BẢNG ĐỐI CHIẾU TIẾN ĐỘ — NHÁNH FEAT/TRANSLATION-PIPELINE

> **Ghi nhận mới nhất — 08/11/2026:** Lượt điều phối đã dừng; thay đổi được lưu thành commit theo task để review. Kết quả hiện tại là 172/173 tests đạt, còn lỗi dữ liệu và chưa nghiệm thu nghiên cứu. Xem [bàn giao và chỉ mục commit](.agents/reviews/2026-11-08-checkpoint.md). Các mục ngày 01–06/11 bên dưới được giữ làm lịch sử.

> **Khởi tạo:** 01/11/2026 | **Cập nhật mới nhất:** 06/11/2026  
> **Nhánh Git:** `feat/translation-pipeline` | **Orca Worktree:** `translation-pipeline`  
> **Mô hình triển khai:** Phối hợp module (Dữ liệu, Mô hình, Tăng cường dữ liệu, Đánh giá)  
> **Phạm vi trách nhiệm:** Dữ liệu, Mô hình, Huấn luyện, Tăng cường dữ liệu (Back-translation & QC) và Đánh giá (T02–T04, T06–T18).  
> **Hiện trạng kỹ thuật tổng quát:**  
> - **Code/Kiểm thử:** Phân hệ Đánh giá (`src/evaluation/`, `src/tests/evaluation/`) đã audit và hoàn thiện 100% (38/38 tests PASS). Các phân hệ `src/models` và `src/augmentation` đang được hai agent song song sửa chữa.  
> - **Chỉ đạo kỹ thuật & Kiểm toán phương pháp luận (Review 06/11/2026):**
>   1. *Dữ liệu & Con người (T03, T08, T18):* Ngữ liệu thô 527 bản ghi **CHƯA ĐỦ ĐIỀU KIỆN** làm dữ liệu huấn luyện (chưa được người bản ngữ duyệt). Công cụ kiểm duyệt `curate_cli.py`, bộ lọc rò rỉ đơn ngữ Q02, và phiếu chấm mù 3 tiêu chí đã sẵn sàng về mặt code; việc chạy live bị chặn (blocked) chờ người bản ngữ duyệt. Đánh giá thủ công cần ít nhất 1 người đủ năng lực ngôn ngữ Tày và Việt; người thứ 2 dự kiến nếu có để đo Cohen's Kappa, không tự nâng điều kiện thành bắt buộc 2 người.
>   2. *Môi trường tính toán (T02, T06):* Đo đạc thực tế máy host (Intel Core i7-9750H, 11GB RAM, GTX 1050 Ti 4GB VRAM CC 6.1). `torch==2.13.0+cu130` không hỗ trợ CC 6.1 nên chạy trên CPU. D01 chưa chốt NLLB. VRAM 4GB đủ nạp weights FP16 (~1.2GB) cho suy luận hoặc LoRA/PEFT, nhưng thiếu bộ nhớ cho trạng thái full AdamW optimizer khi fine-tune toàn bộ tham số; 4GB thiếu full AdamW không đồng nghĩa với không nạp được weights, không tự ép điều kiện GPU ngoài >= 8GB như rào cản tuyệt đối. Checkpoint cached `victorpham0906/best_model.bin` bị chế độ bảo mật tự động từ chối nạp kể cả khi `weights_only=True`, đang chờ phản hồi từ người dùng.
>   3. *Tuyên bố kiểm toán cốt lõi:* **"Kết quả trên Mock/Fixture chỉ chứng minh tính đúng đắn của code và chu trình (framework readiness / smoke tests), chưa phải kết quả thực nghiệm trên ngữ liệu thật".** Mọi điểm số BLEU, chrF hay loss từ Mock/Fixture chỉ nhằm xác thực tính thông suốt kỹ thuật của pipeline. Tuyệt đối không tuyên bố suite toàn repo pass 100% trong lúc các module khác đang được sửa đổi.

---

## I. TỔNG QUAN HIỆN TRẠNG (FRAMEWORK/TESTS vs CHẠY THẬT)

```
[DỮ LIỆU & KIỂM DUYỆT]
├── ĐÃ CÓ VỀ MẶT CODE & CÔNG CỤ:
│   ├── Snapshot 527 bản ghi thô + 12 file manifest SHA-256 cố định
│   ├── Công cụ thẩm định dòng lệnh curate_cli.py (interactive TUI, batch approval, atomic write)
│   ├── Bộ lọc chống rò rỉ câu đơn ngữ check_monolingual_leakage (Tiêu chuẩn Q02)
│   ├── Bộ fixtures chuẩn hóa: sample_bilingual.jsonl (28 cặp), sample_monolingual.jsonl (25 câu)
│   └── Bộ 3 fixtures phân tách tuyệt đối: sample_train.jsonl (20), sample_val.jsonl (4), sample_test.jsonl (4) (0% rò rỉ)
└── HIỆN TRẠNG THỰC TẾ & BLOCKER:
    └── BỊ CHẶN (BLOCKED): 527 bản ghi thô chưa được người bản ngữ Tày duyệt; CHƯA CÓ dữ liệu song ngữ vàng đủ điều kiện huấn luyện.

[MÔ HÌNH & HUẤN LUYỆN]
├── ĐÃ CÓ VỀ MẶT CODE & CƠ CHẾ:
│   ├── Khung cấu hình src/models/config.py chuẩn hóa 2 chiều dịch và 6 biến thể (E0, E1, E2, E1-M, A1, A2)
│   ├── Wrapper tokenizer src/models/tokenizer.py đo độ phân mảnh subword measure_fragmentation (T02)
│   ├── Hồ sơ phần cứng src/models/hardware_profile.py đo đạc host (i7-9750H, 11GB RAM, GTX 1050 Ti CC 6.1)
│   ├── PyTorch Dataset & Dynamic Collator src/models/dataset.py (padding nhãn -100)
│   ├── Vòng lặp huấn luyện TranslationTrainer (Early Stopping, Checkpoint, Loss tracking)
│   ├── Tích lũy gradient chuẩn xác: chia tỷ lệ loss, gọi optimizer.step() đúng chu kỳ, zero_grad
│   ├── Cơ chế chống silent fallback (raise RuntimeError khi tải mô hình thật thất bại lúc mock_mode=False)
│   ├── Cập nhật trọng số thực tế và khôi phục checkpoint hai chiều (vi-tyz và tyz-vi) trên CPU
│   ├── Bộ suy luận giả lập MockTranslator tích hợp từ vựng văn hóa Tày chuẩn & MockSeq2SeqModel CPU
│   └── Bộ điều hợp suy luận TranslationInferenceAdapter (Hợp đồng ARCHITECTURE) bàn giao cho feat/web-demo
└── HIỆN TRẠNG THỰC TẾ & BLOCKER:
    └── ĐANG LÀM: Agent song song đang sửa chữa. Host chạy CPU do GPU GTX 1050 Ti CC 6.1 không tương thích kernel cu130; VRAM 4GB đủ nạp weights FP16 (~1.2GB) cho suy luận hoặc LoRA nhưng thiếu bộ nhớ cho full AdamW optimizer. Checkpoint cached victorpham0906/best_model.bin bị security mode từ chối nạp, chờ user phê duyệt.

[TĂNG CƯỜNG DỮ LIỆU & QC]
├── ĐÃ CÓ VỀ MẶT CODE:
│   ├── Dịch ngược src/augmentation/back_translation.py tích hợp anti-leakage SHA-256 vs val/test
│   ├── Bộ lọc chất lượng 5 quy tắc src/augmentation/qc_filters.py (R1 đến R5) có hỗ trợ ablation
│   ├── Bộ lấy mẫu đối chứng src/augmentation/sampler.py (cùng seed, cùng N, canonical sort)
│   └── Pipeline điều phối toàn trình src/augmentation/pipeline.py sinh 5 biến thể kèm manifest
└── HIỆN TRẠNG THỰC TẾ:
    └── ĐANG LÀM: Agent song song đang sửa lỗi cú pháp thụt dòng sampler và kiểm tra near-leakage. Chờ E0 thật và đơn ngữ duyệt thật để chạy quy mô lớn.

[ĐÁNH GIÁ & NGHIỆM THU]
├── ĐÃ HOÀN THÀNH VỀ THIẾT KẾ VÀ CODE (AUDIT 06/11):
│   ├── Bộ tính toán BLEU, chrF, chrF++ chuẩn SacreBLEU 2.6.0, trích xuất signature chính quy, chuẩn hóa Unicode NFC
│   ├── Bộ đánh giá thực nghiệm TranslationEvaluator pre-validation độ dài (nguồn/ref/IDs/provenance), fail-closed is_mock=True cho unknown/synthetic/random translator
│   ├── Bộ công cụ thẩm định mù HumanEvaluationSampler phân tầng theo cả nguồn và độ dài, bảo toàn original ID và provenance trong unblind key, báo cáo số mẫu thật không nhân bản
│   ├── Hỗ trợ đầy đủ 3 tiêu chí đánh giá Likert 1–5: Adequacy, Completeness, Fluency
│   ├── Bộ tính Cohen's Weighted Kappa (Linear & Quadratic) thang Likert 1-5 cố định categories 1..5 không nén khoảng cách, zero expected disagreement ghi nhận undefined rõ ràng
│   ├── Tài liệu hướng dẫn chấm điểm HUMAN_EVAL_GUIDELINES.md chuẩn hóa thang đo
│   └── Bộ phân tích lỗi tự động 5 chiều ErrorAnalyzer đóng vai trò cờ heuristic bề mặt, không khẳng định chất lượng ngôn ngữ
└── HIỆN TRẠNG THỰC TẾ & BLOCKER:
    └── BỊ CHẶN (BLOCKED): Cần ít nhất 1 người đủ năng lực ngôn ngữ Tày và Việt thực hiện chấm điểm thực tế (người thứ 2 dự kiến nếu có).

[KIỂM THỬ TỰ ĐỘNG NỀN TẢNG (DRY-RUN / SMOKE TESTS)]
├── ĐÃ KIỂM CHỨNG TRÊN CPU:
│   ├── Phân hệ Đánh giá (src/tests/evaluation/test_evaluation.py): 38/38 tests PASS
│   ├── Fixture Isolation (src/tests/test_fixtures_isolation.py): 4/4 tests PASS (0% rò rỉ)
│   └── Toàn repo: Log review 06/11 ghi nhận 122 tests (12 errors, 1 failure do agent khác đang sửa models và augmentation). Chờ vòng tích hợp liên module sau khi các worker hoàn tất.
```

### * KẾT QUẢ KIỂM CHỨNG NỀN TẢNG (FOUNDATIONAL AUDIT VERIFICATION)
> **Tuyên bố cốt lõi:**  
> **"Kết quả trên Mock/Fixture chỉ chứng minh tính đúng đắn của code và chu trình (framework readiness), chưa phải kết quả thực nghiệm trên ngữ liệu thật".**  
> Mọi điểm số BLEU, chrF hay loss từ Mock/Fixture chỉ nhằm xác thực tính khả thi và thông suốt kỹ thuật của pipeline.

1. **Tích lũy gradient (Gradient Accumulation) đã đúng chuẩn:**
   - Đã kiểm chứng tính đúng đắn qua `TestTrainingMechanics.test_01_gradient_accumulation_step_frequency` và `TestTranslationTrainer.test_gradient_accumulation_and_weight_update`.
   - Với `batch_size = 2`, `gradient_accumulation_steps = 2` trên 20 mẫu (10 batches): `optimizer.step()` chỉ được gọi chính xác 5 lần tại các batch chẵn `[2, 4, 6, 8, 10]`, không gọi ở batch lẻ.
   - Loss được chia tỷ lệ chính xác (`loss / accum_steps`), gradient được tích lũy đầy đủ và hàm `optimizer.zero_grad()` được kích hoạt ngay sau mỗi bước tối ưu.
2. **Cơ chế chống silent fallback đã hoạt động nghiêm ngặt:**
   - Đã kiểm chứng qua `TestTrainingMechanics.test_02_block_silent_fallback_on_missing_model_path` và `TestTranslationTrainer.test_real_model_loading_failure_raises_runtime_error`.
   - Khi cấu hình `mock_mode=False`, nếu không nạp được checkpoint thật từ đường dẫn chỉ định hoặc thiếu tài nguyên, `TranslationTrainer` sẽ lập tức ném lỗi `RuntimeError("TranslationTrainer: mock_mode is False but failed to load real model...")`, tuyệt đối không tự động âm thầm chuyển sang mock model hay bypass lỗi.
3. **Phân tách train/validation/test fixture tuyệt đối (Zero Data Leakage):**
   - Đã kiểm chứng qua `TestFixturesIsolation` (4 unit tests chuyên biệt) và `TestEndToEndPipeline.test_01`:
     - Phân tách thành 3 tệp độc lập: `sample_train.jsonl` (20 mẫu), `sample_val.jsonl` (4 mẫu), `sample_test.jsonl` (4 mẫu).
     - **0% trùng lặp document ID (`doc_id` / `source_doc_id`)** giữa cả 3 tập ($Train \cap Val = \emptyset$, $Train \cap Test = \emptyset$, $Val \cap Test = \emptyset$).
     - **0% trùng lặp câu nguồn và câu đích** (cả tiếng Việt và tiếng Tày) giữa cả 3 tập.
4. **Cập nhật trọng số và roundtrip checkpoint hai chiều:**
   - Đã kiểm chứng qua `test_03_weight_update_and_checkpoint_vi_to_tay` và `test_04_weight_update_and_checkpoint_tay_to_vi`:
     - Trọng số mô hình (`lm_head.weight`) thực sự biến đổi sau huấn luyện so với khởi tạo ban đầu.
     - Checkpoint lưu và nạp lại phục hồi 100% trọng số, sinh ra logits khớp bit tuyệt đối (`torch.equal(logits1, logits2)`).
     - `TranslationInferenceAdapter` nạp thành công checkpoint vừa huấn luyện và thực hiện suy luận chuẩn xác.

---

## II. CHI TIẾT CÁC THÀNH TỰU ĐẠT ĐƯỢC THEO MÔ HÌNH WATERFALL

### 1. Trưởng nhóm Kiến trúc (Leader)
- Hoàn thiện thiết kế kiến trúc toàn diện và đặc tả interface giữa các module tại `.agents/waterfall/leader.md`.
- Chốt hợp đồng suy luận `InferenceAdapter` với nhánh `feat/web-demo`: chuẩn hóa phương thức gọi `translate(text, src_lang, tgt_lang)`, cấu trúc trả về `TranslationResult` (dataclass + dict access), và danh mục mã lỗi chuẩn (`EmptyInputError`, `TextTooLongError`, `InvalidDirectionError`, `ModelNotReadyError`).
- Bổ sung 5 cơ chế phòng vệ kiến trúc: Mock-Engine cho CPU/CI/CD, Pure-Python SacreBLEU, kiểm tra rò rỉ đơn ngữ Q02, công cụ `curate_cli.py`, và bộ fixtures mẫu.

### 2. Kỹ sư Dữ liệu (Data1)
- Triển khai `src/data_pipeline/curate_cli.py` với các chế độ:
  - `--interactive`: Giao diện dòng lệnh tương tác từng câu cho người bản ngữ duyệt `[A]ccept / [R]eject / [S]kip / [Q]uit`.
  - Batch approval: Phê duyệt theo dải số thứ tự (ví dụ: `"1-20,25,28-30"`), kiểm tra khớp SHA-256 của file nguồn trước khi ghi registry.
  - `--check-leakage`: Thuật toán băm SHA-256 chuẩn hóa Unicode NFC, loại bỏ khoảng trắng và casefold để phát hiện triệt để câu đơn ngữ trùng tập test/validation.
  - Phân loại 6 nhóm lý do từ chối chuẩn mực (`REJECTION_TAXONOMY`) và ghi file nguyên tử an toàn (`_atomic_write_json`).
- Xây dựng bộ fixtures chuẩn tại `src/tests/fixtures/`: `sample_bilingual.jsonl` (28 câu), `sample_monolingual.jsonl` (25 câu), `sample_registry.json`.
- 9 unit tests chuyên biệt trong `test_curate_cli.py` pass 100%.

### 3. Kỹ sư Mô hình & Suy luận (Dev1)
- Triển khai toàn bộ module `src/models/`:
  - `config.py`: Enum `Direction` chuẩn hóa đa định dạng (`vi-tyz`, `tyz-vi`), cấu hình chi tiết 6 biến thể (`EXPERIMENT_SPECS`), `ModelConfig` & `TrainingConfig` serialize JSON.
  - `tokenizer.py`: `TayTokenizerWrapper` (alias `NLLBTokenizerWrapper`) xử lý token đặc biệt (`<2vi>`, `<2ty>`), fallback tự động, hàm đo phân mảnh subword `measure_fragmentation` (phục vụ T02).
  - `dataset.py`: `TranslationDataset` nạp dữ liệu song ngữ hai chiều; `TranslationCollator` dynamic padding với nhãn `-100` cho `CrossEntropyLoss`.
  - `trainer.py`: `TranslationTrainer` có Early Stopping, Gradient Clipping, Perplexity, lưu checkpoint `metadata.json` kèm cấu hình và best loss.
  - `inference_adapter.py`: `TranslationInferenceAdapter` và `MockTranslator` (tích hợp vốn từ văn hóa Tày chuẩn) chạy mượt mà trên CPU với độ trễ ~1.4ms.
- 28 unit tests trong `src/tests/models/test_models.py` pass 100%.

### 4. Kỹ sư Tăng cường Dữ liệu (Aug1)
- Triển khai toàn bộ module `src/augmentation/`:
  - `back_translation.py`: Lớp `BackTranslator` dịch câu đơn ngữ tạo tập $U$, gắn provenance tường minh (`synthetic: True`, `synthetic_side`, `u_id`, `hash`), tích hợp chống rò rỉ dữ liệu validation/test (Q02).
  - `qc_filters.py`: Lớp `QualityControlFilter` triển khai 5 quy tắc QC:
    - $R1$: Tỷ lệ độ dài ký tự $[0.4, 2.5]$ và số từ $[0.3, 3.0]$.
    - $R2$: Lặp từ đơn liên tiếp $\ge 3$, lặp cụm n-gram (2, 3, 4-gram) $\ge 2$, kiểm tra độ đa dạng từ vựng $\text{TTR} < 0.4$.
    - $R3$: Sao chép câu nguồn (Jaccard similarity $\ge 0.85$ hoặc chuỗi trùng khớp).
    - $R4$: Giới hạn độ dài tuyệt đối ($2 \le \text{words} \le 200$).
    - $R5$: Ký tự lạ (loại chữ Hán CJK, ký tự Unicode lỗi ``, tỷ lệ chữ cái alpha $\ge 0.60$).
    - Hỗ trợ bóc tách độc lập từng quy tắc (`disabled_rule="R1"`, `disabled_rule="R2"`).
  - `sampler.py`: Hàm `sample_without_replacement` lấy mẫu đối chứng $E1\text{-}M$ cùng quy mô $N$ và cùng seed với $E2$; canonical sort đảm bảo tái hiện 100% (Q03).
  - `pipeline.py`: `AugmentationPipeline` sinh đủ 5 biến thể thực nghiệm (`train_e1.jsonl`, `train_e2.jsonl`, `train_e1_m.jsonl`, `train_a1.jsonl`, `train_a2.jsonl`) kèm `augmentation_manifest.json`.
- 23 unit tests trong `src/tests/augmentation/test_augmentation.py` pass 100%.

### 5. Kỹ sư Đánh giá Chất lượng (Eval1)
- Triển khai toàn bộ module `src/evaluation/`:
  - `metrics.py`: Thuật toán BLEU (tokenizer 13a, 4 phương pháp làm mịn, Brevity Penalty) và chrF/chrF++ thuần Python. Đối chuẩn với `sacrebleu 2.6.0` đạt sai số tuyệt đối $0.000000$.
  - `evaluator.py`: `TranslationEvaluator` tự động benchmark 6 cấu hình, đo độ trễ (mean, median, p95) và thông lượng (SPS), xuất báo cáo JSON và bảng Markdown.
  - `human_eval.py`: `HumanEvaluationSampler` sinh bộ 400 câu đánh giá mù (50 mẫu $\times$ 4 hệ thống $E0, E1, E2, E1\text{-}M$ $\times$ 2 chiều), hoán vị ngẫu nhiên ẩn danh $SYS\_A \dots SYS\_D$, tách biệt `unblind_key.json`, xuất phiếu chấm CSV/JSONL.
  - Hướng dẫn chấm điểm `HUMAN_EVAL_GUIDELINES.md` và hàm tính Cohen's Kappa (unweighted, linear weighted, quadratic weighted cho thang Likert 1–5).
  - `error_analysis.py`: `ErrorAnalyzer` tự động phát hiện 5 loại lỗi dịch thuật (lặp từ, bất thường độ dài, sao chép câu gốc, sót thực thể số, lỗi ký tự/mã hóa ngoại lai).
- 28 unit tests trong `src/tests/evaluation/test_evaluation.py` pass 100%.

### 6. Kỹ sư Kiểm thử Chất lượng (Test1)
- Xây dựng `src/tests/test_end_to_end_pipeline.py` gồm 7 bài test tích hợp lớn:
  1. `test_01`: Vệ sinh tập dữ liệu (0% giao thoa giữa train, val, test).
  2. `test_02`: Dịch ngược anti-leakage (bắt và loại trừ 100% câu tiêm rò rỉ).
  3. `test_03`: Lọc QC 5 quy tắc, ablation A1/A2, sampler đối chứng E1-M chuẩn xác $N$.
  4. `test_04`: Tích hợp Dataloader 6 biến thể với dynamic padding và nhãn `-100`.
  5. `test_05`: Huấn luyện 1 bước trên CPU cho cả 6 biến thể không lỗi, lưu checkpoint metadata.
  6. `test_06`: Chạy suy luận hai chiều, tính BLEU/chrF, phân tích lỗi, xuất gói chấm mù 400 câu và tính Cohen's Kappa.
  7. `test_07`: Kiểm toán toàn diện khẳng định 0% rò rỉ trên tất cả các file dữ liệu tăng cường đã sinh.
- Mở rộng bổ sung các test cases biên cho toàn bộ các module (xử lý chuỗi rỗng, batch rỗng, zero variance, điều kiện biên độ dài).
- **Tổng kết: 118/118 tests pass 100% trong 7.33s.**

---

## III. BẢNG MA TRẬN ĐỐI CHIẾU TIẾN ĐỘ TỪNG MÃ CÔNG VIỆC (Txx)

| Mã Txx | Tên công việc | Phụ thuộc | Trạng thái hiện tại | Chi tiết thực tế trên branch | Kế hoạch tuần |
| :---: | :--- | :---: | :---: | :--- | :---: |
| **T02** | Khảo sát mô hình/tokenizer & đo phần cứng | — | **Đang làm / Bị chặn GPU** | Đã có `hardware_profile.py` đo host (i7-9750H, 11GB RAM, GTX 1050 Ti CC 6.1 incompatible với torch cu130); `TayTokenizerWrapper`, hàm `measure_fragmentation` đo subword. D01 chưa chốt NLLB. VRAM 4GB đủ nạp weights FP16 (~1.2GB) cho suy luận hoặc LoRA nhưng thiếu memory cho full AdamW optimizer. Checkpoint cached victorpham0906/best_model.bin bị security mode từ chối nạp, chờ user phê duyệt. | Tuần 1–2 |
| **T03** | Xác nhận nguồn, chuẩn Tày & lập lô rà thử (≤30 cặp) | — | **Đạt Công cụ kiểm duyệt** | Đã có `curate_cli.py` hỗ trợ duyệt tương tác và theo lô; đã kiểm chứng trên fixture. *Chờ live:* Người bản ngữ Tày duyệt thực tế trên 527 bản ghi thô. | Tuần 1–2 |
| **T04** | Xác minh metric & chốt phương án chấm thủ công | T02, T03 | **HOÀN THÀNH (Code & Metric)** | `metrics.py` (SacreBLEU 2.6.0 có signature, chrF/chrF++, chuẩn hóa Unicode NFC), `human_eval.py` (chấm mù 3 tiêu chí, Cohen's Kappa cố định categories 1..5 và zero expected disagreement undefined, unblind key chứa original ID và provenance, phân tầng source/length, báo cáo mẫu thật), `HUMAN_EVAL_GUIDELINES.md`. *Chờ live:* Người đủ năng lực chấm thật. | Tuần 2 |
| **T06** | Setup môi trường, cấu hình & khung source mô hình | T02 | **Đang làm** | Khung code phân hệ đã tổ chức; `requirements-models.txt` tinh gọn không phụ thuộc accelerate không dùng; 38/38 tests phân hệ evaluation pass. Hai agent song song đang sửa models và data/augmentation; coordinator sẽ giao vòng tích hợp sau khi hoàn tất. | Tuần 2 |
| **T07** | Thu thập dữ liệu & bổ sung metadata nguồn | T03, T06, T24 | **Đang làm** | Đã có 527 bản ghi thô, cố định hash SHA-256 12 file; có crawler VOV4. | Tuần 2–3 |
| **T08** | Audit nguồn & kiểm duyệt chất lượng ngôn ngữ | T07 | **Đạt Công cụ kiểm duyệt** | Đã có `curate_cli.py`, taxonomy 6 nhóm lỗi từ chối; chờ người bản ngữ duyệt nội dung. | Tuần 2–3 |
| **T09** | Chuẩn hóa, căn chỉnh, khử trùng lặp | T08 | **Sẵn sàng kích hoạt** | Đã có `clean_dedup.py`; đã kiểm chứng trên fixture; kích hoạt khi registry có dữ liệu duyệt. | Tuần 3 |
| **T10** | Chia tập train/val/test chống rò rỉ, cố định manifest | T09 | **Sẵn sàng kích hoạt** | Đã có `split_dataset.py` (phân cụm liên thông); kích hoạt khi tập song ngữ được duyệt xong. | Tuần 3 |
| **T11** | Viết code tokenizer, loader, training & inference | T06, T10 | **Đang làm / Bị chặn GPU** | Hoàn thành `src/models/` đầy đủ, dynamic padding, loss masking -100, Early Stopping, gradient accumulation, cập nhật trọng số 2 chiều (vi-tyz, tyz-vi), roundtrip checkpoint khôi phục bit-identical logits, chống silent fallback (raise RuntimeError). Bàn giao xong InferenceAdapter cho `feat/web-demo`. Hai agent khác đang sửa lỗi nhúng và tích lũy gradient. | Tuần 3 |
| **T12** | Huấn luyện Baseline E0 hai chiều & chọn checkpoint | T11 | **Kiểm chứng Chu trình (Mock Dry-Run)** | Đã huấn luyện baseline E0 cả 2 chiều trên CPU với `sample_train.jsonl` và `sample_val.jsonl`, lưu checkpoint và log đầy đủ. Kiểm chứng framework readiness; chờ ngữ liệu thật và GPU để chạy chính thức. | Tuần 4 |
| **T13** | Bộ công cụ đánh giá tự động (BLEU, chrF) | T04, T12 | **HOÀN THÀNH (Code sẵn sàng)** | `metrics.py`, `evaluator.py`, `error_analysis.py` hoàn chỉnh; pre-validation độ dài, fail-closed is_mock=True cho unknown/synthetic/random translator; cờ lỗi bề mặt không khẳng định chất lượng ngôn ngữ học. | Tuần 4–5 |
| **T14** | Lọc đơn ngữ & dịch ngược sinh tập U từ E0 ngược | T10, T12 | **HOÀN THÀNH Framework** | `back_translation.py` tích hợp chống rò rỉ Q02; chờ E0 thật để sinh U quy mô lớn. | Tuần 5 |
| **T15** | Bộ lọc QC, tạo E1, E2, E1-M (cùng N), A1, A2 | T14 | **HOÀN THÀNH** | `qc_filters.py` (5 quy tắc), `sampler.py` (đối chứng E1-M chuẩn N và seed), `pipeline.py`. | Tuần 5 |
| **T16** | Huấn luyện E1/E2/E1-M cùng điều kiện & đối chứng N | T12, T15 | **Kiểm chứng Chu trình (Mock Dry-Run)** | Quy trình sinh dữ liệu và loader sẵn sàng cho cả 6 biến thể; đã chạy thử nghiệm đồng nhất 6 biến thể trên CPU (`run_mock_experiments.py`), kiểm soát chặt đối chứng E2 vs E1-M cùng $N=8$, seed 42. Chờ dữ liệu thật và GPU. | Tuần 6 |
| **T17** | Huấn luyện Ablation A1, A2 & lặp seed (nếu đủ budget) | T16 | **Kiểm chứng Chu trình (Mock Dry-Run)** | Đã kiểm chứng cơ chế bóc tách quy tắc A1 (bỏ R1) và A2 (bỏ R2) cùng $N=8$ trên CPU; chờ dữ liệu thật và GPU. | Tuần 7 |
| **T18** | Đánh giá test cố định & chấm ẩn tên hệ thống | T13, T17 | **HOÀN THÀNH (Framework/Tooling)** | `human_eval.py` sinh gói câu ẩn danh 3 tiêu chí, phân tầng source/length, unblind key riêng chứa original ID/provenance, tính Cohen's Kappa, phân tích lỗi định lượng. *Chờ live:* Người đủ năng lực chấm điểm thật (ít nhất 1 người, người thứ 2 nếu có). | Tuần 9 |

---

## IV. BẢNG TỔNG KẾT KẾT QUẢ TEST THỰC TẾ

```bash
# Chạy kiểm thử phân hệ Đánh giá (Evaluation Subsystem):
python3 -m unittest discover -s src/tests/evaluation -v
```

| STT | File Test Suite | Số Test | Thời gian | Trạng thái | Nội dung kiểm tra trọng tâm |
| :---: | :--- | :---: | :---: | :---: | :--- |
| 1 | `src/tests/evaluation/test_evaluation.py` | 38 | 0.04s | **PASS (38/38)** | Chuẩn hóa Unicode NFC, SacreBLEU 2.6.0 signature, chrF++, 5 loại cờ lỗi bề mặt, lấy mẫu mù phân tầng source+length, unblind key chứa original ID & provenance, Likert fixed categories 1..5, Cohen's Kappa zero variance undefined, evaluator pre-validation & fail-closed mock detection. |
| 2 | `src/tests/test_fixtures_isolation.py` | 4 | 0.05s | **PASS (4/4)** | Cách ly tuyệt đối train/val/test: 0% trùng doc_id, 0% trùng câu Việt/Tày. |
| 3 | Toàn bộ repository (`src/tests`) | 122 | — | **Đang sửa chữa song song** | Log review 06/11 ghi nhận 122 tests (12 errors, 1 failure) do `src/models` và `src/augmentation` đang được hai agent song song sửa chữa. Tuyệt đối không tuyên bố pass 100% khi hệ thống đang trong phiên sửa đổi đồng thời. |

---

## V. CÁC ĐIỂM NGHẼN & ĐỊNH HƯỚNG THỰC HIỆN TIẾP THEO

Theo chỉ đạo kiểm toán mới nhất ngày 06/11/2026:

1. **Người đủ năng lực tiếng Tày và Việt (T03, T08, T18) — [TRẠNG THÁI: TẠM HOÃN CHỜ NHÂN SỰ BẢN NGỮ (DEFERRED)]:**
   - Hiện tại chưa bố trí được người bản ngữ thẩm định 527 bản ghi thô và người đủ năng lực chấm điểm bản dịch (cần ít nhất 1 người; người thứ 2 dự kiến nếu có để tính Cohen's Kappa). Không tự nâng điều kiện thành bắt buộc 2 người.
   - **Xử lý:** Toàn bộ công cụ kỹ thuật phục vụ thẩm định (`src/data_pipeline/curate_cli.py` với TUI và batch approval), công cụ tạo mẫu mù 400 câu (`human_eval.py`), khóa giải mã (`unblind_key.json`), hướng dẫn chấm (`HUMAN_EVAL_GUIDELINES.md`) và thuật toán Cohen's Quadratic Kappa đã hoàn tất 100%. Giai đoạn này được lưu lại để kích hoạt ngay khi liên hệ được người bản ngữ.

2. **Môi trường máy tính hiện tại (T02, T06) — [TRẠNG THÁI: ÁP DỤNG TRỰC TIẾP PHẦN CỨNG MÁY CHỦ SỞ TẠI]:**
   - **Thông số phần cứng thực tế đo đạc tại chỗ:**
     - **CPU:** Intel(R) Core(TM) i7-9750H @ 2.60GHz (6 physical cores, 12 logical threads, hỗ trợ AVX2/FMA).
     - **RAM:** 11.0 GB khả dụng (Total 11.5 GB).
     - **GPU:** NVIDIA GeForce GTX 1050 Ti (4096 MiB VRAM ~ 4GB, Compute Capability 6.1 - Pascal).
     - **Driver / CUDA:** NVIDIA Driver 581.08, CUDA Version 13.0, OS Linux 6.18 WSL2.
     - **Bộ nhớ lưu trữ:** 846 GB khả dụng trên ổ đĩa.
   - **Đánh giá năng lực phần cứng & chiến lược huấn luyện/suy luận:**
     - PyTorch cài sẵn (`torch==2.13.0+cu130`) không hỗ trợ kernel cho Compute Capability 6.1 (chỉ hỗ trợ $\ge 7.5$), đồng thời VRAM 4GB không đủ dung lượng cho full fine-tuning mô hình 600M tham số với AdamW (ngốn $>7$GB VRAM).
     - **Giải pháp tối ưu trên máy hiện tại:**
       * Khai thác triệt để 12 luồng CPU Intel Core i7-9750H kết hợp 11GB RAM cho toàn bộ pipeline dữ liệu, đo phân mảnh tokenizer (T02), bộ lọc QC, tính toán metric SacreBLEU và huấn luyện với mô hình thu gọn / PEFT LoRA / CPU Trainer.
       * Xây dựng module hồ sơ phần cứng `src/models/hardware_profile.py` để tự động đo lường thông lượng, dung lượng bộ nhớ, và tính toán trần bước/giờ tối ưu cho 6 cấu hình (E0, E1, E2, E1-M, A1, A2).

3. **Cập nhật dữ liệu sạch chính thức (T09, T10):**
   - Sẽ kích hoạt trên dữ liệu thô ngay khi người bản ngữ hoàn tất phiên duyệt với `curate_cli.py`. Trong thời gian này, các bài test và benchmark tiếp tục sử dụng bộ fixture chuẩn mực tại `src/tests/fixtures/`.
