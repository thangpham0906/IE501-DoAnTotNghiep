# Đặc tả kỹ thuật và kế hoạch triển khai web demo

**Nhánh:** `feat/web-demo` · **Mã việc:** T05, T19, T20, T21, T22 · **Cập nhật:** 06/11/2026.

**Trạng thái: Đã review đạt phạm vi backend, giao diện và luồng giọng nói với engine mock ngày 06/11/2026.** Đã có mã tại `src/web_app/` cùng các bộ kiểm thử unit, HTTP, trình duyệt Orca và hồi quy helper PNG; Codex đã đối chiếu mã/log, mở ảnh mobile/giọng nói và đóng các phát hiện C01–C24. Xem bằng chứng và việc còn lại tại [báo cáo web-demo](../.agents/reports/web-demo.md), lệnh tái hiện tại [README](../README.md#4-chạy-kiểm-thử-tự-động). Chưa tích hợp checkpoint ML thật, chưa xác minh micro vật lý, ASR thật tiếng Việt hoặc cài mới trong môi trường sạch; hệ thống không hỗ trợ nhận dạng tiếng Tày. Kết quả mock chỉ kiểm chứng luồng tương tác và giao tiếp trong phạm vi đã thử, chưa đóng nghiệm thu các Txx toàn dự án.

Phạm vi và D01–D04 theo [PROJECT_CONTEXT.md](../PROJECT_CONTEXT.md); nghiệm thu theo [PROJECT_REQUIREMENTS.md](../PROJECT_REQUIREMENTS.md); phụ thuộc và lịch theo [TASKS.md](../TASKS.md). Giao tiếp liên nhóm được ghi tại [ARCHITECTURE.md](../ARCHITECTURE.md#ứng-dụng-minh-họa). Bằng chứng triển khai/review cập nhật trong [báo cáo web-demo](../.agents/reports/web-demo.md).

**Việc để sau:** Theo [quyết định ngày 06/11/2026](../PROJECT_CONTEXT.md#thứ-tự-tích-hợp-mô-hình-vào-web--06112026), chỉ tiếp tục phần adapter/checkpoint sau khi nhánh `feat/translation-pipeline` hoàn tất và có đầu ra bàn giao đủ điều kiện. Đợt hiện tại chốt phạm vi mock.

**Bắt đầu triển khai:** xem [§8.4 — Thứ tự thực hiện và đợt đầu tiên](#84-thứ-tự-thực-hiện-và-đợt-đầu-tiên). Đoạn giao việc có thể đưa cho Claude Code nằm tại [§8.5](#85-nội-dung-giao-việc-cho-claude-code). Tiến độ thực tế vẫn ghi trong báo cáo nhóm; các mục này không phải xác nhận đã triển khai.

## 1. Phạm vi và nguyên tắc

1. **Web phục vụ minh họa nghiên cứu.** Dịch văn bản Việt ↔ Tày; thử nghiệm âm thanh Việt → transcript Việt → người dùng rà soát → dịch Tày. Không bổ sung TTS hoặc hội thoại thời gian thực.
2. **Tách phụ thuộc web và suy luận.** Mock chạy được trên CPU, không import PyTorch/Transformers/Whisper. Engine thật gọi adapter suy luận dùng chung với pipeline đánh giá; web không tự triển khai một luồng tokenization/generation khác.
3. **Phân biệt mô phỏng và kết quả thật.** Mặc định hai engine là mock. Mỗi kết quả và trạng thái engine có `is_mock`, `engine_type` và định danh riêng; UI luôn gắn nhãn cho kết quả mô phỏng. Lỗi nạp engine thật không được tự chuyển sang mock.
4. **Chỉ công bố khả năng đã kiểm chứng.** Mô hình, token Tày, cách tổ chức hai chiều và phương pháp fine-tune vẫn phụ thuộc D01. Phạm vi ASR thật vẫn cần bằng chứng T05/D04; ứng dụng không công bố hỗ trợ nhận dạng tiếng Tày. Việc sửa đặc tả không đóng D01/D04 hoặc thay thế xác nhận của GVHD.
5. **Giới hạn tài nguyên có thể kiểm tra.** Dùng hàng đợi hữu hạn và worker quản lý vòng đời công việc. Hết thời gian chờ HTTP không đồng nghĩa tính toán nền đã dừng; không nhả suất tính toán khi worker còn chạy.
6. **Dữ liệu và metric có nguồn.** Fixture ghi rõ cách tạo; bản dịch tham chiếu cần người duyệt. Metric chưa có dùng `null`, không điền điểm mặc định hoặc suy ra thông tin checkpoint từ tên thư mục.

Phương án web đề xuất dùng FastAPI với HTML/CSS/Vanilla JavaScript đóng gói nội bộ để giảm công cụ build. Việc thay React dự kiến trong đề cương được ghi tại `PROJECT_CONTEXT.md`; đây là phương án triển khai, chưa phải xác nhận GVHD đã duyệt. Các giới hạn số trong tài liệu là cấu hình khởi đầu để kiểm thử, sẽ điều chỉnh theo tài nguyên đo được.

## 2. Kiến trúc và tổ chức mã nguồn dự kiến

Mọi đường dẫn dưới đây tính từ gốc repo. Chỉ tạo thư mục/file khi bắt đầu phần việc tương ứng.

```text
requirements-web.txt                   # Runtime web
requirements-web-dev.txt               # Kế thừa web, bổ sung kiểm thử
requirements-web-ml.txt                # Kế thừa web, thêm runtime mô hình đã chốt
.env.example                          # Cấu hình mẫu, không chứa bí mật
src/web_app/
├── main.py                           # Lifespan, router /api, static UI
├── core/
│   ├── config.py                     # Pydantic Settings, kiểm tra cấu hình
│   ├── schemas.py                    # Schema request/response và metadata
│   ├── language.py                   # Ánh xạ direction → mã API
│   ├── exceptions.py                 # Lỗi nghiệp vụ, không phụ thuộc HTTP
│   └── logging.py                    # Request ID, trạng thái, timing
├── services/
│   ├── inference_runner.py           # Hàng đợi hữu hạn, worker, deadline
│   ├── translation/
│   │   ├── base.py                   # InferenceEngine, TranslationResult
│   │   ├── mock_engine.py
│   │   ├── pipeline_engine.py        # Gọi adapter do pipeline cung cấp
│   │   └── factory.py
│   └── asr/
│       ├── base.py                   # ASREngine, AudioInput, ASRResult
│       ├── audio.py                  # Đọc WAV có giới hạn và kiểm tra PCM
│       ├── mock_asr.py
│       ├── whisper_engine.py
│       └── factory.py
├── api/
│   ├── dependencies.py               # Engine/runner từ trạng thái ứng dụng
│   ├── middleware.py                 # Giới hạn body, request ID, timing
│   ├── error_handlers.py
│   └── routes/                       # health.py, models.py, translate.py, asr.py
└── ui/
    ├── index.html
    ├── css/app.css
    └── js/                           # app.js, translation.js, voice.js, api_client.js
src/tests/
├── fixtures/audio/                   # Manifest/mẫu nhỏ có quyền chia sẻ nếu đã có
├── web_app/                          # Schema, engine giả, API, runner và lỗi
└── web_app_integration/              # Kiểm tra bằng checkpoint/ASR thật
```

Các package Python có `__init__.py` phù hợp. Test có thể sinh WAV trong bộ nhớ để kiểm tra parser; mẫu âm thanh có lời nói phục vụ T05 là tập riêng, có manifest và trạng thái duyệt. Không tạo mẫu tham chiếu giả để lấp chỗ trống.

### 2.1 Phụ thuộc và cấu hình

Môi trường web dự kiến **Python >= 3.11**, ưu tiên kiểm chứng trên Python 3.12; yêu cầu này riêng với web, không đổi mức Python >= 3.10 hiện có của pipeline dữ liệu. Khi triển khai, ghi phiên bản đã thử và cố định bộ phụ thuộc tương thích; đợt sửa tài liệu này chưa cài hoặc khóa phiên bản thư viện.

| File | Nội dung cần khai báo |
| --- | --- |
| `requirements-web.txt` | `fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`, `python-multipart`; khai báo thêm thư viện nếu mã web import trực tiếp |
| `requirements-web-dev.txt` | Dòng `-r requirements-web.txt`, `pytest`, `httpx`; thêm plugin async nếu bộ test thực tế cần |
| `requirements-web-ml.txt` | Dòng `-r requirements-web.txt`; runtime adapter pipeline theo D01 và runtime ASR. Nếu chọn PyTorch/Transformers: khai báo `torch`, `transformers` và các phụ thuộc tokenizer/adapter thực dùng. Với Whisper: `openai-whisper`, `numpy` và phiên bản tương thích |

Không cài môi trường ML để chạy test mock. Import thư viện ML chỉ xảy ra trong nhánh nạp engine thật. Các test tích hợp thật được tách khỏi bộ test mặc định và không được tự tải checkpoint.

Cấu hình lấy từ biến môi trường → `.env` tại gốc repo → mặc định trong `WebSettings`. Dùng `pydantic-settings`, kiểm tra enum; sức chứa, kích thước và deadline phải dương, riêng `MOCK_DELAY_MS` cho phép 0. Đường dẫn tương đối resolve theo gốc repo đã xác định từ vị trí mã nguồn, không phụ thuộc thư mục gọi lệnh. Bản đầu không dùng thêm `configs/web_config.json` để tránh hai nguồn mặc định lệch nhau.

## 3. Giao diện engine và dữ liệu nội bộ

### 3.1 Ngôn ngữ và chiều dịch

| `direction` | `source_lang` | `target_lang` |
| --- | --- | --- |
| `vi-tay` | `vi` | `tyz` |
| `tay-vi` | `tyz` | `vi` |

Các mã trên là quy ước API. Token nguồn/đích của mô hình do manifest pipeline cung cấp; không mặc định `tyz_Latn` là token hợp lệ. Nếu D01 chọn NLLB, adapter phải kiểm tra token thực sự có trong tokenizer, ID không phải unknown và khớp embeddings/checkpoint; không tự thêm token khi phục vụ request.

Một **bundle đang phục vụ** có thể chứa một mô hình hai chiều hoặc hai mô hình theo chiều. `model_id` ở API chỉ bundle, không buộc số checkpoint là một. `supported_directions` được suy ra từ các route đã nạp và kiểm chứng; chỉ bật các chiều đó. Mục tiêu nghiệm thu F08 vẫn là đủ hai chiều; chạy được một chiều chỉ là kết quả một phần.

### 3.2 Hợp đồng `InferenceEngine`

Đây là giao diện web đề xuất để phối hợp tại T06/T11/T19, cần xác nhận cùng pipeline trước khi hiện thực adapter thật.

| Phương thức | Hành vi |
| --- | --- |
| `load(bundle_path=None)` | Mock dùng fixture nội bộ; engine thật đọc manifest, kiểm tra artifact, gọi loader dùng chung của pipeline |
| `is_ready()` | Trả trạng thái nạp và kiểm tra thành công, không suy từ việc đường dẫn tồn tại |
| `get_supported_directions()` | Danh sách chiều thật sự phục vụ được |
| `translate(text, direction)` | Nhận chuỗi đã chuẩn hóa theo §4.3; trả `TranslationResult`, hoặc lỗi nghiệp vụ chuẩn |
| `get_metadata()` | Trả bundle/version, các artifact theo chiều, loại engine, nhãn mock và metric có nguồn hoặc `null` |
| `unload()` | Chỉ giải phóng tài nguyên sau khi các worker đang dùng engine đã dừng |

`TranslationResult` chứa `translation`, `direction`, `source_lang`, `target_lang`, `model_metadata`. Metadata của kết quả bắt buộc có `model_id`, `artifact_id`, `checkpoint_version`, `tokenizer_version`, `engine_type`, `is_mock`. Không đưa đường dẫn máy chủ vào phản hồi.

Engine thật kiểm tra số token sau tokenization bằng giới hạn từ manifest, tính cả token đặc biệt theo quy ước pipeline; từ chối khi vượt giới hạn, không âm thầm cắt văn bản. Giải mã dùng cấu hình bàn giao, có giới hạn token đầu ra và quy tắc kết thúc. Nếu đầu ra bị cắt do chạm giới hạn mà chưa hoàn tất, trả lỗi rõ ràng; không trình bày thành bản dịch hoàn chỉnh. Không cho client ghi đè cấu hình giải mã trong phiên bản đầu.

Kết quả suy luận web phải được đối chiếu với adapter đánh giá trên cùng mẫu và cấu hình. Khi chia sẻ tokenizer có trạng thái theo ngôn ngữ, dùng khóa hoặc instance độc lập; không đổi token nguồn/đích của request khác. Mặc định worker đơn không thay thế kiểm thử này nếu sau đó tăng concurrency.

### 3.3 Hợp đồng `ASREngine`

| Phương thức | Hành vi |
| --- | --- |
| `load(model_path=None)` | Nạp engine đã cấu hình; Whisper thật dùng weights cục bộ đã đối chiếu checksum |
| `is_ready()` | Xác nhận engine sẵn sàng, tách biệt với engine dịch |
| `get_metadata()` | Trả `model_id`, `model_version`, `engine_type`, `is_mock` |
| `transcribe(audio, language="vi")` | Nhận `AudioInput` đã kiểm tra, chỉ cho `vi`; trả `ASRResult` |
| `unload()` | Chờ worker ASR kết thúc trước khi giải phóng model |

`AudioInput` chứa PCM signed 16-bit little-endian, sample rate 16.000 Hz, một kênh, số frame và thời lượng đã kiểm tra; không truyền thẳng `BytesIO` chứa cả file WAV cho Whisper. `ASRResult` có `transcript`, `language`, `duration_sec`, `model_metadata`.

Adapter Whisper chuyển PCM sang waveform float32 đúng biên độ và gọi nhận dạng với `language="vi"`, `task="transcribe"`; không dùng chế độ dịch sang tiếng Anh. Luồng WAV PCM này tự đọc bằng `wave` và truyền waveform, không gọi decoder `ffmpeg`. Việc cài runtime Whisper phải được thử trong môi trường thật; hỗ trợ file nén/đọc bằng đường dẫn qua `ffmpeg` là phần mở rộng sau, không thuộc API phiên bản đầu.

Khi engine xác định không có lời nói hoặc transcript rỗng, trả `NO_SPEECH_DETECTED`, không chuyển transcript rỗng sang dịch. Không giả định model luôn phát hiện đúng im lặng/tiếng ồn; T05 phải ghi nhận cả trường hợp sinh transcript sai trên các mẫu này. Đánh giá nhận dạng vẫn cần âm thanh có lời nói và transcript đã rà soát; parser WAV không xác minh ngôn ngữ người nói.

### 3.4 Mock và vòng đời

- `MockTranslationEngine` trả kết quả xác định được, luôn có tiền tố `[MOCK vi->tyz]` hoặc `[MOCK tyz->vi]`, kể cả khi khớp fixture. `model_id="mock-demo"`, metric `null`. Fixture có nhãn cách tạo; chỉ gọi là tham chiếu đã duyệt khi có bằng chứng.
- `MockASREngine` đọc WAV hợp lệ và trả transcript mẫu có tiền tố `[MOCK ASR]`, metadata `is_mock=true`. Mock không nhận dạng nội dung file hoặc chứng minh WER. Test trường hợp im lặng/lỗi dùng fake engine có hành vi được chỉ định.
- Độ trễ mock mặc định bằng 0. Khi cần minh họa loading hoặc thử concurrency, cấu hình delay riêng trong test; không dùng độ trễ ngẫu nhiên khiến test thiếu ổn định.
- Lifespan tạo runner và quản lý công việc nạp engine ngoài event loop. Công việc khởi tạo được supervisor giữ tham chiếu; health có thể công bố `loading` khi ứng dụng đã nhận request. Chuyển sang `ready` chỉ sau kiểm tra đầy đủ.
- Engine có trạng thái `loading`, `ready`, `failed`, `disabled` hoặc `stopping`. ASR được phép disabled; dịch văn bản vẫn có thể hoạt động khi ASR lỗi. Cấu hình sai kiểu/giới hạn làm khởi động thất bại; lỗi thiếu hoặc sai artifact làm engine tương ứng `failed`, API phụ thuộc trả 503. Không fallback sang mock.

## 4. API và cấu hình vận hành

### 4.1 Các giá trị khởi đầu

Các giá trị dưới đây phục vụ xây dựng và thử nghiệm ban đầu; không phải ngưỡng hiệu năng đã đo. UI lấy giới hạn từ health; backend là nơi quyết định đầu vào hợp lệ.

| Biến cấu hình | Mặc định / quy tắc |
| --- | --- |
| `TRANSLATION_ENGINE_TYPE` | `mock`; enum `mock`, `pipeline` |
| `MODEL_BUNDLE_PATH` | Không có; bắt buộc khi chọn `pipeline` |
| `MODEL_DEVICE` | `cpu`; `cuda` chỉ dùng khi đã kiểm tra phần cứng/runtime, không tự đổi thiết bị khi lỗi |
| `ASR_ENGINE_TYPE` | `mock`; enum `mock`, `whisper`, `disabled` |
| `WHISPER_MODEL_PATH` | Không có; bắt buộc là weights cục bộ khi chọn `whisper` |
| `ASR_DEVICE` | `cpu`; cấu hình riêng với dịch |
| `MAX_TEXT_LENGTH` | 1.000 Unicode code point sau chuẩn hóa |
| `MAX_JSON_BODY_BYTES` | 65.536 byte, tính trên body thực nhận |
| `MAX_AUDIO_FILE_BYTES` | 10.485.760 byte (10 MiB) |
| `MAX_MULTIPART_BODY_BYTES` | 11.534.336 byte (11 MiB), gồm file và overhead form; phải lớn hơn giới hạn file |
| `MAX_AUDIO_DURATION_SEC` | 30 giây; dữ liệu PCM thực tế cũng phải nằm trong giới hạn |
| `INFERENCE_WORKERS` | 1 worker xử lý chung công việc dịch/ASR; tăng sau đo tài nguyên và kiểm thử thread safety |
| `MAX_QUEUED_INFERENCES` | 8 công việc chờ, không tính worker đang chạy |
| `QUEUE_TIMEOUT_SEC` | 5 giây chờ được bắt đầu |
| `TRANSLATION_TIMEOUT_SEC` | 15 giây từ lúc bắt đầu suy luận tới deadline phản hồi |
| `ASR_TIMEOUT_SEC` | 20 giây từ lúc bắt đầu ASR tới deadline phản hồi |
| `SHUTDOWN_GRACE_SEC` | 30 giây chờ công việc đang chạy khi dừng dịch vụ |
| `MOCK_DELAY_MS` | 0; chỉ dùng chế độ mô phỏng/kiểm thử |

Bản đầu chạy một process Uvicorn, không dùng nhiều worker máy chủ để nhân bản model và hạn mức ngầm trên cùng GPU. Host/port truyền trực tiếp bằng tham số Uvicorn. Các giới hạn token và cấu hình giải mã thuộc bundle pipeline (§7), không dùng số ký tự thay cho số token.

### 4.2 Mã lỗi và cấu trúc chung

Mọi lỗi API do ứng dụng kiểm soát có HTTP status đúng bảng và body `ErrorResponse`. `request_id` xuất hiện trong body lỗi và header `X-Request-ID` của mọi phản hồi API; log sử dụng cùng ID. Không ghi toàn bộ văn bản/âm thanh của người dùng vào log mặc định.

| `error_code` | HTTP | Điều kiện |
| --- | --- | --- |
| `INVALID_INPUT` | 400 | JSON/form sai cấu trúc, thiếu trường, sai kiểu, trường lạ, văn bản rỗng sau chuẩn hóa |
| `UNSUPPORTED_DIRECTION` | 400 | Chiều không thuộc quy ước hoặc không có trong bundle sẵn sàng |
| `INPUT_TOO_LONG` | 400 | Vượt số ký tự hoặc số token; `detail.limit_unit` phân biệt `code_points`/`tokens` |
| `REQUEST_TOO_LARGE` | 413 | Vượt giới hạn toàn body JSON hoặc multipart |
| `AUDIO_TOO_LARGE` | 413 | File vượt giới hạn byte riêng dù body vẫn trong hạn mức |
| `AUDIO_TOO_LONG` | 400 | Thời lượng PCM vượt giới hạn |
| `AUDIO_UNSUPPORTED_FORMAT` | 400 | Không phải WAV PCM theo §5.3 hoặc sample rate/số kênh/bit depth không hỗ trợ |
| `AUDIO_INVALID` | 400 | WAV rỗng, hỏng, thiếu frame hoặc header không khớp dữ liệu |
| `UNSUPPORTED_ASR_LANGUAGE` | 400 | `language` khác `vi` |
| `NO_SPEECH_DETECTED` | 400 | ASR không tìm được lời nói/transcript có nội dung |
| `MODEL_NOT_FOUND` | 404 | `model_id` khác bundle đang phục vụ |
| `MODEL_NOT_READY` | 503 | Engine cần dùng đang loading/failed/stopping hoặc ASR disabled |
| `SERVICE_OVERLOADED` | 503 | Hàng đợi đã đủ số chỗ, không nhận thêm job |
| `INFERENCE_TIMEOUT` | 504 | Quá hạn chờ hoặc chạy; `detail.phase` là `queue`/`execution` |
| `OUTPUT_TOO_LONG` | 500 | Engine dịch chạm giới hạn đầu ra trước khi hoàn tất |
| `INFERENCE_FAILED` | 500 | Suy luận dịch lỗi, gồm lỗi tài nguyên; không lộ stack trace |
| `ASR_FAILURE` | 500 | ASR lỗi sau khi audio đã qua validation |
| `NOT_FOUND` / `METHOD_NOT_ALLOWED` | 404 / 405 | Đường dẫn API/phương thức không tồn tại |
| `INTERNAL_ERROR` | 500 | Lỗi bất ngờ còn lại; trả thông báo an toàn, ghi chi tiết trong log |

Ví dụ lỗi, các con số chỉ minh họa kiểm tra độ dài:

```json
{
  "status": "error",
  "error_code": "INPUT_TOO_LONG",
  "message": "Văn bản vượt quá giới hạn cho phép.",
  "detail": {
    "current_length": 1001,
    "max_allowed": 1000,
    "limit_unit": "code_points"
  },
  "request_id": "example-request"
}
```

`detail` là object hoặc `null`. Cần handler cho `RequestValidationError`, HTTP exceptions của Starlette/FastAPI, domain exceptions và lỗi bất ngờ; không chỉ đổi HTTP 422 thành 400. Nếu dùng `HTTPException`, handler phải chuyển về schema trên. Middleware giới hạn body cũng trả cùng schema khi còn có thể gửi phản hồi.

Thứ tự kiểm tra: giới hạn body → cấu trúc/kiểu/chuẩn hóa → ngôn ngữ/độ dài hoặc WAV hợp lệ → engine sẵn sàng → chiều được hỗ trợ/`model_id` → admission vào runner. Giới hạn token được kiểm tra trong worker trước generation. Với nhiều lỗi schema, ưu tiên lỗi thiếu/sai kiểu là `INVALID_INPUT`; các trường `direction`/`language` có kiểu chuỗi nhưng giá trị sai dùng mã chuyên biệt. Quy tắc này phải có test để UI không phụ thuộc thứ tự validator ngẫu nhiên.

### 4.3 `POST /api/translate`

Request là JSON, không cho trường ngoài hợp đồng:

```json
{
  "text": "Hôm nay bà con cùng nhau lên nương.",
  "direction": "vi-tay",
  "model_id": "mock-demo"
}
```

- `text`: string bắt buộc; chuẩn hóa Unicode NFC rồi bỏ khoảng trắng ở hai đầu, giữ nguyên khoảng trắng bên trong.
- Phép trim dùng chung tập ký tự: U+0009–000D, U+0020, U+0085, U+00A0, U+1680, U+2000–200A, U+2028–2029, U+202F, U+205F, U+3000. Backend và frontend dùng cùng fixture; không giả định `strip()` và `trim()` mặc định luôn tương đương.
- Độ dài hợp lệ từ 1 tới `MAX_TEXT_LENGTH`, đếm Unicode code point sau chuẩn hóa. Python dùng `len()` trên chuỗi chuẩn hóa; JavaScript dùng `Array.from(normalizedText).length`. Kiểm tra thêm giới hạn token ở engine thật; không cắt hoặc tự chia đoạn âm thầm.
- `direction`: string bắt buộc theo §3.1 và khả năng engine. `model_id`: có thể bỏ hoặc `null` để chọn bundle đang phục vụ; nếu truyền phải là chuỗi không rỗng, khớp bundle đó.

Phản hồi 200 sau đây là **mô phỏng**, thời gian 0 chỉ là giá trị ví dụ, không phải số đo:

```json
{
  "status": "success",
  "translation": "[MOCK vi->tyz] Hôm nay bà con cùng nhau lên nương.",
  "direction": "vi-tay",
  "source_lang": "vi",
  "target_lang": "tyz",
  "model_metadata": {
    "model_id": "mock-demo",
    "artifact_id": "mock-text",
    "checkpoint_version": "mock-v1",
    "tokenizer_version": "mock-v1",
    "engine_type": "mock",
    "is_mock": true
  },
  "latency_ms": 0,
  "queue_ms": 0
}
```

Runner đo `queue_ms` từ lúc nhận job tới khi worker bắt đầu; `latency_ms` từ lúc worker bắt đầu tới kết thúc adapter, gồm tokenization/giải mã. Không tính upload, network hoặc render UI vào hai trường này. Đo thêm tổng thời gian request trong log. Nếu dùng CUDA, cách đo phải chờ kết quả GPU hoàn tất tại ranh giới đo; ghi phương pháp trong báo cáo hiệu năng.

### 4.4 `POST /api/asr/transcribe`

Multipart form gồm đúng một `file` WAV PCM signed 16-bit little-endian, 16.000 Hz mono, không quá giới hạn byte/thời lượng tại §4.1; `language` tùy chọn mặc định `vi`, chỉ chấp nhận `vi`. Từ chối file nén MP3/M4A/OGG trong phiên bản đầu. Tên file/MIME là gợi ý; quyết định dựa vào nội dung đã phân tích.

Phản hồi 200 dưới đây là **mô phỏng**; `duration_sec` phải lấy từ file thực nhận, giá trị 1 ở đây chỉ minh họa schema:

```json
{
  "status": "success",
  "transcript": "[MOCK ASR] Đây là transcript mẫu để kiểm thử giao diện.",
  "language": "vi",
  "duration_sec": 1,
  "model_metadata": {
    "model_id": "mock-asr",
    "model_version": "mock-v1",
    "engine_type": "mock",
    "is_mock": true
  },
  "latency_ms": 0,
  "queue_ms": 0,
  "disclaimer": "Thử nghiệm giọng nói tiếng Việt. Ứng dụng không hỗ trợ nhận dạng tiếng Tày."
}
```

API ASR chỉ trả transcript, không tự gọi dịch. `is_mock` luôn đi kèm kết quả và UI hiển thị rõ, độc lập với loại engine dịch. `latency_ms` gồm chuyển PCM sang waveform và nhận dạng; không gồm đọc upload/validation WAV. Nội dung transcript có thể vượt giới hạn dịch; UI yêu cầu người dùng rút gọn trước bước 2.

### 4.5 `GET /api/health`

HTTP 200 xác nhận ứng dụng trả lời được, không tự chứng minh model thật sẵn sàng. `status`: `ready` khi tất cả engine được bật đã ready; `loading` khi còn engine loading và không có failed/stopping; `degraded` khi có failed/stopping. ASR `disabled` không làm hỏng readiness dịch. UI quyết định từng chức năng bằng trạng thái engine tương ứng.

Ví dụ ứng dụng chạy hai engine mock:

```json
{
  "status": "ready",
  "api_version": "1",
  "translation": {
    "state": "ready",
    "engine_type": "mock",
    "is_mock": true,
    "active_model_id": "mock-demo",
    "supported_directions": ["vi-tay", "tay-vi"]
  },
  "asr": {
    "state": "ready",
    "engine_type": "mock",
    "is_mock": true,
    "model_id": "mock-asr",
    "supported_languages": ["vi"]
  },
  "limits": {
    "max_text_length": 1000,
    "max_audio_file_bytes": 10485760,
    "max_audio_duration_sec": 30,
    "queue_timeout_sec": 5,
    "translation_timeout_sec": 15,
    "asr_timeout_sec": 20,
    "audio_format": "wav_pcm_s16le",
    "audio_sample_rate_hz": 16000,
    "audio_channels": 1
  }
}
```

Khi engine không ready, không công bố chiều/ngôn ngữ đang phục vụ; danh sách tương ứng rỗng và định danh chưa nạp là `null`. `is_mock` phản ánh cấu hình engine; ASR disabled có `engine_type="disabled"`, `is_mock=false`. Thông báo lỗi nạp đầy đủ nằm trong log gắn ID; health không lộ đường dẫn hoặc stack trace. Route này đọc trạng thái trong bộ nhớ, không chờ hàng đợi suy luận hoặc thực hiện warm-up.

### 4.6 `GET /api/models`

Trả tối đa một bundle đang phục vụ; bundle có thể định tuyến tới một hoặc hai checkpoint. Khi engine dịch chưa ready, trả 200 với `models: []`; đọc health để biết lý do. Không có API đổi/nạp model tùy ý từ client trong phiên bản đầu.

Ví dụ bundle mock, không gán tên NLLB hay điểm đánh giá thật:

```json
{
  "models": [
    {
      "id": "mock-demo",
      "name": "Mô phỏng dịch văn bản",
      "bundle_version": "mock-v1",
      "engine_type": "mock",
      "is_mock": true,
      "supported_directions": ["vi-tay", "tay-vi"],
      "is_default": true,
      "metrics": null
    }
  ]
}
```

Với engine thật, `metrics` là `null` hoặc object theo từng chiều, tuân theo §7. Không gộp điểm hai chiều thành một cặp BLEU/chrF không rõ nguồn. Version chính xác của artifact dùng cho mỗi request nằm trong `model_metadata` của kết quả.

## 5. Hàng đợi, vòng đời và kiểm tra âm thanh

### 5.1 Quản lý công việc suy luận

Runner là thành phần sống theo lifespan ứng dụng, sở hữu hàng đợi hữu hạn và worker. Route gửi job rồi chờ kết quả; route không trực tiếp giữ/nhả semaphore quanh `run_in_threadpool`. Chỉ chuyển tác vụ sang threadpool chưa bảo đảm deadline hoặc ngăn cạn RAM/VRAM.

Quy trình bắt buộc:

1. Sau validation nhẹ, admission kiểm tra sức chứa và thêm job trong một thao tác không bị xen ngang trên event loop. Có tối đa `INFERENCE_WORKERS` job chạy và `MAX_QUEUED_INFERENCES` job chờ. Hết chỗ trả 503 `SERVICE_OVERLOADED`, không tạo thêm task chờ semaphore vô hạn.
2. Job chờ có deadline riêng. Nếu hết `QUEUE_TIMEOUT_SEC`, loại khỏi hàng đợi, trả 504 với `phase="queue"`; không được gọi engine cho job đó.
3. Worker lấy job theo FIFO, kiểm tra trạng thái hủy/deadline trước khi gọi engine. Tokenization, kiểm tra số token và suy luận thực hiện trong worker; công việc CPU/GPU blocking được đưa ra ngoài event loop.
4. Thời hạn thực thi bắt đầu khi worker nhận job. Nếu request hết hạn, trả 504 với `phase="execution"`, đánh dấu bên chờ không nhận kết quả nữa. **Worker vẫn chiếm suất chạy đến khi hàm suy luận thực sự kết thúc.** Supervisor giữ tham chiếu tới task/future và thu kết quả hoặc exception kể cả khi HTTP request đã kết thúc.
5. Khi server ghi nhận client ngắt kết nối, job còn chờ được bỏ; job đang chạy tiếp tục được theo dõi như trường hợp timeout. Chỉ worker, không phải route hoặc callback hủy request, được giải phóng suất chạy sau khi công việc hoàn tất.
6. Chia sẻ một runner cho dịch và ASR ở bản đầu để giới hạn tổng công việc, kể cả khi chúng cùng dùng GPU. Khi tăng concurrency hoặc tách runner, phải có hạn mức tổng cho từng thiết bị và bằng chứng đo bộ nhớ; giới hạn số request không tự chứng minh đủ VRAM cho model đã nạp.

Phân biệt hai trạng thái độc lập:

| Tình huống | Trạng thái công việc | Trạng thái bên chờ HTTP / xử lý |
| --- | --- | --- |
| Chờ lượt | `queued` | Chờ trong deadline của hàng đợi |
| Đang suy luận | `running` | Chờ trong deadline thực thi |
| Request timeout/ngắt khi đang chạy | Vẫn `running` | Không chờ kết quả; suất chạy vẫn bị giữ |
| Công việc thực sự kết thúc | `finished` | Trả kết quả nếu còn người chờ; nếu không, thu hồi kết quả/exception và ghi log |
| Hủy/quá hạn khi chưa chạy | `discarded` | Bỏ khỏi hàng đợi, không gọi engine |

`asyncio.timeout()` chỉ giới hạn phần chờ bất đồng bộ; hủy await không phải cách dừng thread hoặc kernel GPU. Không dùng lại mẫu “timeout bao quanh semaphore ở route” trong bản đặc tả trước. Không hứa hủy cưỡng bức suy luận bằng threadpool. Nếu cần dừng tính toán đúng deadline, phải khảo sát worker process riêng và kiểm chứng quy trình khởi động lại; đó chưa phải cam kết của bản đầu.

### 5.2 Khởi động, dừng và ghi log

- Nạp engine và warm-up có giới hạn, theo trình tự phù hợp bộ nhớ thiết bị; health chỉ đọc trạng thái. Không đặt tác vụ suy luận dài trực tiếp trong endpoint `async def`.
- Khi dừng, ngừng admission, kết thúc các request đang chờ bằng lỗi 503 và chờ worker đang chạy tối đa thời gian grace. Không gọi `unload()` khi worker còn truy cập model.
- Nếu worker chưa kết thúc sau grace, ghi rõ dịch vụ chưa dừng sạch và yêu cầu cơ chế quản lý process xử lý; không đánh dấu worker đã dừng hoặc tái sử dụng suất/bộ nhớ trong cùng process. Hành vi này cần thử với fake engine bị giữ trước khi vận hành thật.
- Log gồm request/job ID, loại tác vụ, trạng thái, model/version, thời gian chờ/chạy, mã lỗi và trường hợp hoàn tất sau timeout. Phân biệt số request HTTP còn chờ với số worker thực tế còn chạy.
- Khi lỗi tài nguyên làm engine không còn phục vụ được, chuyển engine sang `failed` và trả 503 cho yêu cầu tiếp theo; giữ endpoint health hoạt động nếu process còn sống. Không âm thầm tải model khác hoặc đổi thiết bị.

### 5.3 Kiểm tra WAV và giới hạn upload

Hợp đồng âm thanh phiên bản đầu là **RIFF/WAVE PCM không nén, format tag 1, signed 16-bit little-endian, 16.000 Hz, một kênh**. File float, extensible hoặc dạng nén chưa được hỗ trợ; thông báo định dạng yêu cầu để người dùng chuyển đổi trước khi tải lên.

1. Middleware giới hạn byte body thực nhận trước khi multipart parser ghi spool file. Có thể từ chối sớm theo `Content-Length`, nhưng vẫn đếm byte khi đọc, kể cả khi không có header hoặc truyền chunked. Giới hạn số phần form: một file và tối đa một trường `language`.
2. Đọc file theo từng khối với hạn mức `MAX_AUDIO_FILE_BYTES`, dừng khi vượt giới hạn; không đọc toàn bộ upload không giới hạn rồi mới kiểm tra. Đóng upload/spool file trong mọi đường thành công, lỗi và hủy.
3. Kiểm tra container RIFF/WAVE, khai báo kích thước/chunk so với byte thực, chỉ một cấu hình `fmt` và một phần `data` hợp lệ. Kiểm tra các tham số PCM; không tin đuôi file hoặc MIME. Các chunk metadata nếu có cũng phải nằm trong hạn mức file.
4. Kiểm tra số frame dương, dữ liệu đủ frame và độ dài byte chia hết cho kích thước frame. Tính thời lượng từ số frame thực và sample rate; vượt giới hạn trả `AUDIO_TOO_LONG`, header/dữ liệu không khớp trả `AUDIO_INVALID`.
5. Với cấu hình mặc định, 30 giây tương ứng tối đa 480.000 frame, 960.000 byte PCM. Chỉ cấp phát/đọc số frame đã được kiểm tra; dữ liệu sau chuyển waveform cũng phải có đúng số mẫu và thời lượng. WAV hợp lệ được chuyển thành `AudioInput` trước khi đưa vào ASR.

Do không giải mã file nén trong bản đầu, không công bố cơ chế chống giải nén cho MP3/M4A/OGG. Nếu bổ sung các định dạng đó, phải bổ sung decoder, giới hạn thời gian/bộ nhớ/số mẫu đầu ra và test file hỏng/khai báo thời lượng sai trước khi mở API.

## 6. Giao diện và luồng sử dụng

### 6.1 Giao diện tĩnh

HTML/CSS/Vanilla JavaScript được phục vụ cùng origin với API; CSS/font/script dùng tài nguyên nội bộ. Đường dẫn static được tính từ vị trí `main.py`, ví dụ `Path(__file__).resolve().parent / "ui"`. Đăng ký router `/api` và xử lý đường dẫn API không tồn tại trước khi mount UI tại `/`; lỗi API không trả nhầm HTML của trang chủ.

Frontend tải health/models để hiển thị engine, các chiều được hỗ trợ và giới hạn đầu vào. Dùng `textContent` hoặc thuộc tính `value` để hiển thị văn bản/ lỗi; không diễn giải nội dung dịch thành HTML. Có nhãn trường, thao tác bàn phím, thông báo trạng thái truy cập được và bố cục phù hợp màn hình nhỏ.

“Không gọi CDN” chỉ xác nhận tài nguyên frontend tự chứa. Chạy offline toàn bộ với mô hình thật còn phụ thuộc quy trình chuẩn bị artifact và thử mất mạng tại §9.4.

### 6.2 Dịch văn bản

- Ô nguồn đếm ký tự sau đúng phép chuẩn hóa §4.3, hiển thị giới hạn từ backend và lý do không thể gửi. Nút Dịch vô hiệu khi rỗng, quá giới hạn, engine chưa ready hoặc đang chờ request hiện tại.
- Mỗi yêu cầu giữ snapshot văn bản, chiều dịch và revision UI. Nếu người dùng sửa câu hoặc đổi chiều khi đang chờ, tăng revision, hủy chờ phía client nếu có thể; chỉ nhận phản hồi khớp snapshot hiện hành. Phản hồi cũ không được ghi đè kết quả mới.
- Nút đảo chiều chỉ dùng bản dịch cuối còn khớp nguồn hiện tại để hoán đổi hai ô. Nếu chưa có kết quả hợp lệ, giữ văn bản nguồn, đổi chiều và xóa kết quả cũ. Không gửi request tự động chỉ vì đảo chiều.
- Hiển thị bản dịch, nút sao chép, model/version, nhãn mô phỏng nếu có, thời gian xử lý và thời gian chờ. Copy có thông báo thành công/thất bại; vẫn cho chọn văn bản nếu clipboard API không khả dụng.
- `api_client.js` xử lý mọi mã lỗi §4.2, HTTP lỗi không đúng schema, mất mạng và client timeout. Client timeout phải dài hơn deadline hàng đợi + thực thi + khoảng đệm mạng được cấu hình; không tự gửi lại tác vụ có thể vẫn chạy. Hiển thị lỗi dễ hiểu và cho người dùng chủ động thử lại.

### 6.3 Thử nghiệm giọng nói

```text
Thu âm hoặc chọn WAV tiếng Việt
    → Nhận dạng → Transcript có thể chỉnh sửa
    → Người dùng xác nhận và bấm “Dịch sang tiếng Tày”
    → Dịch đúng nội dung transcript sau chỉnh sửa, direction=vi-tay
```

Bước rà soát transcript giúp giảm lỗi lan truyền, không bảo đảm loại bỏ mọi lỗi ASR/dịch. API không tự kích hoạt bước dịch sau ASR.

- Tab có cảnh báo dễ hiểu: “Giọng nói đang ở mức thử nghiệm cho tiếng Việt. Chưa hỗ trợ nhận dạng tiếng Tày.” Nhãn mock/engine thật được hiển thị riêng cho từng bước; không đưa mã F09/D04 hoặc chi tiết triển khai vào cảnh báo người dùng.
- Thu âm dùng `getUserMedia()` và xử lý audio tại trình duyệt. `voice.js`/AudioWorklet đọc sample rate thực tế, trộn về mono, resample và mã hóa WAV PCM 16 kHz/16-bit. Yêu cầu sample rate từ thiết bị không được coi là bằng chứng dữ liệu đã đúng 16 kHz; backend vẫn kiểm tra lại.
- Cần secure context: HTTPS hoặc localhost. Truy cập `http://<IP-LAN>:8000` không được coi là phương án thu âm đã hỗ trợ. Hướng dẫn demo LAN phải có HTTPS được trình duyệt tin cậy; nếu thiếu, thông báo và cho tải WAV thay thế.
- Xử lý từ chối quyền, không có micro, trình duyệt không hỗ trợ, dừng/hủy thu âm; dừng media tracks và đóng audio context khi kết thúc/rời tab. Tự dừng ở giới hạn thời lượng, không chỉ đổi đồng hồ hiển thị.
- Chỉ cho tải WAV theo §5.3; UI có hướng dẫn định dạng, kiểm tra sơ bộ dung lượng, backend xác thực nội dung. Nếu ASR không có lời nói hoặc lỗi, không bật nút dịch.
- Khi sửa transcript/chọn file mới, vô hiệu hóa kết quả dịch cũ. Gửi snapshot transcript đã chỉnh sửa; nếu vượt giới hạn ký tự/token thì báo lỗi và yêu cầu rút gọn, không cắt tự động. Chỉ bật bước dịch khi chiều `vi-tay` sẵn sàng.

## 7. Hợp đồng bàn giao với pipeline

### 7.1 Trách nhiệm và thời điểm

Nhóm pipeline cung cấp adapter suy luận dùng chung với đánh giá, artifact và bằng chứng chọn checkpoint theo validation. Nhóm web viết lớp nối, quản lý vòng đời, request/response và giao diện. Ghi phiên bản hợp đồng và xác nhận liên nhóm tại `ARCHITECTURE.md` trước khi tích hợp; bản này là đề xuất để phối hợp, không tự xác nhận pipeline đã cung cấp adapter.

Theo quyết định điều phối hiện hành, việc triển khai adapter/checkpoint được để sau khi `feat/translation-pipeline` hoàn tất. T11/T12 vẫn là phụ thuộc nghiệm thu T19/T20; T22 cần bundle cuối theo T16/T17 và bằng chứng validation. D01 quyết định họ mô hình, một hay hai checkpoint và hình thức fine-tune. Không yêu cầu pipeline xuất một tên weights/tokenizer cụ thể khi chưa chốt phương án.

### 7.2 Bundle và metadata bắt buộc

Bố cục minh họa, tên artifact do pipeline đặt:

```text
models/demo-bundle/
├── model_metadata.json              # Manifest có phiên bản schema
├── checksums.json                   # SHA-256 của artifact/config liên quan
├── artifacts/                       # Một hoặc nhiều bộ model/tokenizer
└── validation/                      # Bằng chứng lựa chọn, khi đã có
```

Manifest thật phải đáp ứng các trường/ngữ nghĩa dưới đây. Đường dẫn bên trong bundle là tương đối; không nhúng đường dẫn riêng của máy huấn luyện. API chỉ xuất các trường công khai cần thiết.

| Trường | Yêu cầu |
| --- | --- |
| `schema_version` | Phiên bản hợp đồng; loader từ chối phiên bản không hiểu |
| `model_id`, `bundle_version` | Định danh bundle ổn định; không suy từ tên thư mục |
| `runtime` | Adapter/loader đã thống nhất và phiên bản thư viện cần dùng |
| `artifacts` | Theo từng artifact ID: vị trí model/tokenizer, checkpoint version, tokenizer version, cấu hình kiến trúc/giải mã, language config và danh mục checksum |
| `direction_routes` | Ánh xạ `vi-tay`/`tay-vi` tới artifact và cấu hình ngôn ngữ nguồn/đích tương ứng; có thể dùng chung artifact |
| Giới hạn theo route | `max_source_tokens`, `max_new_tokens`, cách tính token đặc biệt và hành vi khi chạm giới hạn; giá trị từ pipeline, không tự điền mặc định ở web |
| `provenance` | Run ID, phiên bản dữ liệu, cấu hình huấn luyện và nơi đối chiếu log/checkpoint; phạm vi nào chưa có bằng chứng phải ghi rõ |
| `metrics` | `null` hoặc object theo từng chiều; mỗi kết quả có split, phiên bản/hash tập validation, run ID, tên/version/signature công cụ và score thực đo |
| `selection` | Tiêu chí chọn checkpoint bằng validation và tài liệu/log đối chiếu; bắt buộc khi bàn giao nghiệm thu T22 |

Không tạo một JSON giả trông như checkpoint đã huấn luyện. Mock có metadata riêng như §4 và `metrics: null`; không có `training_date` hoặc điểm BLEU/chrF bịa. Nếu chỉ thiếu metric, có thể phục vụ kỹ thuật với `metrics: null` và ghi giới hạn; chưa đủ bằng chứng lựa chọn thì chưa nghiệm thu T22. Nếu thiếu manifest/định danh/ánh xạ bắt buộc, engine thật không được ready.

### 7.3 Kiểm tra trước khi nạp

1. Kiểm tra schema, checksum và khả năng đọc tất cả artifact/config cần thiết từ bundle cục bộ. Không tự tìm model/tokenizer trên mạng khi thiếu file.
2. Loader xử lý đúng loại artifact đã thống nhất: full weights, các shard hoặc adapter kèm base model chính xác. Nếu dùng adapter, phải có phiên bản/checksum base model và hướng dẫn nạp đầy đủ.
3. Đối chiếu tokenizer với checkpoint: vocabulary, token nguồn/đích, padding/BOS/EOS, kích thước embeddings và cấu hình giải mã. Không tự tạo token Tày hoặc lấy tokenizer gần giống để nạp cho qua.
4. Thử suy luận bằng mẫu bàn giao theo từng chiều với cùng preprocessing/generation như pipeline đánh giá; kiểm tra batch/padding và chiều dịch không bị lẫn. Đầu ra này là kiểm tra tương thích, không tự chứng minh chất lượng ngôn ngữ.
5. Đo footprint khi nạp cả dịch và ASR trên cấu hình phục vụ. Bundle chỉ ready khi mọi route đã khai báo đều vượt qua kiểm tra; một route lỗi không được che đi để báo cả bundle sẵn sàng. Có thể bàn giao bundle thử chỉ khai báo một chiều đã kiểm chứng, nhưng chưa đủ nghiệm thu F08.

Các mục còn phụ thuộc D01/T11 hoặc bằng chứng validation được theo dõi trong báo cáo nhóm; không dùng hoàn thành tài liệu thay cho bàn giao artifact.

## 8. Kế hoạch và nghiệm thu

### 8.1 Công việc theo Txx

Mốc tuần theo `TASKS.md`, có thể triển khai sớm phần độc lập. Bằng chứng mock chỉ xác nhận phần khung; phụ thuộc nghiệm thu thật giữ nguyên.

| Mã / mốc | Phần có thể làm độc lập | Điều kiện nghiệm thu và bằng chứng |
| --- | --- | --- |
| T05 — tuần 2 (12–18/11/2026) | Khảo sát Whisper tiếng Việt; lập kế hoạch 5–10 mẫu có lời nói và transcript được rà soát; định nghĩa cách tính WER | Mẫu có nguồn/quyền dùng, manifest/checksum, log ASR thật và đánh giá lỗi riêng; cập nhật D04 bằng kết quả thực tế hoặc trở ngại. Không bắt buộc có bản dịch Tày để đo WER ASR |
| T19 — tuần 4 (26/11–02/12/2026) | Schema, mock, runner, upload, lỗi và kiểm thử API; thống nhất adapter với pipeline | Test độc lập đạt và tích hợp adapter/checkpoint sau T11/T12; kiểm tra chiều, tokenizer/version, giới hạn, lỗi và timing thật. Mock đạt chưa đủ hoàn thành T19 |
| T20 — tuần 5 (03–09/12/2026) | UI dịch hai chiều, loading/lỗi, chống kết quả cũ; kiểm thử trình duyệt bằng mock | Luồng nhập/chọn chiều/nhận kết quả và metadata đúng với backend đã nghiệm thu T19; bằng chứng thao tác và lỗi theo F08 |
| T21 — tuần 7 (17–23/12/2026) | Thu âm/upload WAV, transcript chỉnh sửa, luồng hai bước và cảnh báo PoC | Sau T05/T19/T20: chạy mẫu âm thanh thật → transcript → chỉnh sửa → dịch; giữ transcript trước/sau sửa, kết quả và giới hạn. Không dùng WAV tổng hợp để tuyên bố ASR hoạt động |
| T22 — tuần 8 trở đi (từ 24/12/2026) | Chuẩn bị đóng gói, kiểm tra môi trường sạch và hướng dẫn | Sau T16/T17/T20/T21: bundle chọn bằng validation, thử offline, đo độ trễ trên phần cứng thực có, hướng dẫn README đã chạy và bằng chứng tích hợp. Phần chưa đạt tiếp tục theo lịch dự án |

Manifest mẫu T05 ghi nguồn/quyền sử dụng, ID file/checksum, cách thu, thời lượng, định dạng, transcript gốc, người/ngày rà soát và phiên bản bộ mẫu. Dữ liệu chưa được phép chia sẻ giữ ngoài Git. Nếu có tham chiếu dịch Tày cho T21, phải có nguồn/người duyệt tương ứng; không tự viết bản dịch chuẩn.

Báo cáo ASR lưu model/version/checksum, thiết bị, tham số nhận dạng, transcript đầu ra từng file và lỗi. Định nghĩa trước quy tắc Unicode, hoa/thường, dấu câu và tokenization cho WER; tính tổng lỗi thay thế/xóa/chèn trên tổng token tham chiếu, không lấy trung bình tùy tiện giữa file dài/ngắn. Ghi cách xử lý im lặng và giới hạn tập mẫu nhỏ; số lượng 5–10 chỉ là kế hoạch khảo sát.

### 8.2 Ma trận kiểm tra bắt buộc

| Nhóm | Kịch bản | Kết quả cần kiểm chứng / mức |
| --- | --- | --- |
| Schema văn bản | Thiếu/sai kiểu, trường lạ, chuỗi rỗng, khoảng trắng, NFC/ký tự ngoài BMP, đúng/vượt ranh giới | Mã lỗi/schema và phép đếm frontend/backend thống nhất; mock |
| Chiều/model | Hai chiều, chiều sai, chiều chưa nạp, model ID khác, engine loading/failed/disabled | Mã lỗi đúng; không quảng bá khả năng chưa có; mock rồi kiểm tra lại với model thật |
| Giới hạn token | Chuỗi đủ ngắn theo ký tự nhưng quá số token; đầu ra chạm giới hạn | Không cắt âm thầm; fake adapter kiểm tra hợp đồng và adapter thật xác minh tokenization |
| Metadata | Kết hợp dịch thật/ASR mock và ngược lại; thiếu metric hoặc manifest bắt buộc | Nhãn từng engine rõ; metric `null` khi thiếu; không fallback sang model/mock khác |
| Chuẩn hóa lỗi | Validation, HTTP exception, lỗi domain, unexpected error, 404/405, body quá lớn | Cùng `ErrorResponse`, request ID; không lộ stack trace |
| Hàng đợi | Đủ worker và hàng đợi, thêm request; hết hạn khi chưa chạy | 503 quá tải; 504 `phase=queue`; job quá hạn không gọi engine |
| Timeout/hủy | Worker bị giữ bằng synchronization event; request timeout/ngắt rồi có request tiếp | Worker thực tế không vượt cấu hình; slot không nhả sớm; kết quả muộn được thu hồi |
| Health | Giữ worker chưa hoàn tất rồi gửi health | Health phản hồi trước khi thả worker; không đợi inference queue. Dùng timeout kiểm thử đủ rộng để phát hiện treo, không coi là benchmark <10 ms |
| Shutdown | Dừng lúc có job chờ và job đang chạy | Ngừng admission, không unload model đang dùng; ghi được trường hợp hết grace |
| Upload/WAV | Ranh giới file/body, thiếu `Content-Length`, chunked, nhiều file/field, đổi đuôi, header giả, thiếu frame, sai rate/kênh/bit depth, quá 30 giây | Đúng mã lỗi, cấp phát trong hạn mức và dọn tài nguyên; WAV sinh trong bộ nhớ đủ cho parser |
| ASR | WAV có lời nói thật, im lặng, tiếng ồn và ngôn ngữ không thuộc phạm vi | Đánh giá riêng nhận dạng; không tự dịch transcript rỗng; giả lập chỉ kiểm tra luồng lỗi, chưa xác nhận khả năng model |
| UI | Sửa nguồn/đảo chiều lúc chờ, gửi lặp, mất mạng, từ chối micro, sửa transcript, clipboard lỗi | Không nhận kết quả cũ; thông báo phù hợp; gửi đúng transcript sau chỉnh sửa |
| Tương thích pipeline | Cùng mẫu/generation, cả hai chiều, batch/padding, thiếu/sai tokenizer/token/checksum | Kết quả nhất quán với adapter dùng chung; lỗi artifact không cho engine ready |
| Môi trường/offline | Cài môi trường sạch theo bộ phụ thuộc đã chốt; restart khi không có mạng | Mock không cần ML; engine thật chỉ dùng artifact đã chuẩn bị; ghi rõ phần chưa thử |

Test runner dùng fake engine có event/barrier để kiểm soát lúc bắt đầu/kết thúc, tránh dựa vào sleep ngẫu nhiên. Tách `src/tests/web_app/` cho test độc lập và `src/tests/web_app_integration/` cho checkpoint/ASR thật; collection của test độc lập không import ML. Các bộ test thật chỉ chạy khi có đầu vào hợp lệ và không tự tải mô hình.

### 8.3 Đo hiệu năng và ghi trạng thái

Không dùng “100% test dưới 2 giây” hoặc “health dưới 10 ms” làm cam kết chung. Bộ kiểm thử phải đạt các ca chức năng đã xác định; thời gian chạy được ghi cùng môi trường. Nếu cần mục tiêu độ trễ cho buổi demo, chốt sau phép đo thử.

Đo trên CPU và/hoặc GPU thực có, ghi phần chưa đo. Mỗi phép đo lưu OS, phiên bản thư viện, CPU/RAM/GPU/VRAM, model/checksum, độ dài đầu vào, cấu hình worker, số request, warm-up và cách đồng bộ GPU. Tách cold start, queue time, inference và tổng thời gian phản hồi; báo số mẫu, p50/p95 và lỗi/timeout. Không suy ra benchmark từ mock sleep.

Trạng thái hoàn thành Txx do bằng chứng và phụ thuộc trong `TASKS.md` quyết định. Báo cáo nhóm phải phân biệt **đã sửa đặc tả**, **đã kiểm thử mock**, **đã tích hợp thật** và phần còn thiếu; người tích hợp mới cập nhật tiến độ toàn dự án.

### 8.4 Thứ tự thực hiện và đợt đầu tiên

Các đợt dưới đây là mốc bàn giao bên trong nhánh `feat/web-demo`, không tạo nhánh hoặc mã Txx mới. Mặc định giao **đợt 1 — backend mock của T19** trước; các đợt còn lại là kế hoạch tiếp nối khi được giao. T05 có thể khảo sát riêng sớm hơn khi có mẫu và tài nguyên phù hợp, không buộc phải chờ giao diện hoàn thành.

| Đợt | Phạm vi | Đầu ra để chuyển bước |
| --- | --- | --- |
| 1 — T19 với mock | Môi trường web, engine mock, bốn API, validation WAV/văn bản, runner và lỗi | Backend khởi động được; test độc lập và kiểm tra HTTP thực tế đạt; README/báo cáo có lệnh và kết quả |
| 2 — T20 với mock | Giao diện dịch văn bản nối backend theo §6.1–6.2 | Có bằng chứng thao tác trình duyệt, xử lý lỗi và phản hồi cũ; nhãn mock rõ ràng |
| 3 — T05 và T21 | Khảo sát ASR thật theo T05; xây luồng thu âm/upload → transcript chỉnh sửa → dịch theo T21 | Bằng chứng nhận dạng riêng và luồng tích hợp; phần nào còn mock phải ghi rõ, chưa nghiệm thu T21 nếu thiếu phụ thuộc thật |
| 4 — Tích hợp thật, T22 | Thay mock bằng adapter/bundle pipeline; kiểm tra offline và đóng gói | Để sau khi nhánh `feat/translation-pipeline` hoàn tất; T19/T20 vẫn cần T11/T12, T22 cần bundle cuối chọn bằng validation sau T16/T17 và đủ điều kiện §8.1 |

**Trước khi viết mã đợt 1:**

1. Đọc `AGENTS.md`, `PROJECT_CONTEXT.md`, `TASKS.md`, `.agents/README.md`, `.agents/BRANCHES.md`, báo cáo `web-demo`, `ARCHITECTURE.md`, `PROJECT_REQUIREMENTS.md` và đặc tả này. Dùng đúng worktree `web-demo` trên nhánh `feat/web-demo`, base/đích tích hợp là `master`.
2. Kiểm tra nhánh, worktree, thay đổi đã stage/chưa stage và mã nguồn thực có. Giữ nguyên thay đổi đang có; nếu một phần đã được hiện thực thì kiểm tra và tiếp tục phần còn thiếu, không tạo lại hoặc ghi đè chỉ vì đặc tả từng ghi “chưa có”.
3. Ghi agent/ngày, commit đầu vào, phạm vi T19 và phần nền web phối hợp T06 vào `.agents/reports/web-demo.md`. Xác nhận môi trường Python và các phụ thuộc cần dùng trước khi cài/chạy.

**Thực hiện đợt 1 theo thứ tự:**

1. Tạo phụ thuộc web/runtime và web/dev, cấu hình `.env.example`, schemas và domain exceptions theo §2–4; bổ sung `.gitignore` nếu có đầu ra mới cần loại khỏi Git. Khai báo thư viện thực dùng, chưa cài runtime ML cho đợt mock.
2. Hiện thực `InferenceEngine`, `ASREngine`, các engine mock, ánh xạ chiều dịch và validator WAV. Các engine thật chưa có adapter/artifact phải báo chưa sẵn sàng; không tự tải model hoặc tạo kết quả thay thế.
3. Hiện thực runner theo §5 với hàng đợi hữu hạn, deadline chờ/chạy, giữ suất sau timeout/hủy và xử lý shutdown. Dùng fake engine có event để kiểm tra vòng đời, không chỉ thử bằng sleep ngẫu nhiên.
4. Nối lifespan, dependencies, middleware và bốn endpoint §4; chuẩn hóa mọi lỗi về cùng schema. Máy chủ API phải khởi động được khi chưa có thư mục UI; phần giao diện thực hiện ở đợt 2.
5. Chạy kiểm thử backend phù hợp §8.2, lệnh kiểm tra nền trong README và kiểm tra HTTP thực tế với server mock. Sửa lỗi trong phạm vi đợt 1 trước khi bàn giao; cập nhật README bằng lệnh đã chạy, không chỉ sao chép lệnh dự kiến.

Phạm vi file chính: `src/web_app/` phần backend, `src/tests/web_app/`, `requirements-web.txt`, `requirements-web-dev.txt`, `.env.example`, `.gitignore`, README và báo cáo nhóm. Mục web trong `ARCHITECTURE.md` chỉ cập nhật nếu có thay đổi giao tiếp cần ghi nhận. Đợt 1 không triển khai UI, huấn luyện, crawl, tải checkpoint hoặc sửa các module dữ liệu/mô hình của nhóm pipeline. Các thao tác commit/push/merge/tag thực hiện theo yêu cầu riêng của người dùng, không suy ra từ việc giao viết mã.

**Đợt 1 đủ điều kiện bàn giao khi:**

- Chạy được trong môi trường web/dev không có thư viện ML; `python -m pip check` và `python -m pytest src/tests/web_app/ -v --tb=short` có kết quả thực tế. Các kiểm tra nền của repo được chạy theo README và ghi nhận nếu có lỗi.
- Server mock trả đúng `/api/health`, `/api/models`, `/api/translate`, `/api/asr/transcribe`; thử hai chiều dịch và một WAV hợp lệ, nhận metadata/nhãn mock đúng. Transcript mẫu không được ghi thành kết quả nhận dạng thật.
- Có test cho đầu vào rỗng/sai kiểu/quá giới hạn, chiều/model sai, engine chưa ready, WAV hỏng/quá lớn/quá dài, error schema, hàng đợi đầy, timeout/hủy, health khi worker đang bận và shutdown. Ca timeout phải kiểm tra số worker thực tế còn chạy.
- README có lệnh cài/chạy/test đã kiểm chứng; báo cáo nhóm ghi file thay đổi, môi trường, lệnh, kết quả, giới hạn và phần chờ pipeline. Thiếu checkpoint không chặn việc hoàn thiện backend mock, nhưng **không đánh dấu toàn bộ T19 hoàn thành** khi chưa có T11/T12 và nghiệm thu tích hợp thật.

Sau mốc này, bàn giao kết quả đợt 1 và các việc còn lại. Việc cần thống nhất với pipeline được ghi tại mục “Vướng mắc và bước tiếp theo” trong báo cáo; không tự chốt D01/D04 để vượt phụ thuộc.

### 8.5 Nội dung giao việc cho Claude Code

Mở Claude Code trong worktree `web-demo`, rồi dùng nội dung dưới đây. Đây là yêu cầu triển khai đợt 1; khi giao đợt khác, chỉ rõ phạm vi mới và yêu cầu đọc lại báo cáo hiện tại.

```text
Đọc AGENTS.md và các tài liệu bắt buộc được liệt kê ở mục 8.4 của
docs/SPECS_WEB_DEMO.md, đặc biệt báo cáo .agents/reports/web-demo.md.

Triển khai đợt 1 — backend mock của T19 — theo mục 8.4, trên nhánh
feat/web-demo trong worktree hiện tại. Kiểm tra mã nguồn và trạng thái Git
trước khi sửa; bảo toàn các thay đổi đã stage/chưa stage đang có.

Thực hiện đến khi đủ các đầu ra và kiểm tra của đợt 1, không dừng ở kế hoạch.
Cập nhật README bằng lệnh đã chạy và ghi bằng chứng, lỗi/giới hạn cùng phần
còn chờ vào .agents/reports/web-demo.md. Không đánh dấu T19 hoàn thành
chỉ vì mock chạy được; không tự đổi tiến độ toàn dự án trong TASKS.md.

Phạm vi lần này là backend mock; chưa làm UI, mô hình thật, huấn luyện,
crawl hoặc tải checkpoint. Chưa commit, push, merge hay tạo tag.
Khi đủ mốc đợt 1, bàn giao kết quả và việc tiếp theo bằng tiếng Việt.
```

## 9. Môi trường và lệnh dự kiến

**Các file/lệnh web dưới đây chưa tồn tại/chưa được chạy trong đợt sửa đặc tả.** Chỉ thực hiện sau khi triển khai phần tương ứng. Lệnh vận hành đã được kiểm chứng sau này được đưa vào `README.md`, tránh giữ hai hướng dẫn khác nhau.

### 9.1 Phát triển và kiểm thử độc lập

Chạy từ gốc repo, sau khi xác minh Python 3.11 trở lên và đã tạo các file requirements theo §2.1:

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-web-dev.txt
python -m pip check
python -m pytest src/tests/web_app/ -v --tb=short
```

Khởi động mock rõ ràng để cấu hình cũ trong `.env` không vô tình nạp model thật:

```bash
export TRANSLATION_ENGINE_TYPE=mock
export ASR_ENGINE_TYPE=mock
python -m uvicorn src.web_app.main:app --host 127.0.0.1 --port 8000 --reload
```

Mở `http://localhost:8000`. Bộ kiểm tra phụ thuộc của web phải phối hợp T06 và cập nhật lệnh kiểm tra trong README khi thêm test, để giữ khả năng kiểm tra riêng pipeline dữ liệu.

### 9.2 Kiểm tra tích hợp thật

Chỉ chạy khi đã có bundle, mẫu audio được duyệt và môi trường phù hợp; tạo/kích hoạt `.venv` như §9.1 trước khi cài phụ thuộc. Test tích hợp phải đọc cấu hình đường dẫn, xác nhận kết quả `is_mock=false`, từ chối đầu vào thiếu/sai và ghi rõ trường hợp bỏ qua; skip không được báo là nghiệm thu đạt. Bộ test này không thuộc lệnh mock mặc định.

```bash
python -m pip install -r requirements-web-dev.txt -r requirements-web-ml.txt
python -m pip check
export TRANSLATION_ENGINE_TYPE=pipeline
export MODEL_BUNDLE_PATH=models/demo-bundle
export MODEL_DEVICE=cpu
export ASR_ENGINE_TYPE=whisper
export WHISPER_MODEL_PATH=models/asr/model.pt
export ASR_DEVICE=cpu
python -m pytest src/tests/web_app_integration/ -v --tb=short
```

Các đường dẫn trên là ví dụ về vị trí bàn giao, không có artifact đi kèm repo. Khi chỉ có đầu vào cho một phần, chọn bộ test phù hợp và ghi giới hạn, không tạo dữ liệu giả để vượt kiểm tra.

### 9.3 Phục vụ bằng engine thật

Sau khi đã cài runtime, kiểm tra artifact và thử tích hợp. Khởi đầu trên thiết bị đã đo, ví dụ CPU:

```bash
export TRANSLATION_ENGINE_TYPE=pipeline
export MODEL_BUNDLE_PATH=models/demo-bundle
export MODEL_DEVICE=cpu
export ASR_ENGINE_TYPE=whisper
export WHISPER_MODEL_PATH=models/asr/model.pt
export ASR_DEVICE=cpu
export INFERENCE_WORKERS=1
python -m uvicorn src.web_app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Nếu dùng GPU, chỉ đổi thiết bị sau khi kiểm tra runtime/CUDA và tổng bộ nhớ của các engine. Không dùng `--reload` khi trình diễn mô hình thật. Khi demo qua LAN, cấu hình địa chỉ listen và HTTPS phù hợp §6.3; chưa có hướng dẫn LAN đã được kiểm chứng ở thời điểm này.

### 9.4 Chuẩn bị chạy offline

1. Cài bộ phụ thuộc và chuẩn bị đủ model/tokenizer/config/Whisper weights khi có mạng, theo nguồn và phiên bản đã thống nhất; ghi checksum và điều kiện sử dụng. Không tải trong một request dịch/ASR.
2. Cấu hình loader chỉ đọc artifact cục bộ; file thiếu phải báo lỗi, không tự truy cập hub. Kiểm tra UI không gọi CDN, font hoặc script ngoài.
3. Khởi động lại ứng dụng khi mạng đã ngắt để phát hiện phụ thuộc cache chưa đóng gói; thử cả dịch, thu âm/upload, transcript và xử lý lỗi trên máy demo.
4. Ghi bằng chứng, cấu hình, vị trí lưu artifact và phần cần chuẩn bị trong README/báo cáo nhóm. Không commit weights, môi trường ảo, dữ liệu hạn chế hoặc cache; bổ sung `.gitignore` cho đầu ra mới khi thực sự triển khai.

## 10. Nguồn đối chiếu kỹ thuật

- [Python: timeout](https://docs.python.org/3.12/library/asyncio-task.html#asyncio.timeout) quy định hủy phần chờ và yêu cầu phiên bản; [AnyIO: worker threads](https://anyio.readthedocs.io/en/stable/threads.html) giải thích công việc trong thread tiếp tục sau khi bên chờ bị hủy.
- [FastAPI: upload](https://fastapi.tiangolo.com/tutorial/request-files/) quy định phụ thuộc multipart; [xử lý lỗi](https://fastapi.tiangolo.com/tutorial/handling-errors/) phân biệt các loại exception handler; [Pydantic migration](https://pydantic.dev/docs/validation/latest/get-started/migration/#basesettings-has-moved-to-pydantic-settings) ghi `BaseSettings` ở gói riêng.
- [Whisper transcribe](https://github.com/openai/whisper/blob/main/whisper/transcribe.py) và [audio](https://github.com/openai/whisper/blob/main/whisper/audio.py) mô tả nhận waveform/đường dẫn và đường đọc file qua `ffmpeg`; [MDN getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia#privacy_and_security) nêu điều kiện secure context.

Nguồn được đối chiếu khi review ngày 02/11/2026. Khi triển khai cần kiểm tra lại trên đúng phiên bản thư viện đã khóa; các nguồn này không thay thế test của repo.
