# IE501 — Đồ án tốt nghiệp

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

### Pipeline dữ liệu

Đã có pipeline dữ liệu dùng thư viện chuẩn Python >= 3.10, kiểm tra trên Python 3.12.3. Chạy từ thư mục gốc:

```bash
python3 -m unittest discover -s src/tests/data_pipeline -t . -p 'test_*.py'
```

Đã chạy lại luồng VOV4 106 bài → 97 ứng viên tài liệu → 174 câu đơn ngữ và đối chiếu khớp byte. Các bước xử lý, lệnh chạy lại và điều kiện đưa dữ liệu vào `processed/` nằm trong [hướng dẫn dữ liệu](docs/QUY_TRINH_XAY_DUNG_DU_LIEU.md). Chưa có dữ liệu được duyệt để huấn luyện và chưa có checkpoint mô hình thật. Backend và giao diện demo mức mock đã review đạt với bằng chứng kiểm thử và ảnh bàn giao. Chưa tích hợp mô hình ML thật (T11/T12/T16/T17).

### Web Demo (Mock MVP — Tích hợp Backend & Giao diện Người dùng)

Ứng dụng web phục vụ dịch máy hai chiều Việt - Tày và thử nghiệm giọng nói tiếng Việt với engine giả lập (Mock), tuân thủ đặc tả [SPECS_WEB_DEMO.md](docs/SPECS_WEB_DEMO.md) và hợp đồng [ARCHITECTURE.md](ARCHITECTURE.md). Giao diện người dùng chạy cùng origin với backend, phục vụ tĩnh không phụ thuộc CDN bên ngoài.

**Trạng thái review ngày 06/11/2026: Đạt phạm vi demo mock.** Codex đã đối chiếu mã, log kiểm thử và mở kiểm tra ảnh mobile/giọng nói; các phát hiện C01–C24 đã được xử lý. Kết quả chi tiết, bằng chứng 97 unit, 14 HTTP, 151 backend, 23 pipeline, 20 hồi quy PNG và 9 hành trình browser nằm trong [báo cáo nhóm](.agents/reports/web-demo.md). Chưa kiểm chứng cài mới trong môi trường sạch hoặc nghiệm thu tích hợp mô hình thật.

