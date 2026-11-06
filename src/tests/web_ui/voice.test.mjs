/**
 * voice.test.mjs - Unit tests cho luồng giao diện giọng nói (voice.js, T21).
 *
 * Kiểm tra:
 * - Khởi tạo UI, cảnh báo §6.3, và hiển thị định dạng WAV PCM 16kHz mono 16-bit.
 * - Cập nhật trạng thái setHealth() và nhãn mock độc lập cho ASR và Dịch.
 * - Kiểm tra sơ bộ khi tải lên tệp WAV (đuôi .wav, dung lượng tối đa).
 * - Luồng nhận dạng ASR -> điền transcript -> không tự động gọi dịch.
 * - Chỉnh sửa transcript -> làm mất hiệu lực kết quả dịch cũ.
 * - Dịch transcript (direction=vi-tay) -> hiển thị bản dịch tiếng Tày và nút sao chép.
 * - Chống stale response bằng revision token khi người dùng thay đổi đầu vào.
 * - Vòng đời deactivate() và destroy() an toàn.
 */

import test, { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { initVoice } from '../../web_app/ui/js/voice.js';
import { normalizeText, codePointLength } from '../../web_app/ui/js/text_utils.js';
import { timeoutFor } from '../../web_app/ui/js/api_client.js';

// Setup Mock Window & URL cho môi trường Node.js
if (typeof globalThis.window === 'undefined') {
  globalThis.window = globalThis;
}
globalThis.window.location = { hostname: 'localhost' };
globalThis.window.isSecureContext = true;
globalThis.window.addEventListener = () => {};
globalThis.window.removeEventListener = () => {};
globalThis.URL = globalThis.URL || {};
globalThis.URL.createObjectURL = (blob) => `blob:mock-audio-${Math.random().toString(36).slice(2)}`;
globalThis.URL.revokeObjectURL = () => {};

if (!globalThis.window.AudioContext) {
  globalThis.window.AudioContext = class {
    constructor() {
      this.sampleRate = 16000;
      this.state = 'running';
    }
    createMediaStreamSource() {
      return { connect: () => {} };
    }
    createScriptProcessor() {
      return { connect: () => {}, onaudioprocess: null };
    }
    createGain() {
      return { gain: { value: 1 }, connect: () => {} };
    }
    close() {
      this.state = 'closed';
    }
    get destination() {
      return {};
    }
  };
}

try {
  if (!globalThis.navigator?.mediaDevices) {
    Object.defineProperty(globalThis, 'navigator', {
      value: {
        mediaDevices: {
          getUserMedia: async () => ({
            getTracks: () => [{ stop: () => {} }],
            getAudioTracks: () => [{ stop: () => {}, onended: null }],
          }),
        },
      },
      configurable: true,
      writable: true,
    });
  }
} catch (e) {}

/**
 * Mock DOM Element đơn giản phục vụ test DOM selectors và sự kiện.
 */
class MockElement {
  constructor(id = '', tag = 'div') {
    this.id = id;
    this.tagName = tag.toUpperCase();
    this._value = '';
    this._textContent = '';
    this._innerHTML = '';
    this.disabled = false;
    this.style = {};
    this.title = '';
    this.files = [];

    this.classList = {
      _classes: new Set(),
      add: (c) => this.classList._classes.add(c),
      remove: (c) => this.classList._classes.delete(c),
      contains: (c) => this.classList._classes.has(c),
    };

    this.attributes = new Map();
    this.listeners = new Map();
  }

  get value() {
    return this._value;
  }

  set value(val) {
    this._value = String(val);
  }

  get textContent() {
    return this._textContent;
  }

  set textContent(val) {
    this._textContent = String(val);
  }

  get innerHTML() {
    return this._innerHTML;
  }

  set innerHTML(val) {
    this._innerHTML = String(val);
  }

  addEventListener(event, fn) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event).push(fn);
  }

  removeEventListener(event, fn) {
    const list = this.listeners.get(event) || [];
    this.listeners.set(event, list.filter((f) => f !== fn));
  }

  async dispatchEvent(event) {
    const list = this.listeners.get(event.type) || [];
    for (const fn of list) {
      await fn(event);
    }
  }

  async click() {
    await this.dispatchEvent({ type: 'click' });
  }

  focus() {}

  setAttribute(k, v) {
    this.attributes.set(k, String(v));
  }

  getAttribute(k) {
    return this.attributes.get(k) || null;
  }

  removeAttribute(k) {
    this.attributes.delete(k);
  }

  pause() {}
  load() {}
}

/**
 * Mock Root Element hỗ trợ bắt ID selectors từ innerHTML.
 */
class MockRootElement extends MockElement {
  constructor() {
    super('root', 'div');
    this.elementsById = new Map();
  }

  set innerHTML(html) {
    this._innerHTML = html;
    this.elementsById.clear();

    if (!html) return;

    // Tìm tất cả id="..." trong chuỗi HTML
    const idRegex = /id="([a-zA-Z0-9_-]+)"/g;
    let match;
    while ((match = idRegex.exec(html)) !== null) {
      const id = match[1];
      if (!this.elementsById.has(id)) {
        this.elementsById.set(id, new MockElement(id));
      }
    }
  }

  get innerHTML() {
    return this._innerHTML;
  }

  querySelector(selector) {
    if (selector.startsWith('#')) {
      const id = selector.slice(1);
      return this.elementsById.get(id) || null;
    }
    return null;
  }
}

/**
 * Helper tạo fixture health
 */
function createMockHealth(overrides = {}) {
  return {
    status: 'ready',
    api_version: '1',
    translation: {
      state: 'ready',
      engine_type: 'mock',
      is_mock: true,
      active_model_id: 'mock-demo',
      supported_directions: ['vi-tay', 'tay-vi'],
      ...(overrides.translation || {})
    },
    asr: {
      state: 'ready',
      engine_type: 'mock',
      is_mock: true,
      model_id: 'mock-asr',
      supported_languages: ['vi'],
      ...(overrides.asr || {})
    },
    limits: {
      max_text_length: 1000,
      max_audio_file_bytes: 10485760,
      max_audio_duration_sec: 30,
      queue_timeout_sec: 5,
      translation_timeout_sec: 15,
      asr_timeout_sec: 20,
      audio_format: 'wav_pcm_s16le',
      audio_sample_rate_hz: 16000,
      audio_channels: 1,
      ...(overrides.limits || {})
    }
  };
}

function createFakeWavFile(name = 'test.wav', size = 16000) {
  const blob = new Blob([new Uint8Array(size)], { type: 'audio/wav' });
  blob.name = name;
  return blob;
}

describe('voice.js - Khởi tạo và hợp đồng giao tiếp initVoice', () => {
  let root;

  beforeEach(() => {
    root = new MockRootElement();
  });

  it('render đầy đủ cấu trúc khung và trả về các phương thức điều khiển bắt buộc', () => {
    const voice = initVoice(root, {
      apiRequest: async () => ({}),
      timeoutFor,
      normalizeText,
      codePointLength
    });

    assert.ok(typeof voice.setHealth === 'function');
    assert.ok(typeof voice.deactivate === 'function');
    assert.ok(typeof voice.destroy === 'function');

    // Chứa cảnh báo §6.3 trong innerHTML
    assert.ok(root.innerHTML.toLowerCase().includes('chưa hỗ trợ nhận dạng tiếng tày'));
    assert.ok(root.innerHTML.includes('WAV PCM 16.000 Hz, Mono, 16-bit'));

    // Các phần tử ID bắt buộc phải tồn tại
    assert.ok(root.querySelector('#vp-transcript-input'));
    assert.ok(root.querySelector('#vp-btn-translate'));
    assert.ok(root.querySelector('#vp-btn-transcribe'));
    assert.ok(root.querySelector('#vp-translation-result'));
  });

  it('nút Dịch sang tiếng Tày bị vô hiệu khi khởi tạo (chưa có transcript)', () => {
    initVoice(root, {
      apiRequest: async () => ({}),
      timeoutFor,
      normalizeText,
      codePointLength
    });

    const translateBtn = root.querySelector('#vp-btn-translate');
    assert.equal(translateBtn.disabled, true);
  });
});

