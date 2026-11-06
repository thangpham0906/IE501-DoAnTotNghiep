/**
 * audio.test.mjs - Unit tests cho các module xử lý âm thanh trong audio.js.
 *
 * Kiểm tra:
 * - Trộn đa kênh thành mono (mixToMono).
 * - Chuyển đổi và chống méo clipping 16-bit PCM (floatTo16BitPCM).
 * - Resampling có kiểm soát với sample rates 48000, 44100, 16000, 8000 Hz.
 * - Tính toán ranh giới thời lượng (duration bounds).
 * - Cấu trúc và tính toàn vẹn của WAV header (RIFF, fmt, data, frameCount, byteRate).
 * - Giới hạn thời lượng và vòng đời AudioRecorder.
 *
 * Chú ý: Các mẫu âm thanh tổng hợp trong kiểm thử này chỉ phục vụ xác minh
 * kỹ thuật xử lý tín hiệu, không coi là bằng chứng nhận dạng ASR thật (T05).
 */

import test, { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  mixToMono,
  floatTo16BitPCM,
  resamplePCM,
  encodeWAV,
  parseWAVHeader,
  checkRecordingSupport,
  AudioRecorder
} from '../../web_app/ui/js/audio.js';

describe('audio.js - Trộn đa kênh về mono (mixToMono)', () => {
  it('xử lý mảng kênh rỗng hoặc không hợp lệ', () => {
    assert.equal(mixToMono([]).length, 0);
    assert.equal(mixToMono(null).length, 0);
  });

  it('giữ nguyên khi chỉ có 1 kênh', () => {
    const channel = new Float32Array([0.1, -0.2, 0.5, 0.0]);
    const mono = mixToMono([channel]);
    assert.equal(mono.length, 4);
    for (let i = 0; i < 4; i++) {
      assert.equal(mono[i], channel[i]);
    }
  });

  it('trộn đều trung bình cho 2 kênh stereo', () => {
    const left = new Float32Array([1.0, -0.5, 0.4]);
    const right = new Float32Array([0.0, 0.5, -0.4]);
    const mono = mixToMono([left, right]);

    assert.equal(mono.length, 3);
    assert.ok(Math.abs(mono[0] - 0.5) < 1e-6);
    assert.ok(Math.abs(mono[1] - 0.0) < 1e-6);
    assert.ok(Math.abs(mono[2] - 0.0) < 1e-6);
  });

  it('bảo toàn sự yên lặng (silence in -> silence out)', () => {
    const ch1 = new Float32Array(100);
    const ch2 = new Float32Array(100);
    const mono = mixToMono([ch1, ch2]);
    assert.equal(mono.length, 100);
    for (let i = 0; i < 100; i++) {
      assert.equal(mono[i], 0);
    }
  });
});

describe('audio.js - Chuyển đổi và chống méo clipping 16-bit PCM (floatTo16BitPCM)', () => {
  it('xử lý mảng rỗng', () => {
    assert.equal(floatTo16BitPCM(new Float32Array(0)).length, 0);
    assert.equal(floatTo16BitPCM(null).length, 0);
  });

  it('chuyển đổi chính xác trong dải [-1.0, 1.0]', () => {
    const input = new Float32Array([0.0, 1.0, -1.0, 0.5, -0.5]);
    const pcm16 = floatTo16BitPCM(input);

    assert.equal(pcm16[0], 0);
    assert.equal(pcm16[1], 32767);
    assert.equal(pcm16[2], -32768);
    assert.equal(pcm16[3], 16384);
    assert.equal(pcm16[4], -16384);
  });

  it('chống méo clipping an toàn khi vượt biên (> 1.0 hoặc < -1.0)', () => {
    const input = new Float32Array([2.5, 10.0, -1.8, -99.0]);
    const pcm16 = floatTo16BitPCM(input);

    assert.equal(pcm16[0], 32767);
    assert.equal(pcm16[1], 32767);
    assert.equal(pcm16[2], -32768);
    assert.equal(pcm16[3], -32768);
  });
});

