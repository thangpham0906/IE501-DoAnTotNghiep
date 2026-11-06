/**
 * Client gọi API cho Web Demo (§4, §6, §8.2).
 * Hỗ trợ timeout phòng thủ, hủy chủ động bằng AbortController, chuẩn hóa mã lỗi
 * và không tự ý gửi lại yêu cầu (no automatic retry).
 */

/**
 * Thông điệp tiếng Việt thân thiện tương ứng các mã lỗi theo mục 4.2 của đặc tả.
 */
export const ERROR_MESSAGES = {
  INVALID_INPUT: 'Dữ liệu đầu vào không hợp lệ hoặc rỗng.',
  UNSUPPORTED_DIRECTION: 'Chiều dịch không được hỗ trợ bởi hệ thống hiện tại.',
  INPUT_TOO_LONG: 'Văn bản vượt quá giới hạn độ dài cho phép.',
  REQUEST_TOO_LARGE: 'Kích thước yêu cầu vượt quá giới hạn tối đa cho phép.',
  AUDIO_TOO_LARGE: 'Tập tin âm thanh vượt quá dung lượng tối đa cho phép.',
  AUDIO_TOO_LONG: 'Thời lượng âm thanh vượt quá giới hạn tối đa cho phép.',
  AUDIO_UNSUPPORTED_FORMAT: 'Định dạng âm thanh không hỗ trợ (yêu cầu WAV PCM 16kHz mono 16-bit).',
  AUDIO_INVALID: 'Tập tin âm thanh không hợp lệ hoặc dữ liệu bị lỗi.',
  UNSUPPORTED_ASR_LANGUAGE: 'Ngôn ngữ âm thanh không được hỗ trợ (chỉ hỗ trợ tiếng Việt).',
  NO_SPEECH_DETECTED: 'Không tìm thấy giọng nói có nội dung trong tập tin âm thanh.',
  MODEL_NOT_FOUND: 'Không tìm thấy mô hình được yêu cầu.',
  MODEL_NOT_READY: 'Mô hình hiện chưa sẵn sàng phục vụ. Vui lòng chờ trong giây lát.',
  SERVICE_OVERLOADED: 'Hệ thống đang quá tải hàng đợi xử lý. Vui lòng thử lại sau.',
  INFERENCE_TIMEOUT: 'Quá hạn thời gian xử lý suy luận tại máy chủ. Vui lòng thử lại.',
  OUTPUT_TOO_LONG: 'Kết quả vượt quá giới hạn độ dài đầu ra của mô hình.',
  INFERENCE_FAILED: 'Quá trình dịch văn bản gặp sự cố tại máy chủ.',
  ASR_FAILURE: 'Quá trình nhận dạng giọng nói gặp lỗi tại máy chủ.',
  NOT_FOUND: 'Đường dẫn API không tồn tại.',
  METHOD_NOT_ALLOWED: 'Phương thức HTTP không được phép.',
  INTERNAL_ERROR: 'Máy chủ gặp sự cố nội bộ. Vui lòng thử lại sau.',
  CLIENT_TIMEOUT: 'Hết thời gian chờ phản hồi từ máy chủ.',
  NETWORK_ERROR: 'Không thể kết nối đến máy chủ. Vui lòng kiểm tra mạng.',
  MALFORMED_RESPONSE: 'Phản hồi từ máy chủ không đúng định dạng JSON.',
};

/**
 * Lớp lỗi chuẩn tắc cho các phản hồi API.
 * Chứa code, message, requestId, detail theo hợp đồng ARCHITECTURE.md.
 */
export class ApiError extends Error {
  constructor({ code, message, requestId = null, detail = null, status = null }) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.requestId = requestId;
    this.detail = detail;
    this.status = status;
  }
}

/**
 * Tính toán thời gian timeout phía client cho yêu cầu dịch hoặc ASR.
 * Đảm bảo timeout phía client luôn dài hơn tổng thời gian chờ hàng đợi + thời gian chạy suy luận
 * của máy chủ cộng thêm một khoảng đệm an toàn dương (bufferMs).
 *
 * @param {object|null|undefined} health - Trạng thái trả về từ /api/health
 * @param {'translation'|'asr'} kind - Loại tác vụ
 * @param {number} [bufferMs=5000] - Khoảng đệm an toàn (mặc định 5000ms)
 * @returns {number} - Thời gian timeout tính bằng millisecond (> 0)
 */
export function timeoutFor(health, kind, bufferMs = 5000) {
  const limits = health && typeof health === 'object' && health.limits ? health.limits : {};

  const queueSec =
    typeof limits.queue_timeout_sec === 'number' && limits.queue_timeout_sec > 0
      ? limits.queue_timeout_sec
      : 5;

  let execSec = 15;
  if (kind === 'asr') {
    execSec =
      typeof limits.asr_timeout_sec === 'number' && limits.asr_timeout_sec > 0
        ? limits.asr_timeout_sec
        : 20;
  } else {
    execSec =
      typeof limits.translation_timeout_sec === 'number' && limits.translation_timeout_sec > 0
        ? limits.translation_timeout_sec
        : 15;
  }

  const safeBuffer = typeof bufferMs === 'number' && bufferMs > 0 ? bufferMs : 5000;
  return Math.round((queueSec + execSec) * 1000 + safeBuffer);
}

