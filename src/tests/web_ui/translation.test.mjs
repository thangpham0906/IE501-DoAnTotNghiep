/**
 * Unit tests cho translation.js sử dụng Node.js test runner (node --test).
 * Kiểm tra các luồng nghiệp vụ:
 * - Khởi tạo và kiểm soát nút Dịch theo health/models.
 * - Đếm Unicode code point trên ô nguồn.
 * - Chống stale response bằng snapshot và revision.
 * - Đảo chiều Swap an toàn (chỉ đảo khi khớp snapshot, không tự gửi).
 * - Hiển thị metadata và nhãn mô phỏng.
 */

import test, { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { TranslationController } from '../../web_app/ui/js/translation.js';
import { normalizeText, codePointLength } from '../../web_app/ui/js/text_utils.js';
import { timeoutFor } from '../../web_app/ui/js/api_client.js';

// Mock DOM Element đơn giản phục vụ test logic không phụ thuộc trình duyệt
class MockElement {
  constructor(initialValue = '') {
    this.value = initialValue;
    this.textContent = '';
    this.placeholder = '';
    this.disabled = false;
    this.className = '';
    this.classList = {
      _classes: new Set(),
      add: (c) => this.classList._classes.add(c),
      remove: (c) => this.classList._classes.delete(c),
      contains: (c) => this.classList._classes.has(c),
    };
    this.attributes = new Map();
    this.listeners = new Map();
  }

  addEventListener(event, fn) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event).push(fn);
  }

  dispatchEvent(event) {
    const list = this.listeners.get(event.type) || [];
    for (const fn of list) {
      fn(event);
    }
  }

  setAttribute(name, val) {
    this.attributes.set(name, String(val));
  }

  getAttribute(name) {
    return this.attributes.get(name) || null;
  }

  removeAttribute(name) {
    this.attributes.delete(name);
  }

  focus() {}
  select() {}
}

function createMockElements() {
  return {
    sourceText: new MockElement(),
    targetText: new MockElement(),
    sourceLabel: new MockElement(),
    targetLabel: new MockElement(),
    directionSelect: new MockElement('vi-tay'),
    charCount: new MockElement(),
    translateBtn: new MockElement(),
    swapBtn: new MockElement(),
    clearBtn: new MockElement(),
    copyBtn: new MockElement(),
    copyFeedback: new MockElement(),
    translateSpinner: new MockElement(),
    translateStatusText: new MockElement(),
    errorBanner: new MockElement(),
    metaContainer: new MockElement(),
    metaMockBadge: new MockElement(),
    metaModelInfo: new MockElement(),
    metaTiming: new MockElement(),
    activeModelBadge: new MockElement(),
  };
}

describe('TranslationController - Khởi tạo và kiểm soát nút Dịch', () => {
  let elements;
  let helpers;
  let controller;

  beforeEach(() => {
    elements = createMockElements();
    helpers = {
      apiRequest: async () => {},
      timeoutFor,
      normalizeText,
      codePointLength,
    };
    controller = new TranslationController(elements, helpers);
  });

  it('nút Dịch bị vô hiệu ban đầu khi chưa có văn bản và engine chưa ready', () => {
    assert.equal(elements.translateBtn.disabled, true);
    assert.equal(elements.charCount.textContent, '0 / 1000 ký tự');
  });

  it('nút Dịch vẫn vô hiệu khi engine loading dù đã nhập văn bản', () => {
    controller.setHealth({
      translation: {
        state: 'loading',
        supported_directions: ['vi-tay', 'tay-vi'],
      },
    });
    elements.sourceText.value = 'Hôm nay trời đẹp';
    elements.sourceText.dispatchEvent({ type: 'input' });

    assert.equal(elements.translateBtn.disabled, true);
  });

  it('nút Dịch được bật khi engine ready và văn bản hợp lệ', () => {
    controller.setHealth({
      translation: {
        state: 'ready',
        supported_directions: ['vi-tay', 'tay-vi'],
      },
      limits: { max_text_length: 500 },
    });
    elements.sourceText.value = 'Hôm nay bản làng mở hội';
    elements.sourceText.dispatchEvent({ type: 'input' });

    assert.equal(elements.translateBtn.disabled, false);
    assert.equal(elements.charCount.textContent, '23 / 500 ký tự');
  });

  it('vô hiệu nút Dịch khi văn bản chỉ toàn khoảng trắng hoặc vượt giới hạn', () => {
    controller.setHealth({
      translation: {
        state: 'ready',
        supported_directions: ['vi-tay', 'tay-vi'],
      },
      limits: { max_text_length: 5 },
    });

    // Chỉ toàn khoảng trắng
    elements.sourceText.value = '   \t\n  ';
    elements.sourceText.dispatchEvent({ type: 'input' });
    assert.equal(elements.translateBtn.disabled, true);
    assert.equal(elements.charCount.textContent, '0 / 5 ký tự');

    // Vượt quá 5 code point
    elements.sourceText.value = '123456';
    elements.sourceText.dispatchEvent({ type: 'input' });
    assert.equal(elements.translateBtn.disabled, true);
    assert.ok(elements.charCount.classList.contains('char-count--exceeded'));
  });
});

