"""F02 - Event Log Overview dan statistik dasar."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from . import core
from .loader import ACT_COL, CASE_COL, LIFE_COL, TIME_COL, EventLogData


@dataclass
class Overview:
    n_cases: int
    n_events: int
    n_activities: int
    start: pd.Timestamp
    end: pd.Timestamp
    mean_days: float
    median_days: float
    min_days: float
    max_days: float
    activity_freq: pd.DataFrame     # activity, n_events, n_cases
    lifecycle_freq: pd.DataFrame    # activity x lifecycle
    durations: pd.DataFrame         # case, start, end, n_events, duration_days
    pm4py_mean_days: float = float("nan")


def get_overview(data: EventLogData) -> Overview:
    df = data.df
    dur = core.case_durations(df)

    act = (df.groupby(ACT_COL)
             .agg(n_events=(CASE_COL, "size"), n_cases=(CASE_COL, "nunique"))
             .sort_values("n_events", ascending=False).reset_index())
    act.columns = ["activity", "n_events", "n_cases"]

    if LIFE_COL in df.columns:
        life = (df.assign(_lc=df[LIFE_COL].fillna("(kosong)"))
                  .groupby([ACT_COL, "_lc"]).size().unstack(fill_value=0))
        life.index.name = "activity"
        life = life.reset_index()
    else:
        life = pd.DataFrame()

    # Validasi silang rata-rata cycle time dengan fungsi bawaan PM4Py
    pm_mean = float("nan")
    try:
        import pm4py
        cols = [CASE_COL, ACT_COL, TIME_COL]
        d = pm4py.get_all_case_durations(df[cols])
        if len(d):
            pm_mean = float(sum(d) / len(d)) / core.SECONDS_PER_DAY
    except Exception:
        pass

    durations = dur.reset_index()
    return Overview(
        n_cases=int(df[CASE_COL].nunique()),
        n_events=int(len(df)),
        n_activities=int(df[ACT_COL].nunique()),
        start=df[TIME_COL].min(),
        end=df[TIME_COL].max(),
        mean_days=float(dur["duration_days"].mean()),
        median_days=float(dur["duration_days"].median()),
        min_days=float(dur["duration_days"].min()),
        max_days=float(dur["duration_days"].max()),
        activity_freq=act,
        lifecycle_freq=life,
        durations=durations,
        pm4py_mean_days=pm_mean,
    )
