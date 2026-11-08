# Báo cáo nhóm translation-pipeline

## Bàn giao ngày 08/11/2026

**Kết luận hiện tại: Cần sửa / Chưa đủ bằng chứng.** Lượt điều phối đã dừng theo yêu cầu người dùng; ba việc sửa tiếp và việc tích hợp đã hủy. Đã chia thay đổi thành commit theo task để review, chưa merge về `master`.

Xem [chỉ mục commit và bằng chứng kiểm tra 08/11](../reviews/2026-11-08-checkpoint.md): 173 tests, 172 đạt và một failure; còn tái hiện lỗi ghi đè raw, duyệt mặc định và rò rỉ tài liệu. Các báo cáo có ngày trước đó dưới đây là lịch sử, không thay thế kết luận này và không xác nhận hoàn thành thực nghiệm nghiên cứu.

## Phân công

- Nhánh: `feat/translation-pipeline`; workspace Orca: `translation-pipeline`.
- Base / đích merge: `master` / `master`.
- Người/agent nhận việc: Nhóm Waterfall (`leader`, `data1`, `dev1`, `aug1`, `eval1`, `test1`) & Agent Đánh giá/Tái hiện (Claude Code).
- Commit đầu vào: `8a8f032` (Tích hợp phân công 3 nhánh triển khai).
- Ngày khởi tạo báo cáo: 01/11/2026 | Cập nhật mới nhất: 06/11/2026.
- Phạm vi: Pipeline nghiên cứu dịch Việt–Tày (Dữ liệu, Mô hình, Tăng cường, Đánh giá, Kiểm thử).
- Đọc [phân công chung](../BRANCHES.md), [quy định báo cáo](../README.md), [TASKS.md](../../TASKS.md) và [yêu cầu dự án](../../PROJECT_REQUIREMENTS.md).

## Nhiệm vụ và ranh giới

- Nguồn, kiểm duyệt, làm sạch, chia tập và manifest trong `src/data_pipeline/`.
- Mô hình, tokenizer, loader, huấn luyện và suy luận trong `src/models/`; dịch ngược/QC trong `src/augmentation/`; metric/chấm người/phân tích lỗi trong `src/evaluation/`.
- T06 về nền Python và cấu hình dùng chung; phối hợp nhóm web-demo khi phụ thuộc thay đổi. Tái sử dụng pipeline dữ liệu có sẵn.

Đường dẫn thành phần chưa tồn tại là dự kiến, không phải bằng chứng đã triển khai. Chi tiết giao tiếp và cách nạp mô hình thống nhất tại [ARCHITECTURE.md](../../ARCHITECTURE.md).

## Đầu ra cần bàn giao

- Corpus đủ điều kiện và validation/test cố định, có bằng chứng nguồn/duyệt và kiểm tra rò rỉ.
- Pipeline huấn luyện, U/QC/đối chứng, kết quả E0/E1/E2/E1-M/A1/A2 có manifest/run ID khi đã chạy thật.
- Adapter suy luận và gói checkpoint/tokenizer/config có phiên bản để web-demo tích hợp; kết quả đánh giá và giới hạn để report viết báo cáo.

**Kiểm tra trọng tâm & Tuyên bố kiểm toán cốt lõi:**
> **"Kết quả trên Mock/Fixture chỉ chứng minh tính đúng đắn của code và chu trình (framework readiness / smoke tests), chưa phải kết quả thực nghiệm trên ngữ liệu thật".** Mọi điểm số đo đạc trên CPU và Mock model chỉ dùng cho kiểm thử tích hợp. Toàn bộ 527 bản ghi thô hiện tại CHƯA ĐỦ ĐIỀU KIỆN làm dữ liệu vàng huấn luyện (chờ duyệt bản ngữ); tính phù hợp của NLLB-600M chưa được kết luận thực nghiệm trên máy này (bị chặn GPU).

## Tiến độ từng Txx đối chiếu F01–F07 & Q01–Q07

Cột trạng thái nền chụp từ `TASKS.md` khi khởi tạo. Nhóm cập nhật tiến độ/kết quả thực tế theo từng Txx; tuyệt đối không thu nhỏ thành "mock complete" hay tự đánh dấu hoàn thành nghiên cứu.