describe('voice.js - Cập nhật setHealth() và nhãn Mock độc lập', () => {
  let root;

  beforeEach(() => {
    root = new MockRootElement();
  });

  it('hiển thị nhãn mock độc lập cho ASR và Dịch khi cả hai đều là mock', () => {
    const voice = initVoice(root, {
      apiRequest: async () => ({}),
      timeoutFor,
      normalizeText,
      codePointLength
    });

    const health = createMockHealth({
      asr: { is_mock: true, state: 'ready' },
      translation: { is_mock: true, state: 'ready' }
    });

    voice.setHealth(health);

    const asrBadge = root.querySelector('#vp-badge-asr');
    const transBadge = root.querySelector('#vp-badge-trans');

    assert.ok(asrBadge.classList.contains('vp-badge-mock'));
    assert.ok(asrBadge.textContent.includes('ASR: Mô phỏng'));

    assert.ok(transBadge.classList.contains('vp-badge-mock'));
    assert.ok(transBadge.textContent.includes('Dịch: Mô phỏng'));
  });

  it('hiển thị độc lập: ASR mock nhưng Dịch thật (hoặc ngược lại)', () => {
    const voice = initVoice(root, {
      apiRequest: async () => ({}),
      timeoutFor,
      normalizeText,
      codePointLength
    });

    // Trường hợp: ASR thật (is_mock=false), Dịch mock (is_mock=true)
    const health = createMockHealth({
      asr: { is_mock: false, state: 'ready' },
      translation: { is_mock: true, state: 'ready' }
    });

    voice.setHealth(health);

    const asrBadge = root.querySelector('#vp-badge-asr');
    const transBadge = root.querySelector('#vp-badge-trans');

    assert.ok(asrBadge.classList.contains('vp-badge-ready'));
    assert.ok(!asrBadge.classList.contains('vp-badge-mock'));

    assert.ok(transBadge.classList.contains('vp-badge-mock'));
  });

  it('vô hiệu hóa các nút tương ứng khi engine chưa ready (loading hoặc disabled)', () => {
    const voice = initVoice(root, {
      apiRequest: async () => ({}),
      timeoutFor,
      normalizeText,
      codePointLength
    });

    const health = createMockHealth({
      asr: { state: 'loading' },
      translation: { state: 'failed' }
    });

    voice.setHealth(health);

    const transcribeBtn = root.querySelector('#vp-btn-transcribe');
    const translateBtn = root.querySelector('#vp-btn-translate');

    assert.equal(transcribeBtn.disabled, true);
    assert.equal(translateBtn.disabled, true);
  });
});

describe('voice.js - Kiểm tra sơ bộ tệp WAV tải lên', () => {
  let root;

  beforeEach(() => {
    root = new MockRootElement();
  });

  it('từ chối tệp không có đuôi .wav và hiển thị thông báo lỗi', () => {
    initVoice(root, {
      apiRequest: async () => ({}),
      timeoutFor,
      normalizeText,
      codePointLength
    });

    const fileInput = root.querySelector('#vp-file-input');
    const errorBox = root.querySelector('#vp-asr-error');
    const errorMsg = root.querySelector('#vp-asr-error-msg');

    // Giả lập người dùng chọn file MP3
    fileInput.files = [{ name: 'audio_record.mp3', size: 1024 }];
    fileInput.dispatchEvent({ type: 'change' });

    assert.equal(errorBox.style.display, 'flex');
    assert.ok(errorMsg.textContent.includes('Chỉ chấp nhận tệp có định dạng .wav'));
  });

  it('từ chối tệp WAV vượt quá giới hạn dung lượng max_audio_file_bytes', () => {
    const voice = initVoice(root, {
      apiRequest: async () => ({}),
      timeoutFor,
      normalizeText,
      codePointLength
    });

    // Giới hạn 10 MB
    voice.setHealth(createMockHealth({ limits: { max_audio_file_bytes: 10 * 1024 * 1024 } }));

    const fileInput = root.querySelector('#vp-file-input');
    const errorBox = root.querySelector('#vp-asr-error');
    const errorMsg = root.querySelector('#vp-asr-error-msg');

    // Tệp 15 MB
    fileInput.files = [{ name: 'big_audio.wav', size: 15 * 1024 * 1024 }];
    fileInput.dispatchEvent({ type: 'change' });

    assert.equal(errorBox.style.display, 'flex');
    assert.ok(errorMsg.textContent.includes('vượt quá giới hạn cho phép'));
  });

  it('chấp nhận tệp WAV hợp lệ và hiển thị thông tin tệp', async () => {
    const voice = initVoice(root, {
      apiRequest: async () => ({}),
      timeoutFor,
      normalizeText,
      codePointLength
    });

    voice.setHealth(createMockHealth());

    const fileInput = root.querySelector('#vp-file-input');
    const fileInfo = root.querySelector('#vp-file-info');
    const fileNameDisplay = root.querySelector('#vp-file-name-display');
    const preview = root.querySelector('#vp-audio-preview');

    fileInput.files = [createFakeWavFile('valid_voice.wav', 32000)];
    await fileInput.dispatchEvent({ type: 'change' });

    assert.equal(fileInfo.style.display, 'flex');
    assert.ok(fileNameDisplay.textContent.includes('valid_voice.wav'));
    assert.equal(preview.style.display, 'flex');
  });
});

