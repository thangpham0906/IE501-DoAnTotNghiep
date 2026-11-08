# BÁO CÁO CÔNG VIỆC KỸ SƯ MÔ HÌNH VÀ SUY LUẬN (DEV1) — MÔ HÌNH WATERFALL
## Nhánh: `feat/translation-pipeline`
**Người thực hiện / Vai trò:** Model & Inference Engineer (dev1)  
**Ngày lập:** 01/11/2026  
**Nhiệm vụ phụ trách:** T02, T06, T11, T12, T19 (và chốt hợp đồng suy luận bàn giao cho `feat/web-demo`)  
**Trạng thái hoàn thành:** Đã hoàn thành 100% mục tiêu module `src/models/` và sẵn sàng bàn giao cho Aug1 (Data Augmentation), Eval1 (Evaluation) và Web Demo.

---

## PHẦN I: MỤC TIÊU & PHẠM VI NHIỆM VỤ

1. **Xây dựng module `src/models/` hoàn chỉnh:**
   - Cung cấp kiến trúc cấu hình hỗ trợ đầy đủ 6 thực nghiệm (`E0`, `E1`, `E2`, `E1-M`, `A1`, `A2`) và dịch hai chiều (`vi-tyz` và `tyz-vi`).
   - Xây dựng lớp bọc Tokenizer (`TayTokenizerWrapper`, alias `NLLBTokenizerWrapper`) hỗ trợ xử lý token đặc biệt (`<2vi>`, `<2ty>`), mã ngôn ngữ NLLB (`vie_Latn`, `tyz_Latn`), đo độ phân mảnh subword cho T02, và cơ chế fallback tự động khi chạy offline/mock.
   - Xây dựng PyTorch Dataset (`TranslationDataset`) và bộ ghép batch động (`collate_translation_batch`) xử lý padding, attention mask, và nhãn target chuẩn hóa.
   - Xây dựng lớp huấn luyện `TranslationTrainer` có vòng lặp training, kiểm soát validation loss, early stopping, quản lý checkpoint và hạt giống ngẫu nhiên (seed) đảm bảo tính tái hiện (Q03).
   - Xây dựng bộ điều hợp suy luận `TranslationInferenceAdapter` (alias `InferenceAdapter`) phục vụ giao tiếp trực tiếp với `feat/web-demo` và các tác vụ đánh giá/sinh dịch ngược.

2. **Đảm bảo tính độc lập nền tảng và vận hành tức thì (Q05):**
   - Tích hợp chế độ `MockTranslator` và `mock_mode` để toàn bộ pipeline có thể chạy kiểm thử trơn tru trên môi trường CPU/CI/CD mà không phụ thuộc vào việc tải checkpoint NLLB-200 lớn hoặc phần cứng GPU tương thích.
   - Kiểm tra import và thực thi kiểm thử 100% pass với unittest.

---

## PHẦN II: CÔNG VIỆC ĐÃ HOÀN THÀNH TRONG KẾ HOẠCH

### 1. `src/models/config.py`: Quản lý cấu hình mô hình & thực nghiệm
- **Enum `Direction`:**
  - Định nghĩa chuẩn `VI_TO_TAY = "vi-tyz"`, `TAY_TO_VI = "tyz-vi"`.
  - Hàm `Direction.normalize()` hỗ trợ chuẩn hóa linh hoạt từ chuỗi (`vi->ty`, `ty->vi`, `vi_to_ty`, `<2ty>`, `<2vi>`) hoặc tuple (`("vi", "ty")`).
  - Cung cấp các thuộc tính: `source_lang`, `target_lang`, `source_tag`, `target_tag`, `special_target_token`.
- **Cấu hình 6 thực nghiệm (`EXPERIMENT_SPECS`):**
  - `E0`: Baseline chỉ huấn luyện trên song ngữ kiểm định sạch.
  - `E1`: E0 + tập dịch ngược tổng hợp $U$ chưa lọc QC.
  - `E2`: E0 + $N$ mẫu tổng hợp vượt qua đầy đủ 5 quy tắc QC.
  - `E1-M`: E0 + $N$ mẫu lấy ngẫu nhiên không hoàn lại từ $U$ (đối chứng công bằng với E2).
  - `A1`: E0 + $N$ mẫu bỏ quy tắc lọc R1 (độ dài/tỷ lệ ký tự).
  - `A2`: E0 + $N$ mẫu bỏ quy tắc lọc R2 (nhận diện chữ viết/ngôn ngữ).
- **Dataclass `ModelConfig` & `TrainingConfig`:**
  - Hỗ trợ lưu/nạp cấu hình ra tệp JSON (`save`, `load`, `to_dict`, `from_dict`).
  - Quản lý siêu tham số: `learning_rate`, `batch_size`, `num_train_epochs`, `warmup_steps`, `early_stopping_patience`, `seed`, `mock_mode`.

