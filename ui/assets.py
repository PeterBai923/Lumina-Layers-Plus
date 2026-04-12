# -*- coding: utf-8 -*-
"""Lumina Studio - CSS / JS string constants used by the UI layer."""

DEBOUNCE_JS = """
<script>
(function () {
  if (window.__luminaBlurTriggerInit) return;
  window.__luminaBlurTriggerInit = true;

  function setupBlurTrigger() {
    var sliders = document.querySelectorAll('.compact-row input[type="number"]');
    if (!sliders.length) return 0;
    var boundCount = 0;
    sliders.forEach(function (input) {
      if (input.__blur_bound) return;
      input.__blur_bound = true;
      boundCount += 1;
      var lastValue = input.value;
      // Programmatic updates (e.g. selecting another image) may change value
      // without touching this closure; refresh baseline on user focus.
      input.addEventListener('focus', function () {
        lastValue = input.value;
      });
      // 捕获阶段拦截所有 input 事件，阻止 Gradio 立即处理
      input.addEventListener('input', function (e) {
        if (input.__dispatching) return;
        e.stopImmediatePropagation();
      }, true);
      // 失焦时，如果值有变化且在合法范围内，才触发一次 input 事件
      input.addEventListener('blur', function () {
        var val = parseFloat(input.value);
        if (input.value !== lastValue && !isNaN(val)) {
          var min = parseFloat(input.min);
          var max = parseFloat(input.max);
          if (!isNaN(min) && val < min) { input.value = min; val = min; }
          if (!isNaN(max) && val > max) { input.value = max; val = max; }
          lastValue = input.value;
          input.__dispatching = true;
          input.dispatchEvent(new Event('input', { bubbles: true }));
          input.__dispatching = false;
        }
        lastValue = input.value;
      });
      // Enter 键也触发
      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          input.blur();
        }
      });
    });
    return boundCount;
  }

  function init() {
    setupBlurTrigger();
    var observer = new MutationObserver(function () {
      setupBlurTrigger();
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      setTimeout(init, 1000);
    });
  } else {
    setTimeout(init, 1000);
  }
})();
</script>
"""

