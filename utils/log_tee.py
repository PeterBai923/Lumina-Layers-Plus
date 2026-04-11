"""统一的日志分流（Tee）和启动引导工具。"""

import re
import sys
import threading
from datetime import datetime

import numpy as np

_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')


def patch_asscalar(a):
    """Replace deprecated numpy.asscalar for colormath."""
    return a.item()


class _Tee:
    """同时写入控制台和日志文件的 stdout/stderr 代理。"""

    def __init__(self, log_path, console_stream=None, lock=None):
        self._console = console_stream if console_stream is not None else sys.__stdout__
        self._file = open(log_path, 'a', encoding='utf-8', buffering=1)
        self._at_line_start = True
        self._lock = lock or threading.Lock()
        self.encoding = getattr(self._console, 'encoding', 'utf-8')

    def write(self, msg):
        if self._console is not None:
            try:
                self._console.write(msg)
            except (UnicodeEncodeError, UnicodeDecodeError):
                enc = getattr(self._console, 'encoding', 'utf-8') or 'utf-8'
                self._console.write(msg.encode(enc, errors='replace').decode(enc))
        if not msg:
            return
        clean = _ANSI_RE.sub('', msg)
        if not clean:
            return
        ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        with self._lock:
            for part in clean.splitlines(keepends=True):
                if self._at_line_start:
                    self._file.write(f'[{ts}] ')
                self._file.write(part)
                self._at_line_start = part.endswith('\n')

    def flush(self):
        if self._console is not None:
            self._console.flush()
        try:
            self._file.flush()
        except Exception:
            pass

    def __getattr__(self, name):
        if self._console is not None:
            return getattr(self._console, name)
        raise AttributeError(name)


class _TeeStderr:
    """stderr 分流代理，日志行前缀 [ERR]。"""

    def __init__(self, log_file, lock):
        self._console = sys.__stderr__
        self._file = log_file
        self._lock = lock
        self._at_line_start = True
        self.encoding = getattr(self._console, 'encoding', 'utf-8')

    def write(self, msg):
        if self._console is not None:
            try:
                self._console.write(msg)
            except (UnicodeEncodeError, UnicodeDecodeError):
                enc = getattr(self._console, 'encoding', 'utf-8') or 'utf-8'
                self._console.write(msg.encode(enc, errors='replace').decode(enc))
        if not msg:
            return
        clean = _ANSI_RE.sub('', msg)
        if not clean:
            return
        ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        with self._lock:
            for part in clean.splitlines(keepends=True):
                if self._at_line_start:
                    self._file.write(f'[{ts}] [ERR] ')
                self._file.write(part)
                self._at_line_start = part.endswith('\n')

    def flush(self):
        if self._console is not None:
            self._console.flush()
        try:
            self._file.flush()
        except Exception:
            pass

    def __getattr__(self, name):
        if self._console is not None:
            return getattr(self._console, name)
        raise AttributeError(name)
