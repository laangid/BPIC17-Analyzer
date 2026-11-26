# BPIC17 Event Log Analyzer

Aplikasi desktop Python + PM4Py untuk menjawab **Exercise 11.7 (A–E), 11.15, 11.18, dan 11.22**
(Dumas et al., *Fundamentals of Business Process Management*, Bab 11) dari event log
**BPI Challenge 2017**. Aplikasi ini dibuat untuk Proyek Tahap 1 mata kuliah Process Mining.

Semua jawaban dihitung langsung dari file XES yang dipilih pengguna. Tidak ada angka yang ditulis
manual di kode. Setiap jawaban disertai aturan filter, denominator, daftar case ID, dan event bukti.

---

## 1. Instalasi (Windows + VS Code)

Prasyarat: **Python 3.10 atau lebih baru** dan **Git** (opsional).

1. Ambil proyek dari GitHub, pilih salah satu:
   - `git clone https://github.com/laangid/BPIC17-Analyzer.git`, atau
   - di halaman repo klik **Code → Download ZIP**, lalu extract.
2. Buka folder `BPIC17-Analyzer` di VS Code (**File → Open Folder**).
3. Buka terminal (**Terminal → New Terminal**). Klik panah **˅** di sebelah tombol **+** pada panel terminal,
   lalu pilih **Command Prompt**. Jangan pakai PowerShell, karena perintah `activate` sering diblokir di sana.
4. Jalankan:

   ```bash
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

   Pastikan `(venv)` muncul di awal baris terminal. Proses `pip install` butuh beberapa menit.
   Jika `python` tidak dikenali, ganti dengan `py`.
5. (Opsional) Cek instalasi: `python -m pytest -v` → harus **19 passed**.
6. Jalankan aplikasi: `python main.py`

> Setiap membuka terminal baru, aktifkan lagi venv dengan `venv\Scripts\activate`.
> **Dataset BPIC17 tidak disertakan di repo** karena ukurannya besar. Unduh sesuai bagian 2,
> lalu taruh di folder `data/`.

## 2. Dataset

Unduh **`BPI Challenge 2017.xes.gz`** (sekitar 29,6 MB) dari 4TU.ResearchData:
https://data.4tu.nl/articles/dataset/BPI_Challenge_2017/12696884
(DOI: 10.4121/uuid:5f3067df-f10b-45da-b98b-86ae4c7a310b).
Gunakan log aplikasi utama, **bukan** "BPI Challenge 2017 – Offer log".

File `.xes.gz` dapat dibuka langsung tanpa di-extract. Simpan, misalnya, di folder `data/`.
Pembacaan BPIC17 (sekitar 1,2 juta event) membutuhkan waktu sekitar 1–3 menit dan RAM sekitar 4–8 GB.

## 3. Cara pakai (alur demo)

1. **Dataset & Status** → *Buka file XES...* → pilih file BPIC17. Halaman ini menampilkan status baca,
   jumlah case/event, atribut, dan hasil validasi.
2. **Overview** → total case/event, frekuensi aktivitas, aktivitas × lifecycle, rentang waktu,
   rata-rata/median cycle time, tabel durasi per case.
3. **Exercise 11.7** → *Jalankan analisis 11.7* → tab A–E.
4. **Exercise 11.15 & 11.18** → *Jalankan* → tab 11.15 dan 11.18.
5. **Exercise 11.22** → *Jalankan* → jumlah, persentase, denominator, pasangan event O_Cancelled → O_Accepted.
6. Di setiap halaman soal, pilih satu case untuk memfilter **bukti event**. Klik ganda (atau
   *Buka rincian case*) untuk membuka **Case Explorer**: urutan event lengkap, durasi, dan daftar
   soal yang diloloskan atau tidak diloloskan oleh case tersebut.
7. **Export** → *Jalankan semua & ekspor CSV* (ringkasan semua jawaban + daftar case + bukti event
   per soal). Ekspor per soal juga tersedia lewat tombol *Export CSV...* di setiap halaman soal.
8. **File → Muat log sintetis (edge case)** → memuat log uji kecil berisi 11 skenario edge case.

Mode tanpa GUI (opsional, berguna untuk laporan):

```bash
python main.py --cli "data/BPI Challenge 2017.xes.gz" --out hasil
```

## 4. Struktur folder

```
BPIC17-Analyzer/
├── main.py                  # entry point (GUI / --cli)
├── requirements.txt
├── README.md
├── analyzer/                # mesin analisis, tanpa GUI
│   ├── loader.py            # F01  impor XES via pm4py.read_xes + validasi + urutan event
│   ├── core.py              # fungsi primitif bersama (durasi, contains, endpoint, complete, ...)
│   ├── overview.py          # F02  statistik dasar
│   ├── exercises.py         # F03–F06  Exercise 11.7, 11.15, 11.18, 11.22
│   ├── result.py            # format hasil standar (AnalysisResult)
│   ├── export.py            # F07  ekspor CSV
│   └── cli.py               # mode command-line
├── gui/                     # PySide6
│   ├── main_window.py       # sidebar + semua halaman + Case Explorer + Export + About
│   ├── result_view.py       # tampilan generik satu hasil soal (jawaban, aturan, case, bukti)
│   ├── table_model.py       # tabel pandas + pencarian
│   └── worker.py            # background thread (GUI tidak membeku)
├── tests/
│   ├── synthetic_log.py     # generator log sintetis edge case
│   └── test_exercises.py    # 19 unit test (pytest)
└── data/
    └── synthetic_edge_cases.xes
