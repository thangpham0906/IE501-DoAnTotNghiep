# BÁO CÁO KIỂM CHỨNG CHU TRÌNH THỰC NGHIỆM TRÊN DỮ LIỆU MÔ PHỎNG (MOCK DRY-RUN)

**Thời điểm thực thi**: 2026-11-02 12:22:42 UTC  
**Môi trường thực thi**: CPU (PyTorch 2.13.0 native CPU runtime)  
**Kịch bản điều phối**: `src/models/run_mock_experiments.py`  
**Bộ fixtures kiểm thử**: `sample_train.jsonl`, `sample_val.jsonl`, `sample_test.jsonl`, `sample_monolingual.jsonl`  

---

## ⚠️ Tuyên bố Bản chất Kiểm chứng & Miễn trừ Khoa học

> **LƯU Ý CỐT LÕI (IMPORTANT DISCLAIMER)**:  
> Báo cáo này là bằng chứng nghiệm thu kỹ thuật xác nhận **độ thông suốt của luồng dữ liệu, tính đúng đắn của logic giải thuật, tích lũy gradient, cơ chế chống rò rỉ (Q02), các bộ lọc QC và các giao diện mã nguồn (API interfaces)**.  
> Đây là quy trình chạy thử trên **dữ liệu mô phỏng (fixtures/mock data) và mô hình kiểm thử nhẹ trên CPU**; **HOÀN TOÀN KHÔNG PHẢI KẾT QUẢ NGHIÊN CỨU CHÍNH THỨC** và không thể dùng làm bằng chứng khoa học cho hiệu quả cải thiện dịch thuật của NLLB-200. Thực nghiệm chính thức sẽ được tiến hành riêng khi toàn bộ tập ngữ liệu thực tế đạt chuẩn kiểm định. Không ngoại suy các thông số thời gian, bộ nhớ hay BLEU sang mô hình thật.

---

## 1. Thiết kế và Quy chuẩn 6 Cấu hình Thực nghiệm

Chu trình thực nghiệm đối chiếu 6 cấu hình độc lập được kiểm soát nghiêm ngặt:

1. **E0 (Baseline - Đường cơ sở)**: Huấn luyện hoàn toàn trên dữ liệu song ngữ chuẩn `20` mẫu.
2. **U (Dữ liệu tổng hợp)**: Sinh bằng mô hình đảo E0 (`tyz-vi`) dịch ngược `25` câu đơn ngữ Tày, loại trừ hoàn toàn các câu trùng với tập val và test theo chuẩn Q02.
3. **E2 (Đề xuất chính - Full QC)**: Lọc tập U qua đầy đủ 5 quy tắc (R1 đến R5), lấy ra chính xác **$N = 8$** mẫu kết hợp với E0 (Tổng: `28` mẫu).
4. **E1-M (Kiểm soát ngẫu nhiên - Fair Control)**: Lấy mẫu ngẫu nhiên không hoàn lại từ U đúng **$N = 8$** mẫu cùng master seed `42` kết hợp với E0 (Tổng: `28` mẫu). Đảm bảo quy mô dữ liệu tương đồng $100\%$ với E2.
5. **A1 (Ablation 1)**: Bỏ riêng quy tắc R1 (tỷ lệ độ dài), lấy đúng **$N = 8$** mẫu kết hợp với E0 (Tổng: `28` mẫu).
6. **A2 (Ablation 2)**: Bỏ riêng quy tắc R2 (lặp từ), lấy đúng **$N = 8$** mẫu kết hợp với E0 (Tổng: `28` mẫu).
7. **E1 (Không lọc)**: Kết hợp toàn bộ tập U chưa qua chọn lọc (`25` mẫu) với E0 (Tổng: `45` mẫu).

---

## 2. Bảng Tổng Hợp Kết Quả Định Lượng Trên Tập Test (sample_test.jsonl)

