"""Menjalankan komputasi berat di background thread agar GUI tidak membeku."""

from __future__ import annotations

import traceback

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _Signals(QObject):
    progress = Signal(str)
    finished = Signal(object)
    error = Signal(str)


class Task(QRunnable):
    """Membungkus fungsi fn(progress_callback) -> hasil."""

    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.signals = _Signals()
        self.setAutoDelete(True)

    def run(self):
        try:
            result = self.fn(self.signals.progress.emit)
        except Exception as exc:  # tampilkan pesan error yang jelas ke pengguna
            msg = f"{type(exc).__name__}: {exc}"
            self.signals.error.emit(msg + "\n\n" + traceback.format_exc(limit=3))
        else:
            self.signals.finished.emit(result)


_ACTIVE = set()  # simpan referensi agar objek sinyal tidak terhapus garbage collector


def start(fn, on_done, on_error, on_progress=None) -> Task:
    task = Task(fn)
    task.setAutoDelete(False)
    _ACTIVE.add(task)

    def _cleanup(*_):
        _ACTIVE.discard(task)

    task.signals.finished.connect(on_done)
    task.signals.error.connect(on_error)
    task.signals.finished.connect(_cleanup)
    task.signals.error.connect(_cleanup)
    if on_progress is not None:
        task.signals.progress.connect(on_progress)
    QThreadPool.globalInstance().start(task)
    return task
