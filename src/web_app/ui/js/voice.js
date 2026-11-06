/**
 * voice.js - Module quản lý giao diện và luồng giọng nói (§6.3, T21).
 *
 * Xuất initVoice(root, dependencies) trả về { setHealth, deactivate, destroy }.
 *
 * Luồng hoạt động:
 * Thu âm / Tải WAV -> ASR -> Transcript chỉnh sửa được -> Người dùng bấm "Dịch sang tiếng Tày" -> Dịch snapshot (vi-tay).
 */

import { AudioRecorder, checkRecordingSupport } from './audio.js';

/**
 * Khởi tạo giao diện giọng nói bên trong root element.
 *
 * @param {HTMLElement} root - DOM container dành riêng cho voice tab.
 * @param {Object} dependencies
 * @param {Function} dependencies.apiRequest - Hàm gọi API trả JSON hoặc ném lỗi có { code, message, requestId, detail }.
 * @param {Function} dependencies.timeoutFor - Hàm tính timeout (health, kind) ms.
 * @param {Function} dependencies.normalizeText - Hàm chuẩn hóa text theo Unicode White_Space và NFC.
 * @param {Function} dependencies.codePointLength - Hàm đếm code points.
 * @returns {{
 *   setHealth: (health: Object) => void,
 *   deactivate: () => void,
 *   destroy: () => void
 * }}
 */
