/**
 * app.js - Điểm khởi nhập chính của giao diện Web Demo (§6.1, §6.2, §6.3).
 * Quản lý khởi tạo hệ thống, chuyển đổi tab, đồng bộ health/models và dọn dẹp vòng đời.
 */

import { initVoice } from './voice.js';
import { TranslationController } from './translation.js';
import { apiRequest, timeoutFor } from './api_client.js';
import { normalizeText, codePointLength } from './text_utils.js';

document.addEventListener('DOMContentLoaded', () => {
  // 1. Thu thập các phần tử DOM phục vụ dịch văn bản
  const translationElements = {
    sourceText: document.getElementById('source-text'),
    targetText: document.getElementById('target-text'),
    sourceLabel: document.getElementById('source-label'),
    targetLabel: document.getElementById('target-label'),
    directionSelect: document.getElementById('direction-select'),
    charCount: document.getElementById('char-count'),
    translateBtn: document.getElementById('btn-translate'),
    swapBtn: document.getElementById('btn-swap'),
    clearBtn: document.getElementById('btn-clear-source'),
    copyBtn: document.getElementById('btn-copy-target'),
    copyFeedback: document.getElementById('copy-feedback'),
    translateSpinner: document.getElementById('translate-spinner'),
    translateStatusText: document.getElementById('translate-status-text'),
    errorBanner: document.getElementById('error-banner'),
    metaContainer: document.getElementById('meta-container'),
    metaMockBadge: document.getElementById('meta-mock-badge'),
    metaModelInfo: document.getElementById('meta-model-info'),
    metaTiming: document.getElementById('meta-timing'),
    activeModelBadge: document.getElementById('active-model-badge'),
  };

  // 2. Khởi tạo bộ điều khiển dịch văn bản
  const translation = new TranslationController(translationElements, {
    apiRequest,
    timeoutFor,
    normalizeText,
    codePointLength,
  });

  // 3. Khởi tạo module giọng nói (Task B)
  const voiceRoot = document.getElementById('voice-panel');
  let voiceInstance = null;

  if (voiceRoot && typeof initVoice === 'function') {
    try {
      voiceInstance = initVoice(voiceRoot, {
        apiRequest,
        timeoutFor,
        normalizeText,
        codePointLength,
      });
    } catch (err) {
      console.error('Lỗi khởi tạo module giọng nói (voice.js):', err);
    }
  }

  // 4. Quản lý chuyển đổi Tab (Văn bản <-> Giọng nói)
  const tabText = document.getElementById('tab-text');
  const tabVoice = document.getElementById('tab-voice');
  const panelText = document.getElementById('panel-text');

  function switchTab(target) {
    if (target === 'voice') {
      if (tabText) {
        tabText.classList.remove('active');
        tabText.setAttribute('aria-selected', 'false');
      }
      if (tabVoice) {
        tabVoice.classList.add('active');
        tabVoice.setAttribute('aria-selected', 'true');
      }
      if (panelText) panelText.hidden = true;
      if (voiceRoot) voiceRoot.hidden = false;
    } else {
      // Khi rời khỏi tab giọng nói, gọi deactivate() để tắt mic và dọn dẹp tài nguyên âm thanh
      if (voiceInstance && typeof voiceInstance.deactivate === 'function') {
        try {
          voiceInstance.deactivate();
        } catch (err) {
          console.warn('Lỗi deactivate voice:', err);
        }
      }

      if (tabVoice) {
        tabVoice.classList.remove('active');
        tabVoice.setAttribute('aria-selected', 'false');
      }
      if (tabText) {
        tabText.classList.add('active');
        tabText.setAttribute('aria-selected', 'true');
      }
      if (voiceRoot) voiceRoot.hidden = true;
      if (panelText) panelText.hidden = false;
    }
  }

  if (tabText) {
    tabText.addEventListener('click', () => switchTab('text'));
  }
  if (tabVoice) {
    tabVoice.addEventListener('click', () => switchTab('voice'));
  }

  // 5. Quản lý vòng đời trang: dọn dẹp khi pagehide hoặc beforeunload
  function cleanupApp() {
    if (voiceInstance && typeof voiceInstance.destroy === 'function') {
      try {
        voiceInstance.destroy();
      } catch (err) {
        console.warn('Lỗi destroy voice:', err);
      }
    }
    if (translation && typeof translation.destroy === 'function') {
      translation.destroy();
    }
  }

  window.addEventListener('pagehide', cleanupApp);
  window.addEventListener('beforeunload', cleanupApp);

  // 6. Tải trạng thái Health và danh sách Models từ API
  const engineStatusTrans = document.getElementById('engine-status-translation');
  const engineStatusAsr = document.getElementById('engine-status-asr');
  const globalMockBadge = document.getElementById('global-mock-badge');
  const btnRefresh = document.getElementById('btn-refresh-status');

  async function loadHealthAndModels() {
    if (btnRefresh) {
      btnRefresh.disabled = true;
      btnRefresh.textContent = '⟳ Đang tải...';
    }

    try {
      // Tải GET /api/health
      const health = await apiRequest('/api/health');

      // Chuyển health cho dịch văn bản và giọng nói
      translation.setHealth(health);
      if (voiceInstance && typeof voiceInstance.setHealth === 'function') {
        voiceInstance.setHealth(health);
      }

      // Cập nhật nhãn trạng thái Engine dịch
      if (engineStatusTrans) {
        const tState = health?.translation?.state || 'unknown';
        engineStatusTrans.className = 'badge';
        if (tState === 'ready') {
          engineStatusTrans.classList.add('badge--ready');
          engineStatusTrans.textContent = 'Dịch: Sẵn sàng';
        } else if (tState === 'loading') {
          engineStatusTrans.classList.add('badge--loading');
          engineStatusTrans.textContent = 'Dịch: Đang tải...';
        } else {
          engineStatusTrans.classList.add('badge--failed');
          engineStatusTrans.textContent = `Dịch: ${tState}`;
        }
      }

      // Cập nhật nhãn trạng thái Engine ASR
      if (engineStatusAsr) {
        const aState = health?.asr?.state || 'unknown';
        engineStatusAsr.className = 'badge';
        if (aState === 'ready') {
          engineStatusAsr.classList.add('badge--ready');
          engineStatusAsr.textContent = 'ASR: Sẵn sàng';
        } else if (aState === 'loading') {
          engineStatusAsr.classList.add('badge--loading');
          engineStatusAsr.textContent = 'ASR: Đang tải...';
        } else if (health?.asr?.engine_type === 'disabled') {
          engineStatusAsr.classList.add('badge--model');
          engineStatusAsr.textContent = 'ASR: Tắt';
        } else {
          engineStatusAsr.classList.add('badge--failed');
          engineStatusAsr.textContent = `ASR: ${aState}`;
        }
      }

      // Hiển thị nhãn MÔ PHỎNG chung nếu có ít nhất một engine mock
      if (globalMockBadge) {
        const hasMock = Boolean(health?.translation?.is_mock || health?.asr?.is_mock);
        if (hasMock) {
          globalMockBadge.classList.remove('hidden');
        } else {
          globalMockBadge.classList.add('hidden');
        }
      }

      // Tải GET /api/models
      try {
        const modelsData = await apiRequest('/api/models');
        translation.setModels(modelsData);
      } catch (mErr) {
        console.warn('Không thể nạp danh sách models:', mErr);
      }
    } catch (err) {
      console.error('Lỗi khi tải trạng thái máy chủ:', err);
      if (engineStatusTrans) {
        engineStatusTrans.className = 'badge badge--failed';
        engineStatusTrans.textContent = 'Dịch: Mất kết nối';
      }
      if (engineStatusAsr) {
        engineStatusAsr.className = 'badge badge--failed';
        engineStatusAsr.textContent = 'ASR: Mất kết nối';
      }
    } finally {
      if (btnRefresh) {
        btnRefresh.disabled = false;
        btnRefresh.textContent = '⟳ Làm mới';
      }
    }
  }

  if (btnRefresh) {
    btnRefresh.addEventListener('click', () => {
      loadHealthAndModels();
    });
  }

  // Khởi động nạp dữ liệu lần đầu
  loadHealthAndModels();
});