describe('audio.js - Resampling có kiểm soát (resamplePCM)', () => {
  it('giữ nguyên khi cùng tần số 16000 Hz', () => {
    const input = new Float32Array([0.1, 0.2, 0.3, 0.4]);
    const out = resamplePCM(input, 16000, 16000);
    assert.equal(out.length, 4);
    assert.deepEqual(Array.from(out), Array.from(input));
  });

  it('xử lý mảng rỗng', () => {
    const out = resamplePCM(new Float32Array(0), 48000, 16000);
    assert.equal(out.length, 0);
  });

  it('downsampling 48000 Hz -> 16000 Hz (tỷ lệ 3:1)', () => {
    // 48000 mẫu = đúng 1.0 giây âm thanh ở 48 kHz
    const numSourceSamples = 48000;
    const input = new Float32Array(numSourceSamples);
    // Điền tín hiệu tĩnh 0.5 (DC offset)
    input.fill(0.5);

    const out = resamplePCM(input, 48000, 16000);

    // Kỳ vọng đúng 16000 mẫu (1.0 giây ở 16 kHz)
    assert.equal(out.length, 16000);

    // Kiểm tra độ bảo toàn DC offset (nằm trong dung sai 2% ở vùng giữa, trừ biên do cửa sổ lọc)
    const midSample = out[8000];
    assert.ok(Math.abs(midSample - 0.5) < 0.02, `DC offset lệch quá lớn: ${midSample}`);
  });

  it('downsampling 44100 Hz -> 16000 Hz (tần số chuẩn CD)', () => {
    // 44100 mẫu = 1.0 giây âm thanh ở 44.1 kHz
    const input = new Float32Array(44100);
    input.fill(0.0); // Yên lặng

    const out = resamplePCM(input, 44100, 16000);

    // 44100 * (16000 / 44100) = đúng 16000 mẫu
    assert.equal(out.length, 16000);

    // Yên lặng phải được bảo toàn hoàn toàn
    for (let i = 0; i < out.length; i += 500) {
      assert.equal(out[i], 0);
    }
  });

  it('kiểm tra ranh giới thời lượng (duration bounds)', () => {
    // Thử nghiệm với các độ dài mẫu ngẫu nhiên ở 44100 Hz
    const testDurationsSec = [0.1, 0.5, 1.25, 2.0, 5.0];

    for (const durSec of testDurationsSec) {
      const sourceCount = Math.round(durSec * 44100);
      const input = new Float32Array(sourceCount);
      const out = resamplePCM(input, 44100, 16000);

      const actualDurationOut = out.length / 16000;
      const expectedDurationIn = sourceCount / 44100;

      // Sai lệch thời lượng không được vượt quá 1 mẫu đầu ra (1/16000 s = 0.0625 ms)
      const diffSec = Math.abs(actualDurationOut - expectedDurationIn);
      assert.ok(
        diffSec <= 1 / 16000,
        `Sai lệch thời lượng quá lớn: ${diffSec}s cho dur=${durSec}s`
      );
    }
  });

  it('upsampling 8000 Hz -> 16000 Hz (tỷ lệ 1:2)', () => {
    // 8000 mẫu (1.0s) -> 16000 mẫu (1.0s)
    const input = new Float32Array(8000);
    input.fill(0.3);

    const out = resamplePCM(input, 8000, 16000);
    assert.equal(out.length, 16000);

    const midSample = out[8000];
    assert.ok(Math.abs(midSample - 0.3) < 0.02, `Sai lệch upsampling: ${midSample}`);
  });
});