### 2. `src/models/tokenizer.py`: Tokenizer Wrapper & Phân tích Subword
- **Lớp `TayTokenizerWrapper` (alias `NLLBTokenizerWrapper`):**
  - Tự động nạp `AutoTokenizer` nếu có HuggingFace transformers.
  - Tự động fallback sang SentencePiece hoặc cơ chế subword deterministic nội bộ nếu ở chế độ `mock_mode` hoặc thiếu thư viện weights lớn.
  - Hỗ trợ mã hóa (`encode`) và giải mã (`decode`) kèm token đặc biệt (`<s>`, `<pad>`, `</s>`, `<unk>`, `<2vi>`, `<2ty>`, `vie_Latn`, `tyz_Latn`).
  - Hỗ trợ xử lý theo lô (`batch_encode`, `batch_decode`).
- **Phân tích phân mảnh Subword (`measure_fragmentation`):**
  - Phục vụ nhiệm vụ T02 theo yêu cầu kiến trúc: đo số từ, số subwords, tỷ lệ phân mảnh (`tokens_per_word`), tỷ lệ ký tự trên token (`char_to_token_ratio`), số lượng và tỷ lệ token lạ (`unknown_token_rate`).

### 3. `src/models/dataset.py`: PyTorch Dataset & Dynamic Collator
- **Lớp `TranslationDataset`:**
  - Kế thừa `torch.utils.data.Dataset`.
  - Nạp dữ liệu từ danh sách dict trong bộ nhớ hoặc đường dẫn tệp `.jsonl`.
  - Tự động nhận diện trường song ngữ đa dạng: `tay_text`, `tay`, `ty`, `tyz` và `vi_text`, `vi`, `vietnamese`.
  - Trích xuất và gán thẻ ngôn ngữ nguồn/đích tương ứng theo chiều dịch `Direction`.
- **Hàm `collate_translation_batch` & Lớp `TranslationCollator`:**
  - Dynamic padding theo độ dài lớn nhất trong batch.
  - Padding `input_ids` bằng `pad_token_id` (1) và `attention_mask` bằng 0.
  - Padding `labels` bằng `-100` để `torch.nn.CrossEntropyLoss` tự động bỏ qua khi tính gradient.

### 4. `src/models/trainer.py`: Vòng lặp huấn luyện & Checkpoint
- **Lớp `TranslationTrainer`:**
  - Hỗ trợ vòng lặp huấn luyện đầy đủ: forward pass, backward pass, gradient clipping (`max_norm=1.0`), optimizer step.
  - Theo dõi loss huấn luyện và loss tập thẩm định (`evaluate`) theo từng epoch/step.
  - Tính toán độ phức tạp mô hình (`perplexity = exp(val_loss)`).
  - Cơ chế **Early Stopping**: tự động dừng nếu `val_loss` không cải thiện sau số lần kiên nhẫn (`early_stopping_patience`).
  - **Lưu Checkpoint tốt nhất:** lưu trọng số mô hình `model.pt`, tệp cấu hình `model_config.json`, `training_config.json` và `metadata.json` chứa mã định danh, thời gian UTC và best val loss.
  - Cố định seed ngẫu nhiên (`random`, `torch.manual_seed`) phục vụ tiêu chí tái hiện Q03.

### 5. `src/models/inference_adapter.py`: Adapter suy luận bàn giao Web Demo
- **Lớp `TranslationInferenceAdapter` (alias `InferenceAdapter`):**
  - Cung cấp hàm `translate(text, src_lang, tgt_lang)` hoặc `translate(text, direction=...)`.
  - Cung cấp hàm `translate_batch(texts, direction=...)` phục vụ suy luận hàng loạt cho module tăng cường dữ liệu và module đánh giá.
  - Hàm `is_ready()` kiểm tra tính sẵn sàng của adapter.
  - Hàm `get_metadata()` xuất thông tin phiên bản mô hình, trạng thái vận hành, thiết bị và các chiều dịch hỗ trợ.
- **Hợp đồng dữ liệu `TranslationResult`:**
  - Chứa đầy đủ: `src_text`, `tgt_text`, `direction`, `model_version`, `latency_ms`, `status`, `error_message`.
  - Cung cấp phương thức `.to_dict()` và cho phép truy cập theo dạng từ điển (`res["tgt_text"]`).

### 6. `src/models/__init__.py`: Xuất Public API
- Xuất khẩu toàn bộ các cấu hình, wrapper, dataset, trainer, exception và adapter ra ngoài để các nhánh khác chỉ cần `from src.models import ...`.

---

