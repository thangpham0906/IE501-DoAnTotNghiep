# BÁO CÁO THIẾT KẾ KIẾN TRÚC VÀ ĐẶC TẢ GIAO DIỆN HỆ THỐNG
## Nhánh: `feat/translation-pipeline` — Mô hình Waterfall
**Người thực hiện / Vai trò:** Leader (Kiến trúc sư trưởng hệ thống)  
**Ngày lập:** 01/11/2026  
**Mục tiêu:** Thiết lập khung kiến trúc toàn diện, chuẩn hóa interface giữa các module, chốt hợp đồng suy luận (Inference Adapter) với nhánh `feat/web-demo`, và phân công chi tiết cho 5 agent kỹ thuật (data1, dev1, aug1, eval1, test1) nhằm hoàn thành dứt điểm các nhiệm vụ T02–T18 theo đúng tiến độ và tiêu chuẩn chất lượng.

---

## PHẦN I: MỤC TIÊU KIẾN TRÚC & PHÂN CHIA VAI TRÒ WATERFALL

### 1. Mục tiêu kiến trúc cốt lõi
1. **Tính tái hiện tuyệt đối (Reproducibility - Q03):** Mọi bước từ tiền xử lý, chia tập, sinh dịch ngược, lọc QC, lấy mẫu đối chứng (E1-M, A1, A2) đến đánh giá đều phải cố định seed, lưu hash SHA-256 và ghi vết danh sách ID mẫu.
2. **Không rò rỉ dữ liệu (Zero Data Leakage - Q02):** Tập validation và test phải cố định và cách ly hoàn toàn; câu đơn ngữ dùng để dịch ngược tăng cường phải được kiểm tra loại trừ triệt để với tập test và validation.
3. **Độc lập nền tảng & Chạy được ngay (Platform Independence - Q05):** Hỗ trợ cơ chế mô phỏng (Mock Mode) thông minh và fallback thuật toán thuần Python để toàn bộ pipeline và unit tests có thể chạy kiểm thử trơn tru trên môi trường CPU/CI/CD trước khi nạp trọng số mô hình lớn trên GPU.
4. **Hợp đồng suy luận nhất quán (Consistent Contract):** Cung cấp class `InferenceAdapter` chuẩn hoá cho nhánh `feat/web-demo`, có cơ chế kiểm tra tính sẵn sàng, mã lỗi cụ thể và metadata truy vết phiên bản mô hình.

### 2. Phân công vai trò theo mô hình Waterfall
Mô hình Waterfall trong nhánh được chia làm 5 giai đoạn kế tiếp nhau, do 5 agent chuyên trách phụ trách:

```
[Leader: Kiến trúc & Hợp đồng]
           │
           ▼
[Data1: Dữ liệu & Duyệt chuẩn] ➔ Cung cấp clean data & Curate CLI
           │
           ▼
[Dev1: Models & Suy luận]      ➔ Cung cấp Trainer & InferenceAdapter
           │
           ▼
[Aug1: Dịch ngược & Bộ lọc QC] ➔ Cung cấp E1, E2, E1-M, A1, A2
           │
           ▼
[Eval1: Metrics & Đánh giá]    ➔ Cung cấp BLEU/chrF & 400 câu ẩn tên
           │
           ▼
[Test1: QA & Tích hợp E2E]     ➔ Chạy toàn bộ test suite & Nghiệm thu
```

| Agent | File báo cáo | Phạm vi trách nhiệm chính | Nhiệm vụ liên quan |
| :--- | :--- | :--- | :--- |
| **Leader** | `.agents/waterfall/leader.md` | Thiết kế kiến trúc tổng thể, đặc tả giao diện, hợp đồng suy luận với Web Demo, giám sát tích hợp và đề xuất giải pháp dự phòng. | T01, T06, Kiến trúc |
| **Data1** | `.agents/waterfall/data1.md` | Bổ sung `curate_cli.py` phục vụ người bản ngữ duyệt dữ liệu; sinh fixture kiểm thử; thẩm định nguồn; kiểm tra rò rỉ đơn ngữ vs test/val. | T03, T07, T08, T09, T10 |
| **Dev1** | `.agents/waterfall/dev1.md` | Triển khai `src/models/`: cấu hình (`config.py`), tokenizer NLLB wrapper (`tokenizer.py`), dataset loader (`dataset.py`), trainer (`trainer.py`), và `inference_adapter.py`. | T02, T06, T11, T12, T19 |
| **Aug1** | `.agents/waterfall/aug1.md` | Triển khai `src/augmentation/`: sinh tập U bằng dịch ngược (`back_translation.py`), bộ lọc QC 5 quy tắc (`qc_filters.py`), lấy mẫu cố định $N$ và seed (`sampler.py`), tạo E1, E2, E1-M, A1, A2 (`pipeline.py`). | T14, T15, T16, T17 |
| **Eval1** | `.agents/waterfall/eval1.md` | Triển khai `src/evaluation/`: tính BLEU/chrF++ (`metrics.py`), evaluator tự động (`evaluator.py`), bộ sinh mẫu chấm thủ công 400 câu ẩn tên hệ thống (`human_eval.py`), phân tích lỗi (`error_analysis.py`). | T04, T13, T18 |
| **Test1** | `.agents/waterfall/test1.md` | Xây dựng bộ test toàn diện trong `src/tests/` kiểm tra từng module và luồng tích hợp End-to-End; đảm bảo `python3 -m unittest` pass 100%. | Nghiệm thu toàn branch |