describe('TranslationController - Dịch văn bản và hiển thị metadata', () => {
  it('thực hiện dịch thành công, hiển thị bản dịch và metadata', async () => {
    const elements = createMockElements();
    let requestedBody = null;

    const helpers = {
      apiRequest: async (path, opts) => {
        requestedBody = opts.json;
        return {
          status: 'success',
          translation: 'Vằn nay lăng pỉ noọng.',
          direction: 'vi-tay',
          model_metadata: {
            model_id: 'mock-demo',
            checkpoint_version: 'mock-v1',
            is_mock: true,
          },
          latency_ms: 15,
          queue_ms: 2,
        };
      },
      timeoutFor,
      normalizeText,
      codePointLength,
    };

    const controller = new TranslationController(elements, helpers);
    controller.setHealth({
      translation: { state: 'ready', supported_directions: ['vi-tay', 'tay-vi'] },
    });

    elements.sourceText.value = 'Hôm nay làng xóm.';
    elements.sourceText.dispatchEvent({ type: 'input' });

    await controller.translate();

    assert.equal(requestedBody.text, 'Hôm nay làng xóm.');
    assert.equal(requestedBody.direction, 'vi-tay');
    assert.equal(elements.targetText.value, 'Vằn nay lăng pỉ noọng.');
    assert.equal(elements.metaMockBadge.textContent, 'MÔ PHỎNG');
    assert.equal(elements.metaModelInfo.textContent, 'mock-demo (mock-v1)');
    assert.ok(elements.metaTiming.textContent.includes('15 ms'));
  });
});

describe('TranslationController - Chống Stale Response', () => {
  it('loại bỏ phản hồi cũ nếu người dùng sửa văn bản nguồn trong khi request đang gửi', async () => {
    const elements = createMockElements();
    let resolveApi = null;

    const helpers = {
      apiRequest: async () => {
        return new Promise((resolve) => {
          resolveApi = resolve;
        });
      },
      timeoutFor,
      normalizeText,
      codePointLength,
    };

    const controller = new TranslationController(elements, helpers);
    controller.setHealth({
      translation: { state: 'ready', supported_directions: ['vi-tay', 'tay-vi'] },
    });

    // 1. Nhập câu thứ nhất
    elements.sourceText.value = 'Câu thứ nhất';
    elements.sourceText.dispatchEvent({ type: 'input' });

    // 2. Bấm dịch (đang treo)
    const translatePromise = controller.translate();

    // 3. Người dùng sửa sang câu thứ hai trong lúc request 1 đang chạy
    elements.sourceText.value = 'Câu thứ hai đã thay đổi';
    elements.sourceText.dispatchEvent({ type: 'input' });

    // 4. Request 1 hoàn tất trả về
    resolveApi({
      status: 'success',
      translation: 'Bản dịch cũ của câu thứ nhất',
      direction: 'vi-tay',
    });
    await translatePromise;

    // KẾT QUẢ: targetText KHÔNG được bị ghi đè bởi bản dịch cũ!
    assert.equal(elements.targetText.value, '');
  });

  it('loại bỏ phản hồi cũ nếu người dùng đổi chiều trong khi request đang gửi', async () => {
    const elements = createMockElements();
    let resolveApi = null;

    const helpers = {
      apiRequest: async () => {
        return new Promise((resolve) => {
          resolveApi = resolve;
        });
      },
      timeoutFor,
      normalizeText,
      codePointLength,
    };

    const controller = new TranslationController(elements, helpers);
    controller.setHealth({
      translation: { state: 'ready', supported_directions: ['vi-tay', 'tay-vi'] },
    });

    elements.sourceText.value = 'Câu nguồn';
    elements.sourceText.dispatchEvent({ type: 'input' });

    const translatePromise = controller.translate();

    // Người dùng đổi chiều sang tay-vi
    elements.directionSelect.value = 'tay-vi';
    elements.directionSelect.dispatchEvent({ type: 'change', target: { value: 'tay-vi' } });

    // Request 1 trả về
    resolveApi({
      status: 'success',
      translation: 'Bản dịch vi-tay cũ',
      direction: 'vi-tay',
    });
    await translatePromise;

    // KẾT QUẢ: Không nhận bản dịch của chiều cũ
    assert.equal(elements.targetText.value, '');
  });
});

