import pytest
import pandas as pd
from backend.services import session_manager as sm
from backend.analysis import run_full_analysis


def test_cross_category_detection_and_resolution(client):
    """Test column that is all integers except a few floats:
    1. Confirm detection flags same cells across categories (Data-Type Issues, Suspicious/Outliers)
    2. Confirm resolving them in one place clears them from all others
    3. Confirm 'keep' decision in one category stops re-flagging in another
    4. Confirm quality score updates without double penalizing
    """
    sid = sm.new_session()

    # Column with integers, plus a float that is also statistically extreme (5000.5)
    # and a float that is nearby (25.5)
    # [10, 20, 30, 25.5, 5000.5, 40, 50, 60, 70, 80]
    vals = [10, 20, 30, 25.5, 5000.5, 40, 50, 60, 70, 80]
    df = pd.DataFrame({
        "num_col": vals,
        "name": [f"Item {i}" for i in range(len(vals))]
    })
    sm.set_original(sid, "single", df, {"filename": "test.csv"})

    # 1. Analyze initial state
    res = client.post("/api/analyze", json={"session_id": sid, "dataset": "single"})
    assert res.status_code == 200
    analysis = res.get_json()["analysis"]

    # Verify type issues flags num_col (FLOAT_IN_INTEGER) with affected rows 3 and 4
    type_issues = analysis["types"]["type_issues"]
    assert any(ti["column"] == "num_col" and 3 in ti["affected_indices"] and 4 in ti["affected_indices"] for ti in type_issues)

    # Verify suspicious values flags row 4 (5000.5)
    susp_issues = analysis["suspicious"]["suspicious_issues"]
    assert any(si["column"] == "num_col" and 4 in si["indices"] for si in susp_issues)

    # Verify outliers flags row 4 (5000.5)
    outlier_details = analysis["outliers"]["outlier_details"]
    assert any(od["column"] == "num_col" and 4 in od["combined_indices"] for od in outlier_details)

    # Verify affected-rows returns cross-category tags ("also flagged as: ...")
    aff_res = client.post("/api/dataset/affected-rows", json={
        "session_id": sid,
        "dataset": "single",
        "indices": [3, 4]
    })
    assert aff_res.status_code == 200
    aff_data = aff_res.get_json()
    row_4_rec = next(r for r in aff_data["records"] if r["_row_id"] == 4)
    # Row 4 is flagged across categories!
    assert len(row_4_rec["_also_flagged"]) > 1

    # 2. Test shared "Keep" decision: Keep row 4 in suspicious values
    keep_res = client.post("/api/clean/resolve-suspicious", json={
        "session_id": sid,
        "dataset": "single",
        "column": "num_col",
        "resolution": "keep",
        "row_indices": [4]
    })
    assert keep_res.status_code == 200
    post_keep_analysis = keep_res.get_json()["analysis"]

    # In post_keep_analysis, row 4 must NOT be flagged as suspicious or outlier anymore!
    assert not any(si["column"] == "num_col" and 4 in si.get("indices", []) for si in post_keep_analysis["suspicious"]["suspicious_issues"])
    assert not any(od["column"] == "num_col" and 4 in od.get("combined_indices", []) for od in post_keep_analysis["outliers"]["outlier_details"])

    # 3. Resolve float row 3 via row-level type conversion (round-half-up: 25.5 -> 26)
    conv_row_res = client.post("/api/clean/resolve-type-rows", json={
        "session_id": sid,
        "dataset": "single",
        "column": "num_col",
        "action": "convert",
        "target_type": "int64",
        "row_indices": [3]
    })
    assert conv_row_res.status_code == 200
    working_df = sm.get_working_df(sid, "single")
    assert working_df.at[3, "num_col"] == 26

    # 4. Resolve remaining row 4 via whole-column conversion to int64 or row edit
    # Whole-column conversion should round 5000.5 to 5001 and convert column cleanly to int64
    conv_col_res = client.post("/api/clean/resolve-type-rows", json={
        "session_id": sid,
        "dataset": "single",
        "column": "num_col",
        "action": "convert_all_int"
    })
    assert conv_col_res.status_code == 200
    final_analysis = conv_col_res.get_json()["analysis"]

    # The column now has NO type issues, NO suspicious values, NO outliers!
    assert not any(ti["column"] == "num_col" for ti in final_analysis["types"]["type_issues"])
    assert not any(si["column"] == "num_col" for si in final_analysis["suspicious"]["suspicious_issues"])
    assert not any(od["column"] == "num_col" for od in final_analysis["outliers"]["outlier_details"])

    # Quality score should reflect improved health
    assert final_analysis["quality_score"]["score"] > analysis["quality_score"]["score"]


def test_stable_row_indices_on_deletion(client):
    """Verify that deleting rows preserves stable original row indices for remaining rows."""
    sid = sm.new_session()
    df = pd.DataFrame({
        "num": [100, 200, 300, 400, 500],
        "txt": ["A", "B", "C", "D", "E"]
    })
    sm.set_original(sid, "single", df, {"filename": "test.csv"})

    # Delete row 1 (index 1)
    del_res = client.post("/api/clean/delete-rows", json={
        "session_id": sid,
        "dataset": "single",
        "row_indices": [1]
    })
    assert del_res.status_code == 200

    working_df = sm.get_working_df(sid, "single")
    assert list(working_df.index) == [0, 2, 3, 4]
    # Row 3 is still row 3, with value 400!
    assert working_df.loc[3, "num"] == 400