---

## PHẦN II: ĐẶC TẢ CHI TIẾT INTERFACE GIỮA CÁC MODULE

### 1. Module `src/data_pipeline/curate_cli.py`
Phục vụ người bản ngữ hoặc nhóm nghiên cứu duyệt dữ liệu theo đúng yêu cầu kiểm định nghiêm ngặt của `clean_dedup.py` (cần `approved_record_numbers`, `reviewed_by`, `review_evidence`, và xác minh 4 trạng thái: nguồn gốc, ngôn ngữ, bản dịch, quyền sử dụng).

#### Các hàm và Interface:
```python
def review_batch(
    registry_path: Path,
    source_id: str,
    approved_numbers: list[int],
    reviewer: str,
    evidence: list[str],
    output_registry_path: Path | None = None
) -> dict:
    """Cập nhật source_registry.json với danh sách bản ghi được phê duyệt.
    
    Args:
        registry_path: Đường dẫn tới source_registry.json hiện tại.
        source_id: ID nguồn cần duyệt (vd: 'vov4', 'sample').
        approved_numbers: Danh sách số thứ tự bản ghi được duyệt (1-indexed).
        reviewer: Tên/định danh người duyệt bản ngữ/chuyên gia.
        evidence: Danh sách bằng chứng kiểm duyệt (tài liệu đối chiếu, ghi chú).
        output_registry_path: Đường dẫn ghi file mới (nếu None, ghi đè an toàn).
        
    Returns:
        dict: Source entry đã cập nhật đầy đủ các trường kiểm định.
        
    Raises:
        ValueError: Nếu source_id không tồn tại, số thứ tự ngoài phạm vi, hoặc thiếu thông tin.
    """

def interactive_curate_cli(
    raw_file_path: Path,
    registry_path: Path,
    source_id: str,
    reviewer: str
) -> None:
    """Giao diện dòng lệnh tương tác cho người bản ngữ xem từng cặp và bấm [A]ccept/[R]eject/[Q]uit."""
```

---

### 2. Module `src/models/` (Dev1)

#### 2.1. `src/models/config.py`
```python
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

class Direction(str, Enum):
    VI_TO_TAY = "vi-tyz"
    TAY_TO_VI = "tyz-vi"

@dataclass
class ModelConfig:
    model_name_or_path: str = "facebook/nllb-200-distilled-600M"
    src_lang: str = "vie_Latn"
    tgt_lang: str = "zlm_Latn"  # Fallback mã ngôn ngữ hoặc custom token cho tiếng Tày
    max_length: int = 256
    batch_size: int = 16
    learning_rate: float = 5e-5
    weight_decay: float = 0.01
    num_train_epochs: int = 5
    warmup_steps: int = 500
    seed: int = 42
    fp16: bool = True
    output_dir: Path = Path("models/checkpoints")
    mock_mode: bool = False  # Bật để chạy mô phỏng không cần GPU/tải model nặng
```

#### 2.2. `src/models/tokenizer.py`
```python
class NLLBTokenizerWrapper:
    def __init__(self, model_name_or_path: str, mock_mode: bool = False):
        """Khởi tạo tokenizer NLLB hoặc mock tokenizer cho testing."""
        
    def encode(self, text: str, lang_code: str, max_length: int = 256) -> dict[str, list[int]]:
        """Mã hóa văn bản với ngôn ngữ chỉ định thành input_ids và attention_mask."""
        
    def decode(self, token_ids: list[int]) -> str:
        """Giải mã chuỗi token IDs về văn bản thuần."""
        
    def measure_fragmentation(self, texts: list[str], lang_code: str) -> dict[str, float]:
        """Đo tỷ lệ phân mảnh token (tokens per word, character ratio) phục vụ T02."""
```