# ---------- Header and layout CSS ----------
HEADER_CSS = """
/* Full-width container */
.gradio-container {
    max-width: 100% !important;
    width: 100% !important;
    padding-left: 20px !important;
    padding-right: 20px !important;
}

/* Header row with rounded corners */
.header-row {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 15px 20px;
    margin-left: 0 !important;
    margin-right: 0 !important;
    width: 100% !important;
    border-radius: 16px !important;
    overflow: hidden !important;
    margin-bottom: 15px !important;
    align-items: center;
    box-shadow: 0 4px 15px rgba(102, 126, 234, 0.2) !important;
}

.header-row h1 {
    color: white !important;
    margin: 0 !important;
    font-size: 24px;
    display: flex;
    align-items: center;
    gap: 10px;
}

.header-row p {
    color: rgba(255,255,255,0.8) !important;
    margin: 0 !important;
    font-size: 14px;
}

.header-controls {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    justify-content: flex-start;
    gap: 8px;
    margin-top: -4px;
}

/* 2D Preview: keep fixed box, scale image to fit (no cropping) */
#conv-preview .image-container {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    overflow: hidden !important;
    height: 100% !important;
}
#conv-preview canvas,
#conv-preview img {
    max-width: 100% !important;
    max-height: 100% !important;
    width: auto !important;
    height: auto !important;
}

/* Left sidebar */
.left-sidebar {
    padding: 10px 15px 10px 0;
    height: 100%;
}

.compact-row {
    margin-top: -10px !important;
    margin-bottom: -10px !important;
    gap: 10px;
}

.micro-upload {
    min-height: 40px !important;
}

/* Workspace area */
.workspace-area {
    padding: 0 !important;
}

/* Action buttons */
.action-buttons {
    margin-top: 15px;
    margin-bottom: 15px;
}

/* Upload box height aligned with dropdown row */
.tall-upload {
    height: 84px !important;
    min-height: 84px !important;
    max-height: 84px !important;
    background-color: var(--background-fill-primary, #ffffff) !important;
    border-radius: 8px !important;
    border: 1px dashed var(--border-color-primary, #e5e7eb) !important;
    overflow: hidden !important;
    padding: 0 !important;
}

/* Inner layout for upload area */
.tall-upload .wrap {
    display: flex !important;
    flex-direction: column !important;
    justify-content: center !important;
    align-items: center !important;
    padding: 2px !important;
    height: 100% !important;
}

/* Smaller font in upload area */
.tall-upload .icon-wrap { display: none !important; }
.tall-upload span,
.tall-upload div {
    font-size: 12px !important;
    line-height: 1.3 !important;
    color: var(--body-text-color-subdued, #6b7280) !important;
    text-align: center !important;
    margin: 0 !important;
}

/* LUT status card style */
.lut-status {
    margin-top: 10px !important;
    padding: 8px 12px !important;
    background: var(--background-fill-primary, #ffffff) !important;
    border: 1px solid var(--border-color-primary, #e5e7eb) !important;
    border-radius: 8px !important;
    color: var(--body-text-color, #4b5563) !important;
    font-size: 13px !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    min-height: 36px !important;
    display: flex !important;
    align-items: center !important;
}
.lut-status p {
    margin: 0 !important;
}

/* Transparent group (no box) */
.clean-group {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
}

/* Modeling mode radio text color (avoid theme override) */
.vertical-radio label span {
    color: #374151 !important;
    font-weight: 500 !important;
}

/* Selected state text color */
.vertical-radio input:checked + span,
.vertical-radio label.selected span {
    color: #1f2937 !important;
}

/* Bed size dropdown overlay on preview */
#conv-bed-size-overlay {
    display: flex !important;
    justify-content: flex-end !important;
    align-items: center !important;
    margin-bottom: -8px !important;
    padding: 0 4px !important;
    z-index: 10 !important;
    position: relative !important;
    gap: 0 !important;
}
#conv-bed-size-overlay > .column:first-child {
    display: none !important;
}
#conv-bed-size-dropdown {
    max-width: 160px !important;
    min-width: 130px !important;
}
#conv-bed-size-dropdown input {
    font-size: 12px !important;
    padding: 4px 8px !important;
    height: 28px !important;
    border-radius: 6px !important;
    background: var(--background-fill-secondary, rgba(240,240,245,0.9)) !important;
    border: 1px solid var(--border-color-primary, #ddd) !important;
    cursor: pointer !important;
}
#conv-bed-size-dropdown .wrap {
    min-height: unset !important;
    padding: 0 !important;
}
#conv-bed-size-dropdown ul {
    font-size: 12px !important;
}
"""

# LUT 色块网格样式
LUT_GRID_CSS = """
.lut-swatch,
.lut-color-swatch {
    width: 24px;
    height: 24px;
    border-radius: 4px;
    cursor: pointer;
    border: 1px solid rgba(0,0,0,0.1);
    transition: transform 0.1s, border-color 0.1s;
}
.lut-swatch:hover,
.lut-color-swatch:hover {
    transform: scale(1.2);
    border-color: #333;
    z-index: 10;
    box-shadow: 0 2px 5px rgba(0,0,0,0.2);
}
"""

# 5-Color Combination click handler JS
FIVECOLOR_CLICK_JS = """
<style>
.hidden-5color-btn {
    position: absolute !important;
    left: -9999px !important;
    top: -9999px !important;
    width: 1px !important;
    height: 1px !important;
    overflow: hidden !important;
    opacity: 0 !important;
    visibility: hidden !important;
    pointer-events: none !important;
}
</style>
<script>
(function() {
    // 防止重复注入
    if (window._5colorClickHandlerInjected) return;
    window._5colorClickHandlerInjected = true;

    console.log('[5-Color] Injecting global click handler');

    // 使用事件委托监听所有颜色块点击
    document.addEventListener('click', function(e) {
        const colorBox = e.target.closest('.color-box-v2');
        if (!colorBox) return;

        const idx = colorBox.getAttribute('data-color-idx');
        if (idx === null) return;

        console.log('[5-Color] Color box clicked:', idx);

        // 查找并点击对应的隐藏按钮
        const btn = document.getElementById('color-btn-' + idx + '-5color');
        if (btn) {
            console.log('[5-Color] Triggering button:', btn.id);
            btn.click();
        } else {
            console.error('[5-Color] Button not found:', 'color-btn-' + idx + '-5color');
        }
    });

    console.log('[5-Color] Global click handler installed');
})();
</script>
"""