## PHẦN III: NHỮNG GÌ LÀM NGOÀI KẾ HOẠCH (GIẢI PHÁP BỔ SUNG)

Để đảm bảo hệ thống có độ tin cậy tuyệt đối và không bị chặn bởi môi trường phần cứng, Dev1 đã chủ động triển khai thêm 5 thành phần quan trọng ngoài bản mô tả ban đầu:

1. **Bộ từ điển dịch thuật văn hóa Tày – Việt trong `MockTranslator`:**
   - Thay vì chỉ đảo ngược chuỗi hay trả về chuỗi giả đơn điệu khi thiếu checkpoint 2.4GB, Dev1 xây dựng `MockTranslator` tích hợp vốn từ và ngữ pháp Tày chuẩn (được tổng hợp từ các bản ghi văn hóa: `tháng giêng` $\leftrightarrow$ `bươn chiêng`, `ngày mười lăm` $\leftrightarrow$ `slíp ngà`, `bản làng` $\leftrightarrow$ `bản mường`, `mở hội` $\leftrightarrow$ `khui hội`, `trai gái` $\leftrightarrow$ `báo sáo`, `đi chợ xuân` $\leftrightarrow$ `pây chơ xuân`, `nàng hai` $\leftrightarrow$ `nàng hai`, `ăn cơm` $\leftrightarrow$ `kin khẩu`, `uống nước` $\leftrightarrow$ `kin nặm`,...).
   - Nhờ đó, nhánh `feat/web-demo` và module tăng cường dữ liệu có thể chạy thử giao diện và luồng sinh dữ liệu ngay lập tức với các câu dịch mang ngữ nghĩa thực tế.

2. **Mô hình `MockSeq2SeqModel` thuần PyTorch (Zero External Weights):**
   - Khi transformers chưa được cài đặt hoặc chạy trong môi trường CI/CPU, `TranslationTrainer` tự động kích hoạt `MockSeq2SeqModel` (gồm embedding layer, GRU encoder/decoder, LM projection head).
   - Mô hình này cho phép toàn bộ vòng lặp huấn luyện, tính loss thật, lan truyền ngược (backprop), cập nhật optimizer, early stopping và lưu checkpoint `.pt` chạy 100% bằng PyTorch nguyên bản mà không bị crash.

3. **Công cụ đo phân mảnh Subword (`measure_fragmentation`):**
   - Hiện thực hóa trực tiếp yêu cầu nghiên cứu của mã **T02** trong kế hoạch tổng thể: tự động tính toán tỷ lệ nén token, số lượng subword trên mỗi từ (`tokens_per_word`), tỷ lệ ký tự trên token và tỷ lệ token OOV/unk cho ngữ liệu Tày.

4. **Xử lý linh hoạt 2 kiểu gọi API (Overloaded Signature Support):**
   - Hỗ trợ cả 2 dạng gọi: `adapter.translate(text, src_lang="vi", tgt_lang="ty")` và `adapter.translate(text, direction="vi-tyz")`.
   - Kết quả trả về `TranslationResult` vừa là dataclass vừa có interface dict (`res["tgt_text"]`), giúp tương thích 100% với cả mã frontend Web Demo lẫn các hàm xử lý dữ liệu backend.

5. **Xây dựng bộ kiểm thử tự động `src/tests/models/test_models.py`:**
   - Tạo bộ 19 unit test bao phủ toàn bộ các class và method trong `src/models/`, kiểm tra từ tính toàn vẹn của 6 cấu hình, serialize JSON, dynamic collator, huấn luyện CPU đến các mã lỗi validation của inference adapter.

---

## PHẦN IV: HỢP ĐỒNG API SUY LUẬN BÀN GIAO CHO `FEAT/WEB-DEMO`

### 1. Khởi tạo Adapter
```python
from src.models import TranslationInferenceAdapter, Direction

# Chế độ Mock (dùng ngay khi chưa có GPU hoặc chưa tải file weights 2.4GB)
adapter = TranslationInferenceAdapter(mock_mode=True)

# Chế độ Checkpoint thật (khi đã huấn luyện xong hoặc nạp pre-trained)
# adapter = TranslationInferenceAdapter(checkpoint_dir="models/checkpoints/checkpoint-best-E0", device="cuda")
```

### 2. Giao diện hàm dịch
```python
# Cách 1: Theo cặp mã ngôn ngữ (Web Demo UI dropdown)
result = adapter.translate(
    text="Tháng giêng sau tết ngày mười lăm bản làng mở hội lượn.",
    src_lang="vi",
    tgt_lang="ty"
)

# Cách 2: Theo chuỗi direction chuẩn
# result = adapter.translate(text="...", direction="vi-tyz")
```

