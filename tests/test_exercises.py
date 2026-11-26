"""Unit test semantik filter menggunakan log sintetis edge case.

Jalankan:  python -m pytest -v
"""

import gzip
import os
import shutil
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import synthetic_log as syn  # noqa: E402
from analyzer import core, exercises, overview  # noqa: E402
from analyzer.loader import LogValidationError, load_xes, prepare_dataframe  # noqa: E402


@pytest.fixture(scope="module")
def xes_path(tmp_path_factory):
    p = tmp_path_factory.mktemp("log") / "synthetic.xes"
    return syn.write_xes(str(p))


@pytest.fixture(scope="module")
def data(xes_path):
    # Melalui jalur yang sama dengan aplikasi: tulis XES -> baca dengan PM4Py
    return load_xes(xes_path)


@pytest.fixture(scope="module")
def r117(data):
    return {r.code: r for r in exercises.analyze_117(data)}


def ids(result):
    return set(result.case_ids)


# ---------------------------------------------------------------- loader
def test_load_counts(data):
    assert data.n_cases == syn.EXPECTED["total_cases"]
    assert data.n_events == sum(len(v) for v in syn.CASES.values())
    assert data.has_lifecycle and data.has_resource


def test_load_gzip(xes_path, tmp_path):
    gz = tmp_path / "synthetic.xes.gz"
    with open(xes_path, "rb") as src, gzip.open(gz, "wb") as dst:
        shutil.copyfileobj(src, dst)
    assert load_xes(str(gz)).n_cases == syn.EXPECTED["total_cases"]


def test_missing_file_and_bad_format(tmp_path):
    with pytest.raises(LogValidationError):
        load_xes(str(tmp_path / "tidak_ada.xes"))
    bad = tmp_path / "rusak.xes"
    bad.write_text("<log><trace>ini bukan xes valid")
    with pytest.raises(LogValidationError):
        load_xes(str(bad))


def test_missing_required_attribute():
    df = syn.build_dataframe().drop(columns=["time:timestamp"])
    with pytest.raises(LogValidationError):
        prepare_dataframe(df)


def test_empty_resource_normalized(data):
    ev = data.df[data.df["case:concept:name"] == "S09_fraud_two_complete_empty_resource"]
    fraud = ev[ev["concept:name"] == syn.FRAUD]
    assert fraud["org:resource"].isna().all()


# ---------------------------------------------------------------- durasi
def test_case_durations(data):
    dur = core.case_durations(data.df)["duration_days"]
    for case, exp in syn.expected_durations().items():
        assert dur[case] == pytest.approx(exp)


def test_117_A_B(r117):
    exp = syn.expected_durations()
    assert r117["11.7 A"].count == 11
    assert r117["11.7 B"].mean_days == pytest.approx(sum(exp.values()) / len(exp))


def test_overview_matches_117B(data, r117):
    ov = overview.get_overview(data)
    assert ov.mean_days == pytest.approx(r117["11.7 B"].mean_days)
    assert ov.pm4py_mean_days == pytest.approx(ov.mean_days)


# ---------------------------------------------------------------- 11.7 C/D/E
def test_117C_accepted_twice_counted_once(r117):
    r = r117["11.7 C"]
    assert ids(r) == syn.EXPECTED["117C"]
    assert r.case_ids.count("S01_accepted_twice") == 1


def test_117CD_not_exclusive(r117):
    assert ids(r117["11.7 D"]) == syn.EXPECTED["117D"]
    assert "S03_refused_and_accepted" in ids(r117["11.7 C"]) & ids(r117["11.7 D"])


def test_117C_mean_uses_full_trace(r117):
    exp = syn.expected_durations()
    sel = syn.EXPECTED["117C"]
    assert r117["11.7 C"].mean_days == pytest.approx(sum(exp[c] for c in sel) / len(sel))


def test_117E_endpoint_only(r117):
    r = r117["11.7 E"]
    assert ids(r) == syn.EXPECTED["117E"]
    assert "S02_cancel_middle" not in ids(r)        # O_Cancelled di tengah
    assert "S11_same_timestamp_tie" in ids(r)       # tie -> urutan file dipertahankan


# ---------------------------------------------------------------- 11.15 / 11.18
def test_1115_complete_only(data):
    r = exercises.analyze_1115(data)  # nama soal "Potential Fraud" -> dicocokkan ke "potential fraud"
    assert ids(r) == syn.EXPECTED["1115"]
    assert "S04_fraud_scheduled_twice_complete_once" not in ids(r)
    assert set(r.case_table["jumlah_complete"]) == {2}


def test_1115_comparator_note(data):
    # S04, S05, S06 di-schedule/start >= 2x; hanya S04 yang tidak complete >= 2x
    r = exercises.analyze_1115(data)
    note = [n for n in r.notes if n.startswith("Pembanding")][0]
    assert "3 case" in note and "1 di antaranya" in note


def test_1118_same_resource(data):
    r = exercises.analyze_1118(data)
    assert ids(r) == syn.EXPECTED["1118"]
    assert "S05_fraud_two_complete_diff_resource" not in ids(r)
    assert "S09_fraud_two_complete_empty_resource" not in ids(r)  # resource kosong != sama
    assert ids(r) <= syn.EXPECTED["1115"]


# ---------------------------------------------------------------- 11.22
def test_1122_eventually_follows(data):
    r = exercises.analyze_1122(data)
    assert ids(r) == syn.EXPECTED["1122"]
    assert "S08_accept_then_cancel_end" not in ids(r)
    assert r.denominator == 11
    assert r.percentage == pytest.approx(1 / 11 * 100)
    # bukti: dua event, posisi i < j, tidak bertetangga
    row = r.case_table.iloc[0]
    assert row["posisi_O_Accepted"] - row["posisi_O_Cancelled"] == 2


def test_1122_differs_from_117E(data, r117):
    r = exercises.analyze_1122(data)
    assert ids(r) != ids(r117["11.7 E"])


# ---------------------------------------------------------------- validasi silang PM4Py
def test_pm4py_cross_checks_agree(data):
    for r in exercises.run_all(data):
        assert "BERBEDA" not in r.pm4py_check, (r.code, r.pm4py_check)


def test_reproducible(xes_path):
    a = [r.summary_row() for r in exercises.run_all(load_xes(xes_path))]
    b = [r.summary_row() for r in exercises.run_all(load_xes(xes_path))]
    assert a == b
