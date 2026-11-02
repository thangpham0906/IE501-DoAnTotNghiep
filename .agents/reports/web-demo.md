# Báo cáo nhóm web-demo

## Phân công

- Nhánh: `feat/web-demo`; workspace Orca: `web-demo`.
- Base / đích merge: `master` / `master`.
- Người/agent nhận việc: Codex — review và sửa đặc tả theo yêu cầu ngày 02/11/2026; chưa triển khai ứng dụng.
- Commit đầu vào: `8a8f0326a310ac212f238cc654a3ab2fddc3991c`; bản đặc tả đầu vào chưa được Git theo dõi.
- Ngày khởi tạo báo cáo: 01/11/2026.
- Phạm vi: Ứng dụng demo văn bản và giọng nói.
- Đọc [phân công chung](../BRANCHES.md), [quy định báo cáo](../README.md), [TASKS.md](../../TASKS.md) và [yêu cầu dự án](../../PROJECT_REQUIREMENTS.md).

## Nhiệm vụ và ranh giới

- `src/web_app/`: backend API, frontend, adapter ASR, transcript, xử lý đầu vào và lỗi.
- Cấu hình chạy, đóng gói và kiểm thử tích hợp demo; tách module backend/frontend/ASR trong cùng nhánh.
- T22 chủ trì tích hợp/bàn giao ứng dụng; phối hợp pipeline về checkpoint được chọn bằng validation và report về tài liệu.

Đường dẫn thành phần chưa tồn tại là dự kiến, không phải bằng chứng đã triển khai. Chi tiết giao tiếp và cách nạp mô hình thống nhất tại [ARCHITECTURE.md](../../ARCHITECTURE.md).

## Đầu ra cần bàn giao

- API/UI dịch văn bản hai chiều với model metadata và các trạng thái chờ/lỗi.
- PoC âm thanh → transcript → bản dịch ở ngôn ngữ đã kiểm chứng, hiển thị transcript và giới hạn ASR riêng.
- Hướng dẫn cài/chạy, cấu hình endpoint/model và bằng chứng thử luồng thật khi có checkpoint.

**Có thể bắt đầu:** Thống nhất giao diện suy luận/API, phát triển web và ASR adapter với fixture/mock ghi rõ. Demo với mock chưa phải nghiệm thu mô hình thật; không mặc định ASR hỗ trợ tiếng Tày.

**Kiểm tra trọng tâm:**

- Schema API/client khớp, xử lý rỗng/sai chiều/quá giới hạn/model chưa sẵn sàng và lỗi audio.
- Luồng dùng đúng transcript, model/tokenizer đúng phiên bản, đo phản hồi trên môi trường thực; không huấn luyện trong request.

## Tiến độ từng Txx

Cột trạng thái nền chụp từ `TASKS.md` khi khởi tạo. Nhóm cập nhật tiến độ/kết quả mới của từng Txx; công cụ có sẵn không đồng nghĩa đã chạy với dữ liệu/mô hình thật.

| Mã | Công việc | Phụ thuộc nghiệm thu | Trạng thái nền | Tiến độ trong đợt này / bằng chứng |
| --- | --- | --- | --- | --- |
| T05 | Chốt phạm vi âm thanh và khả năng ASR bằng mẫu thử | — | Chưa làm | Đã sửa đặc tả ASR/mẫu thử/WER tại §3.3, §8; chưa khảo sát ASR thật hoặc đóng D04 |
| T19 | Backend suy luận: kiểm tra đầu vào, chiều dịch, phiên bản mô hình và lỗi | T11, T12 | Chưa làm | Đã sửa hợp đồng engine/API, runner và lỗi tại §3–5; chưa có mã backend/test web |
| T20 | Giao diện dịch văn bản và kiểm tra tích hợp với backend | T19 | Chưa làm | Đã sửa hành vi UI, Unicode và phản hồi cũ tại §6; chưa triển khai giao diện |
| T21 | Tích hợp âm thanh → transcript → bản dịch; ghi phạm vi và mẫu demo | T05, T19, T20 | Chưa làm | Đã sửa luồng hai bước, WAV và điều kiện thu âm tại §5.3/§6.3; chưa chạy luồng thật |
| T22 | Chọn checkpoint theo validation, hoàn thiện demo và hướng dẫn vận hành/tái hiện | T16, T17, T20, T21 | Chưa làm | Đã sửa hợp đồng bundle và lệnh dự kiến tại §7–9; chưa có checkpoint/bằng chứng tích hợp |

