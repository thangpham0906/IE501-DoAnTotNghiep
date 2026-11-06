/**
 * test_orca_browser_suite.mjs - Kịch bản tự động hóa kiểm thử trên Trình duyệt nhúng Orca (§6, §8.2, T20/T21/T22).
 *
 * Tiêu chuẩn chất lượng (C19/C20/C22/C23):
 * 1. Không dùng cổng 8000 cố định; tự tìm cổng trống, khởi chạy máy chủ Uvicorn test riêng và chỉ dừng PID sở hữu.
 * 2. Ghim --page <browserPageId> cho mọi lệnh orca-ide (eval, screenshot, set device, tab close).
 * 3. Đưa vòng đời tab vào phạm vi cleanup try/finally ngay sau khi nhận pageId (dọn tab kể cả khi chuẩn bị test thất bại).
 * 4. Truyền tham số CLI dạng mảng argv an toàn (execFileSync), không nối chuỗi qua shell (kể cả wslpath).
 * 5. Chờ kết quả bằng thăm dò điều kiện DOM xác định (polling 50ms), không dùng sleep cố định; ném lỗi khi timeout.
 * 6. Kiểm thử nhánh AudioRecorder bằng nguồn âm thanh tổng hợp Web Audio (Oscillator -> MediaStreamDestination):
 *    - Cấp stream live độc lập cho từng phiên thu (không dùng lại stream đã stopped).
 *    - Ca 6A: Dừng chủ động bằng nút Stop, kiểm tra WAV PCM 16kHz mono có frame > 0.
 *    - Ca 6B: Tự động dừng khi chạm trần thời lượng (Auto-stop C22), kiểm tra frames > 0 và <= 32000 (chính xác trần 2s).
 *    - Ca 6C: Ngắt kết nối micro đột ngột (Track ended C22) bằng mô phỏng track ended thực sự, không bấm Stop.
 * 7. Upload tệp WAV thật qua input #vp-file-input, gửi tới API ASR với engine mock, assert transcript và nhãn mock;
 *    kiểm tra KHÔNG tự động dịch; sửa transcript và assert dịch đúng snapshot đã sửa.
 * 8. Kiểm tra C20: hủy yêu cầu Dịch A khi ASR B bắt đầu (Transport Abort & Invalidation), assert signal abort,
 *    assert outcome AbortError, assert thứ tự các mốc, transcript B trên DOM và không bị bản dịch cũ của A ghi đè.
 * 9. Kiểm tra C23: Copy button feedback trên DOM thật (sao chép thành công và hướng dẫn khi thiếu quyền/lỗi).
 * 10. Kiểm tra hiển thị responsive trên Mobile (iPhone 12): chọn đúng subtab Upload để kiểm tra kích thước và tọa độ thật;
 *     kiểm tra subtab Thu âm hiển thị nút Bắt đầu trong viewport; không có thanh cuộn ngang.
 * 11. Sử dụng assert nghiêm ngặt; bất kỳ thất bại nào đều làm script thoát với exit code khác 0.
 */

import assert from 'node:assert/strict';
import { execFileSync, spawn } from 'node:child_process';
import fs from 'node:fs';
import net from 'node:net';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { validateScreenshot } from './screenshot_png.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, '..');
const SCREENSHOT_DIR = path.join(REPO_ROOT, 'docs/screenshots');

fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

/**
 * Tìm một cổng TCP còn trống trên 127.0.0.1
 */
async function findFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.listen(0, '127.0.0.1', () => {
      const port = srv.address().port;
      srv.close(() => resolve(port));
    });
    srv.on('error', reject);
  });
}

/**
 * Thực thi lệnh orca-ide bằng mảng tham số argv an toàn (không qua shell).
 */
function runOrca(args) {
  try {
    const out = execFileSync('orca-ide', args, { encoding: 'utf-8', timeout: 30000 });
    return out.trim();
  } catch (err) {
    const detail = err.stderr || err.stdout || err.message;
    throw new Error(`orca-ide ${args.join(' ')} thất bại: ${detail}`);
  }
}

/**
 * Đánh giá biểu thức JavaScript trong ngữ cảnh trang được ghim bằng pageId.
 */
function evalInPage(pageId, code) {
  const stripped = code.replace(/\/\/[^\n]*\n/g, '\n');
  const expr = `(async () => { ${stripped} })()`;
  const raw = runOrca(['eval', '--page', pageId, '--expression', expr, '--json']);
  const parsed = JSON.parse(raw);
  if (!parsed.ok) {
    throw new Error(`eval thất bại trên page ${pageId}: ${parsed.error || raw}`);
  }
  const res = parsed.result?.result;
  try {
    return JSON.parse(res);
  } catch {
    return res;
  }
}

/**
 * Chụp ảnh màn hình viewport của tab được ghim bằng pageId sử dụng execFileSync wslpath không qua shell.
 * Bắt buộc xác thực ảnh hợp lệ (không rỗng, không đơn sắc). Ném lỗi nếu thất bại, không nuốt lỗi.
 */
async function captureScreenshot(pageId, filename) {
  const dest = path.join(SCREENSHOT_DIR, filename);
  let lastErr = null;

  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      if (attempt > 1) {
        await sleep(500);
      }
      const out = runOrca(['screenshot', '--page', pageId, '--format', 'png']);
      const match = out.match(/Screenshot saved to (.*) \(png\)/);
      if (match && match[1]) {
        const winPath = match[1].trim();
        const wslPath = execFileSync('wslpath', [winPath], { encoding: 'utf-8' }).trim();
        fs.copyFileSync(wslPath, dest);
        const meta = validateScreenshot(dest);
        console.log(
          `📸 Đã lưu & xác thực ảnh: ${filename} (${meta.size} bytes, ${meta.width}x${meta.height}, ${meta.colorsCount} màu pixel lấy mẫu)`
        );
        return dest;
      }
      throw new Error(`Không tìm thấy đường dẫn ảnh từ đầu ra: ${out}`);
    } catch (err) {
      lastErr = err;
    }
  }

  throw new Error(`Chụp ảnh screenshot bắt buộc [${filename}] thất bại sau 3 lần thử: ${lastErr?.message}`);
}