export function initVoice(root, dependencies = {}) {
  const {
    apiRequest,
    timeoutFor = () => 20000,
    normalizeText = (t) => (t ? t.normalize('NFC').trim() : ''),
    codePointLength = (t) => (t ? Array.from(t).length : 0)
  } = dependencies;

  if (!root) {
    throw new Error('root element là bắt buộc cho initVoice.');
  }

  // State nội bộ của Voice Panel
  let currentHealth = null;
  let activeTab = 'record'; // 'record' | 'upload'
  let audioBlob = null;
  let audioBlobUrl = null;
  let audioSourceFileName = 'recording.wav';

  let audioRecorder = null;
  let isRecording = false;
  let recordingSessionId = 0; // Định danh phiên thu âm để chặn lỗi/kết quả từ phiên cũ

  // Revision tokens để chống stale response
  let asrRevision = 0;
  let translateRevision = 0;
  let asrAbortController = null;
  let translateAbortController = null;

  // ASR Result state
  let lastAsrResult = null;
  let asrError = null;
  let isTranscribing = false;
  let hasSuccessfulAsr = false; // Chỉ bật khi có kết quả ASR thành công trên âm thanh hiện tại

  // Transcript state
  let editedTranscript = '';
  let transcriptCharCount = 0;

  // Translation Result state
  let lastTranslationResult = null;
  let translationError = null;
  let isTranslating = false;

  // Cấu hình giới hạn mặc định (sẽ cập nhật từ health)
  let limits = {
    max_text_length: 1000,
    max_audio_file_bytes: 10485760, // 10 MiB
    max_audio_duration_sec: 30,
    audio_format: 'wav_pcm_s16le',
    audio_sample_rate_hz: 16000,
    audio_channels: 1
  };

  // Khởi tạo HTML khung
  renderSkeleton();

  // Khởi tạo AudioRecorder
  createRecorderInstance();

  // Đăng ký sự kiện rời trang an toàn
  const onPageHide = () => {
    deactivate();
  };
  window.addEventListener('pagehide', onPageHide);

  /**
   * Tạo instance AudioRecorder với giới hạn thời lượng hiện hành.
   */
  function createRecorderInstance() {
    if (audioRecorder) {
      audioRecorder.destroy();
      audioRecorder = null;
    }

    audioRecorder = new AudioRecorder({
      maxDurationSec: limits.max_audio_duration_sec,
      targetSampleRate: 16000,
      onProgress: ({ durationSec, maxDurationSec }) => {
        if (isRecording) {
          updateTimerDisplay(durationSec, maxDurationSec);
        }
      },
      onMaxDuration: () => {
        // Tự dừng khi chạm ngưỡng tối đa (chặn theo mẫu + timer)
        handleStopRecording();
      },
      onStateChange: () => {
        updateRecordUIState();
      },
      onStop: (result) => {
        isRecording = false;
        if (result && result.blob) {
          setAudioBlob(result.blob, 'recording.wav');
        }
        updateRecordUIState();
      },
      onError: (err) => {
        isRecording = false;
        showAsrError(err.message || 'Lỗi thu âm micro.');
        updateRecordUIState();
      }
    });
  }

  /**
   * Render toàn bộ cấu trúc HTML của voice panel vào root.
   */
  function renderSkeleton() {
    root.innerHTML = `
      <div class="voice-panel">
        <!-- Cảnh báo thử nghiệm §6.3 -->
        <div class="vp-warning-banner" role="alert">
          <span class="vp-warning-icon">⚠️</span>
          <div>
            <strong>Thử nghiệm giọng nói:</strong> Tính năng nhận dạng âm thanh hiện chỉ hỗ trợ
            ngôn ngữ tiếng Việt đầu vào, sau đó dịch sang tiếng Tày. <em>Hệ thống chưa hỗ trợ nhận dạng tiếng Tày.</em>
          </div>
        </div>

        <!-- Thanh thông tin engine & định dạng -->
        <div class="vp-status-bar">
          <div class="vp-status-items">
            <span class="vp-format-hint">
              Định dạng yêu cầu: <strong>WAV PCM 16.000 Hz, Mono, 16-bit</strong> | Tối đa: <span id="vp-limit-duration">30</span>s, <span id="vp-limit-size">10</span>MB
            </span>
          </div>
          <div class="vp-status-items" id="vp-badges-container">
            <span class="vp-badge vp-badge-loading" id="vp-badge-asr">ASR: Đang kiểm tra...</span>
            <span class="vp-badge vp-badge-loading" id="vp-badge-trans">Dịch: Đang kiểm tra...</span>
          </div>
        </div>

        <!-- Tabs chuyển cách nạp âm thanh -->
        <div class="vp-tabs" role="tablist">
          <button type="button" class="vp-tab-btn active" id="vp-tab-record-btn" role="tab" aria-selected="true">
            🎙️ Thu âm trực tiếp
          </button>
          <button type="button" class="vp-tab-btn" id="vp-tab-upload-btn" role="tab" aria-selected="false">
            📁 Tải lên tệp WAV
          </button>
        </div>

        <!-- Khối 1: Nạp âm thanh (Thu âm hoặc Upload) -->
        <section class="vp-card" aria-labelledby="vp-input-title">
          <h3 class="vp-card-title" id="vp-input-title">1. Đầu vào âm thanh tiếng Việt</h3>

          <!-- View Thu âm -->
          <div id="vp-record-view">
            <div class="vp-record-controls">
              <div class="vp-timer-display" id="vp-timer">00:00 / 00:30</div>
              <div id="vp-record-status-text" style="font-size: 0.875rem; color: var(--vp-text-muted);">Sẵn sàng thu âm</div>
              <div class="vp-record-btn-group">
                <button type="button" class="vp-btn vp-btn-primary" id="vp-btn-start-record">
                  🎙️ Bắt đầu thu âm
                </button>
                <button type="button" class="vp-btn vp-btn-danger" id="vp-btn-stop-record" style="display: none;">
                  <span class="vp-recording-pulse"></span> Dừng thu âm
                </button>
                <button type="button" class="vp-btn vp-btn-secondary" id="vp-btn-cancel-record" style="display: none;">
                  Hủy
                </button>
              </div>
            </div>
          </div>

          <!-- View Upload File -->
          <div id="vp-upload-view" style="display: none;">
            <div class="vp-upload-zone" id="vp-drop-zone">
              <input type="file" id="vp-file-input" class="vp-upload-input" accept=".wav,audio/wav,audio/x-wav" />
              <div>
                <strong>Bấm để chọn tệp WAV</strong> hoặc kéo thả tệp vào đây
              </div>
              <div style="font-size: 0.8rem; color: var(--vp-text-muted);">
                Chỉ chấp nhận tệp có đuôi .wav (WAV PCM 16.000 Hz, 1 kênh mono)
              </div>
            </div>
            <div class="vp-file-info" id="vp-file-info" style="display: none;">
              <span id="vp-file-name-display"></span>
              <button type="button" class="vp-btn vp-btn-secondary" id="vp-btn-remove-file" style="padding: 0.2rem 0.5rem; font-size: 0.75rem;">
                Xóa
              </button>
            </div>
          </div>

          <!-- Trình phát âm thanh xem trước -->
          <div class="vp-audio-preview" id="vp-audio-preview" style="display: none;">
            <audio id="vp-audio-player" controls></audio>
            <div style="display: flex; gap: 0.5rem; align-items: center; margin-top: 0.5rem;">
              <button type="button" class="vp-btn vp-btn-primary" id="vp-btn-transcribe">
                🔍 Nhận dạng giọng nói (ASR)
              </button>
            </div>
          </div>

          <!-- Thông báo lỗi ASR -->
          <div class="vp-error-box" id="vp-asr-error" style="display: none;" role="alert">
            <span id="vp-asr-error-msg"></span>
            <span class="vp-error-code" id="vp-asr-error-code"></span>
          </div>
        </section>

        <!-- Khối 2: Transcript nhận dạng & Chỉnh sửa -->
        <section class="vp-card" aria-labelledby="vp-transcript-title">
          <h3 class="vp-card-title" id="vp-transcript-title">
            <span>2. Văn bản nhận dạng (Transcript tiếng Việt)</span>
            <span id="vp-asr-meta-info" style="font-size: 0.8rem; font-weight: normal; color: var(--vp-text-muted);"></span>
          </h3>

          <div class="vp-transcript-wrapper">
            <textarea
              class="vp-textarea"
              id="vp-transcript-input"
              placeholder="Văn bản nhận dạng từ âm thanh sẽ xuất hiện tại đây. Bạn có thể tự do chỉnh sửa trước khi dịch..."
              aria-label="Văn bản nhận dạng tiếng Việt có thể chỉnh sửa"
            ></textarea>

            <div class="vp-char-counter" id="vp-char-counter-container">
              <span id="vp-char-counter">0 / 1000 ký tự</span>
              <span id="vp-char-warning" style="display: none; color: var(--vp-danger);">Vượt quá giới hạn ký tự!</span>
            </div>

            <!-- Nhãn ASR Mock độc lập -->
            <div class="vp-mock-notice" id="vp-asr-mock-notice" style="display: none;">
              ℹ️ <strong>Mô phỏng ASR:</strong> Kết quả mẫu từ hệ thống mock, không phải kết quả nhận dạng thật từ tệp âm thanh.
            </div>

            <div style="margin-top: 0.75rem;">
              <button type="button" class="vp-btn vp-btn-primary" id="vp-btn-translate" disabled>
                🌐 Dịch sang tiếng Tày (vi-tay)
              </button>
            </div>
          </div>
        </section>

        <!-- Khối 3: Kết quả dịch sang tiếng Tày -->
        <section class="vp-card" aria-labelledby="vp-translation-title">
          <h3 class="vp-card-title" id="vp-translation-title">
            <span>3. Bản dịch tiếng Tày</span>
            <span id="vp-trans-meta-info" style="font-size: 0.8rem; font-weight: normal; color: var(--vp-text-muted);"></span>
          </h3>

          <div class="vp-result-box" id="vp-translation-result" tabindex="0" aria-live="polite">
            <span class="vp-result-placeholder">Bản dịch tiếng Tày sẽ hiển thị tại đây sau khi bạn xác nhận transcript và bấm Dịch...</span>
          </div>

          <!-- Nhãn Dịch Mock độc lập -->
          <div class="vp-mock-notice" id="vp-trans-mock-notice" style="display: none;">
            ℹ️ <strong>Mô phỏng Dịch:</strong> Bản dịch được sinh từ mô hình dịch mô phỏng (mock).
          </div>

          <!-- Nút hành động bản dịch -->
          <div style="margin-top: 0.75rem; display: flex; align-items: center; gap: 0.5rem;" id="vp-trans-actions">
            <button type="button" class="vp-btn vp-btn-secondary" id="vp-btn-copy" style="display: none;">
              📋 Sao chép bản dịch
            </button>
            <span class="vp-copied-toast" id="vp-copied-toast" style="display: none;">Đã sao chép!</span>
          </div>

          <!-- Thông báo lỗi Dịch -->
          <div class="vp-error-box" id="vp-trans-error" style="display: none;" role="alert">
            <span id="vp-trans-error-msg"></span>
            <span class="vp-error-code" id="vp-trans-error-code"></span>
          </div>
        </section>
      </div>
    `;

    bindEventListeners();
  }

  /**
   * Đăng ký các sự kiện tương tác DOM.
   */
  function bindEventListeners() {
    // 1. Chuyển đổi tab Thu âm / Upload
    const tabRecordBtn = root.querySelector('#vp-tab-record-btn');
    const tabUploadBtn = root.querySelector('#vp-tab-upload-btn');
    const recordView = root.querySelector('#vp-record-view');
    const uploadView = root.querySelector('#vp-upload-view');

    tabRecordBtn.addEventListener('click', () => {
      if (activeTab === 'record') return;
      activeTab = 'record';
      tabRecordBtn.classList.add('active');
      tabRecordBtn.setAttribute('aria-selected', 'true');
      tabUploadBtn.classList.remove('active');
      tabUploadBtn.setAttribute('aria-selected', 'false');
      recordView.style.display = 'block';
      uploadView.style.display = 'none';
    });

    tabUploadBtn.addEventListener('click', () => {
      if (activeTab === 'upload') return;
      handleCancelRecording();
      activeTab = 'upload';
      tabUploadBtn.classList.add('active');
      tabUploadBtn.setAttribute('aria-selected', 'true');
      tabRecordBtn.classList.remove('active');
      tabRecordBtn.setAttribute('aria-selected', 'false');
      uploadView.style.display = 'block';
      recordView.style.display = 'none';
    });

    // 2. Các nút thu âm
    const startRecordBtn = root.querySelector('#vp-btn-start-record');
    const stopRecordBtn = root.querySelector('#vp-btn-stop-record');
    const cancelRecordBtn = root.querySelector('#vp-btn-cancel-record');

    startRecordBtn.addEventListener('click', () => handleStartRecording());
    stopRecordBtn.addEventListener('click', () => handleStopRecording());
    cancelRecordBtn.addEventListener('click', () => handleCancelRecording());

    // 3. Upload file zone
    const dropZone = root.querySelector('#vp-drop-zone');
    const fileInput = root.querySelector('#vp-file-input');
    const removeFileBtn = root.querySelector('#vp-btn-remove-file');

    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropZone.style.borderColor = 'var(--vp-primary)';
    });

    dropZone.addEventListener('dragleave', () => {
      dropZone.style.borderColor = 'var(--vp-border)';
    });

    dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropZone.style.borderColor = 'var(--vp-border)';
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
        handleFileSelected(e.dataTransfer.files[0]);
      }
    });

    fileInput.addEventListener('change', () => {
      if (fileInput.files && fileInput.files[0]) {
        handleFileSelected(fileInput.files[0]);
      }
    });

    removeFileBtn.addEventListener('click', () => {
      clearAudioInput();
    });

    // 4. Nút Nhận dạng ASR
    const transcribeBtn = root.querySelector('#vp-btn-transcribe');
    transcribeBtn.addEventListener('click', () => handleTranscribe());

    // 5. Chỉnh sửa transcript
    const transcriptInput = root.querySelector('#vp-transcript-input');
    transcriptInput.addEventListener('input', () => {
      handleTranscriptChanged();
    });

    // 6. Nút Dịch sang tiếng Tày
    const translateBtn = root.querySelector('#vp-btn-translate');
    translateBtn.addEventListener('click', () => handleTranslate());

    // 7. Nút Sao chép bản dịch
    const copyBtn = root.querySelector('#vp-btn-copy');
    copyBtn.addEventListener('click', () => handleCopyTranslation());
  }

  /**
   * Bắt đầu thu âm qua micro.
   */
  async function handleStartRecording() {
    clearAsrError();
    clearAudioInput();
    updateTimerDisplay(0, limits.max_audio_duration_sec); // Đặt lại đồng hồ về 00:00 ngay khi bắt đầu phiên thu mới

    const support = checkRecordingSupport();
    if (!support.supported) {
      showAsrError(support.reason);
      return;
    }

    const currentSession = ++recordingSessionId;

    try {
      isRecording = true;
      await audioRecorder.start();
      // Nếu phiên này đã bị hủy hoặc thay thế bởi phiên khác trong lúc đợi cấp quyền:
      if (currentSession !== recordingSessionId || !audioRecorder || audioRecorder.state !== 'recording') {
        if (currentSession === recordingSessionId) {
          isRecording = false;
          updateRecordUIState();
        }
        return;
      }
      isRecording = true;
      updateRecordUIState();
    } catch (err) {
      // Nếu phiên đã cũ hoặc bị hủy: hoàn toàn không cập nhật UI hoặc báo lỗi
      if (currentSession !== recordingSessionId) {
        return;
      }
      isRecording = false;
      showAsrError(err.message || 'Không thể bắt đầu thu âm.');
      updateRecordUIState();
    }
  }

  /**
   * Dừng thu âm và nhận tệp WAV hoàn chỉnh.
   */
  async function handleStopRecording() {
    if (!isRecording && (!audioRecorder || (audioRecorder.state !== 'recording' && audioRecorder.state !== 'stopping'))) return;
    isRecording = false;
    updateRecordUIState();

    try {
      const result = await audioRecorder.stop();
      if (result && result.blob) {
        setAudioBlob(result.blob, 'recording.wav');
      }
    } catch (err) {
      showAsrError(`Lỗi xử lý âm thanh thu được: ${err.message}`);
    } finally {
      isRecording = false;
      updateRecordUIState();
    }
  }

  /**
   * Hủy phiên thu âm hiện tại.
   */
  function handleCancelRecording() {
    recordingSessionId++;
    isRecording = false;
    if (audioRecorder) {
      audioRecorder.cancel();
    }
    updateRecordUIState();
    updateTimerDisplay(0, limits.max_audio_duration_sec);
  }

  /**
   * Cập nhật hiển thị đồng hồ thời gian thu âm.
   */
  function updateTimerDisplay(currentSec, maxSec) {
    const timerEl = root.querySelector('#vp-timer');
    if (!timerEl) return;

    const curM = Math.floor(currentSec / 60);
    const curS = Math.floor(currentSec % 60);
    const maxM = Math.floor(maxSec / 60);
    const maxS = Math.floor(maxSec % 60);

    const pad = (n) => String(n).padStart(2, '0');
    timerEl.textContent = `${pad(curM)}:${pad(curS)} / ${pad(maxM)}:${pad(maxS)}`;
  }

  /**
   * Cập nhật trạng thái các nút bấm trong chế độ thu âm.
   */
  function updateRecordUIState() {
    const startBtn = root.querySelector('#vp-btn-start-record');
    const stopBtn = root.querySelector('#vp-btn-stop-record');
    const cancelBtn = root.querySelector('#vp-btn-cancel-record');
    const statusText = root.querySelector('#vp-record-status-text');

    if (!startBtn || !stopBtn || !cancelBtn) return;

    const isBusy = isRecording || (audioRecorder && (audioRecorder.state === 'recording' || audioRecorder.state === 'requesting_permission' || audioRecorder.state === 'stopping'));

    if (isBusy) {
      startBtn.style.display = 'none';
      stopBtn.style.display = 'inline-flex';
      cancelBtn.style.display = 'inline-flex';
      if (statusText) {
        statusText.textContent = audioRecorder?.state === 'requesting_permission'
          ? 'Đang chờ cấp quyền micro...'
          : audioRecorder?.state === 'stopping'
            ? 'Đang hoàn tất xử lý âm thanh...'
            : 'Đang thu âm... (Chạm tối đa sẽ tự động dừng)';
      }
    } else {
      startBtn.style.display = 'inline-flex';
      stopBtn.style.display = 'none';
      cancelBtn.style.display = 'none';
      if (statusText) {
        statusText.textContent = audioBlob ? 'Đã thu âm xong. Sẵn sàng nhận dạng hoặc thu âm lại.' : 'Sẵn sàng thu âm';
      }
    }
  }

  /**
   * Xử lý khi người dùng chọn hoặc thả một tệp WAV.
   */
  function handleFileSelected(file) {
    handleCancelRecording();
    clearAsrError();
    clearAudioInput();

    // 1. Kiểm tra sơ bộ đuôi tệp .wav
    if (!file.name.toLowerCase().endsWith('.wav')) {
      showAsrError('Chỉ chấp nhận tệp có định dạng .wav (WAV PCM 16.000 Hz, 1 kênh mono).');
      return;
    }

    // 2. Kiểm tra sơ bộ dung lượng tệp
    if (file.size > limits.max_audio_file_bytes) {
      const maxMb = (limits.max_audio_file_bytes / (1024 * 1024)).toFixed(0);
      const actualMb = (file.size / (1024 * 1024)).toFixed(1);
      showAsrError(`Dung lượng tệp (${actualMb} MB) vượt quá giới hạn cho phép (${maxMb} MB).`);
      return;
    }

    // Cập nhật thông tin tệp hiển thị
    const fileInfo = root.querySelector('#vp-file-info');
    const fileNameDisplay = root.querySelector('#vp-file-name-display');
    if (fileInfo && fileNameDisplay) {
      fileNameDisplay.textContent = `📄 ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
      fileInfo.style.display = 'flex';
    }

    setAudioBlob(file, file.name);
  }

  /**
   * Gán Blob âm thanh hiện tại và hiển thị audio preview player.
   */
  function setAudioBlob(blob, fileName) {
    audioBlob = blob;
    audioSourceFileName = fileName;

    // Hủy URL cũ nếu có
    if (audioBlobUrl) {
      URL.revokeObjectURL(audioBlobUrl);
      audioBlobUrl = null;
    }

    audioBlobUrl = URL.createObjectURL(blob);

    const previewContainer = root.querySelector('#vp-audio-preview');
    const audioPlayer = root.querySelector('#vp-audio-player');
    if (previewContainer && audioPlayer) {
      audioPlayer.src = audioBlobUrl;
      previewContainer.style.display = 'flex';
    }

    // Khi có âm thanh mới, vô hiệu hóa các kết quả ASR và Dịch cũ
    invalidateAsrAndTranslation();
    updateTranscribeButtonState();
  }

  /**
   * Xóa toàn bộ đầu vào âm thanh hiện tại.
   */
  function clearAudioInput() {
    audioBlob = null;
    if (audioBlobUrl) {
      URL.revokeObjectURL(audioBlobUrl);
      audioBlobUrl = null;
    }

    const previewContainer = root.querySelector('#vp-audio-preview');
    const audioPlayer = root.querySelector('#vp-audio-player');
    if (previewContainer && audioPlayer) {
      audioPlayer.pause();
      audioPlayer.removeAttribute('src');
      audioPlayer.load();
      previewContainer.style.display = 'none';
    }

    const fileInfo = root.querySelector('#vp-file-info');
    const fileInput = root.querySelector('#vp-file-input');
    if (fileInfo) fileInfo.style.display = 'none';
    if (fileInput) fileInput.value = '';

    invalidateAsrAndTranslation();
    updateTranscribeButtonState();
  }

  /**
   * Reset hoàn toàn giai đoạn Dịch và hủy mọi yêu cầu dịch đang chờ.
   * Dùng khi transcript thay đổi, khi ASR mới bắt đầu, hoặc khi audio bị thay thế.
   */
  function resetTranslationStage() {
    translateRevision++;
    if (translateAbortController) {
      translateAbortController.abort();
      translateAbortController = null;
    }
    isTranslating = false;
    lastTranslationResult = null;
    clearTranslationView();
    clearTranslationError();
    updateTranslateButtonState();
  }

  /**
   * Reset giai đoạn ASR và TẤT CẢ các giai đoạn phụ thuộc (transcript, dịch).
   * Dùng khi đổi audio, nạp audio mới, hoặc khi ASR gặp lỗi.
   */
  function resetAsrAndDependentStages() {
    asrRevision++;
    if (asrAbortController) {
      asrAbortController.abort();
      asrAbortController = null;
    }
    isTranscribing = false;
    hasSuccessfulAsr = false;
    lastAsrResult = null;

    const transcriptInput = root.querySelector('#vp-transcript-input');
    if (transcriptInput) {
      transcriptInput.value = '';
    }
    editedTranscript = '';
    transcriptCharCount = 0;

    const charCounter = root.querySelector('#vp-char-counter');
    if (charCounter) {
      charCounter.textContent = `0 / ${limits.max_text_length} ký tự`;
    }

    clearAsrMeta();
    clearAsrError();
    updateTranscribeButtonState();

    // Vô hiệu hóa và hủy toàn bộ công việc/kết quả dịch phụ thuộc ASR cũ
    resetTranslationStage();
  }

  /**
   * Vô hiệu hóa kết quả ASR và Dịch trước đó khi thay đổi âm thanh đầu vào.
   */
  function invalidateAsrAndTranslation() {
    resetAsrAndDependentStages();
  }

  /**
   * Xử lý gọi API nhận dạng giọng nói POST /api/asr/transcribe.
   */
  async function handleTranscribe() {
    if (!audioBlob) return;

    // Kiểm tra trạng thái ASR engine
    if (currentHealth && currentHealth.asr && currentHealth.asr.state !== 'ready') {
      showAsrError(`Hệ thống ASR chưa sẵn sàng (trạng thái: ${currentHealth.asr.state}).`);
      return;
    }

    // Nếu đang transcribing mà được gọi lại (retry):
    if (isTranscribing) {
      asrRevision++;
      if (asrAbortController) {
        asrAbortController.abort();
        asrAbortController = null;
      }
      isTranscribing = false;
    }

    // QUAN TRỌNG (C20 cross-stage): Khi bắt đầu ASR mới, lập tức hủy và vô hiệu hóa
    // TẤT CẢ công việc/kết quả dịch thuộc về transcript cũ!
    resetTranslationStage();

    clearAsrError();
    isTranscribing = true;
    hasSuccessfulAsr = false;
    updateTranscribeButtonState();
    updateTranslateButtonState();

    const thisRevision = ++asrRevision;
    asrAbortController = new AbortController();

    const formData = new FormData();
    formData.append('file', audioBlob, audioSourceFileName || 'audio.wav');
    formData.append('language', 'vi');

    const timeoutMs = timeoutFor ? timeoutFor(currentHealth, 'asr', 5000) : 25000;

    try {
      const response = await apiRequest('/api/asr/transcribe', {
        method: 'POST',
        formData: formData,
        signal: asrAbortController.signal,
        timeoutMs: timeoutMs
      });

      // Kiểm tra stale response
      if (thisRevision !== asrRevision) {
        return;
      }

      displayAsrResult(response);
    } catch (err) {
      if (thisRevision !== asrRevision) {
        return;
      }
      hasSuccessfulAsr = false;
      lastAsrResult = null;

      // Khi ASR lỗi hoặc no-speech: xóa transcript cũ và metadata cũ, vô hiệu bước dịch
      const transcriptInput = root.querySelector('#vp-transcript-input');
      if (transcriptInput) {
        transcriptInput.value = '';
      }
      editedTranscript = '';
      transcriptCharCount = 0;
      const charCounter = root.querySelector('#vp-char-counter');
      if (charCounter) {
        charCounter.textContent = `0 / ${limits.max_text_length} ký tự`;
      }
      clearAsrMeta();
      resetTranslationStage();

      if (err.name === 'AbortError') {
        return;
      }
      showAsrError(formatErrorMessage(err), err.requestId);
    } finally {
      if (thisRevision === asrRevision) {
        isTranscribing = false;
        updateTranscribeButtonState();
        updateTranslateButtonState();
      }
    }
  }

  /**
   * Hiển thị kết quả ASR nhận được vào ô transcript có thể chỉnh sửa.
   */
  function displayAsrResult(response) {
    const transcriptInput = root.querySelector('#vp-transcript-input');
    const mockNotice = root.querySelector('#vp-asr-mock-notice');
    const asrMetaInfo = root.querySelector('#vp-asr-meta-info');

    const transcriptText = response.transcript || '';
    if (transcriptInput) {
      transcriptInput.value = transcriptText;
      transcriptInput.focus();
    }

    // Hiển thị thông báo mock độc lập
    const isMock = Boolean(response.model_metadata?.is_mock);
    if (mockNotice) {
      mockNotice.style.display = isMock ? 'block' : 'none';
    }

    // Hiển thị thông số metadata
    if (asrMetaInfo) {
      const duration = response.duration_sec != null ? `${response.duration_sec.toFixed(1)}s` : '';
      const latency = response.latency_ms != null ? `${Math.round(response.latency_ms)}ms` : '';
      const model = response.model_metadata?.model_id || '';
      asrMetaInfo.textContent = [duration, latency, model].filter(Boolean).join(' • ');
    }

    const normalized = normalizeText(transcriptText);
    editedTranscript = normalized;
    transcriptCharCount = codePointLength(normalized);

    const charCounter = root.querySelector('#vp-char-counter');
    if (charCounter) {
      charCounter.textContent = `${transcriptCharCount} / ${limits.max_text_length} ký tự`;
    }

    hasSuccessfulAsr = Boolean(transcriptText.trim().length > 0);
    updateTranslateButtonState();
  }

  /**
   * Xử lý khi transcript bị người dùng chỉnh sửa.
   * Vô hiệu hóa kết quả dịch cũ và tính lại độ dài ký tự.
   */
  function handleTranscriptChanged() {
    const transcriptInput = root.querySelector('#vp-transcript-input');
    const charCounter = root.querySelector('#vp-char-counter');
    const charCounterContainer = root.querySelector('#vp-char-counter-container');
    const charWarning = root.querySelector('#vp-char-warning');

    if (!transcriptInput) return;

    const rawText = transcriptInput.value;
    const normalized = normalizeText(rawText);
    editedTranscript = normalized;
    transcriptCharCount = codePointLength(normalized);

    // Bất kỳ sửa đổi nào trên transcript đều làm mất hiệu lực kết quả dịch cũ
    translateRevision++;
    if (translateAbortController) {
      translateAbortController.abort();
      translateAbortController = null;
    }
    isTranslating = false;
    clearTranslationView();

    // Nếu người dùng gõ/sửa transcript trong lúc ASR đang chờ:
    // Hủy yêu cầu ASR đó để phản hồi muộn không đè lên nội dung người dùng đang nhập
    if (isTranscribing) {
      asrRevision++;
      if (asrAbortController) {
        asrAbortController.abort();
        asrAbortController = null;
      }
      isTranscribing = false;
      hasSuccessfulAsr = false;
      updateTranscribeButtonState();
    }

    // Cập nhật bộ đếm ký tự
    const maxLen = limits.max_text_length;
    if (charCounter) {
      charCounter.textContent = `${transcriptCharCount} / ${maxLen} ký tự`;
    }

    const isExceeded = transcriptCharCount > maxLen;
    if (charCounterContainer && charWarning) {
      if (isExceeded) {
        charCounterContainer.classList.add('vp-counter-exceeded');
        charWarning.style.display = 'inline';
        charWarning.textContent = `Vượt quá giới hạn (${transcriptCharCount} > ${maxLen} ký tự). Vui lòng rút gọn!`;
      } else {
        charCounterContainer.classList.remove('vp-counter-exceeded');
        charWarning.style.display = 'none';
      }
    }

    updateTranslateButtonState();
  }

  /**
   * Cập nhật trạng thái nút Dịch sang tiếng Tày.
   * Chỉ bật khi:
   * - Có kết quả ASR thành công của tệp âm thanh hiện hành.
   * - Có nội dung transcript hợp lệ (> 0 và <= max_text_length).
   * - Chiều vi-tay được hỗ trợ và sẵn sàng trong translation health.
   * - Không đang trong tiến trình dịch.
   */
  function updateTranslateButtonState() {
    const translateBtn = root.querySelector('#vp-btn-translate');
    if (!translateBtn) return;

    const hasText = transcriptCharCount > 0 && transcriptCharCount <= limits.max_text_length;
    const isViTayReady = checkIsViTayReady();
    const canTranslate = hasSuccessfulAsr && hasText && isViTayReady;

    if (isTranslating) {
      translateBtn.disabled = true;
      translateBtn.innerHTML = '<span class="vp-spinner"></span> Đang dịch sang tiếng Tày...';
    } else {
      translateBtn.disabled = !canTranslate;
      translateBtn.innerHTML = '🌐 Dịch sang tiếng Tày (vi-tay)';
      if (!hasSuccessfulAsr) {
        translateBtn.title = 'Yêu cầu nhận dạng giọng nói từ âm thanh trước khi dịch.';
      } else if (!hasText) {
        translateBtn.title = 'Vui lòng kiểm tra nội dung transcript.';
      } else if (!isViTayReady) {
        translateBtn.title = 'Mô hình dịch chiều vi-tay chưa sẵn sàng hoặc đang nạp.';
      } else {
        translateBtn.title = '';
      }
    }
  }

  /**
   * Kiểm tra chiều vi-tay có sẵn sàng không theo health.
   */
  function checkIsViTayReady() {
    if (!currentHealth || !currentHealth.translation) return false;
    const t = currentHealth.translation;
    return t.state === 'ready' && Array.isArray(t.supported_directions) && t.supported_directions.includes('vi-tay');
  }

  /**
   * Xử lý gọi API dịch POST /api/translate cho snapshot transcript đã sửa.
   */
  async function handleTranslate() {
    if (!hasSuccessfulAsr) {
      showTranslationError('Vui lòng hoàn thành nhận dạng giọng nói trước khi dịch.');
      return;
    }

    // Nếu đang translating mà bị gọi lại (retry):
    if (isTranslating) {
      translateRevision++;
      if (translateAbortController) {
        translateAbortController.abort();
        translateAbortController = null;
      }
      isTranslating = false;
    }

    const transcriptInput = root.querySelector('#vp-transcript-input');
    if (!transcriptInput) return;

    // Snapshot văn bản đã chuẩn hóa tại thời điểm bấm dịch
    const snapshotText = normalizeText(transcriptInput.value);
    const count = codePointLength(snapshotText);

    if (count === 0) {
      showTranslationError('Vui lòng nhập hoặc kiểm tra nội dung transcript trước khi dịch.');
      return;
    }

    if (count > limits.max_text_length) {
      showTranslationError(`Văn bản (${count} ký tự) vượt quá giới hạn cho phép (${limits.max_text_length} ký tự). Vui lòng rút gọn.`);
      return;
    }

    if (!checkIsViTayReady()) {
      showTranslationError('Chiều dịch Việt - Tày (vi-tay) chưa sẵn sàng trên hệ thống.');
      return;
    }

    clearTranslationError();
    isTranslating = true;
    updateTranslateButtonState();

    const thisRevision = ++translateRevision;
    translateAbortController = new AbortController();

    const resultBox = root.querySelector('#vp-translation-result');
    if (resultBox) {
      resultBox.innerHTML = '<span class="vp-spinner" style="border-top-color: var(--vp-primary);"></span> Đang dịch sang tiếng Tày...';
    }

    const timeoutMs = timeoutFor ? timeoutFor(currentHealth, 'translation', 5000) : 20000;

    try {
      const response = await apiRequest('/api/translate', {
        method: 'POST',
        json: {
          text: snapshotText,
          direction: 'vi-tay'
        },
        signal: translateAbortController.signal,
        timeoutMs: timeoutMs
      });

      if (thisRevision !== translateRevision) {
        return;
      }

      lastTranslationResult = response;
      displayTranslationResult(response);
    } catch (err) {
      if (thisRevision !== translateRevision) {
        return;
      }
      if (err.name === 'AbortError') {
        return;
      }
      showTranslationError(formatErrorMessage(err), err.requestId);
      if (resultBox) {
        resultBox.innerHTML = '<span class="vp-result-placeholder">Bản dịch thất bại. Vui lòng thử lại.</span>';
      }
    } finally {
      if (thisRevision === translateRevision) {
        isTranslating = false;
        updateTranslateButtonState();
      }
    }
  }

  /**
   * Hiển thị kết quả bản dịch tiếng Tày.
   */
  function displayTranslationResult(response) {
    const resultBox = root.querySelector('#vp-translation-result');
    const mockNotice = root.querySelector('#vp-trans-mock-notice');
    const transMetaInfo = root.querySelector('#vp-trans-meta-info');
    const copyBtn = root.querySelector('#vp-btn-copy');

    if (resultBox) {
      resultBox.textContent = response.translation || '';
    }

    // Hiển thị nhãn mock độc lập cho dịch
    const isMock = Boolean(response.model_metadata?.is_mock);
    if (mockNotice) {
      mockNotice.style.display = isMock ? 'block' : 'none';
    }

    if (transMetaInfo) {
      const latency = response.latency_ms != null ? `${Math.round(response.latency_ms)}ms` : '';
      const model = response.model_metadata?.model_id || '';
      transMetaInfo.textContent = [latency, model].filter(Boolean).join(' • ');
    }

    if (copyBtn) {
      copyBtn.style.display = 'inline-flex';
    }
  }

  /**
   * Xóa giao diện kết quả dịch.
   */
  function clearTranslationView() {
    const resultBox = root.querySelector('#vp-translation-result');
    const mockNotice = root.querySelector('#vp-trans-mock-notice');
    const transMetaInfo = root.querySelector('#vp-trans-meta-info');
    const copyBtn = root.querySelector('#vp-btn-copy');
    const copiedToast = root.querySelector('#vp-copied-toast');

    if (resultBox) {
      resultBox.innerHTML = '<span class="vp-result-placeholder">Bản dịch tiếng Tày sẽ hiển thị tại đây sau khi bạn xác nhận transcript và bấm Dịch...</span>';
    }
    if (mockNotice) mockNotice.style.display = 'none';
    if (transMetaInfo) transMetaInfo.textContent = '';
    if (copyBtn) copyBtn.style.display = 'none';
    if (copiedToast) copiedToast.style.display = 'none';
    clearTranslationError();
  }

  /**
   * Xóa metadata của ASR.
   */
  function clearAsrMeta() {
    const asrMetaInfo = root.querySelector('#vp-asr-meta-info');
    const asrMockNotice = root.querySelector('#vp-asr-mock-notice');
    if (asrMetaInfo) asrMetaInfo.textContent = '';
    if (asrMockNotice) asrMockNotice.style.display = 'none';
  }

  /**
   * Sao chép kết quả bản dịch vào clipboard.
   */
  async function handleCopyTranslation() {
    if (!lastTranslationResult || !lastTranslationResult.translation) return;

    const textToCopy = lastTranslationResult.translation;
    const toast = root.querySelector('#vp-copied-toast');
    const resultBox = root.querySelector('#vp-translation-result');

    let copySuccess = false;

    if (navigator?.clipboard?.writeText && typeof navigator.clipboard.writeText === 'function') {
      try {
        await navigator.clipboard.writeText(textToCopy);
        copySuccess = true;
      } catch {
        copySuccess = false;
      }
    }

    if (!copySuccess) {
      // Dự phòng bằng document.execCommand và chọn văn bản
      try {
        if (resultBox && window.getSelection) {
          const selection = window.getSelection();
          const range = document.createRange();
          range.selectNodeContents(resultBox);
          selection.removeAllRanges();
          selection.addRange(range);
          copySuccess = document.execCommand && document.execCommand('copy');
        }
      } catch {
        copySuccess = false;
      }
    }

    if (copySuccess) {
      clearTranslationError();
      if (toast) {
        toast.textContent = 'Đã sao chép!';
        toast.style.display = 'inline';
        setTimeout(() => {
          if (toast) toast.style.display = 'none';
        }, 2000);
      }
    } else {
      // Không sao chép thành công: chọn vùng văn bản để người dùng tiện nhấn Ctrl+C
      try {
        if (resultBox && window.getSelection) {
          const selection = window.getSelection();
          const range = document.createRange();
          range.selectNodeContents(resultBox);
          selection.removeAllRanges();
          selection.addRange(range);
        }
      } catch {}
      if (toast) toast.style.display = 'none';
      showTranslationError('Không thể tự động sao chép. Vui lòng bôi đen và nhấn Ctrl+C.');
    }
  }

  /**
   * Cập nhật trạng thái nút Nhận dạng ASR.
   */
  function updateTranscribeButtonState() {
    const transcribeBtn = root.querySelector('#vp-btn-transcribe');
    if (!transcribeBtn) return;

    const hasAudio = audioBlob != null;
    const isAsrReady = currentHealth?.asr?.state === 'ready';

    if (isTranscribing) {
      transcribeBtn.disabled = true;
      transcribeBtn.innerHTML = '<span class="vp-spinner"></span> Đang nhận dạng...';
    } else {
      transcribeBtn.disabled = !hasAudio || !isAsrReady;
      transcribeBtn.innerHTML = '🔍 Nhận dạng giọng nói (ASR)';
      if (hasAudio && !isAsrReady) {
        transcribeBtn.title = 'Engine ASR chưa sẵn sàng.';
      } else {
        transcribeBtn.title = '';
      }
    }
  }

  /**
   * Hiển thị thông báo lỗi ASR.
   */
  function showAsrError(message, requestId = null) {
    const errorBox = root.querySelector('#vp-asr-error');
    const msgEl = root.querySelector('#vp-asr-error-msg');
    const codeEl = root.querySelector('#vp-asr-error-code');

    if (!errorBox || !msgEl) return;

    msgEl.textContent = message;
    if (codeEl) {
      codeEl.textContent = requestId ? `Mã yêu cầu (Request ID): ${requestId}` : '';
      codeEl.style.display = requestId ? 'block' : 'none';
    }
    errorBox.style.display = 'flex';
  }

  function clearAsrError() {
    const errorBox = root.querySelector('#vp-asr-error');
    if (errorBox) errorBox.style.display = 'none';
  }

  /**
   * Hiển thị thông báo lỗi Dịch.
   */
  function showTranslationError(message, requestId = null) {
    const errorBox = root.querySelector('#vp-trans-error');
    const msgEl = root.querySelector('#vp-trans-error-msg');
    const codeEl = root.querySelector('#vp-trans-error-code');

    if (!errorBox || !msgEl) return;

    msgEl.textContent = message;
    if (codeEl) {
      codeEl.textContent = requestId ? `Mã yêu cầu (Request ID): ${requestId}` : '';
      codeEl.style.display = requestId ? 'block' : 'none';
    }
    errorBox.style.display = 'flex';
  }

  function clearTranslationError() {
    const errorBox = root.querySelector('#vp-trans-error');
    if (errorBox) errorBox.style.display = 'none';
  }

  /**
   * Định dạng thông điệp lỗi thân thiện người dùng dựa trên mã lỗi từ API.
   */
  function formatErrorMessage(err) {
    if (!err) return 'Đã xảy ra lỗi không xác định.';
    if (err.message && !err.code) return err.message;

    switch (err.code) {
      case 'NO_SPEECH_DETECTED':
        return 'Không phát hiện lời nói trong đoạn âm thanh. Vui lòng kiểm tra micro và thử lại.';
      case 'AUDIO_TOO_LONG':
        return `Thời lượng âm thanh vượt quá giới hạn tối đa (${limits.max_audio_duration_sec}s).`;
      case 'AUDIO_TOO_LARGE':
        return 'Dung lượng tệp âm thanh vượt quá giới hạn cho phép.';
      case 'AUDIO_INVALID':
        return 'Định dạng tệp WAV không hợp lệ hoặc dữ liệu bị hỏng.';
      case 'AUDIO_UNSUPPORTED_FORMAT':
        return 'Định dạng âm thanh không được hỗ trợ. Chỉ chấp nhận WAV PCM 16.000 Hz, 1 kênh mono, 16-bit.';
      case 'INPUT_TOO_LONG':
      case 'TEXT_TOO_LONG': {
        const unit = err.detail?.limit_unit === 'tokens' ? 'token' : 'ký tự';
        const max = err.detail?.max_allowed || limits.max_text_length;
        return `Văn bản transcript vượt quá giới hạn tối đa (${max} ${unit}). Vui lòng rút gọn trước khi dịch.`;
      }
      case 'UNSUPPORTED_DIRECTION':
        return 'Chiều dịch này hiện không được hệ thống hỗ trợ.';
      case 'MODEL_NOT_READY':
        return 'Mô hình xử lý chưa sẵn sàng. Vui lòng chờ trong giây lát.';
      case 'SERVICE_OVERLOADED':
        return 'Máy chủ đang quá tải. Vui lòng thử lại sau vài giây.';
      case 'GATEWAY_TIMEOUT':
        return 'Yêu cầu xử lý bị quá thời gian cho phép (timeout).';
      default:
        return err.message || 'Lỗi xử lý yêu cầu.';
    }
  }

  /**
   * Cập nhật thông tin Health từ bên ngoài (§4.5).
   * @param {Object} health
   */
  function setHealth(health) {
    if (!health) return;
    currentHealth = health;

    // Cập nhật limits nếu có
    if (health.limits) {
      limits = { ...limits, ...health.limits };

      const durationLimitEl = root.querySelector('#vp-limit-duration');
      const sizeLimitEl = root.querySelector('#vp-limit-size');
      if (durationLimitEl) durationLimitEl.textContent = String(limits.max_audio_duration_sec);
      if (sizeLimitEl) {
        sizeLimitEl.textContent = String((limits.max_audio_file_bytes / (1024 * 1024)).toFixed(0));
      }

      // Tạo lại recorder instance nếu maxDurationSec thay đổi
      if (audioRecorder && audioRecorder.maxDurationSec !== limits.max_audio_duration_sec) {
        handleCancelRecording();
        createRecorderInstance();
      }

      updateTimerDisplay(0, limits.max_audio_duration_sec);
    }

    // Cập nhật Badges trạng thái
    const asrBadge = root.querySelector('#vp-badge-asr');
    const transBadge = root.querySelector('#vp-badge-trans');

    if (asrBadge && health.asr) {
      const a = health.asr;
      asrBadge.className = 'vp-badge';
      if (a.state === 'ready') {
        if (a.is_mock) {
          asrBadge.classList.add('vp-badge-mock');
          asrBadge.textContent = 'ASR: Mô phỏng (Mock)';
        } else {
          asrBadge.classList.add('vp-badge-ready');
          asrBadge.textContent = 'ASR: Sẵn sàng';
        }
      } else {
        asrBadge.classList.add('vp-badge-disabled');
        asrBadge.textContent = `ASR: ${a.state}`;
      }
    }

    if (transBadge && health.translation) {
      const t = health.translation;
      transBadge.className = 'vp-badge';
      if (t.state === 'ready') {
        if (t.is_mock) {
          transBadge.classList.add('vp-badge-mock');
          transBadge.textContent = 'Dịch: Mô phỏng (Mock)';
        } else {
          transBadge.classList.add('vp-badge-ready');
          transBadge.textContent = 'Dịch: Sẵn sàng';
        }
      } else {
        transBadge.classList.add('vp-badge-disabled');
        transBadge.textContent = `Dịch: ${t.state}`;
      }
    }

    updateTranscribeButtonState();
    updateTranslateButtonState();
  }

  /**
   * Gọi khi người dùng chuyển sang tab khác.
   * Dừng thu âm ngay lập tức, hủy các request đang bay và chống kết quả muộn.
   */
  function deactivate() {
    asrRevision++;
    translateRevision++;

    handleCancelRecording();

    if (asrAbortController) {
      asrAbortController.abort();
      asrAbortController = null;
    }

    if (translateAbortController) {
      translateAbortController.abort();
      translateAbortController = null;
    }

    isTranscribing = false;
    isTranslating = false;
    updateTranscribeButtonState();
    updateTranslateButtonState();
  }

  /**
   * Hủy vĩnh viễn toàn bộ module voice.
   */
  function destroy() {
    deactivate();

    window.removeEventListener('pagehide', onPageHide);

    if (audioRecorder) {
      audioRecorder.destroy();
      audioRecorder = null;
    }

    if (audioBlobUrl) {
      URL.revokeObjectURL(audioBlobUrl);
      audioBlobUrl = null;
    }

    root.innerHTML = '';
  }

  // Khởi tạo hiển thị thời gian ban đầu và trạng thái các nút
  updateTimerDisplay(0, limits.max_audio_duration_sec);
  updateTranscribeButtonState();
  updateTranslateButtonState();
  updateRecordUIState();

  return {
    setHealth,
    deactivate,
    destroy
  };
}
