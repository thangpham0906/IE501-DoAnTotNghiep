# IE501 — Đồ án tốt nghiệp

> **Trạng thái nhánh pipeline ngày 08/11/2026:** Đã dừng lượt điều phối và lưu thay đổi theo task để review. Bộ kiểm thử hiện có một failure và còn lỗi kiểm định dữ liệu; chưa nghiệm thu nghiên cứu. Xem [bàn giao hiện tại](.agents/reviews/2026-11-08-checkpoint.md) trước khi dùng các báo cáo chạy thử bên dưới.

**Đề tài:** Nghiên cứu hệ thống dịch máy cho ngôn ngữ ít tài nguyên: Xây dựng bộ dữ liệu và phương pháp tăng cường dữ liệu cho tiếng Tày.

**Research on Machine Translation Systems for Low-Resource Languages: A Dataset and Data Augmentation Methods for the Tay Language.**

Dự án nghiên cứu bộ dữ liệu, phương pháp tăng cường dữ liệu và hệ thống dịch máy **Việt ↔ Tày**, kèm ứng dụng minh họa.

| Vai trò | Họ tên | MSSV |
| --- | --- | --- |
| Sinh viên | Phạm Quốc Thắng | 25410304 |
| Sinh viên | Lê Minh Thiện | 25410313 |
| Giảng viên hướng dẫn | ThS. Nguyễn Thành Luân | — |

Hệ đào tạo: Đào tạo từ xa — Trường Đại học Công nghệ Thông tin, ĐHQG TP.HCM.

**Thời gian thực hiện:** 05/11/2026–17/01/2027. Xem kế hoạch 11 tuần công việc tại [TASKS.md](TASKS.md).

## Tài liệu dự án

| Tài liệu | Nội dung |
| --- | --- |
| [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) | Bối cảnh, phạm vi và các quyết định cần thống nhất |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Thành phần hệ thống, luồng dữ liệu và cấu trúc mã nguồn dự kiến |
| [PROJECT_REQUIREMENTS.md](PROJECT_REQUIREMENTS.md) | Yêu cầu chức năng, chất lượng và tiêu chí nghiệm thu |
| [TASKS.md](TASKS.md) | Trạng thái hiện tại, công việc, phụ thuộc và bằng chứng hoàn thành |
| [.agents/README.md](.agents/README.md) | Quy định báo cáo/review theo nhóm; [phân công 3 nhánh và báo cáo](.agents/BRANCHES.md) |
| [Quy trình xây dựng dữ liệu](docs/QUY_TRINH_XAY_DUNG_DU_LIEU.md) | Từng bước tạo file trong `data/`, lệnh đã chạy, kết quả và nội dung báo cáo tiến độ |
| [AGENTS.md](AGENTS.md) | Hướng dẫn dành cho agent làm việc với repo |

## Bắt đầu

### Môi trường và Phụ thuộc

Dự án sử dụng Python >= 3.10 (đã kiểm tra và đo đạc trên Python 3.12.3 WSL2 Linux). Các thư viện phục vụ mô hình và đánh giá được liệt kê tại `requirements-models.txt` (`torch`, `sacrebleu 2.6.0`, `sentencepiece 0.2.2`).

> **Lưu ý phần cứng & Phạm vi thực thi:**
> Máy phát triển sở tại (Host: Intel Core i7-9750H 12 luồng, 11GB RAM, GPU NVIDIA GTX 1050 Ti 4GB VRAM Compute Capability 6.1). Do `torch==2.13.0+cu130` yêu cầu CUDA Compute Capability >= 7.5, toàn bộ các bài kiểm thử tự động, tích lũy gradient và chu trình thực nghiệm 6 cấu hình (E0, E1, E2, E1-M, A1, A2) được cấu hình chạy an toàn trên CPU với chế độ `mock_mode=True`.

### Lệnh chạy kiểm thử

Chạy toàn bộ các bộ kiểm thử tích hợp và kiểm tra hồi quy từ thư mục gốc:

```bash
python3 -m unittest discover -s src/tests -t . -p 'test_*.py'
```

