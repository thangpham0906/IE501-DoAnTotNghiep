/**
 * Unit tests cho api_client.js sử dụng Node.js test runner (node --test).
 * Kiểm tra timeoutFor, apiRequest với mock responses, abort, timeout, error mapping và không retry.
 */

import test, { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import {
  apiRequest,
  timeoutFor,
  ApiError,
  ERROR_MESSAGES,
} from '../../web_app/ui/js/api_client.js';

describe('api_client - timeoutFor', () => {
  it('tính timeout cho translation với limits đầy đủ', () => {
    const health = {
      limits: {
        queue_timeout_sec: 5,
        translation_timeout_sec: 15,
        asr_timeout_sec: 20,
      },
    };
    // (5 + 15) * 1000 + 5000 = 25000 ms
    const t = timeoutFor(health, 'translation', 5000);
    assert.equal(t, 25000);
    // Luôn lớn hơn deadline máy chủ (20000ms)
    assert.ok(t > 20000);
  });

  it('tính timeout cho asr với limits đầy đủ', () => {
    const health = {
      limits: {
        queue_timeout_sec: 5,
        translation_timeout_sec: 15,
        asr_timeout_sec: 20,
      },
    };
    // (5 + 20) * 1000 + 5000 = 30000 ms
    const t = timeoutFor(health, 'asr', 5000);
    assert.equal(t, 30000);
  });

  it('áp dụng giá trị mặc định khi health hoặc limits rỗng/null', () => {
    // default queue 5s, translation 15s + 5s buffer = 25000ms
    assert.equal(timeoutFor(null, 'translation'), 25000);
    // default queue 5s, asr 20s + 5s buffer = 30000ms
    assert.equal(timeoutFor({}, 'asr'), 30000);
    assert.equal(timeoutFor({ limits: {} }, 'translation', 3000), 23000);
  });

  it('bảo đảm bufferMs luôn dương', () => {
    const health = { limits: { queue_timeout_sec: 2, translation_timeout_sec: 3 } };
    // bufferMs <= 0 sẽ fallback về 5000
    const t = timeoutFor(health, 'translation', -100);
    assert.equal(t, (2 + 3) * 1000 + 5000);
  });
});

describe('api_client - apiRequest', () => {
  const originalFetch = globalThis.fetch;
  let callCount = 0;

  beforeEach(() => {
    callCount = 0;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('gửi GET request thành công và trả về JSON', async () => {
    globalThis.fetch = async (url, opts) => {
      callCount++;
      assert.equal(opts.method, 'GET');
      return new Response(JSON.stringify({ status: 'ready', api_version: '1' }), {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
          'X-Request-ID': 'req-123',
        },
      });
    };

    const res = await apiRequest('/api/health');
    assert.equal(callCount, 1);
    assert.equal(res.status, 'ready');
    assert.equal(res.api_version, '1');
  });

  it('gửi POST request kèm JSON body thành công', async () => {
    globalThis.fetch = async (url, opts) => {
      callCount++;
      assert.equal(opts.method, 'POST');
      assert.equal(opts.headers['Content-Type'], 'application/json');
      const body = JSON.parse(opts.body);
      assert.equal(body.text, 'Xin chào');
      assert.equal(body.direction, 'vi-tay');

      return new Response(
        JSON.stringify({
          status: 'success',
          translation: 'Slương pỉ noọng',
          direction: 'vi-tay',
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json', 'X-Request-ID': 'req-post' },
        }
      );
    };

    const res = await apiRequest('/api/translate', {
      method: 'POST',
      json: { text: 'Xin chào', direction: 'vi-tay' },
    });

    assert.equal(callCount, 1);
    assert.equal(res.status, 'success');
    assert.equal(res.translation, 'Slương pỉ noọng');
  });

  it('ném ApiError khi máy chủ trả về lỗi §4.2 (ví dụ 400 INPUT_TOO_LONG)', async () => {
    globalThis.fetch = async () => {
      callCount++;
      return new Response(
        JSON.stringify({
          status: 'error',
          error_code: 'INPUT_TOO_LONG',
          message: 'Văn bản vượt quá giới hạn cho phép.',
          detail: { current_length: 1005, max_allowed: 1000, limit_unit: 'code_points' },
          request_id: 'err-400',
        }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json', 'X-Request-ID': 'err-400' },
        }
      );
    };

    await assert.rejects(
      async () => {
        await apiRequest('/api/translate', {
          method: 'POST',
          json: { text: 'Quá dài', direction: 'vi-tay' },
        });
      },
      (err) => {
        assert.ok(err instanceof ApiError);
        assert.equal(err.code, 'INPUT_TOO_LONG');
        assert.equal(err.requestId, 'err-400');
        assert.equal(err.detail.current_length, 1005);
        assert.equal(err.status, 400);
        return true;
      }
    );

    // Không tự động retry
    assert.equal(callCount, 1);
  });

  it('xử lý lỗi 503 MODEL_NOT_READY và 504 INFERENCE_TIMEOUT mà không retry', async () => {
    globalThis.fetch = async () => {
      callCount++;
      return new Response(
        JSON.stringify({
          status: 'error',
          error_code: 'MODEL_NOT_READY',
          message: 'Mô hình chưa sẵn sàng.',
          detail: null,
          request_id: 'err-503',
        }),
        {
          status: 503,
          headers: { 'Content-Type': 'application/json', 'X-Request-ID': 'err-503' },
        }
      );
    };

    await assert.rejects(
      async () => {
        await apiRequest('/api/translate', {
          method: 'POST',
          json: { text: 'Test', direction: 'vi-tay' },
        });
      },
      (err) => {
        assert.equal(err.code, 'MODEL_NOT_READY');
        assert.equal(err.status, 503);
        return true;
      }
    );

    // Đảm bảo không tự ý gửi lại
    assert.equal(callCount, 1);
  });

  it('xử lý phản hồi không phải JSON (malformed HTML hoặc chuỗi rỗng)', async () => {
    globalThis.fetch = async () => {
      callCount++;
      return new Response('<html><body>502 Bad Gateway</body></html>', {
        status: 502,
        headers: { 'Content-Type': 'text/html', 'X-Request-ID': 'bad-gateway' },
      });
    };

    await assert.rejects(
      async () => {
        await apiRequest('/api/translate', { method: 'POST', json: { text: 'Test' } });
      },
      (err) => {
        assert.ok(err instanceof ApiError);
        assert.equal(err.code, 'MALFORMED_RESPONSE');
        assert.equal(err.requestId, 'bad-gateway');
        assert.equal(err.detail.status, 502);
        return true;
      }
    );
    assert.equal(callCount, 1);
  });

  it('ném AbortError khi chủ động hủy bằng AbortController ngoài', async () => {
    const externalController = new AbortController();

    globalThis.fetch = async (url, opts) => {
      callCount++;
      return new Promise((resolve, reject) => {
        opts.signal.addEventListener('abort', () => {
          const e = new Error('The operation was aborted');
          e.name = 'AbortError';
          reject(e);
        });
      });
    };

    const promise = apiRequest('/api/translate', {
      method: 'POST',
      json: { text: 'Test' },
      signal: externalController.signal,
    });

    // Kích hoạt hủy
    externalController.abort();

    await assert.rejects(
      async () => {
        await promise;
      },
      (err) => {
        assert.equal(err.name, 'AbortError');
        return true;
      }
    );
    assert.equal(callCount, 1);
  });

  it('ném CLIENT_TIMEOUT khi quá hạn timeoutMs', async () => {
    globalThis.fetch = async (url, opts) => {
      callCount++;
      return new Promise((resolve, reject) => {
        opts.signal.addEventListener('abort', () => {
          const e = new Error('The operation was aborted');
          e.name = 'AbortError';
          reject(e);
        });
      });
    };

    await assert.rejects(
      async () => {
        await apiRequest('/api/translate', {
          method: 'POST',
          json: { text: 'Test' },
          timeoutMs: 30, // 30ms timeout
        });
      },
      (err) => {
        assert.ok(err instanceof ApiError);
        assert.equal(err.code, 'CLIENT_TIMEOUT');
        return true;
      }
    );
    assert.equal(callCount, 1);
  });

  it('xử lý lỗi mất mạng (network failure)', async () => {
    globalThis.fetch = async () => {
      callCount++;
      throw new TypeError('Failed to fetch');
    };

    await assert.rejects(
      async () => {
        await apiRequest('/api/translate', { method: 'POST', json: { text: 'Test' } });
      },
      (err) => {
        assert.ok(err instanceof ApiError);
        assert.equal(err.code, 'NETWORK_ERROR');
        return true;
      }
    );
    assert.equal(callCount, 1);
  });

  it('C16: ném AbortError khi signal ngoài abort trong lúc đang đọc body stream (res.text)', async () => {
    const externalController = new AbortController();
    let bodyGateAborted = false;

    globalThis.fetch = async (url, opts) => {
      callCount++;
      // Headers trả về ngay lập tức, nhưng res.text() bị hoãn cho đến khi có abort
      return {
        ok: true,
        status: 200,
        headers: new Headers({ 'Content-Type': 'application/json', 'X-Request-ID': 'gate-req' }),
        text: () => {
          return new Promise((resolve, reject) => {
            opts.signal.addEventListener('abort', () => {
              bodyGateAborted = true;
              const err = new Error('The operation was aborted');
              err.name = 'AbortError';
              reject(err);
            });
          });
        },
      };
    };

    const promise = apiRequest('/api/translate', {
      method: 'POST',
      json: { text: 'Test body gate' },
      signal: externalController.signal,
      timeoutMs: 5000,
    });

    // Cho phép event loop chạy một tick để fetch() trả về headers và tiến vào res.text()
    await new Promise((r) => setTimeout(r, 10));

    // Kích hoạt hủy bằng signal ngoài
    externalController.abort();

    await assert.rejects(
      async () => {
        await promise;
      },
      (err) => {
        assert.equal(err.name, 'AbortError');
        return true;
      }
    );

    assert.equal(callCount, 1);
    assert.equal(bodyGateAborted, true);
  });

  it('C16: ném CLIENT_TIMEOUT khi quá hạn timeoutMs trong lúc đang đọc body stream (res.text)', async () => {
    let bodyGateTimedOut = false;

    globalThis.fetch = async (url, opts) => {
      callCount++;
      return {
        ok: true,
        status: 200,
        headers: new Headers({ 'Content-Type': 'application/json', 'X-Request-ID': 'gate-timeout' }),
        text: () => {
          return new Promise((resolve, reject) => {
            opts.signal.addEventListener('abort', () => {
              bodyGateTimedOut = true;
              const err = new Error('The operation was aborted');
              err.name = 'AbortError';
              reject(err);
            });
          });
        },
      };
    };

    await assert.rejects(
      async () => {
        await apiRequest('/api/translate', {
          method: 'POST',
          json: { text: 'Test body timeout' },
          timeoutMs: 30, // 30ms timeout
        });
      },
      (err) => {
        assert.ok(err instanceof ApiError);
        assert.equal(err.code, 'CLIENT_TIMEOUT');
        return true;
      }
    );

    assert.equal(callCount, 1);
    assert.equal(bodyGateTimedOut, true);
  });
});