```

## 5. Pemetaan soal → fungsi

| Soal | Fungsi | Aturan |
|---|---|---|
| 11.7 A | `exercises.analyze_117` | jumlah `case:concept:name` unik |
| 11.7 B | `core.case_durations` | mean (event terakhir − event pertama) per case, hari |
| 11.7 C | `core.cases_containing("O_Accepted")` | **contains** |
| 11.7 D | `core.cases_containing("O_Refused")` | **contains** (tidak eksklusif dengan C) |
| 11.7 E | `core.cases_ending_with("O_Cancelled")` | **endpoint**: event terakhir trace |
| 11.15 | `core.cases_with_min_complete` | ≥ 2 event `W_Assess potential fraud` dengan lifecycle `complete` |
| 11.18 | `core.same_resource_repeats` | ≥ 2 complete oleh `org:resource` identik dan tidak kosong |
| 11.22 | `core.eventually_follows` | ada i < j: event i = O_Cancelled, event j = O_Accepted |

## 6. Definisi operasional & keputusan implementasi

- **Urutan event dalam trace**: diurutkan berdasarkan `time:timestamp` (ascending). Jika timestamp sama,
  urutan asli di file XES dipertahankan (stable sort). Diuji pada skenario `S11_same_timestamp_tie`.
- **Cycle time** dihitung dari trace **utuh**. Filter hanya memilih case dan tidak menghapus event,
  sehingga durasi tidak berubah karena filter.
- **Level case**: satu case dihitung sekali walaupun event pemicunya muncul berkali-kali.
- **Complete occurrence**: `lifecycle:transition == "complete"`. Status `schedule`, `start`, `suspend`,
  `resume`, `ate_abort`, dan `withdraw` tidak dihitung. Halaman 11.15 menampilkan semua event aktivitas
  tersebut beserta kolom *Dihitung (complete)?* sebagai bukti.
- **Nama aktivitas**: soal menulis "W_Assess Potential Fraud", sedangkan BPIC17 memakai
  "W_Assess potential fraud". Pencocokan nama tidak membedakan huruf besar/kecil, dan nama yang
  dipakai ditampilkan di hasil.
- **Resource kosong**: `org:resource` kosong atau tidak ada dinormalisasi menjadi NA lalu dibuang sebelum
  pengelompokan 11.18, sehingga tidak pernah dianggap "resource yang sama".
- **11.22** dianalisis pada level case/trace (bukan level offer ID). Persentase = case cocok ÷ seluruh case
  pada log aktif × 100%, dan denominatornya ditampilkan.
- **Validasi silang PM4Py**: setiap jawaban dihitung dengan pandas di atas DataFrame hasil `pm4py.read_xes`,
  lalu dibandingkan dengan filter bawaan PM4Py: `filter_event_attribute_values(level="case")`,
  `filter_end_activities`, `filter_activities_rework` (pada event complete),
  `filter_eventually_follows_relation`, dan `get_all_case_durations`. Hasil perbandingan tampil di setiap
  jawaban. 11.18 tidak memiliki filter bawaan yang setara.

## 7. Pengujian

```bash
python -m pytest -v
```

Log sintetis (`tests/synthetic_log.py`) mencakup seluruh skenario uji di instruksi bagian 8:

| Skenario | Hasil yang diuji |
|---|---|
| S01 O_Accepted dua kali | 11.7 C menghitung case sekali |
| S02 O_Cancelled di tengah lalu event lain | tidak lolos 11.7 E |
| S03 O_Refused dan O_Accepted | lolos C dan D |
| S04 fraud dijadwalkan 2×, complete 1× | tidak lolos 11.15 |
| S05 dua complete, resource berbeda | lolos 11.15, tidak lolos 11.18 |
| S06 dua complete, resource sama | lolos 11.15 dan 11.18 |
| S07 O_Cancelled → event lain → O_Accepted | lolos 11.22 (tidak bertetangga) |
| S08 O_Accepted → O_Cancelled (akhir) | tidak lolos 11.22, lolos 11.7 E |
| S09 dua complete tanpa resource | lolos 11.15, tidak lolos 11.18 |
| S10 O_Refused → O_Cancelled (akhir) | lolos D dan E |
| S11 timestamp sama | urutan file dipertahankan |

Test lain: impor `.xes` dan `.xes.gz`, file rusak, atribut wajib hilang, durasi per case, konsistensi
Overview vs 11.7 B, validasi silang PM4Py, dan reproduktibilitas (impor ulang → hasil identik).
Performa diuji pada log sintetis berukuran BPIC17 (31.509 case, ±1,2 juta event): seluruh analisis
selesai dalam ±11 detik setelah log dimuat.

## 8. Pembanding dengan materi (BPIC-2017.pdf)

| Soal | Jawaban materi | Catatan |
|---|---|---|
| 11.7 A | 31.509 case | |
| 11.7 B | 21,9 hari | |
| 11.7 C | 17.228 case, 18,1 hari | |
| 11.7 D | 3.720 case, 16,8 hari | |
| 11.7 E | 4.436 case, 23 hari | |
| 11.15 | 13 case (Celonis, complete-only) | Disco: 20 case karena ikut menghitung schedule/start/abort |
| 11.18 | 3 case (Celonis) | Disco v2.0: 8 case |
| 11.22 | (tidak ada kunci jawaban) | |

Selisih kecil dengan materi dapat terjadi karena perbedaan alat (Disco/Celonis) dalam menangani lifecycle,
pembulatan, dan definisi durasi. Penjelasannya perlu dicatat di laporan pengujian.

## 9. Keterbatasan

- Pembacaan XES berukuran besar memakan waktu dan memori. Progres ditampilkan di status bar.
- `User_1` di BPIC17 adalah akun sistem/otomatis, tetapi tetap diperlakukan sebagai resource valid
  (tidak kosong) sesuai definisi soal.
- Analisis 11.22 tidak membedakan offer ID. Interpretasi per offer bukan bagian dari jawaban soal.
- Process discovery (Alpha/Heuristics/Inductive Miner, Petri net) di luar cakupan Tahap 1.

## 10. Lingkungan yang diuji

Python 3.13, PM4Py 2.7.23, pandas 3.0, PySide6 6.12. Versi saat dijalankan ditampilkan di menu **About**.