| Mã Txx | Công việc | Yêu cầu đối chiếu | Trạng thái nền | Trạng thái thực tế | Bằng chứng trực tiếp & Giới hạn kỹ thuật |
| :---: | :--- | :---: | :---: | :---: | :--- |
| **T02** | Khảo sát mô hình/tokenizer, đo đạc phần cứng | F04, Q03, Q05 | Chưa làm | **Đang làm / Bị chặn GPU** | Đã hoàn thiện `src/models/hardware_profile.py`, xuất `docs/HARDWARE_PROFILE.md`. Đo đạc máy host: i7-9750H 12 luồng, 11GB RAM, GTX 1050 Ti 4GB VRAM Compute Capability 6.1. D01 chưa chốt NLLB. VRAM 4GB đủ nạp weights FP16 (~1.2GB) cho suy luận hoặc LoRA, nhưng thiếu bộ nhớ cho full AdamW optimizer state; 4GB thiếu full AdamW không đồng nghĩa với không nạp được weights, không tự ép GPU ngoài >= 8GB. Checkpoint cached victorpham0906/best_model.bin bị auto security mode từ chối nạp, chờ user phê duyệt. |
| **T03** | Xác nhận nguồn, chuẩn tiếng Tày, người duyệt | F01, F02, Q01 | Chưa làm | **Bị chặn (Blocked)** | Đã triển khai `src/data_pipeline/curate_cli.py` (interactive TUI, batch approval, đối chiếu SHA-256). Đã đóng băng snapshot 527 bản ghi thô. *Blocker:* Chưa có người bản ngữ Tày duyệt nội dung; chưa có cặp song ngữ nào đủ điều kiện làm dữ liệu vàng. |
| **T04** | Xác minh metric, thiết kế chấm mù 1–5, bất đồng | F07, Q04 | Chưa làm | **HOÀN THÀNH (Code & Metric)** | Đã hoàn thiện `src/evaluation/metrics.py` (đối chuẩn SacreBLEU 2.6.0 có signature, chrF `nw:0`, chrF++ `nw:2`, chuẩn hóa Unicode NFC). Đã hoàn thiện `src/evaluation/human_eval.py` (chấm mù 4 hệ thống E0/E1/E2/E1-M, 3 tiêu chí Adequacy/Completeness/Fluency, Cohen's Kappa cố định categories 1..5 và zero expected disagreement undefined rõ ràng, unblind key tách biệt lưu original ID và provenance, phân tầng source/length, báo cáo trung thực số mẫu không nhân bản). *Blocker:* Người đủ năng lực chấm thật. |
| **T06** | Tổ chức mã nguồn, phụ thuộc, cấu hình, kiểm thử nền | Q03, Q05, Q07 | Đang làm | **Đang làm** | Đã tinh gọn `requirements-models.txt` không phụ thuộc accelerate không dùng. Phân hệ evaluation đạt 38/38 tests PASS. Hai agent song song đang sửa models và data/augmentation; coordinator sẽ giao vòng tích hợp liên module sau khi hoàn tất. |
| **T07** | Hoàn thiện thu thập/nhập dữ liệu, metadata | F01, Q01, Q07 | Đang làm | **Đang làm** | Đã kiểm kê và gắn hash SHA-256 cho 8 file raw và 4 file interim; tái hiện luồng VOV4 106 bài → 97 ứng viên → 174 câu đơn ngữ khớp byte. *Giới hạn:* Chưa xác minh riêng Tày/Nùng trên từng bản ghi. |
| **T08** | Audit nguồn, phân loại cách tạo, kiểm duyệt | F02, Q01 | Đang làm | **Bị chặn (Blocked)** | Đã có công cụ `curate_cli.py` với taxonomy 6 nhóm lỗi phân loại từ chối bản dịch; đã cách ly `e1_backtranslation_rejected.jsonl`. *Blocker:* Chờ người bản ngữ duyệt thực tế. |
| **T09** | Chuẩn hóa, căn chỉnh, khử trùng lặp | F02, Q01 | Chưa làm | **Bị chặn (Blocked)** | `clean_dedup.py` đã kiểm chứng trên fixture; bị chặn do chờ dữ liệu thô được người bản ngữ duyệt trước khi làm sạch chính thức. |
| **T10** | Chia tập theo tài liệu, chống rò rỉ, manifest | F03, Q02 | Chưa làm | **Bị chặn (Blocked)** | `split_dataset.py` và `check_monolingual_leakage` đã kiểm chứng thuật toán gom nhóm theo tài liệu chống rò rỉ trên fixture. Chờ tập song ngữ duyệt thật để chia chính thức. |
| **T11** | Hoàn thiện tokenizer, loader, huấn luyện, suy luận 2 chiều | F04, Q05, Q06 | Chưa làm | **Đang làm / Bị chặn GPU** | Đã hoàn thiện code `src/models/` (config, tokenizer, dataset collator -100, trainer, inference adapter). Sửa gradient accumulation đúng chuẩn. Đã xác lập Hợp đồng suy luận tại `ARCHITECTURE.md` và bàn giao `TranslationInferenceAdapter` cho web demo. *Blocker:* Fine-tune mô hình thật bị chặn do phần cứng GPU không đủ điều kiện. Hai agent khác đang sửa lỗi nhúng và tích lũy gradient. |
| **T12** | Huấn luyện baseline E0 hai chiều | F04, Q03 | Chưa làm | **Bị chặn (Blocked)** | Đã chạy kiểm chứng chu trình E0 trên CPU với `sample_train.jsonl` (mock dry-run). *Blocker:* Chưa có dữ liệu song ngữ vàng và chưa có GPU để huấn luyện E0 thật. |
| **T13** | Bộ đánh giá tự động, trích xuất signature, phân tích lỗi | F07, Q04 | Chưa làm | **HOÀN THÀNH (Code sẵn sàng)** | Đã hoàn thiện `src/evaluation/evaluator.py`, pre-validation độ dài (nguồn/ref/IDs/provenance), fail-closed `is_mock=True` cho translator unknown/synthetic/random. `ErrorAnalyzer` đóng vai trò cờ heuristic bề mặt. *Blocker:* Chờ checkpoint thật để chạy đánh giá thực nghiệm. |
| **T14** | Dịch ngược tạo tập U dùng chung từ checkpoint E0 đảo | F05, Q02 | Chưa làm | **Bị chặn (Blocked)** | Đã chạy mock dry-run tạo 25 mẫu U từ `sample_monolingual.jsonl` với zero leakage Q02. *Blocker:* Chờ checkpoint E0 thật và đơn ngữ duyệt thật. |
| **T15** | Bộ lọc QC 5 quy tắc, đối chứng E1-M, ablations A1/A2 | F05, Q03 | Chưa làm | **Bị chặn (Blocked)** | `qc_filters.py` và `sampler.py` đã kiểm chứng logic lọc R1-R5, bóc tách A1/A2 và lấy mẫu ngẫu nhiên E1-M cùng $N=8$, seed 42. Chờ tập U thật để chốt ngưỡng QC chính thức trên validation. |
| **T16** | Huấn luyện 6 cấu hình (E0, E1, E2, E1-M, A1, A2) | F06, Q03 | Chưa làm | **Bị chặn (Blocked)** | Đã chạy chu trình mô phỏng 6 cấu hình trên CPU (`run_mock_experiments.py`) trong 8.3s. *Blocker:* Chưa có dữ liệu thật và chưa có GPU để huấn luyện thực tế. |
| **T17** | Thực nghiệm ablation A1/A2 cùng N | F06, Q03 | Chưa làm | **Bị chặn (Blocked)** | Đã kiểm chứng logic bóc tách quy tắc QC trên CPU. *Blocker:* Chưa có dữ liệu thật và chưa có GPU để chạy thực tế. |
| **T18** | Đánh giá test cố định, chấm mù 4 hệ thống, phân tích lỗi | F07, Q04 | Chưa làm | **HOÀN THÀNH (Framework/Tooling)** | `HumanEvaluationSampler` tạo gói chấm mù 3 tiêu chí, phân tầng theo nguồn và độ dài, unblind key riêng chứa original ID/provenance, tính Cohen's Kappa, báo cáo mẫu thật. *Blocker:* Cần ít nhất 1 người đủ năng lực ngôn ngữ Tày và Việt thực hiện chấm điểm thực tế (người thứ 2 dự kiến nếu có để tính Cohen's Kappa), không tự nâng điều kiện thành bắt buộc 2 người. |

