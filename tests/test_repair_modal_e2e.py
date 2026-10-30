import pytest
import pandas as pd
from backend.services import session_manager as sm


def test_mixed_int_float_preview_and_conversion(client):
    """Verify preview and conversion for mixed int/float values (Float -> Int)."""
    sid = sm.new_session()

    # Column with mixed int/float values
    # Rows 1, 4 are whole numbers; rows 2, 3 have decimal fractional parts
    df = pd.DataFrame({
        "mixed_floats": [10.0, 20.5, 30.75, 40.0],
        "category": ["A", "B", "C", "D"],
    })
    sm.set_original(sid, "single", df, {"filename": "test.csv"})

    # 1. Preview conversion to int64
    prev_res = client.post("/api/clean/preview-type-conversion", json={
        "session_id": sid,
        "dataset": "single",
        "column": "mixed_floats",
        "target_type": "int64",
    })
    assert prev_res.status_code == 200
    prev_data = prev_res.get_json()

    assert prev_data["column"] == "mixed_floats"
    assert prev_data["conversion_code"] == "float_to_int"
    assert prev_data["total_values"] == 4
    assert prev_data["convertible_count"] == 4
    assert prev_data["non_convertible_count"] == 0
    # Two values have decimal parts: 20.5 (row 2) and 30.75 (row 3)
    assert prev_data["decimal_loss_count"] == 2
    assert prev_data["is_safe"] is False
    assert any("20.5" in x for x in prev_data["decimal_loss_examples"])
    assert any("30.75" in x for x in prev_data["decimal_loss_examples"])

    # 2. Perform repair-type
    repair_res = client.post("/api/clean/repair-type", json={
        "session_id": sid,
        "dataset": "single",
        "column": "mixed_floats",
        "target_type": "int64",
    })
    assert repair_res.status_code == 200
    repair_data = repair_res.get_json()
    assert repair_data["success"] is True

    working_df = sm.get_working_df(sid, "single")
    assert pd.api.types.is_integer_dtype(working_df["mixed_floats"])
    assert working_df["mixed_floats"].tolist() == [10, 21, 31, 40]


def test_text_with_non_numeric_preview_and_conversion(client):
    """Verify preview shows exact successful vs failed values for text with invalid numbers."""
    sid = sm.new_session()

    # 120 values: 118 valid numbers, 2 non-convertible strings ('N/A' at row 45, 'unknown' at row 78)
    vals = [str(i * 10) for i in range(120)]
    vals[44] = "N/A"      # 1-indexed row 45
    vals[77] = "unknown"  # 1-indexed row 78

    df = pd.DataFrame({"dirty_num_col": vals})
    sm.set_original(sid, "single", df, {"filename": "test.csv"})

    # 1. Preview conversion to int64
    prev_res = client.post("/api/clean/preview-type-conversion", json={
        "session_id": sid,
        "dataset": "single",
        "column": "dirty_num_col",
        "target_type": "int64",
    })
    assert prev_res.status_code == 200
    prev_data = prev_res.get_json()

    assert prev_data["column"] == "dirty_num_col"
    assert prev_data["conversion_code"] == "text_to_int"
    assert prev_data["total_values"] == 120
    assert prev_data["convertible_count"] == 118
    assert prev_data["non_convertible_count"] == 2
    assert any("N/A" in x and "45" in x for x in prev_data["non_convertible_examples"])
    assert any("unknown" in x and "78" in x for x in prev_data["non_convertible_examples"])

    # 2. Perform repair-type
    repair_res = client.post("/api/clean/repair-type", json={
        "session_id": sid,
        "dataset": "single",
        "column": "dirty_num_col",
        "target_type": "int64",
    })
    assert repair_res.status_code == 200
    repair_data = repair_res.get_json()
    assert repair_data["success"] is True

    working_df = sm.get_working_df(sid, "single")
    assert pd.api.types.is_integer_dtype(working_df["dirty_num_col"])
    assert pd.isna(working_df["dirty_num_col"].iloc[44])
    assert pd.isna(working_df["dirty_num_col"].iloc[77])
    assert working_df["dirty_num_col"].iloc[0] == 0
    assert working_df["dirty_num_col"].iloc[1] == 10


