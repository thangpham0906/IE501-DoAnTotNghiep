/**
 * Quản lý giao diện và luồng dịch văn bản hai chiều theo §6.1–6.2.
 * - Bảo vệ stale response bằng revision/snapshot.
 * - Swap đảo chiều an toàn (chỉ hoán đổi khi kết quả khớp snapshot, không tự gửi).
 * - Đếm ký tự Unicode code point theo NFC và tập 25 White_Space.
 * - Hiển thị metadata, thời gian xử lý và nhãn mô phỏng rõ ràng.
 * - Đảm bảo an toàn XSS (dùng textContent / value).
 */

export class TranslationController {
  /**
   * Khởi tạo bộ điều khiển dịch văn bản.
   *
   * @param {object} elements - Các phần tử DOM giao diện
   * @param {object} helpers - Các hàm tiện ích { apiRequest, timeoutFor, normalizeText, codePointLength }
   */
  constructor(elements, helpers) {
    this.elements = elements;
    this.helpers = helpers;

    this.health = null;
    this.models = [];
    this.currentDirection = 'vi-tay';
    this.maxTextLength = 1000;

    this.isTranslating = false;
    this.currentRevision = 0;
    this.activeAbortController = null;
    this.activeSnapshot = null;

    // Snapshot bản dịch hoàn tất gần nhất { sourceText, direction, translationText }
    this.lastCompletedSnapshot = null;

    this._bindEvents();
    this.updateDirectionLabels();
    this.updateCharCount();
    this.updateTranslateButtonState();
  }