## Việc đã làm và đầu ra thực tế

Nhóm translation-pipeline đã xây dựng toàn bộ khung kiến trúc, module chức năng, công cụ dữ liệu, hợp đồng suy luận và kiểm toán kỹ thuật:

| Ngày | Txx / việc đã thực hiện | File / commit / run ID | Kết quả và giới hạn |
| :--- | :--- | :--- | :--- |
| 01/11/2026 | T03, T08: Công cụ thẩm định dữ liệu & Chống rò rỉ đơn ngữ | `src/data_pipeline/curate_cli.py`, `src/tests/data_pipeline/test_curate_cli.py` | 9/9 tests pass. Hỗ trợ interactive TUI, batch approval, atomic write, kiểm tra rò rỉ đơn ngữ vs val/test. Giới hạn: Cần người bản ngữ chạy duyệt dữ liệu thô thật. |
| 01/11/2026 | T02, T06, T11: Module mô hình, tokenizer, dynamic collator, trainer, inference adapter | `src/models/` (`config.py`, `tokenizer.py`, `dataset.py`, `trainer.py`, `inference_adapter.py`), `src/tests/models/test_models.py` | 28/28 tests pass. Hỗ trợ 6 biến thể, đo phân mảnh subword T02, dynamic padding, loss masking -100, Early Stopping, MockTranslator. Bàn giao xong InferenceAdapter cho `feat/web-demo`. Giới hạn: Cần GPU và NLLB weights thật để huấn luyện live. |
| 01/11/2026 | T14, T15: Module tăng cường dữ liệu, bộ lọc QC 5 quy tắc, lấy mẫu đối chứng | `src/augmentation/` (`back_translation.py`, `qc_filters.py`, `sampler.py`, `pipeline.py`), `src/tests/augmentation/test_augmentation.py` | 23/23 tests pass. Sinh tập U, 5 quy tắc QC (R1-R5), ablations (A1, A2), lấy mẫu E1-M cùng kích thước N và seed. Tích hợp zero data leakage guard Q02. Giới hạn: Chờ checkpoint E0 thật để sinh U thật. |
| 01/11/2026 | T04, T13, T18: Module đánh giá tự động, độ đo SacreBLEU, thẩm định mù, phân tích lỗi | `src/evaluation/` (`metrics.py`, `evaluator.py`, `human_eval.py`, `error_analysis.py`), `src/tests/evaluation/test_evaluation.py` | 28/28 tests pass. BLEU & chrF++ đối chuẩn SacreBLEU 2.6.0; sinh bộ câu ẩn danh, khóa unblind riêng; phân loại lỗi bề mặt. Giới hạn: Chờ 2 người bản ngữ chấm điểm thật. |
| 01/11/2026 | T06, T25: Kiểm thử tích hợp toàn trình End-to-End | `src/tests/test_end_to_end_pipeline.py`, bộ fixture `src/tests/fixtures/` | 7/7 tests E2E pass. Kiểm chứng vệ sinh tập chia, anti-leakage dịch ngược, lọc QC & ablation, dataloader 6 biến thể, 1-step CPU training, suy luận & đánh giá toàn trình, kiểm toán 0% rò rỉ trên fixture. |
| 02/11/2026 | T02, T06, T11: Củng cố mô hình thật vs mock, sửa tích lũy gradient, tách fixture train/val/test và runner | `src/models/trainer.py`, `src/models/run_training.py`, `src/models/hardware_profile.py`, `src/tests/test_fixtures_isolation.py`, `src/tests/models/test_models.py` | 131/131 tests pass. Lỗi tải mô hình thật khi mock_mode=False raise RuntimeError; sửa gradient accumulation đúng chuẩn; tách 3 fixture train (20), val (4), test (4) cô lập 100% doc_id và câu. Ghi rõ micro-benchmark CPU không suy diễn sang NLLB-600M GPU. |
| 02/11/2026 | T12, T14, T15, T16, T17: Chu trình thực nghiệm 6 cấu hình mô phỏng (Mock Dry-Run) trên CPU | `src/models/run_mock_experiments.py`, `docs/MOCK_PIPELINE_VERIFICATION.md`, `src/tests/models/test_mock_experiments.py` | 136/136 tests pass. Chạy trọn vẹn 6 cấu hình (E0, E1, E2, E1-M, A1, A2) và E0 đảo trên CPU trong 8.3s; chống rò rỉ Q02; kiểm soát $N=8$; xuất báo cáo mô phỏng; khẳng định rõ là kiểm chứng chu trình kỹ thuật, không phải kết quả nghiên cứu. |
| 03/11/2026 | T04, T06, T13, T18: Audit và hoàn thiện module đánh giá, phụ thuộc mô hình, hợp đồng kiến trúc | `src/evaluation/metrics.py`, `src/evaluation/human_eval.py`, `src/evaluation/evaluator.py`, `src/evaluation/error_analysis.py`, `requirements-models.txt`, `ARCHITECTURE.md`, `src/tests/evaluation/test_evaluation.py` | Hoàn thiện metric SacreBLEU 2.6.0 xuất signature chính quy, chuẩn hóa Unicode NFC chống lệch 0-BLEU; hoàn thiện lấy mẫu phân tầng 3 tiêu chí Likert 1–5 (Adequacy, Completeness, Fluency) và Cohen's Quadratic Weighted Kappa; evaluator bảo toàn sample IDs/provenance; error analyzer làm rõ cờ heuristic bề mặt. |
| 06/11/2026 | T04, T06, T13, T18: Fix findings review 06/11 cho phân hệ Evaluation, requirements và tài liệu | `src/evaluation/human_eval.py`, `src/evaluation/evaluator.py`, `src/evaluation/metrics.py`, `src/tests/evaluation/test_evaluation.py`, `requirements-models.txt`, `ARCHITECTURE.md`, `README.md`, `BRANCH_PROGRESS.md`, `PROJECT_CONTEXT.md` | 38/38 evaluation unit tests PASS. Phân tầng source + length, bảo toàn original ID/provenance trong unblind key tách biệt, Cohen's Kappa cố định categories 1..5 và zero expected disagreement undefined rõ ràng; Evaluator pre-validation độ dài (sources/refs/IDs/provenance), fail-closed is_mock=True cho unknown/synthetic translator; tinh gọn requirements-models.txt loại bỏ accelerate không dùng; xóa scripts/send_done.sh thừa; sửa toàn bộ tài liệu loại bỏ các khẳng định 136 tests pass sai lệch khi log review 06/11 ghi nhận 12 errors/1 failure ở các module models và augmentation; làm rõ D01 chưa chốt NLLB, 4GB thiếu full AdamW != không nạp được weights, cached checkpoint chờ user duyệt; làm rõ D03/T18 cần ít nhất 1 người đủ năng lực (người thứ 2 nếu có). |

