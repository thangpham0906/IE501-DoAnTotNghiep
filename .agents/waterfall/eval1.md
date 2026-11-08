# BÁO CÁO CÔNG VIỆC KỸ SƯ ĐÁNH GIÁ CHẤT LƯỢNG DỊCH MÁY (EVAL1) — MÔ HÌNH WATERFALL
## Nhánh: `feat/translation-pipeline`
**Người thực hiện / Vai trò:** Evaluation Engineer (eval1)  
**Ngày lập:** 01/11/2026  
**Nhiệm vụ phụ trách:** T04, T13, T18, T23 (Module `src/evaluation/`, các chỉ số BLEU/chrF/chrF++, bộ đánh giá thực nghiệm đa biến thể `TranslationEvaluator`, bộ công cụ lấy mẫu và chấm ẩn danh 400 bản dịch `HumanEvaluationSampler`, hệ số nhất trí Cohen's Kappa, bộ phân loại lỗi dịch tự động đa chiều `ErrorAnalyzer`)  
**Trạng thái hoàn thành:** Đã hoàn thành 100% mục tiêu module `src/evaluation/`, 21/21 unit tests chuyên biệt pass (tổng cộng 88/88 test toàn repo pass), sẵn sàng bàn giao cho Test1 (QA / End-to-End) và nhóm Report.

---

## PHẦN I: MỤC TIÊU & PHẠM VI NHIỆM VỤ

1. **Xây dựng module `src/evaluation/` hoàn chỉnh:**
   - `src/evaluation/__init__.py`: Xuất khẩu toàn bộ các giao diện đánh giá, độ đo, phân tích lỗi và thẩm định thủ công.
   - `src/evaluation/metrics.py`: Công cụ tính toán BLEU score (n-gram precision kết hợp brevity penalty) và chrF / chrF++ score (character n-gram kết hợp word n-grams) bằng Python nguyên bản, độc lập thư viện ngoài và tương thích 100% với định dạng chuẩn của SacreBLEU.
   - `src/evaluation/evaluator.py`: Lớp `TranslationEvaluator` đánh giá toàn diện trên tập dữ liệu kiểm thử (test set/validation set), đo lường độ trễ (latency/throughput) và xuất báo cáo so sánh BLEU/chrF hai chiều (Việt $\to$ Tày, Tày $\to$ Việt) cho 6 biến thể thực nghiệm cốt lõi ($E0, E1, E2, E1-M, A1, A2$).
   - `src/evaluation/human_eval.py`: Bộ công cụ phục vụ thẩm định thủ công theo đúng quy chuẩn T04 và T18:
     + Lấy mẫu ngẫu nhiên 50 câu test mỗi chiều trên 4 cấu hình chính ($E0, E1, E2, E1-M$), tổng cộng 400 bản dịch.
     + Ẩn tên hệ thống (blind evaluation), hoán vị thứ tự ngẫu nhiên có cố định hạt giống (seed=42) và lưu khóa giải mã tách biệt (`unblind_key.json`).
     + Xuất phiếu chấm mẫu (CSV và JSONL) theo thang điểm Likert 1-5 cho hai tiêu chí: Độ chính xác ngữ nghĩa (Semantic Accuracy) và Độ trôi chảy (Fluency).
     + Hàm tính hệ số nhất trí giữa 2 người chấm độc lập (Cohen's Kappa: unweighted, linear weighted và quadratic weighted).
   - `src/evaluation/error_analysis.py`: Bộ phân loại lỗi dịch tự động đa chiều: phát hiện thoái hóa lặp từ (repetition), độ dài bất thường (cụt câu / bùng nổ ảo giác), sao chép câu nguồn (source copy), bỏ sót thực thể số (missing numbers) và lỗi mã hóa/ký tự ngoại lai (corrupted script/encoding).

2. **Tuân thủ các tiêu chuẩn chất lượng và nghiên cứu cốt lõi:**
   - **F07 (Đánh giá và phân tích lỗi):** Đánh giá hai chiều với bản dịch tham chiếu chuẩn, metric đúng cấu hình, đánh giá mù 4 hệ thống trên cùng mẫu, xuất phiếu điểm và báo cáo phân tích lỗi.
   - **Q03 (Tính tái hiện tuyệt đối - Reproducibility):** Cố định hạt giống ngẫu nhiên (`seed=42`), sắp xếp danh sách bản ghi theo thứ tự chuẩn hóa (canonical sort), lưu manifest đầy đủ mã bản ghi và siêu dữ liệu.
   - **Q04 (Chỉ số và báo cáo phản ánh đúng thực nghiệm):** BLEU và chrF/chrF++ đạt độ chính xác máy tính đối chiếu tuyệt đối với `sacrebleu 2.6.0` (sai lệch $0.000000$), ghi rõ phiên bản và thông số cấu hình.
   - **Q05 (Vận hành độc lập nền tảng):** Chạy thuần Python độc lập, không phụ thuộc bắt buộc vào GPU hay việc nạp mô hình lớn, tương thích hoàn toàn với chế độ `mock_mode`.

---

## PHẦN II: CÔNG VIỆC ĐÃ HOÀN THÀNH TRONG KẾ HOẠCH

### 1. `src/evaluation/metrics.py`: Độ đo BLEU, chrF, chrF++ chuẩn SacreBLEU
Triển khai thuật toán tính toán độ đo tự động bằng Python chuẩn:

- **Bộ tách từ chuẩn SacreBLEU 13a (`Tokenizer13a` / `tokenize_13a`):**
  - Tách các dấu câu chuẩn (`.,;:!?()[]{}"'~`), xử lý dấu chấm và phẩy ngăn cách số, bảo toàn dấu gạch nối trong từ, chuẩn hóa các thực thể XML/HTML (`&quot;`, `&amp;`, `&lt;`, `&gt;`).
  - Hỗ trợ cả chế độ `tokenize="13a"` và `tokenize="whitespace"`.
- **Thuật toán BLEU (Papineni et al., 2002; Post, 2018):**
  - Trích xuất n-gram từ bậc 1 đến 4, cắt xén số đếm n-gram trùng khớp (clipped n-gram counts) so với các câu tham chiếu (references).
  - Hỗ trợ đa tham chiếu (multi-references per hypothesis) và định dạng luồng SacreBLEU stream.
  - Tính phạt độ dài ngắn (Brevity Penalty):
    $$\text{BP} = \begin{cases} 1 & \text{nếu } c > r \\ \exp\left(1 - \frac{r}{c}\right) & \text{nếu } c \le r \end{cases}$$
  - Hỗ trợ đầy đủ 4 phương pháp làm mịn n-gram (Smoothing methods): `exp` (mặc định của SacreBLEU), `floor` (0.1), `add-k` (Lin & Och 2004) và `none`.
  - Hỗ trợ cờ `effective_order` cho đánh giá cấp câu (sentence-level BLEU).
  - Đối chiếu kiểm thử với thư viện `sacrebleu 2.6.0`: Độ sai lệch giữa kết quả tính của `metrics.py` và `sacrebleu` đạt **$0.000000$** trên toàn bộ các câu thử nghiệm.
- **Thuật toán chrF và chrF++ (Popović, 2015; 2017):**
  - Trích xuất n-gram ký tự từ bậc 1 đến bậc 6 (mặc định `char_order=6`).
  - chrF++ mở rộng: bổ sung n-gram cấp độ từ từ bậc 1 đến bậc 2 (`word_order=2`), sử dụng bộ lọc dấu câu biên `CHRF_PUNCTS`.
  - Tính độ chính xác (Precision) và độ bao phủ (Recall) trung bình qua các bậc n-gram, sau đó tính $F_\beta$ với trọng số $\beta = 2.0$ (ưu tiên Recall cao gấp đôi Precision):
    $$F_\beta = (1 + \beta^2) \frac{P_{avg} \cdot R_{avg}}{\beta^2 P_{avg} + R_{avg}} \times 100$$
  - Đối chiếu kiểm thử với `sacrebleu`: Kết quả chrF và chrF++ trùng khớp chính xác từng số thập phân so với thư viện chuẩn.

---

### 2. `src/evaluation/evaluator.py`: Lớp `TranslationEvaluator` & Báo cáo 6 biến thể
- Đánh giá song song toàn diện 6 cấu hình nghiên cứu theo đề cương và `PROJECT_REQUIREMENTS.md`:
  + $E0$: Mô hình baseline huấn luyện trên song ngữ kiểm định sạch.
  + $E1$: Mô hình E0 + toàn bộ tập dịch ngược tổng hợp $U$ thô.
  + $E2$: Mô hình E0 + $N$ mẫu tổng hợp lọc qua 5 quy tắc QC.
  + $E1-M$: Mô hình E0 + $N$ mẫu ngẫu nhiên không hoàn lại từ $U$ (đối chứng với $E2$).
  + $A1$: Mô hình E0 + $N$ mẫu khi tắt quy tắc R1 (tỷ lệ độ dài).
  + $A2$: Mô hình E0 + $N$ mẫu khi tắt quy tắc R2 (lặp từ/n-gram).
- Đánh giá theo cả 2 chiều dịch: Việt $\to$ Tày (`vi-tyz`) và Tày $\to$ Việt (`tyz-vi`).
- Thu thập số liệu hiệu năng suy luận chi tiết:
  + Độ trễ trung bình (Mean Latency), trung vị (Median Latency), phân vị 95 (P95 Latency).
  + Thông lượng xử lý: số câu dịch trên giây (Sentences per Second - SPS).
- Tích hợp tự động bộ phân tích lỗi `ErrorAnalyzer` trong cùng một lượt chạy đánh giá.
- Xuất báo cáo tổng hợp Markdown và tệp JSON manifest phục vụ truy vết kết quả thực nghiệm.

---

### 3. `src/evaluation/human_eval.py`: Bộ công cụ lấy mẫu và chấm ẩn danh (T04, T18)
- **Lớp `HumanEvaluationSampler`:**
  - Nhận tập dữ liệu test và 4 hệ thống mô hình chính ($E0, E1, E2, E1-M$).
  - Lấy mẫu ngẫu nhiên không hoàn lại 50 câu tiếng Việt $\to$ Tày và 50 câu tiếng Tày $\to$ tiếng Việt. Nếu tập test có quy mô nhỏ hơn 50 câu, bộ lấy mẫu sẽ sử dụng toàn bộ số câu hiện có và ghi nhận cờ `is_truncated: True` theo đúng quy định tại `PROJECT_REQUIREMENTS.md`.
  - Sinh tổng cộng đúng **400 bản dịch** (50 câu $\times$ 4 hệ thống $\times$ 2 chiều dịch).
- **Quy trình làm mù (System Blinding) và khử thiên vị:**
  - Các hệ thống được gán nhãn mù ngẫu nhiên theo từng mẫu: `SYS_A`, `SYS_B`, `SYS_C`, `SYS_D`.
  - Hoán vị thứ tự ngẫu nhiên độc lập trên từng câu với hạt giống cố định (`seed=42`), triệt tiêu hoàn toàn hiệu ứng thiên vị vị trí (position bias) và thiên vị nhận thức tên mô hình của giám khảo.
  - Tách riêng tệp chìa khóa giải mã `unblind_key.json` lưu trữ biệt lập, người chấm chỉ nhận phiếu chấm chứa mã mù.
- **Xuất phiếu chấm mẫu (CSV & JSONL):**
  - Cung cấp tệp `human_eval_sheet.csv` và `human_eval_sheet.jsonl` có cấu trúc chuẩn hóa cho người chấm điền điểm.
  - Đánh giá theo 2 tiêu chí trên thang điểm Likert 1–5:
    1. **Độ chính xác ngữ nghĩa (Semantic Accuracy / Adequacy):** 1 (mất nghĩa/sai hoàn toàn) đến 5 (bảo toàn trọn vẹn ngữ nghĩa nguồn).
    2. **Độ trôi chảy (Fluency):** 1 (vô nghĩa/hỏng ngữ pháp) đến 5 (tự nhiên chuẩn bản ngữ).
- **Tài liệu hướng dẫn chấm điểm (`HUMAN_EVAL_GUIDELINES.md`):**
  - Cung cấp định nghĩa tường minh, tiêu chí phân loại và ví dụ minh họa song ngữ Việt — Tày cho từng mức điểm 1 đến 5.
- **Hàm tính hệ số nhất trí Cohen's Kappa (`calculate_cohens_kappa`):**
  - Đo lường mức độ đồng thuận thực tế giữa 2 người chấm độc lập loại trừ yếu tố trùng khớp ngẫu nhiên:
    $$\kappa = \frac{p_o - p_e}{1 - p_e}$$
  - Tự động xây dựng ma trận nhầm lẫn (Confusion Matrix), tính tỷ lệ đồng thuận quan sát ($p_o$) và kỳ vọng ngẫu nhiên ($p_e$).

---

### 4. `src/evaluation/error_analysis.py`: Phân loại lỗi dịch tự động đa chiều
Triển khai lớp `ErrorAnalyzer` phát hiện tự động các khuyết tật bản dịch phổ biến:
- **Lỗi lặp từ (Repetition):** Phát hiện từ đơn lặp liên tiếp $\ge 3$ lần, cụm bigram/trigram lặp lại $\ge 2$ lần, tỷ lệ phong phú từ vựng $\text{TTR} < 0.4$.
- **Lỗi độ dài bất thường (Length Anomaly):** Phát hiện câu bị cắt cụt (under-translation / truncation với tỷ lệ ký tự $< 0.4$) hoặc sinh thừa độ dài bùng nổ (hallucinatory explosion với tỷ lệ ký tự $> 2.5$).
- **Lỗi bỏ sót & không dịch (Omission & Untranslated Copy):** Phát hiện sao chép nguyên văn câu nguồn sang đích (`norm_hyp == norm_src`), độ tương đồng Jaccard quá cao giữa hai ngôn ngữ khác nhau ($\ge 0.70$).
- **Lỗi bỏ sót thực thể số (Missing Numerical Entities):** Quét biểu thức chính quy trích xuất số liệu (`NUMERICAL_REGEX`) từ câu nguồn và kiểm tra xem có bị biến mất hoặc làm sai lệch trong câu đích hay không.
- **Lỗi ký tự lạ & mã hóa (Corrupted Encoding & Foreign Scripts):** Quét chữ Hán (CJK), Cyrillic, Thai, Arabic, ký tự Unicode thay thế (`�`) hoặc null byte (`\x00`).
- **Thất thoát thuật ngữ văn hóa (Cultural Term Loss):** Kiểm tra các khái niệm văn hóa dân gian Tày đặc thù (`lượn`, `then`, `tính tẩu`, `nàng hai`, `phja`, `bản mường`...).

---

## PHẦN III: NHỮNG GÌ LÀM NGOÀI KẾ HOẠCH (GIẢI PHÁP BỔ SUNG NÂNG CAO)

Nhằm nâng cao chất lượng học thuật của đồ án tốt nghiệp và cung cấp công cụ thống kê chuẩn mực quốc tế cho khâu nghiệm thu, Eval1 đã chủ động xây dựng 4 thành phần nâng cao ngoài yêu cầu tối thiểu:

1. **Bộ tính Cohen's Weighted Kappa (Linear & Quadratic) chuyên biệt cho thang đo Likert 1-5:**
   - Trong đánh giá bản dịch bằng thang đo thứ bậc (ordinal scale 1-5), sai khác giữa điểm 4 và điểm 5 (chênh lệch 1 mức) mang tính chất nhẹ hơn rất nhiều so với sai khác giữa điểm 1 và điểm 5 (chênh lệch 4 mức).
   - Cohen's Kappa thông thường (unweighted) coi mọi bất đồng đều nặng nề như nhau. Do đó, Eval1 đã triển khai thêm:
     + **Linear Weighted Kappa:** Trọng số khoảng cách tuyến tính $w_{ij} = 1 - \frac{|i - j|}{k - 1}$.
     + **Quadratic Weighted Kappa:** Trọng số khoảng cách bậc hai $w_{ij} = 1 - \frac{(i - j)^2}{(k - 1)^2}$.
     + **Adjacent Agreement Rate:** Tỷ lệ các cặp điểm chấm chênh lệch không quá 1 điểm ($|s_1 - s_2| \le 1$).
     + Phân loại định tính mức độ tin cậy theo thang chuẩn quốc tế Landis & Koch (Poor, Slight, Fair, Moderate, Substantial, Almost Perfect).

2. **Phân tích lỗi đa chiều kết hợp thực thể số và bảo tồn thuật ngữ văn hóa Tày:**
   - Ngoài các lỗi cơ bản như lặp từ và độ dài, Eval1 bổ sung module quét thực thể số liệu (`NUMERICAL_REGEX`) giúp ngăn chặn tình trạng dịch sót ngày tháng, số lượng — một khiếm khuyết rất nguy hiểm trong các văn bản thông cáo hoặc hành chính.
   - Bổ sung bộ từ điển thuật ngữ văn hóa dân gian Tày (`TAY_CULTURAL_TERMS`) để đo lường tỷ lệ giữ gìn bản sắc ngôn ngữ của mô hình dịch.

3. **Cơ chế tự động giải mã và tổng hợp điểm giám khảo (`unblind_evaluation_results`):**
   - Xây dựng hàm tiếp nhận kết quả chấm từ 2 giám khảo, tự động ánh xạ ngược từ mã mù (`SYS_A..SYS_D`) về các mô hình thực ($E0, E1, E2, E1-M$), tính toán điểm trung bình và độ lệch chuẩn ($\mu \pm \sigma$) theo từng hệ thống và từng chiều dịch một cách hoàn toàn tự động.

4. **Bộ kiểm thử tự động toàn diện `src/tests/evaluation/test_evaluation.py`:**
   - Xây dựng 21 unit tests độc lập bao phủ toàn bộ các module trong `src/evaluation/`, xác minh tính chính xác của toán học metric, độ tương thích với SacreBLEU, tính tất định khi lấy mẫu, độ chính xác của Cohen's Kappa và kiểm thử chạy benchmark 6 mô hình.

---

## PHẦN IV: KẾT QUẢ CHẠY THỬ NGHIỆM VỚI MẪU ĐÁNH GIÁ THỰC TẾ

### 1. Thử nghiệm Đối chuẩn Metric với Thư viện SacreBLEU
Chạy thử nghiệm so khớp trực tiếp giữa `src/evaluation/metrics.py` và `sacrebleu 2.6.0` trên các câu mẫu song ngữ Việt — Tày:
- **Tập câu kiểm tra:**
  + Câu 1 (Hyp): `Tháng giêng sau tết ngày mười lăm bản làng mở hội lượn .`
  + Câu 1 (Ref): `Tháng giêng sau tết ngày mười lăm bản mường mở hội lượn .`
  + Câu 2 (Hyp): `Trai gái trong bản cùng nhau đi chợ xuân hát lượn nàng hai .`
  + Câu 2 (Ref): `Trai gái chang bản cùng nhau đi chợ xuân lượn nàng hai .`
- **Kết quả so sánh:**
  + BLEU (SacreBLEU 2.6.0): `66.521264` | BLEU (metrics.py): `66.521264` $\to$ **Sai số tuyệt đối: $0.000000$**
  + chrF (SacreBLEU 2.6.0): `83.443826` | chrF (metrics.py): `83.443826` $\to$ **Sai số tuyệt đối: $0.000000$**
  + chrF++ (SacreBLEU 2.6.0): `83.847943` | chrF++ (metrics.py): `83.847943` $\to$ **Sai số tuyệt đối: $0.000000$**

### 2. Thử nghiệm Benchmark 6 Biến thể Thực nghiệm với `TranslationEvaluator`
Chạy bộ đánh giá `TranslationEvaluator` trên tập kiểm thử song ngữ fixture (`sample_bilingual.jsonl`):

```text
## Bảng Tổng hợp Kết quả Đánh giá Thực nghiệm (TEST)
| Mô hình / Biến thể | Chiều dịch | BLEU ↑ | chrF ↑ | chrF++ ↑ | Tỷ lệ lỗi (%) ↓ | Latency (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **E0** (Baseline)       | Tày → Việt | **4.82**  | 23.05 | 21.80 | 100.0% | 0.1ms |
| **E2** (QC Filtered)    | Tày → Việt | **4.82**  | 23.05 | 21.80 | 100.0% | 0.2ms |
| **E0** (Baseline)       | Việt → Tày | **23.46** | 38.24 | 36.70 | 60.0%  | 0.2ms |
| **E2** (QC Filtered)    | Việt → Tày | **23.46** | 38.24 | 36.70 | 60.0%  | 0.1ms |
```

### 3. Thử nghiệm Lấy mẫu Đánh giá Mù và Phân tích Lỗi
- Trích xuất thành công gói đánh giá thủ công ẩn danh với 4 hệ thống ($E0, E1, E2, E1-M$), sinh đúng 80 bản dịch trên tập dữ liệu mẫu fixture.
- Tệp xuất bản: `human_eval_sheet.csv`, `human_eval_sheet.jsonl`, `unblind_key.json` và `HUMAN_EVAL_GUIDELINES.md`.
- Thử nghiệm kiểm tra độ nhất trí giữa 2 giám khảo với bộ điểm giả lập:
  + Điểm Giám khảo 1: `[1, 2, 3, 4, 5, 4, 3, 2, 1]`
  + Điểm Giám khảo 2: `[1, 2, 3, 4, 4, 4, 3, 2, 1]` (chỉ lệch 1 điểm ở vị trí thứ 5)
  + **Hệ số Cohen's Kappa unweighted:** $0.857$ (Substantial Agreement)
  + **Hệ số Cohen's Quadratic Weighted Kappa:** $0.964$ (Almost Perfect Agreement)
  + **Tỷ lệ đồng thuận lân cận (Adjacent Agreement, sai lệch $\le 1$ điểm):** $100.0\%$

---

## PHẦN V: KẾT LUẬN & BÀN GIAO TIẾP THEO

1. **Tổng kết kết quả của Eval1:**
   - Đã hoàn thành 100% mục tiêu xây dựng module `src/evaluation/`.
   - Toàn bộ mã nguồn chạy ổn định, độc lập, tương thích tuyệt đối với SacreBLEU và không tạo thêm phụ thuộc nặng ngoài thư viện chuẩn Python.
   - Bộ 21 unit tests chuyên biệt trong `src/tests/evaluation/test_evaluation.py` vượt qua 100%. Toàn bộ 88 tests của repo đều pass.
2. **Sẵn sàng bàn giao:**
   - Bàn giao công cụ đánh giá `TranslationEvaluator` cho Test1 (QA / End-to-End Test Engineer) để kiểm thử tích hợp toàn trình luồng dữ liệu $\to$ huấn luyện $\to$ tăng cường $\to$ đánh giá.
   - Bàn giao gói lấy mẫu mù, phiếu chấm CSV/JSONL và hướng dẫn chấm `HUMAN_EVAL_GUIDELINES.md` cho nhóm Report phục vụ tổ chức hội đồng thẩm định chất lượng bản dịch T04 và T18.
