"""Model tabel Qt untuk pandas DataFrame + tabel dengan kotak pencarian."""

from __future__ import annotations

import re

import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QRegularExpression, QSortFilterProxyModel, Qt
from PySide6.QtWidgets import QAbstractItemView, QHBoxLayout, QLabel, QLineEdit, QTableView, QVBoxLayout, QWidget

# Nama kolom yang lebih mudah dibaca di GUI
PRETTY = {
    "case:concept:name": "Case ID",
    "concept:name": "Aktivitas",
    "time:timestamp": "Timestamp",
    "lifecycle:transition": "Lifecycle",
    "org:resource": "Resource",
    "_event_idx": "Posisi",
    "duration_days": "Durasi (hari)",
    "n_events": "Jumlah event",
    "activity": "Aktivitas",
    "n_cases": "Jumlah case",
    "jumlah_complete": "Jumlah complete",
    "total_complete": "Total complete",
    "jumlah_oleh_resource": "Complete oleh resource",
    "resource": "Resource (sama)",
    "dihitung_complete": "Dihitung (complete)?",
    "peran": "Peran dalam pola",
    "start": "Mulai",
    "end": "Selesai",
}


def _fmt(v) -> str:
    if v is None or (not isinstance(v, (list, tuple)) and pd.isna(v)):
        return ""
    if isinstance(v, pd.Timestamp):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, float):
        return f"{v:,.4f}".rstrip("0").rstrip(".") if abs(v) < 1e6 else f"{v:,.2f}"
    if isinstance(v, bool):
        return "ya" if v else "tidak"
    return str(v)


class DataFrameModel(QAbstractTableModel):
    def __init__(self, df: pd.DataFrame | None = None, parent=None):
        super().__init__(parent)
        self._df = pd.DataFrame()
        self._cache = []
        self.set_df(df if df is not None else pd.DataFrame())

    def set_df(self, df: pd.DataFrame):
        self.beginResetModel()
        self._df = df.reset_index(drop=True)
        self._raw = self._df.to_numpy(dtype=object) if len(self._df.columns) else []
        self.endResetModel()

    @property
    def df(self) -> pd.DataFrame:
        return self._df

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._df)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._df.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        v = self._raw[index.row()][index.column()]
        if role == Qt.DisplayRole:
            return _fmt(v)
        if role == Qt.UserRole:  # untuk sorting numerik
            if isinstance(v, pd.Timestamp):
                return v.value
            if v is None or (not isinstance(v, str) and pd.isna(v)):
                return ""
            return v
        if role == Qt.TextAlignmentRole and isinstance(v, (int, float)) and not isinstance(v, bool):
            return int(Qt.AlignRight | Qt.AlignVCenter)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            name = str(self._df.columns[section])
            return PRETTY.get(name, name)
        return str(section + 1)


class SearchableTable(QWidget):
    """QTableView + kotak pencarian (mencari di semua kolom)."""

    def __init__(self, title: str = "", placeholder: str = "Cari...", parent=None):
        super().__init__(parent)
        self.model = DataFrameModel()
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterKeyColumn(-1)
        self.proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy.setSortRole(Qt.UserRole)

        self.view = QTableView()
        self.view.setModel(self.proxy)
        self.view.setSortingEnabled(True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.view.setAlternatingRowColors(True)
        self.view.verticalHeader().setDefaultSectionSize(22)

        self.search = QLineEdit()
        self.search.setPlaceholderText(placeholder)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._on_search)
        self.info = QLabel("")
        self.info.setStyleSheet("color:#666")

        top = QHBoxLayout()
        if title:
            lbl = QLabel(f"<b>{title}</b>")
            top.addWidget(lbl)
        top.addWidget(self.search, 1)
        top.addWidget(self.info)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(top)
        lay.addWidget(self.view)

    def set_df(self, df: pd.DataFrame):
        self.model.set_df(df)
        # tampilkan sesuai urutan data asli (urutan trace) sampai pengguna klik header
        self.proxy.sort(-1)
        self.view.horizontalHeader().setSortIndicator(-1, Qt.AscendingOrder)
        self.view.resizeColumnsToContents()
        for c in range(self.model.columnCount()):
            if self.view.columnWidth(c) > 380:
                self.view.setColumnWidth(c, 380)
        self._update_info()

    def _on_search(self, text: str):
        self.proxy.setFilterKeyColumn(-1)
        self.proxy.setFilterRegularExpression(
            QRegularExpression(re.escape(text), QRegularExpression.CaseInsensitiveOption))
        self._update_info()

    def filter_exact(self, column: int, value: str):
        """Tampilkan hanya baris yang nilai kolomnya persis sama (dipakai untuk bukti per case)."""
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.proxy.setFilterKeyColumn(column)
        self.proxy.setFilterRegularExpression(QRegularExpression("^" + re.escape(value) + "$"))
        self._update_info()

    def clear_filter(self):
        self.search.clear()
        self._on_search("")

    def _update_info(self):
        self.info.setText(f"{self.proxy.rowCount():,} / {self.model.rowCount():,} baris")

    def selected_value(self, column: int = 0):
        idx = self.view.selectionModel().selectedRows(column) if self.view.selectionModel() else []
        if not idx:
            return None
        src = self.proxy.mapToSource(idx[0])
        return self.model.df.iat[src.row(), column]
