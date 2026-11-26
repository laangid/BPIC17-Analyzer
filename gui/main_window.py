"""Jendela utama aplikasi.

Alur kerja (sesuai instruksi bagian 6):
Impor XES -> Overview -> Pilih Latihan -> Jalankan Analisis -> Lihat Jawaban -> Periksa Case -> Ekspor
"""

from __future__ import annotations

import os
import platform
import sys

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QFileDialog, QFormLayout, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar,
                               QPushButton, QSpinBox, QSplitter, QStackedWidget, QTabWidget, QTextBrowser,
                               QVBoxLayout, QWidget)

import analyzer
from analyzer import core, export, exercises, overview
from analyzer.loader import ACT_COL, CASE_COL, EventLogData, LogValidationError, load_xes

from . import worker
from .result_view import ResultView
from .table_model import SearchableTable

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAGES = ["1. Dataset & Status", "2. Overview", "3. Exercise 11.7", "4. Exercise 11.15 & 11.18",
         "5. Exercise 11.22", "6. Case Explorer", "7. Export", "About"]


def _card(title: str) -> tuple[QFrame, QLabel]:
    f = QFrame()
    f.setFrameShape(QFrame.StyledPanel)
    f.setStyleSheet("QFrame{background:#f4f8f8;border-radius:6px}")
    lay = QVBoxLayout(f)
    t = QLabel(title)
    t.setStyleSheet("color:#555")
    v = QLabel("-")
    v.setStyleSheet("font-size:17px;font-weight:bold;color:#0b3d5e")
    v.setTextInteractionFlags(Qt.TextSelectableByMouse)
    lay.addWidget(t)
    lay.addWidget(v)
    return f, v


