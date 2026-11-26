"""Analisis soal wajib: Exercise 11.7 (A-E), 11.15, 11.18, 11.22.

Setiap fungsi:
1. Menghitung jawaban dengan fungsi primitif di core.py (pandas di atas DataFrame dari PM4Py).
2. Memvalidasi silang dengan filter bawaan PM4Py jika tersedia (dicatat di pm4py_check).
3. Mengembalikan AnalysisResult lengkap dengan daftar case dan event bukti.
"""

from __future__ import annotations

import pandas as pd

from . import core
from .loader import ACT_COL, CASE_COL, LIFE_COL, RES_COL, TIME_COL, EventLogData
from .result import AnalysisResult

ACCEPTED = "O_Accepted"
REFUSED = "O_Refused"
CANCELLED = "O_Cancelled"
FRAUD = "W_Assess Potential Fraud"

EVIDENCE_COLS = [CASE_COL, "_event_idx", TIME_COL, ACT_COL, LIFE_COL, RES_COL]


# ---------------------------------------------------------------- helpers
def _evidence_cols(df: pd.DataFrame) -> list:
    return [c for c in EVIDENCE_COLS if c in df.columns]


def _pm4py_df(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in [CASE_COL, ACT_COL, TIME_COL, LIFE_COL, RES_COL] if c in df.columns]
    return df[cols]


def _check(own: int, other) -> str:
    if other is None:
        return "tidak tersedia"
    return f"cocok ({other:,})" if int(other) == int(own) else f"BERBEDA: PM4Py={int(other):,}, aplikasi={own:,}"


def _pm4py_count(fn) -> object:
    try:
        res = fn()
        return int(res[CASE_COL].nunique()) if len(res) else 0
    except Exception:
        return None


def _case_table(durations: pd.DataFrame, case_ids, extra: pd.DataFrame | None = None) -> pd.DataFrame:
    t = durations.loc[list(case_ids), ["start", "end", "n_events", "duration_days"]].reset_index()
    if extra is not None and not extra.empty:
        t = t.merge(extra, on=CASE_COL, how="left")
    return t


# ---------------------------------------------------------------- 11.7
def analyze_117(data: EventLogData, durations: pd.DataFrame | None = None) -> list:
    import pm4py

    df = data.df
    dur = durations if durations is not None else core.case_durations(df)
    total = len(dur)
    pdf = _pm4py_df(df)
    results = []

    # A
    try:
        pm_a = len(pm4py.get_all_case_durations(pdf))
    except Exception:
        pm_a = None
    results.append(AnalysisResult(
        code="11.7 A", question="Berapa jumlah keseluruhan case?",
        rule="Hitung case ID unik (case:concept:name) pada seluruh log.",
        count=total, denominator=total,
        case_table=_case_table(dur, dur.index),
        pm4py_check=_check(total, pm_a)))

    # B
    mean_all = core.mean_duration_days(dur)
    try:
        d = pm4py.get_all_case_durations(pdf)
        pm_b = sum(d) / len(d) / core.SECONDS_PER_DAY
        check_b = "cocok" if abs(pm_b - mean_all) < 1e-6 else f"BERBEDA: PM4Py={pm_b:.4f} hari"
        check_b += f" (PM4Py get_all_case_durations = {pm_b:.4f} hari)"
    except Exception:
        check_b = "tidak tersedia"
    results.append(AnalysisResult(
        code="11.7 B", question="Berapa rata-rata cycle time seluruh case?",
        rule="Cycle time case = timestamp event terakhir - timestamp event pertama (trace utuh); "
             "rata-rata seluruh case, dalam hari.",
        count=total, denominator=total, mean_days=mean_all,
        case_table=_case_table(dur, dur.index), pm4py_check=check_b))

    # C & D: contains
    for code, act, label in [("11.7 C", ACCEPTED, "successful"), ("11.7 D", REFUSED, "unsuccessful")]:
        real = core.resolve_activity(df, act)
        ids = core.cases_containing(df, act)
        ev = df.loc[df[ACT_COL] == real, _evidence_cols(df)]
        occ = ev.groupby(CASE_COL).size().rename(f"jumlah_{real}").reset_index()
        pm = _pm4py_count(lambda: pm4py.filter_event_attribute_values(pdf, ACT_COL, [real], level="case", retain=True))
        results.append(AnalysisResult(
            code=code, question=f"Berapa {label} cases dan rata-rata cycle time-nya?",
            rule=f"CONTAINS: case memuat minimal satu event '{real}'. Case dihitung sekali walau event muncul berkali-kali. "
                 "Durasi dari trace utuh.",
            count=len(ids), denominator=total, mean_days=core.mean_duration_days(dur, ids),
            case_table=_case_table(dur, ids, occ), evidence=ev.reset_index(drop=True),
            notes=["11.7 C dan D tidak saling eksklusif; satu case bisa masuk keduanya."],
            pm4py_check=_check(len(ids), pm)))

    # E: endpoint
    real_c = core.resolve_activity(df, CANCELLED)
    ids = core.cases_ending_with(df, CANCELLED)
    last = core.last_events(df).loc[ids].reset_index()
    ev = last[[c for c in _evidence_cols(df) if c in last.columns]]
    any_cancel = len(core.cases_containing(df, CANCELLED))
    pm = _pm4py_count(lambda: pm4py.filter_end_activities(pdf, [real_c], retain=True))
    results.append(AnalysisResult(
        code="11.7 E", question="Berapa canceled cases dan rata-rata cycle time-nya?",
        rule=f"ENDPOINT: event TERAKHIR pada trace adalah '{real_c}'. Case yang memiliki O_Cancelled "
             "di tengah lalu berlanjut ke event lain TIDAK dihitung.",
        count=len(ids), denominator=total, mean_days=core.mean_duration_days(dur, ids),
        case_table=_case_table(dur, ids), evidence=ev,
        notes=[f"Pembanding: {any_cancel:,} case pernah memuat O_Cancelled di posisi mana pun "
               "(bukan jawaban soal)."],
        pm4py_check=_check(len(ids), pm)))
    return results