describe('voice.js - Luồng ASR -> Transcript chỉnh sửa -> Dịch tiếng Tày', () => {
  let root;

  beforeEach(() => {
    root = new MockRootElement();
  });

  it('nhận dạng ASR thành công, hiển thị transcript và không tự động gọi dịch', async () => {
    let asrCalled = false;
    let translateCalled = false;

    const mockApiRequest = async (path, options) => {
      if (path === '/api/asr/transcribe') {
        asrCalled = true;
        // Kiểm tra đúng multipart form data
        assert.ok(options.formData);
        return {
          status: 'success',
          transcript: 'Hôm nay trời rất đẹp tại bản làng.',
          language: 'vi',
          duration_sec: 2.5,
          latency_ms: 120,
          queue_ms: 5,
          model_metadata: {
            model_id: 'mock-asr',
            model_version: 'v1',
            engine_type: 'mock',
            is_mock: true
          }
        };
      }
      if (path === '/api/translate') {
        translateCalled = true;
        return {};
      }
      return {};
    };

    const voice = initVoice(root, {
      apiRequest: mockApiRequest,
      timeoutFor,
      normalizeText,
      codePointLength
    });

    voice.setHealth(createMockHealth());

    // Nạp tệp WAV hợp lệ
    const fileInput = root.querySelector('#vp-file-input');
    fileInput.files = [createFakeWavFile('test.wav', 16000)];
    await fileInput.dispatchEvent({ type: 'change' });

    // Bấm nhận dạng ASR
    const transcribeBtn = root.querySelector('#vp-btn-transcribe');
    await transcribeBtn.click();

    assert.equal(asrCalled, true);
    // Quan trọng: ASR không được tự kích hoạt bước dịch!
    assert.equal(translateCalled, false);

    // Transcript được điền vào ô
    const transcriptInput = root.querySelector('#vp-transcript-input');
    assert.equal(transcriptInput.value, 'Hôm nay trời rất đẹp tại bản làng.');

    // Mock notice hiển thị do model_metadata.is_mock=true
    const mockNotice = root.querySelector('#vp-asr-mock-notice');
    assert.equal(mockNotice.style.display, 'block');

    // Nút dịch sang tiếng Tày được bật
    const translateBtn = root.querySelector('#vp-btn-translate');
    assert.equal(translateBtn.disabled, false);
  });

  it('sửa transcript làm mất hiệu lực kết quả dịch cũ', async () => {
    const voice = initVoice(root, {
      apiRequest: async (path) => {
        if (path === '/api/asr/transcribe') {
          return {
            status: 'success',
            transcript: 'Câu nguồn ban đầu',
            language: 'vi',
            duration_sec: 1.5,
            latency_ms: 60,
            model_metadata: { model_id: 'mock-asr', is_mock: true }
          };
        }
        if (path === '/api/translate') {
          return {
            status: 'success',
            translation: 'Bản dịch tiếng Tày mẫu',
            direction: 'vi-tay',
            source_lang: 'vi',
            target_lang: 'tyz',
            latency_ms: 50,
            queue_ms: 2,
            model_metadata: { model_id: 'mock-demo', is_mock: true }
          };
        }
        return {};
      },
      timeoutFor,
      normalizeText,
      codePointLength
    });

    voice.setHealth(createMockHealth());

    // Nạp tệp WAV và chạy ASR thành công
    const fileInput = root.querySelector('#vp-file-input');
    fileInput.files = [createFakeWavFile('test.wav', 16000)];
    await fileInput.dispatchEvent({ type: 'change' });

    const transcribeBtn = root.querySelector('#vp-btn-transcribe');
    await transcribeBtn.click();

    // Bấm dịch
    const translateBtn = root.querySelector('#vp-btn-translate');
    assert.equal(translateBtn.disabled, false);
    await translateBtn.click();

    const resultBox = root.querySelector('#vp-translation-result');
    assert.equal(resultBox.textContent, 'Bản dịch tiếng Tày mẫu');

    // Người dùng gõ sửa transcript
    const transcriptInput = root.querySelector('#vp-transcript-input');
    transcriptInput.value = 'Câu nguồn đã được chỉnh sửa';
    transcriptInput.dispatchEvent({ type: 'input' });

    // Kết quả dịch cũ phải bị xóa ngay lập tức
    assert.ok(resultBox.innerHTML.includes('Bản dịch tiếng Tày sẽ hiển thị'));
  });

  it('dịch snapshot văn bản đã chỉnh sửa và hỗ trợ sao chép', async () => {
    let capturedText = null;

    const mockApiRequest = async (path, options) => {
      if (path === '/api/asr/transcribe') {
        return {
          status: 'success',
          transcript: 'Ban đầu từ audio',
          language: 'vi',
          duration_sec: 2.0,
          latency_ms: 50,
          model_metadata: { model_id: 'mock-asr', is_mock: true }
        };
      }
      if (path === '/api/translate') {
        capturedText = options.json?.text;
        return {
          status: 'success',
          translation: 'Văn bản đã dịch sang tiếng Tày',
          direction: 'vi-tay',
          source_lang: 'vi',
          target_lang: 'tyz',
          latency_ms: 45,
          queue_ms: 1,
          model_metadata: { model_id: 'mock-demo', is_mock: true }
        };
      }
      return {};
    };

    const voice = initVoice(root, {
      apiRequest: mockApiRequest,
      timeoutFor,
      normalizeText,
      codePointLength
    });

    voice.setHealth(createMockHealth());

    // Nạp audio và chạy ASR
    const fileInput = root.querySelector('#vp-file-input');
    fileInput.files = [createFakeWavFile('audio.wav', 16000)];
    await fileInput.dispatchEvent({ type: 'change' });

    const transcribeBtn = root.querySelector('#vp-btn-transcribe');
    await transcribeBtn.click();

    const transcriptInput = root.querySelector('#vp-transcript-input');
    transcriptInput.value = '   Đoạn văn bản tiếng Việt sau chuẩn hóa   ';
    transcriptInput.dispatchEvent({ type: 'input' });

    const translateBtn = root.querySelector('#vp-btn-translate');
    await translateBtn.click();

    // Văn bản gửi đi là snapshot đã chuẩn hóa (cắt khoảng trắng 2 đầu)
    assert.equal(capturedText, 'Đoạn văn bản tiếng Việt sau chuẩn hóa');

    const resultBox = root.querySelector('#vp-translation-result');
    assert.equal(resultBox.textContent, 'Văn bản đã dịch sang tiếng Tày');

    // Nút copy hiển thị
    const copyBtn = root.querySelector('#vp-btn-copy');
    assert.equal(copyBtn.style.display, 'inline-flex');
  });

  it('không cắt tự động khi transcript vượt quá giới hạn max_text_length, hiển thị cảnh báo', () => {
    const voice = initVoice(root, {
      apiRequest: async () => ({}),
      timeoutFor,
      normalizeText,
      codePointLength
    });

    voice.setHealth(createMockHealth({ limits: { max_text_length: 50 } }));

    const transcriptInput = root.querySelector('#vp-transcript-input');
    // Chuỗi 60 ký tự (> 50)
    transcriptInput.value = 'Một chuỗi văn bản rất dài cố tình vượt quá giới hạn năm mươi ký tự';
    transcriptInput.dispatchEvent({ type: 'input' });

    const warningEl = root.querySelector('#vp-char-warning');
    const translateBtn = root.querySelector('#vp-btn-translate');

    assert.equal(warningEl.style.display, 'inline');
    assert.ok(warningEl.textContent.includes('Vui lòng rút gọn'));
    assert.equal(translateBtn.disabled, true);
  });
});

