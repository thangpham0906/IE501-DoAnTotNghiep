/**
 * audio.js - Xử lý âm thanh phía client: thu âm PCM, trộn mono, resample và mã hóa WAV.
 *
 * Tuân thủ đặc tả §5.3, §6.3:
 * - Chuẩn đầu ra: WAV PCM 16.000 Hz, 1 kênh (mono), 16-bit little-endian, format tag 1.
 * - Đọc actual sampleRate từ AudioContext (44.1 kHz, 48 kHz, v.v.), không giả định 16 kHz.
 * - Trộn đa kênh về mono (linear averaging).
 * - Resampling có kiểm soát chống aliasing bằng windowed sinc interpolation.
 * - Chặn cứng thời lượng theo số lượng mẫu và đồng hồ timer.
 * - Quản lý vòng đời dọn dẹp đầy đủ: tracks, AudioContext, worklet node, timers, URLs.
 */

/**
 * Trộn nhiều kênh Float32Array thành 1 kênh mono bằng phép lấy trung bình.
 * @param {Float32Array[]} channels - Danh sách mảng mẫu của từng kênh.
 * @returns {Float32Array} Mảng mẫu mono.
 */
export function mixToMono(channels) {
  if (!channels || channels.length === 0) {
    return new Float32Array(0);
  }
  if (channels.length === 1) {
    return new Float32Array(channels[0]);
  }

  const numChannels = channels.length;
  const frameCount = channels[0].length;
  const mono = new Float32Array(frameCount);

  for (let i = 0; i < frameCount; i++) {
    let sum = 0;
    for (let c = 0; c < numChannels; c++) {
      sum += channels[c][i] || 0;
    }
    mono[i] = sum / numChannels;
  }

  return mono;
}

/**
 * Resample mảng mẫu PCM từ sourceSampleRate về targetSampleRate.
 * Sử dụng bộ lọc nội suy sinc kèm cửa sổ Hann để chống aliasing khi downsampling.
 *
 * @param {Float32Array} samples - Mảng mẫu đầu vào.
 * @param {number} sourceSampleRate - Tần số lấy mẫu nguồn (Hz).
 * @param {number} [targetSampleRate=16000] - Tần số lấy mẫu đích (Hz, mặc định 16000).
 * @returns {Float32Array} Mảng mẫu đã resample về targetSampleRate.
 */
export function resamplePCM(samples, sourceSampleRate, targetSampleRate = 16000) {
  if (!samples || samples.length === 0) {
    return new Float32Array(0);
  }

  if (sourceSampleRate === targetSampleRate) {
    return new Float32Array(samples);
  }

  const ratio = targetSampleRate / sourceSampleRate;
  const outLength = Math.round(samples.length * ratio);
  if (outLength <= 0) {
    return new Float32Array(0);
  }

  const output = new Float32Array(outLength);

  if (ratio < 1) {
    // Downsampling: Cần bộ lọc thông thấp chống aliasing (cutoff = 0.5 * ratio)
    const cutoff = 0.5 * ratio;
    // Bán kính cửa sổ sinc tỷ lệ nghịch với ratio để thu đủ năng lượng
    const filterRadius = Math.min(32, Math.max(4, Math.ceil(4 / ratio)));

    for (let i = 0; i < outLength; i++) {
      const center = i / ratio;
      const kStart = Math.max(0, Math.floor(center - filterRadius));
      const kEnd = Math.min(samples.length - 1, Math.ceil(center + filterRadius));

      let sum = 0;
      let weightSum = 0;

      for (let k = kStart; k <= kEnd; k++) {
        const d = k - center;
        if (Math.abs(d) > filterRadius) continue;

        // Cửa sổ Hann
        const window = 0.5 + 0.5 * Math.cos((Math.PI * d) / filterRadius);

        // Hàm Sinc chuẩn hóa
        const z = 2 * cutoff * d;
        const sinc = z === 0 ? 1 : Math.sin(Math.PI * z) / (Math.PI * z);

        const weight = 2 * cutoff * sinc * window;
        sum += samples[k] * weight;
        weightSum += weight;
      }

      output[i] = weightSum > 0 ? sum / weightSum : 0;
    }
  } else {
    // Upsampling: Nội suy sinc thông thường (cutoff = 0.5)
    const filterRadius = 6;

    for (let i = 0; i < outLength; i++) {
      const center = i / ratio;
      const kStart = Math.max(0, Math.floor(center - filterRadius));
      const kEnd = Math.min(samples.length - 1, Math.ceil(center + filterRadius));

      let sum = 0;
      let weightSum = 0;

      for (let k = kStart; k <= kEnd; k++) {
        const d = k - center;
        if (Math.abs(d) > filterRadius) continue;

        const window = 0.5 + 0.5 * Math.cos((Math.PI * d) / filterRadius);
        const sinc = d === 0 ? 1 : Math.sin(Math.PI * d) / (Math.PI * d);

        const weight = sinc * window;
        sum += samples[k] * weight;
        weightSum += weight;
      }

      output[i] = weightSum > 0 ? sum / weightSum : 0;
    }
  }

  return output;
}