## Việc đã làm và đầu ra thực tế

Đợt ngày 02/11/2026 gồm review rồi sửa đặc tả theo yêu cầu tiếp theo của người dùng; chưa có kết quả triển khai ứng dụng. Trạng thái nghiệm thu các Txx bên trên giữ nguyên. Các số mục trong cột tiến độ tham chiếu bản đặc tả sau sửa.

| Ngày | Txx / việc đã thực hiện | File / commit / run ID | Kết quả và giới hạn |
| --- | --- | --- | --- |
| 02/11/2026 | Review đặc tả liên quan T05, T19–T22 | [SPECS_WEB_DEMO.md](../../docs/SPECS_WEB_DEMO.md); chi tiết bản trước sửa bên dưới | Phát hiện R01–R10; giữ nguyên đầu vào ở lượt review |
| 02/11/2026 | Sửa trực tiếp đặc tả theo yêu cầu tiếp theo | `docs/SPECS_WEB_DEMO.md`, `ARCHITECTURE.md` (mục web), `PROJECT_CONTEXT.md` (đề xuất web) | Đã xử lý R01–R10 ở mức tài liệu; D01/D04 và các phụ thuộc nghiệm thu thật giữ nguyên |
| 02/11/2026 | Ghi hướng dẫn để giao triển khai cho Claude Code | [Đặc tả §8.4–8.5](../../docs/SPECS_WEB_DEMO.md#84-thứ-tự-thực-hiện-và-đợt-đầu-tiên) | Có thứ tự đợt, phạm vi/tiêu chí bàn giao backend mock và nội dung giao việc; chưa khởi chạy agent hoặc triển khai code |

## Kiểm tra đã chạy

| Ngày | Lệnh / môi trường | Kết quả thực tế | Log / giới hạn |
| --- | --- | --- | --- |
| 02/11/2026 | `git status --short --branch`, `git branch -a -vv`, `git worktree list --porcelain`, `git rev-parse HEAD`; đối chiếu file bằng `rg` và Python `pathlib` | Đúng nhánh/worktree `web-demo`; chưa có `src/web_app/`, `src/tests/web_app/`, hai file requirements web hoặc `configs/web_config.json` | Chưa có ứng dụng để chạy bộ kiểm thử web |
| 02/11/2026 | `python3` với `importlib.metadata`; thí nghiệm timeout bên dưới | Python 3.12.3, AnyIO 4.14.2; semaphore có sức chứa 1 nhưng quan sát được 2 worker chạy đồng thời sau timeout | Thử cơ chế bằng hàm giả lập; không chạy FastAPI, mô hình dịch hoặc ASR |
| 02/11/2026 | `python3` đọc Markdown bằng `pathlib`/`re`, parse JSON bằng `json.loads`, gọi `bash -n` cho các block Bash; đối chiếu link/mục và khoảng trắng | 6 ví dụ JSON hợp lệ, 4 đoạn Bash đúng cú pháp; không có link nội bộ/tham chiếu mục hỏng hoặc giá trị cũ bị loại còn sót trong đặc tả | Chỉ kiểm tra tĩnh tài liệu; không thực thi lệnh cài/chạy ứng dụng |
| 02/11/2026 | `git diff --check`; kiểm tra whitespace riêng trong đặc tả chưa được Git theo dõi | Không phát hiện lỗi khoảng trắng | Chưa chạy test web hoặc mô hình thật vì chưa có mã/đầu vào |
| 02/11/2026 | Sau khi thêm §8.4–8.5: `git diff --check`, Python kiểm tra Markdown và link nội bộ; đối chiếu hash của `git diff --cached --binary` trước/sau | 16 liên kết hợp lệ, không lỗi fence/khoảng trắng; nội dung đã stage của người dùng giữ nguyên | Chỉ sửa đặc tả/báo cáo; phần bổ sung mới chưa stage hoặc commit |

## Vướng mắc và bước tiếp theo

- Phụ thuộc còn thiếu: Chưa có mã web, môi trường web, checkpoint hoặc bằng chứng ASR trong worktree; các phụ thuộc nghiệm thu trong bảng Txx giữ nguyên.
- Thay đổi giao tiếp cần phối hợp: Chốt adapter dùng chung, ánh xạ chiều dịch/token và hợp đồng checkpoint với pipeline tại `ARCHITECTURE.md`; xem R04.
- Bước tiếp theo: Khi được giao triển khai, bắt đầu đợt 1 — backend mock T19 — theo [đặc tả §8.4](../../docs/SPECS_WEB_DEMO.md#84-thứ-tự-thực-hiện-và-đợt-đầu-tiên); nội dung giao việc cho Claude Code ở §8.5. Xác nhận hợp đồng adapter/bundle với pipeline trước tích hợp thật; T05 là phần khảo sát riêng khi có đầu vào. R01–R10 đã được xử lý ở mức đặc tả; vẫn cần mã/test thực tế để nghiệm thu.

## Review và tích hợp

- Trạng thái nhóm: **Sẵn sàng review** đối với tài liệu đã sửa; ứng dụng chưa triển khai.
- Kết luận review: **Đạt ở mức chỉnh sửa và kiểm tra tĩnh tài liệu** theo R01–R10; **Chưa đủ bằng chứng** nghiệm thu ứng dụng.
- Người / ngày review: Codex / 02/11/2026.
- Điểm cần sửa / chưa đủ bằng chứng: Chưa có xác nhận adapter/bundle từ pipeline, chưa khóa phụ thuộc và chưa chạy kiểm thử web/ASR/mô hình thật. Bảng dưới ghi cách xử lý R01–R10 trong tài liệu.
- Commit/PR triển khai đã tích hợp: **Chưa merge**.
- Txx đủ điều kiện cập nhật trong `TASKS.md`: Chưa có kết luận mới.

### Đối chiếu sau sửa đặc tả — 02/11/2026

| Nhận xét | Vị trí xử lý trong `docs/SPECS_WEB_DEMO.md` | Giới hạn kiểm chứng |
| --- | --- | --- |
| R01 | §4.1, §5.1–5.2: hàng đợi hữu hạn, tách deadline, worker giữ suất sau timeout/hủy, shutdown | Chưa hiện thực runner; bằng chứng ở lượt review chỉ tái hiện lỗi mẫu cũ |
| R02 | §3.3, §4.4, §5.3: chỉ WAV PCM, giới hạn byte/frame và truyền waveform vào Whisper | Chưa chạy parser hoặc Whisper thật |
| R03 | §2.1, §9: Python >= 3.11, phụ thuộc web/dev/ML và lệnh cài rõ ràng | Chưa khóa/cài bộ phụ thuộc hoặc kiểm chứng môi trường sạch |
| R04 | §3.1–3.2, §7: adapter dùng chung, bundle một/hai checkpoint, token và giới hạn; đề xuất ghi tại `ARCHITECTURE.md` | Chờ phối hợp pipeline và D01 |
| R05 | §4.6, §7: metric `null` khi thiếu, metadata bắt buộc không fallback, bằng chứng validation | Chưa có checkpoint/metric thật |
| R06 | §4.2–4.5: handler mọi nhóm lỗi, thứ tự validation, health và cách tính timing | Chưa có endpoint để xác minh runtime |
| R07 | §3.4, §4, §6: nhãn mock riêng cho dịch/ASR; không tự đổi engine khi lỗi | Ví dụ JSON được kiểm tra cú pháp, chưa kiểm tra UI |
| R08 | §6.3, §9.4: điều kiện micro/HTTPS, chuẩn hóa audio và chuẩn bị offline | Chưa thử trình duyệt/LAN/mất mạng |
| R09 | §8: tách mock và nghiệm thu thật, đầy đủ phụ thuộc Txx, ma trận kiểm tra và phương pháp đo | Không dùng mục tiêu hiệu năng làm kết quả đã đạt |
| R10 | §1–2, §6: trạng thái thiết kế, đường dẫn tương đối, hành vi UI; ghi đề xuất công nghệ trong `PROJECT_CONTEXT.md` | Không đổi trạng thái D01/D04 hoặc tự coi GVHD đã duyệt |

### Review bản đặc tả trước sửa — 02/11/2026

Đầu vào: [đặc tả web](../../docs/SPECS_WEB_DEMO.md), đối chiếu với `PROJECT_CONTEXT.md`, `TASKS.md`, `PROJECT_REQUIREMENTS.md`, `ARCHITECTURE.md`, `README.md` và phân công nhóm. Dòng tham chiếu dưới đây thuộc bản đặc tả có SHA-256 `320a08b7676bf3d6e14d7fb68e5f12237628c92d6bf6aa08d2107d0cf532580d`.

Khung module, adapter mock, API dịch và bước sửa transcript là nền tảng phù hợp. Các mâu thuẫn sau được ghi nhận ở lượt review ban đầu, trước yêu cầu sửa trực tiếp. Giữ bảng này và bằng chứng timeout để đối chiếu; trạng thái sau sửa nằm ở bảng phía trên.

| Mã / mức ưu tiên | Vị trí trong đặc tả | Phát hiện, ảnh hưởng và hướng sửa |
| --- | --- | --- |
| R01 — Cần sửa trước triển khai | §5.1, dòng 431–450; §4.2, dòng 293 | `asyncio.timeout()` có thể kết thúc request và nhả semaphore khi worker vẫn đang chạy; thí nghiệm bên dưới đã tái hiện vượt sức chứa. Semaphore cũng không đặt giới hạn số request đang chờ, nên chưa có cơ chế phát sinh `SERVICE_OVERLOADED`. Cần giới hạn hàng đợi, tách thời gian chờ/chạy, giữ suất tính toán tới khi worker thực sự kết thúc; quy định xử lý client hủy, shutdown và tài nguyên dùng chung giữa dịch/ASR. |
| R02 — Cần sửa trước triển khai | §3.4, dòng 228–233; §4.3.5, dòng 384; §5.3; §6.3, dòng 500 | API nhận WAV/MP3/M4A/OGG nhưng mock và kiểm tra thời lượng chỉ xử lý WAV. Hướng dẫn vừa yêu cầu kiểm tra `ffmpeg`, vừa hứa không cần `ffmpeg`. Nên chốt MVP WAV PCM với sample rate/số kênh/bit depth cụ thể, hoặc mô tả đầy đủ decoder cho từng định dạng. Đọc upload theo giới hạn byte, giới hạn cả dữ liệu sau giải mã và thời gian decoder; không chỉ kiểm tra đuôi/header. Adapter cần chuyển `BytesIO` thành waveform phù hợp hoặc đường dẫn qua decoder trước khi gọi Whisper. |
| R03 — Cần sửa trước triển khai | §1, dòng 14; §4.1, dòng 244; §9 | Danh sách phụ thuộc tối thiểu thiếu `pydantic-settings`, `python-multipart` và công cụ chạy `pytest`. Mẫu `asyncio.timeout()` yêu cầu Python >= 3.11, trong khi README hiện chỉ quy định Python >= 3.10 cho pipeline dữ liệu. Cần khai báo riêng môi trường web, phiên bản tương thích và phụ thuộc kiểm thử; làm rõ file ML có kế thừa requirements web hay yêu cầu cài cả hai. |
| R04 — Cần sửa trước triển khai | §3.1, dòng 114; §4.3.3, dòng 329; §7 | D01 chưa chốt mô hình và cách tổ chức hai chiều, nhưng đặc tả mặc định NLLB, `tyz_Latn`, một checkpoint hai chiều và cấu trúc weights cố định. Cần thống nhất adapter dùng chung với pipeline tại `ARCHITECTURE.md`; hỗ trợ bundle/checkpoint theo quyết định thực tế, chỉ bật chiều đã kiểm chứng. Bổ sung kiểm tra tokenizer/checkpoint/token ID, token nguồn/đích và cấu hình giải mã, giới hạn token đầu vào/đầu ra, hành vi khi quá giới hạn; kiểm tra hai chiều đồng thời không lẫn trạng thái tokenizer. |
| R05 — Cần sửa trước triển khai | §4.3.3, dòng 340–344; §7, dòng 520–540 | Metadata được ghi là bắt buộc nhưng thiếu lại fallback từ tên thư mục và tạo chỉ số mặc định. Các số `24.5`/`48.2` chưa gắn nguồn hay nhãn giả lập. Cần dùng `null`/không công bố khi chưa đánh giá; tuyệt đối không tạo metric thay thế. Metadata định danh/ánh xạ bắt buộc bị thiếu hoặc sai phải làm engine thật không sẵn sàng. Kết quả thật cần truy tới run, validation, chiều dịch, cấu hình metric và phiên bản model/tokenizer. |
| R06 — Cần bổ sung | §4.2; §5.1, dòng 425–450; §5.2 | Handler mới chỉ mô tả `RequestValidationError`, trong khi route ném `HTTPException(detail=...)`; mặc định phản hồi này không khớp `ErrorResponse`. Cần hợp đồng xử lý cả HTTP/domain/unexpected errors, ánh xạ lỗi validation theo trường và quy tắc ưu tiên khi nhiều lỗi. Bổ sung trạng thái health khi chỉ một engine sẵn sàng và định nghĩa `latency_ms` có tính thời gian xếp hàng hay không. |
| R07 — Cần bổ sung | §3.4; §4.3.2; §4.3.5; §6.2–6.3 | Hai engine được cấu hình độc lập nhưng health chỉ có một `engine_type`; ASR response bỏ `model_metadata` dù `ASRResult` có trường này. Transcript mock có thể bị hiểu là nhận dạng thật; mock dịch khớp fixture cũng không có tiền tố. Cần metadata riêng từng engine và nhãn mô phỏng luôn hiện trên UI; không tự đổi sang mock khi nạp engine thật lỗi. Fixture chưa được kiểm duyệt không gọi là bản dịch chuẩn. |
| R08 — Cần bổ sung | §6.1, dòng 474; §6.3, dòng 500; §9 | Thu âm qua `getUserMedia()` cần secure context như HTTPS hoặc localhost; truy cập HTTP bằng IP LAN không đáp ứng điều kiện mặc định. Cần hướng dẫn môi trường demo, xử lý từ chối quyền/không có micro, chuyển sample rate thực tế sang 16 kHz, dừng track và giới hạn thời lượng phía trình duyệt. Cam kết offline cho engine thật phải có bước chuẩn bị/checksum checkpoint, tokenizer và Whisper weights, rồi thử khởi động khi không có mạng. |
| R09 — Cần sửa tiêu chí nghiệm thu | §8.1, dòng 550–554; §8.2, dòng 572–573; §9.2 | T19 không thể nghiệm thu đầy đủ chỉ bằng mock khi `TASKS.md` yêu cầu T11/T12. T05/T21 cần âm thanh có lời nói thật, transcript được rà soát và đánh giá ASR riêng; WAV tổng hợp chỉ kiểm thử parser/validation. Thêm ca model chưa sẵn sàng, timeout, quá tải, nạp sai checkpoint/tokenizer, ASR im lặng và lỗi khi chạy kết hợp. Ngưỡng toàn bộ test <2 giây, health <10 ms và yêu cầu đo cả CPU/GPU phải gắn môi trường/tài nguyên và phương pháp đo; chưa có số đo để khẳng định. |
| R10 — Cần đồng bộ tài liệu và bổ sung hành vi UI | §1–2; §6; §8 | Ghi rõ đây là bản nháp chưa triển khai; thay đường dẫn máy cá nhân bằng đường dẫn tương đối/cấu hình. Vanilla JS là lựa chọn đề xuất khác React trong kiến trúc hiện tại; ghi lý do/quyết định đúng nơi. D04 còn chưa xác minh, không dùng việc viết spec thay cho khảo sát T05. Bổ sung cách xử lý kết quả cũ khi sửa câu/đảo chiều lúc đang dịch, chặn gửi lặp, thống nhất phép đếm ký tự Unicode và quy tắc transcript vượt giới hạn dịch. Luồng sửa transcript giúp giảm lỗi lan truyền, chưa có cơ sở gọi là xử lý triệt để. |

Nguồn kỹ thuật đã đối chiếu:

- [FastAPI concurrency](https://raw.githubusercontent.com/fastapi/fastapi/master/fastapi/concurrency.py) dùng lại [Starlette `run_in_threadpool`](https://raw.githubusercontent.com/Kludex/starlette/main/starlette/concurrency.py), gọi `anyio.to_thread.run_sync`; [AnyIO về worker threads](https://anyio.readthedocs.io/en/stable/threads.html) mô tả thread vẫn tiếp tục sau khi bên chờ bị hủy. [Python timeout](https://docs.python.org/3.12/library/asyncio-task.html#asyncio.timeout) được thêm từ Python 3.11; [semaphore](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore) quản lý bộ đếm acquire/release.
- [FastAPI upload](https://fastapi.tiangolo.com/tutorial/request-files/) yêu cầu `python-multipart`; [Pydantic migration](https://pydantic.dev/docs/validation/latest/get-started/migration/#basesettings-has-moved-to-pydantic-settings) xác nhận `BaseSettings` nằm ở gói riêng; [FastAPI error handlers](https://fastapi.tiangolo.com/tutorial/handling-errors/) phân biệt HTTP errors và validation errors.
- [Whisper transcribe](https://raw.githubusercontent.com/openai/whisper/main/whisper/transcribe.py) nhận đường dẫn, NumPy array hoặc tensor; [Whisper audio](https://raw.githubusercontent.com/openai/whisper/main/whisper/audio.py) dùng `ffmpeg` khi đọc từ đường dẫn. [MDN getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia#privacy_and_security) quy định secure context.

### Bằng chứng thử riêng cơ chế timeout

Chạy trên Python 3.12.3 / AnyIO 4.14.2 sẵn có. Môi trường không có FastAPI, Starlette, Pydantic, pydantic-settings, python-multipart hoặc pytest. Không cài thêm thư viện, tải mô hình hay chạy thử chất lượng dịch/ASR. Lệnh đã chạy dùng cùng primitive AnyIO mà wrapper Starlette gọi, với hàm giả lập thay cho suy luận:

```bash
python3 - <<'PY'
import asyncio
import anyio
import threading
import time

active = 0
peak = 0
lock = threading.Lock()
events = []
start = time.monotonic()

def event(label):
    with lock:
        events.append((round(time.monotonic() - start, 3), label))

def fake_inference(name):
    global active, peak
    with lock:
        active += 1
        peak = max(peak, active)
    event(name + ': worker started')
    time.sleep(0.3)
    with lock:
        active -= 1
    event(name + ': worker finished')

async def main():
    semaphore = asyncio.Semaphore(1)
    async def request(name):
        try:
            async with asyncio.timeout(0.05):
                async with semaphore:
                    await anyio.to_thread.run_sync(fake_inference, name)
        except TimeoutError:
            event(name + ': timeout returned')
    await request('request-1')
    await request('request-2')
    await asyncio.sleep(0.35)
    print('Configured semaphore capacity:', 1)
    print('Observed peak simultaneously running workers:', peak)
    for elapsed, label in sorted(events):
        print(f'{elapsed:.3f}s {label}')

asyncio.run(main())
PY
```

Kết quả quan sát:

```text
Configured semaphore capacity: 1
Observed peak simultaneously running workers: 2
0.007s request-1: worker started
0.051s request-1: timeout returned
0.052s request-2: worker started
0.104s request-2: timeout returned
0.308s request-1: worker finished
0.353s request-2: worker finished
```

Đây là bằng chứng lỗi trong mẫu quản lý vòng đời tác vụ; không phải số đo độ trễ ứng dụng hoặc bằng chứng cạn VRAM thực tế. Cần kiểm thử lại với bộ phiên bản web được chốt khi triển khai.

## Nhật ký

| Ngày | Người | Nội dung | Bằng chứng |
| --- | --- | --- | --- |
| 01/11/2026 | Codex | Khởi tạo phân công và báo cáo nhóm; chưa thực hiện các nhiệm vụ triển khai | File báo cáo này |
| 02/11/2026 | Codex | Review đặc tả, đối chiếu trạng thái repo và tái hiện vấn đề timeout; giữ nguyên bản đặc tả và trạng thái nghiệm thu Txx | R01–R10 và lệnh/kết quả trong báo cáo này |
| 02/11/2026 | Codex | Sửa trực tiếp đặc tả theo yêu cầu người dùng, đồng bộ đề xuất giao tiếp/bối cảnh và kiểm tra tĩnh; giữ trạng thái nghiệm thu Txx | Bảng đối chiếu sau sửa, 6 ví dụ JSON và 4 đoạn Bash đã kiểm tra |
| 02/11/2026 | Codex | Bổ sung hướng dẫn giao việc cho Claude Code theo yêu cầu; chưa triển khai backend | Đặc tả §8.4–8.5 và mục bước tiếp theo của báo cáo |
