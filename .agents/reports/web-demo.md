# Báo cáo nhóm web-demo

## Phân công

- Nhánh: `feat/web-demo`; workspace Orca: `web-demo`.
- Base / đích merge: `master` / `master`.
- Người/agent nhận việc: Codex — review/sửa đặc tả và review mã ngày 02/11/2026; Claude Code là agent triển khai đợt 1 theo thông tin người dùng.
- Commit đầu vào lượt đặc tả: `8a8f0326a310ac212f238cc654a3ab2fddc3991c`; đặc tả khi đó chưa được Git theo dõi.
- Đầu vào review mã: `226ee43c761b81112e0216d4b5f8dd7608322685` cùng thay đổi chưa commit trong worktree `web-demo`; đã đọc cả file untracked.
- Ngày khởi tạo báo cáo: 01/11/2026.
- Phạm vi: Ứng dụng demo văn bản và giọng nói.
- Đọc [phân công chung](../BRANCHES.md), [quy định báo cáo](../README.md), [TASKS.md](../../TASKS.md) và [yêu cầu dự án](../../PROJECT_REQUIREMENTS.md).

## Bàn giao commit theo task — 06/11/2026

Theo yêu cầu người dùng sau khi chốt review, đã đóng gói phạm vi mock thành các commit local trên `feat/web-demo`, từ HEAD đầu vào `226ee43`. Worktree: `/home/thangpham/orca/workspaces/HKI-IE501-DoAnTotNghiep/web-demo`; đích tích hợp dự kiến `master`. **Chưa push, chưa merge.** Các câu “chưa commit” trong lịch sử bên dưới mô tả thời điểm review tương ứng.

| Thứ tự | Commit | Task / phạm vi để review |
| --- | --- | --- |
| 1 | `cf2ef1d` | T19: backend API, schema/lỗi, runner và vòng đời engine mock, phục vụ static, cấu hình/phụ thuộc và tests Python |
| 2 | `79aac1f` | T20: API client, chuẩn hóa văn bản, điều khiển dịch, CSS chung và tests module |
| 3 | `59b8f5d` | T21: AudioWorklet/PCM/WAV, luồng transcript → dịch mock, CSS giọng nói và hồi quy phiên thu âm/phản hồi cũ |
| 4 | `a342816` | T22: HTML/bootstrap nối hai tab, HTTP/WAV fixtures, browser suite, helper PNG và ảnh bàn giao |
| 5 | Commit chứa mục này: `docs(T19-T22): ghi nhận review và hoãn tích hợp pipeline` | Bối cảnh/quyết định, hợp đồng frontend, đặc tả, hướng dẫn chạy và báo cáo review |

T20/T21 tách module để review; HTML và bootstrap nối các module nằm ở T22. Các lệnh trong `package.json` được đưa vào lịch sử cùng thời điểm các file test tương ứng xuất hiện; bản cuối khớp bản đã review. Khi chuẩn bị commit chỉ bỏ dòng trống dư cuối `core/config.py`, `core/language.py` và bỏ quyền thực thi trên ảnh PNG; không đổi hành vi ứng dụng. Đã đối chiếu nội dung mã/fixture/ảnh với snapshot trước commit và chạy `git diff --cached --check` theo từng nhóm. Các bộ kiểm thử chức năng giữ bằng chứng ngày 06/11 ở phần chốt review, không tính việc commit là một lượt chạy test mới.