/**
 * Chuyển đổi Float32 [-1.0, 1.0] sang Int16Array [-32768, 32767] với giới hạn chống méo (clipping).
 * @param {Float32Array} samples
 * @returns {Int16Array}
 */
export function floatTo16BitPCM(samples) {
  if (!samples) return new Int16Array(0);

  const length = samples.length;
  const pcm16 = new Int16Array(length);

  for (let i = 0; i < length; i++) {
    let s = samples[i];
    // Chặn trong phạm vi hợp lệ [-1.0, 1.0]
    if (s > 1.0) s = 1.0;
    else if (s < -1.0) s = -1.0;

    // Chuyển sang 16-bit có dấu
    pcm16[i] = s < 0 ? Math.round(s * 32768) : Math.round(s * 32767);
  }

  return pcm16;
}

/**
 * Mã hóa mẫu PCM thành mảng byte WAV (RIFF/WAVE PCM 16-bit little-endian).
 * Tạo cấu trúc đúng 44 bytes header + data bytes chuẩn tắc.
 *
 * @param {Float32Array|Int16Array} samples - Dữ liệu âm thanh.
 * @param {number} [sampleRate=16000] - Tần số lấy mẫu (mặc định 16000 Hz).
 * @returns {Uint8Array} Toàn bộ tệp WAV dưới dạng byte buffer.
 */
export function encodeWAV(samples, sampleRate = 16000) {
  const pcm16 = samples instanceof Int16Array ? samples : floatTo16BitPCM(samples);
  const numFrames = pcm16.length;
  const bytesPerSample = 2; // 16-bit
  const numChannels = 1; // mono
  const dataByteLength = numFrames * bytesPerSample;
  const totalLength = 44 + dataByteLength;

  const buffer = new ArrayBuffer(totalLength);
  const view = new DataView(buffer);

  // 1. RIFF chunk descriptor
  // "RIFF" (0x52, 0x49, 0x46, 0x46)
  writeString(view, 0, 'RIFF');
  // RIFF size = 36 + dataByteLength
  view.setUint32(4, 36 + dataByteLength, true);
  // "WAVE" (0x57, 0x41, 0x56, 0x45)
  writeString(view, 8, 'WAVE');

  // 2. "fmt " subchunk
  writeString(view, 12, 'fmt ');
  // Subchunk1Size = 16 (cho PCM không nén)
  view.setUint32(16, 16, true);
  // AudioFormat = 1 (WAVE_FORMAT_PCM)
  view.setUint16(20, 1, true);
  // NumChannels = 1 (mono)
  view.setUint16(22, numChannels, true);
  // SampleRate = 16000
  view.setUint32(24, sampleRate, true);
  // ByteRate = SampleRate * NumChannels * BitsPerSample/8 = 16000 * 1 * 2 = 32000
  view.setUint32(28, sampleRate * numChannels * bytesPerSample, true);
  // BlockAlign = NumChannels * BitsPerSample/8 = 2
  view.setUint16(32, numChannels * bytesPerSample, true);
  // BitsPerSample = 16
  view.setUint16(34, 16, true);

  // 3. "data" subchunk
  writeString(view, 36, 'data');
  // Subchunk2Size = dataByteLength
  view.setUint32(40, dataByteLength, true);

  // Ghi các mẫu PCM 16-bit little-endian
  let offset = 44;
  for (let i = 0; i < numFrames; i++, offset += 2) {
    view.setInt16(offset, pcm16[i], true);
  }

  return new Uint8Array(buffer);
}

