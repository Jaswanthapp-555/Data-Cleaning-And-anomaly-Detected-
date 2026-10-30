import pytest
import io
import pandas as pd
import numpy as np

from backend.analysis import run_full_analysis
from backend.services import session_manager as sm
from backend.analysis.missing_analyzer import detect_identifier_column
from backend.comparison.comparison_engine import compare_datasets
from backend.reports.report_builder import build_single_report, build_comparison_report


def test_schema_problems_removed_from_analysis_and_quality():
    """Verify Schema Problems are completely removed from single-dataset analysis and quality scorer."""
    df = pd.DataFrame({
        "id": [1, 2, 3, 4, 5],
        "name": ["Alice", "Bob", "Charlie", "David", "Eve"],
        "age": [25, 30, 35, 40, 45],
    })
    
    analysis = run_full_analysis(df)
    
    # 1. Issue center should have NO "Schema Problems"
    issue_center = analysis.get("issue_center", [])
    for issue in issue_center:
        assert issue.get("category") != "Schema Problems"
        assert issue.get("count", 0) > 0  # Cards must never have count <= 0

    # 2. Quality score factors should NOT include "Schema Issues"
    qs = analysis.get("quality_score", {})
    factors = qs.get("factors", {})
    assert "Schema Issues" not in factors
    assert "schema_penalty" not in qs.get("breakdown", {})
    assert qs.get("score") is not None

    # 3. schema_issues in schema dict should be empty list
    assert analysis.get("schema", {}).get("schema_issues") == []

    # 4. Internal identifier detection must still work as expected
    id_info = detect_identifier_column(df["id"], "id")
    assert id_info["is_identifier"] is True


def test_stale_issue_cards_two_dataset_mode_and_separation(client):
    """Verify that fixing a Data-Type issue in Reference dataset:
    1. Removes the card from Reference Issue Center (never shows count <= 0).
    2. Does NOT touch or invalidate the Current dataset's state/analysis.
    """
    sid = sm.new_session()

    # Reference dataset: purchase_amount as string with some decimals or float with decimals
    # where mostly whole numbers or numeric data
    ref_csv = (
        "id,purchase_amount,status\n"
        "1,100.50,active\n"
        "2,200.75,active\n"
        "3,300.25,pending\n"
        "4,400.10,active\n"
        "5,500.99,closed\n"
        "6,600.45,pending\n"
        "7,700,active\n"
        "8,800,active\n"
        "9,900,active\n"
        "10,1000,closed\n"
    ).encode("utf-8")

    # Current dataset: has missing status values instead
    cur_csv = (
        "id,purchase_amount,status\n"
        "1,100,active\n"
        "2,200,\n"
        "3,300,\n"
        "4,400,active\n"
        "5,500,\n"
    ).encode("utf-8")

    # Upload Reference
    res_ref = client.post(
        "/api/upload/file",
        data={"file": (io.BytesIO(ref_csv), "reference.csv"), "dataset": "ref"},
        content_type="multipart/form-data",
        headers={"X-Session-Id": sid},
    )
    assert res_ref.status_code == 200

    # Upload Current
    res_cur = client.post(
        "/api/upload/file",
        data={"file": (io.BytesIO(cur_csv), "current.csv"), "dataset": "cur"},
        content_type="multipart/form-data",
        headers={"X-Session-Id": sid},
    )
    assert res_cur.status_code == 200

    # Analyze Reference
    an_ref = client.post("/api/analyze", json={"session_id": sid, "dataset": "ref"}).get_json()["analysis"]
    # Analyze Current
    an_cur = client.post("/api/analyze", json={"session_id": sid, "dataset": "cur"}).get_json()["analysis"]

    # Verify Current has missing values in status
    cur_missing = [iss for iss in an_cur.get("issue_center", []) if iss["category"] == "Missing Values" and iss["column"] == "status"]
    assert len(cur_missing) == 1
    assert cur_missing[0]["count"] == 3

    # Now let's perform a cleaning action on Reference dataset:
    # Repair purchase_amount to float64
    convert_res = client.post(
        "/api/clean/repair-type",
        json={"session_id": sid, "dataset": "ref", "column": "purchase_amount", "target_type": "float64"},
    )
    assert convert_res.status_code == 200

    # Fetch fresh analysis for Reference via GET /api/analysis/result
    get_ref = client.get(f"/api/analysis/result?session_id={sid}&dataset=ref")
    assert get_ref.status_code == 200
    ref_fresh_analysis = get_ref.get_json()["analysis"]

    # Ensure no card has count <= 0 in Reference issue center
    for iss in ref_fresh_analysis.get("issue_center", []):
        assert iss.get("count", 0) > 0
        assert iss.get("category") != "Schema Problems"

    # CRITICAL: Verify Current dataset analysis was completely untouched
    get_cur = client.get(f"/api/analysis/result?session_id={sid}&dataset=cur")
    assert get_cur.status_code == 200
    cur_fresh_analysis = get_cur.get_json()["analysis"]
    cur_missing_after = [iss for iss in cur_fresh_analysis.get("issue_center", []) if iss["category"] == "Missing Values" and iss["column"] == "status"]
    assert len(cur_missing_after) == 1
    assert cur_missing_after[0]["count"] == 3