/**
 * Gửi yêu cầu HTTP đến API máy chủ.
 *
 * @param {string} path - Đường dẫn API (ví dụ '/api/translate')
 * @param {object} [options] - Cấu hình yêu cầu
 * @param {string} [options.method='GET'] - Phương thức HTTP
 * @param {object} [options.json] - Body dữ liệu JSON
 * @param {FormData} [options.formData] - Body dữ liệu FormData (cho upload audio)
 * @param {AbortSignal} [options.signal] - Signal hủy yêu cầu từ phía gọi
 * @param {number} [options.timeoutMs] - Thời hạn timeout phía client (ms)
 * @returns {Promise<any>} - Dữ liệu JSON trả về từ API
 * @throws {ApiError|Error} - Lỗi chuẩn tắc hoặc AbortError khi bị hủy
 */
export async function apiRequest(
  path,
  { method = 'GET', json, formData, signal, timeoutMs } = {}
) {
  const controller = new AbortController();
  let isTimedOut = false;
  let timeoutTimer = null;

  if (typeof timeoutMs === 'number' && timeoutMs > 0) {
    timeoutTimer = setTimeout(() => {
      isTimedOut = true;
      controller.abort();
    }, timeoutMs);
  }

  let onExternalAbort = null;
  if (signal) {
    if (signal.aborted) {
      if (timeoutTimer) clearTimeout(timeoutTimer);
      const abortErr = new Error('Yêu cầu đã bị hủy.');
      abortErr.name = 'AbortError';
      throw abortErr;
    }
    onExternalAbort = () => {
      controller.abort();
    };
    signal.addEventListener('abort', onExternalAbort, { once: true });
  }

  const headers = {};
  let body;

  if (json !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(json);
  } else if (formData !== undefined) {
    // Để trình duyệt/runtime tự động thêm boundary thích hợp cho multipart/form-data
    body = formData;
  }

  const fetchOptions = {
    method: method.toUpperCase(),
    headers,
    body,
    signal: controller.signal,
  };

  let res;
  let rawText = '';
  let requestId = null;

  try {
    res = await fetch(path, fetchOptions);
    requestId = res.headers ? res.headers.get('x-request-id') : null;
    rawText = await res.text();
  } catch (err) {
    if (isTimedOut) {
      throw new ApiError({
        code: 'CLIENT_TIMEOUT',
        message: ERROR_MESSAGES.CLIENT_TIMEOUT,
        detail: { timeoutMs },
      });
    }

    if (signal?.aborted || (err.name === 'AbortError' && !isTimedOut)) {
      const abortErr = new Error('Yêu cầu đã bị hủy.');
      abortErr.name = 'AbortError';
      throw abortErr;
    }

    throw new ApiError({
      code: 'NETWORK_ERROR',
      message: res ? 'Không thể đọc nội dung phản hồi từ máy chủ.' : ERROR_MESSAGES.NETWORK_ERROR,
      requestId,
      detail: { originalError: err.message },
      status: res ? res.status : null,
    });
  } finally {
    if (timeoutTimer) clearTimeout(timeoutTimer);
    if (signal && onExternalAbort) {
      signal.removeEventListener('abort', onExternalAbort);
    }
  }

  let data = null;
  if (rawText.trim().length > 0) {
    try {
      data = JSON.parse(rawText);
    } catch {
      throw new ApiError({
        code: 'MALFORMED_RESPONSE',
        message: ERROR_MESSAGES.MALFORMED_RESPONSE,
        requestId,
        detail: { status: res.status, snippet: rawText.slice(0, 120) },
        status: res.status,
      });
    }
  }

  if (res.ok) {
    // Trường hợp HTTP 200 nhưng body chứa status: error
    if (data && typeof data === 'object' && data.status === 'error') {
      const code = data.error_code || 'API_ERROR';
      throw new ApiError({
        code,
        message: data.message || ERROR_MESSAGES[code] || 'Lỗi yêu cầu.',
        requestId: data.request_id || requestId,
        detail: data.detail || null,
        status: res.status,
      });
    }
    return data;
  }

  // Trường hợp HTTP >= 400
  const errorCode =
    data && typeof data === 'object' && data.error_code
      ? data.error_code
      : res.status === 404
      ? 'NOT_FOUND'
      : res.status === 405
      ? 'METHOD_NOT_ALLOWED'
      : 'HTTP_ERROR';

  const message =
    data && typeof data === 'object' && data.message
      ? data.message
      : ERROR_MESSAGES[errorCode] || `Yêu cầu thất bại với mã trạng thái ${res.status}.`;

  const detail =
    data && typeof data === 'object' && data.detail !== undefined
      ? data.detail
      : { status: res.status };

  throw new ApiError({
    code: errorCode,
    message,
    requestId: (data && data.request_id) || requestId,
    detail,
    status: res.status,
  });
}