/**
 * Ghi chuỗi ASCII vào DataView tại offset xác định.
 * @param {DataView} view
 * @param {number} offset
 * @param {string} str
 */
function writeString(view, offset, str) {
  for (let i = 0; i < str.length; i++) {
    view.setUint8(offset + i, str.charCodeAt(i));
  }
}

/**
 * Phân tích và kiểm tra sơ bộ cấu trúc header WAV từ ArrayBuffer.
 * @param {ArrayBuffer} buffer
 * @returns {{
 *   valid: boolean,
 *   riffSize: number,
 *   audioFormat: number,
 *   channels: number,
 *   sampleRate: number,
 *   byteRate: number,
 *   blockAlign: number,
 *   bitsPerSample: number,
 *   dataSize: number,
 *   frameCount: number,
 *   durationSec: number,
 *   error?: string
 * }}
 */
export function parseWAVHeader(buffer) {
  if (!buffer || buffer.byteLength < 44) {
    return { valid: false, error: 'Kích thước tệp quá nhỏ (< 44 bytes).' };
  }

  const view = new DataView(buffer);
  const riff = String.fromCharCode(view.getUint8(0), view.getUint8(1), view.getUint8(2), view.getUint8(3));
  if (riff !== 'RIFF') {
    return { valid: false, error: `Header không phải RIFF (nhận ${riff}).` };
  }

  const riffSize = view.getUint32(4, true);
  const wave = String.fromCharCode(view.getUint8(8), view.getUint8(9), view.getUint8(10), view.getUint8(11));
  if (wave !== 'WAVE') {
    return { valid: false, error: `Container không phải WAVE (nhận ${wave}).` };
  }

  const fmt = String.fromCharCode(view.getUint8(12), view.getUint8(13), view.getUint8(14), view.getUint8(15));
  if (fmt !== 'fmt ') {
    return { valid: false, error: `Thiếu chunk fmt tại vị trí 12 (nhận ${fmt}).` };
  }

  const fmtSize = view.getUint32(16, true);
  const audioFormat = view.getUint16(20, true);
  const channels = view.getUint16(22, true);
  const sampleRate = view.getUint32(24, true);
  const byteRate = view.getUint32(28, true);
  const blockAlign = view.getUint16(32, true);
  const bitsPerSample = view.getUint16(34, true);

  const dataHeaderOffset = 20 + fmtSize;
  if (dataHeaderOffset + 8 > buffer.byteLength) {
    return { valid: false, error: 'Chunk data vượt quá kích thước buffer.' };
  }

  const dataTag = String.fromCharCode(
    view.getUint8(dataHeaderOffset),
    view.getUint8(dataHeaderOffset + 1),
    view.getUint8(dataHeaderOffset + 2),
    view.getUint8(dataHeaderOffset + 3)
  );
  if (dataTag !== 'data') {
    return { valid: false, error: `Kỳ vọng chunk 'data', nhận ${dataTag}.` };
  }

  const dataSize = view.getUint32(dataHeaderOffset + 4, true);
  const frameCount = blockAlign > 0 ? Math.floor(dataSize / blockAlign) : 0;
  const durationSec = sampleRate > 0 ? frameCount / sampleRate : 0;

  return {
    valid: true,
    riffSize,
    audioFormat,
    channels,
    sampleRate,
    byteRate,
    blockAlign,
    bitsPerSample,
    dataSize,
    frameCount,
    durationSec
  };
}

/**
 * Kiểm tra môi trường có hỗ trợ ghi âm trực tiếp hay không (§6.3).
 * @returns {{ supported: boolean, reason?: string }}
 */