describe('audio.js - Mã hóa WAV và xác thực Header (encodeWAV & parseWAVHeader)', () => {
  it('tạo tệp WAV với kích thước header chuẩn xác 44 bytes', () => {
    const numSamples = 1600; // 0.1 giây ở 16 kHz
    const samples = new Float32Array(numSamples);
    const wavBytes = encodeWAV(samples, 16000);

    // Header 44 bytes + (1600 mẫu * 2 bytes/mẫu) = 3244 bytes
    assert.equal(wavBytes.length, 44 + numSamples * 2);

    const parsed = parseWAVHeader(wavBytes.buffer);
    assert.equal(parsed.valid, true);
    assert.equal(parsed.audioFormat, 1); // PCM không nén
    assert.equal(parsed.channels, 1); // Mono
    assert.equal(parsed.sampleRate, 16000); // 16 kHz
    assert.equal(parsed.bitsPerSample, 16); // 16-bit
    assert.equal(parsed.blockAlign, 2); // 1 * 2 = 2
    assert.equal(parsed.byteRate, 32000); // 16000 * 2 = 32000
    assert.equal(parsed.frameCount, numSamples);
    assert.ok(Math.abs(parsed.durationSec - 0.1) < 1e-6);
  });

  it('khớp hoàn toàn cấu trúc mà backend validate_wav yêu cầu', () => {
    // 480 mẫu = 0.03 giây ở 16 kHz
    const samples = new Float32Array(480);
    const wavBytes = encodeWAV(samples, 16000);
    const view = new DataView(wavBytes.buffer);

    // 1. Tag RIFF
    const riff = String.fromCharCode(view.getUint8(0), view.getUint8(1), view.getUint8(2), view.getUint8(3));
    assert.equal(riff, 'RIFF');

    // 2. RIFF Size = total - 8
    const riffSize = view.getUint32(4, true);
    assert.equal(riffSize + 8, wavBytes.length);

    // 3. WAVE
    const wave = String.fromCharCode(view.getUint8(8), view.getUint8(9), view.getUint8(10), view.getUint8(11));
    assert.equal(wave, 'WAVE');

    // 4. fmt
    const fmt = String.fromCharCode(view.getUint8(12), view.getUint8(13), view.getUint8(14), view.getUint8(15));
    assert.equal(fmt, 'fmt ');
    assert.equal(view.getUint32(16, true), 16); // fmt subchunk size

    // 5. data
    const data = String.fromCharCode(view.getUint8(36), view.getUint8(37), view.getUint8(38), view.getUint8(39));
    assert.equal(data, 'data');
    assert.equal(view.getUint32(40, true), 480 * 2);
  });

  it('xác minh ranh giới tối đa 30 giây (960.044 bytes)', () => {
    // 30 giây * 16000 = 480.000 mẫu
    const maxFrames = 480000;
    const samples = new Float32Array(maxFrames);
    const wavBytes = encodeWAV(samples, 16000);

    // 44 + 480.000 * 2 = 960.044 bytes
    assert.equal(wavBytes.length, 960044);

    const parsed = parseWAVHeader(wavBytes.buffer);
    assert.equal(parsed.valid, true);
    assert.equal(parsed.durationSec, 30.0);
    assert.equal(parsed.frameCount, 480000);
  });

  it('phát hiện tệp WAV không hợp lệ khi phân tích', () => {
    // Quá ngắn
    const shortBuffer = new ArrayBuffer(20);
    assert.equal(parseWAVHeader(shortBuffer).valid, false);

    // Sai magic tag
    const fakeBuffer = new ArrayBuffer(44);
    const view = new DataView(fakeBuffer);
    view.setUint8(0, 'N'.charCodeAt(0));
    assert.equal(parseWAVHeader(fakeBuffer).valid, false);
  });
});