## Kiểm tra đã chạy

| Ngày | Lệnh / môi trường | Kết quả thực tế | Log / giới hạn |
| :--- | :--- | :--- | :--- |
| 01/11/2026 | `python3 -m unittest discover -s src/tests -t . -p 'test_*.py'` / Linux WSL2, Python 3.12 | **118/118 tests PASS** in 7.33s (0 Failure, 0 Error) | Bao phủ toàn bộ 7 test suites. Tự động chạy trên CPU do GPU GTX 1050 Ti CC 6.1 không tương thích PyTorch cu130. |
| 02/11/2026 | `python3 -m unittest discover -s src/tests` / Linux WSL2, Python 3.12 | **131/131 tests PASS** in 7.77s (0 Failure, 0 Error) | Test cách ly fixture 100% không rò rỉ, test mock_mode=False raise RuntimeError, test tích lũy gradient & cập nhật trọng số, roundtrip checkpoint hai chiều. |
| 03/11/2026 | `python3 -m unittest discover -s src/tests/evaluation` / Linux WSL2, Python 3.12 | **PASS (32 tests)** | Kiểm tra các bài test phân hệ evaluation ban đầu. |
| 06/11/2026 | `python3 -m unittest discover -s src/tests/evaluation -v` / Linux WSL2, Python 3.12 | **PASS (38/38 tests)** in 0.04s | Bao phủ toàn diện: SacreBLEU 2.6.0 signature, Unicode NFC parity, phân tầng source + length, unblind key provenance, Cohen's Kappa fixed categories 1..5, zero variance undefined, evaluator pre-validation độ dài và fail-closed mock detection. |
| 06/11/2026 | `python3 -m unittest discover -s src/tests` / Linux WSL2, Python 3.12 (Log review) | **122 tests, 12 errors, 1 failure** | Ghi nhận tại `/tmp/translation-pipeline-review-20261106.log`: do hai agent song song đang sửa module models (lỗi nhúng, test runner) và augmentation (thụt dòng sampler, rò rỉ đơn ngữ). Tuyệt đối không tuyên bố toàn repo pass trong lúc các worker khác đang sửa đổi. |