# ---------------------------------------------------------------- 11.15
def analyze_1115(data: EventLogData, activity: str = FRAUD, min_occ: int = 2,
                 durations: pd.DataFrame | None = None) -> AnalysisResult:
    import pm4py

    df = data.df
    dur = durations if durations is not None else core.case_durations(df)
    real = core.resolve_activity(df, activity)
    counts = core.cases_with_min_complete(df, activity, min_occ)
    ids = counts.index.tolist()

    # Bukti: semua event aktivitas tsb di case terpilih + penanda mana yang dihitung
    all_ev = df[(df[ACT_COL] == real) & df[CASE_COL].isin(ids)]
    ev = all_ev[_evidence_cols(df)].copy()
    ev["dihitung_complete"] = core.complete_mask(all_ev).values

    extra = counts.rename("jumlah_complete").reset_index()

    # Pembanding (bukan jawaban): aktivitas di-schedule atau di-start >= min_occ kali.
    # Ini mendekati penjelasan buku mengapa Disco menghasilkan angka lebih besar
    # (Disco ikut menghitung occurrence yang di-schedule/start tetapi tidak complete).
    ev_any = df[df[ACT_COL] == real]
    if LIFE_COL in df.columns:
        lc = ev_any[LIFE_COL].fillna("").str.strip().str.lower()
        per_lc = ev_any[lc.isin(["schedule", "start"])].assign(_lc=lc).groupby([CASE_COL, "_lc"]).size()
        loose_ids = set(per_lc[per_lc >= min_occ].reset_index()[CASE_COL])
        loose = len(loose_ids)
        loose_not_complete = len(loose_ids - set(ids))
    else:
        loose, loose_not_complete = len(ids), 0

    # Validasi silang: rework filter PM4Py pada event complete saja
    pdf = _pm4py_df(df[core.complete_mask(df)])
    pm = _pm4py_count(lambda: pm4py.filter_activities_rework(pdf, real, min_occurrences=min_occ))

    notes = [f"Nama aktivitas di log: '{real}'." + ("" if real == activity else f" (dicocokkan dari '{activity}')"),
             "Hanya event dengan lifecycle:transition = 'complete' yang dihitung; "
             "schedule/start/suspend/resume/ate_abort/withdraw diabaikan.",
             f"Pembanding (bukan jawaban): {loose:,} case men-schedule atau men-start '{real}' >= {min_occ}x; "
             f"{loose_not_complete:,} di antaranya TIDAK complete >= {min_occ}x sehingga tidak dihitung "
             "(inilah sebab tool seperti Disco memberi angka lebih besar)."]
    if not data.has_lifecycle:
        notes.append("PERINGATAN: log tidak memiliki lifecycle, semua event dianggap complete.")

    return AnalysisResult(
        code="11.15", question=f"Berapa case dengan '{real}' selesai (complete) minimal {min_occ}x?",
        rule=f"REPEATED COMPLETE: hitung event '{real}' dengan lifecycle 'complete' per case; pilih case dengan jumlah >= {min_occ}.",
        count=len(ids), denominator=len(dur), mean_days=core.mean_duration_days(dur, ids),
        case_table=_case_table(dur, ids, extra), evidence=ev.reset_index(drop=True),
        notes=notes, pm4py_check=_check(len(ids), pm) + " [pm4py.filter_activities_rework pada event complete]")