describe('TranslationController - Thao tác Đảo chiều (Swap)', () => {
  it('đảo hai ô an toàn khi kết quả khớp snapshot nguồn và không tự gửi', async () => {
    const elements = createMockElements();
    let apiCallCount = 0;

    const helpers = {
      apiRequest: async () => {
        apiCallCount++;
        return {
          status: 'success',
          translation: 'Bản dịch tiếng Tày',
          direction: 'vi-tay',
          model_metadata: { is_mock: true },
        };
      },
      timeoutFor,
      normalizeText,
      codePointLength,
    };

    const controller = new TranslationController(elements, helpers);
    controller.setHealth({
      translation: { state: 'ready', supported_directions: ['vi-tay', 'tay-vi'] },
    });

    elements.sourceText.value = 'Câu tiếng Việt';
    elements.sourceText.dispatchEvent({ type: 'input' });
    await controller.translate();

    assert.equal(apiCallCount, 1);
    assert.equal(elements.targetText.value, 'Bản dịch tiếng Tày');

    // Nhấn nút Swap
    elements.swapBtn.dispatchEvent({ type: 'click' });

    // Hai ô đã được hoán đổi
    assert.equal(elements.sourceText.value, 'Bản dịch tiếng Tày');
    assert.equal(elements.targetText.value, 'Câu tiếng Việt');
    assert.equal(elements.directionSelect.value, 'tay-vi');
    assert.equal(controller.currentDirection, 'tay-vi');

    // Quan trọng: KHÔNG tự động gửi yêu cầu dịch
    assert.equal(apiCallCount, 1);
  });

  it('khi chưa có bản dịch hoặc nguồn bị sửa lệch snapshot: giữ nguyên nguồn, đổi chiều, xóa kết quả cũ và không tự gửi', () => {
    const elements = createMockElements();
    let apiCallCount = 0;

    const helpers = {
      apiRequest: async () => {
        apiCallCount++;
      },
      timeoutFor,
      normalizeText,
      codePointLength,
    };

    const controller = new TranslationController(elements, helpers);
    controller.setHealth({
      translation: { state: 'ready', supported_directions: ['vi-tay', 'tay-vi'] },
    });

    // Chỉ có văn bản nguồn, chưa dịch
    elements.sourceText.value = 'Chưa dịch câu này';
    elements.sourceText.dispatchEvent({ type: 'input' });

    elements.swapBtn.dispatchEvent({ type: 'click' });

    // Giữ nguyên nguồn, đổi chiều, xóa kết quả
    assert.equal(elements.sourceText.value, 'Chưa dịch câu này');
    assert.equal(elements.targetText.value, '');
    assert.equal(elements.directionSelect.value, 'tay-vi');
    assert.equal(controller.currentDirection, 'tay-vi');

    // Không tự gửi
    assert.equal(apiCallCount, 0);
  });
});