describe('audio.js - Quản lý vòng đời AudioRecorder', () => {
  it('checkRecordingSupport thông báo lý do chính xác khi không có window', () => {
    // Trong môi trường Node.js (không có window hoặc window không phải secure context)
    const res = checkRecordingSupport();
    assert.equal(res.supported, false);
    assert.ok(typeof res.reason === 'string');
  });

  it('khởi tạo AudioRecorder với các tham số cấu hình', () => {
    const recorder = new AudioRecorder({
      maxDurationSec: 30,
      targetSampleRate: 16000
    });

    assert.equal(recorder.state, 'idle');
    assert.equal(recorder.maxDurationSec, 30);
    assert.equal(recorder.targetSampleRate, 16000);
  });

  it('hủy phiên thu âm cancel() chuyển sang trạng thái cancelled', () => {
    const recorder = new AudioRecorder({ maxDurationSec: 30 });
    recorder.cancel();
    assert.equal(recorder.state, 'cancelled');
  });

  it('destroy() gọi dọn dẹp và reset trạng thái an toàn', () => {
    const recorder = new AudioRecorder();
    recorder.destroy();
    assert.equal(recorder.state, 'cancelled');
  });

  it('C22: Deferred permission race (start A -> cancel -> start B -> resolve A -> resolve B) chỉ kích hoạt B và dừng A', async () => {
    // Thiết lập mock navigator và Web Audio API
    let resolvePermissionA = null;
    let resolvePermissionB = null;

    const promiseA = new Promise((resolve) => {
      resolvePermissionA = resolve;
    });
    const promiseB = new Promise((resolve) => {
      resolvePermissionB = resolve;
    });

    let getUserMediaCallCount = 0;
    let trackAStopped = false;
    let trackBStopped = false;

    const mockStreamA = {
      getTracks: () => [
        {
          stop: () => {
            trackAStopped = true;
          },
        },
      ],
      getAudioTracks: () => [
        {
          stop: () => {
            trackAStopped = true;
          },
          onended: null,
        },
      ],
    };

    const mockStreamB = {
      getTracks: () => [
        {
          stop: () => {
            trackBStopped = true;
          },
        },
      ],
      getAudioTracks: () => [
        {
          stop: () => {
            trackBStopped = true;
          },
          onended: null,
        },
      ],
    };

    const originalNavigatorDesc = Object.getOwnPropertyDescriptor(globalThis, 'navigator');
    const originalWindowDesc = Object.getOwnPropertyDescriptor(globalThis, 'window');

    try {
      Object.defineProperty(globalThis, 'window', {
        value: {
          isSecureContext: true,
          location: { hostname: 'localhost' },
          AudioContext: class {
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
          },
        },
        configurable: true,
        writable: true,
      });

      Object.defineProperty(globalThis, 'navigator', {
        value: {
          mediaDevices: {
            getUserMedia: async () => {
              getUserMediaCallCount++;
              if (getUserMediaCallCount === 1) return promiseA;
              return promiseB;
            },
          },
        },
        configurable: true,
        writable: true,
      });

      const recorder = new AudioRecorder({ maxDurationSec: 30 });

      // 1. Start phiên A
      const startAPromise = recorder.start();
      assert.equal(recorder.state, 'requesting_permission');
      assert.equal(getUserMediaCallCount, 1);

      // 2. Cancel phiên A
      recorder.cancel();
      assert.equal(recorder.state, 'cancelled');

      // 3. Start phiên B
      const startBPromise = recorder.start();
      assert.equal(recorder.state, 'requesting_permission');
      assert.equal(getUserMediaCallCount, 2);

      // 4. Quyền của phiên A được cấp muộn (resolve A)
      resolvePermissionA(mockStreamA);
      await startAPromise;

      // Track A phải bị dừng ngay lập tức vì phiên A đã bị hủy!
      assert.equal(trackAStopped, true, 'Track A phải bị dừng khi resolve muộn');
      // Trạng thái KHÔNG bị đổi thành recording của phiên A
      assert.equal(recorder.state, 'requesting_permission', 'Vẫn giữ trạng thái chờ của phiên B');
      assert.equal(trackBStopped, false, 'Track B chưa được resolve nên không bị dừng');

      // 5. Quyền của phiên B được cấp (resolve B)
      resolvePermissionB(mockStreamB);
      await startBPromise;

      // Phiên B phải bước vào trạng thái recording thành công!
      assert.equal(recorder.state, 'recording', 'Phiên B phải vào trạng thái recording');
      assert.equal(trackBStopped, false, 'Track B phải vẫn đang hoạt động');

      // 6. Dọn dẹp
      recorder.cancel();
      assert.equal(trackBStopped, true, 'Khi cancel phiên B thì Track B mới dừng');
    } finally {
      if (originalNavigatorDesc) {
        Object.defineProperty(globalThis, 'navigator', originalNavigatorDesc);
      } else {
        delete globalThis.navigator;
      }
      if (originalWindowDesc) {
        Object.defineProperty(globalThis, 'window', originalWindowDesc);
      } else {
        delete globalThis.window;
      }
    }
  });
});