describe('voice.js - Chống Stale Response bằng Revision Token', () => {
  let root;

  beforeEach(() => {
    root = new MockRootElement();
  });

  it('từ chối kết quả ASR đến muộn nếu người dùng đã đổi tệp âm thanh', async () => {
    let resolveAsr = null;
    const slowAsrPromise = new Promise((resolve) => {
      resolveAsr = resolve;
    });

    const mockApiRequest = async (path) => {
      if (path === '/api/asr/transcribe') {
        return slowAsrPromise;
      }
      return {};
    };

    const voice = initVoice(root, {
      apiRequest: mockApiRequest,
      timeoutFor,
      normalizeText,
      codePointLength
    });

    voice.setHealth(createMockHealth());

    // Nạp tệp A
    const fileInput = root.querySelector('#vp-file-input');
    fileInput.files = [createFakeWavFile('audio_a.wav', 1000)];
    await fileInput.dispatchEvent({ type: 'change' });

    // Bắt đầu nhận dạng A
    const transcribeBtn = root.querySelector('#vp-btn-transcribe');
    const transcribePromise = transcribeBtn.click();

    // Người dùng nhanh chóng chọn tệp B (thay đổi file)
    fileInput.files = [createFakeWavFile('audio_b.wav', 2000)];
    await fileInput.dispatchEvent({ type: 'change' });

    // Request cũ của A mới trả về
    resolveAsr({
      status: 'success',
      transcript: 'Nội dung cũ của file A',
      model_metadata: { is_mock: true }
    });

    await transcribePromise;

    // Transcript không được phép nhận nội dung cũ của A
    const transcriptInput = root.querySelector('#vp-transcript-input');
    assert.equal(transcriptInput.value, '');
  });

  it('từ chối kết quả Dịch đến muộn nếu người dùng đã sửa transcript', async () => {
    let resolveTranslate = null;
    const slowTranslatePromise = new Promise((resolve) => {
      resolveTranslate = resolve;
    });

    const mockApiRequest = async (path) => {
      if (path === '/api/asr/transcribe') {
        return {
          status: 'success',
          transcript: 'Nội dung gốc',
          model_metadata: { is_mock: true }
        };
      }
      if (path === '/api/translate') {
        return slowTranslatePromise;
      }
      return {};
    };

    const voice = initVoice(root, {
      apiRequest: mockApiRequest,
      timeoutFor,
      normalizeText,
      codePointLength
    });

    voice.setHealth(createMockHealth());

    // Nạp tệp và chạy ASR thành công để kích hoạt trạng thái dịch
    const fileInput = root.querySelector('#vp-file-input');
    fileInput.files = [createFakeWavFile('audio.wav', 16000)];
    await fileInput.dispatchEvent({ type: 'change' });

    const transcribeBtn = root.querySelector('#vp-btn-transcribe');
    await transcribeBtn.click();

    // Bấm dịch
    const translateBtn = root.querySelector('#vp-btn-translate');
    assert.equal(translateBtn.disabled, false);
    const translatePromise = translateBtn.click();

    // Người dùng sửa transcript trong khi đang chờ dịch
    const transcriptInput = root.querySelector('#vp-transcript-input');
    transcriptInput.value = 'Nội dung đã sửa khác hẳn';
    transcriptInput.dispatchEvent({ type: 'input' });

    // Request dịch cũ mới trả về
    resolveTranslate({
      status: 'success',
      translation: 'Bản dịch cho nội dung gốc',
      model_metadata: { is_mock: true }
    });

    await translatePromise;

    // Kết quả dịch cũ phải bị từ chối
    const resultBox = root.querySelector('#vp-translation-result');
    assert.ok(!resultBox.textContent.includes('Bản dịch cho nội dung gốc'));
  });
});