#### 2.3. `src/models/dataset.py`
```python
class TranslationDataset:
    def __init__(self, jsonl_path: Path, tokenizer: NLLBTokenizerWrapper, direction: Direction, max_length: int = 256):
        """Đọc file JSONL chứa 'tay_text' và 'vi_text', tạo các mẫu huấn luyện tokenized."""
        
    def __len__(self) -> int: ...
    def __getitem__(self, idx: int) -> dict[str, any]:
        """Trả về {'input_ids': Tensor, 'attention_mask': Tensor, 'labels': Tensor}."""

def collate_translation_batch(batch: list[dict], pad_token_id: int = 1) -> dict[str, any]:
    """Dynamic padding theo chiều dài lớn nhất trong batch."""
```

#### 2.4. `src/models/trainer.py`
```python
class TranslationTrainer:
    def __init__(self, config: ModelConfig, direction: Direction):
        """Khởi tạo model, tokenizer, optimizer, scheduler theo config."""
        
    def train(self, train_dataset: TranslationDataset, val_dataset: TranslationDataset) -> dict[str, any]:
        """Huấn luyện mô hình, theo dõi validation loss, lưu checkpoint tốt nhất.
        
        Returns:
            dict: Lịch sử huấn luyện (train_loss, val_loss, val_bleu, execution_time_sec).
        """
        
    def save_checkpoint(self, output_path: Path, metadata: dict) -> None:
        """Lưu model weights kèm manifest.json ghi run_id, seed, loss, config."""
        
    def load_checkpoint(self, checkpoint_path: Path) -> None:
        """Tải weights từ checkpoint đã lưu."""
```

---

### 3. Module `src/augmentation/` (Aug1)

#### 3.1. `src/augmentation/back_translation.py`
```python
class BackTranslator:
    def __init__(self, adapter: any, batch_size: int = 16):
        """Sử dụng InferenceAdapter của checkpoint E0 chiều ngược để dịch câu đơn ngữ."""
        
    def generate_u_dataset(
        self,
        monolingual_records: list[dict],
        generation_direction: Direction,
        output_path: Path,
        manifest_path: Path
    ) -> dict:
        """Dịch câu đơn ngữ để tạo tập U thô (chưa lọc QC).
        
        Ghi vết đầy đủ: source_monolingual_id, generation_model, generation_direction.
        """
```

#### 3.2. `src/augmentation/qc_filters.py`
Bộ lọc chất lượng 5 quy tắc (R1 đến R5):
```python
@dataclass
class QCFilterConfig:
    min_length: int = 2
    max_length: int = 200
    min_length_ratio: float = 0.4
    max_length_ratio: float = 2.5
    max_ngram_repeat: int = 3
    max_repeat_count: int = 2
    disallow_exact_copy: bool = True
    valid_character_set: str = "latin_viet_tay"  # Không chứa ký tự lạ, lỗi mã hóa UTF-8

class QCFilter:
    def __init__(self, config: QCFilterConfig = None): ...
    
    def evaluate_pair(self, src: str, tgt: str, disabled_rule: str | None = None) -> tuple[bool, list[str]]:
        """Kiểm tra một cặp câu qua 5 quy tắc QC.
        
        Args:
            src: Câu nguồn.
            tgt: Câu đích sinh ra.
            disabled_rule: 'R1' (độ dài), 'R2' (tỷ lệ độ dài), v.v. để phục vụ Ablation.
            
        Returns:
            (is_accepted, rejection_reasons)
        """
        
    def filter_records(
        self,
        records: list[dict],
        disabled_rule: str | None = None
    ) -> tuple[list[dict], list[dict], dict]:
        """Lọc toàn bộ tập bản ghi, trả về (kept_records, rejected_records, statistics)."""
```

#### 3.3. `src/augmentation/sampler.py`
```python
def sample_without_replacement(
    records: list[dict],
    n_samples: int,
    seed: int = 42
) -> tuple[list[dict], dict]:
    """Lấy ngẫu nhiên không hoàn lại đúng n_samples từ danh sách records.
    
    Returns:
        (sampled_records, manifest_info): Kèm danh sách IDs và seed để tái hiện 100%.
    """
```