**Việc để sau: adapter/checkpoint chỉ tiếp tục khi nhánh `feat/translation-pipeline` hoàn tất**, theo [quyết định điều phối](../../PROJECT_CONTEXT.md#thứ-tự-tích-hợp-mô-hình-vào-web--06112026). Khi có xác nhận và đầu ra bàn giao, thực hiện đối chiếu hợp đồng rồi kiểm thử tích hợp thật; chưa đánh dấu T19–T22 hoàn thành toàn diện.

## Nhiệm vụ và ranh giới

### Đợt tiếp nối do Codex điều phối — 03/11/2026

- Theo yêu cầu người dùng, Codex nhận vai trò lead xuyên suốt phần web: chia việc, thống nhất giao tiếp, review và trả phát hiện cho Claude Code sửa. Agent triển khai tiếp tục dùng `local[1m]`, effort `max`.
- Phạm vi nhận tiếp: T20 giao diện dịch văn bản; phần kỹ thuật T21 thu âm/upload → transcript chỉnh sửa → dịch với mock; chuẩn bị phục vụ static, kiểm thử trình duyệt và bàn giao T22. Nghiệm thu thật T05/T19–T22 vẫn cần các đầu vào tương ứng.
- Nhánh/worktree: tiếp tục `feat/web-demo` tại `web-demo`, HEAD đầu vào `226ee43`; giữ toàn bộ thay đổi backend chưa commit đã review đạt. Base/đích tích hợp vẫn là `master`; chưa giao commit/push/merge.
- Chia file độc lập: agent UI sở hữu HTML/CSS chung, client API, chuẩn hóa và dịch văn bản; agent giọng nói sở hữu `voice.js`, xử lý PCM/WAV và CSS riêng; agent backend sở hữu phục vụ static và kiểm thử HTTP liên quan. Giao tiếp frontend được ghi tại `ARCHITECTURE.md` trước khi triển khai; coordinator tổng hợp báo cáo để tránh ghi đè.
- Đầu vào/đầu ra: đặc tả §6/§8.2 và backend mock → UI chạy cùng origin, không dùng CDN, nhãn mock từng bước, kiểm tra chống phản hồi cũ và dọn tài nguyên âm thanh. Sau khi các phần độc lập xong sẽ giao kiểm thử tích hợp trình duyệt và cập nhật hướng dẫn.
- Đã đọc tình trạng nhánh pipeline: có mã adapter đang được stage tại worktree riêng; chưa nằm trong nhánh web. Báo cáo upstream nêu các lần chạy mock/fixture, chưa phải baseline được nghiệm thu. Cần đối chiếu hợp đồng trước khi tích hợp; không lấy báo cáo "bàn giao adapter" làm bằng chứng tương thích.
- Trạng thái đợt tiếp nối: **Đã review đạt phạm vi demo mock ngày 06/11/2026**. Đã đóng C16–C24 sau khi đối chiếu mã, kiểm thử và ảnh; giữ kết luận đạt backend mock C01–C15. Chưa nghiệm thu mô hình/ASR thật hoặc đóng các Txx toàn dự án. Theo yêu cầu mới, adapter/checkpoint để sau khi `feat/translation-pipeline` hoàn tất; commit theo task được bàn giao riêng bên dưới, chưa push/merge. Lịch sử review được giữ để đối chiếu trạng thái tại từng thời điểm.

Run Orca: `run_7df7c4d9f4bc`. Ba lệnh khởi chạy đều trả `state=ready`, `agent=claude`, `model=local[1m]`, `effort=max` trên đúng worktree hiện có. Đây là bằng chứng giao việc, chưa phải kết quả triển khai.

| Phần việc | Task / dispatch | Trạng thái giao việc |
| --- | --- | --- |
| T20 giao diện dịch và API client | `task_32c4134d72db` / `ctx_4b6d344daf06` | Worker đã bàn giao; Codex yêu cầu sửa C16–C18 trong lượt tích hợp |
| T21 luồng giọng nói và PCM/WAV | `task_6918e9943251` / `ctx_a76107396307` | Worker đã bàn giao; còn kiểm thử tích hợp trình duyệt |
| Phục vụ static và audit hợp đồng adapter | `task_3f3e5f63f615` / `ctx_35d512fea2ef` | Worker đã bàn giao; đã đọc mã, chờ kiểm tra cùng UI thật |
| Kiểm thử tích hợp trình duyệt và bàn giao (Lượt 1) | `task_b32a7cb0ca85` / `ctx_0be1db3eb759` | Worker báo 93 tests Node, 151 tests Python, 23 tests pipeline đạt; Codex review ngày 04/11 xác nhận bản sửa C16–C18 qua 29 tests liên quan nhưng yêu cầu sửa C19–C22. Tuyên bố 8/8 hành trình trình duyệt chưa đủ bằng chứng, không dùng làm nghiệm thu |
| Sửa C19–C22 và hoàn thiện kiểm thử tích hợp trình duyệt (Lượt 2) | `task_69a67b2e5020` / `ctx_624c2d6d7311` | Worker báo 104 tests Node (90 unit + 14 HTTP), 151 tests Python, 23 tests pipeline và 8 ca browser đạt. Codex chạy 48 tests audio/voice đạt nhưng tái hiện nhánh lỗi còn lại của C19/C20/C22; cần sửa tiếp, chưa chốt UI/voice đạt |
| Khắc phục C19/C20/C22 bổ sung và C23 (Lượt 3) | `task_37ac97ec4e97` / `ctx_a43103aff2e4` | Codex đã đối chiếu các bản sửa được giao qua đọc mã, gồm reset đồng hồ theo phiên. Chưa nghiệm thu: chưa có kết quả test lượt 3 hợp lệ. Sau thông báo `msg_90a4d00c37c7`, dispatch chuyển `failed`, liveness `unverifiable`, terminal `retained`; chưa xác nhận worker đã dừng. Lần thử test gần nhất trước đó bị bộ xét duyệt của Claude chặn (`local[1m] is temporarily unavailable`) |
| Khôi phục cùng task và chẩn đoán classifier | `task_37ac97ec4e97` / `ctx_cc5769e376e8` | Worker bàn giao `succeeded` ngày 06/11. Codex đối chiếu transcript: 97 unit, 14 HTTP, 151 backend, 23 pipeline đạt; 9 journeys DOM đạt. Classifier đã xét duyệt thành công, main model vẫn `local[1m]`/`max`, auto mode bật. Mở C24 vì ảnh mobile trống và ảnh voice thiếu phần kết quả |
| C24 — hoàn thiện bước chụp và kiểm tra ảnh bàn giao | `task_73838da21b60` / `ctx_7517fa4dd017` | Worker bàn giao; ảnh mới hiển thị đạt, 9 journeys browser và 14 HTTP đạt. Codex tái hiện lỗi helper đọc byte PNG chưa bỏ filter nên chưa đóng C24 |
| C24 — sửa kiểm tra pixel PNG | `task_c4b61fd6241a` / `ctx_7197f92e6c95` | Worker bàn giao `succeeded`; Codex review đạt: 20 hồi quy PNG, 9 journeys browser và ảnh thật. Đóng C24; mã ứng dụng giữ nguyên |

#### Chốt review C24 và demo mock — Codex, 06/11/2026

**Kết luận: Đạt phạm vi backend, UI và luồng giọng nói với engine mock; C01–C24 đã được xử lý theo bằng chứng từng lượt.** Đã nhận `worker_done` `msg_47d15bec2263`, đọc mã cuối và đối chiếu các lệnh/tool result thực trong transcript `e6e22fd1-0646-4ad0-931e-b93641657559`. Không còn phát hiện cần sửa trong phạm vi review này. Trạng thái này không thay nghiệm thu checkpoint/ASR thật, kiểm tra micro vật lý hoặc cài mới trong môi trường sạch.

Bản sửa cuối tách decoder vào `scripts/screenshot_png.mjs`, thêm `scripts/screenshot_png.test.mjs` và nối helper vào script browser. Decoder hoàn tác filters 0–4 trước khi đếm màu, kiểm tra CRC/chunk và độ dài scanline, giới hạn dữ liệu giải nén 64 MiB. Phạm vi cố ý giới hạn ở PNG RGB/RGBA 8-bit hoàn toàn đục, không interlace; định dạng khác bị từ chối rõ. Lấy mẫu màu là cách phát hiện ảnh rỗng, không thay việc mở ảnh kiểm tra nội dung UI.

| Kiểm tra lượt cuối | Bằng chứng đã đối chiếu | Kết quả |
| --- | --- | --- |
| `node --test scripts/screenshot_png.test.mjs` | Cùng gradient RGB/RGBA qua filters 0–4 khớp từng byte và cùng 64 màu lấy mẫu; ảnh 2D mixed filters; ảnh đơn sắc >5.000 byte, alpha không hỗ trợ, payload thiếu/thừa và PNG hỏng bị từ chối; 9 ảnh browser được chấp nhận | Exit 0; 20 tests đạt, 0 lỗi; 648.419 ms |
| `node scripts/test_orca_browser_suite.mjs` | 9 journeys và 9 ảnh mới; helper bắt buộc kiểm chứng ảnh. Một lỗi EOF ở lần chụp đầu được retry thành công | Exit 0; bản cuối hoàn tất toàn bộ luồng mock đã định nghĩa |
| Nội dung ảnh 06/07/08/09 | Codex mở trực tiếp: trạng thái đã thu âm và transcript mock, transcript đã sửa cùng bản dịch, bố cục văn bản mobile và điều khiển upload/WAV/ASR mobile | Hiển thị đạt; ảnh mobile 390×844, scale 1 trên Orca |
| Dọn tài nguyên | Log đóng tab `61b1b03b-aeb0-487c-8783-3a33ecbdd9c3`; Codex kiểm tra PID 2461802 không tồn tại, kết nối TCP 41717 trả `ECONNREFUSED` | Server test đã dừng; worker có log danh sách tab rỗng |

Lần chạy helper đầu có 19/20 đạt do một regex thông báo lỗi trong test chưa khớp; worker sửa kỳ vọng và bổ sung trường hợp chunk cắt cụt, rồi chạy lại 20/20 như bảng. Không sửa decoder để bỏ qua dữ liệu hỏng. Các lệnh được chạy với `pipefail` nên ghi log qua `tee` vẫn giữ exit code lỗi. Log cục bộ ở `/tmp/web-demo-c24-png-reGz9K/`; `after.json` ghi SHA-256 và thời gian làm mới 9 ảnh. Hai ảnh tên cũ `06_e2e_asr_success_not_autotranslated.png` và `07_e2e_voice_translation_result.png` không thuộc bộ 9 ảnh của lượt hiện hành.

SHA-256 bản mã đã review: `screenshot_png.mjs` = `e4222d146e6dcbda7b4b5cf14d57b0f8db9f804bb292ebf2cedf6cf0eb2a0bc3`; `screenshot_png.test.mjs` = `508797808dddc373fc70b3711870167a87df359e298981f9b27ef5ce0ff01bd5`; `test_orca_browser_suite.mjs` = `47c83aaed6d354d303fcd015566244623574b66367f56867e7b6af90c8152256`. Snapshot 61 file ứng dụng/backend/tests UI giữ nguyên trong lượt sửa decoder; so với trước C24 chỉ có mô tả suite HTTP đổi ở lượt trước. Vì vậy giữ bằng chứng **97 unit, 14 HTTP, 151 backend và 23 pipeline** đã đối chiếu bên dưới; không chạy lại hoặc cộng trùng các bộ đó.

Giới hạn nghiệm thu còn lại: micro vật lý, ASR tiếng Việt thật, adapter/checkpoint dịch đủ điều kiện, đo chất lượng/độ trễ thật, kiểm tra cài mới và vận hành offline. Browser dùng nguồn âm tổng hợp để kiểm tra PCM/WAV và engine mock; responsive Orca không chứng minh Safari/iPhone vật lý. Nhánh `feat/web-demo`, HEAD đầu vào `226ee43`; chưa commit/push/merge, chưa cập nhật trạng thái nghiệm thu toàn dự án trong `TASKS.md`.

#### Review bản sửa ảnh C24 — Codex, 06/11/2026

Đã xử lý `worker_done` `msg_fb6f72ac4b3d` và đối chiếu transcript `e6e22fd1-0646-4ad0-931e-b93641657559`. So với snapshot SHA-256 của 61 file trước C24, mã ứng dụng/backend/unit không đổi; file HTTP chỉ đổi tên suite để ghi đúng engine mock. Thay đổi chức năng nằm trong script browser: screenshot bắt buộc ném lỗi sau retry, cuộn card giọng nói vào khung và dùng viewport mobile 390×844, scale 1. Đây là kiểm tra responsive trên trình duyệt Orca, không phải Safari hoặc thiết bị iPhone vật lý.

- Lượt cuối `node scripts/test_orca_browser_suite.mjs` hoàn tất 9 journeys, có log chụp đủ 9 ảnh hiện hành và cleanup tab `04a4e114-f5e4-4d8f-84c9-09495faae77d`, server cổng 45285 / PID 2338459. Codex kiểm tra PID không còn tồn tại. Lỗi EOF ở lần chụp đầu được helper retry, không bỏ qua bước ảnh.
- `npm --prefix src/web_app/ui run test:http`: 14 tests đạt, 0 lỗi, 893.748 ms. Lệnh `npm test` từ gốc repo trước đó thất bại vì không có `package.json` tại gốc; không tính là kiểm thử đạt.
- Codex mở trực tiếp ảnh 07: thấy transcript đã sửa, bản dịch, nhãn mock và hướng dẫn sao chép khi thiếu quyền; ảnh 08/09 hiển thị bố cục văn bản/upload trên mobile. Kích thước lần lượt 47.835 / 35.458 / 43.533 byte. SHA-256 ảnh 07: `f17682726270d09b52d8f1bef90d489b5c47ef635358201115e347a8e651a52f`; ảnh 08: `9949ffdca3c4baf6ee8cd715d9029e05d8ef59429abaa32eb3084dd5d3406683`; ảnh 09: `f3aaa1b49811604b0958626ca1abf3b666e5848d10c3b3f66eb01ba1528fdbae`.

**C24 còn lỗi ở bước kiểm chứng ảnh:** `validateScreenshot()` coi byte sau `zlib.inflateSync` là RGB dù PNG scanline vẫn chứa dữ liệu qua filter. Codex gọi trực tiếp helper bằng Node/vm với PNG RGB 8-bit hợp lệ trong bộ nhớ: cùng gradient 256 màu, 256×64, 49.284 byte, filter None được chấp nhận (64 màu được lấy mẫu), filter Sub bị từ chối vì helper đếm nhầm 2 màu. Ảnh đơn sắc cùng kích thước bị từ chối như mong đợi. Các ảnh browser hiện tại dùng filter 1/2/3/4; số `colorsCount` trong log chưa phải số màu pixel đã giải mã. Không dùng phép đếm này làm bằng chứng độc lập về nội dung ảnh.

Đã giao tiếp C24 để giải mã filter đúng trong phạm vi định dạng được hỗ trợ, kiểm tra độ dài dữ liệu và thêm hồi quy cùng pixel qua các filter, ảnh đơn sắc lớn hơn ngưỡng byte, dữ liệu thiếu/hỏng và ảnh browser thật. Bằng chứng hiển thị mới được chấp nhận; chưa chốt helper/đóng C24. Không chạy lại backend/unit/pipeline không bị ảnh hưởng; chưa commit/push/merge.

#### Review bằng chứng lượt khôi phục — Codex, 06/11/2026

Đã xử lý `worker_done` `msg_709778e37ac7`, đối chiếu transcript thực `9ca4e52b-1e22-4ff5-98b2-4693521bf578`, debug log và file ảnh. Transcript không có lệnh Edit/Write sửa mã trong lượt này. Màn hình worker vẫn ghi `local[1m] [max]`, `auto mode on`; debug ghi các lượt `classifier_request_started` với model `cx/gpt-5.6-sol[1m]`, tiếp theo `classifier_request_finished outcome=ok`. **Bước kiểm thử đã được gỡ chặn trong phiên khôi phục.** Đây không phải bằng chứng đã vá lỗi chuyển đổi JSON của 9Router được tái hiện trước đó; Codex không sửa gateway hoặc cấu hình permission.

| Lệnh worker đã chạy | Bằng chứng Codex đã đối chiếu | Giới hạn |
| --- | --- | --- |
| `npm run test:unit --prefix src/web_app/ui` | 97 tests, 21 suites, pass 97 / fail 0; 2.370 s | Kiểm tra mã UI và audio/voice bằng fixture, gồm các nhánh C20/C22/C23 |
| `npm run test:http --prefix src/web_app/ui` | 14 tests, pass 14 / fail 0; 1.011 s | HTTP thật tới backend với engine mock |
| `.venv/bin/pytest src/tests/web_app/ -v --tb=short` | 151 passed, 1 warning; 2.62 s | Có cảnh báo deprecation của TestClient/httpx; lần gọi Python hệ thống trước đó thất bại vì thiếu pytest, đã chạy lại đúng venv |
| `python3 -S -m unittest discover -s src/tests/data_pipeline -t . -p 'test_*.py'` | 23 tests, OK; 0.243 s | Bộ pipeline hiện có, không chạy huấn luyện hay xử lý corpus mới |
| `npm run test:browser --prefix src/web_app/ui` | 9 journeys hoàn tất; log cleanup tab `edd0a92e-901b-4007-bb67-3421e0d3e4ff`, server test cổng 44553 | Assert DOM/PCM/WAV/transport đạt; ảnh bàn giao chưa đạt C24 |

Các lệnh hoàn tất ở trên có tool result không báo lỗi; worker báo exit 0. Worker còn chạy lại `npm test` và có 111 tests đạt, bằng tổng 97 unit + 14 HTTP, không cộng thêm 111 vào số ca độc lập. Codex giữ kết quả theo đúng phiên bản đã kiểm tra, không chạy lại các bộ đã đạt khi chưa có thay đổi liên quan.

**C24 — P2, cần sửa bằng chứng ảnh:** Codex mở trực tiếp hai ảnh `08_e2e_mobile_text_layout.png` và `09_e2e_mobile_voice_controls_scrolled.png`: đều chỉ có một màu nền, kích thước 390×844, 2.742 byte, cùng SHA-256 `7f95ade0271a86feba020d29f2e968022373407dd335605e278e57070ea2500d`. Ảnh `07_e2e_voice_upload_and_translate_result.png` phần lớn trống phía trên và không thấy transcript/bản dịch cần minh họa. `captureScreenshot()` hiện chỉ copy file rồi báo đã lưu; khi lỗi có thể trả `null` nhưng suite vẫn công bố đạt. Đây là khoảng thiếu ở bằng chứng hiển thị, chưa đủ để kết luận ứng dụng hỏng hoặc mobile không hoạt động. Cần xác minh paint/focus/device/scroll, chụp ảnh thật đúng nội dung và làm bước bàn giao ảnh thất bại rõ ràng khi ảnh bắt buộc thiếu/rỗng.

Đã giao C24 trên cùng nhánh/worktree. Lần nối tiếp đầu thất bại ở `terminal_create` (`ctx_4004340e7d82`, không tạo terminal và không gửi prompt); dùng lại terminal cũ cũng bị Orca từ chối nhận diện agent. Sau khi đối chiếu trạng thái, Codex retry **cùng Task C24** bằng worker Claude mới, nhận `ctx_7517fa4dd017` / `term_e0921392-2581-473f-bd68-965075d0b772`, đúng `local[1m]`, effort `max`. Không đóng hay ghi đè terminal cũ. Chưa commit/push/merge; nghiệm thu mô hình/ASR thật và các Txx toàn dự án vẫn chờ phụ thuộc.

#### Chẩn đoán classifier và khôi phục task — Codex, 05/11/2026

Theo yêu cầu kiểm tra lỗi rồi tiếp tục, Codex đã xác minh Claude Code 2.1.318 và gateway 9Router 0.5.112. Endpoint danh sách model trả HTTP 200; cấu hình alias `local` đang định tuyến tới combo Gemini 3.8 Flash. Usage gateway ghi `ok` ở thời điểm sát lỗi classifier cuối của worker cũ. Các dữ kiện này chứng minh gateway có phản hồi, chưa chứng minh classifier nhận được kết quả hợp lệ; cần debug log để xác định nguyên nhân. Theo [tài liệu Claude Code](https://code.claude.com/docs/en/errors#auto-mode-cannot-determine-the-safety-of-an-action), thông báo này có thể xuất hiện khi classifier không tạo được quyết định; không đồng nghĩa test đã được chạy và thất bại.

Lần kiểm tra chi tiết mới bằng `worker-show --full` cho worker cũ trả `observation.status=exited`, `exactWorker=true`, terminal có `exitCause=operator_close`; kiểm tra tiến trình trong WSL không còn Claude/Node ở cwd web-demo. Bằng chứng này bổ sung cho projection `unverifiable` đã ghi ở lượt trước. Giữ terminal cũ được người dùng bảo lưu. Khôi phục trên cùng Task với terminal mới `term_fa58d115-1b85-42f9-927d-8279dc138a1e`; màn hình startup xác nhận model/effort và `auto mode on` đúng yêu cầu.

Lệnh start với `--retry-of ctx_a43103aff2e4` bị từ chối do Task đã ở trạng thái `ready` (không phải failed/blocked). Codex kiểm tra dispatch theo hướng dẫn trả về, rồi start cùng Task đang ready bằng terminal mới, nhận dispatch `ctx_cc5769e376e8`, `state=ready`. Chưa thay đổi cấu hình permission, classifier model hoặc gateway. Hướng dẫn khôi phục yêu cầu thử unit qua Bash bình thường một lần; nếu tiếp tục bị classifier từ chối thì đọc debug log, báo lỗi cụ thể và dừng retry. Chỉ khi được xét duyệt và chạy đạt mới tiếp tục HTTP/browser.

Escalation `msg_stop_18b67e2bce35a82e52668ea5` báo worker cần người dùng xác nhận đọc file hướng dẫn do Codex tạo ở `/tmp`. Đã yêu cầu chọn quyền đọc một lần; task/dispatch vẫn mở. Trạng thái nghiệm thu UI/voice giữ nguyên: **chưa đủ bằng chứng thực thi bản sửa mới**.

Chẩn đoán độc lập tiếp theo tái hiện lỗi giao thức của gateway: POST `/v1/messages`, `stream=false`, có `system` và content block theo Anthropic, với `local[1m]` hoặc trực tiếp `ag/gemini-3.8-flash-high`, đều trả HTTP 200 nhưng body là `object=chat.completion`, `choices`, không có `type=message`, `content` hoặc `stop_reason`. Thêm header nhận diện Claude CLI vẫn có kết quả tương tự. Payload chỉ yêu cầu trả “OK”, không gửi nội dung repo hoặc thông tin xác thực ra đầu ra chẩn đoán. Đây là kiểm tra giao thức model, không phải kiểm thử ứng dụng web.

Mã [nonStreamingHandler.js của 9Router](https://github.com/decolua/9router/blob/master/open-sse/handlers/chatCore/nonStreamingHandler.js) nhánh Gemini/Antigravity tạo kết quả OpenAI rồi trả thẳng, chưa chuyển tiếp sang định dạng Claude khi client yêu cầu Claude. Đường xử lý SSE có bước chuyển đó; cần sửa/kiểm chứng riêng đường JSON. Đây là lỗi tương thích đã tái hiện, phù hợp với triệu chứng classifier không đọc được phản hồi, nhưng còn cần log classifier của lượt mới để chốt liên hệ trực tiếp. Chưa sửa cài đặt 9Router, restart dịch vụ hoặc đổi model/permission. Không kết luận đã gỡ lỗi `temporarily unavailable` chỉ từ HTTP 200.

#### Sự cố điều phối sau review — Codex, 05/11/2026

Lệnh `orca-ide orchestration check --run run_7df7c4d9f4bc` nhận escalation `msg_90a4d00c37c7`: `stop_unverified`, lý do “Agent process stop was requested but never confirmed”, exit code báo trong thông điệp là `-1`. Đây là sự cố trạng thái worker, không phải exit code của một lần chạy kiểm thử.

Codex đã đối chiếu `worker-show`, `worker-list --include-remote` và `worker-read` cho dispatch `ctx_a43103aff2e4`. Hai lệnh trạng thái trả `failed`, liveness `unverifiable`, terminal `retained`. `worker-read` chỉ trả fallback terminal rỗng (`sourceExact=false`, `contentComplete=false`); dù phần terminal ghi `exited`, projection vẫn báo `unverifiable` do `missing_status`. Không có transcript mới hoặc bằng chứng đủ chắc chắn về việc tiến trình agent đã dừng.

**Giữ trạng thái bị chặn, chưa nghiệm thu UI/voice.** Chưa tự retry, release, reset hoặc mở worker thay thế. Điều kiện tiếp tục là Orca xác minh được trạng thái worker trước và cơ chế xét duyệt lệnh hoạt động lại; sau đó mới khôi phục công việc trên cùng Task theo quy trình recovery và chạy các kiểm thử còn thiếu. Không thay đổi mã ứng dụng trong lượt này; kết luận review mã và giới hạn kiểm thử bên dưới giữ nguyên.

#### Review bổ sung bản sửa lượt 3 — Codex, 05/11/2026

Sau thông báo `msg_stop_4ae49d50685281f9ec67a32e`, Codex đã đối chiếu bản sửa đồng hồ: `handleStartRecording()` đặt lại thời gian về 0 trước bước chờ mở micro; Journey 6C assert trạng thái 0 ngay sau Start rồi mới chờ tiến độ dương và phát sự kiện native `ended`. Kiểm tra session của recorder vẫn giữ vai trò loại callback phiên cũ; riêng cờ `isRecording` không phải định danh phiên.

Các bản sửa đã được rà qua mã gồm hủy giai đoạn dịch khi ASR mới bắt đầu, lỗi cấp quyền đến muộn, trạng thái sau dừng thu, reset đồng hồ, clipboard, fixture âm thanh từng phiên, đối chiếu payload WAV thực và kiểm tra cleanup trước khi dọn fixture. Không phát hiện thêm lỗi chặn trong lượt đọc bản sửa cuối này. Kết luận này chỉ áp dụng cho phạm vi mã đã đọc, không khẳng định ứng dụng hoặc bộ kiểm thử đã chạy đạt.

**Trạng thái: Bị chặn ở bước kiểm thử; chưa nghiệm thu UI/voice mock.** Lần thử mới nhất của worker với `node --test src/tests/web_ui/audio.test.mjs` tiếp tục bị bộ xét duyệt tự động từ chối với `local[1m] is temporarily unavailable`; các lần thử npm unit và Python trước đó cũng bị chặn. Không có kết quả thực thi hợp lệ cho code lượt 3. `git diff --check` do Codex chạy đạt (exit 0), chỉ xác minh khoảng trắng của diff được Git theo dõi, không kiểm tra cú pháp JS hoặc hành vi file untracked.

Bước còn lại khi cơ chế xét duyệt thông thường hoạt động: chạy unit UI, HTTP integration và browser Orca theo README; sửa lỗi phát sinh có log; ghi lệnh/exit code/môi trường rồi gửi `worker_done` đúng outcome để Codex review bằng chứng cuối. Chưa dùng ảnh hay kết quả lượt cũ làm bằng chứng cho bản mới. Không đi vòng bằng tiền tố `!`, tắt xét duyệt hoặc đổi công cụ/agent để thực thi lệnh bị chặn. Giữ nguyên task/dispatch, không tạo vòng retry tự động khi điều kiện chưa thay đổi; chưa commit/push/merge hay đóng các Txx phụ thuộc mô hình thật.

#### Review lượt 3 — Codex, 04/11/2026

**Chưa đạt bàn giao UI/voice mock.** Codex đã đọc mã và transcript worker. Bản sửa có helper hủy giai đoạn dịch khi bắt đầu ASR mới, kiểm tra phiên trong các nhánh lỗi cấp quyền/setup, callback `onStop`, ghim page cho mobile và truyền đường dẫn screenshot bằng argv. Đây là thay đổi trong mã, chưa phải kết quả kiểm thử.

- **Bằng chứng bị chặn:** lệnh worker `node --test src/tests/web_ui/audio.test.mjs src/tests/web_ui/voice.test.mjs`, lệnh gửi `worker_done` và lần đọc thông báo sau đó đều bị bộ xét duyệt tự động từ chối vì `local[1m] is temporarily unavailable`. Không có exit code hoặc log test lượt 3 để kết luận đạt. Thu hồi các tuyên bố 108/108 Node, 151/151 Python, 23/23 pipeline và 9/9 browser của lượt này; kết quả có bằng chứng ở lượt trước chỉ áp dụng cho phiên bản khi đó. Không dùng tiền tố `!`, tắt xét duyệt hoặc giả danh worker để báo thành công.
- **C19/C22 — thiếu kiểm tra đúng nhánh:** Journey 6 trong `scripts/test_orca_browser_suite.mjs` bấm Stop sau 500 ms; test `voice.test.mjs` mang tên stop/auto-stop cũng chỉ bấm Stop. Chưa có ca tự chạm giới hạn và track ended xác minh UI, số frame WAV, dừng track/context và khả năng thu tiếp. Journey 8 chỉ xóa một bản dịch đã hoàn tất khi bấm ASR mới; chưa giữ request dịch A rồi trả ASR B trước và thả A sau trên trình duyệt. Hai unit test mới có promise gate cho C20 vẫn chưa chạy. Cần tên ca/ảnh đúng nội dung và bằng chứng thực thi trước khi đóng phát hiện.
- **C22 — trạng thái chờ cấp quyền chưa đồng bộ qua đọc mã:** `handleStartRecording()` gọi `updateRecordUIState()` trước `audioRecorder.start()`; lần render đó thấy recorder còn idle/cancelled nên báo đang thu âm. Sau khi recorder chuyển `requesting_permission` và sau khi `await start()` thành công đều không render lại. Test mới yêu cầu hiện “Đang chờ cấp quyền micro...” ngay sau click không khớp trình tự này. Cần thông báo đúng lúc đang chờ quyền và khi bắt đầu thu, giữ kiểm tra phiên; đây là nhận xét từ mã, chưa phải một lần test đã chạy và thất bại.
- **C23 — P2, copy báo thành công dù chưa sao chép:** `voice.js:handleCopyTranslation()` khi thiếu Clipboard API chỉ gọi Selection/Range, sau đó vẫn hiện `#vp-copied-toast` có nội dung “Đã sao chép!”. Phải chỉ báo thành công sau thao tác copy thành công; trường hợp thiếu API hoặc bị từ chối cần hướng dẫn sao chép thủ công và cho chọn văn bản. Bổ sung kiểm tra success, thiếu API và rejected permission trên mã UI thực.
- **C19 — dọn tab khi chuẩn bị test thất bại:** tạo tab và assert `pageLoaded` nằm trước `try/finally` đóng tab. Nếu trang không ready hoặc eval lỗi tại bước này, tab do test tạo không được đóng. Đưa vòng đời tab vào phạm vi cleanup ngay sau khi nhận page ID và xác minh nhánh thất bại.

Việc tiếp theo thuộc Claude Code: sửa các điểm trên, chạy kiểm thử bằng công cụ thông thường khi bộ xét duyệt hoạt động trở lại, gửi kết quả có log/exit code. Nếu vẫn bị chặn, giữ trạng thái chưa kiểm chứng; Codex không dùng kiểm thử ở công cụ khác để đi vòng quyết định xét duyệt. README và phần trạng thái đặc tả đã được sửa để không công bố hoàn thiện UI. Chưa commit/push/merge; chưa thay đổi trạng thái Txx toàn dự án.

#### Review lại lượt 2 — Codex, 04/11/2026

**Cần sửa tiếp C19, C20 và C22.** Các ca kẹt nút đã báo và điều kiện ASR của C21 đã có bản sửa; bộ kiểm tra `node --test --test-reporter=spec src/tests/web_ui/audio.test.mjs src/tests/web_ui/voice.test.mjs` do Codex chạy đạt 48 tests, exit 0 (445 ms). Các ca bổ sung dưới đây cho thấy phạm vi còn thiếu:

- **C20, phản hồi dịch cũ sau lần ASR mới:** probe gọi `initVoice` thật, hoàn tất ASR A rồi giữ request dịch A; bấm ASR lần nữa, trả transcript B trước, sau đó thả bản dịch A. UI hiện transcript `[MOCK ASR] revised` cùng kết quả `OLD TRANSLATION first`. Bắt đầu ASR mới phải vô hiệu request/kết quả dịch thuộc transcript cũ, ở cả nhánh ASR thành công hoặc lỗi.
- **C22, lỗi cấp quyền của phiên cũ:** start A → cancel → start B thành công → reject permission A bằng `NotAllowedError`; recorder vẫn đang ghi B nhưng `onError` của A vẫn được gửi tới UI hiện hành. `start()` có kiểm tra session ở nhánh thành công nhưng chưa chặn callback/throw của nhánh lỗi cũ; cần bảo vệ cả `handleStartRecording()` phía UI và lỗi setup/addModule.
- **C22, trạng thái UI sau dừng:** Codex mở trang Orca riêng, dùng Web Audio tạo nguồn tổng hợp thay `getUserMedia`, thao tác nút thu âm thật trên DOM; server test có giới hạn 1 giây. Auto-stop tạo WAV 16 kHz, 14.080 frame, 28.204 byte; backend chấp nhận HTTP 200 với `duration_sec=0.88` và `is_mock=true`. Track input đã `ended`, context recorder đã `closed`, nhưng UI vẫn báo “Đang thu âm...”, nút bắt đầu bị ẩn và nút dừng còn hiện. `handleStopRecording()` render trước khi recorder đổi state và không render lại sau khi hoàn tất. Phải đồng bộ UI cho auto-stop, stop chủ động và track ended.
- **C19, kiểm tra mobile cho kết quả sai:** script vẫn gọi `set device` thiếu `--page`; không chọn subtab Upload trước khi kiểm tra drop zone. Probe trình duyệt trả `activeUpload=false`, `clientRects=0`, kích thước `0×0`, ancestor `display:none` nhưng biểu thức `rect.top >= 0 && rect.top <= innerHeight` vẫn trả true. Cần kiểm tra visibility/kích thước thực và đúng viewport/page; bổ sung ca ghi âm cùng các ca phản hồi muộn trên UI thật. Helper chép screenshot còn `execSync` nội suy đường dẫn, cần chuyển argv như phần gọi CLI.

Kiểm tra browser của Codex xác nhận đường thu PCM → WAV bằng nguồn tổng hợp và validation API, không phải micro vật lý hoặc nhận dạng tiếng nói thật. Đã đóng generator, tab review và server do Codex sở hữu sau kiểm tra. Các dòng log script gọi engine mock là “ASR thật” cần đổi thành “gọi API ASR với engine mock”.

#### Review lượt tích hợp — Codex, 04/11/2026

**Kết luận: Cần sửa C19–C22 trước bàn giao UI/voice mock.** C16–C18 đã được đối chiếu mã; Codex chạy `node --test --test-reporter=spec src/tests/web_ui/api_client.test.mjs src/tests/web_ui/translation.test.mjs` đạt 29 tests, exit 0 (183.6 ms). `git diff --check` đạt. Chưa chạy lại bộ HTTP/browser của worker vì phát hiện cách kiểm tra chưa đáng tin cậy dưới đây.

| Mã / ưu tiên | Bằng chứng thực tế | Yêu cầu xử lý |
| --- | --- | --- |
| C19 — P1 | `scripts/test_orca_browser_suite.mjs` chỉ log/chụp hình, không assert kết quả; bước ASR gửi POST không có WAV rồi tự gán transcript. `browser_e2e.test.mjs` chủ yếu gọi HTTP, hai ca XSS/double-submit chỉ kiểm tra đối tượng giả tự viết, không chạy mã UI. Dùng cổng 8000 và tự nhận bất kỳ server có health HTTP 200; lệnh Orca không ghim page ID. Ảnh mobile không đủ chứng minh luồng giọng nói hoạt động | Thay bằng kiểm tra mã UI thật trong trình duyệt, upload WAV thật qua input và assert transcript/mock label/không tự dịch/payload sau chỉnh sửa. Assert failure phải exit khác 0; giữ page ID, truyền CLI bằng argv an toàn, dùng server do test sở hữu hoặc URL opt-in được kiểm chứng, kiểm tra readiness thực. Phân loại rõ unit/HTTP/browser; sửa tài liệu và rút tuyên bố 8/8 chưa được chứng minh |
| C20 — P1 | Probe Node gọi `initVoice` thật với helper DOM của repo và promise gate: chọn file B khi ASR file A đang chờ, rồi thả A → nút vẫn disabled/“Đang nhận dạng...”; sửa transcript trong lúc dịch rồi thả phản hồi cũ → nút vẫn disabled/“Đang dịch...”. Invalidate tăng revision nhưng không hạ cờ busy; finally bỏ qua revision cũ | Mỗi lần hủy/thay input phải giải phóng trạng thái chờ của UI, cho phép gửi nội dung mới và vẫn loại phản hồi cũ. Phủ cả replace/remove file, edit transcript, retry và chuyển tab; chỉnh transcript trong lúc ASR chờ cũng không được bị phản hồi cũ ghi đè |
| C21 — P2 | Probe trên `initVoice` thật: nhập transcript thủ công ngay khi chưa có lần ASR thành công vẫn bật nút dịch. `updateTranslateButtonState` chỉ kiểm tra text và translation health; bắt lỗi ASR không xóa transcript/metadata từ lần trước | Bước dịch giọng nói cần transcript thuộc lần ASR thành công hiện hành; ASR lỗi/no-speech hoặc thay audio phải vô hiệu bước dịch và dữ liệu cũ. Vẫn cho sửa transcript sau ASR thành công và gửi đúng nội dung đã sửa |
| C22 — P1 | Probe `AudioRecorder` thật với hai promise cấp quyền: start A → cancel → start B → resolve A thì state thành recording và track A chưa dừng; resolve B thì state thành idle, track B bị dừng trong khi A còn sống. `_isCancelled` bị reset giữa phiên, thiếu định danh phiên. Chuyển subtab Thu âm → Upload cũng không gọi cancel | Thêm định danh phiên cho mọi bước async, chỉ phiên hiện hành được dùng/tắt tài nguyên của mình. Late permission/setup của phiên cũ phải dừng riêng track/context cũ, không ảnh hưởng phiên mới. Dọn mic khi chuyển sang upload/chọn file/rời tab; kiểm chứng ghi âm tạo PCM/WAV có frame thực trên trình duyệt với nguồn tổng hợp, giữ giới hạn chưa thử micro vật lý |

Các probe do Codex chạy để tái hiện lỗi đều exit 0 và in trạng thái quan sát; exit 0 của probe không có nghĩa ứng dụng đạt. Đây là các phát hiện mới sau lượt worker bàn giao, cần Claude Code sửa và bổ sung kiểm tra hồi quy. Không dùng âm thanh tổng hợp hoặc transcript tự điền để khẳng định ASR thật; phạm vi ASR dự kiến là tiếng Việt, tiếng Tày chưa được hỗ trợ.

#### Review đầu ra từng phần — Codex, 03/11/2026

- Task A báo 32 tests Node trong phần sở hữu và 151 tests Python đạt; Task C báo 151 tests Python (gồm 16 test static mới) và 53 tests Node đạt. Đây là kết quả worker báo, chưa thay thế kiểm thử tích hợp trình duyệt hoặc kết luận review cuối.
- Task B sau đó báo 37 tests Node phần âm thanh/voice đạt (21 audio, 16 voice), 32 tests Node khác và 151 tests Python tiếp tục đạt. Mẫu PCM giả chỉ xác minh xử lý/luồng ứng dụng; chưa có bằng chứng micro vật lý hoặc ASR thật.
- Codex đọc `api/static.py`, các test static và vị trí đăng ký trong `main.py`: chỉ phục vụ trang chủ và hai thư mục assets, không mount catch-all tại `/`. Không thấy lỗi chặn riêng phần static qua lượt đọc này; còn cần xác minh assets/giao diện thực tế trong task tích hợp.
- **C16 — P1, cần sửa:** `api_client.js` dọn timer và external abort listener ngay khi `fetch()` trả headers, trước `res.text()`. Probe độc lập giữ body chưa trả, gọi external abort và chờ quá timeout 20 ms: fetch signal vẫn chưa abort ở khoảng 96 ms; thả body thì request trả success. Phải giữ timeout/hủy đến hết đọc và xử lý body, phân biệt `CLIENT_TIMEOUT`/`AbortError`, dọn tài nguyên trong finally bao trùm toàn yêu cầu. Bổ sung test có body gate hoặc server stream; test chỉ giữ fetch trước headers không đủ.
- **C17 — P2, cần sửa:** `translation.js` chỉ invalidate khi đang gửi; sửa nguồn hoặc đổi chiều sau một lần thành công vẫn giữ kết quả/metadata cũ. Probe: nguồn đổi `source A` → `source B` nhưng kết quả vẫn `[MOCK vi->tyz] source A`; đổi sang `tay-vi` thì nhãn đích thành Tiếng Việt trong khi kết quả vẫn của chiều trước. Cần xóa hoặc đánh dấu rõ kết quả mất hiệu lực, không để copy/metadata khiến người dùng hiểu là bản dịch của nguồn/chiều hiện hành. Rà thêm thất bại khi gửi lại và swap sau hoàn tất; snapshot hoán đổi không được gán timing/model của phép suy luận chiều cũ cho phép dịch chiều mới.
- **C18 — P2, cần sửa:** `translation.js:showError()` luôn thêm đơn vị “ký tự” cho `INPUT_TOO_LONG`, bỏ qua `detail.limit_unit`. Lỗi giới hạn token phải dùng đơn vị đúng, không trình bày giới hạn token thành số ký tự. Bổ sung kiểm tra cả `code_points` và `tokens`.
- Task tích hợp phải sửa C16–C18 rồi kiểm chứng hồi quy và browser trước khi xin Codex review cuối; không sửa assertion hoặc bỏ ca lỗi để đạt số lượng test.

#### Điều kiện tích hợp pipeline thật

Task C đã đối chiếu read-only mã tại worktree `translation-pipeline`. Codex xác nhận bằng đọc `src/models/inference_adapter.py`: `_initialize()` (khoảng dòng 289–311) chuyển sang MOCK khi thiếu checkpoint/đường dẫn hoặc bắt lỗi nạp dù `mock_mode=False`; `translate()` (khoảng dòng 423–438) bỏ qua lỗi chạy và trả bản dịch fallback. Điều này trái hợp đồng không fallback của web; chưa được bật engine thật dựa trên adapter hiện tại.

Các khoảng thiếu cần phối hợp: lifecycle đang nạp trong constructor, ánh xạ chiều `vi-tyz`/`tyz-vi`, cấu trúc kết quả `tgt_text` và metadata/mock, tokenization có `truncation=True`, thiếu manifest/checksum/bundle theo §7. Wrapper web chỉ nên ánh xạ hợp đồng sau khi upstream có đường suy luận đúng; không dùng wrapper để che lỗi fallback/cắt token. Không sửa worktree pipeline hoặc coi các checkpoint mock/fixture là baseline thật trong đợt này. Các điểm này không chặn hoàn thiện UI với backend mock đã có.

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
| T19 | Backend suy luận: kiểm tra đầu vào, chiều dịch, phiên bản mô hình và lỗi | T11, T12 | Chưa làm | Đang làm; review đợt 1 backend mock đạt ngày 03/11/2026: Codex kiểm tra độc lập 135 tests web và 21 ca HTTP thật đạt; chưa merge, chờ T11/T12 để tích hợp và nghiệm thu mô hình thật |
| T20 | Giao diện dịch văn bản và kiểm tra tích hợp với backend | T19 | Chưa làm | Phần mock review đạt ngày 06/11: 97 unit, 14 HTTP, 9 hành trình browser và ảnh bàn giao; C24 đã đóng. T20 toàn diện vẫn Đang làm, chờ T19 và checkpoint T11/T12 |
| T21 | Tích hợp âm thanh → transcript → bản dịch; ghi phạm vi và mẫu demo | T05, T19, T20 | Chưa làm | Phần kỹ thuật mock review đạt, C20–C24 đã đóng. T21 vẫn Đang làm: chưa xác minh micro vật lý hoặc ASR thật tiếng Việt; tiếng Tày không thuộc phạm vi ASR |
| T22 | Chọn checkpoint theo validation, hoàn thiện demo và hướng dẫn vận hành/tái hiện | T16, T17, T20, T21 | Chưa làm | Đang làm: đã chốt bàn giao UI mức mock và cập nhật lệnh tái hiện. Chưa kiểm chứng cài mới trong môi trường sạch; nghiệm thu đầy đủ chờ checkpoint/adapter thật từ pipeline (T11/T12/T16/T17) |

## Việc đã làm và đầu ra thực tế

Lượt review đầu ngày 02/11/2026 chỉ có khung ban đầu và môi trường web, chưa có backend khởi động được. Sau các lượt triển khai và sửa lỗi của Claude Code, Codex đã review đạt phạm vi đợt 1 backend mock ngày 03/11/2026; chi tiết và giới hạn ở mục Review và tích hợp. Các số mục trong cột tiến độ tham chiếu bản đặc tả sau sửa; chưa cập nhật tiến độ chung trong `TASKS.md`.

Các mã `226ee43` trong bảng là HEAD đầu vào của lượt làm việc, không phải commit chứa phần triển khai mới. Thay đổi đợt này vẫn chưa commit.

| Ngày | Txx / việc đã thực hiện | File / commit / run ID | Kết quả và giới hạn |
| --- | --- | --- | --- |
| 02/11/2026 | Review đặc tả liên quan T05, T19–T22 | [SPECS_WEB_DEMO.md](../../docs/SPECS_WEB_DEMO.md); chi tiết bản trước sửa bên dưới | Phát hiện R01–R10; giữ nguyên đầu vào ở lượt review |
| 02/11/2026 | Sửa trực tiếp đặc tả theo yêu cầu tiếp theo | `docs/SPECS_WEB_DEMO.md`, `ARCHITECTURE.md` (mục web), `PROJECT_CONTEXT.md` (đề xuất web) | Đã xử lý R01–R10 ở mức tài liệu; D01/D04 và các phụ thuộc nghiệm thu thật giữ nguyên |
| 02/11/2026 | Ghi hướng dẫn để giao triển khai cho Claude Code | [Đặc tả §8.4–8.5](../../docs/SPECS_WEB_DEMO.md#84-thứ-tự-thực-hiện-và-đợt-đầu-tiên) | Có thứ tự đợt, phạm vi/tiêu chí bàn giao backend mock và nội dung giao việc; chưa khởi chạy agent hoặc triển khai code |
| 02/11/2026 | Review đầu ra Claude Code cho T19 | Working tree trên `226ee43`: `.gitignore`, `.env.example`, requirements web và các package dưới `src/web_app/`, `src/tests/web_app/` | Cần sửa C01–C04 bên dưới; lượt review này chỉ cập nhật báo cáo, giữ nguyên mã triển khai |
| 02/11/2026 | Triển khai Task A (Core, engines mock, WAV) | Claude Code (`task_c62f93553845`, dispatch `ctx_f4e12538e2de`, commit `226ee43`) | Hoàn thành C02 và một phần C01, C03; 62 unit tests cho Core, Translation, ASR và Audio WAV đạt 100% |
| 02/11/2026 | Triển khai Task B (InferenceRunner, hàng đợi FIFO, timeout, cancellation, shutdown) | Claude Code (`task_c805ce4fe37a`, dispatch `ctx_af857a44557f`, terminal `term_1b06a493-7ca7-4cea-aa8e-afe624b46d3d`, run `run_7df7c4d9f4bc`, commit `226ee43`) | Hoàn thành 13 unit tests cho InferenceRunner đạt 100%; bảo toàn worker slot invariant sau timeout/hủy |
| 02/11/2026 | Triển khai Task C (Tích hợp API, Middleware body/request ID, Handlers, Lifespan, Kiểm thử toàn diện và verify server Uvicorn HTTP thật) | Claude Code (`task_756921e5127b`, dispatch `ctx_013d01ec2559`, commit `226ee43`) | Hoàn tất đợt 1 backend mock; xử lý C01–C04 có bằng chứng; 113/113 tests web đạt 100%; verify HTTP server Uvicorn 9/9 PASS; hoàn thiện README/báo cáo |
| 02/11/2026 | Review cuối backend mock T19 | Codex (`term_39daca05-5f81-4088-828c-fbb237026e3d`, commit `226ee43`) | Kết luận CẦN SỬA với 9 phát hiện C05–C13: double response 413/200, unload khi loader chạy, expired queue job, spool leak khi multipart cắt cụt, leak exception message, lỗi pipeline unittest -S, late OOM không chuyển failed, metadata rỗng vẫn ready, invalid JSON encoding trả HTTP_ERROR |
| 02/11/2026 | Sửa lỗi và kiểm thử hồi quy C05–C13 (Task C lượt 2) | Claude Code (`task_a4ad31160f26`, dispatch `ctx_0ad2807ca364`, commit `226ee43`) | Đã sửa C05–C13; 121/121 tests web đạt; 23 tests pipeline chạy tốt với python3 -S stdlib; verify HTTP server thật 11/11 PASS; pin requirements |
| 03/11/2026 | Review lại đợt 1 (R2) | Codex (`term_39daca05-5f81-4088-828c-fbb237026e3d`, commit `226ee43`) | Kết luận CẦN SỬA TIẾP: C05 và C07 pass; mở lại C06, C08, C12; phát hiện C14 mới |
| 03/11/2026 | Sửa dứt điểm C08, C12, C14 và probe C07 (Task C lượt 3) | Claude Code (`task_21f851d696dc`, dispatch `ctx_c8fd9d28d8f7`, commit `226ee43`) | Sửa dứt điểm C08, C12, C14; 131/131 tests web đạt (18 regression tests); 23 tests pipeline python3 -S đạt; verify HTTP server thật 12/12 PASS; pin anyio/starlette |
| 03/11/2026 | Review R3 đợt 1 | Codex (`term_39daca05-5f81-4088-828c-fbb237026e3d`, commit `226ee43`) | C08, C12, C14 và C07 đạt; ghi nhận nhánh C06 còn hở: translation.load() ném exception trong lúc shutdown làm load_engines chuyển failed rồi đi tiếp vào ASR vô điều kiện; cần theo dõi load work trước dispatch và đóng admission toàn diện |
| 03/11/2026 | Sửa triệt để C06 đa pha và theo dõi pre-dispatch (Task C lượt 4) | Claude Code (`task_5131a764bf4e`, dispatch `ctx_6a09d82e3675`, commit `226ee43`) | Đã sửa dứt điểm C06: đóng admission load khi stopping, không chạy ASR khi translation load lỗi lúc shutdown, đếm `_pending_load_count` trước dispatch |
| 03/11/2026 | Review R4 đợt 1 | Codex (`term_39daca05-5f81-4088-828c-fbb237026e3d`, commit `226ee43`) | Phát hiện regression: translation_dispatched/asr_dispatched=False khi load raise exception bình thường làm supervisor đổi failed thành stopping và return, bỏ qua nạp ASR độc lập. Yêu cầu phân biệt lỗi load bình thường (giữ failed, vẫn cho pha sau chạy nếu chưa stopping) với true shutdown |
| 03/11/2026 | Sửa lỗi nạp thông thường & kiểm thử 2 cấu hình degraded thật (Task C lượt 5) | Claude Code (`task_31e242f187da`, dispatch `ctx_507ca2a91dc4`, commit `226ee43`) | Đã sửa dứt điểm nhánh lỗi load bình thường: phân biệt `_is_stopping` với exception; cả 2 cấu hình factory thật (pipeline dịch lỗi + ASR mock khỏe và ngược lại) đều hoạt động đúng thiết kế (503 cho route lỗi, 200 cho route khỏe, health degraded); 135/135 tests web đạt; 23 tests pipeline đạt |
| 03/11/2026 | Review cuối đợt 1 | Codex (`term_39daca05-5f81-4088-828c-fbb237026e3d`, commit `226ee43`) | HTTP server thật do coordinator chạy đạt 21/21 ca; SHA-256 backend/requirements khớp `7c7b70e2084cffa8e8669305023a434d849c360534e638d7c0ba3d29916df6e5`. Phát hiện C15: bộ test còn race với background loading khi test gửi request trước khi fake ASR load xong (nhánh return_whitespace_transcript nhận 503 thay vì 400) |
| 03/11/2026 | Sửa C15 & kiểm chứng 3 process độc lập liên tiếp (Task C lượt 6) | Claude Code (`task_c504279c314e`, dispatch `ctx_bfc33554abb2`, HEAD `226ee43`) | Thêm `client.portal.call(supervisor.wait_loaded)` cho fixture và các TestClient cần engine sẵn sàng; giữ riêng test trạng thái loading. Ba lần chạy pytest độc lập đều đạt 135/135 tests; pipeline stdlib đạt 23 tests. Chỉ sửa test/báo cáo, hash backend/requirements giữ nguyên |
| 03/11/2026 | Review kết thúc đợt 1 sau sửa C15 | Codex; nhánh `feat/web-demo`, HEAD `226ee43`, thay đổi chưa commit | Đạt phạm vi backend mock: chạy độc lập 135 tests web (2.11s), 23 tests pipeline; đối chiếu hash với backend đã đạt 21 ca HTTP thật. Không còn phát hiện chặn bàn giao trong phạm vi đã kiểm tra; toàn T19 vẫn Đang làm |
| 03/11/2026 | Triển khai Task D lượt 1 (Sửa C16–C18, Tích hợp UI + Voice với backend mock) | Claude Code (`task_b32a7cb0ca85`, dispatch `ctx_0be1db3eb759`, terminal `term_19767073-b107-42db-87d6-e63c9639b04b`, commit `226ee43`) | Sửa dứt điểm C16, C17, C18 có test hồi quy; 93 tests Node, 151 tests Python, 23 tests pipeline đạt; Codex review ngày 04/11 xác nhận C16–C18 qua 29 tests nhưng phát hiện C19–C22 |
| 04/11/2026 | Triển khai Task D lượt 2 (Sửa C19–C22, Tách tầng kiểm thử unit/HTTP/browser, Upload WAV thật và tự động hóa kiểm thử trình duyệt có assertions) | Claude Code (`task_69a67b2e5020`, dispatch `ctx_624c2d6d7311`, terminal `term_90d00dcdb337ecdd82859cf755fc9f5a`, commit `226ee43`) | Sửa dứt điểm C19–C22; 104/104 tests Node đạt (90 unit + 14 http integration, exit 0, 0.99s); 151/151 tests Python web đạt (exit 0, 2.49s); 23/23 tests pipeline stdlib đạt (exit 0, 0.24s); kịch bản kiểm thử Trình duyệt nhúng Orca tự sinh cổng test ngẫu nhiên, ghim pageId, nạp WAV thật qua input và assert kết quả đạt 8/8 journeys (exit 0), lưu 9 ảnh tại `docs/screenshots/`; cập nhật tài liệu ranh giới ASR tiếng Việt và loại trừ tiếng Tày; chờ Codex review |
| 04/11/2026 | Triển khai Task D lượt 3 (bản sửa C19/C20/C22) | Claude Code (`task_37ac97ec4e97`, dispatch `ctx_a43103aff2e4`, terminal `term_b21fe0a713492681270dfe32842fc3b7`, HEAD `226ee43`) | Đã sửa mã, chưa xác minh thực thi. Codex đối chiếu transcript: bộ xét duyệt chặn lệnh test và `worker_done` vì model tạm thời không khả dụng. Thu hồi số lượng test/bộ browser đạt từng ghi ở dòng này; xem review lượt 3 và phát hiện C23 |


## Kiểm tra đã chạy

| Ngày | Lệnh / môi trường | Kết quả thực tế | Log / giới hạn |
| --- | --- | --- | --- |
| 02/11/2026 | `git status --short --branch`, `git branch -a -vv`, `git worktree list --porcelain`, `git rev-parse HEAD`; đối chiếu file bằng `rg` và Python `pathlib` | Đúng nhánh/worktree `web-demo`; chưa có `src/web_app/`, `src/tests/web_app/`, hai file requirements web hoặc `configs/web_config.json` | Chưa có ứng dụng để chạy bộ kiểm thử web |
| 02/11/2026 | `python3` với `importlib.metadata`; thí nghiệm timeout bên dưới | Python 3.12.3, AnyIO 4.14.2; semaphore có sức chứa 1 nhưng quan sát được 2 worker chạy đồng thời sau timeout | Thử cơ chế bằng hàm giả lập; không chạy FastAPI, mô hình dịch hoặc ASR |
| 02/11/2026 | `python3` đọc Markdown bằng `pathlib`/`re`, parse JSON bằng `json.loads`, gọi `bash -n` cho các block Bash; đối chiếu link/mục và khoảng trắng | 6 ví dụ JSON hợp lệ, 4 đoạn Bash đúng cú pháp; không có link nội bộ/tham chiếu mục hỏng hoặc giá trị cũ bị loại còn sót trong đặc tả | Chỉ kiểm tra tĩnh tài liệu; không thực thi lệnh cài/chạy ứng dụng |
| 02/11/2026 | `git diff --check`; kiểm tra whitespace riêng trong đặc tả chưa được Git theo dõi | Không phát hiện lỗi khoảng trắng | Chưa chạy test web hoặc mô hình thật vì chưa có mã/đầu vào |
| 02/11/2026 | Sau khi thêm §8.4–8.5: `git diff --check`, Python kiểm tra Markdown và link nội bộ; đối chiếu hash của `git diff --cached --binary` trước/sau | 16 liên kết hợp lệ, không lỗi fence/khoảng trắng; nội dung đã stage của người dùng giữ nguyên | Chỉ sửa đặc tả/báo cáo; phần bổ sung mới chưa stage hoặc commit |
| 02/11/2026 | `.venv/bin/python -m pip check` | Exit 0: `No broken requirements found.` | Pinned exact versions: fastapi 0.162.0, uvicorn 0.54.0, pydantic 2.14.2, pydantic-settings 2.16.2, python-multipart 0.0.33, pytest 9.2.0, httpx 0.28.1 |
| 02/11/2026 | `python3 -S -m unittest discover -s src/tests -t . -p 'test_*.py'` | Exit 0: 23 tests đạt (0.286s) | Môi trường Python stdlib thuần túy (-S) đạt 23/23 tests pipeline, không bị ảnh hưởng bởi import test web nhờ cơ chế load_tests |
| 02/11/2026 | `.venv/bin/python -m pytest src/tests/web_app/test_core.py src/tests/web_app/test_engines.py src/tests/web_app/test_audio.py -v --tb=short` | Exit 0: 62 tests đạt (0.31s) | Toàn bộ 62 tests thuộc phạm vi Task A đạt: 16 core (Unicode NFC, White_Space trim, config validation, deadlines hữu hạn, exceptions), 13 engines (lifecycle, mock metadata, translate, transcribe, factories), 33 audio (validate_wav, biên 30s, container/chunks, tách mã lỗi) |
| 02/11/2026 | `.venv/bin/python -m pytest src/tests/web_app/test_runner.py -v --tb=short` | Exit 0: 13 tests đạt (0.42s) | Toàn bộ 13 tests thuộc phạm vi Task B đạt: hàng đợi FIFO, queue timeout, cancel queued/running, execution timeout, shutdown |
| 02/11/2026 | `.venv/bin/python -m pytest src/tests/web_app/ -v --tb=short` | Exit 0: 121 tests đạt (1.93s) | Toàn bộ 121 tests web đạt 100%: 16 core, 13 engines, 33 audio, 13 runner, 6 health/models, 15 translate, 10 asr, 7 errors/lifecycle, 8 regression tests chuyên biệt C05–C13 |
| 03/11/2026 | `.venv/bin/python -m pip check` | Exit 0: `No broken requirements found.` | Pinned exact versions gồm cả anyio 4.16.0 và starlette 1.10.0 trong requirements-web.txt |
| 03/11/2026 | `python3 -S -m unittest discover -s src/tests -t . -p 'test_*.py'` | Exit 0: 23 tests đạt (0.189s) | Môi trường stdlib thuần túy (-S) tiếp tục đạt 23/23 tests pipeline, độc lập hoàn toàn với web |
| 03/11/2026 | `python3 -S -m unittest discover -s src/tests/data_pipeline -t . -p 'test_*.py'` | Exit 0: 23 tests đạt (0.188s) | Chạy riêng sub-package pipeline đạt 23/23 tests |
| 03/11/2026 | `.venv/bin/python -m pytest src/tests/web_app/ -v --tb=short` (worker chạy 3 process độc lập xác minh C15) | Lần 1: 135 passed (1.96s), exit 0<br>Lần 2: 135 passed (1.88s), exit 0<br>Lần 3: 135 passed (1.91s), exit 0 | Các test cần engine sẵn sàng đã chờ hoàn tất nạp; không tái hiện C15 trong ba lần chạy này |
| 03/11/2026 | `.venv/bin/python -m pytest src/tests/web_app/ -q` (Codex chạy độc lập sau sửa C15) | Exit 0: 135 passed, 1 warning (2.11s) | Warning Starlette TestClient sử dụng httpx đã deprecated; không có test thất bại. Chưa kiểm thử UI hoặc mô hình thật |
| 03/11/2026 | `python3 -S -m unittest discover -s src/tests/data_pipeline -t . -p 'test_*.py'` (Codex chạy độc lập) | Exit 0: 23 tests đạt | Kiểm tra pipeline trong môi trường chỉ có thư viện chuẩn |
| 03/11/2026 | Kiểm thử máy chủ HTTP thật Uvicorn do Coordinator chạy độc lập | 21/21 ca PASS (HTTP 200, 400, 404, 405, 413, 503) | Xác minh độc lập bởi Codex coordinator trên backend hiện tại: 4 endpoint, hai chiều dịch, WAV, các mã lỗi, chunked JSON/multipart quá hạn mức, multipart language cắt cụt, hai cấu hình degraded bằng factory thật (pipeline/mock và mock/whisper) |
| 03/11/2026 | `npm test --prefix src/web_app/ui` | Exit 0: 93 tests đạt (0.42s) | Toàn bộ 93 tests frontend đạt 100%: 14 api_client, 21 audio, 11 text_utils, 19 translation, 16 voice, 12 browser_e2e (bao gồm test hồi quy C16 body stream gate, C17 invalidate/swap metadata, C18 tokens vs code_points) |
| 03/11/2026 | `.venv/bin/python -m pytest src/tests/web_app/ -v --tb=short` | Exit 0: 151 tests đạt (2.50s) | Toàn bộ 151 tests backend đạt 100% bao gồm cả 16 static UI tests, 13 runner, 33 audio, 62 core/engines và các tests hồi quy C05–C15 |
| 03/11/2026 | `python3 -S -m unittest discover -s src/tests/data_pipeline -t . -p 'test_*.py'` | Exit 0: 23 tests đạt (0.256s) | Môi trường Python stdlib thuần túy (-S) tiếp tục đạt 23/23 tests pipeline độc lập |
| 04/11/2026 | `node --test --test-reporter=spec src/tests/web_ui/api_client.test.mjs src/tests/web_ui/translation.test.mjs` (Codex chạy độc lập) | Exit 0: 29 tests đạt (183.6 ms) | Xác nhận độc lập bản sửa C16–C18; phát hiện C19–C22 |
| 04/11/2026 | `npm run test:unit --prefix src/web_app/ui` | Exit 0: 90 tests đạt (0.41s) | Toàn bộ 90 tests unit frontend đạt: api_client (14), audio (22 gồm C22 deferred permission race), text_utils (11), translation (17 gồm XSS/double-submit trên product code), voice (26 gồm C20 busy reset/stale discard, C21 ASR prerequisite gating/failure reset, C22 mic cancel on upload) |
| 04/11/2026 | `npm run test:http --prefix src/web_app/ui` | Exit 0: 14 tests đạt (1.21s) | Chạy Uvicorn test riêng biệt trên cổng động ngẫu nhiên do test tự sinh, pin mock, kiểm tra static serving, MIME types, path traversal, REST APIs và upload WAV thật qua multipart |
| 04/11/2026 | `npm test --prefix src/web_app/ui` | Exit 0: 104 tests đạt (0.99s) | Chạy trọn vẹn 104 tests (90 unit + 14 http integration) đạt 100% |
| 04/11/2026 | `node scripts/test_orca_browser_suite.mjs` | Exit 0: 8/8 journeys đạt | Kịch bản tự động hóa trên Trình duyệt nhúng Orca: tự tìm cổng trống, chạy máy chủ test riêng chỉ dừng PID mình sở hữu, ghim pageId cho mọi lệnh (eval/screenshot/close), nạp WAV 16kHz mono thật qua DOM input, assert transcript backend và nhãn mock, assert không tự dịch, sửa transcript và assert dịch đúng snapshot, kiểm tra responsive mobile iPhone 12 cuộn voice controls vào viewport, lưu 9 ảnh tại docs/screenshots/ |
| 04/11/2026 | `.venv/bin/python -m pytest src/tests/web_app/ -v --tb=short` | Exit 0: 151 tests đạt (2.49s) | Toàn bộ 151 tests backend đạt 100% bao gồm cả 16 static UI tests, 13 runner, 33 audio, 62 core/engines và các tests hồi quy C05–C15 |
| 04/11/2026 | `python3 -S -m unittest discover -s src/tests/data_pipeline -t . -p 'test_*.py'` | Exit 0: 23 tests đạt (0.24s) | Môi trường Python stdlib thuần túy (-S) tiếp tục đạt 23/23 tests pipeline độc lập |
| 04/11/2026 | `git diff --check` | Exit 0 | Không còn lỗi khoảng trắng hay dòng trống thừa cuối file |


## Vướng mắc và bước tiếp theo

- Phụ thuộc còn thiếu: Demo mock đã review đạt và đóng C24. Khảo sát mẫu audio, nhận dạng tiếng nói thật (T05/T21) và checkpoint/adapter pipeline thật (T11/T12/T16/T17/T22) chưa đủ đầu vào nghiệm thu; cần kiểm tra micro vật lý, cài mới và vận hành offline trước bàn giao đầy đủ.
- Thay đổi giao tiếp cần phối hợp: Chốt adapter dùng chung, ánh xạ chiều dịch/token và hợp đồng checkpoint với pipeline tại `ARCHITECTURE.md`; xem R04.
- Bước tiếp theo: **Để adapter/checkpoint làm sau khi nhánh `feat/translation-pipeline` hoàn tất**, theo [quyết định ngày 06/11/2026](../../PROJECT_CONTEXT.md#thứ-tự-tích-hợp-mô-hình-vào-web--06112026). Khi upstream bàn giao đủ điều kiện mới đối chiếu hợp đồng và kiểm thử tích hợp T19/T20/T22; khảo sát ASR thật vẫn cần mẫu tiếng Việt được phép dùng. Người dùng đã giao commit local theo task; chưa giao push/merge.

## Review và tích hợp

- Trạng thái nhóm: **Đang làm** các T19–T22 theo phụ thuộc nghiệm thu thật; phạm vi backend/UI/voice mức mock đã review đạt ngày 06/11.
- Kết luận hiện hành: **Đạt phạm vi demo mock; C01–C24 đã được xử lý theo các ca hồi quy và bằng chứng đã đối chiếu.** Không còn phát hiện cần sửa trong lượt review này; chưa kết luận chất lượng mô hình thật hoặc nghiệm thu toàn diện.
- Người / ngày review hiện hành: Codex / 06/11/2026; chi tiết lượt khôi phục ở đầu báo cáo. Phần C01–C15 bên dưới giữ bằng chứng review backend ngày 03/11/2026.
- Tiến độ xử lý các phát hiện từ kết quả triển khai và sửa lỗi của Claude Code:
  - **C01 (P1): ĐÃ XỬ LÝ CÓ BẰNG CHỨNG.** Hoàn thiện toàn bộ `src/web_app/main.py`, `core/schemas.py`, `core/logging.py`, `services/supervisor.py`, `services/inference_runner.py`, `services/asr/audio.py`, `api/middleware.py`, `api/error_handlers.py`, `api/utils.py`, `api/router.py` và 4 route API (`/api/health`, `/api/models`, `/api/translate`, `/api/asr/transcribe`). Uvicorn khởi động bình thường, phục vụ trọn vẹn cả 4 API và xử lý lỗi chuẩn tắc.
  - **C02 (P1): ĐÃ XỬ LÝ CÓ BẰNG CHỨNG.** Hiện thực hoàn chỉnh `normalize_and_trim_text` tại `src/web_app/core/language.py` theo đúng spec §4.3 (Unicode NFC + trim toàn bộ 25 ký tự whitespace), có 6 unit tests chuyên biệt kiểm chứng.
  - **C03 (P1): ĐÃ XỬ LÝ CÓ BẰNG CHỨNG.** Có 135 tests tự động trong `src/tests/web_app/` cho các kịch bản backend dùng mock/fake; Codex chạy độc lập đạt 135/135 tests (exit 0, 2.11s). Chưa bao phủ phần UI và mô hình thật của ma trận §8.2.
  - **C04 (P2): ĐÃ XỬ LÝ CÓ BẰNG CHỨNG.** `README.md` đã được cập nhật đầy đủ hướng dẫn cài đặt, chạy test và khởi động máy chủ API mock đã kiểm chứng; báo cáo nhóm ghi đầy đủ log HTTP thực tế, số lượng test và tài liệu bàn giao.
  - **C05 (P1): ĐÃ XỬ LÝ CÓ BẰNG CHỨNG.** Sửa `src/web_app/api/middleware.py`: ngắt ngay khi vượt hạn mức bằng `BodySizeLimitExceeded`, chặn app gửi response bằng `send_wrapper`, trả đúng MỘT response 413 `REQUEST_TOO_LARGE`. Probe coordinator xác nhận chỉ trả `[413]`.
  - **C06 (P1 - ĐÃ XỬ LÝ THEO CÁC CA HỒI QUY):**
    - Đóng admission cho MỌI pha load ngay khi bắt đầu stopping, kể cả khi translation load ném exception: bắt exception và kiểm tra `_is_stopping`, lập tức giữ state `stopping`, không overwrite thành `failed` và **tuyệt đối không chuyển sang pha ASR**.
    - Phân biệt rành mạch giữa lỗi load bình thường khi khởi động (`self._is_stopping is False`) và true shutdown (`self._is_stopping is True`): khi load translation lỗi bình thường (ví dụ cấu hình pipeline chưa có weights), trạng thái giữ đúng `failed`, bỏ qua validation nhưng vẫn cho phép pha ASR độc lập chạy tiếp để nạp mock ASR khỏe mạnh.
    - Cả 2 cấu hình degraded dùng factory thật của repo đều đạt: (1) pipeline dịch lỗi + ASR mock khỏe -> translate 503, asr 200, health degraded; (2) mock dịch khỏe + whisper ASR thiếu weights -> translate 200, asr 503, health degraded.
    - Theo dõi cả load work đã được nhận/chờ dispatch thông qua `_pending_load_count` lấy trước khi gọi `run_sync`, loại bỏ hoàn toàn race window mà supervisor thấy idle và gọi `unload()` trước khi thread load bắt đầu.
    - Luồng worker thread khi thức dậy kiểm tra `should_run = not self._is_stopping`, nếu supervisor đã stopping thì bỏ qua việc gọi `engine.load()`.
  - **C07 (P1): ĐÃ XỬ LÝ CÓ BẰNG CHỨNG.** Sửa `src/web_app/services/inference_runner.py`: worker loop kiểm tra `now >= candidate.queue_deadline` trước khi gọi `func`, loại bỏ job hết hạn với 504 phase=queue, không gọi engine. Test hồi quy với Timer release worker trong lúc event loop bị stall `time.sleep(0.15)` xác nhận `job_b_called is False`.
  - **C08 (P2): ĐÃ XỬ LÝ CÓ BẰNG CHỨNG.** Trong `SafeASRMultiPartParser(max_files=1, max_fields=1)`, theo dõi trạng thái container bằng `_ended` (gọi từ callback `on_end`) và `_part_in_progress`. Từ chối mọi body thiếu boundary kết thúc (`--B--`) hoặc có part dở dang (như part language bị cắt cụt) với 400 `INVALID_INPUT`, không gọi ASR/inference. Đóng 100% spool files đã tạo trong `finally`.
  - **C09 (P2): ĐÃ XỬ LÝ CÓ BẰNG CHỨNG.** Sửa `src/web_app/api/routes/translate.py` và `src/web_app/api/routes/asr.py`: public error message cố định an toàn, không chứa `{e}` hay file paths, sentinels; log chi tiết nội bộ với `request_id`.
  - **C10 (P2): ĐÃ XỬ LÝ CÓ BẰNG CHỨNG.** Sửa `src/tests/web_app/__init__.py`: định nghĩa `load_tests` để trả về empty `TestSuite` khi chạy trong môi trường stdlib thuần túy (`python3 -S`), giúp `python3 -S -m unittest discover -s src/tests -t . -p 'test_*.py'` đạt 23/23 tests exit 0 mà không cần cài web. Cập nhật `README.md` lệnh `src/tests/data_pipeline`.
  - **C11 (P1): ĐÃ XỬ LÝ CÓ BẰNG CHỨNG.** Wire `on_fatal_error` từ `InferenceRunner` sang `EngineSupervisor.handle_fatal_error`, phát hiện `MemoryError` muộn (kể cả sau khi request đã timeout/hủy) và chuyển trạng thái engine sang `failed`, health `degraded`, các request tiếp theo trả 503 `MODEL_NOT_READY`.
  - **C12 (P2): ĐÃ XỬ LÝ CÓ BẰNG CHỨNG.** Kiểm tra toàn bộ hợp đồng metadata bắt buộc: `artifact_id`, `checkpoint_version`, `tokenizer_version`, `model_id`, tính nhất quán kiểu boolean `is_mock` vs `engine_type` cho cả dịch và ASR. Endpoint `/api/health` và `/api/models` đọc 100% snapshot an toàn từ supervisor, không gọi getters có thể throw/block trong request.
  - **C13 (P2): ĐÃ XỬ LÝ CÓ BẰNG CHỨNG.** Chuẩn hóa `src/web_app/api/error_handlers.py`: `http_exception_handler` chuyển HTTP 400 và lỗi decode body (`b'\xff'`) về đúng `error_code: "INVALID_INPUT"` theo §4.2, loại bỏ mã ngoài hợp đồng như `HTTP_ERROR`.
  - **C14 (P1): ĐÃ XỬ LÝ CÓ BẰNG CHỨNG.** Sửa `InferenceRunner.start()`: cấm tái khởi động (`RuntimeError`) khi runner đang dừng hoặc worker threads trước đó chưa kết thúc hoàn toàn; `_worker_loop` tự động drain và thoát sạch sẽ sau shutdown grace exhaustion mà không bị treo vô hạn; worker thread luôn hoàn tất future trước khi thoát; shutdown lặp lại an toàn.
  - **C15 (P2 - ĐÃ XỬ LÝ CÓ BẰNG CHỨNG):** Thêm helper `wait_client_loaded(client: TestClient)` dùng `client.portal.call(supervisor.wait_loaded)` cho fixture và các TestClient cần engine sẵn sàng; không dùng sleep cố định để chờ ready. Test cố ý kiểm tra loading giữ luồng riêng, chỉ chờ sau khi mở event gate. Worker chạy ba process pytest đều đạt 135/135; Codex đọc lại cách đồng bộ và chạy độc lập cũng đạt 135/135. Kết quả này xác nhận ca lỗi đã phát hiện, không bảo đảm không còn mọi race condition.
  - **C16 (P1): ĐÃ XỬ LÝ CÓ BẰNG CHỨNG.** `src/web_app/ui/js/api_client.js`: gom `fetch()` và `res.text()` vào chung một khối `try ... catch ... finally`; `timeoutTimer` và external abort listener được duy trì hoạt động trong suốt quá trình đọc body stream; phân biệt rõ `CLIENT_TIMEOUT` (mã client timeout) và `AbortError` (chủ động hủy); bổ sung 2 test hồi quy có body stream gate kiểm chứng ngắt đọc body stream.
  - **C17 (P2): ĐÃ XỬ LÝ CÓ BẰNG CHỨNG.** `src/web_app/ui/js/translation.js`: hàm `checkSourceChanged()` tự động xóa kết quả cũ và metadata ngay khi người dùng chỉnh sửa văn bản nguồn hoặc đổi chiều dịch dropdown; trong `handleSwap()`, xóa hoàn toàn metadata/timing của chiều cũ và không gán cho trạng thái đảo; khi bắt đầu `translate()`, xóa sạch kết quả cũ tránh để lại kết quả cũ khi request sau gặp lỗi mạng hoặc 503. Bổ sung 4 test hồi quy chuyên biệt.
  - **C18 (P2): ĐÃ XỬ LÝ CÓ BẰNG CHỨNG.** `src/web_app/ui/js/translation.js` và `src/web_app/ui/js/voice.js`: hàm `showError()` và `formatErrorMessage()` đọc trường `detail.limit_unit`, phân biệt rành mạch giữa `tokens` (đơn vị: token) và `code_points` (đơn vị: ký tự); bổ sung 2 unit test cho cả hai trường hợp.
  - **C19 (P1): CÓ BẢN SỬA, CHỜ BỘ XÉT DUYỆT ĐỂ CHẠY KIỂM CHỨNG.** `scripts/test_orca_browser_suite.mjs` đã được cập nhật hoàn chỉnh:
    1. Đưa vòng đời tab vào khối `try/finally` ngay sau khi nhận `pageId` (bảo đảm đóng tab kể cả khi chuẩn bị test thất bại).
    2. Ca Journey 6 cấp stream live độc lập cho từng phiên thu (`createLiveSyntheticFixture` đăng ký cleanup ngay khi tạo context, có timeout race 2s cho `ctx.resume()`, dọn dẹp các handle an toàn trong finally).
    3. Ca 6C khai báo và kiểm tra trực tiếp phần tử `#vp-timer` (`timerEl`), xác minh reset về 00:00 ngay sau khi Start, ném lỗi nếu timeout chờ PCM, xác nhận `track.readyState === 'live'` và listener native `track.onended` tồn tại trước khi phát sự kiện native `ended` mà không bấm nút Stop.
    4. `assertWavAttributes` kiểm tra độc lập `actualPayloadBytes = buf.byteLength - 44`, so sánh `dataSize === actualPayloadBytes`, kiểm tra `Number.isInteger(frames) && frames > 0`, và kiểm tra trần tuyệt đối `frames <= 32000` (chính xác trần 2s) cho cả 3 ca 6A, 6B, 6C.
    5. Ca Journey 8 ghi nhận rõ ràng `signalWasAborted === true`, outcome `AbortError`, assert thứ tự sự kiện `sequence`, assert transcript B trên DOM không bị bản dịch cũ của A ghi đè.
    6. Ca Journey 7 assert feedback copy trung thực trên DOM thật (`validCopyFeedback`); Journey 9 kiểm tra responsive mobile iPhone 12 chọn đúng subtab Upload và assert kích thước/tọa độ thật; chuyển đổi screenshot dùng `execFileSync('wslpath')` không qua shell.
  - **C20 (P1): CÓ BẢN SỬA, CHỜ KIỂM THỬ LƯỢT 3.** `voice.js` xây dựng helper chuyển trạng thái tập trung `resetTranslationStage()` và `resetAsrAndDependentStages()`, hủy request dịch và tăng revision ngay khi bắt đầu ASR mới; bổ sung 2 unit test có promise gate (cho cả nhánh ASR B thành công và lỗi) và kịch bản Journey 8 trên trình duyệt thật. Chờ bộ xét duyệt để chạy và lấy exit code.
  - **C21 (P2): ĐÃ XỬ LÝ CÓ BẰNG CHỨNG.** `src/web_app/ui/js/voice.js`: thêm biến trạng thái `hasSuccessfulAsr`; `updateTranslateButtonState()` kiểm tra `hasSuccessfulAsr && hasText && isViTayReady`; người dùng gõ tay transcript khi chưa có ASR thành công trên âm thanh hiện hành thì nút Dịch luôn bị vô hiệu; khi ASR gặp lỗi (hoặc no speech) hoặc người dùng thay đổi/xóa file âm thanh, lập tức xóa transcript cũ, xóa metadata cũ, đặt `hasSuccessfulAsr = false` và vô hiệu nút Dịch; sau khi ASR thành công, người dùng sửa transcript thì nút Dịch vẫn bật và dịch đúng snapshot đã sửa. Đã bổ sung 4 test hồi quy chuyên biệt trong `voice.test.mjs`.
  - **C22 (P1): CÓ BẢN SỬA, CHỜ BỘ XÉT DUYỆT ĐỂ CHẠY KIỂM CHỨNG.** `audio.js` và `voice.js`:
    1. Thêm `onStateChange` và `_changeState(newState)` vào `AudioRecorder`; `voice.js` đồng bộ `updateRecordUIState()` đúng thời điểm đang chờ quyền ("Đang chờ cấp quyền micro..."), đang thu ("Đang thu âm..."), và sau khi dừng; đặt lại đồng hồ `updateTimerDisplay(0, limits.max_audio_duration_sec)` ngay khi bắt đầu phiên mới (`handleStartRecording`) và bảo vệ callback `onProgress` với `if (isRecording)`.
    2. Bổ sung callback `onStop` và bọc phục hồi nút Bắt đầu thu âm trong `finally` của `handleStopRecording()`.
    3. Bổ sung unit test cho tự chạm giới hạn (auto-stop `onMaxDuration` tự nhiên qua timer) và ngắt track đột ngột (`audioTrack.onended`), dọn dẹp sạch sẽ trong `finally`.
    4. Kịch bản browser Journey 6C mô phỏng track ended thực sự qua `fixture.track.stop()` và `fixture.track.dispatchEvent(new Event('ended'))` mà không bấm Stop; ca 6B kiểm tra auto-stop chính xác trần 32.000 frames.
  - **C23 (P2): ĐÃ SỬA TRONG MÃ, CHỜ KIỂM THỬ.** `voice.js:handleCopyTranslation()` kiểm tra chặt chẽ `copySuccess`, chỉ hiển thị `#vp-copied-toast` ("Đã sao chép!") khi sao chép thực sự thành công; trường hợp thiếu API hoặc bị từ chối quyền thì chọn vùng text trong DOM và hiển thị cảnh báo lỗi hướng dẫn người dùng nhấn Ctrl+C. Đã bổ sung unit test kiểm chứng cả 3 nhánh (success, rejected permission, missing API) trong `voice.test.mjs` và assert trên DOM trình duyệt thật.
  - *Nguồn bằng chứng:* Các lượt triển khai do Claude Code thực hiện; kết luận review cuối và các kiểm tra độc lập ghi rõ Codex ở bảng trên và phần dưới.
- Commit/PR triển khai đã tích hợp: **Chưa commit, push hoặc merge**; HEAD vẫn là `226ee43c761b81112e0216d4b5f8dd7608322685`.
- Txx đủ điều kiện cập nhật trong `TASKS.md`: Có thể ghi mốc backend mock đợt 1 sau khi người tích hợp tiếp nhận; chưa đánh dấu toàn T19 hoàn tất, vẫn chờ checkpoint T11/T12 thật. Đợt này không sửa `TASKS.md`.

### Kết luận review cuối đợt 1 — Codex, 03/11/2026

**Đạt phạm vi backend mock theo đặc tả §8.4.** Không còn phát hiện chặn bàn giao trong phạm vi đã kiểm tra sau các bản sửa C01–C15. Claude Code thực hiện mã và test; Codex điều phối, review và cập nhật kết luận này.

- Kiểm tra độc lập cuối: 135 tests web đạt (2.11s), 23 tests pipeline stdlib đạt, `pip check` và `git diff --check` đạt.
- Máy chủ Uvicorn thật đạt 21/21 ca HTTP: đường đi thành công của bốn endpoint, hai chiều dịch, WAV, lỗi đầu vào, body truyền chunk vượt giới hạn, multipart cắt cụt và trạng thái degraded khi một engine không nạp được. Các phản hồi lỗi được kiểm tra request ID khớp header/body.
- Bản sửa C15 chỉ đổi test/báo cáo. SHA-256 của các file Python backend cùng hai file requirements vẫn là `7c7b70e2084cffa8e8669305023a434d849c360534e638d7c0ba3d29916df6e5`, khớp bản đã chạy 21 ca HTTP.
- Giới hạn: còn warning deprecation TestClient/httpx; chưa kiểm thử UI, cài mới trong môi trường sạch, mô hình/ASR thật hay đánh giá chất lượng nghiên cứu. Các cấu hình pipeline/whisper nêu trên kiểm tra việc báo chưa sẵn sàng, không chứng minh mô hình thật đã chạy.
- Nhánh `feat/web-demo`, worktree `/home/thangpham/orca/workspaces/HKI-IE501-DoAnTotNghiep/web-demo`; phần triển khai chưa commit hoặc merge. T19 vẫn **Đang làm**; T20 và các phụ thuộc mô hình thật tiếp tục theo phân công.

### Lượt kiểm tra trước sửa C15 — Codex, 03/11/2026

Coordinator chạy kiểm tra trên backend hiện tại:
- HTTP server thật do coordinator chạy đạt 21/21 ca (4 endpoint, hai chiều dịch, WAV, các mã lỗi, chunked JSON/multipart quá hạn mức, multipart language cắt cụt, hai cấu hình degraded bằng factory thật pipeline/mock và mock/whisper).
- SHA-256 backend/requirements khớp chuẩn: `7c7b70e2084cffa8e8669305023a434d849c360534e638d7c0ba3d29916df6e5`.
- Phát hiện C15: Test suite còn race với background loading khi test gửi request trước khi fake ASR load xong (`test_asr_empty_or_whitespace_transcript_returns_no_speech` nhánh whitespace nhận 503 thay vì 400). Yêu cầu đồng bộ bằng portal `wait_loaded()`, rà soát toàn bộ TestClient trực tiếp, loại bỏ sleep cố định và chạy 3 process pytest độc lập liên tiếp.

### Review R4 đợt 1 mã triển khai — Codex, 03/11/2026

Coordinator chạy kiểm tra trên factory thật của repo và phát hiện regression trong supervisor.load_engines:
- Khi translation load lỗi bình thường lúc khởi động (`TRANSLATION_ENGINE_TYPE='pipeline'`), `not translation_dispatched` đổi state thành `stopping` và return, làm ASR mock bị bỏ qua không được nạp và cả hai engine đều chuyển sang stopping dù `_is_stopping=False`.
- Yêu cầu: Phân biệt rành mạch giữa lỗi load bình thường (giữ `failed`, cho phép engine tiếp theo nạp) và trường hợp shutdown thật (`_is_stopping=True`).

### Review R3 đợt 1 mã triển khai — Codex, 03/11/2026

Coordinator chạy kiểm tra độc lập và ghi nhận kết quả:
- C05 và C07 đạt; C08, C12, C14 và held-loader shutdown đã giải quyết các ca trước.
- 121 tests web pass (2.08s); python3 -S unittest discover đạt 23 tests pass; pip check pass.
- Nhánh còn lại của C06: khi `translation.load()` ném exception trong lúc shutdown, khối `except Exception` trong `load_engines()` đặt `translation_state=failed` rồi đi tiếp sang bước ASR vô điều kiện; ASR state bị đổi từ stopping về loading và bắt đầu load sau khi supervisor đã stopping. Yêu cầu đóng admission cho mọi pha load khi stopping và theo dõi pre-dispatch work.

### Review đợt 2 mã triển khai — Codex, 03/11/2026

Coordinator chạy probe độc lập: C05 và C07 đã đạt; mở lại C06, C08, C12 và ghi nhận C14 mới:

| Mã / ưu tiên | Vị trí / bằng chứng | Phát hiện và yêu cầu xử lý |
| --- | --- | --- |
| C06 — P1 (Reopened) | `src/web_app/services/supervisor.py`, `src/web_app/main.py` | Theo dõi thread loader dựa vào finally của asyncio coroutine; khi task bị cancel trên event loop, supervisor đánh dấu loader_active=false trong khi OS thread vẫn đang chạy, dẫn đến shutdown gọi unload() khi thread load còn hoạt động. Cần theo dõi kết thúc thật của OS thread. |
| C08 — P2 (Reopened) | `src/web_app/api/routes/asr.py` | Multipart cắt cụt part language không có closing boundary bị bỏ qua và trả 200 thay vì 400. Cần kiểm tra kết thúc toàn bộ container qua closing boundary (--B--), từ chối part dở dang và giới hạn max 1 file + max 1 text field. |
| C12 — P2 (Reopened) | `src/web_app/services/supervisor.py`, `api/routes/health.py` | Bỏ sót trường bắt buộc artifact_id; chưa kiểm tra tính nhất quán kiểu boolean is_mock vs engine_type; health gọi getters trực tiếp khi chưa ready có thể bị crash hoặc trả nhãn unknown. Cần kiểm tra toàn bộ hợp đồng và health đọc snapshot an toàn. |
| C14 — P1 (Mới) | `src/web_app/services/inference_runner.py` | start() cho phép khởi động lại và tạo thêm workers trong khi shutdown trước đó chưa kết thúc (grace exhausted), làm tăng số active workers vượt quá INFERENCE_WORKERS; worker thread bị treo vô hạn sau grace timeout do _shutdown_event chưa set. Cần cấm restart khi chưa drain và cho phép worker tự thoát sạch sẽ. |

### Review cuối mã triển khai đợt 1 — Codex, 02/11/2026

Coordinator chạy probe ASGI/thread độc lập và phát hiện 9 điểm C05–C13; kết luận CẦN SỬA:

| Mã / ưu tiên | Vị trí / bằng chứng | Phát hiện và yêu cầu xử lý |
| --- | --- | --- |
| C05 — P1 | `src/web_app/api/middleware.py:64–103` | Middleware bounded_receive chỉ đặt flag rồi trả chunk; app vẫn chạy và gửi 200, sau đó middleware gửi tiếp 413 -> response_starts [200, 413]. Cần ngắt ngay lập tức, trả đúng 1 response 413, không gọi engine. |
| C06 — P1 | `src/web_app/main.py:60–70`, `src/web_app/services/supervisor.py` | Lifespan cancel load_task không dừng worker thread nạp; shutdown gọi unload() khi loader còn đang chạy. Cần quản lý loader thread, có grace và không unload nếu loader/inference còn chạy. |
| C07 — P1 | `src/web_app/services/inference_runner.py:156–199` | Worker loop không kiểm queue_deadline trước func; khi event loop bận, worker bốc job đã quá hạn và vẫn thực thi. Cần kiểm monotonic deadline trước khi gọi engine, discard với 504 phase=queue. |
| C08 — P2 | `src/web_app/api/routes/asr.py:38` | Multipart cắt cụt để lại SpooledTemporaryFile mở do parse dở không trả về trong form. Cần giới hạn parts (max 1 file, max 1 language) và đảm bảo đóng 100% spools tạo ra trong mọi trường hợp. |
| C09 — P2 | `src/web_app/api/routes/translate.py:123`, `src/web_app/api/routes/asr.py:136` | Message ném ra chứa `{e}`, làm rò rỉ private path và sentinels cho client khi gặp lỗi nội bộ. Cần dùng message cố định an toàn, chỉ log nội bộ kèm request_id. |
| C10 — P2 | `README.md`, `src/tests/web_app/` | Lệnh `python3 -S -m unittest discover -s src/tests` bị 8 lỗi import do test web import pytest/httpx trong môi trường chỉ có stdlib. Cần cách ly discovery và cập nhật lệnh pipeline độc lập. |
| C11 — P1 | `src/web_app/services/inference_runner.py`, `src/web_app/services/supervisor.py` | Lỗi tài nguyên (MemoryError) xảy ra sau khi request đã timeout/hủy không được báo về supervisor; engine vẫn báo ready và request sau vẫn gọi lại engine hỏng. Cần hook fatal error chuyển engine sang failed. |
| C12 — P2 | `src/web_app/services/supervisor.py` | Chỉ kiểm tra model_id, bỏ sót checkpoint_version, tokenizer_version, supported_directions và bundle info; metadata rỗng vẫn publish ready. Cần validate hợp đồng đầy đủ trước khi ready. |
| C13 — P2 | `src/web_app/api/error_handlers.py:104` | Body JSON sai encoding (`b'\xff'`) bị ném HTTPException 400 và handler gán error_code `HTTP_ERROR` ngoài hợp đồng. Cần chuẩn hóa mọi lỗi 400 input về `INVALID_INPUT`. |

### Review mã triển khai đợt 1 — 02/11/2026

Phạm vi là trạng thái thực tế trong worktree `web-demo`, nhánh `feat/web-demo`, HEAD `226ee43` (commit đặc tả). Tại lúc nhận review, phần triển khai mới chưa commit: `.gitignore` bị sửa; `.env.example`, hai requirements web, `src/web_app/` và `src/tests/web_app/` là untracked. Không suy ra trạng thái ở workspace khác từ review này.

Môi trường đã kiểm tra: Python 3.12.3; FastAPI 0.162.0, Starlette 1.10.0, Pydantic 2.14.2, pydantic-settings 2.16.2, pytest 9.2.0, Uvicorn 0.54.0. `.venv` không cài `torch`, `transformers`, `openai-whisper`. Đã có nền phụ thuộc mock nhưng chưa có ứng dụng để chạy.

| Mã / ưu tiên | Vị trí / bằng chứng | Phát hiện và yêu cầu xử lý |
| --- | --- | --- |
| C01 — P1 | `src/web_app/`; yêu cầu §8.4, bước 2–4; Uvicorn exit 3 | Thiếu `main.py`, schemas, engine/mock, runner, validator WAV, middleware/handlers và bốn route. Hiện chỉ có ba module core và các `__init__.py` rỗng. Cần hoàn thiện backend mock đến khi khởi động và gọi được bốn API; không thể nghiệm thu phần hàng đợi/timeout từ khung package. |
| C02 — P1 | [language.py](../../src/web_app/core/language.py), hàm `normalize_and_trim_text`, dòng 38–44 | Hàm còn `TODO(human)` và `pass`, trả `None` cho mọi đầu vào thay vì chuỗi chuẩn hóa. Thử `'  a\u0301  '`, `'   '`, `'\u2000Xin chào\u3000'` đều trả `None`. Cần hiện thực NFC/trim theo spec và kiểm tra cả rỗng, Unicode whitespace, giữ khoảng trắng nội bộ. |
| C03 — P1 | `src/tests/web_app/` chỉ có `__init__.py`; pytest exit 5 | Không có test web nào để xác nhận API, WAV, hàng đợi, timeout/hủy hoặc shutdown. 23 test dữ liệu cũ đạt không thay thế bộ này. Cần viết test có kiểm tra hành vi thực tế theo §8.2, chạy lại và bàn giao kết quả cùng kiểm tra HTTP. |
| C04 — P2 | [README.md](../../README.md) và báo cáo nhóm tại thời điểm nhận review | README chưa có hướng dẫn web đã chạy; báo cáo chưa ghi đợt triển khai của Claude, commit đầu vào hay bằng chứng test/HTTP. Cần hoàn thiện tài liệu bàn giao sau khi code chạy được. Lượt review này chỉ bổ sung phát hiện/kết quả kiểm tra, không thay cho báo cáo triển khai của tác giả. |

Lỗi định dạng phụ: `.gitignore` có dòng trống thừa cuối file, làm `git diff --check` thất bại. Chưa sửa mã hoặc `.gitignore` trong lượt review; không commit/push/merge. T19 còn đang làm và chưa có cơ sở chuyển sang nghiệm thu đợt 2.

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
| 02/11/2026 | Codex | Review mã Claude trong working tree; xác nhận backend chưa khởi động và chưa có test web; giữ nguyên mã để giao sửa tiếp | C01–C04, pytest exit 5, Uvicorn exit 3; 23 test dữ liệu cũ đạt |
| 02/11/2026 | Claude Code | Triển khai hoàn tất Task A: Core (C02), Engines Mock (C01 phần engine/wav), Unit tests Core/Engines/Audio (C03 phần A); run ID task_c62f93553845, dispatch ctx_f4e12538e2de | 62 test đạt, exit code 0; chi tiết hợp đồng bàn giao bên dưới |
| 02/11/2026 | Claude Code | Triển khai hoàn tất Task B: InferenceRunner (C01 phần runner), Unit tests Runner (C03 phần B); run ID task_72cf1976ee4a, dispatch ctx_3eb69a30cf7f | 13 test runner đạt, exit code 0; chi tiết hợp đồng bàn giao bên dưới |
| 02/11/2026 | Claude Code | Triển khai hoàn tất Task C: Tích hợp API, Middleware, Error Handlers, Lifespan, 113 tests web, Verify Uvicorn HTTP server thật; run ID task_756921e5127b, dispatch ctx_013d01ec2559 | 113 test web đạt, 9/9 HTTP thật đạt, exit code 0; hoàn tất đợt 1 backend mock; chi tiết bên dưới |

### Bàn giao kỹ thuật Task A cho agent tích hợp — 02/11/2026

- **Người thực hiện:** Claude Code worker (`term_fcab4f4d-8d09-47cf-9778-7076ec45ec3b`), Task ID: `task_c62f93553845`, Dispatch ID: `ctx_f4e12538e2de`.
- **Commit đầu vào:** `226ee43c761b81112e0216d4b5f8dd7608322685`.
- **Phạm vi sở hữu Task A:**
  - Core: `src/web_app/core/language.py`, `src/web_app/core/config.py`, `src/web_app/core/exceptions.py`.
  - Translation: Toàn bộ `src/web_app/services/translation/` (`base.py`, `mock.py`, `factory.py`, `__init__.py`).
  - ASR: Toàn bộ `src/web_app/services/asr/` (`base.py`, `mock.py`, `factory.py`, `audio.py`, `__init__.py`).
  - Unit Tests: `src/tests/web_app/audio_fixtures.py`, `src/tests/web_app/test_core.py`, `src/tests/web_app/test_engines.py`, `src/tests/web_app/test_audio.py`.
- **Tiến độ giải quyết các điểm review C01–C04:**
  - **C02 (P1): ĐÃ GIẢI QUYẾT.** `normalize_and_trim_text` chuẩn hóa Unicode NFC và trim toàn bộ 25 ký tự whitespace chuẩn spec §4.3, giữ nguyên khoảng trắng nội bộ. 6 unit tests bao phủ chuỗi rỗng, dấu tổ hợp, non-BMP, whitespace đặc thù.
  - **C01 (P1): Hoàn thành một phần (phần Core + Engines + WAV).** Các interface `InferenceEngine`, `ASREngine`, mock engines, factories và validator WAV đã hoàn tất; phần runner và route/entrypoint do Task B đảm nhiệm.
  - **C03 (P1): Hoàn thành 62 unit tests cho Core, Engines và Audio.** Pytest exit code 0; không import ML trên mock path; kiểm thử đầy đủ các điều kiện biên và mã lỗi.
  - **C04 (P2):** Cập nhật đầy đủ bằng chứng, lệnh chạy và tài liệu bàn giao kỹ thuật tại báo cáo này.

#### Chi tiết Hợp đồng Public API của Task A

1. **`InferenceEngine` & `MockTranslationEngine` (`src/web_app/services/translation/`):**
   - **Constructor:** `MockTranslationEngine(mock_delay_ms: int = 0)`
   - **Phương thức (đồng bộ):**
     - `load(bundle_path: str | Path | None = None) -> None`: Nạp giả lập; chuyển `is_ready()` sang `True`.
     - `is_ready() -> bool`: Kiểm tra trạng thái sẵn sàng.
     - `get_supported_directions() -> list[str]`: Trả `["vi-tay", "tay-vi"]` khi ready, ngược lại `[]`.
     - `translate(text: str, direction: str) -> TranslationResult`:
       - Tiền tố kết quả: `[MOCK vi->tyz] {text}` hoặc `[MOCK tyz->vi] {text}`.
       - Ném `ModelNotReadyError` (503) nếu chưa ready.
       - Ném `UnsupportedDirectionError` (400) nếu `direction` không thuộc `("vi-tay", "tay-vi")`.
     - `get_metadata() -> TranslationMetadata`:
       `TranslationMetadata(model_id="mock-demo", artifact_id="mock-text", checkpoint_version="mock-v1", tokenizer_version="mock-v1", engine_type="mock", is_mock=True)`
     - `get_bundle_info() -> BundleModelInfo`:
       `BundleModelInfo(id="mock-demo", name="Mô phỏng dịch văn bản", bundle_version="mock-v1", engine_type="mock", is_mock=True, supported_directions=["vi-tay", "tay-vi"], is_default=True, metrics=None)`
     - `unload() -> None`: Chuyển `is_ready()` về `False`.
   - **Factory:** `create_translation_engine(settings: WebSettings) -> InferenceEngine`.
     - `mock` -> trả `MockTranslationEngine(mock_delay_ms=settings.MOCK_DELAY_MS)` (chưa load, không blocking).
     - `pipeline` -> trả `UnavailableTranslationEngine` (gọi `load()` ném `ModelNotReadyError`, `is_ready()` là `False`, không fallback mock).

2. **`ASREngine` & `MockASREngine` (`src/web_app/services/asr/`):**
   - **Constructor:** `MockASREngine(mock_delay_ms: int = 0)`
   - **Phương thức (đồng bộ):**
     - `load(model_path: str | Path | None = None) -> None`: Nạp giả lập; chuyển `is_ready()` sang `True`.
     - `is_ready() -> bool`: Kiểm tra trạng thái sẵn sàng.
     - `get_metadata() -> ASRMetadata`:
       `ASRMetadata(model_id="mock-asr", model_version="mock-v1", engine_type="mock", is_mock=True)`
     - `transcribe(audio: AudioInput, language: str = "vi") -> ASRResult`:
       - Chỉ nhận `AudioInput` đã qua validation và `language == "vi"`.
       - Ném `ModelNotReadyError` (503) nếu chưa ready.
       - Ném `UnsupportedASRLanguageError` (400) nếu `language != "vi"`.
       - Trả `ASRResult(transcript="[MOCK ASR] Đây là transcript mẫu để kiểm thử giao diện.", language="vi", duration_sec=audio.duration_sec, model_metadata=get_metadata())`.
     - `unload() -> None`: Chuyển `is_ready()` về `False`.
   - **Factory:** `create_asr_engine(settings: WebSettings) -> ASREngine | None`.
     - `disabled` -> trả `None`.
     - `mock` -> trả `MockASREngine(mock_delay_ms=settings.MOCK_DELAY_MS)` (chưa load).
     - `whisper` -> trả `UnavailableASREngine` (`load()` ném `ModelNotReadyError`, không fallback).

3. **`validate_wav(data: bytes, settings: WebSettings) -> AudioInput` (`src/web_app/services/asr/audio.py`):**
   - **Đầu vào:** `data: bytes`, `settings: WebSettings`.
   - **Đầu ra:** `AudioInput(pcm_bytes: bytes, sample_rate_hz=16000, channels=1, frame_count=int, duration_sec=float)`.
   - **Cơ chế phân loại lỗi:**
     - Dung lượng tệp > `settings.MAX_AUDIO_FILE_BYTES` -> ném `AudioTooLargeError` (HTTP 413, code `AUDIO_TOO_LARGE`).
     - Thời lượng PCM > `settings.MAX_AUDIO_DURATION_SEC` -> ném `AudioTooLongError` (HTTP 400, code `AUDIO_TOO_LONG`).
     - Không phải RIFF/WAVE, hoặc format tag != 1, sample rate != 16000, channels != 1, bits != 16 -> ném `AudioUnsupportedFormatError` (HTTP 400, code `AUDIO_UNSUPPORTED_FORMAT`).
     - Tệp ngắn < 44 bytes, RIFF size không khớp byte thực, chunk header cắt cụt, chunk size tràn tệp, thiếu byte đệm lẻ, thiếu fmt/data, duplicate fmt/data, data trước fmt, block align != 2, byte rate != 32000, byte PCM lẻ, 0 frames -> ném `AudioInvalidError` (HTTP 400, code `AUDIO_INVALID`).
   - Cấp phát bộ nhớ: Chỉ tạo slice `pcm_bytes` và cấp phát `AudioInput` sau khi tất cả các bước xác thực và giới hạn đã vượt qua.

4. **Core Updates (`src/web_app/core/`):**
   - `normalize_and_trim_text(text: str) -> str`: NFC + trim 25 ký tự whitespace hai đầu theo spec §4.3.
   - `WebSettings`: Kiểm tra các deadline `QUEUE_TIMEOUT_SEC`, `TRANSLATION_TIMEOUT_SEC`, `ASR_TIMEOUT_SEC`, `SHUTDOWN_GRACE_SEC` là số thực dương hữu hạn (`math.isfinite`), kiểm tra ràng buộc `MAX_MULTIPART_BODY_BYTES > MAX_AUDIO_FILE_BYTES`, hàm `resolve_path()` phân giải tương đối theo `REPO_ROOT`.
   - `InferenceTimeoutError`: Constructor nhận `(phase: str, message: str | None = None)` với thuộc tính `phase` và `detail={"phase": phase}`.

### Bàn giao kỹ thuật Task B (InferenceRunner) — 02/11/2026

- **Người thực hiện:** Claude Code worker (`term_1b06a493-7ca7-4cea-aa8e-afe624b46d3d`), Task ID: `task_c805ce4fe37a`, Dispatch ID: `ctx_af857a44557f`, Run ID: `run_7df7c4d9f4bc`.
- **Commit đầu vào:** `226ee43c761b81112e0216d4b5f8dd7608322685`.
- **Phạm vi sở hữu Task B:**
  - `src/web_app/services/inference_runner.py`: Quản lý N worker threads dài hạn, hàng đợi FIFO hữu hạn, tách riêng `queue_deadline` và `exec_deadline`.
  - `src/tests/web_app/test_runner.py`: 13 bài kiểm thử đơn vị bao phủ toàn diện hàng đợi đầy (503), hết hạn hàng đợi (504 phase=queue), hủy yêu cầu chờ trong hàng đợi, hủy/timeout yêu cầu đang chạy (worker tiếp tục giữ slot và thu hồi late completion/exception), shutdown với grace period.
- **Hợp đồng Public API của InferenceRunner:**
  - `async def start() -> None`: Khởi tạo N worker thread phục vụ vòng lặp FIFO.
  - `async def run(func, *, task_type, request_id, model_id=None, execution_timeout_sec=None) -> RunnerResult[T]`: Tiếp nhận tác vụ, xếp hàng, thực thi và đo đạc `queue_ms`, `latency_ms`.
  - `async def shutdown(grace_sec=None) -> bool`: Ngừng tiếp nhận, loại bỏ các job đang chờ và đợi worker hoàn tất trong thời gian grace.

### Bàn giao kỹ thuật Task C (Tích hợp API, Kiểm thử và Bàn giao Đợt 1) — 02/11/2026

- **Người thực hiện:** Claude Code worker (`term_027eaa00-951c-4f5a-ab26-21fbfd168f34`), Task ID: `task_756921e5127b`, Dispatch ID: `ctx_013d01ec2559`.
- **Mô hình thực hiện:** local[1m] (ultracode / Custom Haiku), effort max.
- **Commit đầu vào:** `226ee43c761b81112e0216d4b5f8dd7608322685`.
- **Phạm vi sở hữu Task C:**
  - Entrypoint ứng dụng: `src/web_app/main.py` (`create_app()`, `app = create_app()`).
  - Schemas và Logging: `src/web_app/core/schemas.py`, `src/web_app/core/logging.py`, `src/web_app/services/supervisor.py`.
  - Middleware & Error Handlers: `src/web_app/api/middleware.py`, `src/web_app/api/error_handlers.py`, `src/web_app/api/utils.py`.
  - API Routes: `src/web_app/api/router.py`, `src/web_app/api/routes/__init__.py`, `src/web_app/api/routes/health.py`, `src/web_app/api/routes/models.py`, `src/web_app/api/routes/translate.py`, `src/web_app/api/routes/asr.py`.
  - Kiểm thử tích hợp: `src/tests/web_app/conftest.py`, `src/tests/web_app/test_api_health_models.py`, `src/tests/web_app/test_api_translate.py`, `src/tests/web_app/test_api_asr.py`, `src/tests/web_app/test_api_errors_and_lifecycle.py`.
  - Cấu hình & tài liệu: `.gitignore`, `README.md`, `.agents/reports/web-demo.md`.

#### Chi tiết Triển khai và Hợp đồng Public API của Task C

1. **Khởi tạo ứng dụng & Lifespan (`create_app` trong `src/web_app/main.py`):**
   - Signature: `create_app(settings=None, translation_engine=None, asr_engine=_UNSET) -> FastAPI`.
   - Hỗ trợ dependency injection linh hoạt cho test fakes và Uvicorn mặc định (`app = create_app()`).
   - Lifespan khởi động runner, khởi chạy nạp engine bất đồng bộ ngoài event loop (`supervisor.load_engines()`).
   - Health trả `loading` khi đang nạp, chỉ chuyển `ready` sau khi kiểm tra định danh và khả năng engine.
   - ASR disabled không ảnh hưởng readiness của dịch văn bản.
   - Shutdown an toàn: ngừng admission, hủy job chờ, đợi worker trong `SHUTDOWN_GRACE_SEC`. Nếu hết grace mà worker vẫn đang chạy, ghi log cảnh báo và **không gọi `unload()`** để tránh xung đột bộ nhớ.

2. **Hợp đồng 4 Route API (§4):**
   - **`GET /api/health`:**
     - Đọc trạng thái trực tiếp trong bộ nhớ, không chờ hàng đợi suy luận.
     - Phản hồi `HealthResponse` gồm `status` ("ready"|"loading"|"degraded"), `translation` info, `asr` info và `limits`.
   - **`GET /api/models`:**
     - Đọc trong bộ nhớ, trả danh mục bundle mô hình đang phục vụ.
     - Trả `models: []` với HTTP 200 khi engine dịch chưa sẵn sàng.
   - **`POST /api/translate`:**
     - Input JSON: `{"text": "...", "direction": "vi-tay"|"tay-vi", "model_id": "..." (optional)}`. Cấm trường lạ (`extra="forbid"`).
     - Thứ tự kiểm tra nghiêm ngặt: Giới hạn byte body (64 KiB) → Cấu trúc schema / sai kiểu (`INVALID_INPUT`) → Chuẩn hóa NFC và trim 25 ký tự whitespace → Kiểm tra rỗng (`INVALID_INPUT`) → Độ dài code points (<= 1000, vượt quá trả `INPUT_TOO_LONG`) → Semantic direction (`UNSUPPORTED_DIRECTION`) → Engine readiness (`MODEL_NOT_READY`) → Chiều hỗ trợ bởi bundle / Model ID (`MODEL_NOT_FOUND`) → Admission vào runner.
     - Output: `TranslateResponse` kèm `model_metadata` (is_mock=True), `latency_ms`, `queue_ms`.
   - **`POST /api/asr/transcribe`:**
     - Multipart form: bắt buộc chính xác 1 file `file` (WAV PCM signed 16-bit 16kHz mono) và tối đa 1 `language` (mặc định "vi", chỉ nhận "vi"). Cấm duplicate hoặc extra fields.
     - Giới hạn body (11 MiB) và giới hạn file riêng (10 MiB) đọc theo chunk bị chặn (bounded chunk reading).
     - Kiểm tra toàn diện container RIFF/WAVE, PCM format tag 1, 16kHz, mono, thời lượng <= 30s.
     - Quản lý tài nguyên: đóng toàn bộ `UploadFile` trong mọi trường hợp (thành công, lỗi validation, hủy).
     - Kiểm tra transcript: nếu fake engine trả transcript rỗng hoặc chỉ có khoảng trắng, ánh xạ thành `NO_SPEECH_DETECTED` (400).

3. **Middleware Body Limit và X-Request-ID (`src/web_app/api/middleware.py`):**
   - Kiểm tra `Content-Length` sớm và đếm byte streaming chunk thực nhận, ngăn ngừa tấn công lying length hoặc chunked encoding trước khi multipart parser spooling ra ổ đĩa.
   - Trích xuất header `X-Request-ID` hoặc sinh UUID ngẫu nhiên; đính kèm vào tất cả response headers và error bodies.

4. **Xử lý Ngoại lệ Tập trung (`src/web_app/api/error_handlers.py`):**
   - Ánh xạ mọi lỗi (`AppError`, `RequestValidationError`, `StarletteHTTPException`, `Exception`) về đúng schema `ErrorResponse` (§4.2).
   - Tuyệt đối không để lộ stack trace, đường dẫn máy chủ hay dữ liệu nội bộ.

5. **Giám sát Client Disconnect (`src/web_app/api/utils.py`):**
   - Đồng thời với tác vụ runner, giám sát tín hiệu ngắt kết nối `request.is_disconnected()`.
   - Khi client hủy kết nối: hủy coroutine chờ, runner ghi nhận `caller_cancelled = True`, loại bỏ job nếu còn trong hàng đợi hoặc để worker tiếp tục hoàn tất suy luận mà không giải phóng slot sớm.

#### Bằng chứng Kiểm thử Thực tế và Kiểm tra Môi trường

- **Kiểm tra phụ thuộc (`python -m pip check`):**
  Exit code 0: `No broken requirements found.` (đã pin phiên bản chính xác trong requirements-web.txt và requirements-web-dev.txt, bao gồm cả anyio==4.16.0 và starlette==1.10.0 do import trực tiếp).
- **Kiểm thử đơn vị và tích hợp Web (`python -m pytest src/tests/web_app/ -v --tb=short`):**
  Exit code 0: **131/131 tests passed** trong 2.27s.
  - `test_core.py`: 16 tests (Unicode NFC, trim 25 whitespace, config cross-field, finite positive deadlines, domain exceptions).
  - `test_engines.py`: 13 tests (vòng đời engine dịch và ASR, factories, mock metadata, unavailable engines).
  - `test_audio.py`: 33 tests (validate_wav, ranh giới 30s, non-RIFF, non-PCM, sample rate, channels, bit depth, header hỏng, odd byte pad).
  - `test_runner.py`: 13 tests (InferenceRunner FIFO, service overloaded 503, queue timeout 504, client cancellation, worker slot invariant, shutdown grace).
  - `test_api_health_models.py`: 6 tests (health default ready, loading state, asr disabled, engine failed, worker withheld non-blocking, models unready).
  - `test_api_translate.py`: 15 tests (2 chiều dịch, Unicode NFC/whitespace, non-BMP/emoji, boundary 1000/1001, empty text, wrong type priority, extra fields forbid, direction/model_id validation, queue full, timeouts, memory error).
  - `test_api_asr.py`: 10 tests (transcribe success, multipart rules, unsupported language, file chunk limit, format validation, duration limit, unready, empty/whitespace transcript -> NO_SPEECH_DETECTED, unexpected failure).
  - `test_api_errors_and_lifecycle.py`: 7 tests (404 Not Found, 405 Method Not Allowed, X-Request-ID preservation, UploadFile cleanup, shutdown clean unload, shutdown grace exhaustion preserve engine, client disconnect monitoring).
  - `test_regressions_c05_c13.py`: 18 tests (C05 single response 413 on chunked oversized, C06 no unload while loading & safe repeated shutdown for translation & ASR, C07 skip expired queue job with event loop stall, C08 truncated language field & missing closing boundary rejection with 100% closed spools, C09 sanitized exceptions without leaks, C11 late OOM transitions to failed, C12 full mandatory metadata and in-memory snapshot, C13 invalid JSON encoding returns 400 INVALID_INPUT, C14 start prohibited when stopping/active and worker auto-exit).
- **Kiểm thử dữ liệu nền (`python3 -S -m unittest discover -s src/tests -t . -p 'test_*.py'`):**
  Exit code 0: **23/23 tests passed** trong 0.209s trong môi trường Python stdlib thuần túy (-S) không cài bất kỳ gói web nào.
- **Kiểm tra định dạng Git (`git diff --check`):**
  Exit code 0: Sạch hoàn toàn, không có lỗi khoảng trắng hay dòng thừa cuối file.
- **Kiểm thử máy chủ HTTP thật Uvicorn (1 process trên 127.0.0.1 port 35063):**
  - Khởi chạy Uvicorn process độc lập (PID 3607184), kiểm tra bằng `httpx.Client`:
    - `GET /api/health` -> HTTP 200 (status: ready, translation ready, asr ready, limits đúng) [PASS]
    - `GET /api/models` -> HTTP 200 (bundle mock-demo có sẵn) [PASS]
    - `POST /api/translate` (vi-tay) -> HTTP 200 (bản dịch `[MOCK vi->tyz] ...`, latency đo được) [PASS]
    - `POST /api/translate` (tay-vi) -> HTTP 200 (bản dịch `[MOCK tyz->vi] ...`, latency đo được) [PASS]
    - `POST /api/asr/transcribe` (tệp WAV PCM 16kHz mono) -> HTTP 200 (transcript `[MOCK ASR] ...`, duration 1.5s) [PASS]
    - `POST /api/translate` (chunked oversized body không Content-Length) -> HTTP 413 `REQUEST_TOO_LARGE` [PASS]
    - `POST /api/translate` (invalid JSON binary encoding `b'\xff\xfe'`) -> HTTP 400 `INVALID_INPUT` [PASS]
    - `POST /api/asr/transcribe` (truncated multipart language field không closing boundary) -> HTTP 400 `INVALID_INPUT` [PASS]
    - `POST /api/translate` (text rỗng) -> HTTP 400 `INVALID_INPUT` [PASS]
    - `POST /api/translate` (direction "en-vi") -> HTTP 400 `UNSUPPORTED_DIRECTION` [PASS]
    - `GET /api/unknown_route` -> HTTP 404 `NOT_FOUND` [PASS]
    - `GET /api/translate` -> HTTP 405 `METHOD_NOT_ALLOWED` [PASS]
  - Tiến trình Uvicorn được dừng sạch sau kiểm thử bằng lệnh `terminate()`.

#### Giới hạn Hiện tại và Phần cần Agent Tiếp theo Xử lý

- **Trạng thái mốc T19:** Đã hoàn tất đợt 1 backend mock theo đúng đặc tả §8.4 và xử lý triệt để các phát hiện review C01–C14; toàn bộ 4 API và hợp đồng xử lý lỗi đã sẵn sàng. Chưa thể đóng nghiệm thu toàn diện T19 do phụ thuộc T11/T12 (mô hình dịch thật từ pipeline) chưa hoàn tất.
- **Giao diện người dùng (UI):** Chưa triển khai mã frontend HTML/CSS/JS (thuộc phạm vi đợt 2 — T20).
- **Mô hình học máy thật:** Chưa cài đặt thư viện ML (`torch`, `transformers`, `openai-whisper`), chưa tải checkpoint hay trọng số thật.
- **Bàn giao:** Đã chuẩn bị đầy đủ bằng chứng kiểm thử và tài liệu; sẵn sàng để Codex coordinator thực hiện review lại đợt 1 theo quy trình dự án.
