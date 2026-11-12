# T07 — Kiểm kê nguồn và metadata

**Ngày:** 12/11/2026  
**Nhánh dự kiến:** `feat/dataset-weekly`  
**Trạng thái:** đang làm; chỉ xác minh được metadata trong manifest, chưa xác minh bản ghi raw.

## 1. Kết quả từ snapshot đã có

Nguồn: `data/manifests/inventory.json`, `data/manifests/source_registry.json`, `data/manifests/validation_report.json`; snapshot `intake-2026-11-01-v1`.

| Nguồn | File raw | Bản ghi | URL theo registry | Cần bổ sung |
| --- | --- | ---: | ---: | --- |
| VOV4 | `data/raw/vov4/articles.jsonl` | 106 | 106 | Kiểm tra URL từng bài, phân biệt Tày/Nùng, điều kiện sử dụng |
| Glosbe | `data/raw/glosbe/dictionary_pairs.jsonl` | 150 | 0 | URL mục từ/cặp bản dịch, cách trích xuất |
| ScriptureEarth | `data/raw/scripture/tay_scripture.jsonl` | 80 | 0 | Tên tài liệu/ấn bản, vị trí trích dẫn |
| SGK tiếng Tày | `data/raw/textbook/sgk_tay.jsonl` | 22 | 0 | Sách, ấn bản, trang, bằng chứng trích xuất |
| JW.org | `data/raw/jw/tay_jw.jsonl` | 50 | 0 | Bài gốc, phiên bản ngôn ngữ, URL |
| Báo địa phương | `data/raw/local_news/articles.jsonl` | 30 | 0 | URL bài tương ứng hoặc bằng chứng tài liệu |
| Dân ca Tày | `data/raw/folk_songs/tay_folk_songs.jsonl` | 30 | 0 | Tuyển tập, tác giả, trang/vị trí |
| Từ điển | `data/raw/dictionary/tay_vi_dict.jsonl` | 59 | 0 | Xác minh từ điển thật hay dữ liệu template |
| **Tổng** | | **527** | **106** | **421 bản ghi chưa khai báo URL** |

- 527 là **tổng số bản ghi raw được khai báo**, gồm 106 bài VOV4 và 421 ứng viên có hai trường văn bản, không phải 527 cặp dịch đã kiểm duyệt.
- 97 tài liệu VOV4 ứng viên, 174 câu đơn ngữ và 100 bản ghi dịch ngược bị cách ly là **các tầng xử lý khác**, không cộng vào 527.
- `training_approved_records=0` theo inventory; 8 nguồn đều có `training_approved=false` trong registry.
- Bảy nguồn ngoài VOV4 thiếu URL theo registry; thông tin `source_domain` không thay cho URL bản ghi hay bản sao tài liệu có thể đối chiếu.
- Tài liệu `docs/QUY_TRINH_XAY_DUNG_DU_LIEU.md` ghi nhận dấu hiệu trùng danh sách literal ở một số nguồn với script tạo corpus cũ; cần kiểm chứng độc lập trước khi gắn nhãn "thu thập từ web".

## 2. Giới hạn xác minh

Các đường dẫn `data/raw/`, `data/interim/`, `data/quarantine/` được `.gitignore` loại khỏi repository. Không thể tái kiểm đếm raw, so hash, xác nhận sự tồn tại của câu trên trang gốc, độ chính xác Tày–Việt hoặc quyền sử dụng chỉ từ manifest. Không được tự cấp `verified`, `approved` hoặc `confirmed`.

**Danh mục website/nguồn được khai báo** chỉ là đầu mối để xác minh thủ công, không phải bằng chứng từng câu:

- VOV4 chuyên mục Tày–Nùng: <https://vov4.vov.vn/taynung>
- Glosbe: <https://glosbe.com/>
- ScriptureEarth: <https://www.scriptureearth.org/>
- JW.org: <https://www.jw.org/>
- Báo Cao Bằng: <https://baocaobang.vn/>
- Báo Lạng Sơn: <https://baolangson.vn/>

## 3. Công cụ T07 mới

Chạy từ root repo, không cần thư viện ngoài Python chuẩn:

```bash
python3 src/data_pipeline/validate_metadata.py --output data/manifests/t07-metadata-audit-YYYYMMDD.json
python3 -m unittest src.tests.data_pipeline.test_metadata -v
```

Công cụ kiểm tra: snapshot ID, ID và path nguồn, SHA-256 ở inventory/registry, thống kê raw/URL, các trường status và dấu hiệu thiếu bằng chứng. Báo cáo ghi rõ `raw_sources_checked=0` khi không cấp raw. Lệnh chỉ tạo **báo cáo mới, không ghi đè**.

Khi có corpus cục bộ đã đối chiếu:

```bash
python3 src/data_pipeline/validate_metadata.py \
  --raw-dir data/raw \
  --output data/manifests/t07-with-raw-YYYYMMDD.json
```

Lúc đó công cụ mới đọc từng JSONL, kiểm tra số bản ghi, SHA-256 và số URL hợp lệ. Kiểm tra kỹ thuật này **không thay thế** kiểm chứng nội dung hay quyền sử dụng.

## 4. Việc còn lại để hoàn tất T07

1. Có 8 file raw nguyên bản và kiểm tra hash với snapshot.
2. Thu thập bằng chứng cấp bản ghi: URL thực tế hoặc tên tài liệu/ấn bản/trang/vị trí; phân loại `crawl`, `manual`, `template`, `synthetic`, hoặc `unknown` dựa trên chứng cứ.
3. Cập nhật metadata/registry có kiểm soát với tài liệu chứng minh; không thay đổi trạng thái phê duyệt nếu thiếu kiểm duyệt.
4. Phân loại nguồn đủ hồ sơ để chuyển sang T08 và nguồn phải giữ chờ kiểm tra.

**Không đánh dấu T07 hoàn thành chỉ vì code và báo cáo đã được tạo.**