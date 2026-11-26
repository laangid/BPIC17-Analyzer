"""Mesin analisis event log BPIC17 (tanpa GUI).

Modul:
- loader    : impor XES via PM4Py + validasi atribut + normalisasi urutan event
- core      : fungsi primitif bersama (durasi, contains, endpoint, complete, eventually follows)
- result    : format hasil analisis standar (AnalysisResult)
- overview  : statistik dasar event log (F02)
- exercises : Exercise 11.7 A-E, 11.15, 11.18, 11.22
- export    : ekspor CSV
"""

__version__ = "1.0.0"