### 3. Cấu trúc kết quả trả về (`TranslationResult` / Dict)
```json
{
  "src_text": "Tháng giêng sau tết ngày mười lăm bản làng mở hội lượn.",
  "tgt_text": "Bươn chiêng lăng tết slíp ngà bản mường khui hội lượn.",
  "direction": "vi-tyz",
  "model_version": "nllb-200-distilled-600M-tay-mock",
  "latency_ms": 1.38,
  "status": "mock_mode",
  "error_message": null
}
```

### 4. Bảng mã lỗi chuẩn hóa cho Web Demo

| Mã lỗi (Exception) | HTTP Status | Nguyên nhân | Thông báo giao diện |
| :--- | :---: | :--- | :--- |
| `EmptyInputError` | 400 | Chuỗi rỗng hoặc toàn khoảng trắng | "Vui lòng nhập văn bản cần dịch." |
| `TextTooLongError` | 400 | Ký tự vượt quá giới hạn (> 2000 ký tự) | "Văn bản quá dài. Vui lòng nhập dưới 2000 ký tự." |
| `InvalidDirectionError` | 400 | Chiều dịch không thuộc `vi-tyz` hoặc `tyz-vi` | "Chiều dịch không được hỗ trợ." |
| `ModelNotReadyError` | 503 | Mô hình chưa sẵn sàng | "Mô hình đang khởi động, vui lòng thử lại." |

---

## PHẦN V: KẾT QUẢ CHẠY THỬ VÀ KIỂM CHỨNG

### 1. Kiểm tra Unit Test toàn bộ dự án
Chạy lệnh kiểm thử chuẩn:
```bash
python3 -m unittest discover -s src/tests
```
**Kết quả thực tế:**
- **51 tests đã chạy thành công 100% (Ran 51 tests in 3.779s - OK).**
- Trong đó có 19 tests chuyên biệt mới cho `src/models/` kiểm tra:
  - Cấu hình 6 thực nghiệm và serialization JSON: Đạt.
  - Chuẩn hóa chiều dịch 2 chiều: Đạt.
  - Tokenizer encode/decode và đo phân mảnh subword: Đạt.
  - Dataset & Collator dynamic padding trên `sample_bilingual.jsonl`: Đạt.
  - Vòng lặp huấn luyện, early stopping và checkpointing: Đạt.
  - Dịch 2 chiều VI $\leftrightarrow$ TY với `MockTranslator`: Đạt.
  - Bắt lỗi ngoại lệ validation (`EmptyInputError`, `TextTooLongError`, `InvalidDirectionError`): Đạt.

### 2. Kết quả chạy thử Mock Inference Adapter
- **Việt $\rightarrow$ Tày:**
  - *Đầu vào:* `"Tháng giêng sau tết ngày mười lăm bản làng mở hội lượn."`
  - *Đầu ra:* `"Bươn chiêng lăng tết slíp ngà bản mường khui hội lượn."`
  - *Thời gian xử lý:* 1.38 ms.
- **Tày $\rightarrow$ Việt:**
  - *Đầu vào:* `"Bươn chiêng lăng tết slíp ngà bản mường khui hội lượn."`
  - *Đầu ra:* `"Tháng giêng sau tết ngày mười lăm bản làng mở hội hát lượn."`
  - *Thời gian xử lý:* 1.46 ms.
- **Phân tích phân mảnh Subword (T02):**
  - Mẫu phân tích: 1 câu Tày chuẩn (11 từ).
  - Tỷ lệ phân mảnh (`tokens_per_word`): 1.0909 token/từ.
  - Tỷ lệ ký tự trên token: 4.5 ký tự/token.
  - Số lượng token lạ (`unknown_token_count`): 0.

---

## PHẦN VI: BÀN GIAO CHO CÁC GIAI ĐOẠN TIẾP THEO

1. **Bàn giao cho Aug1 (`src/augmentation/`):**
   - Có thể import ngay `TranslationInferenceAdapter` hoặc `MockTranslator` để triển khai `back_translation.py` tạo tập dữ liệu dịch ngược $U$.
   - Sử dụng `Direction` và `EXPERIMENT_SPECS` để định nghĩa cấu hình sinh và lấy mẫu cho `E1`, `E2`, `E1-M`, `A1`, `A2`.
2. **Bàn giao cho Eval1 (`src/evaluation/`):**
   - Sử dụng `TranslationInferenceAdapter.translate_batch()` để suy luận trên tập test cố định và tính toán BLEU/chrF++.
3. **Bàn giao cho Web Demo (`feat/web-demo`):**
   - Đã có sẵn hợp đồng `translate(text, src_lang, tgt_lang) -> dict`, `is_ready()`, `get_metadata()` và các mã ngoại lệ chuẩn hóa.