def test_tab1_and_issue_center_agreement_datetime(client):
    """Verify Tab 1 and Issue Center both read the same detection result for DATETIME_AS_TEXT,
    and both clear the issue after conversion with each row logged in Change History."""
    sid = sm.new_session()
    # 10 date strings in Transaction_Date stored as object/text
    dates = [f"2023-01-{i:02d}" for i in range(1, 11)]
    df = pd.DataFrame({
        "Transaction_Date": dates,
        "Amount": [100 * i for i in range(1, 11)],
    })
    sm.set_original(sid, "single", df, {"filename": "transactions.csv"})

    # 1. Fetch analysis (what Issue Center reads)
    ana_res = client.get(f"/api/analysis/result?session_id={sid}&dataset=single")
    assert ana_res.status_code == 200
    analysis = ana_res.get_json()["analysis"]
    type_issues = analysis["types"]["type_issues"]
    dt_issue = next((i for i in type_issues if i["column"] == "Transaction_Date"), None)
    assert dt_issue is not None
    assert dt_issue["type"] == "DATETIME_AS_TEXT"
    # Column-level issue: all 10 dates convert cleanly, so 0 value-level problems
    assert len(dt_issue["affected_indices"]) == 0
    assert dt_issue["clean_count"] == 10

    # 2. Fetch Tab 1 affected rows (what Tab 1 reads)
    rows_res = client.post("/api/clean/type-issue-rows", json={
        "session_id": sid,
        "dataset": "single",
        "column": "Transaction_Date",
    })
    assert rows_res.status_code == 200
    tab1_data = rows_res.get_json()
    assert tab1_data["total_affected"] == 0
    assert len(tab1_data["rows"]) == 0
    assert tab1_data["proposed_target"] == "datetime64"
    assert tab1_data["clean_count"] == 10

    # 3. Convert entire column via Tab 1 Primary Button action
    conv_res = client.post("/api/clean/resolve-type-rows", json={
        "session_id": sid,
        "dataset": "single",
        "column": "Transaction_Date",
        "action": "convert_column",
        "target_type": "datetime64",
    })
    assert conv_res.status_code == 200
    conv_data = conv_res.get_json()
    assert conv_data["success"] is True

    # Check that each row logged its own entry plus the summary repair entry
    assert len(conv_data["entries"]) >= 10
    row_entries = [e for e in conv_data["entries"] if e["action"] == "CONVERT_ROW_TYPE"]
    assert len(row_entries) == 10
    for entry in row_entries:
        assert entry["column"] == "Transaction_Date"

    # Working df column is cast to datetime64
    working_df = sm.get_working_df(sid, "single")
    assert pd.api.types.is_datetime64_any_dtype(working_df["Transaction_Date"])

    # Re-check analysis (Issue Center) - Transaction_Date must be gone from type_issues!
    post_ana = conv_data["analysis"]
    post_type_issues = post_ana["types"]["type_issues"]
    assert not any(i["column"] == "Transaction_Date" for i in post_type_issues)

    # Re-check Tab 1 - type-issue-rows must return 0 affected!
    post_rows_res = client.post("/api/clean/type-issue-rows", json={
        "session_id": sid,
        "dataset": "single",
        "column": "Transaction_Date",
    })
    assert post_rows_res.status_code == 200
    post_tab1_data = post_rows_res.get_json()
    assert post_tab1_data["total_affected"] == 0
    assert len(post_tab1_data["rows"]) == 0

    # History entries are persisted in session manager
    history = sm.get_history(sid, "single")
    dt_entries = [h for h in history if h.get("column") == "Transaction_Date" and h.get("action") == "CONVERT_ROW_TYPE"]
    assert len(dt_entries) == 10


