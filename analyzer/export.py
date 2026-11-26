"""Ekspor hasil analisis ke CSV (F07)."""

from __future__ import annotations

import os
import re

import pandas as pd

from .result import AnalysisResult


def _slug(code: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "_", code).strip("_")


def _fmt(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].astype(str)
    return out


def export_summary(results: list, path: str, source_file: str = "") -> str:
    rows = [r.summary_row() for r in results]
    df = pd.DataFrame(rows)
    if source_file:
        df.insert(0, "dataset", source_file)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def export_result(result: AnalysisResult, folder: str, source_file: str = "") -> list:
    """Menyimpan 3 file: ringkasan, daftar case terpilih, dan event bukti."""
    os.makedirs(folder, exist_ok=True)
    base = os.path.join(folder, f"exercise_{_slug(result.code)}")
    paths = [export_summary([result], base + "_ringkasan.csv", source_file)]
    if not result.case_table.empty:
        p = base + "_daftar_case.csv"
        _fmt(result.case_table).to_csv(p, index=False, encoding="utf-8-sig")
        paths.append(p)
    if not result.evidence.empty:
        p = base + "_bukti_event.csv"
        _fmt(result.evidence).to_csv(p, index=False, encoding="utf-8-sig")
        paths.append(p)
    return paths


def export_dataframe(df: pd.DataFrame, path: str) -> str:
    _fmt(df).to_csv(path, index=False, encoding="utf-8-sig")
    return path