#### 3.4. `src/augmentation/pipeline.py`
```python
class AugmentationPipeline:
    """Điều phối toàn bộ quy trình sinh các biến thể thực nghiệm:
    - E1: Train gốc + U (toàn bộ U)
    - E2: Train gốc + N mẫu qua đầy đủ QC
    - E1-M: Train gốc + N mẫu ngẫu nhiên từ U (đối chứng cùng kích thước N)
    - A1: Train gốc + N mẫu lọc QC khi BỎ R1
    - A2: Train gốc + N mẫu lọc QC khi BỎ R2
    """
    def run(
        self,
        train_e0_path: Path,
        u_dataset_path: Path,
        output_dir: Path,
        seed: int = 42
    ) -> dict: ...
```

---

### 4. Module `src/evaluation/` (Eval1)

#### 4.1. `src/evaluation/metrics.py`
```python
def calculate_bleu(hypotheses: list[str], references: list[list[str]]) -> dict[str, float]:
    """Tính SacreBLEU; có fallback thuần Python nếu chưa cài sacrebleu."""

def calculate_chrf(hypotheses: list[str], references: list[list[str]], word_order: int = 2) -> dict[str, float]:
    """Tính chrF++ (word_order=2) theo chuẩn nghiên cứu dịch máy."""

def compute_metrics_bundle(hypotheses: list[str], references: list[str]) -> dict[str, float]:
    """Tính toàn bộ BLEU, chrF++, độ dài trung bình, tỷ lệ từ chưa dịch."""
```

#### 4.2. `src/evaluation/evaluator.py`
```python
class ModelEvaluator:
    def __init__(self, adapter: any): ...
    
    def evaluate_dataset(
        self,
        test_jsonl_path: Path,
        direction: Direction,
        output_report_path: Path
    ) -> dict:
        """Chạy suy luận trên toàn bộ test set và xuất báo cáo metric chuẩn JSON."""
```

#### 4.3. `src/evaluation/human_eval.py`
Đảm bảo phục vụ yêu cầu T18 và đề cương nghiên cứu:
```python
class HumanEvalSampler:
    """Sinh bộ 400 câu ẩn danh đánh giá thủ công:
    - 50 câu nguồn mỗi chiều x 2 chiều = 100 câu nguồn.
    - Mỗi câu nguồn có 4 bản dịch từ 4 hệ thống: E0, E1, E2, E1-M.
    - Tổng cộng: 100 x 4 = 400 bản dịch.
    - Thứ tự các hệ thống được xáo trộn ngẫu nhiên và mã hóa thành Cand_A, Cand_B, Cand_C, Cand_D.
    - Sinh 2 file:
        1. evaluation_sheet.jsonl/csv (ẩn tên, phục vụ người chấm điểm 1-5 theo 3 tiêu chí: Đúng nghĩa, Đủ ý, Tự nhiên).
        2. unblinding_key.json (khóa giải mã, bảo mật, chỉ mở sau khi chấm xong).
    """
    def generate_blind_sheet(
        self,
        test_records: list[dict],
        system_translations: dict[str, list[str]],  # {'E0': [...], 'E1': [...], 'E2': [...], 'E1-M': [...]}
        direction: Direction,
        sample_size: int = 50,
        seed: int = 42,
        output_dir: Path = Path("data/evaluation/human_eval")
    ) -> dict: ...
```

#### 4.4. `src/evaluation/error_analysis.py`
```python
def analyze_translation_errors(
    sources: list[str],
    hypotheses: list[str],
    references: list[str]
) -> dict[str, any]:
    """Phân loại lỗi định lượng: từ chưa dịch (copy nguồn), lặp từ, thiếu ý, ảo giác (hallucination)."""
```

---

## PHẦN III: HỢP ĐỒNG SUY LUẬN VỚI `FEAT/WEB-DEMO` (INFERENCE ADAPTER)

Để nhánh `feat/web-demo` có thể phát triển song song độc lập mà không bị chặn, giao diện suy luận được chốt chuẩn hóa tại `src/models/inference_adapter.py`.

### 1. Cấu trúc dữ liệu và Hợp đồng (Data Contracts)