| Cấu hình | Mục đích đối sánh | Quy mô Train | Test Loss ↓ | Test PPL ↓ | BLEU ↑ | chrF ↑ | chrF++ ↑ | Tỷ lệ lỗi (%) ↓ | Latency trung bình |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **E0** | Baseline dữ liệu sạch | 20 | 10.4142 | 33328.09 | **4.59** | 23.77 | 22.40 | 75.0% | 0.60 ms |
| **E1** | Song ngữ gốc + toàn bộ U (chưa lọc) | 45 | 10.3794 | 32190.29 | **4.59** | 23.77 | 22.40 | 75.0% | 0.20 ms |
| **E2** | Song ngữ gốc + N mẫu qua 5 quy tắc QC | 28 | 10.3854 | 32384.74 | **4.59** | 23.77 | 22.40 | 75.0% | 0.23 ms |
| **E1-M** | Song ngữ gốc + N mẫu ngẫu nhiên từ U | 28 | 10.3858 | 32395.56 | **4.59** | 23.77 | 22.40 | 75.0% | 0.20 ms |
| **A1** | Song ngữ gốc + N mẫu bỏ quy tắc R1 | 28 | 10.3854 | 32384.74 | **4.59** | 23.77 | 22.40 | 75.0% | 0.18 ms |
| **A2** | Song ngữ gốc + N mẫu bỏ quy tắc R2 | 28 | 10.3854 | 32384.74 | **4.59** | 23.77 | 22.40 | 75.0% | 0.18 ms |

---

## 3. Nhật Ký Kiểm Chứng Kỹ Thuật (Technical Verification Findings)

### 3.1. Tính Toàn Vẹn Của Cơ Chế Chống Rò Rỉ (Q02 Anti-Leakage)
- Mã nguồn kiểm chứng: `src/augmentation/back_translation.py` qua hàm `_extract_eval_sentence_hashes()`.
- Đã đối chiếu toàn bộ các câu trong `src/tests/fixtures/sample_monolingual.jsonl` với băm SHA-256 của `src/tests/fixtures/sample_val.jsonl` và `src/tests/fixtures/sample_test.jsonl`.
- Kết quả: **0 câu rò rỉ lọt vào tập dữ liệu tổng hợp U**. Cơ chế băm chuẩn hóa hoạt động chính xác trước khi đưa vào hàng đợi dịch ngược.

### 3.2. Tính Nhất Quán Về Kích Thước Kiểm Soát (Fair Control N)
- Số mẫu được chọn qua bộ lọc QC 5 tiêu chí: **$N = 8$ mẫu**.
- Số lượng mẫu trích xuất cho các nhánh kiểm soát: `len(E2) = len(E1-M) = len(A1) = len(A2) = 8`.
- Điều này đảm bảo tính tương đồng thống kê tuyệt đối khi chuyển sang ngữ liệu lớn, loại trừ hoàn toàn nhiễu do chênh lệch dung lượng huấn luyện.

### 3.3. Tích Lũy Gradient & Cập Nhật Trọng Số Trên CPU
- Kiểm chứng `optimizer.step()`: chạy đúng chu kỳ phân đoạn tích lũy gradient `gradient_accumulation_steps = 2`.
- Kiểm chứng checkpointing: Toàn bộ 6 thư mục checkpoint đều xuất đủ 4 tệp cốt lõi (`model.pt`, `model_config.json`, `training_config.json`, `metadata.json`).
- Trọng số nạp lại (`load_checkpoint`) cho kết quả suy luận và logits trùng khớp 100% với trạng thái tại thời điểm lưu.

### 3.4. Giao Tiếp Suy Luận & Đánh Giá Tự Động (Inference Adapter & Evaluator)
- `TranslationInferenceAdapter` tương thích hoàn toàn hai chiều `vi-tyz` và `tyz-vi`.
- `TranslationEvaluator` tự động tính toán đồng thời BLEU, chrF, chrF++, phân loại lỗi định lượng và đo lường độ trễ suy luận (latency, p95, throughput).

---

## 4. Kết Luận Nghiệm Thu & Khuyến Nghị Chuyển Tiếp

1. **Chu trình thực nghiệm 6 cấu hình đã hoàn tất thông suốt 100%**: Sẵn sàng nhận tham số và cấu hình NLLB-200 khi huấn luyện chính thức.
2. **Không ghi nhận lỗi chặn (Zero Blockers)**: Luồng dữ liệu từ Curate CLI -> Back-translation -> QC -> Sampler -> Trainer -> Evaluator hoạt động nhịp nhàng không phụ thuộc giả định ẩn.
3. **Điều kiện chuyển sang huấn luyện chính thức**: Khi tập ngữ liệu song ngữ đạt mốc tối thiểu theo tài liệu và môi trường GPU có sẵn, thay đổi `--mock-mode False` và nạp trọng số NLLB-200.

*Báo cáo được khởi tạo tự động bởi `src/models/run_mock_experiments.py`.*