describe('voice.js - Hồi quy C20, C21 & C22 (Review Codex 04/11/2026)', () => {
  let root;

  beforeEach(() => {
    root = new MockRootElement();
  });

  it('C20: thay file B khi ASR file A đang chờ không làm kẹt nút và cho phép phiên mới hoạt động', async () => {
    let resolveAsrA = null;
    const promiseA = new Promise((resolve) => {
      resolveAsrA = resolve;
    });

    let asrCallCount = 0;
    const mockApiRequest = async (path, opts) => {
      if (path === '/api/asr/transcribe') {
        asrCallCount++;
        if (asrCallCount === 1) return promiseA;
        return {
          status: 'success',
          transcript: 'Transcript của file B',
          model_metadata: { is_mock: true }
        };
      }
      return {};
    };

    const voice = initVoice(root, {
      apiRequest: mockApiRequest,
      timeoutFor,
      normalizeText,
      codePointLength
    });
    voice.setHealth(createMockHealth());

    const fileInput = root.querySelector('#vp-file-input');
    const transcribeBtn = root.querySelector('#vp-btn-transcribe');
    const transcriptInput = root.querySelector('#vp-transcript-input');

    // 1. Nạp file A và bấm transcribe (đang pending)
    fileInput.files = [createFakeWavFile('file_a.wav', 16000)];
    await fileInput.dispatchEvent({ type: 'change' });
    const transcribeAPromise = transcribeBtn.click();

    assert.equal(transcribeBtn.disabled, true);
    assert.ok(transcribeBtn.innerHTML.includes('Đang nhận dạng'));

    // 2. Người dùng chọn file B trong khi A đang chờ
    fileInput.files = [createFakeWavFile('file_b.wav', 16000)];
    await fileInput.dispatchEvent({ type: 'change' });

    // C20 Check: Trạng thái UI phải được giải phóng ngay lập tức, không kẹt disabled
    assert.equal(transcribeBtn.disabled, false);
    assert.ok(transcribeBtn.innerHTML.includes('Nhận dạng giọng nói'));

    // 3. Thả response của file A
    resolveAsrA({
      status: 'success',
      transcript: 'Transcript của file A (đã cũ)',
      model_metadata: { is_mock: true }
    });
    await transcribeAPromise;

    // Transcript KHÔNG bị kết quả file A ghi đè
    assert.equal(transcriptInput.value, '');

    // 4. Bấm transcribe cho file B: hoạt động bình thường
    await transcribeBtn.click();
    assert.equal(asrCallCount, 2);
    assert.equal(transcriptInput.value, 'Transcript của file B');
  });

  it('C20: sửa transcript trong lúc dịch đang chờ không làm kẹt nút và cho phép gửi dịch nội dung mới', async () => {
    let resolveTranslate1 = null;
    const promise1 = new Promise((resolve) => {
      resolveTranslate1 = resolve;
    });

    let translateCalls = [];
    const mockApiRequest = async (path, opts) => {
      if (path === '/api/asr/transcribe') {
        return {
          status: 'success',
          transcript: 'Văn bản gốc từ ASR',
          model_metadata: { is_mock: true }
        };
      }
      if (path === '/api/translate') {
        translateCalls.push(opts.json?.text);
        if (translateCalls.length === 1) return promise1;
        return {
          status: 'success',
          translation: 'Bản dịch mới cho văn bản đã sửa',
          direction: 'vi-tay',
          model_metadata: { is_mock: true }
        };
      }
      return {};
    };

    const voice = initVoice(root, {
      apiRequest: mockApiRequest,
      timeoutFor,
      normalizeText,
      codePointLength
    });
    voice.setHealth(createMockHealth());

    // Nạp audio và ASR
    const fileInput = root.querySelector('#vp-file-input');
    fileInput.files = [createFakeWavFile('voice.wav', 16000)];
    await fileInput.dispatchEvent({ type: 'change' });
    await root.querySelector('#vp-btn-transcribe').click();

    const translateBtn = root.querySelector('#vp-btn-translate');
    const transcriptInput = root.querySelector('#vp-transcript-input');
    const resultBox = root.querySelector('#vp-translation-result');

    // 1. Bấm Dịch lần 1 (đang pending)
    const translate1Promise = translateBtn.click();
    assert.equal(translateBtn.disabled, true);
    assert.ok(translateBtn.innerHTML.includes('Đang dịch sang tiếng Tày'));

    // 2. Người dùng sửa transcript trong khi request 1 đang bay
    transcriptInput.value = 'Văn bản đã sửa nội dung';
    transcriptInput.dispatchEvent({ type: 'input' });

    // C20 Check: Nút Dịch phải được giải phóng ngay, không kẹt spinner
    assert.equal(translateBtn.disabled, false);
    assert.ok(translateBtn.innerHTML.includes('Dịch sang tiếng Tày'));

    // 3. Thả phản hồi request 1
    resolveTranslate1({
      status: 'success',
      translation: 'Bản dịch cũ của request 1',
      model_metadata: { is_mock: true }
    });
    await translate1Promise;

    // Kết quả cũ của request 1 không được hiển thị vào resultBox
    assert.ok(!resultBox.textContent.includes('Bản dịch cũ của request 1'));

    // 4. Bấm Dịch lần 2 cho nội dung mới: gửi thành công
    await translateBtn.click();
    assert.equal(translateCalls.length, 2);
    assert.equal(translateCalls[1], 'Văn bản đã sửa nội dung');
    assert.equal(resultBox.textContent, 'Bản dịch mới cho văn bản đã sửa');
  });

  it('C20: sửa transcript trong lúc ASR đang chờ sẽ hủy ASR và không bị kết quả ASR cũ đè lên', async () => {
    let resolveAsr = null;
    const slowAsrPromise = new Promise((resolve) => {
      resolveAsr = resolve;
    });

    const mockApiRequest = async (path) => {
      if (path === '/api/asr/transcribe') {
        return slowAsrPromise;
      }
      return {};
    };

    const voice = initVoice(root, {
      apiRequest: mockApiRequest,
      timeoutFor,
      normalizeText,
      codePointLength
    });
    voice.setHealth(createMockHealth());

    const fileInput = root.querySelector('#vp-file-input');
    fileInput.files = [createFakeWavFile('voice.wav', 16000)];
    await fileInput.dispatchEvent({ type: 'change' });

    const transcribeBtn = root.querySelector('#vp-btn-transcribe');
    const transcribePromise = transcribeBtn.click();

    const transcriptInput = root.querySelector('#vp-transcript-input');
    // Người dùng gõ tay vào transcript trong khi ASR đang chờ
    transcriptInput.value = 'Nội dung người dùng tự tay nhập';
    transcriptInput.dispatchEvent({ type: 'input' });

    // ASR cũ trả về
    resolveAsr({
      status: 'success',
      transcript: 'Kết quả ASR đến muộn',
      model_metadata: { is_mock: true }
    });
    await transcribePromise;

    // Transcript phải giữ nguyên nội dung người dùng đã nhập, không bị ghi đè!
    assert.equal(transcriptInput.value, 'Nội dung người dùng tự tay nhập');
    // Transcribe button được giải phóng
    assert.equal(transcribeBtn.disabled, false);
  });

  it('C20: deactivate() khi rời tab giải phóng toàn bộ trạng thái chờ', () => {
    const voice = initVoice(root, {
      apiRequest: async () => new Promise(() => {}), // Treo vô hạn
      timeoutFor,
      normalizeText,
      codePointLength
    });
    voice.setHealth(createMockHealth());

    voice.deactivate();

    const transcribeBtn = root.querySelector('#vp-btn-transcribe');
    const translateBtn = root.querySelector('#vp-btn-translate');
    assert.ok(!transcribeBtn.innerHTML.includes('vp-spinner'));
    assert.ok(!translateBtn.innerHTML.includes('vp-spinner'));
  });

  it('C21: nhập transcript thủ công khi chưa có ASR thành công thì nút Dịch bị vô hiệu', () => {
    const voice = initVoice(root, {
      apiRequest: async () => ({}),
      timeoutFor,
      normalizeText,
      codePointLength
    });
    voice.setHealth(createMockHealth());

    const transcriptInput = root.querySelector('#vp-transcript-input');
    const translateBtn = root.querySelector('#vp-btn-translate');

    // Chưa chạy ASR, cố tình gõ văn bản
    transcriptInput.value = 'Văn bản gõ thủ công không qua ASR';
    transcriptInput.dispatchEvent({ type: 'input' });

    // C21 Invariant: Nút Dịch bắt buộc phải vô hiệu!
    assert.equal(translateBtn.disabled, true);
    assert.ok(translateBtn.title.includes('Yêu cầu nhận dạng'));
  });

  it('C21: ASR gặp lỗi (hoặc no speech) sẽ xóa transcript và metadata cũ, vô hiệu nút Dịch', async () => {
    let returnError = false;
    const mockApiRequest = async (path) => {
      if (path === '/api/asr/transcribe') {
        if (returnError) {
          const err = new Error('Không phát hiện giọng nói.');
          err.code = 'NO_SPEECH_DETECTED';
          throw err;
        }
        return {
          status: 'success',
          transcript: 'Transcript thành công ban đầu',
          duration_sec: 1.5,
          latency_ms: 50,
          model_metadata: { is_mock: true }
        };
      }
      return {};
    };

    const voice = initVoice(root, {
      apiRequest: mockApiRequest,
      timeoutFor,
      normalizeText,
      codePointLength
    });
    voice.setHealth(createMockHealth());

    const fileInput = root.querySelector('#vp-file-input');
    const transcribeBtn = root.querySelector('#vp-btn-transcribe');
    const transcriptInput = root.querySelector('#vp-transcript-input');
    const translateBtn = root.querySelector('#vp-btn-translate');

    // 1. ASR thành công lần đầu
    fileInput.files = [createFakeWavFile('voice.wav', 16000)];
    await fileInput.dispatchEvent({ type: 'change' });
    await transcribeBtn.click();

    assert.equal(transcriptInput.value, 'Transcript thành công ban đầu');
    assert.equal(translateBtn.disabled, false);

    // 2. Lần ASR thứ 2 gặp lỗi NO_SPEECH_DETECTED
    returnError = true;
    await transcribeBtn.click();

    // C21 Invariant: transcript cũ bị xóa, metadata cũ bị xóa, nút dịch bị vô hiệu!
    assert.equal(transcriptInput.value, '', 'Transcript cũ phải bị xóa khi ASR lỗi');
    assert.equal(translateBtn.disabled, true, 'Nút dịch phải bị vô hiệu khi ASR lỗi');
    const asrMeta = root.querySelector('#vp-asr-meta-info');
    assert.equal(asrMeta.textContent, '');
  });

  it('C21: thay đổi hoặc xóa audio file sẽ xóa transcript cũ và vô hiệu nút Dịch', async () => {
    const mockApiRequest = async (path) => {
      if (path === '/api/asr/transcribe') {
        return {
          status: 'success',
          transcript: 'Transcript hợp lệ',
          model_metadata: { is_mock: true }
        };
      }
      return {};
    };

    const voice = initVoice(root, {
      apiRequest: mockApiRequest,
      timeoutFor,
      normalizeText,
      codePointLength
    });
    voice.setHealth(createMockHealth());

    const fileInput = root.querySelector('#vp-file-input');
    const transcribeBtn = root.querySelector('#vp-btn-transcribe');
    const transcriptInput = root.querySelector('#vp-transcript-input');
    const translateBtn = root.querySelector('#vp-btn-translate');
    const removeFileBtn = root.querySelector('#vp-btn-remove-file');

    // ASR thành công
    fileInput.files = [createFakeWavFile('voice.wav', 16000)];
    await fileInput.dispatchEvent({ type: 'change' });
    await transcribeBtn.click();
    assert.equal(translateBtn.disabled, false);

    // Người dùng xóa tệp âm thanh
    await removeFileBtn.click();

    // C21 Invariant: Transcript và Dịch bị vô hiệu hoàn toàn
    assert.equal(transcriptInput.value, '');
    assert.equal(translateBtn.disabled, true);
  });

  it('C21: sau khi ASR thành công, người dùng sửa transcript thì nút Dịch vẫn bật và dịch đúng snapshot đã sửa', async () => {
    let capturedTranslatedText = null;
    const mockApiRequest = async (path, opts) => {
      if (path === '/api/asr/transcribe') {
        return {
          status: 'success',
          transcript: 'Hôm nay trời nắng',
          model_metadata: { is_mock: true }
        };
      }
      if (path === '/api/translate') {
        capturedTranslatedText = opts.json?.text;
        return {
          status: 'success',
          translation: 'Bản dịch cho trời mưa',
          direction: 'vi-tay',
          model_metadata: { is_mock: true }
        };
      }
      return {};
    };

    const voice = initVoice(root, {
      apiRequest: mockApiRequest,
      timeoutFor,
      normalizeText,
      codePointLength
    });
    voice.setHealth(createMockHealth());

    const fileInput = root.querySelector('#vp-file-input');
    fileInput.files = [createFakeWavFile('voice.wav', 16000)];
    await fileInput.dispatchEvent({ type: 'change' });
    await root.querySelector('#vp-btn-transcribe').click();

    const transcriptInput = root.querySelector('#vp-transcript-input');
    const translateBtn = root.querySelector('#vp-btn-translate');

    // Sửa transcript
    transcriptInput.value = 'Hôm nay trời mưa to';
    transcriptInput.dispatchEvent({ type: 'input' });

    // Nút dịch vẫn bật
    assert.equal(translateBtn.disabled, false);

    await translateBtn.click();
    assert.equal(capturedTranslatedText, 'Hôm nay trời mưa to');
  });

  it('C22: chuyển subtab sang Upload khi đang thu âm sẽ tự động cancel micro', () => {
    const voice = initVoice(root, {
      apiRequest: async () => ({}),
      timeoutFor,
      normalizeText,
      codePointLength
    });

    const startRecordBtn = root.querySelector('#vp-btn-start-record');
    const tabUploadBtn = root.querySelector('#vp-tab-upload-btn');

    // Bắt đầu thu âm
    startRecordBtn.dispatchEvent({ type: 'click' });

    // Bấm chuyển sang tab upload
    tabUploadBtn.dispatchEvent({ type: 'click' });

    // Giao diện thu âm phải trở lại trạng thái sẵn sàng (đã cancel)
    const statusText = root.querySelector('#vp-record-status-text');
    assert.equal(statusText.textContent, 'Sẵn sàng thu âm');
  });

  it('C22: chọn tệp WAV khi đang thu âm sẽ dừng micro an toàn', () => {
    initVoice(root, {
      apiRequest: async () => ({}),
      timeoutFor,
      normalizeText,
      codePointLength
    });

    const startRecordBtn = root.querySelector('#vp-btn-start-record');
    const fileInput = root.querySelector('#vp-file-input');

    // Bắt đầu thu âm
    startRecordBtn.dispatchEvent({ type: 'click' });

    // Chọn file WAV
    fileInput.files = [createFakeWavFile('upload.wav', 16000)];
    fileInput.dispatchEvent({ type: 'change' });

    const statusText = root.querySelector('#vp-record-status-text');
    assert.equal(statusText.textContent, 'Sẵn sàng thu âm');
  });

  it('C20 Cross-stage: ASR A -> Translate A đang chờ -> ASR B trả trước -> Translate A trả muộn bị loại bỏ', async () => {
    let resolveTranslateA = null;
    const promiseTranslateA = new Promise((resolve) => {
      resolveTranslateA = resolve;
    });

    let asrCount = 0;
    const mockApiRequest = async (path, opts) => {
      if (path === '/api/asr/transcribe') {
        asrCount++;
        return {
          status: 'success',
          transcript: asrCount === 1 ? 'Transcript A' : 'Transcript B',
          model_metadata: { is_mock: true }
        };
      }
      if (path === '/api/translate') {
        return promiseTranslateA;
      }
      return {};
    };

    const voice = initVoice(root, {
      apiRequest: mockApiRequest,
      timeoutFor,
      normalizeText,
      codePointLength
    });
    voice.setHealth(createMockHealth());

    const fileInput = root.querySelector('#vp-file-input');
    const transcribeBtn = root.querySelector('#vp-btn-transcribe');
    const translateBtn = root.querySelector('#vp-btn-translate');
    const transcriptInput = root.querySelector('#vp-transcript-input');
    const resultBox = root.querySelector('#vp-translation-result');

    // 1. ASR file A thành công -> hiện Transcript A
    fileInput.files = [createFakeWavFile('file_a.wav', 16000)];
    await fileInput.dispatchEvent({ type: 'change' });
    await transcribeBtn.click();
    assert.equal(transcriptInput.value, 'Transcript A');

    // 2. Bấm Dịch cho Transcript A (đang pending)
    const translateAPromise = translateBtn.click();
    assert.equal(translateBtn.disabled, true);

    // 3. Người dùng chọn file B và bấm ASR cho file B -> trả về Transcript B
    fileInput.files = [createFakeWavFile('file_b.wav', 16000)];
    await fileInput.dispatchEvent({ type: 'change' });
    await transcribeBtn.click();
    assert.equal(transcriptInput.value, 'Transcript B');

    // 4. Request Dịch của Transcript A trả về muộn
    resolveTranslateA({
      status: 'success',
      translation: 'Bản dịch cũ của A',
      direction: 'vi-tay',
      model_metadata: { is_mock: true }
    });
    await translateAPromise;

    // C20 Invariant: ResultBox TUYỆT ĐỐI không được chứa bản dịch của A khi transcript đang là B!
    assert.ok(!resultBox.textContent.includes('Bản dịch cũ của A'), 'Bản dịch cũ của A không được hiển thị cạnh Transcript B');
  });

  it('C20 Cross-stage: ASR A -> Translate A đang chờ -> ASR B gặp lỗi -> Translate A trả muộn vẫn bị từ chối', async () => {
    let resolveTranslateA = null;
    const promiseTranslateA = new Promise((resolve) => {
      resolveTranslateA = resolve;
    });

    let asrCount = 0;
    const mockApiRequest = async (path, opts) => {
      if (path === '/api/asr/transcribe') {
        asrCount++;
        if (asrCount === 1) {
          return {
            status: 'success',
            transcript: 'Transcript A',
            model_metadata: { is_mock: true }
          };
        }
        const err = new Error('Không phát hiện lời nói.');
        err.code = 'NO_SPEECH_DETECTED';
        throw err;
      }
      if (path === '/api/translate') {
        return promiseTranslateA;
      }
      return {};
    };

    const voice = initVoice(root, {
      apiRequest: mockApiRequest,
      timeoutFor,
      normalizeText,
      codePointLength
    });
    voice.setHealth(createMockHealth());

    const fileInput = root.querySelector('#vp-file-input');
    const transcribeBtn = root.querySelector('#vp-btn-transcribe');
    const translateBtn = root.querySelector('#vp-btn-translate');
    const transcriptInput = root.querySelector('#vp-transcript-input');
    const resultBox = root.querySelector('#vp-translation-result');

    // 1. ASR file A thành công
    fileInput.files = [createFakeWavFile('file_a.wav', 16000)];
    await fileInput.dispatchEvent({ type: 'change' });
    await transcribeBtn.click();

    // 2. Bấm Dịch A (đang pending)
    const translateAPromise = translateBtn.click();

    // 3. Người dùng chọn file B và ASR B bị lỗi
    fileInput.files = [createFakeWavFile('file_b.wav', 16000)];
    await fileInput.dispatchEvent({ type: 'change' });
    await transcribeBtn.click();
    assert.equal(transcriptInput.value, '');
    assert.equal(translateBtn.disabled, true);

    // 4. Request Dịch A trả về
    resolveTranslateA({
      status: 'success',
      translation: 'Bản dịch cũ của A',
      direction: 'vi-tay',
      model_metadata: { is_mock: true }
    });
    await translateAPromise;

    // C20 Invariant: ResultBox không nhận bản dịch của A, nút Dịch vẫn bị vô hiệu
    assert.ok(!resultBox.textContent.includes('Bản dịch cũ của A'));
    assert.equal(translateBtn.disabled, true);
  });

  it('C22: start A -> cancel -> start B thành công -> reject permission A không tác động UI phiên B', async () => {
    let rejectPermissionA = null;
    let resolvePermissionB = null;

    const promiseA = new Promise((_, reject) => {
      rejectPermissionA = reject;
    });
    const promiseB = new Promise((resolve) => {
      resolvePermissionB = resolve;
    });

    let callCount = 0;
    const originalGetUserMedia = globalThis.navigator.mediaDevices.getUserMedia;
    globalThis.navigator.mediaDevices.getUserMedia = async () => {
      callCount++;
      if (callCount === 1) return promiseA;
      return promiseB;
    };

    try {
      const voice = initVoice(root, {
        apiRequest: async () => ({}),
        timeoutFor,
        normalizeText,
        codePointLength
      });

      const startRecordBtn = root.querySelector('#vp-btn-start-record');
      const cancelRecordBtn = root.querySelector('#vp-btn-cancel-record');
      const statusText = root.querySelector('#vp-record-status-text');
      const errorBox = root.querySelector('#vp-asr-error');

      // 1. Start phiên A
      startRecordBtn.dispatchEvent({ type: 'click' });
      assert.equal(statusText.textContent, 'Đang chờ cấp quyền micro...');

      // 2. Cancel phiên A
      cancelRecordBtn.dispatchEvent({ type: 'click' });
      assert.equal(statusText.textContent, 'Sẵn sàng thu âm');

      // 3. Start phiên B
      startRecordBtn.dispatchEvent({ type: 'click' });
      assert.equal(statusText.textContent, 'Đang chờ cấp quyền micro...');

      // 4. Quyền phiên B được cấp thành công trước
      const mockStreamB = {
        getTracks: () => [{ stop: () => {} }],
        getAudioTracks: () => [{ stop: () => {}, onended: null }],
      };
      resolvePermissionB(mockStreamB);
      await new Promise((r) => setTimeout(r, 20));

      assert.ok(statusText.textContent.includes('Đang thu âm'));

      // 5. Phiên A cũ bị reject NotAllowedError
      const permErr = new Error('Permission denied');
      permErr.name = 'NotAllowedError';
      rejectPermissionA(permErr);
      await new Promise((r) => setTimeout(r, 20));

      // C22 Invariant: Lỗi của phiên A KHÔNG được hiển thị, phiên B vẫn đang thu âm bình thường!
      assert.ok(statusText.textContent.includes('Đang thu âm'), 'Phiên B phải tiếp tục thu âm bình thường');
      assert.equal(errorBox.style.display, 'none', 'Không được hiển thị lỗi của phiên A cũ');

      // Dọn dẹp phiên B
      cancelRecordBtn.dispatchEvent({ type: 'click' });
    } finally {
      globalThis.navigator.mediaDevices.getUserMedia = originalGetUserMedia;
    }
  });

  it('C22: trạng thái UI sau khi stop/auto-stop phục hồi nút Start và cho phép thu âm lần tiếp theo', async () => {
    const originalGetUserMedia = globalThis.navigator.mediaDevices.getUserMedia;
    globalThis.navigator.mediaDevices.getUserMedia = async () => ({
      getTracks: () => [{ stop: () => {} }],
      getAudioTracks: () => [{ stop: () => {}, onended: null }],
    });

    try {
      const voice = initVoice(root, {
        apiRequest: async () => ({}),
        timeoutFor,
        normalizeText,
        codePointLength
      });

      const startRecordBtn = root.querySelector('#vp-btn-start-record');
      const stopRecordBtn = root.querySelector('#vp-btn-stop-record');
      const cancelRecordBtn = root.querySelector('#vp-btn-cancel-record');
      const statusText = root.querySelector('#vp-record-status-text');

      // 1. Bắt đầu thu âm
      await startRecordBtn.dispatchEvent({ type: 'click' });
      assert.equal(startRecordBtn.style.display, 'none');
      assert.equal(stopRecordBtn.style.display, 'inline-flex');

      // 2. Dừng thu âm (stop)
      await stopRecordBtn.dispatchEvent({ type: 'click' });

      // C22 Invariant: Giao diện phải được đồng bộ lại SAU stop
      assert.equal(startRecordBtn.style.display, 'inline-flex', 'Nút Bắt đầu thu âm phải hiển thị lại sau khi dừng');
      assert.equal(stopRecordBtn.style.display, 'none', 'Nút Dừng thu âm phải bị ẩn');
      assert.equal(cancelRecordBtn.style.display, 'none', 'Nút Hủy phải bị ẩn');
      assert.ok(statusText.textContent.includes('Đã thu âm xong') || statusText.textContent.includes('Sẵn sàng'), 'Status text phải cập nhật');

      // 3. Có thể thu âm lần thứ hai thành công
      await startRecordBtn.dispatchEvent({ type: 'click' });
      assert.equal(startRecordBtn.style.display, 'none');
      assert.equal(stopRecordBtn.style.display, 'inline-flex');

      // Dọn dẹp
      await cancelRecordBtn.dispatchEvent({ type: 'click' });
    } finally {
      globalThis.navigator.mediaDevices.getUserMedia = originalGetUserMedia;
    }
  });

  it('C22: tự động dừng khi chạm ngưỡng thời lượng (auto-stop timer) phục hồi nút Start và cập nhật UI', async () => {
    const originalGetUserMedia = globalThis.navigator.mediaDevices.getUserMedia;
    let trackStopped = false;
    globalThis.navigator.mediaDevices.getUserMedia = async () => ({
      getTracks: () => [{ stop: () => { trackStopped = true; } }],
      getAudioTracks: () => [{ stop: () => { trackStopped = true; }, onended: null }],
    });

    let voice = null;
    try {
      voice = initVoice(root, {
        apiRequest: async () => ({}),
        timeoutFor,
        normalizeText,
        codePointLength
      });

      // Cấu hình hạn mức thời lượng cực ngắn (50ms) để kích hoạt timer auto-stop tự nhiên
      voice.setHealth(createMockHealth({ limits: { max_audio_duration_sec: 0.05 } }));

      const startRecordBtn = root.querySelector('#vp-btn-start-record');
      const stopRecordBtn = root.querySelector('#vp-btn-stop-record');
      const statusText = root.querySelector('#vp-record-status-text');

      // 1. Bắt đầu thu âm
      await startRecordBtn.dispatchEvent({ type: 'click' });
      assert.equal(startRecordBtn.style.display, 'none');
      assert.equal(stopRecordBtn.style.display, 'inline-flex');

      // 2. Chờ 80ms để timer auto-stop tự động kích hoạt
      await new Promise((r) => setTimeout(r, 80));

      // C22 Invariant: Sau khi auto-stop kết thúc tự nhiên:
      // - startBtn phục hồi hiển thị
      // - stopBtn bị ẩn
      // - Track âm thanh được dừng
      // - statusText cập nhật đã thu âm xong
      assert.equal(startRecordBtn.style.display, 'inline-flex', 'Nút Bắt đầu phải hiển thị sau auto-stop');
      assert.equal(stopRecordBtn.style.display, 'none', 'Nút Dừng phải bị ẩn sau auto-stop');
      assert.equal(trackStopped, true, 'Track âm thanh phải được dọn dẹp khi auto-stop');
      assert.ok(statusText.textContent.includes('Đã thu âm xong') || statusText.textContent.includes('Sẵn sàng'));

      // 3. Có thể bắt đầu thu âm phiên tiếp theo
      await startRecordBtn.dispatchEvent({ type: 'click' });
      assert.equal(startRecordBtn.style.display, 'none');
      assert.equal(stopRecordBtn.style.display, 'inline-flex');
    } finally {
      if (voice) voice.destroy();
      globalThis.navigator.mediaDevices.getUserMedia = originalGetUserMedia;
    }
  });

  it('C22: ngắt track âm thanh đột ngột (audioTrack.onended) tự động dừng và phục hồi UI', async () => {
    let trackEndedCallback = null;
    let trackStopped = false;
    const originalGetUserMedia = globalThis.navigator.mediaDevices.getUserMedia;
    globalThis.navigator.mediaDevices.getUserMedia = async () => ({
      getTracks: () => [{ stop: () => { trackStopped = true; } }],
      getAudioTracks: () => [
        {
          stop: () => { trackStopped = true; },
          set onended(fn) {
            trackEndedCallback = fn;
          },
          get onended() {
            return trackEndedCallback;
          },
        },
      ],
    });

    let voice = null;
    try {
      voice = initVoice(root, {
        apiRequest: async () => ({}),
        timeoutFor,
        normalizeText,
        codePointLength
      });

      const startRecordBtn = root.querySelector('#vp-btn-start-record');
      const stopRecordBtn = root.querySelector('#vp-btn-stop-record');

      // Bắt đầu thu âm
      await startRecordBtn.dispatchEvent({ type: 'click' });
      assert.equal(startRecordBtn.style.display, 'none');
      assert.equal(stopRecordBtn.style.display, 'inline-flex');

      // Kích hoạt sự kiện rút micro (track ended)
      if (trackEndedCallback) {
        trackEndedCallback();
      }
      await new Promise((r) => setTimeout(r, 20));

      // C22 Invariant: Giao diện phải được phục hồi
      assert.equal(startRecordBtn.style.display, 'inline-flex', 'Nút Bắt đầu phải hiển thị lại khi track kết thúc');
      assert.equal(stopRecordBtn.style.display, 'none', 'Nút Dừng phải bị ẩn khi track kết thúc');
      assert.equal(trackStopped, true, 'Track âm thanh phải được giải phóng');
    } finally {
      if (voice) voice.destroy();
      globalThis.navigator.mediaDevices.getUserMedia = originalGetUserMedia;
    }
  });

  it('C23: copy thành công hiển thị toast; copy thất bại hoặc thiếu API không hiện toast và hiển thị hướng dẫn lỗi', async () => {
    let clipboardWriteSucceeded = true;
    const originalClipboardDesc = Object.getOwnPropertyDescriptor(globalThis.navigator, 'clipboard');

    const mockApiRequest = async (path) => {
      if (path === '/api/asr/transcribe') {
        return {
          status: 'success',
          transcript: 'Transcript test',
          model_metadata: { is_mock: true }
        };
      }
      if (path === '/api/translate') {
        return {
          status: 'success',
          translation: 'Bản dịch tiếng Tày để test copy',
          direction: 'vi-tay',
          model_metadata: { is_mock: true }
        };
      }
      return {};
    };

    let voice = null;
    try {
      voice = initVoice(root, {
        apiRequest: mockApiRequest,
        timeoutFor,
        normalizeText,
        codePointLength
      });
      voice.setHealth(createMockHealth());

      // Nạp audio, transcribe và dịch
      const fileInput = root.querySelector('#vp-file-input');
      fileInput.files = [createFakeWavFile('voice.wav', 16000)];
      await fileInput.dispatchEvent({ type: 'change' });
      await root.querySelector('#vp-btn-transcribe').click();
      await root.querySelector('#vp-btn-translate').click();

      const copyBtn = root.querySelector('#vp-btn-copy');
      const copiedToast = root.querySelector('#vp-copied-toast');
      const errorBox = root.querySelector('#vp-trans-error');
      const errorMsg = root.querySelector('#vp-trans-error-msg');

      // Nhánh 1: Clipboard API hoạt động bình thường -> copy thành công
      Object.defineProperty(globalThis.navigator, 'clipboard', {
        value: {
          writeText: async () => {
            if (!clipboardWriteSucceeded) {
              throw new Error('Permission denied');
            }
          },
        },
        configurable: true,
        writable: true,
      });

      clipboardWriteSucceeded = true;
      await copyBtn.dispatchEvent({ type: 'click' });

      assert.equal(copiedToast.style.display, 'inline', 'Toast phải hiển thị khi copy thành công');
      assert.equal(copiedToast.textContent, 'Đã sao chép!');
      assert.equal(errorBox.style.display, 'none', 'Không được hiển thị lỗi khi copy thành công');

      // Nhánh 2: Clipboard API bị từ chối quyền (Permission denied)
      clipboardWriteSucceeded = false;
      await copyBtn.dispatchEvent({ type: 'click' });

      assert.equal(copiedToast.style.display, 'none', 'Toast KHÔNG được hiển thị khi copy bị từ chối quyền (C23)');
      assert.equal(errorBox.style.display, 'flex', 'Phải hiển thị hộp cảnh báo lỗi khi copy bị từ chối quyền');
      assert.ok(errorMsg.textContent.includes('Không thể tự động sao chép'), 'Thông báo phải hướng dẫn bôi đen và nhấn Ctrl+C');

      // Nhánh 3: Hoàn toàn thiếu Clipboard API (navigator.clipboard = undefined)
      Object.defineProperty(globalThis.navigator, 'clipboard', {
        value: undefined,
        configurable: true,
        writable: true,
      });
      await copyBtn.dispatchEvent({ type: 'click' });

      assert.equal(copiedToast.style.display, 'none', 'Toast KHÔNG được hiển thị khi thiếu Clipboard API (C23)');
      assert.equal(errorBox.style.display, 'flex', 'Phải hiển thị hộp cảnh báo lỗi khi thiếu Clipboard API');
      assert.ok(errorMsg.textContent.includes('Không thể tự động sao chép'), 'Thông báo phải hướng dẫn bôi đen và nhấn Ctrl+C');
    } finally {
      if (voice) voice.destroy();
      if (originalClipboardDesc) {
        Object.defineProperty(globalThis.navigator, 'clipboard', originalClipboardDesc);
      } else {
        delete globalThis.navigator.clipboard;
      }
    }
  });
});

describe('voice.js - Vòng đời an toàn (deactivate & destroy)', () => {
  let root;

  beforeEach(() => {
    root = new MockRootElement();
  });

  it('deactivate() hủy các request đang chạy và tăng revision token', () => {
    const voice = initVoice(root, {
      apiRequest: async () => ({}),
      timeoutFor,
      normalizeText,
      codePointLength
    });

    voice.deactivate();

    const translateBtn = root.querySelector('#vp-btn-translate');
    assert.equal(translateBtn.disabled, true);
  });

  it('destroy() dọn dẹp hoàn toàn DOM root', () => {
    const voice = initVoice(root, {
      apiRequest: async () => ({}),
      timeoutFor,
      normalizeText,
      codePointLength
    });

    voice.destroy();
    assert.equal(root.innerHTML, '');
  });
});