**Adapter/checkpoint làm sau khi nhánh `feat/translation-pipeline` hoàn tất**, theo [quyết định điều phối](PROJECT_CONTEXT.md#thứ-tự-tích-hợp-mô-hình-vào-web--06112026). Hiện dùng cấu hình mock để chạy demo.

> **Lưu ý nghiên cứu:** Ứng dụng hiện chạy hoàn toàn ở chế độ mô phỏng (Mock MVP), phục vụ kiểm chứng luồng tương tác, độ an toàn giao tiếp và trải nghiệm người dùng; **chưa tích hợp checkpoint mô hình ML thật** (không yêu cầu GPU, PyTorch, Transformers hay Whisper); **chưa xác minh micro vật lý hoặc nhận dạng ASR thật trên tiếng Việt** (nhận dạng giọng nói tiếng Tày nằm ngoài khả năng và phạm vi đề tài, hệ thống không hỗ trợ).

#### 1. Yêu cầu môi trường
- Python >= 3.11 (đã kiểm chứng trên Python 3.12.3)
- Node.js >= 18 (đã kiểm chứng trên Node v24.21.0)

#### 2. Cài đặt và khởi chạy máy chủ
```bash
# Thiết lập môi trường Python
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-web-dev.txt
python -m pip check

# Khởi chạy máy chủ Web Demo (phục vụ cả API và giao diện tại http://127.0.0.1:8000)
export TRANSLATION_ENGINE_TYPE=mock
export ASR_ENGINE_TYPE=mock
python -m uvicorn src.web_app.main:app --host 127.0.0.1 --port 8000
```

#### 3. Sử dụng ứng dụng trên trình duyệt
Mở trình duyệt và truy cập: **`http://127.0.0.1:8000/`**

- **Tab Văn bản (Dịch hai chiều):**
  - Hỗ trợ hai chiều dịch: **Tiếng Việt → Tiếng Tày** (`vi-tay`) và **Tiếng Tày → Tiếng Việt** (`tay-vi`).
  - Phím tắt: nhấn `Ctrl+Enter` (hoặc `Cmd+Enter`) trong ô nhập liệu để dịch nhanh.
  - Chuẩn hóa ký tự: Tự động chuẩn hóa Unicode NFC và cắt tỉa 25 ký tự khoảng trắng theo chuẩn `White_Space`. Đếm ký tự chính xác theo Unicode code points (bao gồm cả ký tự ngoài BMP và emoji).
  - Nút Đảo chiều (Swap): Hoán đổi an toàn hai ô văn bản khi kết quả khớp snapshot nguồn; dọn sạch metadata và thời gian xử lý của chiều cũ; không tự ý kích hoạt gửi yêu cầu.
  - Nút Sao chép (Copy): Tự động sao chép kết quả vào Clipboard kèm thông báo phản hồi (hoặc hướng dẫn bôi đen sao chép thủ công nếu bị từ chối quyền).
  - Nhãn MÔ PHỎNG: Hiển thị nhãn mô phỏng và thông số độ trễ suy luận, thời gian hàng đợi khi chạy mock engine.

- **Tab Giọng nói (Thử nghiệm ASR tiếng Việt & Dịch tiếng Tày):**
  - Hỗ trợ 2 chế độ: **Thu âm trực tiếp** qua micro và **Tải lên tệp WAV**.
  - Quy chuẩn tệp âm thanh: Tệp WAV PCM signed 16-bit, tần số lấy mẫu 16.000 Hz, 1 kênh mono, thời lượng tối đa 30 giây, dung lượng tối đa 10 MiB.
  - Luồng tương tác có kiểm soát: Nhận dạng âm thanh qua ASR → Văn bản nhận dạng xuất hiện trong ô Transcript → **Người dùng tự do chỉnh sửa** → Bấm nút "Dịch sang tiếng Tày (vi-tay)" để dịch bản ghi đã chỉnh sửa. Ứng dụng **tuyệt đối không tự động dịch** sau ASR nhằm bảo đảm người dùng luôn kiểm duyệt được nội dung. Nút Dịch chỉ được bật khi có kết quả ASR thành công từ âm thanh hiện hành.
  - Yêu cầu ngữ cảnh bảo mật: Ghi âm micro yêu cầu kết nối bảo mật (`https://` hoặc `localhost` / `127.0.0.1`). Trên kết nối HTTP mạng nội bộ LAN, giao diện sẽ hướng dẫn người dùng chuyển sang tải lên tệp WAV.

#### 4. Chạy kiểm thử tự động
Hệ thống cung cấp các bộ kiểm thử tách bạch theo từng tầng công nghệ:

```bash
# 1. Bộ kiểm thử backend web Python (core, audio, runner, API, hồi quy C05-C15)
python -m pytest src/tests/web_app/ -v --tb=short

# 2. Bộ kiểm thử pipeline dữ liệu thư viện chuẩn Python stdlib
python3 -S -m unittest discover -s src/tests/data_pipeline -t . -p 'test_*.py'

# 3. Bộ kiểm thử đơn vị frontend UI (audio PCM, phiên thu âm, text_utils, API client, translation, voice)
npm run test:unit --prefix src/web_app/ui

# 4. Bộ kiểm thử tích hợp HTTP (static, REST API mock, upload WAV trên cổng test riêng)
npm run test:http --prefix src/web_app/ui

# 5. Kiểm thử trình duyệt nhúng Orca (cần Orca đang chạy và CLI orca-ide; ảnh lưu tại docs/screenshots/)
npm run test:browser --prefix src/web_app/ui

# 6. Hồi quy helper PNG và kiểm chứng 9 ảnh browser hiện hành
node --test scripts/screenshot_png.test.mjs
```

Các lệnh chạy từ gốc repo sau khi kích hoạt môi trường Python ở bước cài đặt. `npm test --prefix src/web_app/ui` gộp unit và HTTP; không bao gồm browser hoặc hồi quy PNG. Bộ browser tự mở server mock trên cổng riêng và đóng tài nguyên sau khi chạy; ảnh bắt buộc thiếu, hỏng hoặc đơn sắc làm bước kiểm thử thất bại. Helper PNG chỉ hỗ trợ RGB/RGBA 8-bit đục, không interlace; vẫn cần mở ảnh để đối chiếu nội dung UI.

#### 5. Các endpoint API khả dụng (§4)
- `GET http://127.0.0.1:8000/`: Phục vụ giao diện người dùng `index.html`.
- `GET http://127.0.0.1:8000/api/health`: Trạng thái sẵn sàng của hệ thống, metadata engine và các hạn mức vận hành.
- `GET http://127.0.0.1:8000/api/models`: Danh mục bundle mô hình đang phục vụ.
- `POST http://127.0.0.1:8000/api/translate`: Suy luận dịch văn bản hai chiều (`vi-tay` và `tay-vi`).
- `POST http://127.0.0.1:8000/api/asr/transcribe`: Nhận dạng giọng nói tiếng Việt từ tệp WAV PCM 16kHz mono.

Xem [kiểm kê dữ liệu](data/manifests/inventory.json), [danh mục nguồn](data/manifests/source_registry.json) và [kết quả kiểm tra](data/manifests/validation_report.json). Dữ liệu và log hiện lưu cục bộ, được `.gitignore` loại khỏi Git trong khi xác minh nguồn và điều kiện sử dụng; bản clone chỉ có manifest sẽ không tự có corpus. Các số lượng chi tiết và việc còn lại được quản lý tại [TASKS.md](TASKS.md).

## Tài liệu tham khảo

- [Đề cương chi tiết đồ án](docs/DeCuongDATN_25410304_25410313.pdf)
- [Bản Markdown để chỉnh đề cương](docs/DeCuongDATN_25410304_25410313.md)
- [Các mục đã sửa và hướng dẫn xuất PDF](docs/REVIEW_DE_CUONG.md)
- [Danh sách GVHD và thông tin](reference/Danh%20sách%20GVHD%20và%20thông%20tin.md)
