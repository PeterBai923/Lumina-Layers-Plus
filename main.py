#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                          LUMINA STUDIO v1.6.7                                 ║
║                    Multi-Material 3D Print Color System                       ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  Copyright (C) 2025 Lumina Studio Contributors                                ║
║  License: GNU GPL v3.0                                                        ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Main Entry Point
"""

import os
import sys
import signal
import numpy as np

setattr(np, "asscalar", lambda a: a.item())

from core.utils.logger import get_logger, init_logging
from config import LogConfig

# Handle PyInstaller bundled resources
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    _PROJECT_ROOT = sys._MEIPASS
    # Also set the working directory to where the exe is located
    os.chdir(os.path.dirname(sys.executable))
else:
    # Running as script
    _PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

_GRADIO_TEMP = os.path.join(os.getcwd(), "output", ".gradio_cache")
os.makedirs(_GRADIO_TEMP, exist_ok=True)
os.environ["GRADIO_TEMP_DIR"] = _GRADIO_TEMP

import time
import threading
import webbrowser
import socket
import gradio as gr     # type:ignore
from ui.layout import create_app
from ui.styles import CUSTOM_CSS

def find_available_port(start_port=7860, max_attempts=1000):
    """Return first free port in [start_port, start_port + max_attempts)."""
    import socket
    for i in range(max_attempts):
        port = start_port + i
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError(f"No available port found after {max_attempts} attempts")

def start_browser(port):
    """Launch the default web browser after a short delay."""
    time.sleep(2)
    webbrowser.open(f"http://127.0.0.1:{port}")

def _graceful_shutdown(signum, frame):
    """Handle SIGTERM/SIGINT for clean container shutdown.
    处理 SIGTERM/SIGINT 信号，实现容器优雅退出。

    Args:
        signum (int): Signal number received. (接收到的信号编号)
        frame (frame): Current stack frame. (当前栈帧)
    """
    logger = get_logger("main")
    sig_name = signal.Signals(signum).name
    logger.info(f"收到 %s 信号，正在关闭...", sig_name)
    os._exit(0)


if __name__ == "__main__":
    try:
        # Register signal handlers for graceful shutdown (SIGTERM from docker stop)
        signal.signal(signal.SIGTERM, _graceful_shutdown)
        signal.signal(signal.SIGINT, _graceful_shutdown)

        init_logging(LogConfig.get_log_path())
        logger = get_logger("main")
        PORT = find_available_port(7860)

        threading.Thread(target=start_browser, args=(PORT,), daemon=True).start()
        logger.info(f"Lumina Studio 运行在 http://127.0.0.1:{PORT}")
        app = create_app()

        try:
            from ui.assets import DEBOUNCE_JS, FIVECOLOR_CLICK_JS
            # Import crop extension for head JS injection
            from ui.widgets.crop_modal import get_crop_head_js
            
            # Find icon path (handle both dev and frozen modes)
            icon_path = None
            if os.path.exists("icon.ico"):
                icon_path = "icon.ico"
            elif getattr(sys, 'frozen', False):
                # In frozen mode, check in _MEIPASS
                icon_in_bundle = os.path.join(sys._MEIPASS, "icon.ico")
                if os.path.exists(icon_in_bundle):
                    icon_path = icon_in_bundle
            
            app.launch(
                inbrowser=False,
                server_name="0.0.0.0",
                server_port=PORT,
                show_error=True,
                prevent_thread_lock=True,
                favicon_path=icon_path,
                css=CUSTOM_CSS,
                theme=gr.themes.Soft(),
                head=get_crop_head_js() + DEBOUNCE_JS + FIVECOLOR_CLICK_JS
            )
        except Exception as e:
            logger.error(f"启动 Gradio 应用失败: {e}")
            import traceback
            traceback.print_exc()
            raise

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

        logger.info("正在停止...")
        os._exit(0)
        
    except Exception as e:
        logger.error(f"致命错误: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")
        os._exit(1)