  /**
   * Đăng ký các sự kiện tương tác của người dùng.
   */
  _bindEvents() {
    // 1. Nhập liệu nguồn: cập nhật đếm ký tự, kiểm tra tính hợp lệ và hủy request cũ nếu có
    if (this.elements.sourceText) {
      this.elements.sourceText.addEventListener('input', () => {
        this.invalidatePendingRequest();
        this.checkSourceChanged();
        this.updateCharCount();
        this.updateTranslateButtonState();
      });

      // Phím tắt Ctrl+Enter hoặc Cmd+Enter để dịch nhanh
      this.elements.sourceText.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
          e.preventDefault();
          if (this.canTranslate()) {
            this.translate();
          }
        }
      });
    }

    // 2. Chọn chiều dịch
    if (this.elements.directionSelect) {
      this.elements.directionSelect.addEventListener('change', (e) => {
        const newDirection = e.target.value;
        if (newDirection !== this.currentDirection) {
          this.invalidatePendingRequest();
          this.currentDirection = newDirection;
          // Đổi chiều làm mất hiệu lực kết quả và metadata của chiều cũ
          if (this.elements.targetText) {
            this.elements.targetText.value = '';
          }
          this.lastCompletedSnapshot = null;
          this.clearMetadata();
          this.clearError();
          this.updateDirectionLabels();
          this.updateTranslateButtonState();
        }
      });
    }

    // 3. Nút đảo chiều (Swap)
    if (this.elements.swapBtn) {
      this.elements.swapBtn.addEventListener('click', () => {
        this.handleSwap();
      });
    }

    // 4. Nút Dịch
    if (this.elements.translateBtn) {
      this.elements.translateBtn.addEventListener('click', () => {
        if (this.canTranslate()) {
          this.translate();
        }
      });
    }

    // 5. Nút Xóa nguồn
    if (this.elements.clearBtn) {
      this.elements.clearBtn.addEventListener('click', () => {
        this.handleClear();
      });
    }

    // 6. Nút Sao chép kết quả
    if (this.elements.copyBtn) {
      this.elements.copyBtn.addEventListener('click', () => {
        this.handleCopy();
      });
    }
  }

  /**
   * Cập nhật thông tin Health từ /api/health.
   */
  setHealth(health) {
    this.health = health;

    // Cập nhật giới hạn độ dài nếu có trong limits
    if (health?.limits?.max_text_length) {
      this.maxTextLength = Number(health.limits.max_text_length) || 1000;
    }

    // Kiểm tra chiều dịch hiện tại có được hỗ trợ hay không
    const supported = health?.translation?.supported_directions || [];
    if (supported.length > 0 && !supported.includes(this.currentDirection)) {
      this.currentDirection = supported[0];
      if (this.elements.directionSelect) {
        this.elements.directionSelect.value = this.currentDirection;
      }
      this.updateDirectionLabels();
    }

    this.updateCharCount();
    this.updateTranslateButtonState();
  }

  /**
   * Cập nhật danh sách Models từ /api/models.
   */
  setModels(modelsData) {
    this.models = modelsData?.models || [];
    this.updateModelInfoDisplay();
  }

  /**
   * Hủy bỏ yêu cầu đang xử lý dở dang khi người dùng chỉnh sửa hoặc đổi chiều.
   */
  invalidatePendingRequest() {
    if (this.isTranslating) {
      this.currentRevision++;
      if (this.activeAbortController) {
        this.activeAbortController.abort();
        this.activeAbortController = null;
      }
      this.isTranslating = false;
      this.activeSnapshot = null;
      this.hideLoading();
    }
  }

  /**
   * Kiểm tra và làm mất hiệu lực kết quả dịch đã hoàn tất nếu nội dung nguồn hoặc chiều dịch thay đổi.
   */
  checkSourceChanged() {
    const raw = this.elements.sourceText ? this.elements.sourceText.value : '';
    const currentNormalized = this.helpers.normalizeText(raw);
    if (
      this.lastCompletedSnapshot &&
      (this.lastCompletedSnapshot.sourceText !== currentNormalized ||
        this.lastCompletedSnapshot.direction !== this.currentDirection)
    ) {
      if (this.elements.targetText) {
        this.elements.targetText.value = '';
      }
      this.lastCompletedSnapshot = null;
      this.clearMetadata();
      this.clearError();
    }
  }

  /**
   * Kiểm tra điều kiện có thể bấm nút Dịch.
   * "Chỉ bật nút dịch với engine/direction sẵn sàng, input hợp lệ và không đang gửi."
   */
  canTranslate() {
    if (this.isTranslating) return false;

    // Kiểm tra trạng thái engine dịch
    const engineState = this.health?.translation?.state;
    if (engineState !== 'ready') return false;

    // Kiểm tra chiều dịch được hỗ trợ
    const supportedDirs = this.health?.translation?.supported_directions || [];
    if (!supportedDirs.includes(this.currentDirection)) return false;

    // Kiểm tra độ dài văn bản sau chuẩn hóa NFC + trim 25 khoảng trắng
    const raw = this.elements.sourceText ? this.elements.sourceText.value : '';
    const normalized = this.helpers.normalizeText(raw);
    const count = this.helpers.codePointLength(normalized);

    return count >= 1 && count <= this.maxTextLength;
  }

  /**
   * Cập nhật trạng thái bật/tắt của nút Dịch.
   */
  updateTranslateButtonState() {
    if (!this.elements.translateBtn) return;

    const enabled = this.canTranslate();
    this.elements.translateBtn.disabled = !enabled;

    // Cập nhật tooltip hoặc lý do nếu bị vô hiệu
    let reason = '';
    const raw = this.elements.sourceText ? this.elements.sourceText.value : '';
    const normalized = this.helpers.normalizeText(raw);
    const count = this.helpers.codePointLength(normalized);

    if (this.isTranslating) {
      reason = 'Đang trong quá trình dịch yêu cầu trước...';
    } else if (this.health?.translation?.state !== 'ready') {
      const state = this.health?.translation?.state || 'chưa tải';
      reason = `Engine dịch chưa sẵn sàng (trạng thái: ${state}).`;
    } else if (count === 0) {
      reason = 'Vui lòng nhập văn bản cần dịch.';
    } else if (count > this.maxTextLength) {
      reason = `Văn bản vượt quá giới hạn ${this.maxTextLength} ký tự.`;
    }

    if (reason && !enabled) {
      this.elements.translateBtn.setAttribute('title', reason);
    } else {
      this.elements.translateBtn.removeAttribute('title');
    }
  }

  /**
   * Đếm ký tự Unicode code point và hiển thị trên giao diện.
   */
  updateCharCount() {
    if (!this.elements.charCount || !this.elements.sourceText) return;

    const raw = this.elements.sourceText.value;
    const normalized = this.helpers.normalizeText(raw);
    const count = this.helpers.codePointLength(normalized);

    this.elements.charCount.textContent = `${count} / ${this.maxTextLength} ký tự`;

    if (count > this.maxTextLength) {
      this.elements.charCount.classList.add('char-count--exceeded');
      this.elements.charCount.setAttribute(
        'aria-label',
        `Cảnh báo: Đã nhập ${count} ký tự, vượt quá giới hạn tối đa ${this.maxTextLength} ký tự.`
      );
    } else {
      this.elements.charCount.classList.remove('char-count--exceeded');
      this.elements.charCount.setAttribute(
        'aria-label',
        `Đã nhập ${count} trên tổng số tối đa ${this.maxTextLength} ký tự.`
      );
    }
  }

  /**
   * Cập nhật nhãn Tiếng Việt / Tiếng Tày cho ô nguồn và ô đích.
   */
  updateDirectionLabels() {
    const isViTay = this.currentDirection === 'vi-tay';
    if (this.elements.sourceLabel) {
      this.elements.sourceLabel.textContent = isViTay ? 'Tiếng Việt' : 'Tiếng Tày';
    }
    if (this.elements.targetLabel) {
      this.elements.targetLabel.textContent = isViTay ? 'Tiếng Tày' : 'Tiếng Việt';
    }
    if (this.elements.sourceText) {
      this.elements.sourceText.placeholder = isViTay
        ? 'Nhập văn bản tiếng Việt cần dịch...'
        : 'Nhập văn bản tiếng Tày cần dịch...';
    }
  }

  /**
   * Xử lý thao tác Đảo chiều (Swap).
   * "Swap chỉ dùng kết quả khớp snapshot; nếu không giữ nguồn, đổi chiều, xóa kết quả và không tự gửi."
   */
  handleSwap() {
    this.invalidatePendingRequest();

    const raw = this.elements.sourceText ? this.elements.sourceText.value : '';
    const currentNormalized = this.helpers.normalizeText(raw);

    // Kiểm tra xem kết quả hiện tại có khớp với snapshot nguồn và chiều dịch vừa dịch xong không
    const isMatched =
      this.lastCompletedSnapshot &&
      this.lastCompletedSnapshot.sourceText === currentNormalized &&
      this.lastCompletedSnapshot.direction === this.currentDirection &&
      Boolean(this.lastCompletedSnapshot.translationText);

    const oppositeDirection = this.currentDirection === 'vi-tay' ? 'tay-vi' : 'vi-tay';

    if (isMatched) {
      // Có bản dịch khớp nguồn: hoán đổi hai ô
      const oldSource = this.lastCompletedSnapshot.sourceText;
      const oldTranslation = this.lastCompletedSnapshot.translationText;

      this.currentDirection = oppositeDirection;
      if (this.elements.directionSelect) {
        this.elements.directionSelect.value = oppositeDirection;
      }

      this.elements.sourceText.value = oldTranslation;
      if (this.elements.targetText) {
        this.elements.targetText.value = oldSource;
      }

      // Snapshot hoán đổi không được gán timing/model của phép suy luận chiều cũ cho phép dịch chiều mới.
      this.clearMetadata();
      this.clearError();

      // Lưu lại snapshot đảo để người dùng có thể đổi ngược lại nếu muốn mà không mang metadata cũ
      this.lastCompletedSnapshot = {
        sourceText: this.helpers.normalizeText(oldTranslation),
        direction: oppositeDirection,
        translationText: oldSource,
      };

      this.updateDirectionLabels();
      this.updateCharCount();
      this.updateTranslateButtonState();
      // "và không tự gửi" -> không gọi translate()
    } else {
      // Chưa có kết quả hợp lệ khớp nguồn: giữ nguyên văn bản nguồn, đổi chiều, xóa kết quả cũ
      this.currentDirection = oppositeDirection;
      if (this.elements.directionSelect) {
        this.elements.directionSelect.value = oppositeDirection;
      }

      if (this.elements.targetText) {
        this.elements.targetText.value = '';
      }
      this.lastCompletedSnapshot = null;
      this.clearMetadata();
      this.clearError();

      this.updateDirectionLabels();
      this.updateCharCount();
      this.updateTranslateButtonState();
      // "và không tự gửi" -> không gọi translate()
    }
  }

  /**
   * Xóa nội dung văn bản nguồn và kết quả.
   */
  handleClear() {
    this.invalidatePendingRequest();
    if (this.elements.sourceText) {
      this.elements.sourceText.value = '';
      this.elements.sourceText.focus();
    }
    if (this.elements.targetText) {
      this.elements.targetText.value = '';
    }
    this.lastCompletedSnapshot = null;
    this.clearMetadata();
    this.clearError();
    this.updateCharCount();
    this.updateTranslateButtonState();
  }

  /**
   * Sao chép kết quả dịch vào Clipboard.
   * "Copy có thông báo thành công/thất bại; vẫn cho chọn văn bản nếu clipboard API không khả dụng."
   */
  async handleCopy() {
    if (!this.elements.targetText) return;
    const text = this.elements.targetText.value;
    if (!text) return;

    let copySuccess = false;

    if (navigator?.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(text);
        copySuccess = true;
      } catch {
        copySuccess = false;
      }
    }

    // Dự phòng khi Clipboard API không khả dụng hoặc bị từ chối quyền
    if (!copySuccess) {
      try {
        this.elements.targetText.select();
        copySuccess = document.execCommand('copy');
      } catch {
        copySuccess = false;
      }
    }

    if (copySuccess) {
      this.showCopyFeedback('Đã sao chép vào bộ nhớ tạm!', false);
    } else {
      this.showCopyFeedback('Không thể tự động sao chép. Vui lòng bôi đen và nhấn Ctrl+C.', true);
    }
  }

  /**
   * Hiển thị thông báo phản hồi thao tác sao chép.
   */
  showCopyFeedback(message, isError) {
    if (!this.elements.copyFeedback) return;
    this.elements.copyFeedback.textContent = message;
    this.elements.copyFeedback.className = isError
      ? 'copy-feedback copy-feedback--error'
      : 'copy-feedback copy-feedback--success';

    clearTimeout(this._copyTimer);
    this._copyTimer = setTimeout(() => {
      if (this.elements.copyFeedback) {
        this.elements.copyFeedback.textContent = '';
        this.elements.copyFeedback.className = 'copy-feedback';
      }
    }, 3000);
  }

  /**
   * Gửi yêu cầu dịch văn bản tới /api/translate.
   */
  async translate() {
    if (!this.canTranslate()) return;

    const raw = this.elements.sourceText.value;
    const normalized = this.helpers.normalizeText(raw);

    this.currentRevision++;
    const revision = this.currentRevision;

    const snapshot = {
      revision,
      text: normalized,
      direction: this.currentDirection,
    };
    this.activeSnapshot = snapshot;

    this.activeAbortController = new AbortController();
    this.isTranslating = true;

    this.showLoading();
    this.clearError();
    this.clearMetadata();
    // Xóa kết quả cũ khi bắt đầu yêu cầu mới để tránh hiển thị kết quả cũ nếu request thất bại
    if (this.elements.targetText) {
      this.elements.targetText.value = '';
    }
    this.lastCompletedSnapshot = null;
    this.updateTranslateButtonState();

    const timeoutMs = this.helpers.timeoutFor(this.health, 'translation', 5000);

    try {
      const res = await this.helpers.apiRequest('/api/translate', {
        method: 'POST',
        json: {
          text: normalized,
          direction: this.currentDirection,
        },
        signal: this.activeAbortController.signal,
        timeoutMs,
      });

      // BẢO VỆ STALE RESPONSE:
      // Kiểm tra revision, chiều dịch và văn bản nguồn hiện hành
      const currentSource = this.helpers.normalizeText(this.elements.sourceText.value);
      if (
        snapshot.revision !== this.currentRevision ||
        snapshot.direction !== this.currentDirection ||
        snapshot.text !== currentSource
      ) {
        // Phản hồi cũ/lệch snapshot: loại bỏ, không ghi đè UI
        return;
      }

      // Hiển thị kết quả bằng textContent/value an toàn
      const translation = res.translation || '';
      if (this.elements.targetText) {
        this.elements.targetText.value = translation;
      }

      // Lưu snapshot hoàn tất cho tính năng Đảo chiều (Swap)
      this.lastCompletedSnapshot = {
        sourceText: normalized,
        direction: this.currentDirection,
        translationText: translation,
      };

      this.renderMetadata(res);
      this.clearError();
    } catch (err) {
      // Nếu revision đã đổi thì bỏ qua lỗi của request cũ
      if (snapshot.revision !== this.currentRevision) {
        return;
      }

      // Nếu người dùng chủ động hủy (do edit hoặc clear) thì không báo lỗi
      if (err.name === 'AbortError') {
        return;
      }

      this.showError(err);
    } finally {
      if (snapshot.revision === this.currentRevision) {
        this.isTranslating = false;
        this.activeAbortController = null;
        this.activeSnapshot = null;
        this.hideLoading();
        this.updateTranslateButtonState();
      }
    }
  }

  /**
   * Hiển thị trạng thái đang xử lý dịch.
   */
  showLoading() {
    if (this.elements.translateSpinner) {
      this.elements.translateSpinner.classList.remove('hidden');
    }
    if (this.elements.translateStatusText) {
      this.elements.translateStatusText.textContent = 'Đang dịch...';
    }
  }

  /**
   * Ẩn trạng thái đang xử lý dịch.
   */
  hideLoading() {
    if (this.elements.translateSpinner) {
      this.elements.translateSpinner.classList.add('hidden');
    }
    if (this.elements.translateStatusText) {
      this.elements.translateStatusText.textContent = '';
    }
  }

  /**
   * Hiển thị thông báo lỗi lên banner.
   */
  showError(err) {
    if (!this.elements.errorBanner) return;

    let msg = err.message || 'Đã xảy ra lỗi không xác định.';
    if (err.code === 'INPUT_TOO_LONG' && err.detail) {
      const current = err.detail.current_length;
      const max = err.detail.max_allowed;
      const unit = err.detail.limit_unit === 'tokens' ? 'token' : 'ký tự';
      if (current !== undefined && max !== undefined) {
        msg = `Văn bản vượt quá giới hạn (hiện tại: ${current}, tối đa: ${max} ${unit}).`;
      } else {
        msg = `Văn bản vượt quá giới hạn ${unit} cho phép.`;
      }
    }

    if (err.requestId) {
      msg += ` (Mã yêu cầu: ${err.requestId})`;
    }

    this.elements.errorBanner.textContent = msg;
    this.elements.errorBanner.classList.remove('hidden');
  }

  /**
   * Xóa thông báo lỗi.
   */
  clearError() {
    if (!this.elements.errorBanner) return;
    this.elements.errorBanner.textContent = '';
    this.elements.errorBanner.classList.add('hidden');
  }

  /**
   * Hiển thị thông tin metadata, timing và nhãn mô phỏng.
   */
  renderMetadata(res) {
    if (!this.elements.metaContainer) return;

    const meta = res.model_metadata || {};
    const latency = typeof res.latency_ms === 'number' ? res.latency_ms : 0;
    const queue = typeof res.queue_ms === 'number' ? res.queue_ms : 0;
    const isMock = Boolean(meta.is_mock);

    // Hiển thị nhãn Mock nếu có
    if (this.elements.metaMockBadge) {
      if (isMock) {
        this.elements.metaMockBadge.textContent = 'MÔ PHỎNG';
        this.elements.metaMockBadge.classList.remove('hidden');
      } else {
        this.elements.metaMockBadge.classList.add('hidden');
      }
    }

    // Hiển thị chi tiết model và checkpoint
    if (this.elements.metaModelInfo) {
      const modelId = meta.model_id || 'unknown';
      const version = meta.checkpoint_version || meta.model_version || '';
      this.elements.metaModelInfo.textContent = version ? `${modelId} (${version})` : modelId;
    }

    // Hiển thị thời gian
    if (this.elements.metaTiming) {
      this.elements.metaTiming.textContent = `Độ trễ: ${latency} ms | Hàng đợi: ${queue} ms`;
    }

    this.elements.metaContainer.classList.remove('hidden');
  }

  /**
   * Xóa hiển thị metadata.
   */
  clearMetadata() {
    if (!this.elements.metaContainer) return;
    this.elements.metaContainer.classList.add('hidden');
    if (this.elements.metaMockBadge) {
      this.elements.metaMockBadge.classList.add('hidden');
    }
    if (this.elements.metaModelInfo) {
      this.elements.metaModelInfo.textContent = '';
    }
    if (this.elements.metaTiming) {
      this.elements.metaTiming.textContent = '';
    }
  }

  /**
   * Cập nhật thông tin mô hình hiển thị trên thanh điều khiển.
   */
  updateModelInfoDisplay() {
    if (!this.elements.activeModelBadge) return;
    const activeModel = this.models.find((m) => m.is_default) || this.models[0];
    if (activeModel) {
      this.elements.activeModelBadge.textContent = activeModel.name || activeModel.id;
    }
  }

  /**
   * Dọn dẹp tài nguyên khi hủy bộ điều khiển.
   */
  destroy() {
    this.invalidatePendingRequest();
    clearTimeout(this._copyTimer);
  }
}
