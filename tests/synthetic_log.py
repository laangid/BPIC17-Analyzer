"""Generator log sintetis berisi edge case dari tabel skenario uji (instruksi bagian 8).

Jalankan langsung untuk membuat file XES demo:
    python tests/synthetic_log.py            -> data/synthetic_edge_cases.xes
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd

FRAUD = "W_Assess potential fraud"  # ejaan sesuai BPIC17 (huruf kecil), soal menulis "Potential Fraud"
BASE = datetime(2016, 1, 1, 8, 0, tzinfo=timezone.utc)

# Setiap case: list (aktivitas, lifecycle, resource, offset_hari)
# Resource None = atribut tidak ada; "" = string kosong -> keduanya harus dianggap tidak teridentifikasi.
CASES = {
    # 11.7 C: O_Accepted dua kali -> dihitung SEKALI
    "S01_accepted_twice": [
        ("A_Create Application", "complete", "User_1", 0),
        ("O_Accepted", "complete", "User_1", 2),
        ("O_Accepted", "complete", "User_2", 4),
        ("A_Pending", "complete", "User_2", 10),
    ],
    # 11.7 E: O_Cancelled di tengah lalu ada event lain -> BUKAN canceled
    "S02_cancel_middle": [
        ("A_Create Application", "complete", "User_1", 0),
        ("O_Cancelled", "complete", "User_1", 3),
        ("O_Created", "complete", "User_1", 4),
        ("A_Pending", "complete", "User_3", 6),
    ],
    # 11.7 C & D: O_Refused dan O_Accepted -> lolos keduanya
    "S03_refused_and_accepted": [
        ("A_Create Application", "complete", "User_1", 0),
        ("O_Refused", "complete", "User_2", 5),
        ("O_Accepted", "complete", "User_2", 8),
    ],
    # 11.15: dijadwalkan 2x tetapi complete hanya 1x -> TIDAK lolos 11.15
    "S04_fraud_scheduled_twice_complete_once": [
        ("A_Create Application", "complete", "User_1", 0),
        (FRAUD, "schedule", "User_5", 1),
        (FRAUD, "start", "User_5", 1.5),
        (FRAUD, "ate_abort", "User_5", 2),
        (FRAUD, "schedule", "User_5", 3),
        (FRAUD, "start", "User_5", 3.5),
        (FRAUD, "complete", "User_5", 4),
    ],
    # 11.15 lolos, 11.18 tidak: dua complete oleh resource berbeda
    "S05_fraud_two_complete_diff_resource": [
        ("A_Create Application", "complete", "User_1", 0),
        (FRAUD, "start", "User_5", 1),
        (FRAUD, "complete", "User_5", 2),
        (FRAUD, "start", "User_6", 3),
        (FRAUD, "complete", "User_6", 4),
    ],
    # 11.15 dan 11.18 lolos: dua complete oleh resource sama
    "S06_fraud_two_complete_same_resource": [
        ("A_Create Application", "complete", "User_1", 0),
        (FRAUD, "start", "User_7", 1),
        (FRAUD, "complete", "User_7", 2),
        (FRAUD, "start", "User_7", 3),
        (FRAUD, "complete", "User_7", 5),
    ],
    # 11.22 lolos: O_Cancelled -> aktivitas lain -> O_Accepted (tidak bertetangga)
    "S07_cancel_then_accept": [
        ("A_Create Application", "complete", "User_1", 0),
        ("O_Cancelled", "complete", "User_1", 2),
        ("O_Created", "complete", "User_2", 3),
        ("O_Accepted", "complete", "User_2", 7),
    ],
    # 11.22 TIDAK lolos: O_Accepted lalu O_Cancelled tanpa accepted sesudahnya; 11.7 E lolos
    "S08_accept_then_cancel_end": [
        ("A_Create Application", "complete", "User_1", 0),
        ("O_Accepted", "complete", "User_1", 2),
        ("O_Cancelled", "complete", "User_1", 12),
    ],
    # 11.15 lolos, 11.18 TIDAK: dua complete tanpa resource (kosong / tidak ada)
    "S09_fraud_two_complete_empty_resource": [
        ("A_Create Application", "complete", "User_1", 0),
        (FRAUD, "complete", None, 1),
        (FRAUD, "complete", "", 2),
    ],
    # 11.7 E lolos (berakhir O_Cancelled), juga D (mengandung O_Refused)
    "S10_refused_then_cancel_end": [
        ("A_Create Application", "complete", "User_1", 0),
        ("O_Refused", "complete", "User_4", 1),
        ("O_Cancelled", "complete", "User_4", 3),
    ],
    # Timestamp sama: urutan asli file dipertahankan -> event terakhir O_Cancelled
    "S11_same_timestamp_tie": [
        ("A_Create Application", "complete", "User_1", 0),
        ("O_Accepted", "complete", "User_1", 1),
        ("O_Cancelled", "complete", "User_1", 1),
    ],
}

# Jawaban yang benar untuk log sintetis di atas (dipakai unit test)
EXPECTED = {
    "total_cases": 11,
    "117C": {"S01_accepted_twice", "S03_refused_and_accepted", "S07_cancel_then_accept",
             "S08_accept_then_cancel_end", "S11_same_timestamp_tie"},
    "117D": {"S03_refused_and_accepted", "S10_refused_then_cancel_end"},
    "117E": {"S08_accept_then_cancel_end", "S10_refused_then_cancel_end", "S11_same_timestamp_tie"},
    "1115": {"S05_fraud_two_complete_diff_resource", "S06_fraud_two_complete_same_resource",
             "S09_fraud_two_complete_empty_resource"},
    "1118": {"S06_fraud_two_complete_same_resource"},
    "1122": {"S07_cancel_then_accept"},
}


def build_dataframe() -> pd.DataFrame:
    rows = []
    for case_id, events in CASES.items():
        for act, life, res, offset in events:
            row = {"case:concept:name": case_id, "concept:name": act,
                   "lifecycle:transition": life,
                   "time:timestamp": BASE + timedelta(days=offset)}
            if res is not None:
                row["org:resource"] = res
            rows.append(row)
    return pd.DataFrame(rows)


def expected_durations() -> dict:
    return {c: max(e[3] for e in ev) - min(e[3] for e in ev) for c, ev in CASES.items()}


def write_xes(path: str) -> str:
    import pm4py
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    pm4py.write_xes(build_dataframe(), path)
    return path


if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, "data", "synthetic_edge_cases.xes")
    print("Ditulis:", write_xes(out))
