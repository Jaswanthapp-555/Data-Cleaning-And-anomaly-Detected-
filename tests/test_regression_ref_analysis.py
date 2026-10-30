"""Regression test for shared analysis engine bug (single positional indexer is out-of-bounds).

Tests:
1. Two Dataset mode ("ref" and "cur") and Single Dataset mode ("single").
2. Row deletions creating non-contiguous indices (e.g. index labels > len(df)).
3. All-empty (all NaN / NaT) columns.
4. Data-type conversions to all supported types (float64, int64, str, datetime64).
5. Safe preview of conversions turning values to blanks and prevention of silent column erasure.
6. Reset to Original.
7. Full analysis endpoint (/api/analyze), issue center list, and /api/analysis/result.
"""
import pytest
import io
import pandas as pd
import numpy as np

from backend.analysis import run_full_analysis
from backend.services import session_manager as sm
from backend.cleaning import cleaning_engine as ce
from backend.analysis.type_analyzer import preview_type_conversion


def _create_sample_csv_with_all_types():
    # 300 rows so after deletions it can be reduced to 274 rows
    rows = ["id,numeric_val,float_val,text_val,date_val"]
    for i in range(300):
        rows.append(f"{i},{i * 2},{i * 1.5 + 0.5},Category_{i % 5},2024-01-{(i % 28) + 1:02d}")
    return "\n".join(rows).encode("utf-8")


@pytest.mark.parametrize("dataset_mode", ["single", "ref", "cur"])
def test_full_analysis_after_row_deletions_no_out_of_bounds(client, dataset_mode):
    """Test that after row deletions reducing dataset (e.g. 300 rows down to 274 rows),
    the shared analysis engine does not fail with 'single positional indexer is out-of-bounds'."""
    sid = sm.new_session()
    csv_bytes = _create_sample_csv_with_all_types()

    # Upload file
    upload_res = client.post(
        "/api/upload/file",
        data={"file": (io.BytesIO(csv_bytes), "sample.csv"), "dataset": dataset_mode},
        content_type="multipart/form-data",
        headers={"X-Session-Id": sid},
    )
    assert upload_res.status_code == 200

    # Delete 26 rows (from 300 down to 274 rows)
    rows_to_delete = list(range(10, 36))
    del_res = client.post(
        "/api/clean/delete-rows",
        json={"session_id": sid, "dataset": dataset_mode, "row_indices": rows_to_delete},
    )
    assert del_res.status_code == 200
    assert del_res.get_json()["new_row_count"] == 274

    # Run full analysis
    an_res = client.post("/api/analyze", json={"session_id": sid, "dataset": dataset_mode})
    assert an_res.status_code == 200, an_res.get_json()
    an_data = an_res.get_json()["analysis"]
    assert "issue_center" in an_data
    assert "stats" in an_data
    assert "outliers" in an_data

    # Fetch analysis result (used by Cleaning Studio and Issue Center)
    res_get = client.get(f"/api/analysis/result?session_id={sid}&dataset={dataset_mode}")
    assert res_get.status_code == 200, res_get.get_json()
    res_data = res_get.get_json()["analysis"]
    assert res_data is not None
    assert "issue_center" in res_data


@pytest.mark.parametrize("dataset_mode", ["single", "ref", "cur"])
def test_all_empty_column_handled_gracefully(client, dataset_mode):
    """Test that all-empty columns (all NaN) do not crash any analysis module,
    show 'Insufficient data for reliable analysis' in stats, and are flagged in issue center."""
    sid = sm.new_session()
    df = pd.DataFrame({
        "id": [1, 2, 3, 4, 5],
        "all_nan_col": [np.nan, np.nan, np.nan, np.nan, np.nan],
        "category": ["A", "B", "A", "B", "A"],
    })
    # Introduce row deletion to test non-contiguous index with empty column
    df = df.drop(index=[1, 3])
    sm.set_original(sid, dataset_mode, df, {"filename": "test.csv"})

    an_res = client.post("/api/analyze", json={"session_id": sid, "dataset": dataset_mode})
    assert an_res.status_code == 200, an_res.get_json()
    analysis = an_res.get_json()["analysis"]

    # Issue center should have FULLY_EMPTY_COLUMN
    issues = analysis["issue_center"]
    empty_issues = [i for i in issues if i.get("column") == "all_nan_col"]
    assert len(empty_issues) >= 1
    assert any("empty" in i["description"].lower() or "missing" in i["description"].lower() for i in empty_issues)

    # Stats should indicate insufficient data
    stats = analysis["stats"]
    all_col_stats = stats.get("numerical", []) + stats.get("categorical", [])
    empty_stat = [s for s in all_col_stats if s.get("column") == "all_nan_col"]
    assert len(empty_stat) >= 1
    assert empty_stat[0].get("insufficient_data") is True
    assert "insufficient data" in empty_stat[0].get("message", "").lower()

    # Cleaning Studio endpoint must succeed
    res_get = client.get(f"/api/analysis/result?session_id={sid}&dataset={dataset_mode}")
    assert res_get.status_code == 200


