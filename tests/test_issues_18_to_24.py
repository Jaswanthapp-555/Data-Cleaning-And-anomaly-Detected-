import pytest
import pandas as pd
import numpy as np
import io

from backend.analysis.missing_analyzer import detect_identifier_column, analyze_missing
from backend.analysis.type_analyzer import analyze_types
from backend.cleaning.cleaning_engine import (
    resolve_suspicious_value,
    resolve_outlier,
    delete_column_missing_rows,
    fill_missing,
)
from backend.reports.report_builder import build_single_report
from backend.reports.html_renderer import render_html_report
from backend.reports.pdf_renderer import render_pdf_report
from backend.services.session_manager import get_session, set_original_analysis, get_original_analysis


def test_issue_21b_identifier_false_positive_price():
    # High uniqueness numeric column named 'Price' must NOT be flagged as an identifier
    prices = pd.Series([19.99, 29.99, 39.99, 49.99, 59.99, 69.99, 79.99, 89.99, 99.99, 109.99])
    res = detect_identifier_column(prices, "Price")
    assert res["is_identifier"] is False, f"Price should not be an identifier: {res}"

    # An actual ID column with high uniqueness and ID name SHOULD be flagged
    ids = pd.Series(["USER_101", "USER_102", "USER_103", "USER_104", "USER_105"])
    res_id = detect_identifier_column(ids, "user_id")
    assert res_id["is_identifier"] is True
    assert res_id["confidence"] == "strong"


def test_issue_22a_type_analyzer_column_names():
    df = pd.DataFrame({
        "num_as_text": ["1.2", "3.4", "5.6", "7.8"],
        "date_as_text": ["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04"],
    })
    res = analyze_types(df)
    issues = res.get("type_issues", [])
    assert len(issues) >= 2
    for issue in issues:
        assert "column" in issue
        assert issue["column"] in ["num_as_text", "date_as_text"]
        assert len(issue["column"]) > 0


def test_issue_21c_mode_disallowed_on_numeric():
    df = pd.DataFrame({
        "Price": [10.5, np.nan, 20.0, 30.5, 40.0],
    })
    with pytest.raises(ValueError, match="mode.*numeric|only applicable to categorical"):
        fill_missing(df, "Price", "mode")


def test_issue_18_resolve_suspicious_values():
    df = pd.DataFrame({
        "Item": ["Apple", "Banana", "Cherry", "Date"],
        "Quantity": [10, -999, 15, 20],  # -999 is suspicious
    })
    # Test delete_row (default/recommended action)
    cleaned_df, entries = resolve_suspicious_value(df, row_index=1, column="Quantity", resolution="delete_row")
    assert len(cleaned_df) == 3
    assert -999 not in cleaned_df["Quantity"].values
    assert entries[0]["action"] == "DELETE_ROWS"

    # Test keep
    df_keep, entries_keep = resolve_suspicious_value(df, row_index=1, column="Quantity", resolution="keep")
    assert len(df_keep) == 4
    assert entries_keep[0]["action"] == "LEAVE_UNCHANGED"

    # Test correct
    df_corr, entries_corr = resolve_suspicious_value(df, row_index=1, column="Quantity", resolution="correct", manual_value=12)
    assert len(df_corr) == 4
    assert df_corr.at[1, "Quantity"] == 12


def test_issue_19_resolve_outliers():
    df = pd.DataFrame({
        "Val": [10.0, 11.0, 10.5, 9.8, 10.2, 500.0]  # 500 is outlier at index 5
    })
    # Test keep logs unchanged
    df_keep, entries_keep = resolve_outlier(df, row_index=5, column="Val", resolution="keep")
    assert len(df_keep) == 6
    assert entries_keep[0]["action"] == "LEAVE_UNCHANGED"

    # Test replace with median_excl_outliers
    df_rep, entries_rep = resolve_outlier(df, row_index=5, column="Val", resolution="replace", impute_method="median_excl_outliers")
    assert df_rep.at[5, "Val"] != 500.0
    assert len(entries_rep) > 0

    # Test delete_row
    df_del, entries_del = resolve_outlier(df, row_index=5, column="Val", resolution="delete_row")
    assert len(df_del) == 5


