# Bàn giao trạng thái pipeline — 08/11/2026

- Nhánh/worktree: `feat/translation-pipeline` / `translation-pipeline`.
- Commit đầu vào: `8a8f032`; nhánh nhận tích hợp dự kiến: `master`.
- Người kiểm tra: Codex, đối chiếu mã nguồn, Git, thông điệp Orca và chạy kiểm thử.
- Theo yêu cầu người dùng, đã dừng goal và hủy ba lượt sửa tiếp cùng lượt tích hợp của run `run_735130e20dea`. Ba worker đã thoát trước khi báo hoàn tất lượt sửa cuối.
- Người dùng sau đó yêu cầu lưu thay đổi thành commit theo task. Các commit dưới đây lưu trạng thái đang làm; kết luận review là **Cần sửa / Chưa đủ bằng chứng**, chưa merge và chưa nghiệm thu nghiên cứu.

## Chỉ mục commit để review

| Commit | Task | Phạm vi |
| --- | --- | --- |
| `eb1c93a0` | T06 | Phụ thuộc, `.gitignore`, fixture song ngữ/đơn ngữ và train/validation/test |
| `e96d2946` | T03, T08–T10 | CLI duyệt, làm sạch, chia tập, kiểm thử dữ liệu và cách ly fixture |
| `27483e28` | T02, T11 | Cấu hình, tokenizer, loader, mô hình, trainer, checkpoint, adapter và đo phần cứng |
| `ef94e952` | T14, T15 | Dịch ngược, năm quy tắc QC, lấy mẫu E2/E1-M/A1/A2 và manifest |
| `61a2c81b` | T04, T13, T18 | Metric, evaluator, lấy mẫu chấm mù, Kappa và phân tích lỗi |
| `2afe20f1` | T06, T16, T17 | Runner sáu cấu hình trên fixture và kiểm thử liên thành phần |

Commit tài liệu chứa file này lưu báo cáo lịch sử, kế hoạch cũ và ghi nhận bàn giao hiện tại. Nội dung staged và unstaged đã được gom theo thành phần; mã nguồn và fixture giữ nguyên nội dung tại thời điểm người dùng yêu cầu commit. Có cả thay đổi đã tồn tại trước lượt điều phối này.

## Kiểm tra thực tế ngày 08/11

Đã chạy trước khi chia commit, trên cùng nội dung mã nguồn và fixture:

```sh
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
python3 -m unittest discover -s src/tests -t . -p 'test_*.py'
```

```text
Ran 173 tests in 30.163s
FAILED (failures=1)

FAIL: test_evaluator_tiers_and_fixture_separation
AssertionError: 'mock_simulation' != 'smoke_fixture'
```

172 kiểm thử đạt, một kiểm thử thất bại tại `src/tests/evaluation/test_evaluation.py:886`. Log đầy đủ được giữ cục bộ tại `/tmp/translation-pipeline-audit-20261108.log`; tệp tạm không phải artifact bền vững của repo.

Trong lần chạy này, kiểm thử runner đã huấn luyện E0 chiều đảo và sáu biến thể chiều Việt → Tày trên CPU, với 20 mẫu train, 4 validation, 4 test. U gồm 25 mẫu do **mock lexicon** sinh; E2/E1-M/A1/A2 cùng 22 mẫu tổng hợp. Checkpoint và báo cáo của kiểm thử được tạo trong thư mục tạm. Đây là kiểm chứng chạy chương trình, chưa đáp ứng thiết kế thực nghiệm dùng E0 chiều ngược để sinh U từ corpus đã duyệt.

`git diff --check HEAD` trước khi commit còn báo khoảng trắng cuối dòng và dòng trống cuối file, chủ yếu ở tài liệu lịch sử. Không coi kiểm tra định dạng này là đã đạt.

## Lỗi còn tái hiện ngoài bộ unit test

Các kiểm tra dưới đây dùng dữ liệu giả và thư mục tạm, không sửa dữ liệu nguồn thật. Kết quả được giữ tại `/tmp/translation-pipeline-regressions-20261108.jsonl`.

| Task | Kết quả quan sát | Giới hạn cần xử lý |
| --- | --- | --- |
| T03, T08, Q07 | `curate_candidate_file` ghi đè được tệp sentinel trong `data/raw` giả lập; các trạng thái duyệt mặc định tạo `training_approved=True` | Bảo vệ output và yêu cầu quyết định duyệt rõ ràng chưa đúng |
| T08, T14 | `validate_dataset_admissibility` nhận E0 có `training_approved=False` | Kiểm tra định dạng chưa phải kiểm định điều kiện nghiên cứu |
| T10, T14, Q02 | Đơn ngữ cùng tài liệu với validation vẫn sinh một bản ghi U được nhận, trong khi `leakage_count=0` | Còn rò rỉ theo tài liệu và mất provenance trong đường sinh U |
| T13, Q04 | Unit test phân loại kết quả smoke trả `mock_simulation` thay vì `smoke_fixture` | Hợp đồng metadata giữa mô hình và evaluator chưa thống nhất |

Ba kiểm tra bổ sung cho thấy một phần sửa đã có tác dụng: tokenizer đóng băng với dung lượng 256 không phát sinh ID vượt biên; cấu hình tokenizer BLEU không hợp lệ bị từ chối; lấy hai mẫu từ sáu nguồn thay đổi theo seed, không còn luôn chọn hai nguồn đầu. Đây chỉ là xác minh các tình huống cụ thể. Các finding khác về checkpoint/tokenizer, padding, chiều dịch và đường chạy nghiên cứu chưa được nghiệm thu toàn diện sau lượt sửa cuối.

## Dữ liệu, artifact và tài liệu lịch sử

- Registry/inventory ghi snapshot 527 bản ghi, tám nguồn và không có bản ghi được duyệt. Tại lần kiểm tra 08/11, cả tám đường dẫn raw trong registry đều không tồn tại ở worktree này; chỉ có manifest trong `data/`.
- Còn một checkpoint E0 cục bộ từ 02/11: `mock_mode=True`, CPU, ba epoch và 12 bước. Checkpoint này nằm trong thư mục bị Git bỏ qua; không phải kết quả baseline trên corpus thật.
- Chưa có corpus đủ điều kiện, bộ thực nghiệm nghiên cứu hai chiều, phiếu chấm thực tế hoặc nghiệm thu tích hợp cuối.
- `docs/MOCK_PIPELINE_VERIFICATION.md` và các báo cáo 01–06/11 được giữ làm lịch sử. Những câu “100%”, “zero blockers”, “sẵn sàng nghiên cứu” trong đó không phải kết luận hiện tại. Các ước tính bộ nhớ weights cũng chưa chứng minh khả năng chạy suy luận hoặc LoRA/PEFT trên GPU 4GB.
- Chưa cập nhật trạng thái nghiệm thu trong `TASKS.md`; việc commit không thay thế review hoặc merge về `master`.
