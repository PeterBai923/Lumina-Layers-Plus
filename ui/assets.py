# -*- coding: utf-8 -*-
"""Lumina Studio - JS string constants used by the UI layer.

CSS has been moved to ui/styles/ package.
"""

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

# 5-Color Combination click handler JS (CSS for .hidden-5color-btn is in hidden.css)
FIVECOLOR_CLICK_JS = """
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
