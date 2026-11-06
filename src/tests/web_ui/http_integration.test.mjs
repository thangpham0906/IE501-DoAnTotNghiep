/**
 * http_integration.test.mjs - Bộ kiểm thử tích hợp HTTP cho Web Demo API và Static Serving (§4, §6.1, §8.2).
 * Chạy với Node.js test runner: node --test src/tests/web_ui/http_integration.test.mjs
 *
 * Kiểm tra toàn diện trên máy chủ Uvicorn do bài test tự khởi chạy trên cổng trống:
 * - Phục vụ Static assets (index.html, CSS, JS nội bộ không CDN, an toàn MIME type)
 * - Dịch văn bản 2 chiều (vi-tay, tay-vi, Unicode non-BMP, giới hạn ranh giới, lỗi rỗng)
 * - Upload và nhận dạng ASR từ tệp WAV mẫu, từ chối định dạng sai
 * - Đảm bảo chỉ dừng PID do bài test sở hữu, không nhận server lạ
 */

import test, { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import net from 'node:net';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, '../../../');

let serverProcess = null;
let serverPort = null;
let serverUrl = null;
let serverLogs = '';

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

before(async () => {
  serverPort = await findFreePort();
  serverUrl = `http://127.0.0.1:${serverPort}`;

  const pythonBin = fs.existsSync(path.join(REPO_ROOT, '.venv/bin/python'))
    ? path.join(REPO_ROOT, '.venv/bin/python')
    : 'python3';

  serverProcess = spawn(
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
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    }
  );

  serverProcess.stderr.on('data', (d) => {
    serverLogs += d.toString();
  });
  serverProcess.stdout.on('data', (d) => {
    serverLogs += d.toString();
  });

  // Chờ máy chủ sẵn sàng và engine nạp xong
  const startTime = Date.now();
  let isReady = false;
  while (Date.now() - startTime < 8000) {
    try {
      const res = await fetch(`${serverUrl}/api/health`, { signal: AbortSignal.timeout(400) });
      if (res.ok) {
        const data = await res.json();
        if (data.status === 'ready' && data.translation?.state === 'ready' && data.asr?.state === 'ready') {
          isReady = true;
          break;
        }
      }
    } catch {}
    await new Promise((r) => setTimeout(r, 100));
  }

  if (!isReady) {
    if (serverProcess) {
      serverProcess.kill('SIGTERM');
      serverProcess = null;
    }
    throw new Error(`Máy chủ test Uvicorn tại ${serverUrl} không khởi động kịp. Logs:\n${serverLogs}`);
  }
});

after(() => {
  if (serverProcess && serverProcess.pid) {
    try {
      serverProcess.kill('SIGTERM');
    } catch {}
    serverProcess = null;
  }
});

describe('HTTP Integration - Phục vụ tài nguyên tĩnh & Không CDN (§6.1)', () => {
  it('GET / trả về index.html hợp lệ với tiêu đề và không chứa liên kết CDN', async () => {
    const res = await fetch(`${serverUrl}/`);
    assert.equal(res.status, 200);
    assert.ok(res.headers.get('content-type').includes('text/html'));

    const html = await res.text();
    assert.ok(html.includes('<title>Dịch máy Việt - Tày & Thử nghiệm Giọng nói</title>'));
    assert.ok(html.includes('href="/css/app.css"'));
    assert.ok(html.includes('href="/css/voice.css"'));
    assert.ok(html.includes('src="/js/app.js"'));

    // Không sử dụng bất kỳ CDN bên ngoài nào
    assert.equal(html.includes('cdnjs.cloudflare.com'), false);
    assert.equal(html.includes('cdn.jsdelivr.net'), false);
    assert.equal(html.includes('unpkg.com'), false);
  });

  it('GET /css/app.css và /css/voice.css trả về đúng Content-Type text/css', async () => {
    const resApp = await fetch(`${serverUrl}/css/app.css`);
    assert.equal(resApp.status, 200);
    assert.ok(resApp.headers.get('content-type').includes('text/css'));

    const resVoice = await fetch(`${serverUrl}/css/voice.css`);
    assert.equal(resVoice.status, 200);
    assert.ok(resVoice.headers.get('content-type').includes('text/css'));
  });

  it('GET /js/app.js, /js/translation.js, /js/voice.js trả về đúng mã JavaScript', async () => {
    for (const mod of ['app.js', 'translation.js', 'voice.js', 'api_client.js', 'audio.js', 'text_utils.js']) {
      const res = await fetch(`${serverUrl}/js/${mod}`);
      assert.equal(res.status, 200, `Module ${mod} phải tải thành công (HTTP 200)`);
      const ct = res.headers.get('content-type') || '';
      assert.ok(ct.includes('javascript'), `Module ${mod} phải có MIME type javascript`);
    }
  });

  it('phòng thủ Path Traversal: các yêu cầu thoát thư mục tĩnh trả về 404', async () => {
    const res = await fetch(`${serverUrl}/css/../main.py`);
    assert.equal(res.status, 404);
  });
});