```python
from dataclasses import dataclass
from enum import Enum
import time

class AdapterStatus(str, Enum):
    UNINITIALIZED = "uninitialized"
    READY = "ready"
    MOCK = "mock_mode"
    ERROR = "error"

@dataclass
class TranslationResult:
    src_text: str
    tgt_text: str
    direction: str
    model_version: str
    latency_ms: float
    status: str
    error_message: str | None = None

class InferenceAdapter:
    """Hợp đồng suy luận chính thức phục vụ Web Demo và Evaluation."""
    
    def __init__(
        self,
        checkpoint_dir: str | None = None,
        direction: Direction | str = Direction.VI_TO_TAY,
        device: str = "cpu",
        mock_mode: bool = False
    ):
        """Khởi tạo adapter. Nếu checkpoint_dir=None hoặc mock_mode=True, chạy ở MOCK mode an toàn."""
        
    def is_ready(self) -> bool:
        """Kiểm tra mô hình đã sẵn sàng nhận request suy luận hay chưa."""
        
    def translate(
        self,
        text: str,
        direction: Direction | str | None = None,
        max_length: int = 256,
        num_beams: int = 4
    ) -> TranslationResult:
        """Dịch một câu đơn.
        
        Validation rules:
        - text rỗng hoặc chỉ có whitespace -> raise EmptyInputError hoặc trả status='empty_input'
        - len(text) > 2000 ký tự -> raise TextTooLongError
        - sai chiều -> raise InvalidDirectionError
        """
        
    def translate_batch(
        self,
        texts: list[str],
        direction: Direction | str | None = None,
        batch_size: int = 16
    ) -> list[TranslationResult]:
        """Dịch theo lô phục vụ đánh giá và sinh dữ liệu tăng cường."""
        
    def get_metadata(self) -> dict:
        """Trả về thông tin phiên bản mô hình, checkpoint hash, thiết bị phần cứng."""
```

### 2. Bảng mã lỗi chuẩn hóa cho Web Demo (Error Codes)

| Mã lỗi (Exception / Code) | HTTP Status tương ứng | Nguyên nhân | Phản hồi giao diện đề xuất |
| :--- | :---: | :--- | :--- |
| `EMPTY_INPUT` | 400 | Người dùng bấm dịch chuỗi rỗng hoặc toàn khoảng trắng. | "Vui lòng nhập văn bản cần dịch." |
| `TEXT_TOO_LONG` | 400 | Văn bản vượt quá giới hạn ký tự (mặc định > 2000 ký tự). | "Văn bản quá dài. Vui lòng nhập dưới 2000 ký tự." |
| `INVALID_DIRECTION` | 400 | Chiều dịch không thuộc `vi-tyz` hoặc `tyz-vi`. | "Chiều dịch không được hỗ trợ." |
| `MODEL_NOT_READY` | 503 | Mô hình chưa tải xong weights vào bộ nhớ. | "Hệ thống đang khởi động mô hình, vui lòng thử lại sau giây lát." |
| `INFERENCE_TIMEOUT` | 504 | Quá thời gian suy luận cho phép (> 15 giây). | "Thời gian xử lý quá lâu, vui lòng thử lại với câu ngắn hơn." |
| `INTERNAL_ERROR` | 500 | Lỗi ngoại lệ tính toán PyTorch/CUDA runtime. | "Đã xảy ra lỗi nội bộ trong quá trình dịch." |

---

## PHẦN IV: NHỮNG GÌ NGOÀI KẾ HOẠCH & ĐỀ XUẤT BỔ SUNG

Để đảm bảo toàn bộ pipeline chạy không phát sinh lỗi bất ngờ trong môi trường thực tế, Leader đề xuất và thiết kế thêm 5 cơ chế bổ sung:

1. **Cơ chế Mock-Engine tích hợp sẵn trong mọi module:**
   - *Vấn đề thực tế:* Việc tải checkpoint NLLB-200 (2.4GB) hoặc yêu cầu CUDA GPU có thể làm gãy các tác vụ CI/CD hoặc làm chậm quá trình kiểm thử của nhánh Web Demo.
   - *Giải pháp:* Tích hợp cờ `mock_mode=True` tại `NLLBTokenizerWrapper`, `TranslationTrainer` và `InferenceAdapter`. Khi bật cờ này, adapter áp dụng thuật toán biến đổi từ vựng đối xứng giả lập (mock translation) có độ trễ thực tế, giúp test suite và Web Demo chạy độc lập 100% không cần GPU.
2. **Bộ tính toán Metric thuần Python dự phòng (`Pure-Python SacreBLEU & chrF`):**
   - *Vấn đề thực tế:* Môi trường máy người dùng hoặc máy chấm có thể thiếu thư viện C-extension `sacrebleu`.
   - *Giải pháp:* Module `metrics.py` được thiết kế có thuật toán n-gram matching và character n-gram F-score viết bằng Python standard library làm fallback dự phòng.