def test_resolved_columns_drop_out_of_dropdown_data(client):
    csv_data = b"ID,Price,Score\n1,10.0,100\n2,12.0,105\n3,11.0,98\n4,10.5,102\n5,9.5,99\n6,500.0,101\n"
    res = client.post("/api/session/new")
    sid = res.get_json()["session_id"]
    upload_res = client.post(
        "/api/upload/file",
        data={"file": (io.BytesIO(csv_data), "data.csv"), "dataset": "single"},
        content_type="multipart/form-data",
        headers={"X-Session-Id": sid},
    )
    assert upload_res.status_code == 200

    # Run analysis
    an_run = client.post("/api/analyze", json={"session_id": sid, "dataset": "single"})
    assert an_run.status_code == 200
    an_res = an_run.get_json()["analysis"]
    outlier_cols = [d["column"] for d in an_res["outliers"]["outlier_details"]]
    assert "Price" in outlier_cols

    # Resolve the outlier by keeping it
    clean_res = client.post(
        "/api/clean/resolve-outlier",
        json={"session_id": sid, "dataset": "single", "column": "Price", "row_index": 5, "resolution": "keep"}
    )
    assert clean_res.status_code == 200

    # Now Price should have DROPPED OUT of outlier_details!
    an_res2 = client.get(f"/api/analysis/result?session_id={sid}&dataset=single").get_json()["analysis"]
    outlier_cols2 = [d["column"] for d in an_res2["outliers"]["outlier_details"]]
    assert "Price" not in outlier_cols2
    assert an_res2["outliers"]["columns_with_outliers"] == 0


def test_issue_20_delete_column_missing_rows():
    df = pd.DataFrame({
        "A": [1, np.nan, 3, 4],     # missing at row 1
        "B": [np.nan, "x", "y", "z"], # missing at row 0
    })
    # Delete missing ONLY in column A
    cleaned_df, entry = delete_column_missing_rows(df, "A")
    assert len(cleaned_df) == 3
    # Row 1 (where A was missing) must be removed
    assert list(cleaned_df["A"]) == [1, 3, 4]
    # Row 0 (where B was missing, but A was 1) must still be present!
    assert pd.isna(cleaned_df.iloc[0]["B"])
    assert entry["action"] == "DELETE_ROWS_BY_COLUMN"
    assert entry["column"] == "A"


def test_issue_22b_quality_score_preservation(client):
    # Upload dirty CSV
    csv_data = b"ID,Price,Category\n1,10.5,A\n2,,A\n3,25.0,B\n4,10000.0,\n"
    res = client.post("/api/session/new")
    sid = res.get_json()["session_id"]

    upload_res = client.post(
        "/api/upload/file",
        data={"file": (io.BytesIO(csv_data), "dirty.csv"), "dataset": "single"},
        headers={"X-Session-Id": sid},
        content_type="multipart/form-data",
    )
    assert upload_res.status_code == 200

    # Clean a value
    fill_res = client.post("/api/clean/fill-missing", json={
        "session_id": sid,
        "dataset": "single",
        "column": "Price",
        "method": "mean",
    })
    assert fill_res.status_code == 200

    # Get HTML report
    rep_res = client.post("/api/report/html", json={"session_id": sid, "mode": "single"})
    assert rep_res.status_code == 200
    html_text = rep_res.data.decode("utf-8")
    assert "Dataset Overview" in html_text

    # Fetch original analysis and verify preserved
    orig_an = get_original_analysis(sid, "single")
    assert orig_an is not None
    assert orig_an["missing"]["total_missing"] > 0