describe('HTTP Integration - Tích hợp API Backend thật (§4, §6.2)', () => {
  it('GET /api/health trả về trạng thái ready và thông số mock đầy đủ', async () => {
    const res = await fetch(`${serverUrl}/api/health`);
    assert.equal(res.status, 200);
    const data = await res.json();

    assert.equal(data.status, 'ready');
    assert.equal(data.api_version, '1');
    assert.equal(data.translation.state, 'ready');
    assert.equal(data.translation.is_mock, true);
    assert.deepEqual(data.translation.supported_directions, ['vi-tay', 'tay-vi']);
    assert.equal(data.asr.state, 'ready');
    assert.equal(data.asr.is_mock, true);
    assert.ok(data.limits.max_text_length >= 1000);
  });

  it('GET /api/models trả về danh sách bundle mô hình khả dụng', async () => {
    const res = await fetch(`${serverUrl}/api/models`);
    assert.equal(res.status, 200);
    const data = await res.json();

    assert.ok(Array.isArray(data.models));
    assert.ok(data.models.length >= 1);
    const defaultModel = data.models.find((m) => m.is_default);
    assert.ok(defaultModel, 'Phải có một mô hình mặc định');
    assert.equal(defaultModel.id, 'mock-demo');
  });

  it('POST /api/translate chiều vi-tay thành công với model metadata và timing', async () => {
    const res = await fetch(`${serverUrl}/api/translate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: 'Bản làng vào mùa xuân rất đẹp',
        direction: 'vi-tay',
      }),
    });

    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.status, 'success');
    assert.equal(data.direction, 'vi-tay');
    assert.ok(data.translation.startsWith('[MOCK vi->tyz]'));
    assert.ok(typeof data.latency_ms === 'number');
    assert.ok(typeof data.queue_ms === 'number');
    assert.equal(data.model_metadata.is_mock, true);
  });

  it('POST /api/translate chiều tay-vi thành công', async () => {
    const res = await fetch(`${serverUrl}/api/translate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: 'Vằn nay bấc đây',
        direction: 'tay-vi',
      }),
    });

    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.status, 'success');
    assert.equal(data.direction, 'tay-vi');
    assert.ok(data.translation.startsWith('[MOCK tyz->vi]'));
  });

  it('POST /api/translate bảo tồn ký tự Unicode ngoài BMP (astral plane / emoji / Tày)', async () => {
    const nonBmpText = 'Chúc mừng năm mới 🌸 𠮷 bản làng Tày';
    const res = await fetch(`${serverUrl}/api/translate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: nonBmpText,
        direction: 'vi-tay',
      }),
    });

    assert.equal(res.status, 200);
    const data = await res.json();
    assert.ok(data.translation.includes('🌸'));
    assert.ok(data.translation.includes('𠮷'));
  });

  it('POST /api/translate từ chối văn bản chỉ chứa khoảng trắng với 400 INVALID_INPUT', async () => {
    const res = await fetch(`${serverUrl}/api/translate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: '   \t\n   ',
        direction: 'vi-tay',
      }),
    });

    assert.equal(res.status, 400);
    const data = await res.json();
    assert.equal(data.error_code, 'INVALID_INPUT');
  });

  it('POST /api/translate từ chối văn bản vượt quá 1000 code points với 400 INPUT_TOO_LONG', async () => {
    const longText = 'a'.repeat(1001);
    const res = await fetch(`${serverUrl}/api/translate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: longText,
        direction: 'vi-tay',
      }),
    });

    assert.equal(res.status, 400);
    const data = await res.json();
    assert.equal(data.error_code, 'INPUT_TOO_LONG');
    assert.equal(data.detail.limit_unit, 'code_points');
    assert.equal(data.detail.current_length, 1001);
    assert.equal(data.detail.max_allowed, 1000);
  });
});

describe('HTTP Integration - Gọi API thật với engine mock cho Giọng nói ASR (§4, §6.3)', () => {
  it('POST /api/asr/transcribe với tệp WAV 16kHz mono hợp lệ trả về transcript và không tự dịch', async () => {
    const fixturePath = path.join(REPO_ROOT, 'src/tests/fixtures/valid_16k_mono.wav');
    assert.ok(fs.existsSync(fixturePath), 'Tệp fixture valid_16k_mono.wav phải tồn tại');

    const fileBuffer = fs.readFileSync(fixturePath);
    const blob = new Blob([fileBuffer], { type: 'audio/wav' });

    const formData = new FormData();
    formData.append('file', blob, 'sample.wav');
    formData.append('language', 'vi');

    const res = await fetch(`${serverUrl}/api/asr/transcribe`, {
      method: 'POST',
      body: formData,
    });

    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.status, 'success');
    assert.equal(data.language, 'vi');
    assert.ok(typeof data.transcript === 'string' && data.transcript.length > 0);
    assert.ok(typeof data.duration_sec === 'number' && data.duration_sec > 0);
    assert.equal(data.model_metadata.is_mock, true);

    // Không tự động chứa trường translation trong phản hồi ASR
    assert.equal(data.translation, undefined);
  });

  it('POST /api/asr/transcribe từ chối định dạng WAV không phải PCM 16-bit với 400 AUDIO_UNSUPPORTED_FORMAT', async () => {
    const fixturePath = path.join(REPO_ROOT, 'src/tests/fixtures/invalid_format.wav');
    const fileBuffer = fs.readFileSync(fixturePath);
    const blob = new Blob([fileBuffer], { type: 'audio/wav' });

    const formData = new FormData();
    formData.append('file', blob, 'invalid.wav');
    formData.append('language', 'vi');

    const res = await fetch(`${serverUrl}/api/asr/transcribe`, {
      method: 'POST',
      body: formData,
    });

    assert.equal(res.status, 400);
    const data = await res.json();
    assert.equal(data.error_code, 'AUDIO_UNSUPPORTED_FORMAT');
  });

  it('POST /api/asr/transcribe từ chối tệp bị cắt cụt với 400 AUDIO_INVALID', async () => {
    const fixturePath = path.join(REPO_ROOT, 'src/tests/fixtures/truncated.wav');
    const fileBuffer = fs.readFileSync(fixturePath);
    const blob = new Blob([fileBuffer], { type: 'audio/wav' });

    const formData = new FormData();
    formData.append('file', blob, 'truncated.wav');
    formData.append('language', 'vi');

    const res = await fetch(`${serverUrl}/api/asr/transcribe`, {
      method: 'POST',
      body: formData,
    });

    assert.equal(res.status, 400);
    const data = await res.json();
    assert.equal(data.error_code, 'AUDIO_INVALID');
  });
});
