import pandas as pd
from backend.comparison.comparison_engine import compare_datasets
from backend.comparison.drift_detector import detect_drift
from backend.analysis import run_full_analysis


def test_schema_comparison():
    ref_df = pd.DataFrame({"A": [1, 2], "B": ["x", "y"], "C": [1.0, 2.0]})
    cur_df = pd.DataFrame({"A": [1, 2], "B": ["x", "y"], "D": [10, 20]})  # C removed, D added

    ref_a = run_full_analysis(ref_df)
    cur_a = run_full_analysis(cur_df)

    res = compare_datasets(ref_df, cur_df, ref_a, cur_a)
    schema = res["schema"]

    assert "D" in schema["added_columns"]
    assert "C" in schema["removed_columns"]
    assert "A" in schema["common_columns"]


def test_drift_detection():
    import numpy as np
    np.random.seed(42)
    ref_vals = np.random.normal(10, 1, 100)
    cur_vals = np.random.normal(20, 1, 100)  # Clear shift

    ref_df = pd.DataFrame({"val": ref_vals})
    cur_df = pd.DataFrame({"val": cur_vals})

    results = detect_drift(ref_df, cur_df)
    assert len(results) == 1
    assert results[0]["drift_detected"] is True
    assert results[0]["ks_available"] is True


def test_comparison_string_dtype_no_crash():
    """Item 4: Ensure comparing datasets with string/text columns and pd.NA does not raise TypeError for mean reduction."""
    ref_df = pd.DataFrame({
        "customer_id": ["CUST_001", "CUST_002", "CUST_003"],
        "category": pd.Series(["Electronics", "Home", pd.NA], dtype="string"),
        "notes": ["ok", "pending", "done"],
        "amount": [100.5, 250.0, 75.25],
    })
    cur_df = pd.DataFrame({
        "customer_id": ["CUST_001", "CUST_002", "CUST_004"],
        "category": pd.Series(["Electronics", "Home & Garden", "Books"], dtype="string"),
        "notes": ["ok", "urgent", "pending"],
        "amount": [120.0, 250.0, 95.0],
    })

    ref_a = run_full_analysis(ref_df)
    cur_a = run_full_analysis(cur_df)

    res = compare_datasets(ref_df, cur_df, ref_a, cur_a)
    assert res is not None
    assert "summary" in res
    assert "narrative" in res["summary"]
    assert "schema" in res
    assert "drift" in res


def test_comparison_identifier_auto_detection_and_matching():
    """Item 5: Ensure customer_id is auto-selected as identifier and positional mismatch is avoided."""
    ref_df = pd.DataFrame({
        "customer_id": ["CUST_0021", "CUST_0022", "CUST_0023", "CUST_0024"],
        "income": [50000, 60000, 70000, 80000],
        "city": ["NY", "LA", "Chicago", "Houston"],
    })
    # Current dataset has CUST_0022 deleted, which shifts positional indices
    cur_df = pd.DataFrame({
        "customer_id": ["CUST_0021", "CUST_0023", "CUST_0024"],
        "income": [50000, 75000, -500],  # CUST_0023 changed income, CUST_0024 has negative income anomaly
        "city": ["NY", "Chicago", "Houston"],
    })

    ref_a = run_full_analysis(ref_df)
    cur_a = run_full_analysis(cur_df)

    res = compare_datasets(ref_df, cur_df, ref_a, cur_a)
    summary = res["summary"]
    row_match = res["row_match"]

    # Must detect customer_id as identifier
    assert "customer_id" in summary.get("matching_strategy", "")
    assert "customer_id" in row_match["strategy"]
    assert row_match["deleted_record_count"] == 1
    assert "CUST_0022" in row_match["deleted_record_ids"]

    # customer_id must NEVER be listed as a changed cell value!
    for rec in row_match["modified_records"]:
        cols = [ch["column"] for ch in rec["changes"]]
        assert "customer_id" not in cols

    # Item 6c: frequently_changed_columns must be present
    assert "frequently_changed_columns" in row_match
    frequent = row_match["frequently_changed_columns"]
    assert any(fc["column"] == "income" for fc in frequent)

    # Item 6d: negative income (-500) must be flagged inline as an anomaly
    modified = row_match["modified_records"]
    cust_24 = next((r for r in modified if r["id"] == "CUST_0024"), None)
    assert cust_24 is not None
    income_change = next(ch for ch in cust_24["changes"] if ch["column"] == "income")
    assert income_change["anomalous"] is True
    assert "Negative value" in income_change["anomaly_reason"]


def test_comparison_drift_skips_identifier_and_handles_datetime():
    """Item 6a: Ensure categorical drift is skipped on identifier columns, and datetime columns get trend analysis."""
    ref_df = pd.DataFrame({
        "customer_id": [f"ID_{i}" for i in range(100)],
        "created_at": pd.date_range("2025-01-01", periods=100, freq="D"),
        "amount": [10.0 * i for i in range(100)],
    })
    cur_df = pd.DataFrame({
        "customer_id": [f"ID_{i+50}" for i in range(100)],
        "created_at": pd.date_range("2025-04-11", periods=100, freq="D"),
        "amount": [15.0 * i for i in range(100)],
    })

    drift_res = detect_drift(ref_df, cur_df)
    drift_cols = {d["column"]: d for d in drift_res}

    # Identifier column must NOT have categorical drift run on it (classified as identifier with drift_detected=False)
    assert "customer_id" in drift_cols
    assert drift_cols["customer_id"]["type"] == "identifier"
    assert drift_cols["customer_id"]["drift_detected"] is False
    assert "Unique identifier" in drift_cols["customer_id"]["interpretation"]

    # Datetime column must have temporal trend analysis
    assert "created_at" in drift_cols
    assert drift_cols["created_at"]["type"] == "datetime"
    assert "Temporal span shifted" in drift_cols["created_at"]["interpretation"]