@pytest.mark.parametrize("dataset_mode", ["single", "ref"])
def test_conversions_to_each_supported_type_and_reset(client, dataset_mode):
    """Test converting columns to float64, int64, str, datetime64 followed by Reset to Original."""
    sid = sm.new_session()
    df = pd.DataFrame({
        "id": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "num_col": ["10", "20", "30", "40", "50", "60", "70", "80", "90", "100"],
        "float_col": [1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5],
        "date_col": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05",
                     "2024-01-06", "2024-01-07", "2024-01-08", "2024-01-09", "2024-01-10"],
    })
    sm.set_original(sid, dataset_mode, df, {"filename": "types.csv"})

    # 1. Convert num_col (text) -> float64
    r1 = client.post("/api/clean/repair-type", json={
        "session_id": sid, "dataset": dataset_mode, "column": "num_col", "target_type": "float64"
    })
    assert r1.status_code == 200, r1.get_json()

    # 2. Convert float_col (float) -> int64
    r2 = client.post("/api/clean/repair-type", json={
        "session_id": sid, "dataset": dataset_mode, "column": "float_col", "target_type": "int64"
    })
    assert r2.status_code == 200, r2.get_json()

    # 3. Convert id (int) -> str
    r3 = client.post("/api/clean/repair-type", json={
        "session_id": sid, "dataset": dataset_mode, "column": "id", "target_type": "str"
    })
    assert r3.status_code == 200, r3.get_json()

    # 4. Convert date_col (text) -> datetime64
    r4 = client.post("/api/clean/repair-type", json={
        "session_id": sid, "dataset": dataset_mode, "column": "date_col", "target_type": "datetime64"
    })
    assert r4.status_code == 200, r4.get_json()

    # Verify analysis result after all conversions
    an_get = client.get(f"/api/analysis/result?session_id={sid}&dataset={dataset_mode}")
    assert an_get.status_code == 200, an_get.get_json()

    # 5. Reset to Original
    reset_res = client.post("/api/clean/reset", json={"session_id": sid, "dataset": dataset_mode})
    assert reset_res.status_code == 200

    # Verify analysis result after reset
    an_after_reset = client.get(f"/api/analysis/result?session_id={sid}&dataset={dataset_mode}")
    assert an_after_reset.status_code == 200, an_after_reset.get_json()
    assert an_after_reset.get_json()["analysis"] is not None


def test_type_conversion_preview_and_protection_against_silent_emptying(client):
    """Test that a conversion which would turn all values into blanks:
    1. Lists those failures in its preview.
    2. Flags will_be_empty=True.
    3. Rejects execution in repair_type rather than silently leaving column empty."""
    sid = sm.new_session()
    df = pd.DataFrame({
        "unparseable_text": ["apple", "banana", "cherry", "date"],
        "valid_nums": [1, 2, 3, 4],
    })
    sm.set_original(sid, "ref", df, {"filename": "test.csv"})

    # Preview converting unparseable text -> float64
    prev_res = client.post("/api/clean/preview-type-conversion", json={
        "session_id": sid, "dataset": "ref", "column": "unparseable_text", "target_type": "float64"
    })
    assert prev_res.status_code == 200
    prev_data = prev_res.get_json()

    # Must list all failures in preview
    assert prev_data["non_convertible_count"] == 4
    assert prev_data["convertible_count"] == 0
    assert len(prev_data["non_convertible_examples"]) == 4
    assert prev_data["will_be_empty"] is True
    assert prev_data["is_safe"] is False

    # Attempting to repair-type must fail with descriptive error rather than silently leaving column empty
    repair_res = client.post("/api/clean/repair-type", json={
        "session_id": sid, "dataset": "ref", "column": "unparseable_text", "target_type": "float64"
    })
    assert repair_res.status_code == 400
    err_msg = repair_res.get_json()["error"]
    assert "entirely empty" in err_msg.lower() or "failed for all values" in err_msg.lower()


def test_no_iloc_with_row_ids_in_inspect_rows(client):
    """Test affected-rows endpoint when row ids are not continuous or when some IDs were deleted."""
    sid = sm.new_session()
    df = pd.DataFrame({"A": [10, 20, 30, 40, 50]})
    # Delete row 0, 1, 2. Remaining rows have index labels [3, 4]
    df = df.drop(index=[0, 1, 2])
    sm.set_original(sid, "ref", df, {"filename": "test.csv"})

    # Request affected-rows with row id 3 and non-existent id 0
    res = client.post("/api/dataset/affected-rows", json={
        "session_id": sid, "dataset": "ref", "indices": [0, 3]
    })
    assert res.status_code == 200
    records = res.get_json()["records"]
    assert len(records) == 1
    assert records[0]["_row_id"] == 3
    assert records[0]["A"] == 40