def test_issue_23_and_24_report_builder_and_valid_pdf():
    df = pd.DataFrame({
        "Age": [25, 30, 35, 40, np.nan],
        "Salary": [50000.0, 60000.0, 75000.0, 80000.0, 95000.0],
        "Department": ["HR", "IT", "IT", "HR", "Sales"],
    })
    from backend.analysis import run_full_analysis
    analysis = run_full_analysis(df)

    data = build_single_report(
        ds_key="single",
        source_info={"filename": "test.csv", "filesize": 1024, "loaded_at": "2026-09-11"},
        df_original=df,
        df_final=df,
        analysis_before=analysis,
        analysis_after=analysis,
        change_history=[],
        dataset_label="Employees",
    )

    # Check Statistics in data model (Issue 23a)
    assert "stats" in data
    assert "numerical" in data["stats"]
    assert "categorical" in data["stats"]
    assert len(data["stats"]["numerical"]) >= 2  # Age, Salary
    assert len(data["stats"]["categorical"]) >= 1  # Department

    # Check Visualizations in data model (Issue 23b)
    assert "visualizations" in data
    assert "missing_chart" in data["visualizations"]
    assert "score_chart" in data["visualizations"]
    assert data["visualizations"]["missing_chart"].startswith("data:image/png;base64,")

    # Check Final Summary in data model (Issue 23c)
    assert "final_summary" in data
    assert "text" in data["final_summary"]
    assert len(data["final_summary"]["text"]) > 20

    # Render HTML
    html = render_html_report(data)
    assert "Statistics" in html
    assert "Numerical Statistics" in html
    assert "Categorical Statistics" in html
    assert "Visualizations" in html
    assert "Final Summary" in html

    # Verify PDF generation creates valid %PDF bytes (Issue 24)
    pdf_bytes = render_pdf_report(html)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF"), f"Expected %PDF header, got: {pdf_bytes[:20]}"
    assert len(pdf_bytes) > 1000


def test_sequential_outlier_dropout(client):
    """Test that resolving outliers one-by-one updates counts and drops column when fully resolved."""
    # 20 rows: Quantity has 2 outliers (rows 18, 19), Price has 2 outliers (rows 16, 17)
    rows = ["ID,Quantity,Price"]
    for i in range(16):
        rows.append(f"{i},10,50.0")
    rows.append("16,10,5000.0")
    rows.append("17,10,6000.0")
    rows.append("18,1000,50.0")
    rows.append("19,2000,50.0")
    csv_bytes = "\n".join(rows).encode("utf-8")

    res = client.post("/api/session/new")
    sid = res.get_json()["session_id"]
    client.post(
        "/api/upload/file",
        data={"file": (io.BytesIO(csv_bytes), "outliers.csv"), "dataset": "single"},
        headers={"X-Session-Id": sid},
        content_type="multipart/form-data",
    )
    client.post("/api/analyze", json={"session_id": sid, "dataset": "single"})

    # Check initial: Quantity and Price both have outliers
    an = client.get(f"/api/analysis/result?session_id={sid}&dataset=single").get_json()["analysis"]
    out_map = {d["column"]: d["combined_count"] for d in an["outliers"]["outlier_details"]}
    assert "Quantity" in out_map and out_map["Quantity"] == 2
    assert "Price" in out_map and out_map["Price"] == 2

    # Step 1: Resolve 1 Quantity outlier (row 18) by keeping it
    r1 = client.post("/api/clean/resolve-outlier", json={
        "session_id": sid, "dataset": "single", "column": "Quantity", "row_index": 18, "resolution": "keep"
    }).get_json()["analysis"]
    out_map1 = {d["column"]: d["combined_count"] for d in r1["outliers"]["outlier_details"]}
    assert out_map1["Quantity"] == 1
    assert out_map1["Price"] == 2

    # Step 2: Resolve the second Quantity outlier (row 19) by correcting it to 10
    r2 = client.post("/api/clean/resolve-outlier", json={
        "session_id": sid, "dataset": "single", "column": "Quantity", "row_index": 19, "resolution": "correct", "manual_value": "10"
    }).get_json()["analysis"]
    out_map2 = {d["column"]: d["combined_count"] for d in r2["outliers"]["outlier_details"]}
    # Quantity MUST be completely gone!
    assert "Quantity" not in out_map2
    assert "Price" in out_map2 and out_map2["Price"] == 2

    # Step 3: Resolve 1 Price outlier by deleting row 16
    r3 = client.post("/api/clean/resolve-outlier", json={
        "session_id": sid, "dataset": "single", "column": "Price", "row_index": 16, "resolution": "delete_row"
    }).get_json()["analysis"]
    out_map3 = {d["column"]: d["combined_count"] for d in r3["outliers"]["outlier_details"]}
    assert "Quantity" not in out_map3
    assert "Price" in out_map3 and out_map3["Price"] == 1

    # Step 4: Resolve final Price outlier (which shifted to index 16 after delete)
    remaining_price_idx = int(r3["outliers"]["outlier_details"][0]["combined_indices"][0])
    res4 = client.post("/api/clean/resolve-outlier", json={
        "session_id": sid, "dataset": "single", "column": "Price", "row_index": remaining_price_idx, "resolution": "replace", "impute_method": "median_excl_outliers"
    })
    assert res4.status_code == 200, res4.get_json()
    r4 = res4.get_json()["analysis"]
    # All outliers resolved!
    assert len(r4["outliers"]["outlier_details"]) == 0
    assert r4["outliers"]["columns_with_outliers"] == 0