## Vướng mắc và Điểm chặn (Blockers)

1. **Dữ liệu & Con người (T03, T08, T18):**
   - 527 bản ghi thô hiện có **chưa được người bản ngữ Tày kiểm định và phê duyệt**. Toàn bộ dữ liệu song ngữ hiện tại chưa đủ điều kiện làm tập train/val/test chính thức.
   - Đánh giá thủ công cần ít nhất 1 người đủ năng lực ngôn ngữ Tày và Việt thực hiện chấm điểm thực tế (người thứ 2 dự kiến nếu có để tính Cohen's Kappa), chưa bố trí được nhân sự thực hiện.
2. **Môi trường tính toán & Mô hình (T02, T06, T11, T12, T16, T17):**
   - Máy host (Intel Core i7-9750H, 11GB RAM, GPU NVIDIA GeForce GTX 1050 Ti 4GB VRAM Compute Capability 6.1):
     - `torch==2.13.0+cu130` không hỗ trợ kiến trúc Pascal CC 6.1 (yêu cầu CC >= 7.5), nên PyTorch chạy trên CPU.
     - D01 chưa chốt NLLB. VRAM 4GB đủ nạp weights FP16 (~1.2GB) cho suy luận hoặc LoRA/PEFT, nhưng thiếu bộ nhớ cho full AdamW optimizer state; 4GB thiếu full AdamW không đồng nghĩa với không nạp được weights, không tự ép GPU ngoài >= 8GB như rào cản tuyệt đối.
     - Checkpoint cached `victorpham0906/best_model.bin` bị chế độ bảo mật tự động từ chối nạp kể cả khi `weights_only=True`, đang chờ phản hồi từ người dùng.
3. **Phối hợp liên agent:**
   - Hai agent song song đang tiến hành chỉnh sửa `src/models` và `data/augmentation`.
   - Vòng tích hợp toàn diện và kiểm toán bằng chứng cuối cùng đã được điều phối viên Orca cấu hình, sẽ thực hiện sau khi các worker độc lập hoàn tất.

## Review và tích hợp

- Trạng thái nhóm: **Đang làm / Bị chặn dữ liệu vàng & người đủ năng lực chấm**.
- Đã hoàn thành trong phạm vi nhiệm vụ: Toàn bộ code và kiểm thử phân hệ Đánh giá (`src/evaluation/`, `src/tests/evaluation/`), tệp phụ thuộc `requirements-models.txt`, tài liệu `README.md`, Hợp đồng suy luận `ARCHITECTURE.md`, đối chiếu tiến độ `BRANCH_PROGRESS.md` và `PROJECT_CONTEXT.md`. Báo cáo đánh giá độc lập ghi nhận tại `.agents/reviews/2026-11-03-evaluation.md`.
- Kết luận review: **Phân hệ Đánh giá (T04, T13, T18) và Hợp đồng suy luận ĐẠT chuẩn kỹ thuật, bảo đảm trung thực phương pháp luận và vượt qua 38/38 unit tests chuyên biệt.**