def test_rating_text_column_tab1_and_whole_conversion(client):
    """Test text-stored 'rating' column with clean numbers, a few non-numeric entries, and a few blanks.
    Confirm that:
    1. Only the non-numeric entries appear in Tab 1 affected rows table.
    2. One click converts the whole column across all rows.
    3. Blanks stay blank (<NA>).
    4. Proposed type is nullable Int64.
    5. The column disappears from dropdown and Issue Center afterwards.
    """
    import numpy as np
    sid = sm.new_session()
    # 20 rows:
    # 15 clean numbers: "1", "2", "3", ...
    # 2 non-numeric: "five", "unknown"
    # 3 blanks: "", None, np.nan
    vals = ["1", "2", "3", "4", "5", "1", "2", "3", "4", "5", "five", "1", "2", "", "unknown", "4", "5", None, "1", np.nan]
    df = pd.DataFrame({"rating": vals, "user": [f"u{i}" for i in range(len(vals))]})
    sm.set_original(sid, "single", df, {"filename": "ratings.csv"})

    # 1. Fetch analysis: verify proposed type is Int64 and affected_indices has only the 2 non-numeric rows (indices 10 and 14)
    ana_res = client.get(f"/api/analysis/result?session_id={sid}&dataset=single")
    assert ana_res.status_code == 200
    analysis = ana_res.get_json()["analysis"]
    type_issues = analysis["types"]["type_issues"]
    rating_issue = next(i for i in type_issues if i["column"] == "rating")
    assert rating_issue["proposed_type"] == "Int64"
    assert sorted(rating_issue["affected_indices"]) == [10, 14]
    assert rating_issue["non_convertible_count"] == 2

    # Verify Issue Center card count is 2 (value-level problems)
    issue_center = analysis["issue_center"]
    ic_rating = next(i for i in issue_center if i.get("column") == "rating")
    assert ic_rating["count"] == 2
    assert "2 values cannot convert" in ic_rating["description"]

    # 2. Fetch Tab 1 affected rows: confirm ONLY non-numeric rows appear
    tab1_res = client.post("/api/clean/type-issue-rows", json={
        "session_id": sid, "dataset": "single", "column": "rating"
    })
    assert tab1_res.status_code == 200
    t1 = tab1_res.get_json()
    assert t1["total_affected"] == 2
    assert len(t1["rows"]) == 2
    assert [r["row_index"] for r in t1["rows"]] == [10, 14]
    assert [r["current_value"] for r in t1["rows"]] == ["five", "unknown"]
    assert all(r["can_convert"] is False for r in t1["rows"])
    assert t1["proposed_target"] == "Int64"
    assert "2 cannot" in t1["summary"]

    # 3. Convert whole column across all rows in one action
    conv_res = client.post("/api/clean/resolve-type-rows", json={
        "session_id": sid, "dataset": "single", "column": "rating",
        "action": "convert_column", "target_type": "Int64"
    })
    assert conv_res.status_code == 200
    conv_data = conv_res.get_json()
    assert conv_data["success"] is True

    # 4. Check dataframe state:
    working_df = sm.get_working_df(sid, "single")
    # Proposed nullable Int64 was applied
    assert pd.api.types.is_integer_dtype(working_df["rating"]) or str(working_df["rating"].dtype) == "Int64"
    # Clean numbers converted
    assert working_df["rating"].iloc[0] == 1
    assert working_df["rating"].iloc[1] == 2
    # Unconvertible became blank / <NA>
    assert pd.isna(working_df["rating"].iloc[10])
    assert pd.isna(working_df["rating"].iloc[14])
    # Blanks stayed blank / <NA>
    assert pd.isna(working_df["rating"].iloc[13])
    assert pd.isna(working_df["rating"].iloc[17])
    assert pd.isna(working_df["rating"].iloc[19])

    # 5. Issue completely cleared from analysis & Issue Center
    post_ana = conv_data["analysis"]
    assert not any(i["column"] == "rating" for i in post_ana["types"]["type_issues"])
    assert not any(i.get("column") == "rating" and i.get("category") == "Data-Type Issues" for i in post_ana["issue_center"])

    # 6. Check Change History logged rows
    history = sm.get_history(sid, "single")
    rating_history = [h for h in history if h.get("column") == "rating"]
    assert len(rating_history) > 0


def test_tab1_delete_rows_and_history_logging(client):
    """Verify Tab 1 row deletion logs each deleted row as its own Change History entry
    and adjusts indices properly."""
    sid = sm.new_session()
    df = pd.DataFrame({
        "status_code": ["100", "200", "bad_code", "400", "corrupt_data"],
    })
    sm.set_original(sid, "single", df, {"filename": "status.csv"})

    del_res = client.post("/api/clean/resolve-type-rows", json={
        "session_id": sid,
        "dataset": "single",
        "column": "status_code",
        "action": "delete_row",
        "target_type": "int64",
        "row_indices": [2, 4],
    })
    assert del_res.status_code == 200
    del_data = del_res.get_json()
    assert del_data["success"] is True

    # 2 separate entries logged
    assert len(del_data["entries"]) == 2
    assert all(e["action"] == "DELETE_ROWS" for e in del_data["entries"])

    working_df = sm.get_working_df(sid, "single")
    assert len(working_df) == 3
    assert 2 not in working_df.index
    assert 4 not in working_df.index