Hoặc chạy độc lập từng phân hệ chuyên biệt:

```bash
# Kiểm thử phân hệ Đánh giá (Metrics SacreBLEU 2.6.0, Phân tích lỗi, Chấm mù Human Eval, Cohen's Kappa)
python3 -m unittest discover -s src/tests/evaluation

# Kiểm thử phân hệ Mô hình & Cơ chế huấn luyện (Gradient accumulation, dynamic collator, adapter)
python3 -m unittest discover -s src/tests/models

# Kiểm thử phân hệ Dữ liệu (Curate CLI, chống rò rỉ đơn ngữ Q02)
python3 -m unittest discover -s src/tests/data_pipeline

# Kiểm thử phân hệ Tăng cường dữ liệu (Back-translation, 5 bộ lọc QC, bộ lấy mẫu đối chứng)
python3 -m unittest discover -s src/tests/augmentation

# Kiểm thử tích hợp toàn trình (End-to-End Pipeline)
python3 -m unittest src/tests/test_end_to_end_pipeline.py
```

### Hiện trạng và Giới hạn Kỹ thuật Trung thực

- **Dữ liệu:** Đã có snapshot 527 bản ghi thô và các tệp manifest SHA-256 cố định; đã chạy lại luồng VOV4 106 bài → 97 ứng viên tài liệu → 174 câu đơn ngữ và đối chiếu khớp byte. **Chưa có bản ghi nào được người bản ngữ Tày xác nhận duyệt để làm dữ liệu vàng huấn luyện.**
- **Mô hình:** Đã kiểm chứng thiết kế code huấn luyện hai chiều và bộ điều hợp `TranslationInferenceAdapter` bàn giao cho `feat/web-demo`. Kiến trúc chưa chốt NLLB (D01 đang mở). Host chạy CPU do GPU GTX 1050 Ti CC 6.1 không tương thích kernel cu130; VRAM 4GB đủ nạp weights FP16 (~1.2GB) cho suy luận hoặc LoRA nhưng thiếu bộ nhớ cho full AdamW optimizer. Checkpoint cached `victorpham0906/best_model.bin` bị chế độ bảo mật tự động từ chối nạp, đang chờ phê duyệt từ người dùng. Hai agent song song đang hoàn thiện module mô hình và tăng cường dữ liệu.
- **Đánh giá:** Đã tích hợp SacreBLEU 2.6.0 có signature và chuẩn hóa Unicode NFC; công cụ chấm mù 3 tiêu chí và Cohen's Kappa sẵn sàng. Đánh giá thủ công cần ít nhất 1 người đủ năng lực ngôn ngữ Tày và Việt, người thứ 2 dự kiến nếu có để đo độ nhất trí liên giám khảo. **Chưa có người bản ngữ đủ năng lực thực hiện chấm điểm thực tế.**
- Mọi điểm số đo đạc trên Mock model và fixture nhỏ chỉ chứng minh tính thông suốt của chu trình kỹ thuật (framework readiness / smoke tests), tuyệt đối không phải kết quả nghiên cứu khoa học chính thức.

Xem [kiểm kê dữ liệu](data/manifests/inventory.json), [danh mục nguồn](data/manifests/source_registry.json) và [kết quả kiểm tra](data/manifests/validation_report.json). Dữ liệu và log hiện lưu cục bộ, được `.gitignore` loại khỏi Git trong khi xác minh nguồn và điều kiện sử dụng; bản clone chỉ có manifest sẽ không tự có corpus. Các số lượng chi tiết và việc còn lại được quản lý tại [TASKS.md](TASKS.md).

## Tài liệu tham khảo

- [Đề cương chi tiết đồ án](docs/DeCuongDATN_25410304_25410313.pdf)
- [Bản Markdown để chỉnh đề cương](docs/DeCuongDATN_25410304_25410313.md)
- [Các mục đã sửa và hướng dẫn xuất PDF](docs/REVIEW_DE_CUONG.md)
- [Danh sách GVHD và thông tin](reference/Danh%20sách%20GVHD%20và%20thông%20tin.md)