def test_sequential_suspicious_dropout(client):
    """Test that resolving suspicious values one-by-one drops columns when count reaches 0."""
    # Create dataset with Customer_ID placeholder values ("Unknown", "TBD") and Status placeholders ("TBD")
    rows = ["Customer_ID,Status,Val"]
    rows.append("Unknown,TBD,10")
    rows.append("Unknown,Active,11")
    for i in range(10):
        rows.append(f"CUST_{i},Active,{10 + (i % 3)}")
    csv_bytes = "\n".join(rows).encode("utf-8")

    res = client.post("/api/session/new")
    sid = res.get_json()["session_id"]
    client.post(
        "/api/upload/file",
        data={"file": (io.BytesIO(csv_bytes), "susp.csv"), "dataset": "single"},
        headers={"X-Session-Id": sid},
        content_type="multipart/form-data",
    )
    client.post("/api/analyze", json={"session_id": sid, "dataset": "single"})

    an = client.get(f"/api/analysis/result?session_id={sid}&dataset=single").get_json()["analysis"]
    susp_issues = an["suspicious"]["suspicious_issues"]
    susp_cols = {i["column"] for i in susp_issues}
    assert "Customer_ID" in susp_cols
    assert "Status" in susp_cols

    # Step 1: Keep row 0 ("Unknown") in Customer_ID
    res1 = client.post("/api/clean/resolve-suspicious", json={
        "session_id": sid, "dataset": "single", "column": "Customer_ID", "row_index": 0, "resolution": "keep"
    })
    assert res1.status_code == 200, res1.get_json()
    r1 = res1.get_json()["analysis"]
    cid_issue = next((i for i in r1["suspicious"]["suspicious_issues"] if i["column"] == "Customer_ID"), None)
    assert cid_issue is not None
    assert cid_issue["count"] == 1

    # Step 2: Delete row 1 in Customer_ID
    res2 = client.post("/api/clean/resolve-suspicious", json={
        "session_id": sid, "dataset": "single", "column": "Customer_ID", "row_index": 1, "resolution": "delete_row"
    })
    assert res2.status_code == 200, res2.get_json()
    r2 = res2.get_json()["analysis"]
    cid_issue2 = next((i for i in r2["suspicious"]["suspicious_issues"] if i["column"] == "Customer_ID"), None)
    # Customer_ID MUST be completely gone!
    assert cid_issue2 is None
    # Status still has its placeholder
    status_issue = next((i for i in r2["suspicious"]["suspicious_issues"] if i["column"] == "Status"), None)
    assert status_issue is not None

    # Step 3: Correct Status row 0 to "Active"
    res3 = client.post("/api/clean/resolve-suspicious", json={
        "session_id": sid, "dataset": "single", "column": "Status", "row_index": 0, "resolution": "correct", "manual_value": "Active"
    })
    assert res3.status_code == 200, res3.get_json()
    r3 = res3.get_json()["analysis"]
    assert len(r3["suspicious"]["suspicious_issues"]) == 0
    assert r3["suspicious"]["has_suspicious"] is False