def _run_button(text: str) -> QPushButton:
    b = QPushButton(text)
    b.setStyleSheet("QPushButton{background:#0b5e57;color:white;padding:6px 14px;border-radius:4px}"
                    "QPushButton:disabled{background:#9bb}")
    return b


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BPIC17 Event Log Analyzer — Exercise Bab 11 FBPM (PM4Py)")
        self.resize(1280, 820)

        self.data: EventLogData | None = None
        self.durations: pd.DataFrame | None = None
        self.results: dict = {}   # code -> AnalysisResult
        self._busy = False

        # ---- sidebar + halaman
        self.nav = QListWidget()
        self.nav.addItems(PAGES)
        self.nav.setFixedWidth(210)
        self.nav.setStyleSheet("QListWidget{font-size:13px} QListWidget::item{padding:8px}")
        self.stack = QStackedWidget()
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)

        self.stack.addWidget(self._build_dataset_page())
        self.stack.addWidget(self._build_overview_page())
        self.stack.addWidget(self._build_117_page())
        self.stack.addWidget(self._build_1115_page())
        self.stack.addWidget(self._build_1122_page())
        self.stack.addWidget(self._build_explorer_page())
        self.stack.addWidget(self._build_export_page())
        self.stack.addWidget(self._build_about_page())

        central = QWidget()
        lay = QHBoxLayout(central)
        lay.addWidget(self.nav)
        lay.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        # ---- status bar
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(220)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.status_file = QLabel("Belum ada dataset")
        self.statusBar().addPermanentWidget(self.status_file)
        self.statusBar().addPermanentWidget(self.progress)
        self.statusBar().showMessage("Siap. Mulai dengan membuka file XES.")

        self._build_menu()
        self.nav.setCurrentRow(0)
        self._set_loaded_state(False)

    # ================================================================ menu
    def _build_menu(self):
        m = self.menuBar().addMenu("&File")
        a = QAction("Buka XES...", self)
        a.setShortcut("Ctrl+O")
        a.triggered.connect(self.open_file)
        m.addAction(a)
        a = QAction("Muat log sintetis (edge case)", self)
        a.triggered.connect(self.open_synthetic)
        m.addAction(a)
        m.addSeparator()
        a = QAction("Keluar", self)
        a.triggered.connect(self.close)
        m.addAction(a)
        h = self.menuBar().addMenu("&Help")
        a = QAction("About", self)
        a.triggered.connect(lambda: self.nav.setCurrentRow(PAGES.index("About")))
        h.addAction(a)

    # ================================================================ halaman 1: dataset
    def _build_dataset_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("<h2>Dataset & Status</h2>"
                             "Pilih file event log BPIC17 (.xes atau .xes.gz). File dibaca dengan <code>pm4py.read_xes</code>."))
        row = QHBoxLayout()
        self.btn_open = _run_button("Buka file XES...")
        self.btn_open.clicked.connect(self.open_file)
        self.btn_syn = QPushButton("Muat log sintetis (edge case)")
        self.btn_syn.clicked.connect(self.open_synthetic)
        self.btn_reload = QPushButton("Muat ulang dataset")
        self.btn_reload.clicked.connect(self.reload_file)
        row.addWidget(self.btn_open)
        row.addWidget(self.btn_syn)
        row.addWidget(self.btn_reload)
        row.addStretch(1)
        lay.addLayout(row)

        form = QFormLayout()
        self.lbl_file = QLabel("-")
        self.lbl_file.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_status = QLabel("Belum ada dataset")
        self.lbl_counts = QLabel("-")
        self.lbl_attrs = QLabel("-")
        self.lbl_attrs.setWordWrap(True)
        form.addRow("File aktif:", self.lbl_file)
        form.addRow("Status baca:", self.lbl_status)
        form.addRow("Jumlah case / event:", self.lbl_counts)
        form.addRow("Atribut tersedia:", self.lbl_attrs)
        lay.addLayout(form)

        self.tbl_validation = SearchableTable("Validasi atribut", "Cari...")
        lay.addWidget(self.tbl_validation, 1)
        lay.addWidget(QLabel("<b>Pesan proses</b>"))
        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(170)
        lay.addWidget(self.log_box)
        return w

    # ================================================================ halaman 2: overview
    def _build_overview_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("<h2>Event Log Overview</h2>"))
        grid = QGridLayout()
        self.ov_cards = {}
        titles = ["Total case", "Total event", "Jumlah aktivitas", "Rentang waktu",
                  "Rata-rata cycle time", "Median cycle time", "Min / Maks cycle time", "Validasi PM4Py (mean)"]
        for i, t in enumerate(titles):
            f, v = _card(t)
            self.ov_cards[t] = v
            grid.addWidget(f, i // 4, i % 4)
        lay.addLayout(grid)
        lay.addWidget(QLabel("<small>Cycle time case = timestamp event terakhir − event pertama (trace utuh), satuan hari, "
                             "ketelitian 4 desimal di tabel.</small>"))
        tabs = QTabWidget()
        self.tbl_act = SearchableTable("", "Cari aktivitas...")
        self.tbl_life = SearchableTable("", "Cari aktivitas...")
        self.tbl_dur = SearchableTable("", "Cari case ID...")
        tabs.addTab(self.tbl_act, "Frekuensi aktivitas")
        tabs.addTab(self.tbl_life, "Aktivitas × lifecycle")
        tabs.addTab(self.tbl_dur, "Durasi per case")
        self.tbl_dur.view.doubleClicked.connect(lambda _: self._open_case_from(self.tbl_dur))
        lay.addWidget(tabs, 1)
        return w

    # ================================================================ halaman 3: 11.7
    def _build_117_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("<h2>Exercise 11.7 (A–E)</h2>"
                             "C dan D memakai aturan <b>contains</b> (case memuat event); "
                             "E memakai aturan <b>endpoint</b> (event terakhir trace)."))
        row = QHBoxLayout()
        self.btn_117 = _run_button("Jalankan analisis 11.7")
        self.btn_117.clicked.connect(self.run_117)
        row.addWidget(self.btn_117)
        row.addStretch(1)
        lay.addLayout(row)
        self.tbl_117 = SearchableTable("Ringkasan jawaban", "Cari...")
        self.tbl_117.setMaximumHeight(210)
        lay.addWidget(self.tbl_117)
        self.tabs_117 = QTabWidget()
        self.rv_117 = {}
        for code in ["11.7 A", "11.7 B", "11.7 C", "11.7 D", "11.7 E"]:
            rv = ResultView()
            rv.open_case.connect(self.show_case)
            self.rv_117[code] = rv
            self.tabs_117.addTab(rv, code)
        self.tbl_117.view.clicked.connect(lambda idx: self.tabs_117.setCurrentIndex(self.tbl_117.proxy.mapToSource(idx).row()))
        lay.addWidget(self.tabs_117, 1)
        return w

    # ================================================================ halaman 4: 11.15 & 11.18
    def _build_1115_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("<h2>Exercise 11.15 & 11.18 — Repeated complete & same resource</h2>"
                             "Hanya event dengan <code>lifecycle:transition = complete</code> yang dihitung."))
        row = QHBoxLayout()
        row.addWidget(QLabel("Aktivitas:"))
        self.in_fraud = QLineEdit(exercises.FRAUD)
        self.in_fraud.setMinimumWidth(260)
        row.addWidget(self.in_fraud)
        row.addWidget(QLabel("Minimal complete:"))
        self.in_min = QSpinBox()
        self.in_min.setRange(1, 100)
        self.in_min.setValue(2)
        row.addWidget(self.in_min)
        self.btn_1115 = _run_button("Jalankan 11.15 && 11.18")
        self.btn_1115.clicked.connect(self.run_1115)
        row.addWidget(self.btn_1115)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addWidget(QLabel("<small>Nama aktivitas dicocokkan tanpa membedakan huruf besar/kecil "
                             "(BPIC17 menulis 'W_Assess potential fraud').</small>"))
        self.tabs_1115 = QTabWidget()
        self.rv_1115 = ResultView()
        self.rv_1118 = ResultView()
        for rv, name in [(self.rv_1115, "11.15 — complete ≥ 2×"), (self.rv_1118, "11.18 — oleh resource sama")]:
            rv.open_case.connect(self.show_case)
            self.tabs_1115.addTab(rv, name)
        lay.addWidget(self.tabs_1115, 1)
        return w

    # ================================================================ halaman 5: 11.22
    def _build_1122_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("<h2>Exercise 11.22 — Eventually follows</h2>"
                             "Case dipilih jika ada posisi i &lt; j dengan event i = aktivitas pertama dan event j = "
                             "aktivitas kedua (tidak harus bersebelahan). Berbeda dengan 11.7 E."))
        row = QHBoxLayout()
        row.addWidget(QLabel("Aktivitas pertama:"))
        self.in_first = QLineEdit(exercises.CANCELLED)
        row.addWidget(self.in_first)
        row.addWidget(QLabel("→ diikuti:"))
        self.in_second = QLineEdit(exercises.ACCEPTED)
        row.addWidget(self.in_second)
        self.btn_1122 = _run_button("Jalankan 11.22")
        self.btn_1122.clicked.connect(self.run_1122)
        row.addWidget(self.btn_1122)
        row.addStretch(1)
        lay.addLayout(row)
        self.rv_1122 = ResultView()
        self.rv_1122.open_case.connect(self.show_case)
        lay.addWidget(self.rv_1122, 1)
        return w

    # ================================================================ halaman 6: case explorer
    def _build_explorer_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("<h2>Case Explorer</h2>Pilih case untuk melihat urutan event dan atributnya."))
        row = QHBoxLayout()
        row.addWidget(QLabel("Case ID:"))
        self.in_case = QLineEdit()
        self.in_case.setPlaceholderText("ketik case ID persis, mis. Application_652823628")
        self.in_case.returnPressed.connect(lambda: self.show_case(self.in_case.text().strip()))
        row.addWidget(self.in_case, 1)
        b = QPushButton("Tampilkan")
        b.clicked.connect(lambda: self.show_case(self.in_case.text().strip()))
        row.addWidget(b)
        lay.addLayout(row)

        split = QSplitter(Qt.Horizontal)
        self.ex_cases = SearchableTable("Semua case", "Cari case ID...")
        self.ex_cases.view.selectionModel().selectionChanged.connect(
            lambda *_: self._open_case_from(self.ex_cases, switch=False))
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self.ex_header = QLabel("<i>Belum ada case dipilih.</i>")
        self.ex_header.setWordWrap(True)
        self.ex_header.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.ex_header.setStyleSheet("background:#f4f8f8;padding:6px;border-radius:6px")
        self.ex_events = SearchableTable("Urutan event (trace)", "Cari di event...")
        rl.addWidget(self.ex_header)
        rl.addWidget(self.ex_events, 1)
        split.addWidget(self.ex_cases)
        split.addWidget(right)
        split.setSizes([330, 850])
        lay.addWidget(split, 1)
        return w

    # ================================================================ halaman 7: export
    def _build_export_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("<h2>Export</h2>"
                             "Menjalankan ulang seluruh analisis pada log aktif lalu menyimpan CSV: "
                             "ringkasan semua jawaban + daftar case dan bukti event per soal.<br>"
                             "Ekspor per soal juga tersedia di setiap halaman soal (tombol <i>Export CSV...</i>)."))
        row = QHBoxLayout()
        self.btn_export_all = _run_button("Jalankan semua & ekspor CSV...")
        self.btn_export_all.clicked.connect(self.export_all)
        self.btn_export_dur = QPushButton("Ekspor durasi per case (CSV)...")
        self.btn_export_dur.clicked.connect(self.export_durations)
        row.addWidget(self.btn_export_all)
        row.addWidget(self.btn_export_dur)
        row.addStretch(1)
        lay.addLayout(row)
        self.tbl_summary = SearchableTable("Ringkasan semua jawaban", "Cari...")
        lay.addWidget(self.tbl_summary, 1)
        return w

    # ================================================================ halaman 8: about
    def _build_about_page(self) -> QWidget:
        import pm4py
        from PySide6 import __version__ as pyside_version
        tb = QTextBrowser()
        tb.setOpenExternalLinks(True)
        tb.setHtml(f"""
        <h2>BPIC17 Event Log Analyzer</h2>
        <p>Aplikasi Proyek Tahap 1 — menjawab Exercise 11.7 (A–E), 11.15, 11.18, dan 11.22 (Dumas et al.,
        <i>Fundamentals of BPM</i>, Bab 11) dari event log BPI Challenge 2017.</p>
        <h3>Versi lingkungan</h3>
        <table border="1" cellpadding="4" cellspacing="0">
        <tr><td>Aplikasi</td><td>{analyzer.__version__}</td></tr>
        <tr><td>Python</td><td>{platform.python_version()} ({sys.platform})</td></tr>
        <tr><td>PM4Py</td><td>{pm4py.__version__}</td></tr>
        <tr><td>pandas</td><td>{pd.__version__}</td></tr>
        <tr><td>PySide6</td><td>{pyside_version}</td></tr>
        </table>
        <h3>Definisi operasional</h3>
        <ul>
        <li><b>Case/trace</b>: event dengan <code>case:concept:name</code> yang sama.</li>
        <li><b>Urutan event</b>: per case diurutkan menurut <code>time:timestamp</code>; jika timestamp sama,
            urutan asli di file XES dipertahankan (stable sort).</li>
        <li><b>Cycle time</b>: timestamp event terakhir − event pertama dari trace utuh, dalam hari.
            Filter hanya memilih case; event tidak dihapus sebelum durasi dihitung.</li>
        <li><b>Contains</b> (11.7 C, D): case memuat minimal satu event aktivitas target; dihitung sekali per case.</li>
        <li><b>Endpoint</b> (11.7 E): event terakhir trace adalah aktivitas target.</li>
        <li><b>Complete occurrence</b> (11.15): event dengan <code>lifecycle:transition</code> = <code>complete</code>.
            Status schedule, start, suspend, resume, ate_abort, withdraw tidak dihitung.</li>
        <li><b>Same resource</b> (11.18): ≥ 2 complete occurrence dalam satu case dengan <code>org:resource</code> identik;
            resource kosong tidak dianggap sama.</li>
        <li><b>Eventually follows</b> (11.22): ada posisi i &lt; j, event i = O_Cancelled, event j = O_Accepted;
            persentase = case cocok / seluruh case log aktif × 100%.</li>
        </ul>
        <h3>Validasi silang</h3>
        <p>Setiap jawaban dihitung dengan pandas di atas DataFrame hasil PM4Py, lalu dibandingkan dengan filter bawaan
        PM4Py bila tersedia (<code>filter_event_attribute_values</code>, <code>filter_end_activities</code>,
        <code>filter_activities_rework</code>, <code>filter_eventually_follows_relation</code>,
        <code>get_all_case_durations</code>).</p>
        <p>Dataset: BPI Challenge 2017, 4TU.ResearchData,
        <a href="https://doi.org/10.4121/uuid:5f3067df-f10b-45da-b98b-86ae4c7a310b">doi:10.4121/uuid:5f3067df-f10b-45da-b98b-86ae4c7a310b</a></p>
        """)
        return tb

    # ================================================================ state helpers
    def _set_loaded_state(self, loaded: bool):
        for b in (self.btn_117, self.btn_1115, self.btn_1122, self.btn_export_all,
                  self.btn_export_dur, self.btn_reload):
            b.setEnabled(loaded and not self._busy)
        for b in (self.btn_open, self.btn_syn):
            b.setEnabled(not self._busy)

    def _begin(self, msg: str):
        self._busy = True
        self.progress.setRange(0, 0)  # indeterminate
        self.statusBar().showMessage(msg)
        self._log(msg)
        self._set_loaded_state(self.data is not None)
        self.setCursor(Qt.BusyCursor)

    def _end(self, msg: str):
        self._busy = False
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.statusBar().showMessage(msg)
        self._log(msg)
        self._set_loaded_state(self.data is not None)
        self.unsetCursor()

    def _log(self, msg: str):
        self.log_box.appendPlainText(msg)

    def _error(self, msg: str):
        self._end("Gagal: " + msg.splitlines()[0])
        QMessageBox.critical(self, "Terjadi kesalahan", msg)

    def _need_data(self) -> bool:
        if self.data is None:
            QMessageBox.warning(self, "Belum ada dataset", "Buka file XES terlebih dahulu.")
            return False
        return not self._busy

    # ================================================================ load
    def open_file(self):
        if self._busy:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Pilih event log XES", "",
                                              "Event log XES (*.xes *.xes.gz *.gz);;Semua file (*)")
        if path:
            self.load_path(path)

    def open_synthetic(self):
        if self._busy:
            return
        sys.path.insert(0, os.path.join(APP_ROOT, "tests"))
        import synthetic_log
        path = os.path.join(APP_ROOT, "data", "synthetic_edge_cases.xes")
        synthetic_log.write_xes(path)
        self.load_path(path)

    def reload_file(self):
        if self.data is not None and not self._busy:
            self.load_path(self.data.path)

    def load_path(self, path: str):
        self._begin(f"Mengimpor {os.path.basename(path)} ...")
        self.lbl_status.setText("Sedang membaca...")

        def job(progress):
            data = load_xes(path, progress)
            progress("Menghitung durasi case dan overview...")
            ov = overview.get_overview(data)
            dur = core.case_durations(data.df)
            return data, ov, dur

        worker.start(job, self._on_loaded, self._on_load_error, self._log)

    def _on_load_error(self, msg: str):
        self.lbl_status.setText("<span style='color:#b00'>Gagal</span>")
        self._error(msg)

    def _on_loaded(self, payload):
        data, ov, dur = payload
        self.data, self.durations = data, dur
        self.results.clear()
        for rv in list(self.rv_117.values()) + [self.rv_1115, self.rv_1118, self.rv_1122]:
            rv.title.setText("<i>Belum dijalankan untuk dataset ini.</i>")
            rv.answer.setText("")
            rv.rule.setText("")
            rv.meta.setText("")
            rv.cases.set_df(pd.DataFrame())
            rv.evidence.set_df(pd.DataFrame())
        self.tbl_117.set_df(pd.DataFrame())
        self.tbl_summary.set_df(pd.DataFrame())

        self.lbl_file.setText(data.path)
        self.lbl_status.setText(f"<span style='color:#0a0'>Berhasil</span> ({data.load_seconds:.1f} detik)")
        self.lbl_counts.setText(f"{data.n_cases:,} case / {data.n_events:,} event")
        self.lbl_attrs.setText(", ".join(data.attributes))
        val = pd.DataFrame(data.validation, columns=["Pemeriksaan", "OK", "Keterangan"])
        self.tbl_validation.set_df(val)
        for w in data.warnings:
            self._log("PERINGATAN: " + w)
        self.status_file.setText(f"{data.filename} — {data.n_cases:,} case")

        c = self.ov_cards
        c["Total case"].setText(f"{ov.n_cases:,}")
        c["Total event"].setText(f"{ov.n_events:,}")
        c["Jumlah aktivitas"].setText(f"{ov.n_activities}")
        c["Rentang waktu"].setText(f"{ov.start:%Y-%m-%d}<br>s/d {ov.end:%Y-%m-%d}")
        c["Rata-rata cycle time"].setText(f"{ov.mean_days:.2f} hari")
        c["Median cycle time"].setText(f"{ov.median_days:.2f} hari")
        c["Min / Maks cycle time"].setText(f"{ov.min_days:.2f} / {ov.max_days:.2f} hari")
        c["Validasi PM4Py (mean)"].setText(f"{ov.pm4py_mean_days:.2f} hari")
        self.tbl_act.set_df(ov.activity_freq)
        self.tbl_life.set_df(ov.lifecycle_freq)
        self.tbl_dur.set_df(ov.durations)
        self.ex_cases.set_df(ov.durations[[CASE_COL, "n_events", "duration_days"]])
        self._end(f"Dataset siap: {data.n_cases:,} case, {data.n_events:,} event.")
        self.nav.setCurrentRow(1)

    # ================================================================ analisis
    def _run(self, label, fn, on_done):
        if not self._need_data():
            return
        self._begin(f"Menjalankan {label} ...")
        data, dur = self.data, self.durations
        worker.start(lambda progress: fn(data, dur), lambda r: (on_done(r), self._end(f"{label} selesai.")),
                     self._error, self._log)

    def run_117(self):
        def done(results):
            rows = []
            for r in results:
                self.results[r.code] = r
                self.rv_117[r.code].set_result(r, self.data.filename)
                rows.append({"Kode": r.code, "Pertanyaan": r.question, "Jawaban": r.answer_text(),
                             "Validasi PM4Py": r.pm4py_check})
            self.tbl_117.set_df(pd.DataFrame(rows))
        self._run("Exercise 11.7", lambda d, dur: exercises.analyze_117(d, dur), done)

    def run_1115(self):
        act, n = self.in_fraud.text().strip() or exercises.FRAUD, self.in_min.value()

        def done(pair):
            r15, r18 = pair
            self.results[r15.code], self.results[r18.code] = r15, r18
            self.rv_1115.set_result(r15, self.data.filename)
            self.rv_1118.set_result(r18, self.data.filename)
        self._run("Exercise 11.15 & 11.18",
                  lambda d, dur: (exercises.analyze_1115(d, act, n, dur), exercises.analyze_1118(d, act, n, dur)), done)

    def run_1122(self):
        a = self.in_first.text().strip() or exercises.CANCELLED
        b = self.in_second.text().strip() or exercises.ACCEPTED

        def done(r):
            self.results[r.code] = r
            self.rv_1122.set_result(r, self.data.filename)
        self._run("Exercise 11.22", lambda d, dur: exercises.analyze_1122(d, a, b, dur), done)

    # ================================================================ case explorer
    def _open_case_from(self, table: SearchableTable, switch: bool = True):
        cid = table.selected_value(0)
        if cid is not None:
            self.show_case(str(cid), switch=switch)

    def show_case(self, case_id: str, switch: bool = True):
        if self.data is None or not case_id:
            return
        trace = core.case_trace(self.data.df, case_id)
        if switch:
            self.nav.setCurrentRow(PAGES.index("6. Case Explorer"))
        self.in_case.setText(case_id)
        if trace.empty:
            self.ex_header.setText(f"<span style='color:#b00'>Case '{case_id}' tidak ditemukan.</span>")
            self.ex_events.set_df(pd.DataFrame())
            return
        cols = ["_event_idx", "time:timestamp", ACT_COL, "lifecycle:transition", "org:resource"]
        cols = [c for c in cols if c in trace.columns]
        other = [c for c in trace.columns if c not in cols and not c.startswith("_") and c != CASE_COL]
        view = trace[cols + other].dropna(axis=1, how="all")
        d = self.durations.loc[case_id]
        member = [code for code, r in sorted(self.results.items())
                  if code not in ("11.7 A", "11.7 B") and case_id in set(r.case_ids)]
        not_member = [code for code in sorted(self.results) if code not in ("11.7 A", "11.7 B") and code not in member]
        last_act = trace.iloc[-1][ACT_COL]
        txt = (f"<b>{case_id}</b> &mdash; {int(d['n_events'])} event, durasi <b>{d['duration_days']:.4f} hari</b> "
               f"({d['start']:%Y-%m-%d %H:%M} → {d['end']:%Y-%m-%d %H:%M}). Event terakhir: <b>{last_act}</b>.<br>")
        if self.results:
            txt += ("Lolos filter: <b>" + (", ".join(member) or "-") + "</b>"
                    + (" &nbsp;|&nbsp; Tidak lolos: " + ", ".join(not_member) if not_member else ""))
        else:
            txt += "<i>Jalankan analisis soal untuk melihat kategori case ini.</i>"
        self.ex_header.setText(txt)
        self.ex_events.set_df(view)

    # ================================================================ export
    def export_all(self):
        if not self._need_data():
            return
        folder = QFileDialog.getExistingDirectory(self, "Pilih folder untuk menyimpan CSV")
        if not folder:
            return
        data = self.data

        def job(progress):
            progress("Menjalankan seluruh analisis...")
            results = exercises.run_all(data)
            progress("Menyimpan CSV...")
            paths = [export.export_summary(results, os.path.join(folder, "ringkasan_semua_jawaban.csv"), data.filename)]
            for r in results:
                paths += export.export_result(r, folder, data.filename)
            return results, paths

        def done(payload):
            results, paths = payload
            for r in results:
                self.results[r.code] = r
            self.tbl_summary.set_df(pd.DataFrame([r.summary_row() for r in results]))
            QMessageBox.information(self, "Ekspor selesai", f"{len(paths)} file CSV disimpan di:\n{folder}")

        self._begin("Menjalankan semua analisis & ekspor ...")
        worker.start(job, lambda p: (done(p), self._end("Ekspor selesai.")), self._error, self._log)

    def export_durations(self):
        if not self._need_data():
            return
        path, _ = QFileDialog.getSaveFileName(self, "Simpan durasi per case", "durasi_per_case.csv", "CSV (*.csv)")
        if path:
            export.export_dataframe(self.durations.reset_index(), path)
            QMessageBox.information(self, "Ekspor selesai", f"Tersimpan: {path}")