3. **Module kiểm tra rò rỉ đơn ngữ độc lập (`check_monolingual_leakage`):**
   - *Vấn đề thực tế:* Tiêu chuẩn Q02 nghiêm cấm câu đơn ngữ dùng sinh U trùng với validation/test.
   - *Giải pháp:* Trước khi đưa dữ liệu đơn ngữ vào `back_translation.py`, pipeline tự động chạy kiểm tra giao tập (set intersection trên chuỗi đã normalize chữ thường) với validation set và test set. Nếu phát hiện trùng lặp, lập tức loại bỏ và ghi log cảnh báo.
4. **Công cụ duyệt dữ liệu CLI `curate_cli.py` cho người bản ngữ:**
   - *Vấn đề thực tế:* Hiện tại `clean_dedup.py` trả về `no_approved_data` do chưa có công cụ để người duyệt gán nhãn phê duyệt đúng schema của `source_registry.json`.
   - *Giải pháp:* Xây dựng `curate_cli.py` cho phép nhập liệu dòng lệnh hoặc duyệt theo batch có đối chiếu hash SHA-256 tự động, giúp giải quyết điểm nghẽn dữ liệu lớn nhất của dự án.
5. **Đóng gói bộ Fixtures chuẩn trong `src/tests/fixtures/`:**
   - Cung cấp sẵn các file mẫu nhỏ hợp lệ (`raw_sample.jsonl`, `approved_registry.json`, `tiny_monolingual.jsonl`) để các bài test của Dev1, Aug1, Eval1 chạy tức thì mà không phụ thuộc vào dữ liệu thật bên ngoài.

---

## PHẦN V: TỔNG HỢP TIẾN TRÌNH CÁC AGENT TIẾP THEO

- **Giai đoạn 1 (Data1):** Triển khai `src/data_pipeline/curate_cli.py`, tạo fixture dữ liệu kiểm duyệt mẫu đạt chuẩn, kiểm tra rò rỉ dữ liệu. (ĐÃ HOÀN THÀNH)
- **Giai đoạn 2 (Dev1):** Hoàn thiện 5 file trong `src/models/`, đặc biệt là `inference_adapter.py` để Web Demo có thể import ngay. (ĐÃ HOÀN THÀNH)
- **Giai đoạn 3 (Aug1):** Triển khai 4 file trong `src/augmentation/` phục vụ sinh E1, E2, E1-M, A1, A2. (ĐÃ HOÀN THÀNH)
- **Giai đoạn 4 (Eval1):** Triển khai 4 file trong `src/evaluation/`, xuất bộ 400 câu ẩn tên và khóa giải mã. (ĐÃ HOÀN THÀNH)
- **Giai đoạn 5 (Test1):** Viết unit tests cho toàn bộ các module trên và chạy kiểm thử toàn diện `unittest`. (ĐÃ HOÀN THÀNH: 118/118 tests PASS)

---

## PHẦN VI: TỔNG KẾT NGHIỆM THU TOÀN DIỆN (COMPREHENSIVE ACCEPTANCE & REVIEWS)

Leader tiến hành đánh giá và nghiệm thu toàn diện kết quả thực hiện của 5 kỹ sư kỹ thuật (data1, dev1, aug1, eval1, test1) theo mô hình Waterfall:

### 1. Architecture Review (Đánh giá Kiến trúc Hệ thống)
- **Tính toàn vẹn hợp đồng giao diện (Interface & Data Contracts):**
  - Hợp đồng `InferenceAdapter` giữa pipeline và nhánh `feat/web-demo` đã được hiện thực hóa chuẩn xác tại `src/models/inference_adapter.py`. Hỗ trợ cả 2 dạng gọi `translate(text, src_lang, tgt_lang)` và `translate(text, direction=...)`, trả về đối tượng `TranslationResult` hỗ trợ cả thuộc tính trực tiếp và định dạng dict (`res["tgt_text"]`), cung cấp các mã ngoại lệ chuẩn (`EmptyInputError`, `TextTooLongError`, `InvalidDirectionError`, `ModelNotReadyError`).
  - Toàn bộ 6 biến thể thực nghiệm cốt lõi (`E0`, `E1`, `E2`, `E1-M`, `A1`, `A2`) đã được mô hình hóa nhất quán xuyên suốt từ cấu hình `src/models/config.py`, bộ sinh tăng cường `src/augmentation/sampler.py` đến bộ đánh giá `src/evaluation/evaluator.py`.
