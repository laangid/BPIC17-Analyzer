"""Format hasil analisis standar. Semua soal mengembalikan AnalysisResult
sehingga GUI, Case Explorer, dan ekspor CSV dapat dipakai seragam."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


@dataclass
class AnalysisResult:
    code: str                    # contoh: "11.7 C"
    question: str                # pertanyaan soal
    rule: str                    # aturan/filter yang dipakai (ditampilkan ke pengguna)
    count: int                   # jumlah case yang lolos
    denominator: int             # jumlah seluruh case pada log aktif
    mean_days: Optional[float] = None
    percentage: Optional[float] = None
    case_table: pd.DataFrame = field(default_factory=pd.DataFrame)   # 1 baris per case terpilih
    evidence: pd.DataFrame = field(default_factory=pd.DataFrame)     # event-event pembukti
    notes: list = field(default_factory=list)
    pm4py_check: str = ""        # hasil validasi silang dengan filter bawaan PM4Py

    @property
    def case_ids(self) -> list:
        if self.case_table.empty:
            return []
        return self.case_table.iloc[:, 0].astype(str).tolist()

    def answer_text(self) -> str:
        parts = [f"{self.count:,} case"]
        if self.mean_days is not None:
            parts.append("rata-rata cycle time " + ("-" if pd.isna(self.mean_days) else f"{self.mean_days:.2f} hari"))
        if self.percentage is not None:
            parts.append(f"{self.percentage:.2f}% dari {self.denominator:,} case")
        return ", ".join(parts)

    def summary_row(self) -> dict:
        return {
            "kode": self.code,
            "pertanyaan": self.question,
            "aturan_filter": self.rule,
            "jumlah_case": self.count,
            "denominator": self.denominator,
            "rata2_cycle_time_hari": None if self.mean_days is None else round(self.mean_days, 4),
            "persentase": None if self.percentage is None else round(self.percentage, 4),
            "validasi_pm4py": self.pm4py_check,
            "catatan": " | ".join(self.notes),
        }
