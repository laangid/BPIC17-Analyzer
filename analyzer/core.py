"""Fungsi primitif bersama. Semua analisis memakai fungsi-fungsi ini agar konsisten.

Semua fungsi menerima DataFrame yang sudah disiapkan oleh loader.prepare_dataframe
(event sudah terurut per case dan memiliki kolom _event_idx).

Prinsip penting:
- Filter pada level CASE: hasil adalah himpunan case ID; satu case dihitung sekali.
- Cycle time SELALU dihitung dari trace utuh (tidak ada event yang dihapus).
"""

from __future__ import annotations

import pandas as pd

from .loader import ACT_COL, CASE_COL, LIFE_COL, RES_COL, TIME_COL

SECONDS_PER_DAY = 86400.0


# ---------------------------------------------------------------- aktivitas
def resolve_activity(df: pd.DataFrame, name: str) -> str:
    """Mencocokkan nama aktivitas tanpa membedakan huruf besar/kecil dan spasi berlebih.

    Contoh: soal menulis "W_Assess Potential Fraud", sedangkan BPIC17 memakai
    "W_Assess potential fraud". Jika tidak ditemukan, nama asli dikembalikan.
    """
    acts = pd.Series(df[ACT_COL].unique())
    if name in set(acts):
        return name
    norm = " ".join(name.lower().split())
    matches = [a for a in acts if " ".join(str(a).lower().split()) == norm]
    return matches[0] if matches else name


def activity_mask(df: pd.DataFrame, activity: str) -> pd.Series:
    return df[ACT_COL] == resolve_activity(df, activity)


def complete_mask(df: pd.DataFrame) -> pd.Series:
    """Event yang merepresentasikan penyelesaian: lifecycle:transition == 'complete'.

    Nilai lain (schedule, start, suspend, resume, ate_abort, withdraw, ...) TIDAK dihitung.
    Jika log tidak memiliki lifecycle, semua event dianggap complete.
    """
    if LIFE_COL not in df.columns:
        return pd.Series(True, index=df.index)
    return df[LIFE_COL].fillna("").str.strip().str.lower() == "complete"


# ---------------------------------------------------------------- durasi
def case_durations(df: pd.DataFrame) -> pd.DataFrame:
    """Durasi tiap case = timestamp event terakhir - timestamp event pertama (trace utuh)."""
    g = df.groupby(CASE_COL, sort=True)[TIME_COL]
    out = pd.DataFrame({"start": g.min(), "end": g.max(), "n_events": g.size()})
    out["duration_days"] = (out["end"] - out["start"]).dt.total_seconds() / SECONDS_PER_DAY
    out.index.name = CASE_COL
    return out


def mean_duration_days(durations: pd.DataFrame, case_ids=None) -> float:
    d = durations if case_ids is None else durations.loc[list(case_ids)]
    return float(d["duration_days"].mean()) if len(d) else float("nan")


# ---------------------------------------------------------------- filter case
def cases_containing(df: pd.DataFrame, activity: str) -> list:
    """Contains: case yang memuat minimal satu event dengan aktivitas tersebut."""
    m = activity_mask(df, activity)
    return sorted(df.loc[m, CASE_COL].unique().tolist())


def last_events(df: pd.DataFrame) -> pd.DataFrame:
    """Event terakhir di setiap trace (berdasarkan urutan trace yang sudah ditetapkan)."""
    return df.groupby(CASE_COL, sort=True).tail(1).set_index(CASE_COL)


def cases_ending_with(df: pd.DataFrame, activity: str) -> list:
    """Endpoint: case yang event TERAKHIR pada trace-nya adalah aktivitas tersebut."""
    act = resolve_activity(df, activity)
    last = last_events(df)
    return sorted(last.index[last[ACT_COL] == act].tolist())


def complete_occurrences(df: pd.DataFrame, activity: str) -> pd.DataFrame:
    """Semua event complete untuk aktivitas tertentu (dipakai 11.15 & 11.18)."""
    return df[activity_mask(df, activity) & complete_mask(df)]


def cases_with_min_complete(df: pd.DataFrame, activity: str, min_occ: int = 2) -> pd.Series:
    """Rework: jumlah complete occurrence per case, hanya case dengan jumlah >= min_occ."""
    counts = complete_occurrences(df, activity).groupby(CASE_COL).size()
    return counts[counts >= min_occ].sort_index()


def same_resource_repeats(df: pd.DataFrame, activity: str, min_occ: int = 2) -> pd.DataFrame:
    """Case di mana >= min_occ complete occurrence dilakukan oleh resource yang SAMA.

    Resource kosong/NA dibuang lebih dulu sehingga dua event tanpa resource
    tidak pernah dianggap dikerjakan oleh resource yang sama.
    Hasil: DataFrame [case, resource, n_by_resource].
    """
    if RES_COL not in df.columns:
        return pd.DataFrame(columns=[CASE_COL, RES_COL, "n_by_resource"])
    ev = complete_occurrences(df, activity)
    ev = ev[ev[RES_COL].notna()]
    g = ev.groupby([CASE_COL, RES_COL]).size().reset_index(name="n_by_resource")
    return g[g["n_by_resource"] >= min_occ].sort_values([CASE_COL, RES_COL]).reset_index(drop=True)


def eventually_follows(df: pd.DataFrame, first: str, second: str) -> pd.DataFrame:
    """Case yang punya posisi i < j dengan event i = first dan event j = second.

    Kedua event tidak harus bersebelahan. Untuk bukti, diambil pasangan:
    O_Cancelled PERTAMA dan O_Accepted pertama SESUDAHNYA.
    Hasil: DataFrame per case dengan posisi & timestamp pasangan bukti.
    """
    a = resolve_activity(df, first)
    b = resolve_activity(df, second)
    cols = [CASE_COL, "_event_idx", TIME_COL]
    ev_a = df.loc[df[ACT_COL] == a, cols]
    ev_b = df.loc[df[ACT_COL] == b, cols]
    first_a = ev_a.groupby(CASE_COL).first()  # first occurrence (data sudah terurut)
    if first_a.empty or ev_b.empty:
        return pd.DataFrame(columns=[CASE_COL, "pos_first", "time_first", "pos_second", "time_second"])
    merged = ev_b.merge(first_a, left_on=CASE_COL, right_index=True, suffixes=("_b", "_a"))
    merged = merged[merged["_event_idx_b"] > merged["_event_idx_a"]]
    pairs = merged.groupby(CASE_COL).first().reset_index()
    pairs = pairs.rename(columns={"_event_idx_a": "pos_first", f"{TIME_COL}_a": "time_first",
                                  "_event_idx_b": "pos_second", f"{TIME_COL}_b": "time_second"})
    return pairs[[CASE_COL, "pos_first", "time_first", "pos_second", "time_second"]].sort_values(CASE_COL).reset_index(drop=True)


def case_trace(df: pd.DataFrame, case_id: str) -> pd.DataFrame:
    """Seluruh event dari satu case, terurut sesuai urutan trace."""
    return df[df[CASE_COL] == str(case_id)].sort_values("_event_idx")