describe('TranslationController - Hồi quy C17 & C18', () => {
  let elements;
  let helpers;
  let controller;
  let apiCallCount = 0;

  beforeEach(() => {
    elements = createMockElements();
    apiCallCount = 0;
    helpers = {
      apiRequest: async (path, opts) => {
        apiCallCount++;
        return {
          status: 'success',
          translation: `[MOCK ${opts.json.direction}] ${opts.json.text}`,
          direction: opts.json.direction,
          model_metadata: {
            model_id: 'mock-demo',
            checkpoint_version: 'v1',
            is_mock: true,
          },
          latency_ms: 18,
          queue_ms: 3,
        };
      },
      timeoutFor,
      normalizeText,
      codePointLength,
    };
    controller = new TranslationController(elements, helpers);
    controller.setHealth({
      translation: { state: 'ready', supported_directions: ['vi-tay', 'tay-vi'] },
    });
  });

  it('C17: sửa nguồn sau khi đã có bản dịch thành công sẽ xóa kết quả cũ và metadata', async () => {
    // 1. Dịch source A
    elements.sourceText.value = 'source A';
    elements.sourceText.dispatchEvent({ type: 'input' });
    await controller.translate();

    assert.equal(elements.targetText.value, '[MOCK vi-tay] source A');
    assert.equal(elements.metaContainer.classList.contains('hidden'), false);
    assert.ok(elements.metaTiming.textContent.includes('18 ms'));

    // 2. Người dùng sửa nguồn thành source B
    elements.sourceText.value = 'source B';
    elements.sourceText.dispatchEvent({ type: 'input' });

    // KẾT QUẢ: targetText và metadata phải bị xóa, không được giữ [MOCK vi-tay] source A
    assert.equal(elements.targetText.value, '');
    assert.equal(elements.metaContainer.classList.contains('hidden'), true);
    assert.equal(controller.lastCompletedSnapshot, null);
  });

  it('C17: đổi chiều sau khi đã có bản dịch thành công sẽ xóa kết quả cũ và metadata', async () => {
    // 1. Dịch thành công với chiều vi-tay
    elements.sourceText.value = 'source A';
    elements.sourceText.dispatchEvent({ type: 'input' });
    await controller.translate();

    assert.equal(elements.targetText.value, '[MOCK vi-tay] source A');
    assert.equal(elements.targetLabel.textContent, 'Tiếng Tày');

    // 2. Người dùng đổi sang chiều tay-vi qua select
    elements.directionSelect.value = 'tay-vi';
    elements.directionSelect.dispatchEvent({ type: 'change', target: { value: 'tay-vi' } });

    // KẾT QUẢ: nhãn đích chuyển thành Tiếng Việt, targetText bị xóa, metadata bị xóa
    assert.equal(elements.targetLabel.textContent, 'Tiếng Việt');
    assert.equal(elements.targetText.value, '');
    assert.equal(elements.metaContainer.classList.contains('hidden'), true);
    assert.equal(controller.lastCompletedSnapshot, null);
  });

  it('C17: swap sau khi hoàn tất không được gán timing/metadata của chiều cũ cho kết quả đảo', async () => {
    // 1. Dịch thành công
    elements.sourceText.value = 'source A';
    elements.sourceText.dispatchEvent({ type: 'input' });
    await controller.translate();

    assert.equal(elements.targetText.value, '[MOCK vi-tay] source A');
    assert.equal(elements.metaContainer.classList.contains('hidden'), false);

    // 2. Bấm swap
    elements.swapBtn.dispatchEvent({ type: 'click' });

    // KẾT QUẢ: Hai ô đảo nhau, nhưng metadata và timing của chiều cũ bị xóa sạch
    assert.equal(elements.sourceText.value, '[MOCK vi-tay] source A');
    assert.equal(elements.targetText.value, 'source A');
    assert.equal(elements.metaContainer.classList.contains('hidden'), true);
    assert.equal(elements.metaTiming.textContent, '');
  });

  it('C17: request dịch tiếp theo bị lỗi thì không giữ lại kết quả cũ của lần trước', async () => {
    // 1. Dịch thành công lần đầu
    elements.sourceText.value = 'source A';
    elements.sourceText.dispatchEvent({ type: 'input' });
    await controller.translate();

    assert.equal(elements.targetText.value, '[MOCK vi-tay] source A');

    // 2. Lần dịch tiếp theo gặp lỗi 503 từ máy chủ
    helpers.apiRequest = async () => {
      const err = new Error('Mô hình đang bận.');
      err.code = 'MODEL_NOT_READY';
      err.status = 503;
      throw err;
    };

    elements.sourceText.value = 'source B';
    elements.sourceText.dispatchEvent({ type: 'input' });
    await controller.translate();

    // KẾT QUẢ: targetText phải rỗng, không được chứa bản dịch của source A
    assert.equal(elements.targetText.value, '');
    assert.equal(elements.metaContainer.classList.contains('hidden'), true);
    assert.equal(elements.errorBanner.classList.contains('hidden'), false);
    assert.ok(elements.errorBanner.textContent.includes('Mô hình đang bận'));
  });

  it('C18: showError hiển thị đúng đơn vị token khi detail.limit_unit là tokens', () => {
    controller.showError({
      code: 'INPUT_TOO_LONG',
      message: 'Văn bản vượt quá giới hạn.',
      detail: {
        current_length: 600,
        max_allowed: 512,
        limit_unit: 'tokens',
      },
      requestId: 'req-tok-1',
    });

    assert.equal(elements.errorBanner.classList.contains('hidden'), false);
    assert.equal(
      elements.errorBanner.textContent,
      'Văn bản vượt quá giới hạn (hiện tại: 600, tối đa: 512 token). (Mã yêu cầu: req-tok-1)'
    );
  });

  it('C18: showError hiển thị đúng đơn vị ký tự khi detail.limit_unit là code_points', () => {
    controller.showError({
      code: 'INPUT_TOO_LONG',
      message: 'Văn bản vượt quá giới hạn.',
      detail: {
        current_length: 1005,
        max_allowed: 1000,
        limit_unit: 'code_points',
      },
      requestId: 'req-cp-1',
    });

    assert.equal(elements.errorBanner.classList.contains('hidden'), false);
    assert.equal(
      elements.errorBanner.textContent,
      'Văn bản vượt quá giới hạn (hiện tại: 1005, tối đa: 1000 ký tự). (Mã yêu cầu: req-cp-1)'
    );
  });

  it('An toàn XSS trên TranslationController thật: hiển thị bản dịch chứa script/HTML tags an toàn qua value/textContent', async () => {
    const maliciousPayload = '<script>alert("xss")</script><img src=x onerror=alert(1)>';
    helpers.apiRequest = async () => ({
      status: 'success',
      translation: maliciousPayload,
      direction: 'vi-tay',
      model_metadata: { is_mock: true },
    });

    elements.sourceText.value = 'Nội dung dịch';
    elements.sourceText.dispatchEvent({ type: 'input' });
    await controller.translate();

    assert.equal(elements.targetText.value, maliciousPayload);
    // targetText là textarea (thuộc tính value), dữ liệu chỉ là chuỗi văn bản thuần túy
    assert.ok(elements.targetText.value.includes('<script>'));
  });

  it('Chống double-submit trên TranslationController thật: khi đang dịch (isTranslating), canTranslate() trả false và không gửi lặp', async () => {
    let resolveApi = null;
    const slowPromise = new Promise((resolve) => {
      resolveApi = resolve;
    });

    let networkCallCount = 0;
    helpers.apiRequest = async () => {
      networkCallCount++;
      return slowPromise;
    };

    elements.sourceText.value = 'Nội dung dịch thử';
    elements.sourceText.dispatchEvent({ type: 'input' });

    // Lần gọi 1
    const t1 = controller.translate();
    assert.equal(controller.isTranslating, true);
    assert.equal(controller.canTranslate(), false, 'canTranslate() phải trả false khi đang dịch');

    // Lần gọi 2 & 3 kích hoạt trong khi lần 1 đang bay
    const t2 = controller.translate();
    const t3 = controller.translate();

    resolveApi({
      status: 'success',
      translation: 'Kết quả dịch',
      direction: 'vi-tay',
      model_metadata: { is_mock: true },
    });

    await Promise.all([t1, t2, t3]);

    // Bắt buộc chỉ có duy nhất 1 yêu cầu gửi qua mạng!
    assert.equal(networkCallCount, 1);
    assert.equal(elements.targetText.value, 'Kết quả dịch');
  });
});
