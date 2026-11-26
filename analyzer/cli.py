"""Mode command-line (opsional) untuk menjalankan semua analisis tanpa GUI.

Contoh:  python main.py --cli "BPI Challenge 2017.xes.gz" --out hasil/
"""

from __future__ import annotations

import os

from . import export, overview
from .exercises import run_all
from .loader import load_xes


def run_cli(path: str, out_dir: str | None = None) -> list:
    data = load_xes(path, progress=print)
    for check, ok, detail in data.validation:
        print(f"  [{'OK' if ok else '!!'}] {check}: {detail}")
    for w in data.warnings:
        print("  PERINGATAN:", w)

    ov = overview.get_overview(data)
    print(f"\nOverview: {ov.n_cases:,} case, {ov.n_events:,} event, {ov.n_activities} aktivitas, "
          f"{ov.start} s/d {ov.end}, rata-rata cycle time {ov.mean_days:.2f} hari")

    results = run_all(data)
    print()
    for r in results:
        print(f"[{r.code}] {r.answer_text()}")
        print(f"    aturan : {r.rule}")
        print(f"    PM4Py  : {r.pm4py_check}")
        for n in r.notes:
            print(f"    catatan: {n}")
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        export.export_summary(results, os.path.join(out_dir, "ringkasan_semua_jawaban.csv"), data.filename)
        for r in results:
            export.export_result(r, out_dir, data.filename)
        print(f"\nCSV disimpan di: {os.path.abspath(out_dir)}")
    return results
