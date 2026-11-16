# T07 — Thu thập nguồn theo 5 bước, không tạo dữ liệu giả

Ngày ghi nhận: **16/11/2026**. Branch duy nhất: `feat/dataset-weekly`.

> **Trạng thái:** Đã kiểm tra trang nguồn công khai, đã viết code nhập/audit, đã kiểm thử logic bằng fixture. **Chưa tải dữ liệu gốc hoặc crawl live trong môi trường này**, do kết nối tải ngoài không hoạt động. Mọi con số card là *publisher claims*, không phải corpus đã thu thập. Không phê duyệt dữ liệu để train.

## Bước 1 — Kiểm chứng và nhập dataset Hugging Face

Nguồn chính thức: https://huggingface.co/datasets/HeyDunaX/tay-vietnamese-nmt

- Trang dữ liệu hiển thị khoảng **20.600** bản ghi train, **22.849** bản ghi tổng cộng, split `train` và `test`, cấu trúc `translation.tay` / `translation.viet`.
- Card ghi giấy phép `cc-by-nc-4.0`; việc một card tự công bố giấy phép hoặc đã được kiểm duyệt **không chứng minh** quyền và chất lượng mọi bản ghi.
- Chưa xác minh corpus SHA, số bản ghi thực tế, từ nào đúng tiếng Tày/Nùng, hoặc bản dịch đúng. Không coi các dòng trình chiếu trên card là bằng chứng kiểm duyệt.

**Cài đặt (chạy ở máy có Internet, từ root của repo):**

```bash
python3 -m pip install -r requirements-acquisition.txt
python3 src/data_pipeline/import_hf_tay_vi.py \
  --train-output data/raw/hf_tay_vi/train-20261116.jsonl \
  --test-output data/quarantine/hf_tay_vi/upstream-test-20261116.jsonl \
  --manifest data/manifests/t07-hf-import-20261116.json
```

Đổi hậu tố ngày/ID khi chạy lại; công cụ cấm ghi đè. Công cụ truy vấn revision SHA thực tế, **đóng băng** revision khi tải, đọc `train` và `test` thật từ upstream, giữ nguyên văn bản, ghi số dòng/checksum SHA-256 cho từng file. Nếu upstream không có hai split hoặc bản ghi thiếu cột, chương trình báo lỗi; **không tự bịa split, bản dịch hay nguồn**.

`train-*.jsonl` chỉ là **ứng viên song ngữ chưa duyệt**. `upstream-test-*.jsonl` nằm trong quarantine, không dùng huấn luyện. **Không tự thêm corpus này vào `source_registry.json` với `training_approved=true`.**

## Bước 2 — Crawl VOV4 có kiểm soát

Nguồn: https://vov4.vov.vn/taynung

Đã xác định từ web công khai hai bài cụ thể (chỉ discovery URL, chưa tải HTML bằng crawler), ghi vào `data/manifests/t07_source_discovery_2026-11-16.json`.

Dùng crawler **đã có** `src/data_pipeline/crawl_vov4.py`, không tạo crawler trùng:

```bash
python3 src/data_pipeline/crawl_vov4.py \
  --max-pages 10 --delay 2.0 \
  --output data/raw/vov4/articles-20261116.jsonl \
  --errors data/interim/vov4-errors-20261116.jsonl \
  --manifest data/manifests/vov4-crawl-20261116.json
```

Crawler này gọi `robots.txt`, giới hạn delay >= 1 giây, ghi URL và metadata bài; **không vượt robots.txt** nếu bị từ chối hoặc gặp lỗi. Phải kiểm tra điều kiện sử dụng trước khi chia sẻ/huấn luyện corpus. Mục Tày–Nùng không chứng minh từng bài thuộc tiếng Tày; chỉ gán `unverified_tay_nung`. **Không tự tạo cặp dịch Việt tương ứng.** Lần thực thi mới chưa chạy được nên số bài mới = *chưa xác định*, không ghi thành công giả.