export function checkRecordingSupport() {
  if (typeof window === 'undefined') {
    return { supported: false, reason: 'Môi trường không có window (không phải trình duyệt).' };
  }

  const hostname = window.location?.hostname || '';
  const isLocalhost =
    hostname === 'localhost' ||
    hostname === '127.0.0.1' ||
    hostname === '[::1]';

  const isSecure = window.isSecureContext || isLocalhost;
  if (!isSecure) {
    return {
      supported: false,
      reason: 'Thu âm yêu cầu kết nối bảo mật (HTTPS hoặc localhost). Trên mạng nội bộ LAN HTTP, vui lòng tải lên tệp WAV.'
    };
  }

  if (!navigator.mediaDevices || typeof navigator.mediaDevices.getUserMedia !== 'function') {
    return {
      supported: false,
      reason: 'Trình duyệt không hỗ trợ MediaDevices/getUserMedia. Vui lòng sử dụng trình duyệt hiện đại hoặc tải lên tệp WAV.'
    };
  }

  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  if (!AudioCtx) {
    return {
      supported: false,
      reason: 'Trình duyệt không hỗ trợ Web Audio API (AudioContext).'
    };
  }

  return { supported: true };
}

/**
 * Mã nguồn processor dưới dạng chuỗi để tạo Blob URL dự phòng khi addModule gặp hạn chế đường dẫn.
 */
const WORKLET_PROCESSOR_CODE = `
class PCMWorkletProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._isPaused = false;
    this.port.onmessage = (event) => {
      const data = event.data;
      if (!data) return;
      if (data.type === 'pause') this._isPaused = true;
      else if (data.type === 'resume') this._isPaused = false;
    };
  }
  process(inputs) {
    if (this._isPaused) return true;
    const input = inputs[0];
    if (!input || input.length === 0) return true;
    const numChannels = input.length;
    const frameCount = input[0].length;
    if (frameCount === 0) return true;
    const channels = new Array(numChannels);
    for (let c = 0; c < numChannels; c++) {
      channels[c] = new Float32Array(input[c]);
    }
    this.port.postMessage({ type: 'pcm', channels, frameCount });
    return true;
  }
}
registerProcessor('pcm-worklet-processor', PCMWorkletProcessor);
`;

/**
 * Quản lý vòng đời thu âm âm thanh micro hoàn chỉnh.
 * Xử lý: cấp quyền, AudioContext, AudioWorklet, resample, chặn cứng thời lượng, dọn tài nguyên.
 */
export class AudioRecorder {
  /**
   * @param {Object} options
   * @param {number} [options.maxDurationSec=30] - Thời lượng tối đa (giây).
   * @param {number} [options.targetSampleRate=16000] - Tần số lấy mẫu đầu ra (Hz).
   * @param {string} [options.workletUrl] - Đường dẫn tới pcm-worklet.js.
   * @param {Function} [options.onProgress] - Callback thông báo tiến độ { durationSec, maxDurationSec }.
   * @param {Function} [options.onMaxDuration] - Callback khi chạm giới hạn thời lượng.
   * @param {Function} [options.onError] - Callback khi phát sinh lỗi ngoại lệ.
   */
  constructor(options = {}) {
    this.maxDurationSec = options.maxDurationSec || 30;
    this.targetSampleRate = options.targetSampleRate || 16000;
    this.workletUrl = options.workletUrl || null;
    this.onProgress = options.onProgress || null;
    this.onMaxDuration = options.onMaxDuration || null;
    this.onError = options.onError || null;
    this.onStop = options.onStop || null;
    this.onStateChange = options.onStateChange || null;

    /** @type {'idle'|'requesting_permission'|'recording'|'stopping'|'stopped'|'cancelled'} */
    this.state = 'idle';

    this._mediaStream = null;
    this._audioContext = null;
    this._workletNode = null;
    this._sourceNode = null;
    this._scriptProcessorNode = null; // fallback nếu AudioWorklet không khả dụng
    this._chunks = []; // Mảng các Float32Array mono
    this._totalSamplesRecorded = 0;
    this._timerId = null;
    this._progressIntervalId = null;
    this._workletBlobUrl = null;
    this._actualSampleRate = 16000;
    this._isCancelled = false;
    this._sessionId = 0;
  }