def test_card_disappears_when_count_reaches_zero_single_mode(client):
    """Verify that when missing values are filled in single dataset mode,
    the Missing Values issue card completely disappears from the issue center.
    """
    sid = sm.new_session()
    csv_data = (
        "id,val\n"
        "1,10.0\n"
        "2,20.0\n"
        "3,\n"
        "4,\n"
        "5,50.0\n"
    ).encode("utf-8")

    # Upload single dataset
    res = client.post(
        "/api/upload/file",
        data={"file": (io.BytesIO(csv_data), "single.csv"), "dataset": "single"},
        content_type="multipart/form-data",
        headers={"X-Session-Id": sid},
    )
    assert res.status_code == 200

    # Analyze
    an_res = client.post("/api/analyze", json={"session_id": sid, "dataset": "single"}).get_json()["analysis"]
    missing_cards = [iss for iss in an_res.get("issue_center", []) if iss["category"] == "Missing Values" and iss["column"] == "val"]
    assert len(missing_cards) == 1
    assert missing_cards[0]["count"] == 2

    # Clean: Fill missing with mean
    fill_res = client.post(
        "/api/clean/fill-missing",
        json={"session_id": sid, "dataset": "single", "column": "val", "method": "mean"},
    )
    assert fill_res.status_code == 200

    # Get analysis result
    get_res = client.get(f"/api/analysis/result?session_id={sid}&dataset=single")
    assert get_res.status_code == 200
    fresh_an = get_res.get_json()["analysis"]

    # Verify Missing Values card for 'val' is completely gone!
    remaining_missing = [iss for iss in fresh_an.get("issue_center", []) if iss["category"] == "Missing Values" and iss["column"] == "val"]
    assert len(remaining_missing) == 0

    # Verify no issue in issue center has count <= 0
    for iss in fresh_an.get("issue_center", []):
        assert iss.get("count", 0) > 0


def test_reports_exclude_schema_issues_and_preserve_schema_comparison():
    """Verify single report excludes schema issues, while comparison report preserves two-dataset schema comparison."""
    ref_df = pd.DataFrame({"A": [1, 2, 3], "B": ["x", "y", "z"]})
    cur_df = pd.DataFrame({"A": [1, 2, 3], "C": [10.5, 20.5, 30.5]})

    ref_an = run_full_analysis(ref_df)
    cur_an = run_full_analysis(cur_df)

    # 1. Single report
    single_rep = build_single_report(
        "ref", {"filename": "ref.csv"}, ref_df, ref_df, ref_an, ref_an, [], "Reference Dataset"
    )
    assert "Schema Problems" not in [iss.get("category") for iss in single_rep.get("issues", [])]
    # Check score breakdown
    score_breakdown = single_rep.get("quality_after", {}).get("breakdown", {})
    assert "Schema Issues" not in score_breakdown
    assert "schema_penalty" not in score_breakdown

    # 2. Comparison report
    comp_result = compare_datasets(ref_df, cur_df, ref_an, cur_an)
    comp_rep = build_comparison_report(
        {"filename": "ref.csv"}, {"filename": "cur.csv"},
        ref_df, cur_df, ref_df, cur_df,
        ref_an, ref_an, cur_an, cur_an,
        [], [], comp_result
    )
    # Must preserve Schema Comparison
    assert "comparison" in comp_rep
    schema_comp = comp_rep["comparison"].get("schema", {})
    assert "C" in schema_comp.get("added_columns", [])
    assert "B" in schema_comp.get("removed_columns", [])
    assert "A" in schema_comp.get("common_columns", [])