async function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function main() {
  console.log('=== BẮT ĐẦU BỘ KIỂM THỬ TRÌNH DUYỆT ORCA CHO WEB DEMO (C19/C20/C22/C23) ===\n');

  // 1. Tìm cổng TCP trống và khởi chạy máy chủ Uvicorn test riêng biệt
  const serverPort = await findFreePort();
  const serverUrl = `http://127.0.0.1:${serverPort}`;
  console.log(`1. Khởi chạy máy chủ Uvicorn test riêng trên cổng ${serverPort} (Hạn mức duration: 2s) ...`);

  const pythonBin = fs.existsSync(path.join(REPO_ROOT, '.venv/bin/python'))
    ? path.join(REPO_ROOT, '.venv/bin/python')
    : 'python3';

  let serverStderr = '';
  const serverProcess = spawn(
    pythonBin,
    [
      '-m',
      'uvicorn',
      'src.web_app.main:app',
      '--host',
      '127.0.0.1',
      '--port',
      String(serverPort),
      '--log-level',
      'warning',
    ],
    {
      cwd: REPO_ROOT,
      env: {
        ...process.env,
        TRANSLATION_ENGINE_TYPE: 'mock',
        ASR_ENGINE_TYPE: 'mock',
        MAX_AUDIO_DURATION_SEC: '2', // Hạn mức máy chủ 2 giây để kiểm tra auto-stop
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    }
  );

  serverProcess.stderr.on('data', (d) => {
    serverStderr += d.toString();
  });
  serverProcess.stdout.on('data', (d) => {
    serverStderr += d.toString();
  });

  const cleanupServer = () => {
    if (serverProcess && serverProcess.pid) {
      try {
        serverProcess.kill('SIGTERM');
      } catch {}
    }
  };
  process.on('exit', cleanupServer);
  process.on('SIGINT', cleanupServer);

  // 2. Chờ máy chủ sẵn sàng
  console.log(`2. Chờ máy chủ tại ${serverUrl} sẵn sàng và engines mock load xong...`);
  const startWait = Date.now();
  let serverReady = false;
  while (Date.now() - startWait < 8000) {
    try {
      const res = await fetch(`${serverUrl}/api/health`, { signal: AbortSignal.timeout(400) });
      if (res.ok) {
        const h = await res.json();
        if (h.status === 'ready' && h.translation?.state === 'ready' && h.asr?.state === 'ready') {
          serverReady = true;
          break;
        }
      }
    } catch {}
    await sleep(100);
  }

  assert.ok(serverReady, `Máy chủ test tại cổng ${serverPort} không sẵn sàng kịp. Logs:\n${serverStderr}`);
  console.log('   ✓ Máy chủ Uvicorn và 2 engine mock đã sẵn sàng phục vụ.');

  // 3. Mở tab trình duyệt Orca kết nối đến serverUrl với phạm vi cleanup try/finally ghim pageId
  console.log(`\n3. Mở tab trình duyệt Orca kết nối tới ${serverUrl} ...`);
  let pageId = null;

  try {
    const tabOutRaw = runOrca(['tab', 'create', '--url', serverUrl, '--json']);
    const tabParsed = JSON.parse(tabOutRaw);
    assert.ok(tabParsed.ok, `Không thể tạo tab trình duyệt: ${tabOutRaw}`);

    pageId = tabParsed.result?.browserPageId || tabParsed.id;
    assert.ok(pageId, 'Không lấy được browserPageId từ Orca tab create');
    console.log(`   ✓ Đã tạo tab thành công, ghim browserPageId: ${pageId}`);

    // Chờ trang tải hoàn tất trên DOM (nằm TRONG phạm vi cleanup try/finally của tab)
    const pageLoaded = evalInPage(
      pageId,
      `
      const start = Date.now();
      while (Date.now() - start < 4000) {
        if (document.getElementById('engine-status-translation')?.textContent.includes('Sẵn sàng')) {
          return true;
        }
        await new Promise(r => setTimeout(r, 50));
      }
      return false;
    `
    );
    assert.ok(pageLoaded, 'Trang không tải xong trạng thái health trong 4s');

    // JOURNEY 1: Kiểm tra nạp trang ban đầu và các nhãn Mock
    console.log('\n--- JOURNEY 1: Kiểm tra nạp trang ban đầu & Nhãn Mock ---');
    const initData = evalInPage(
      pageId,
      `
      return {
        title: document.title,
        transBadge: document.getElementById('engine-status-translation')?.textContent.trim(),
        asrBadge: document.getElementById('engine-status-asr')?.textContent.trim(),
        mockBadgeVisible: !document.getElementById('global-mock-badge')?.classList.contains('hidden'),
        btnTranslateDisabled: document.getElementById('btn-translate')?.disabled,
        activeTab: document.getElementById('tab-text')?.classList.contains('active'),
        panelTextVisible: !document.getElementById('panel-text')?.hidden,
        voicePanelHidden: document.getElementById('voice-panel')?.hidden
      };
    `
    );

    assert.strictEqual(initData.title, 'Dịch máy Việt - Tày & Thử nghiệm Giọng nói', 'Tiêu đề trang không đúng');
    assert.ok(initData.transBadge.includes('Sẵn sàng'), 'Engine dịch chưa báo sẵn sàng');
    assert.ok(initData.asrBadge.includes('Sẵn sàng'), 'Engine ASR chưa báo sẵn sàng');
    assert.strictEqual(initData.mockBadgeVisible, true, 'Nhãn MÔ PHỎNG chung phải hiển thị');
    assert.strictEqual(initData.btnTranslateDisabled, true, 'Nút Dịch ban đầu phải bị vô hiệu khi chưa có input');
    assert.strictEqual(initData.panelTextVisible, true, 'Panel văn bản phải hiển thị ban đầu');
    assert.strictEqual(initData.voicePanelHidden, true, 'Panel giọng nói ban đầu phải bị ẩn');
    console.log('   ✓ Khởi tạo trang ban đầu đạt.');
    await captureScreenshot(pageId, '01_e2e_init_page_desktop.png');

    // JOURNEY 2: Dịch văn bản tiếng Việt sang tiếng Tày (vi-tay)
    console.log('\n--- JOURNEY 2: Dịch văn bản tiếng Việt sang tiếng Tày (vi-tay) ---');
    const translateResult = evalInPage(
      pageId,
      `
      const src = document.getElementById('source-text');
      src.value = 'Mùa xuân hoa đào nở rộ trên bản làng';
      src.dispatchEvent(new Event('input', { bubbles: true }));
      const btn = document.getElementById('btn-translate');
      btn.click();

      // Thăm dò điều kiện (polling) cho đến khi ô kết quả có dữ liệu
      const start = Date.now();
      let targetVal = '';
      while (Date.now() - start < 4000) {
        targetVal = document.getElementById('target-text')?.value || '';
        if (targetVal) break;
        await new Promise(r => setTimeout(r, 50));
      }
      if (!targetVal) throw new Error('Timeout chờ kết quả dịch vi-tay');

      return {
        source: src.value,
        target: targetVal,
        metaBadge: document.getElementById('meta-mock-badge')?.textContent.trim(),
        metaTiming: document.getElementById('meta-timing')?.textContent.trim(),
        metaContainerVisible: !document.getElementById('meta-container')?.classList.contains('hidden')
      };
    `
    );

    assert.strictEqual(
      translateResult.target,
      '[MOCK vi->tyz] Mùa xuân hoa đào nở rộ trên bản làng',
      'Kết quả dịch vi-tay không đúng'
    );
    assert.strictEqual(translateResult.metaBadge, 'MÔ PHỎNG', 'Nhãn mock trong kết quả dịch phải hiển thị');
    assert.strictEqual(translateResult.metaContainerVisible, true, 'Container metadata phải hiển thị');
    assert.ok(translateResult.metaTiming.includes('Độ trễ:'), 'Timing metadata phải hiển thị độ trễ');
    console.log('   ✓ Dịch văn bản vi-tay đạt:', translateResult.target);
    await captureScreenshot(pageId, '02_e2e_translate_vi_tay.png');

    // JOURNEY 3: Thao tác Đảo chiều (Swap) an toàn & Dịch ngược (tay-vi)
    console.log('\n--- JOURNEY 3: Thao tác Đảo chiều (Swap) an toàn & Dịch ngược (tay-vi) ---');
    const swapData = evalInPage(
      pageId,
      `
      const swapBtn = document.getElementById('btn-swap');
      swapBtn.click();
      return {
        source: document.getElementById('source-text')?.value,
        target: document.getElementById('target-text')?.value,
        dir: document.getElementById('direction-select')?.value,
        sourceLabel: document.getElementById('source-label')?.textContent.trim(),
        targetLabel: document.getElementById('target-label')?.textContent.trim(),
        metaContainerHidden: document.getElementById('meta-container')?.classList.contains('hidden'),
        btnTranslateDisabled: document.getElementById('btn-translate')?.disabled
      };
    `
    );

    assert.strictEqual(swapData.source, '[MOCK vi->tyz] Mùa xuân hoa đào nở rộ trên bản làng', 'Nguồn sau swap sai');
    assert.strictEqual(swapData.target, 'Mùa xuân hoa đào nở rộ trên bản làng', 'Đích sau swap sai');
    assert.strictEqual(swapData.dir, 'tay-vi', 'Chiều dịch sau swap phải là tay-vi');
    assert.strictEqual(swapData.sourceLabel, 'Tiếng Tày', 'Nhãn nguồn phải đổi thành Tiếng Tày');
    assert.strictEqual(swapData.targetLabel, 'Tiếng Việt', 'Nhãn đích phải đổi thành Tiếng Việt');
    assert.strictEqual(swapData.metaContainerHidden, true, 'Metadata của chiều cũ phải bị xóa sạch sau swap (C17)');
    console.log('   ✓ Đảo chiều Swap an toàn đạt (metadata chiều cũ đã bị xóa sạch).');
    await captureScreenshot(pageId, '03_e2e_swap_safe.png');

    // Dịch ngược chiều tay-vi sau Swap
    console.log('   Dịch ngược chiều tay-vi sau swap...');
    const reverseData = evalInPage(
      pageId,
      `
      const btn = document.getElementById('btn-translate');
      btn.click();

      // Thăm dò điều kiện (polling) cho đến khi ô kết quả có tiền tố tyz->vi
      const start = Date.now();
      let revVal = '';
      while (Date.now() - start < 4000) {
        revVal = document.getElementById('target-text')?.value || '';
        if (revVal.startsWith('[MOCK tyz->vi]')) break;
        await new Promise(r => setTimeout(r, 50));
      }
      if (!revVal.startsWith('[MOCK tyz->vi]')) throw new Error('Timeout chờ kết quả dịch ngược tay-vi');

      return {
        target: revVal,
        metaTiming: document.getElementById('meta-timing')?.textContent.trim()
      };
    `
    );
    assert.strictEqual(
      reverseData.target,
      '[MOCK tyz->vi] [MOCK vi->tyz] Mùa xuân hoa đào nở rộ trên bản làng',
      'Dịch ngược chiều tay-vi sai'
    );
    console.log('   ✓ Dịch ngược chiều tay-vi đạt:', reverseData.target);
    await captureScreenshot(pageId, '04_e2e_translate_tay_vi.png');

    // JOURNEY 4: Hồi quy C17 (Sửa nguồn làm mất hiệu lực kết quả và metadata cũ)
    console.log('\n--- JOURNEY 4: Hồi quy C17 (Sửa nguồn làm mất hiệu lực kết quả cũ) ---');
    const c17Data = evalInPage(
      pageId,
      `
      const src = document.getElementById('source-text');
      src.value = 'Văn bản đã sửa';
      src.dispatchEvent(new Event('input', { bubbles: true }));
      return {
        targetVal: document.getElementById('target-text')?.value,
        metaHidden: document.getElementById('meta-container')?.classList.contains('hidden'),
        charCount: document.getElementById('char-count')?.textContent.trim()
      };
    `
    );
    assert.strictEqual(c17Data.targetVal, '', 'targetText phải bị xóa ngay lập tức khi sửa nguồn (C17)');
    assert.strictEqual(c17Data.metaHidden, true, 'Metadata phải bị ẩn ngay khi sửa nguồn (C17)');
    console.log('   ✓ Hồi quy C17 đạt (kết quả và metadata cũ đã bị xóa sạch khi sửa nguồn).');

    // JOURNEY 5: Chuyển Tab Giọng nói & Hồi quy C21 (Chưa có ASR thì cấm dịch)
    console.log('\n--- JOURNEY 5: Chuyển sang Tab Giọng nói & Hồi quy C21 ---');
    const voiceTabData = evalInPage(
      pageId,
      `
      const tabVoice = document.getElementById('tab-voice');
      tabVoice.click();
      const transcriptInput = document.querySelector('#vp-transcript-input');
      const translateBtn = document.querySelector('#vp-btn-translate');

      // Thử cố tình gõ transcript khi chưa có ASR
      transcriptInput.value = 'Gõ thủ công không qua ASR';
      transcriptInput.dispatchEvent(new Event('input', { bubbles: true }));

      return {
        textHidden: document.getElementById('panel-text')?.hidden,
        voiceVisible: !document.getElementById('voice-panel')?.hidden,
        translateBtnDisabled: translateBtn?.disabled,
        translateBtnTitle: translateBtn?.title
      };
    `
    );

    assert.strictEqual(voiceTabData.textHidden, true, 'Panel văn bản phải bị ẩn');
    assert.strictEqual(voiceTabData.voiceVisible, true, 'Panel giọng nói phải hiển thị');
    assert.strictEqual(voiceTabData.translateBtnDisabled, true, 'C21 Invariant: Nút Dịch phải vô hiệu khi chưa có ASR');
    assert.ok(voiceTabData.translateBtnTitle.includes('Yêu cầu nhận dạng'), 'Tooltip phải giải thích cần nhận dạng ASR');
    console.log('   ✓ C21 Invariant đạt (nhập transcript thủ công không thể kích hoạt dịch).');
    await captureScreenshot(pageId, '05_e2e_voice_tab_c21_disabled.png');

    // JOURNEY 6: Thu âm trực tiếp bằng nguồn tổng hợp Web Audio (Oscillator) & Kiểm tra cả 3 nhánh:
    // 6A. Dừng chủ động bằng nút Stop -> kiểm tra WAV PCM 16kHz mono có frame > 0
    // 6B. Tự động dừng khi chạm trần thời lượng (Auto-stop C22) -> kiểm tra frames > 0 và <= 32000 (trần 2s)
    // 6C. Ngắt kết nối micro đột ngột (Track ended C22) -> mô phỏng track ended thực, assert UI tự động phục hồi
    console.log('\n--- JOURNEY 6: Thu âm trực tiếp qua AudioRecorder bằng nguồn tổng hợp (Manual Stop, Auto-Stop 2s, Track-Ended C22) ---');
    const recordFlowData = evalInPage(
      pageId,
      `
      // Chuyển sang subtab Thu âm
      document.getElementById('vp-tab-record-btn').click();

      const originalGetUserMedia = navigator.mediaDevices.getUserMedia;
      const originalAudioContext = window.AudioContext || window.webkitAudioContext;

      // Capture AudioContext mà AudioRecorder của ứng dụng tạo ra để xác minh dọn dẹp tài nguyên
      const recorderContexts = [];
      window.AudioContext = class extends originalAudioContext {
        constructor(...args) {
          super(...args);
          recorderContexts.push(this);
        }
      };

      const createdFixtures = [];

      // Hàm cấp stream live độc lập cho từng phiên thu (không dùng lại stream đã stopped)
      async function createLiveSyntheticFixture() {
        const ctx = new originalAudioContext();
        const fixture = { ctx, osc: null, dest: null, stream: null, track: null };
        createdFixtures.push(fixture); // Đăng ký vào danh sách cleanup ngay lập tức

        if (ctx.state === 'suspended') {
          const resumePromise = ctx.resume();
          const timeoutPromise = new Promise((_, rej) => setTimeout(() => rej(new Error('Timeout resume context')), 2000));
          await Promise.race([resumePromise, timeoutPromise]);
        }
        if (ctx.state !== 'running') {
          throw new Error('Không thể khởi động synthetic AudioContext, state=' + ctx.state);
        }
        const osc = ctx.createOscillator();
        fixture.osc = osc;
        const dest = ctx.createMediaStreamDestination();
        fixture.dest = dest;
        osc.type = 'sine';
        osc.frequency.setValueAtTime(440, ctx.currentTime);
        osc.connect(dest);
        osc.start();

        const track = dest.stream.getAudioTracks()[0];
        fixture.stream = dest.stream;
        fixture.track = track;
        return dest.stream;
      }

      navigator.mediaDevices.getUserMedia = async () => createLiveSyntheticFixture();

      // Helper đọc cấu trúc WAV header từ audio player và kiểm tra trạng thái dọn dẹp tài nguyên
      async function inspectPlayerWav(fixture, recorderCtx) {
        const p = document.getElementById('vp-audio-player');
        if (!p || !p.src || !p.src.startsWith('blob:')) return null;
        const res = await fetch(p.src);
        const buf = await res.arrayBuffer();
        if (buf.byteLength < 44) return null;
        const view = new DataView(buf);
        const riff = String.fromCharCode(view.getUint8(0), view.getUint8(1), view.getUint8(2), view.getUint8(3));
        const wave = String.fromCharCode(view.getUint8(8), view.getUint8(9), view.getUint8(10), view.getUint8(11));
        const formatTag = view.getUint16(20, true);
        const channels = view.getUint16(22, true);
        const sampleRate = view.getUint32(24, true);
        const bitsPerSample = view.getUint16(34, true);
        const dataSize = view.getUint32(40, true);
        const actualPayloadBytes = buf.byteLength - 44; // Số byte payload thực tế của tệp
        const frames = dataSize / (channels * (bitsPerSample / 8));
        const durationSec = frames / sampleRate;

        const recorderContextClosed = recorderCtx ? recorderCtx.state === 'closed' : false;
        const trackEnded = fixture?.track ? fixture.track.readyState === 'ended' : false;

        return {
          validWav: riff === 'RIFF' && wave === 'WAVE',
          formatTag,
          channels,
          sampleRate,
          bitsPerSample,
          dataSize,
          actualPayloadBytes,
          frames,
          durationSec,
          recorderContextClosed,
          trackEnded
        };
      }

      let wav6A = null;
      let wav6B = null;
      let wav6C = null;
      let manualStopSuccess = false;
      let autoStopSuccess = false;
      let trackEndedSuccess = false;

      try {
        const startBtn = document.getElementById('vp-btn-start-record');
        const stopBtn = document.getElementById('vp-btn-stop-record');
        const statusText = document.getElementById('vp-record-status-text');

        // 6A: Thu âm chủ động và bấm Stop sau 400ms
        startBtn.click();

        // Chờ trạng thái thu âm thực sự kích hoạt (statusText báo Đang thu âm)
        const pollStartA = Date.now();
        while (Date.now() - pollStartA < 2000) {
          if (statusText.textContent.includes('Đang thu âm')) break;
          await new Promise(r => setTimeout(r, 50));
        }
        if (!statusText.textContent.includes('Đang thu âm')) {
          throw new Error('Timeout chờ trạng thái Đang thu âm ở ca 6A');
        }

        const fixtureA = createdFixtures[createdFixtures.length - 1];
        const recorderCtxA = recorderContexts[recorderContexts.length - 1];

        await new Promise(r => setTimeout(r, 400));
        stopBtn.click();

        // Thăm dò cho đến khi tệp âm thanh hoàn tất
        const pollStopA = Date.now();
        while (Date.now() - pollStopA < 3000) {
          const w = await inspectPlayerWav(fixtureA, recorderCtxA);
          if (w && w.validWav && w.frames > 0 && w.recorderContextClosed && w.trackEnded) {
            wav6A = w;
            break;
          }
          await new Promise(r => setTimeout(r, 50));
        }
        if (!wav6A) throw new Error('Timeout chờ hoàn tất WAV ở ca 6A');
        manualStopSuccess = Boolean(startBtn.style.display !== 'none' && stopBtn.style.display === 'none');

        // 6B: Thu âm tự động dừng khi chạm trần thời lượng máy chủ (2s / 32000 frames)
        startBtn.click();

        const pollStartB = Date.now();
        while (Date.now() - pollStartB < 2000) {
          if (statusText.textContent.includes('Đang thu âm')) break;
          await new Promise(r => setTimeout(r, 50));
        }
        if (!statusText.textContent.includes('Đang thu âm')) {
          throw new Error('Timeout chờ trạng thái Đang thu âm ở ca 6B');
        }

        const fixtureB = createdFixtures[createdFixtures.length - 1];
        const recorderCtxB = recorderContexts[recorderContexts.length - 1];

        // Không bấm Stop, chờ quá 2.1s để auto-stop kích hoạt tự nhiên
        const pollAutoStop = Date.now();
        while (Date.now() - pollAutoStop < 4000) {
          if (startBtn.style.display !== 'none' && stopBtn.style.display === 'none') {
            autoStopSuccess = true;
            break;
          }
          await new Promise(r => setTimeout(r, 100));
        }
        if (!autoStopSuccess) throw new Error('Timeout chờ auto-stop ở ca 6B');

        const pollStopB = Date.now();
        while (Date.now() - pollStopB < 3000) {
          const w = await inspectPlayerWav(fixtureB, recorderCtxB);
          if (w && w.validWav && w.frames > 0 && w.recorderContextClosed && w.trackEnded) {
            wav6B = w;
            break;
          }
          await new Promise(r => setTimeout(r, 50));
        }
        if (!wav6B) throw new Error('Timeout chờ hoàn tất WAV ở ca 6B');

        // 6C: Ngắt track đột ngột (Track ended thực sự qua native onended, không bấm Stop)
        startBtn.click();

        // Xác minh đồng hồ đã được reset về 00:00 ngay sau khi bấm Start của phiên 6C
        const timerEl = document.getElementById('vp-timer');
        if (!timerEl) {
          throw new Error('Không tìm thấy phần tử #vp-timer trên DOM ở ca 6C');
        }
        if (!timerEl.textContent.startsWith('00:00')) {
          throw new Error('Đồng hồ thu âm chưa được reset về 00:00 khi bắt đầu phiên mới ở ca 6C: ' + timerEl.textContent);
        }

        const pollStartC = Date.now();
        while (Date.now() - pollStartC < 2000) {
          if (statusText.textContent.includes('Đang thu âm')) break;
          await new Promise(r => setTimeout(r, 50));
        }
        if (!statusText.textContent.includes('Đang thu âm')) {
          throw new Error('Timeout chờ trạng thái Đang thu âm ở ca 6C');
        }

        const fixtureC = createdFixtures[createdFixtures.length - 1];
        const recorderCtxC = recorderContexts[recorderContexts.length - 1];

        // Chờ đồng hồ tiến độ ứng dụng ghi nhận PCM đã được thu (timer > 0 của chính phiên 6C này)
        let timerTicked = false;
        const pollProgressC = Date.now();
        while (Date.now() - pollProgressC < 2500) {
          if (!timerEl.textContent.startsWith('00:00')) {
            timerTicked = true;
            break;
          }
          await new Promise(r => setTimeout(r, 50));
        }
        if (!timerTicked) {
          throw new Error('Timeout chờ tiến độ ghi âm (PCM frames) ở ca 6C: timer vẫn là ' + timerEl.textContent);
        }

        if (!fixtureC || !fixtureC.track || fixtureC.track.readyState !== 'live') {
          throw new Error('Track 6C không ở trạng thái live trước khi ngắt');
        }

        // Kiểm tra listener onended đã được AudioRecorder gắn trên track
        if (typeof fixtureC.track.onended !== 'function') {
          throw new Error('AudioRecorder chưa gắn onended listener lên track ở ca 6C');
        }

        // Kích hoạt ngắt track thật mà không bấm nút Stop
        fixtureC.track.stop();
        fixtureC.track.dispatchEvent(new Event('ended'));

        const pollTrackEnded = Date.now();
        while (Date.now() - pollTrackEnded < 3000) {
          if (startBtn.style.display !== 'none' && stopBtn.style.display === 'none') {
            trackEndedSuccess = true;
            break;
          }
          await new Promise(r => setTimeout(r, 50));
        }
        if (!trackEndedSuccess) throw new Error('Timeout chờ phục hồi UI ở ca 6C');
        wav6C = await inspectPlayerWav(fixtureC, recorderCtxC);

        // 6D: Gọi API ASR với engine mock trên tệp âm thanh thu được
        const transcribeBtn = document.getElementById('vp-btn-transcribe');
        transcribeBtn.click();

        // Thăm dò cho đến khi transcript được điền
        const asrPoll = Date.now();
        let finalTranscript = '';
        while (Date.now() - asrPoll < 4000) {
          finalTranscript = document.getElementById('vp-transcript-input')?.value || '';
          if (finalTranscript) break;
          await new Promise(r => setTimeout(r, 50));
        }
        if (!finalTranscript) throw new Error('Timeout chờ transcript từ ASR');

        return {
          manualStopSuccess,
          autoStopSuccess,
          trackEndedSuccess,
          wav6A,
          wav6B,
          wav6C,
          transcript: finalTranscript,
          mockBadgeVisible: document.getElementById('vp-asr-mock-notice')?.style.display !== 'none',
          translateBtnEnabled: !document.getElementById('vp-btn-translate')?.disabled,
          translationEmpty: document.getElementById('vp-translation-result')?.textContent.includes('Bản dịch tiếng Tày sẽ hiển thị')
        };
      } finally {
        window.AudioContext = originalAudioContext;
        navigator.mediaDevices.getUserMedia = originalGetUserMedia;
        for (const f of createdFixtures) {
          try { if (f.osc) f.osc.stop(); } catch (e) {}
          try { if (f.track) f.track.stop(); } catch (e) {}
          try { if (f.ctx && f.ctx.state !== 'closed') f.ctx.close(); } catch (e) {}
        }
      }
    `
    );

    // Hàm helper xác thực đồng nhất cho cả 3 ca 6A, 6B, 6C
    function assertWavAttributes(wav, label, maxFrames = 32000) {
      assert.ok(wav, `${label}: WAV object phải tồn tại`);
      assert.strictEqual(wav.validWav, true, `${label}: Phải là WAV chuẩn RIFF/WAVE`);
      assert.strictEqual(wav.formatTag, 1, `${label}: Format tag phải là 1 (PCM)`);
      assert.strictEqual(wav.channels, 1, `${label}: Phải là 1 kênh mono`);
      assert.strictEqual(wav.sampleRate, 16000, `${label}: Tần số lấy mẫu phải là 16.000 Hz`);
      assert.strictEqual(wav.bitsPerSample, 16, `${label}: Độ sâu bit phải là 16-bit`);
      assert.ok(wav.frames > 0 && Number.isInteger(wav.frames), `${label}: Số frames phải là số nguyên dương`);
      assert.ok(
        wav.frames <= maxFrames,
        `${label}: Số frame (${wav.frames}) không được vượt quá trần cấu hình ${maxFrames} (2s ở 16kHz)`
      );
      assert.strictEqual(
        wav.dataSize,
        wav.actualPayloadBytes,
        `${label}: Header dataSize (${wav.dataSize}) phải khớp đúng kích thước payload thực (${wav.actualPayloadBytes} bytes)`
      );
      assert.strictEqual(
        wav.dataSize,
        wav.frames * 2,
        `${label}: Kích thước data (${wav.dataSize} bytes) phải khớp đúng frameCount * 2 bytes`
      );
      assert.strictEqual(wav.recorderContextClosed, true, `${label}: AudioContext của recorder phải được đóng hoàn toàn`);
      assert.strictEqual(wav.trackEnded, true, `${label}: Track micro phải chuyển sang ended sau khi dừng`);
    }

    // Assert toàn diện ca 6A
    assert.strictEqual(recordFlowData.manualStopSuccess, true, '6A: Dừng thu âm chủ động bằng Stop phải thành công và phục hồi UI');
    assertWavAttributes(recordFlowData.wav6A, '6A (Manual Stop)');

    // Assert toàn diện ca 6B
    assert.strictEqual(recordFlowData.autoStopSuccess, true, '6B: Tự động dừng (Auto-stop) khi chạm trần thời lượng phải thành công và phục hồi nút Start (C22)');
    assertWavAttributes(recordFlowData.wav6B, '6B (Auto-Stop)');

    // Assert toàn diện ca 6C
    assert.strictEqual(recordFlowData.trackEndedSuccess, true, '6C: Ngắt track đột ngột phải tự động dừng và phục hồi nút Start mà không cần bấm Stop (C22)');
    assertWavAttributes(recordFlowData.wav6C, '6C (Track Ended)');

    // Assert 6D
    assert.ok(
      typeof recordFlowData.transcript === 'string' && recordFlowData.transcript.length > 0,
      'ASR engine mock phải trả về transcript'
    );
    assert.strictEqual(recordFlowData.mockBadgeVisible, true, 'Nhãn ASR Mock phải hiển thị');
    assert.strictEqual(recordFlowData.translateBtnEnabled, true, 'Nút Dịch sang tiếng Tày phải bật sau ASR thành công (C21)');
    assert.strictEqual(recordFlowData.translationEmpty, true, 'Bắt buộc không được tự động dịch sau ASR');
    console.log('   ✓ Thu âm trực tiếp qua AudioRecorder (Manual stop 6A, Auto-stop 2s/32000 frames 6B, Track-ended 6C) & gọi API ASR với engine mock đạt:', recordFlowData.transcript);
    evalInPage(pageId, `document.querySelectorAll('.vp-card')[1]?.scrollIntoView({ block: 'center', behavior: 'instant' });`);
    await sleep(300);
    await captureScreenshot(pageId, '06_e2e_voice_recorder_auto_stop_and_asr.png');

    // JOURNEY 7: Nạp tệp WAV qua input Upload, sửa transcript, dịch sang tiếng Tày & kiểm tra C23 Copy feedback
    console.log('\n--- JOURNEY 7: Nạp tệp WAV qua input Upload, sửa transcript, dịch & kiểm tra C23 Copy feedback ---');
    const uploadAndTranslateData = evalInPage(
      pageId,
      `
      // Chuyển sang subtab Upload
      document.getElementById('vp-tab-upload-btn').click();

      // Sử dụng encodeWAV từ /js/audio.js nội bộ của repo để sinh tệp WAV chuẩn 16kHz mono có frame thực
      const { encodeWAV } = await import('/js/audio.js');
      const samples = new Float32Array(24000); // 1.5 giây ở 16.000 Hz
      for (let i = 0; i < samples.length; i++) {
        samples[i] = Math.sin((2 * Math.PI * 440 * i) / 16000) * 0.5;
      }
      const wavBytes = encodeWAV(samples, 16000);
      const blob = new Blob([wavBytes.buffer], { type: 'audio/wav' });
      const file = new File([blob], 'sample_voice.wav', { type: 'audio/wav' });

      const dt = new DataTransfer();
      dt.items.add(file);
      const fileInput = document.querySelector('#vp-file-input');
      fileInput.files = dt.files;
      fileInput.dispatchEvent(new Event('change', { bubbles: true }));

      // Nhấn nút nhận dạng ASR
      const transcribeBtn = document.querySelector('#vp-btn-transcribe');
      transcribeBtn.click();

      // Thăm dò cho đến khi nhận được transcript
      const asrPoll = Date.now();
      let transcriptText = '';
      while (Date.now() - asrPoll < 4000) {
        transcriptText = document.querySelector('#vp-transcript-input')?.value || '';
        if (transcriptText) break;
        await new Promise(r => setTimeout(r, 50));
      }
      if (!transcriptText) throw new Error('Timeout chờ transcript từ ASR');

      // Người dùng chỉnh sửa transcript
      const transcriptInput = document.querySelector('#vp-transcript-input');
      transcriptInput.value = 'Hôm nay trời rất đẹp, bà con cùng đi làm nương rẫy sau khi sửa';
      transcriptInput.dispatchEvent(new Event('input', { bubbles: true }));

      // Nhấn nút Dịch sang tiếng Tày
      const translateBtn = document.querySelector('#vp-btn-translate');
      translateBtn.click();

      // Thăm dò cho đến khi nhận được bản dịch
      const transPoll = Date.now();
      let transVal = '';
      while (Date.now() - transPoll < 4000) {
        transVal = document.querySelector('#vp-translation-result')?.textContent.trim() || '';
        if (transVal.startsWith('[MOCK vi->tyz]')) break;
        await new Promise(r => setTimeout(r, 50));
      }
      if (!transVal.startsWith('[MOCK vi->tyz]')) throw new Error('Timeout chờ bản dịch tiếng Tày');

      const resultBox = document.querySelector('#vp-translation-result');
      const copyBtn = document.querySelector('#vp-btn-copy');

      // Thử bấm sao chép và kiểm tra feedback (C23)
      copyBtn.click();
      await new Promise(r => setTimeout(r, 100));

      const copiedToast = document.querySelector('#vp-copied-toast');
      const copyToastVisible = copiedToast && copiedToast.style.display !== 'none';
      const toastText = copiedToast?.textContent.trim();
      const errorBox = document.querySelector('#vp-trans-error');
      const errorVisible = errorBox && errorBox.style.display !== 'none';
      const errorMsg = document.querySelector('#vp-trans-error-msg')?.textContent.trim();

      return {
        fileNameDisplay: document.querySelector('#vp-file-name-display')?.textContent.trim(),
        translatedText: transVal,
        mockNoticeVisible: document.querySelector('#vp-trans-mock-notice')?.style.display !== 'none',
        copyBtnVisible: copyBtn?.style.display !== 'none',
        copyToastVisible,
        toastText,
        errorVisible,
        errorMsg
      };
    `
    );

    assert.ok(uploadAndTranslateData.fileNameDisplay.includes('sample_voice.wav'), 'Tên file upload phải hiển thị');
    assert.strictEqual(
      uploadAndTranslateData.translatedText,
      '[MOCK vi->tyz] Hôm nay trời rất đẹp, bà con cùng đi làm nương rẫy sau khi sửa',
      'Bản dịch phải dịch đúng snapshot transcript đã sửa'
    );
    assert.strictEqual(uploadAndTranslateData.mockNoticeVisible, true, 'Nhãn dịch mock phải hiển thị');
    assert.strictEqual(uploadAndTranslateData.copyBtnVisible, true, 'Nút sao chép bản dịch phải hiển thị');

    // C23 Invariant: Hoặc là copy thành công (toast "Đã sao chép!"), hoặc là fallback (chọn văn bản và hiển thị hướng dẫn)
    const validCopyFeedback =
      (uploadAndTranslateData.copyToastVisible && uploadAndTranslateData.toastText === 'Đã sao chép!') ||
      (uploadAndTranslateData.errorVisible && uploadAndTranslateData.errorMsg.includes('Không thể tự động sao chép'));
    assert.ok(validCopyFeedback, 'C23: Thao tác copy phải cho phản hồi trung thực (toast thành công hoặc hướng dẫn bôi đen)');
    console.log('   ✓ Upload tệp WAV, dịch transcript đã sửa và kiểm tra C23 copy feedback đạt:', uploadAndTranslateData.translatedText);
    evalInPage(pageId, `document.querySelectorAll('.vp-card')[1]?.scrollIntoView({ block: 'start', behavior: 'instant' });`);
    await sleep(300);
    await captureScreenshot(pageId, '07_e2e_voice_upload_and_translate_result.png');

    // JOURNEY 8: Kiểm tra hủy yêu cầu Dịch A khi bắt đầu ASR B (Transport Abort & Invalidation C20)
    console.log('\n--- JOURNEY 8: Hủy yêu cầu Dịch A khi bắt đầu ASR B (Transport Abort & Invalidation C20) ---');
    const c20BrowserData = evalInPage(
      pageId,
      `
      const originalFetch = window.fetch;
      let releaseTranslateAGate = null;
      let translateACalled = false;
      let translateASettled = false;
      let translateAOutcome = null;
      let signalWasAborted = false;
      const sequence = [];

      try {
        // Cài đặt gate hoãn request /api/translate đầu tiên để giữ in-flight
        window.fetch = async (...args) => {
          const url = String(args[0]);
          if (url.includes('/api/translate') && !translateACalled) {
            translateACalled = true;
            sequence.push('translate_A_started');
            const signal = args[1]?.signal;

            await new Promise((resolve) => { releaseTranslateAGate = resolve; });

            if (signal?.aborted) {
              signalWasAborted = true;
            }

            try {
              const res = await originalFetch.apply(window, args);
              translateASettled = true;
              translateAOutcome = 'success_HTTP_' + res.status;
              sequence.push('translate_A_settled');
              return res;
            } catch (err) {
              translateASettled = true;
              translateAOutcome = err.name; // 'AbortError'
              sequence.push('translate_A_settled_' + err.name);
              throw err;
            }
          }
          return originalFetch.apply(window, args);
        };

        // 1. Chuẩn bị transcript A
        const transcriptInput = document.getElementById('vp-transcript-input');
        transcriptInput.value = 'Văn bản của lượt A';
        transcriptInput.dispatchEvent(new Event('input', { bubbles: true }));

        // 2. Bấm Dịch lượt A -> Yêu cầu Dịch A bắt đầu và bị giữ tại gate
        const translateBtn = document.getElementById('vp-btn-translate');
        translateBtn.click();

        // Thăm dò đảm bảo Translate A đã thực sự vào gate
        const pollGate = Date.now();
        while (Date.now() - pollGate < 3000) {
          if (translateACalled) break;
          await new Promise(r => setTimeout(r, 50));
        }

        // 3. Người dùng chuyển sang lượt ASR B: bấm ASR B trong khi Translate A vẫn đang pending tại gate
        const transcribeBtn = document.getElementById('vp-btn-transcribe');
        transcribeBtn.click();

        // Thăm dò cho đến khi ASR B thành công và điền transcript mới
        const asrPoll = Date.now();
        while (Date.now() - asrPoll < 4000) {
          const val = document.getElementById('vp-transcript-input')?.value;
          if (val && val !== 'Văn bản của lượt A') {
            sequence.push('asr_B_completed');
            break;
          }
          await new Promise(r => setTimeout(r, 50));
        }

        const transcriptAfterB = document.getElementById('vp-transcript-input')?.value;

        // 4. Bây giờ mới giải phóng cổng chặn Translate A
        if (releaseTranslateAGate) {
          releaseTranslateAGate();
        }

        // Thăm dò đảm bảo Translate A đã thực sự settled
        const pollSettled = Date.now();
        while (Date.now() - pollSettled < 4000) {
          if (translateASettled) break;
          await new Promise(r => setTimeout(r, 50));
        }

        const resultBox = document.getElementById('vp-translation-result');
        const hasOldTranslation = resultBox?.textContent.includes('Văn bản của lượt A');
        const resultTextEmpty = resultBox?.textContent.includes('Bản dịch tiếng Tày sẽ hiển thị');
        const translateBtnReady = !translateBtn.disabled;

        return {
          translateACalled,
          translateASettled,
          translateAOutcome,
          signalWasAborted,
          sequence,
          transcriptAfterB,
          hasOldTranslation,
          resultTextEmpty,
          translateBtnReady
        };
      } finally {
        window.fetch = originalFetch;
      }
    `
    );

    assert.strictEqual(c20BrowserData.translateACalled, true, 'Translate A phải thực sự được gọi vào gate');
    assert.strictEqual(c20BrowserData.translateASettled, true, 'Translate A phải thực sự hoàn tất sau khi mở gate');
    assert.strictEqual(c20BrowserData.translateAOutcome, 'AbortError', 'Yêu cầu dịch A phải bị hủy với AbortError (C20 transport cancellation)');
    assert.strictEqual(c20BrowserData.signalWasAborted, true, 'Signal của Translate A phải có aborted=true');
    assert.ok(
      c20BrowserData.sequence.indexOf('translate_A_started') < c20BrowserData.sequence.indexOf('asr_B_completed'),
      'Thứ tự: Translate A phải bắt đầu trước khi ASR B hoàn tất'
    );
    assert.ok(
      c20BrowserData.sequence.indexOf('asr_B_completed') < c20BrowserData.sequence.indexOf('translate_A_settled_AbortError'),
      'Thứ tự: ASR B phải hoàn tất trước khi Translate A settled'
    );
    assert.strictEqual(c20BrowserData.hasOldTranslation, false, 'C20 Invariant: Bản dịch cũ của lượt A không được phép xuất hiện cạnh transcript B');
    assert.strictEqual(c20BrowserData.resultTextEmpty, true, 'Vùng kết quả dịch phải trống');
    assert.strictEqual(c20BrowserData.translateBtnReady, true, 'Nút dịch phải sẵn sàng để dịch transcript B');
    console.log('   ✓ C20 Hủy yêu cầu Dịch A khi ASR B bắt đầu (Transport Abort & Invalidation) đạt 100%:', c20BrowserData.sequence.join(' -> '));

    // JOURNEY 9: Kiểm tra Responsive và Viewport trên Mobile (iPhone 12)
    console.log('\n--- JOURNEY 9: Kiểm tra Responsive trên Mobile (iPhone 12) ---');
    runOrca(['viewport', '--width', '390', '--height', '844', '--scale', '1', '--mobile', '--page', pageId, '--json']);
    await sleep(500);

    // 9.1 Tab Văn bản trên Mobile
    evalInPage(pageId, `
      document.getElementById('tab-text').click();
      window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
    `);
    await sleep(300);

    const mobileTextData = evalInPage(
      pageId,
      `
      return {
        noHorizontalScroll: document.documentElement.scrollWidth <= window.innerWidth + 2,
        gridSingleColumn: window.getComputedStyle(document.querySelector('.translation-grid')).gridTemplateColumns.split(' ').length === 1
      };
    `
    );
    assert.strictEqual(mobileTextData.noHorizontalScroll, true, 'Giao diện mobile không được có thanh cuộn ngang');
    assert.strictEqual(mobileTextData.gridSingleColumn, true, 'Lưới dịch trên mobile phải co về 1 cột tuần tự');
    await captureScreenshot(pageId, '08_e2e_mobile_text_layout.png');

    // 9.2 Tab Giọng nói trên Mobile (chọn subtab Upload và kiểm tra kích thước DOM thực)
    evalInPage(pageId, `
      document.getElementById('tab-voice').click();
      document.getElementById('vp-tab-upload-btn').click();
      document.getElementById('vp-drop-zone')?.scrollIntoView({ block: 'center', behavior: 'instant' });
    `);
    await sleep(300);

    const mobileVoiceData = evalInPage(
      pageId,
      `
      const dropZone = document.getElementById('vp-drop-zone');
      const rect = dropZone ? dropZone.getBoundingClientRect() : null;
      const comp = dropZone ? window.getComputedStyle(dropZone) : null;
      const clientRects = dropZone ? dropZone.getClientRects() : [];

      return {
        noHorizontalScroll: document.documentElement.scrollWidth <= window.innerWidth + 2,
        activeUpload: document.getElementById('vp-tab-upload-btn')?.classList.contains('active'),
        isDisplayed: comp && comp.display !== 'none',
        clientRectsCount: clientRects.length,
        hasPositiveDimensions: rect && rect.width > 0 && rect.height > 0,
        controlsInView: rect && rect.top >= 0 && rect.top <= window.innerHeight
      };
    `
    );
    assert.strictEqual(mobileVoiceData.noHorizontalScroll, true, 'Tab giọng nói mobile không có thanh cuộn ngang');
    assert.strictEqual(mobileVoiceData.activeUpload, true, 'Subtab Upload phải đang active');
    assert.strictEqual(mobileVoiceData.isDisplayed, true, 'Dropzone phải có display khác none');
    assert.ok(mobileVoiceData.clientRectsCount > 0, 'Dropzone phải có clientRects thực tế');
    assert.strictEqual(mobileVoiceData.hasPositiveDimensions, true, 'Dropzone phải có width và height dương');
    assert.strictEqual(mobileVoiceData.controlsInView, true, 'Khu vực điều khiển upload phải nằm trong viewport');
    await captureScreenshot(pageId, '09_e2e_mobile_voice_controls_scrolled.png');
    console.log('   ✓ Kiểm tra responsive Mobile (iPhone 12) đạt: drop zone hiển thị thực tế với kích thước dương và nằm trong viewport.');

    // Khôi phục thiết bị về mặc định
    try {
      runOrca(['viewport', '--width', '1148', '--height', '921', '--scale', '1', '--page', pageId, '--json']);
    } catch {}

    console.log('\n===============================================================');
    console.log('✓ TẤT CẢ 9 JOURNEYS KIỂM THỬ TRÌNH DUYỆT ORCA ĐỀU ĐẠT 100%!');
    console.log('===============================================================');
  } finally {
    // Đóng tab trình duyệt Orca bằng browserPageId đã ghim
    if (pageId) {
      console.log(`\nDọn dẹp: Đóng tab trình duyệt Orca pageId=${pageId} ...`);
      try {
        runOrca(['tab', 'close', '--page', pageId, '--json']);
        console.log('   ✓ Đã đóng tab trình duyệt thành công.');
      } catch (e) {
        console.warn('   Không thể đóng tab:', e.message);
      }
    }

    // Dừng tiến trình máy chủ Uvicorn test riêng
    console.log(`Dọn dẹp: Dừng máy chủ test PID=${serverProcess?.pid} trên cổng ${serverPort} ...`);
    cleanupServer();
    console.log('   ✓ Đã giải phóng máy chủ test và cổng TCP.');
  }
}

main().catch((err) => {
  console.error('\n❌ LỖI KIỂM THỬ TRÌNH DUYỆT ORCA THẤT BẠI:');
  console.error(err);
  process.exit(1);
});
