# Báo cáo các Role theo Mô hình Waterfall — Nhánh translation-pipeline

Thư mục này chứa nhật ký công việc của các agent tham gia triển khai pipeline theo mô hình Waterfall cho nhánh `feat/translation-pipeline`:

- `leader.md`: Trưởng nhóm / Kiến trúc sư hệ thống (Phân tích yêu cầu, thiết kế kiến trúc, hợp đồng interface, tổng hợp nghiệm thu).
- `data1.md`: Kỹ sư dữ liệu (Công cụ thẩm định/duyệt dữ liệu cho người bản ngữ, sinh fixture kiểm thử, kiểm tra rò rỉ).
- `dev1.md`: Kỹ sư mô hình & suy luận (Module `src/models/`: config, tokenizer, dataset, trainer, inference adapter cho web-demo).
- `aug1.md`: Kỹ sư tăng cường dữ liệu (Module `src/augmentation/`: back-translation, bộ lọc QC 5 quy tắc, sampling E1-M cùng kích thước N, ablations A1/A2).
- `eval1.md`: Kỹ sư đánh giá (Module `src/evaluation/`: metrics BLEU/chrF, đánh giá tự động, bộ sinh mẫu chấm thủ công 400 câu ẩn tên, phân tích lỗi).
- `test1.md`: Kỹ sư kiểm thử / QA (Module `src/tests/`: unit tests & integration test end-to-end, chạy `python3 -m unittest`).
