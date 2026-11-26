"""Widget generik untuk menampilkan satu AnalysisResult:
jawaban, aturan filter, denominator, validasi PM4Py, daftar case, dan bukti event."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QSplitter,
                               QVBoxLayout, QWidget)

from analyzer import export
from analyzer.result import AnalysisResult

from .table_model import SearchableTable


class ResultView(QWidget):
    open_case = Signal(str)  # minta Case Explorer membuka case tertentu

    def __init__(self, parent=None):
        super().__init__(parent)
        self.result: AnalysisResult | None = None
        self.source_file = ""

        self.title = QLabel("<i>Belum dijalankan.</i>")
        self.title.setWordWrap(True)
        self.answer = QLabel("")
        self.answer.setStyleSheet("font-size:18px; font-weight:bold; color:#0b5e57; padding:4px 0")
        self.answer.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.rule = QLabel("")
        self.rule.setWordWrap(True)
        self.rule.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.meta = QLabel("")
        self.meta.setWordWrap(True)
        self.meta.setStyleSheet("color:#444")

        box = QFrame()
        box.setFrameShape(QFrame.StyledPanel)
        box.setStyleSheet("QFrame{background:#f4f8f8; border-radius:6px}")
        bl = QVBoxLayout(box)
        for w in (self.title, self.answer, self.rule, self.meta):
            bl.addWidget(w)

        self.cases = SearchableTable("Daftar case terpilih", "Cari case ID / nilai...")
        self.evidence = SearchableTable("Bukti event", "Cari di bukti event...")
        self.cases.view.selectionModel().selectionChanged.connect(self._on_case_selected)
        self.cases.view.doubleClicked.connect(lambda _: self._open_selected())

        self.btn_all_ev = QPushButton("Tampilkan semua bukti")
        self.btn_all_ev.clicked.connect(self.evidence.clear_filter)
        self.btn_open = QPushButton("Buka rincian case di Case Explorer")
        self.btn_open.clicked.connect(self._open_selected)
        self.btn_export = QPushButton("Export CSV...")
        self.btn_export.clicked.connect(self._export)
        for b in (self.btn_open, self.btn_export, self.btn_all_ev):
            b.setEnabled(False)

        btns = QHBoxLayout()
        btns.addWidget(QLabel("<small>Pilih case untuk melihat buktinya; klik ganda untuk membuka rincian.</small>"))
        btns.addStretch(1)
        btns.addWidget(self.btn_all_ev)
        btns.addWidget(self.btn_open)
        btns.addWidget(self.btn_export)

        split = QSplitter(Qt.Vertical)
        split.addWidget(self.cases)
        split.addWidget(self.evidence)
        split.setSizes([300, 250])

        lay = QVBoxLayout(self)
        lay.addWidget(box)
        lay.addLayout(btns)
        lay.addWidget(split, 1)

    def set_result(self, result: AnalysisResult, source_file: str = ""):
        self.result = result
        self.source_file = source_file
        self.title.setText(f"<b>{result.code}</b> &mdash; {result.question}")
        self.answer.setText("Jawaban: " + result.answer_text())
        self.rule.setText(f"<b>Aturan filter:</b> {result.rule}")
        meta = [f"<b>Case terpilih:</b> {result.count:,} &nbsp;|&nbsp; <b>Denominator (seluruh case log aktif):</b> {result.denominator:,}",
                f"<b>Validasi silang PM4Py:</b> {result.pm4py_check or '-'}"]
        meta += [f"&bull; {n}" for n in result.notes]
        self.meta.setText("<br>".join(meta))
        self.cases.set_df(result.case_table)
        self.evidence.set_df(result.evidence)
        has_cases = not result.case_table.empty
        self.btn_open.setEnabled(has_cases)
        self.btn_export.setEnabled(True)
        self.btn_all_ev.setEnabled(not result.evidence.empty)

    def _on_case_selected(self, *_):
        cid = self.cases.selected_value(0)
        if cid is not None and not self.evidence.model.df.empty:
            self.evidence.filter_exact(0, str(cid))

    def _open_selected(self):
        cid = self.cases.selected_value(0)
        if cid is None and self.result is not None and self.result.case_ids:
            cid = self.result.case_ids[0]
        if cid is not None:
            self.open_case.emit(str(cid))

    def _export(self):
        if self.result is None:
            return
        folder = QFileDialog.getExistingDirectory(self, "Pilih folder untuk menyimpan CSV")
        if not folder:
            return
        try:
            paths = export.export_result(self.result, folder, self.source_file)
        except Exception as exc:
            QMessageBox.critical(self, "Gagal ekspor", str(exc))
            return
        QMessageBox.information(self, "Ekspor selesai", "File tersimpan:\n" + "\n".join(paths))