  /**
   * Chuyển đổi trạng thái và thông báo tới observer.
   * @param {'idle'|'requesting_permission'|'recording'|'stopping'|'stopped'|'cancelled'} newState
   * @private
   */
  _changeState(newState) {
    this.state = newState;
    if (this.onStateChange) {
      try {
        this.onStateChange(newState);
      } catch (e) {
        console.error('Lỗi onStateChange callback:', e);
      }
    }
  }

  /**
   * Bắt đầu thu âm.
   * @returns {Promise<void>}
   */
  async start() {
    if (this.state === 'recording' || this.state === 'requesting_permission') {
      return;
    }

    const support = checkRecordingSupport();
    if (!support.supported) {
      const err = new Error(support.reason || 'Thiết bị không hỗ trợ thu âm.');
      err.code = 'NOT_SUPPORTED';
      if (this.onError) this.onError(err);
      throw err;
    }

    const currentSession = ++this._sessionId;
    this._isCancelled = false;
    this._changeState('requesting_permission');
    this._chunks = [];
    this._totalSamplesRecorded = 0;

    let stream = null;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });
    } catch (err) {
      // Nếu phiên này đã bị hủy hoặc thay thế bởi phiên khác trong lúc đợi cấp quyền, hoàn toàn bỏ qua lỗi cũ
      if (this._sessionId !== currentSession || this._isCancelled) {
        return;
      }
      this._changeState('idle');
      const userErr = new Error(
        err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError'
          ? 'Quyền truy cập micro bị từ chối. Vui lòng cấp quyền micro trong cài đặt trình duyệt hoặc chọn tải lên tệp WAV.'
          : err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError'
            ? 'Không tìm thấy thiết bị micro. Vui lòng kiểm tra kết nối thiết bị.'
            : `Không thể mở micro: ${err.message || 'Lỗi không xác định.'}`
      );
      userErr.code = err.name || 'PERMISSION_ERROR';
      if (this.onError) this.onError(userErr);
      throw userErr;
    }

    // Xử lý hủy muộn (Late permission resolve): nếu phiên này đã bị hủy hoặc thay thế bởi phiên khác
    if (this._sessionId !== currentSession || this._isCancelled || this.state !== 'requesting_permission') {
      if (stream) {
        try {
          stream.getTracks().forEach((track) => track.stop());
        } catch (e) {}
      }
      return;
    }

    this._mediaStream = stream;

    // Lắng nghe sự kiện track bị ngắt đột ngột (rút micro)
    const audioTrack = stream.getAudioTracks()[0];
    if (audioTrack) {
      audioTrack.onended = () => {
        if (this._sessionId === currentSession && this.state === 'recording') {
          this.stop();
        }
      };
    }

    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      const ctx = new AudioCtx();
      this._audioContext = ctx;
      this._actualSampleRate = ctx.sampleRate;

      if (this._sessionId !== currentSession || this._isCancelled) {
        stream.getTracks().forEach((track) => track.stop());
        try { ctx.close(); } catch (e) {}
        return;
      }

      this._sourceNode = ctx.createMediaStreamSource(stream);

      // Cấu hình thu thập PCM
      await this._setupAudioPipeline(currentSession);

      if (this._sessionId !== currentSession || this._isCancelled) {
        stream.getTracks().forEach((track) => track.stop());
        try { ctx.close(); } catch (e) {}
        return;
      }

      this._changeState('recording');

      // Chặn cứng thời lượng bằng timer phòng vệ
      this._timerId = setTimeout(() => {
        if (this._sessionId === currentSession && this.state === 'recording') {
          if (this.onMaxDuration) this.onMaxDuration();
          this.stop();
        }
      }, this.maxDurationSec * 1000);

      // Cập nhật đồng hồ tiến độ định kỳ
      this._progressIntervalId = setInterval(() => {
        if (this._sessionId === currentSession && this.state === 'recording') {
          const durationSec = Math.min(
            this.maxDurationSec,
            this._totalSamplesRecorded / this._actualSampleRate
          );
          if (this.onProgress) {
            this.onProgress({
              durationSec,
              maxDurationSec: this.maxDurationSec
            });
          }
        }
      }, 100);
    } catch (err) {
      if (this._sessionId !== currentSession || this._isCancelled) {
        return;
      }
      this._cleanupResources();
      this._changeState('idle');
      const setupErr = new Error(`Lỗi khởi tạo đường dẫn âm thanh: ${err.message}`);
      setupErr.code = 'AUDIO_PIPELINE_ERROR';
      if (this.onError) this.onError(setupErr);
      throw setupErr;
    }
  }

  /**
   * Thiết lập AudioWorklet hoặc ScriptProcessor fallback.
   * @param {number} currentSession
   * @private
   */
  async _setupAudioPipeline(currentSession) {
    const hasAudioWorklet =
      this._audioContext.audioWorklet &&
      typeof this._audioContext.audioWorklet.addModule === 'function';

    if (hasAudioWorklet) {
      try {
        if (this.workletUrl) {
          await this._audioContext.audioWorklet.addModule(this.workletUrl);
        } else {
          // Tạo Blob URL nội bộ nếu không cung cấp URL cụ thể
          const blob = new Blob([WORKLET_PROCESSOR_CODE], { type: 'application/javascript' });
          this._workletBlobUrl = URL.createObjectURL(blob);
          await this._audioContext.audioWorklet.addModule(this._workletBlobUrl);
        }

        if (this._sessionId !== currentSession) return;

        this._workletNode = new AudioWorkletNode(this._audioContext, 'pcm-worklet-processor');
        this._workletNode.port.onmessage = (event) => {
          if (this._sessionId === currentSession) {
            this._handleWorkletMessage(event);
          }
        };

        this._sourceNode.connect(this._workletNode);
        return;
      } catch (e) {
        // Nếu AudioWorklet addModule bị chặn (ví dụ do CSP hoặc URL), fallback sang ScriptProcessor
        console.warn('Không thể nạp AudioWorklet, chuyển sang ScriptProcessor fallback:', e);
      }
    }

    if (this._sessionId !== currentSession) return;

    // Fallback an toàn: ScriptProcessorNode
    const bufferSize = 4096;
    this._scriptProcessorNode = this._audioContext.createScriptProcessor(bufferSize, 1, 1);
    this._scriptProcessorNode.onaudioprocess = (e) => {
      if (this._sessionId !== currentSession || this.state !== 'recording') return;
      const inputBuffer = e.inputBuffer;
      const channelData = inputBuffer.getChannelData(0);
      this._handlePCMData(new Float32Array(channelData));
    };

    this._sourceNode.connect(this._scriptProcessorNode);
    // Nối với gain 0 rồi tới destination để giữ script processor chạy mà không phát ra loa
    const silentGain = this._audioContext.createGain();
    silentGain.gain.value = 0;
    this._scriptProcessorNode.connect(silentGain);
    silentGain.connect(this._audioContext.destination);
  }

  /**
   * Xử lý gói dữ liệu gửi từ AudioWorklet.
   * @private
   */
  _handleWorkletMessage(event) {
    if (this.state !== 'recording') return;
    const data = event.data;
    if (!data || data.type !== 'pcm') return;

    // Trộn các kênh về mono
    const mono = mixToMono(data.channels);
    this._handlePCMData(mono);
  }

  /**
   * Tiếp nhận mảng mẫu mono và kiểm soát chặn cứng thời lượng theo mẫu.
   * @private
   */
  _handlePCMData(monoChunk) {
    if (this.state !== 'recording') return;

    const maxSamplesAllowed = Math.floor(this._actualSampleRate * this.maxDurationSec);
    const remainingSamples = maxSamplesAllowed - this._totalSamplesRecorded;

    if (remainingSamples <= 0) {
      // Đã chạm hoặc vượt ngưỡng tối đa
      if (this.onMaxDuration) this.onMaxDuration();
      this.stop();
      return;
    }

    if (monoChunk.length > remainingSamples) {
      // Cắt đúng ranh giới mẫu tối đa cho phép
      const sliced = monoChunk.subarray(0, remainingSamples);
      this._chunks.push(sliced);
      this._totalSamplesRecorded += sliced.length;
      if (this.onMaxDuration) this.onMaxDuration();
      this.stop();
    } else {
      this._chunks.push(monoChunk);
      this._totalSamplesRecorded += monoChunk.length;
    }
  }

  /**
   * Dừng thu âm và hoàn thiện tệp WAV PCM 16 kHz.
   * @returns {Promise<{
   *   blob: Blob,
   *   wavBytes: Uint8Array,
   *   durationSec: number,
   *   sampleRate: number,
   *   frameCount: number
   * }>}
   */
  async stop() {
    if (this.state !== 'recording' && this.state !== 'requesting_permission') {
      return null;
    }

    this._sessionId++;
    this._changeState('stopping');

    // Xóa timers
    if (this._timerId) {
      clearTimeout(this._timerId);
      this._timerId = null;
    }
    if (this._progressIntervalId) {
      clearInterval(this._progressIntervalId);
      this._progressIntervalId = null;
    }

    // Ghép toàn bộ mẫu đã thu thập ở sampleRate thực tế
    const totalSamples = this._totalSamplesRecorded;
    const combined = new Float32Array(totalSamples);
    let offset = 0;
    for (const chunk of this._chunks) {
      combined.set(chunk, offset);
      offset += chunk.length;
    }

    const actualSampleRate = this._actualSampleRate;

    // Dọn dẹp tài nguyên phần cứng ngay lập tức
    this._cleanupResources();
    this._changeState('stopped');

    // Resample từ actualSampleRate về chuẩn 16.000 Hz
    const resampled = resamplePCM(combined, actualSampleRate, this.targetSampleRate);

    // Chặn cứng đầu ra không vượt quá số frame cho phép theo maxDurationSec ở 16 kHz
    const maxTargetFrames = Math.floor(this.targetSampleRate * this.maxDurationSec);
    const finalSamples =
      resampled.length > maxTargetFrames ? resampled.subarray(0, maxTargetFrames) : resampled;

    const frameCount = finalSamples.length;
    const durationSec = frameCount / this.targetSampleRate;

    // Mã hóa WAV chuẩn tắc
    const wavBytes = encodeWAV(finalSamples, this.targetSampleRate);
    const blob = new Blob([wavBytes.buffer], { type: 'audio/wav' });

    const result = {
      blob,
      wavBytes,
      durationSec,
      sampleRate: this.targetSampleRate,
      frameCount
    };

    if (this.onStop) {
      try {
        this.onStop(result);
      } catch (e) {
        console.error('Lỗi onStop callback:', e);
      }
    }

    return result;
  }

  /**
   * Hủy phiên thu âm hiện tại và hủy toàn bộ dữ liệu.
   */
  cancel() {
    this._sessionId++;
    this._isCancelled = true;
    this._changeState('cancelled');
    this._chunks = [];
    this._totalSamplesRecorded = 0;
    this._cleanupResources();
  }

  /**
   * Dọn dẹp toàn bộ tài nguyên (tracks, context, nodes, URLs, timers).
   * @private
   */
  _cleanupResources() {
    if (this._timerId) {
      clearTimeout(this._timerId);
      this._timerId = null;
    }
    if (this._progressIntervalId) {
      clearInterval(this._progressIntervalId);
      this._progressIntervalId = null;
    }

    if (this._mediaStream) {
      try {
        this._mediaStream.getTracks().forEach((track) => track.stop());
      } catch (e) {
        // Bỏ qua lỗi ngắt track
      }
      this._mediaStream = null;
    }

    if (this._workletNode) {
      try {
        this._workletNode.disconnect();
      } catch (e) {}
      this._workletNode = null;
    }

    if (this._scriptProcessorNode) {
      try {
        this._scriptProcessorNode.disconnect();
      } catch (e) {}
      this._scriptProcessorNode = null;
    }

    if (this._sourceNode) {
      try {
        this._sourceNode.disconnect();
      } catch (e) {}
      this._sourceNode = null;
    }

    if (this._audioContext) {
      try {
        if (this._audioContext.state !== 'closed') {
          this._audioContext.close();
        }
      } catch (e) {}
      this._audioContext = null;
    }

    if (this._workletBlobUrl) {
      try {
        URL.revokeObjectURL(this._workletBlobUrl);
      } catch (e) {}
      this._workletBlobUrl = null;
    }
  }

  /**
   * Hủy và giải phóng vĩnh viễn phiên ghi âm.
   */
  destroy() {
    this.cancel();
  }
}
