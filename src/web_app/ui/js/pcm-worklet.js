/**
 * pcm-worklet.js - AudioWorkletProcessor trích xuất luồng PCM từ micro.
 *
 * Chạy trên AudioWorklet thread độc lập để thu thập mẫu âm thanh thô (Float32Array)
 * mà không gây gián đoạn UI thread.
 */

class PCMWorkletProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._isPaused = false;

    this.port.onmessage = (event) => {
      const data = event.data;
      if (!data) return;

      if (data.type === 'pause') {
        this._isPaused = true;
      } else if (data.type === 'resume') {
        this._isPaused = false;
      }
    };
  }

  process(inputs, outputs, parameters) {
    if (this._isPaused) {
      return true;
    }

    const input = inputs[0];
    if (!input || input.length === 0) {
      return true;
    }

    const numChannels = input.length;
    const frameCount = input[0].length;
    if (frameCount === 0) {
      return true;
    }

    // Sao chép buffer từng kênh để truyền an toàn qua MessagePort
    const channels = new Array(numChannels);
    for (let c = 0; c < numChannels; c++) {
      channels[c] = new Float32Array(input[c]);
    }

    this.port.postMessage({
      type: 'pcm',
      channels: channels,
      frameCount: frameCount
    });

    return true;
  }
}

registerProcessor('pcm-worklet-processor', PCMWorkletProcessor);
