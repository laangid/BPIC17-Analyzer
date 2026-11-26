"""F01 - Impor dan validasi event log XES menggunakan PM4Py.

Hasil impor adalah objek EventLogData yang berisi pandas DataFrame yang sudah
dinormalisasi:
- kolom standar XES: case:concept:name, concept:name, time:timestamp,
  (opsional) lifecycle:transition, org:resource
- kolom bantu:
    _orig_pos  : posisi event sesuai urutan di file XES (tie-breaker)
    _event_idx : posisi event di dalam trace (0, 1, 2, ...) setelah diurutkan

ATURAN URUTAN EVENT (didokumentasikan sesuai instruksi 7.1):
Event di dalam satu case diurutkan berdasarkan time:timestamp secara ascending.
Jika dua event memiliki timestamp yang sama, urutan aslinya di file XES
dipertahankan (stable sort menggunakan _orig_pos).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

import pandas as pd

CASE_COL = "case:concept:name"
ACT_COL = "concept:name"
TIME_COL = "time:timestamp"
LIFE_COL = "lifecycle:transition"
RES_COL = "org:resource"

REQUIRED_COLS = [CASE_COL, ACT_COL, TIME_COL]
OPTIONAL_COLS = [LIFE_COL, RES_COL]


class LogValidationError(Exception):
    """Dilempar jika file tidak bisa dibaca atau atribut wajib tidak ada."""


@dataclass
class EventLogData:
    df: pd.DataFrame
    path: str
    load_seconds: float = 0.0
    has_lifecycle: bool = False
    has_resource: bool = False
    validation: list = field(default_factory=list)  # list of (check, ok, detail)
    warnings: list = field(default_factory=list)

    @property
    def filename(self) -> str:
        return os.path.basename(self.path)

    @property
    def n_cases(self) -> int:
        return int(self.df[CASE_COL].nunique())

    @property
    def n_events(self) -> int:
        return int(len(self.df))

    @property
    def attributes(self) -> list:
        return [c for c in self.df.columns if not c.startswith("_")]


def _report(cb: Optional[Callable[[str], None]], msg: str) -> None:
    if cb is not None:
        cb(msg)


def load_xes(path: str, progress: Optional[Callable[[str], None]] = None) -> EventLogData:
    """Membaca file .xes atau .xes.gz dengan pm4py.read_xes lalu memvalidasi atributnya."""
    if not path or not os.path.isfile(path):
        raise LogValidationError(f"File tidak ditemukan: {path}")
    lower = path.lower()
    if not (lower.endswith(".xes") or lower.endswith(".xes.gz")):
        raise LogValidationError("Format file harus .xes atau .xes.gz")

    import pm4py  # import di sini agar GUI tetap cepat terbuka

    _report(progress, f"Membaca {os.path.basename(path)} dengan PM4Py (bisa beberapa menit untuk BPIC17)...")
    t0 = time.time()
    try:
        df = pm4py.read_xes(path)
    except Exception as exc:  # file rusak / bukan XES valid
        raise LogValidationError(f"PM4Py gagal membaca file XES: {exc}") from exc
    if not isinstance(df, pd.DataFrame):
        df = pm4py.convert_to_dataframe(df)
    if df is None or len(df) == 0:
        raise LogValidationError("Event log kosong (tidak ada event).")

    _report(progress, "Memvalidasi atribut...")
    data = prepare_dataframe(df, path)
    data.load_seconds = time.time() - t0
    _report(progress, f"Selesai: {data.n_cases:,} case, {data.n_events:,} event ({data.load_seconds:.1f} detik).")
    return data


def prepare_dataframe(df: pd.DataFrame, path: str = "<memory>") -> EventLogData:
    """Validasi atribut wajib, normalisasi tipe data, dan urutkan event per case."""
    validation = []
    warnings = []

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    for c in REQUIRED_COLS:
        validation.append((f"Atribut wajib '{c}'", c in df.columns,
                           "tersedia" if c in df.columns else "TIDAK ADA"))
    if missing:
        raise LogValidationError(
            "Atribut wajib tidak tersedia: " + ", ".join(missing)
            + ". Pastikan file adalah event log XES dengan case ID, concept:name, dan time:timestamp.")

    df = df.copy()
    df["_orig_pos"] = range(len(df))

    # Normalisasi timestamp
    if not pd.api.types.is_datetime64_any_dtype(df[TIME_COL]):
        df[TIME_COL] = pd.to_datetime(df[TIME_COL], utc=True, errors="coerce", format="mixed")
    n_bad_ts = int(df[TIME_COL].isna().sum())
    if n_bad_ts:
        warnings.append(f"{n_bad_ts} event tidak memiliki timestamp valid dan diabaikan dalam perhitungan durasi.")

    df[CASE_COL] = df[CASE_COL].astype(str)
    df[ACT_COL] = df[ACT_COL].astype(str)

    has_life = LIFE_COL in df.columns
    has_res = RES_COL in df.columns
    validation.append(("Atribut lifecycle:transition", has_life,
                       "terdeteksi" if has_life else "tidak ada (semua event dianggap complete)"))
    validation.append(("Atribut org:resource", has_res,
                       "terdeteksi" if has_res else "tidak ada (analisis 11.18 tidak dapat dilakukan)"))
    if not has_life:
        warnings.append("lifecycle:transition tidak ada: semua event dianggap 'complete'.")
    if not has_res:
        warnings.append("org:resource tidak ada: Exercise 11.18 tidak dapat dihitung.")

    if has_life:
        df[LIFE_COL] = df[LIFE_COL].astype("string")
    if has_res:
        # Resource kosong ("" / spasi / NaN) dinormalisasi menjadi NA eksplisit
        res = df[RES_COL].astype("string").str.strip()
        res = res.mask(res == "", pd.NA)
        df[RES_COL] = res

    # Urutan event: per case, timestamp ascending, tie -> urutan asli di file
    df = df.sort_values([CASE_COL, TIME_COL, "_orig_pos"], kind="mergesort").reset_index(drop=True)
    df["_event_idx"] = df.groupby(CASE_COL, sort=False).cumcount()

    validation.append(("Jumlah case > 0", df[CASE_COL].nunique() > 0, f"{df[CASE_COL].nunique():,} case"))
    validation.append(("Jumlah event > 0", len(df) > 0, f"{len(df):,} event"))

    return EventLogData(df=df, path=path, has_lifecycle=has_life, has_resource=has_res,
                        validation=validation, warnings=warnings)