## Bước 3 — Phân loại theo provenance

| Đầu vào | Loại | Trạng thái huấn luyện |
| --- | --- | --- |
| Hugging Face train sau khi tải thật | ứng viên song ngữ Tày/Việt, chưa kiểm chứng từng dòng | `training_approved=false` |
| Hugging Face upstream test | holdout công bố, tách hẳn | không được đưa vào train |
| VOV4 Tày–Nùng | đơn ngữ ứng viên; chưa xác minh ngôn ngữ | không tự ghép thành bilingual |
| 421 ứng viên corpus cũ | song ngữ chưa chứng minh nguồn/bản dịch | vẫn chưa duyệt |
| 100 synthetic bị cách ly | nguồn tổng hợp bị từ chối | tiếp tục quarantine |

Mỗi bản ghi HF tải được giữ nguyên chuỗi, gắn `source_id`, `source_url`, `source_revision`, `source_split`, `source_record_number`, bốn trạng thái review và `training_approved=false`. URL dataset-level **không đồng nghĩa** đã có bằng chứng cấp bản ghi.

## Bước 4 — Audit trước khi cân nhắc training

Chạy **sau bước 1 đã tải thành công**:

```bash
python3 src/data_pipeline/audit_external_corpus.py \
  --train data/raw/hf_tay_vi/train-20261116.jsonl \
  --holdout data/quarantine/hf_tay_vi/upstream-test-20261116.jsonl \
  --existing data/raw/glosbe/dictionary_pairs.jsonl \
  --existing data/raw/scripture/tay_scripture.jsonl \
  --existing data/raw/textbook/sgk_tay.jsonl \
  --existing data/raw/jw/tay_jw.jsonl \
  --existing data/raw/local_news/articles.jsonl \
  --existing data/raw/folk_songs/tay_folk_songs.jsonl \
  --existing data/raw/dictionary/tay_vi_dict.jsonl \
  --output data/manifests/t07-hf-overlap-20261116.json
```

Báo cáo sẽ ghi SHA-256 các đầu vào, exact pair overlap, trùng phía Tày/Việt, trùng document ID nếu có, bản ghi bị đánh dấu duyệt sớm hoặc synthetic. **Chưa kiểm tra near-duplicate, đúng ngôn ngữ, đúng nghĩa và quyền sử dụng; zero exact overlap không phải zero leakage toàn diện**. Bước sau (T08/T10) phải tiếp tục kiểm tra này.

Kiểm thử offline bằng fixture do test định nghĩa, không phải câu Tày thực:

```bash
python3 -m unittest src.tests.data_pipeline.test_hf_import src.tests.data_pipeline.test_external_audit -v
```

## Bước 5 — Cập nhật riêng `feat/dataset-weekly`

Trên nhánh này commit **chỉ** code nhập nguồn, code audit, unit tests, danh mục URL công khai và quy trình. Không commit corpus chưa rõ quyền sử dụng; `data/raw/`, `data/quarantine/` và `data/interim/` đã bị Git bỏ qua.

**Chưa sửa:** `source_registry.json`, `inventory.json`, pipeline train hoặc nhánh `feat/translation-pipeline`; khi tải thành công, đối chiếu SHA và kiểm duyệt rồi mới cập nhật registry trong một commit riêng.

### Tiêu chí hoàn thành thực sự

1. Thực thi lệnh tải thành công có revision SHA, số hàng thực tế, output SHA-256.
2. Thực thi VOV4 crawl theo robots và lưu log/manifest (hoặc ghi rõ nguồn không cho crawl).
3. Audit trùng lặp/holdout với raw thật và báo cáo các lỗi; rà soát near-duplicates bổ sung.
4. Dữ liệu nguồn, ngôn ngữ, bản dịch và quyền sử dụng được kiểm tra bằng chứng trước khi cấp `training_approved`.

**T07 hiện chưa hoàn thành.** Không lấy kết quả mock/fixture để tuyên bố corpus đã được xác minh.