- **Nguyên tắc Chống rò rỉ dữ liệu (Zero Data Leakage - Q02):**
  - Cơ chế phòng vệ rò rỉ 3 lớp: `curate_cli.py` (`check_monolingual_leakage`), `back_translation.py` (`_extract_eval_sentence_hashes`), và test tích hợp `test_end_to_end_pipeline.py` (`test_02`, `test_07`). Đảm bảo toàn bộ câu đơn ngữ trước khi dịch ngược đều được đối chiếu hash SHA-256 (sau chuẩn hóa NFC, lowercase, bỏ khoảng trắng thừa) với tập validation và test.
- **Tính tái hiện tuyệt đối (Reproducibility - Q03):**
  - Tất cả các bước lấy mẫu ngẫu nhiên (chia tập, chọn mẫu tăng cường $N$, làm mù hệ thống) đều áp dụng cơ chế Canonical Sorting (sắp xếp ổn định theo hash hoặc ID trước khi xáo trộn) kết hợp cố định `seed=42`. Khắc phục triệt để sự phụ thuộc vào thứ tự đọc file của hệ điều hành.
- **Độc lập nền tảng & Sẵn sàng CI/CD (Platform Independence - Q05):**
  - Cơ chế `mock_mode` và `MockTranslator` (tích hợp từ điển văn hóa Tày chuẩn) cùng mô hình thuần PyTorch `MockSeq2SeqModel` cho phép toàn bộ quy trình từ huấn luyện, dịch ngược, lọc QC đến đánh giá chạy mượt mà trên CPU/CI/CD mà không cần GPU hoặc checkpoint 2.4GB.

### 2. Code Review (Đánh giá Chất lượng Mã Nguồn)
- **Module Dữ liệu (`src/data_pipeline/curate_cli.py`):**
  - Mã nguồn tuân thủ typing chuẩn (`mypy` ready), xử lý ghi file an toàn nguyên tử (`_atomic_write_json` qua file tạm `.tmp.<pid>` trước khi hoán đổi), kiểm tra SHA-256 toàn vẹn dữ liệu gốc trước khi cập nhật `source_registry.json`.
  - Giao diện dòng lệnh hỗ trợ cả 3 chế độ: tương tác từng câu (`--interactive`), duyệt theo lô số thứ tự (`--approve-numbers`), và kiểm tra rò rỉ (`--check-leakage`). Phân loại lý do từ chối chuẩn mực theo 6 nhóm lỗi ngôn ngữ Tày.
- **Module Mô hình & Huấn luyện (`src/models/`):**
  - `TayTokenizerWrapper`: Xử lý mượt mà cả NLLB tokenizer thật lẫn fallback mock; bổ sung hàm đo độ phân mảnh subword `measure_fragmentation` phục vụ trực tiếp nhiệm vụ nghiên cứu T02. Đã fix lỗi biên `batch_encode([])`.
  - `TranslationCollator`: Triển khai dynamic padding chuẩn xác theo độ dài lớn nhất trong batch; gán nhãn padding bằng `-100` giúp `CrossEntropyLoss` bỏ qua hoàn toàn việc tính gradient trên token đệm `<pad>`.
  - `TranslationTrainer`: Tích hợp Early Stopping, Gradient Clipping, tính Perplexity, lưu checkpoint kèm `metadata.json` chứa cấu hình và best loss.
- **Module Tăng cường Dữ liệu (`src/augmentation/`):**
  - `QualityControlFilter`: Triển khai đầy đủ 5 quy tắc ($R1 \to R5$); đặc biệt thuật toán R2 kiểm soát n-gram đa kích thước (2, 3, 4-gram) kết hợp tỷ lệ phong phú từ vựng TTR; hỗ trợ bóc tách độc lập từng quy tắc (`disabled_rule="R1"`, `disabled_rule="R2"`).
  - `AugmentationPipeline`: Đánh dấu nguồn gốc dữ liệu tường minh (`synthetic: True/False`, `source_type: "back_translation"`), xuất manifest đầy đủ SHA-256 và danh sách ID mẫu.
- **Module Đánh giá (`src/evaluation/`):**
  - `metrics.py`: Thuật toán BLEU và chrF/chrF++ thuần Python chuẩn xác, đối chuẩn với `sacrebleu 2.6.0` đạt sai số tuyệt đối $0.000000$.
  - `human_eval.py`: Sinh gói đánh giá mù 4 hệ thống ($E0, E1, E2, E1-M$) 400 bản dịch, lưu tách biệt `unblind_key.json`, tích hợp tính Cohen's Weighted Kappa (Linear & Quadratic) chuyên biệt cho thang đo Likert 1–5.
  - `error_analysis.py`: Tự động phân loại 5 chiều lỗi (lặp từ, bất thường độ dài, chép nguồn, sót thực thể số, lỗi ký tự/mã hóa ngoại lai).