# ---------------------------------------------------------------- 11.18
def analyze_1118(data: EventLogData, activity: str = FRAUD, min_occ: int = 2,
                 durations: pd.DataFrame | None = None) -> AnalysisResult:
    df = data.df
    dur = durations if durations is not None else core.case_durations(df)
    real = core.resolve_activity(df, activity)

    if not data.has_resource:
        return AnalysisResult(
            code="11.18", question="Berapa case dengan aktivitas selesai minimal 2x oleh resource yang sama?",
            rule="Tidak dapat dihitung: atribut org:resource tidak tersedia.",
            count=0, denominator=len(dur), notes=["org:resource tidak ada di log."])

    pairs = core.same_resource_repeats(df, activity, min_occ)
    ids = sorted(pairs[CASE_COL].unique().tolist())

    comp = core.complete_occurrences(df, activity)
    n_empty = int(comp[RES_COL].isna().sum())
    total_comp = comp.groupby(CASE_COL).size().rename("total_complete")
    extra = (pairs.groupby(CASE_COL)
                  .agg(resource=(RES_COL, lambda s: ", ".join(map(str, s))),
                       jumlah_oleh_resource=("n_by_resource", lambda s: ", ".join(map(str, s))))
                  .join(total_comp).reset_index())

    ev = comp.merge(pairs[[CASE_COL, RES_COL]], on=[CASE_COL, RES_COL])[_evidence_cols(df)]

    rework_cases = core.cases_with_min_complete(df, activity, min_occ)
    notes = [f"Nama aktivitas di log: '{real}'.",
             "Resource kosong/tidak teridentifikasi dibuang sebelum pengelompokan, "
             "sehingga dua event tanpa resource TIDAK dianggap resource yang sama.",
             f"Event complete '{real}' tanpa resource di seluruh log: {n_empty:,}.",
             f"Subset dari 11.15: {len(ids):,} dari {len(rework_cases):,} case 11.15."]
    return AnalysisResult(
        code="11.18", question=f"Berapa case dengan '{real}' selesai minimal {min_occ}x oleh resource yang sama?",
        rule=f"SAME RESOURCE: dalam satu case, >= {min_occ} event '{real}' berstatus 'complete' "
             "memiliki org:resource identik dan tidak kosong.",
        count=len(ids), denominator=len(dur), mean_days=core.mean_duration_days(dur, ids),
        case_table=_case_table(dur, ids, extra), evidence=ev.sort_values([CASE_COL, "_event_idx"]).reset_index(drop=True),
        notes=notes, pm4py_check="tidak ada filter bawaan PM4Py yang setara; dihitung dengan pandas pada DataFrame hasil PM4Py")


# ---------------------------------------------------------------- 11.22
def analyze_1122(data: EventLogData, first: str = CANCELLED, second: str = ACCEPTED,
                 durations: pd.DataFrame | None = None) -> AnalysisResult:
    import pm4py

    df = data.df
    dur = durations if durations is not None else core.case_durations(df)
    a = core.resolve_activity(df, first)
    b = core.resolve_activity(df, second)
    pairs = core.eventually_follows(df, first, second)
    ids = pairs[CASE_COL].tolist()
    total = len(dur)
    pct = (len(ids) / total * 100.0) if total else 0.0

    # Bukti: dua event pasangan (posisi i dan j) per case
    key = pd.concat([pairs[[CASE_COL, "pos_first"]].rename(columns={"pos_first": "_event_idx"}).assign(peran=f"i: {a}"),
                     pairs[[CASE_COL, "pos_second"]].rename(columns={"pos_second": "_event_idx"}).assign(peran=f"j: {b}")])
    ev = df.merge(key, on=[CASE_COL, "_event_idx"])[_evidence_cols(df) + ["peran"]]
    ev = ev.sort_values([CASE_COL, "_event_idx"]).reset_index(drop=True)

    extra = pairs.rename(columns={"pos_first": f"posisi_{a}", "time_first": f"waktu_{a}",
                                  "pos_second": f"posisi_{b}", "time_second": f"waktu_{b}"})
    adjacent = int((pairs["pos_second"] - pairs["pos_first"] == 1).sum()) if len(pairs) else 0

    pdf = _pm4py_df(df)
    pm = _pm4py_count(lambda: pm4py.filter_eventually_follows_relation(pdf, [(a, b)], retain=True))

    return AnalysisResult(
        code="11.22", question=f"Adakah '{a}' yang kemudian diikuti '{b}'? Berapa persentase case-nya?",
        rule=f"EVENTUALLY FOLLOWS: ada posisi i < j dalam trace dengan event i = '{a}' dan event j = '{b}'. "
             "Tidak harus bersebelahan. Persentase = case cocok / seluruh case pada log aktif x 100%.",
        count=len(ids), denominator=total, percentage=pct, mean_days=core.mean_duration_days(dur, ids),
        case_table=_case_table(dur, ids, extra), evidence=ev,
        notes=[("Ya, pola ini terjadi." if ids else "Tidak ditemukan case dengan pola ini."),
               f"Pasangan bukti: '{a}' pertama dan '{b}' pertama sesudahnya. "
               f"Hanya {adjacent:,} case yang pasangannya bersebelahan langsung.",
               "Analisis pada level case/trace (bukan level offer ID)."],
        pm4py_check=_check(len(ids), pm) + " [pm4py.filter_eventually_follows_relation]")


def run_all(data: EventLogData) -> list:
    dur = core.case_durations(data.df)
    out = analyze_117(data, dur)
    out.append(analyze_1115(data, durations=dur))
    out.append(analyze_1118(data, durations=dur))
    out.append(analyze_1122(data, durations=dur))
    return out