### 3. Test Review (Đánh giá Kết quả Kiểm thử)
- **Tổng số lượng bài test:** **118/118 tests PASS** (0 Failure, 0 Error) trong **6.45s - 7.33s**.
- **Phân bổ bài test theo thành phần:**
  1. `src/tests/test_end_to_end_pipeline.py`: 7 tests tích hợp E2E lớn (vệ sinh tập chia, anti-leakage dịch ngược, lọc QC & ablation, dataloader 6 biến thể, huấn luyện CPU 1 step, suy luận và đánh giá toàn trình, kiểm toán 0% rò rỉ toàn bộ file sinh ra).
  2. `src/tests/models/test_models.py`: 28 tests (cấu hình, tokenizer, fragmentation, dynamic padding, loss masking -100, trainer, inference adapter, edge cases).
  3. `src/tests/augmentation/test_augmentation.py`: 23 tests (5 quy tắc QC, ablations A1/A2, sampler đối chứng E1-M đúng $N$, back-translation, edge cases, anti-leakage).
  4. `src/tests/evaluation/test_evaluation.py`: 28 tests (SacreBLEU parity 0.000000, chrF++, 5 loại lỗi, lấy mẫu mù 400 câu, Cohen's Kappa, edge cases).
  5. `src/tests/data_pipeline/test_data_workflow.py`: 20 tests (crawling, robots, clean/dedup, deterministic split).
  6. `src/tests/data_pipeline/test_curate_cli.py`: 9 tests (batch curation, CLI tương tác, chống rò rỉ đơn ngữ).
  7. `src/tests/data_pipeline/test_build_vov_candidates.py`: 3 tests (trích xuất ứng viên VOV4).
- **Kiểm thử điều kiện biên:** Đã kiểm tra bao phủ đầu vào rỗng, khoảng trắng, câu đơn từ, $N$ lớn hơn tập ứng viên, ma trận Cohen's Kappa không phương sai (zero variance), và nhãn padding `-100`.

### 4. Kết luận Nghiệm thu Bàn giao & Khuyến nghị Vận hành
- **Kết luận:** Nhánh `feat/translation-pipeline` đã hoàn thành xuất sắc 100% mục tiêu kiến trúc, module hóa, hợp đồng giao diện và bộ kiểm thử tự động theo mô hình Waterfall.
- **Sẵn sàng tích hợp:**
  - Nhánh `feat/web-demo` có thể import trực tiếp `from src.models import TranslationInferenceAdapter` để triển khai giao diện dịch song ngữ ngay lập tức với `mock_mode=True`.
  - Nhóm `report` có đầy đủ đặc tả toán học, quy trình lấy mẫu mù 400 câu, hướng dẫn chấm điểm `HUMAN_EVAL_GUIDELINES.md` và mã nguồn tính Cohen's Kappa để đưa vào báo cáo đồ án tốt nghiệp.
- **Khuyến nghị cho giai đoạn chạy Live (Production Run):**
  1. *Dữ liệu thật & Người bản ngữ thật (T03, T08):* Dùng công cụ `curate_cli.py` để người bản ngữ Tày tiến hành phê duyệt thực tế trên 527 bản ghi thô hiện có tại `data/raw/` nhằm chuyển trạng thái `source_registry.json` sang `approved`.
  2. *Môi trường GPU thật (T12, T16, T17):* Khi triển khai huấn luyện NLLB-200 thật, cần máy chủ có GPU hỗ trợ CUDA CC $\ge 7.5$ (hoặc cài đặt PyTorch tương thích CUDA 12.x/cu126 cho GeForce GTX 1050 Ti CC 6.1) và tải checkpoint `facebook/nllb-200-distilled-600M` để thực thi huấn luyện 6 mô hình thật.
  3. *Hội đồng chấm thật (T18):* Sử dụng tệp `human_eval_sheet.csv` đã sinh để 2 giám khảo bản ngữ chấm độc lập, sau đó chạy `calculate_cohens_kappa` và `unblind_evaluation_results` để thu được điểm số chính thức.

*Báo cáo nghiệm thu hoàn tất bởi Leader vào ngày 01/11/2026.*

