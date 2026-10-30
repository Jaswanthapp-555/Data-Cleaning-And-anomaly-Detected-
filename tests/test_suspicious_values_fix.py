"""Tests verifying false-positive fixes in Suspicious Values detection."""
import io
import pandas as pd
import pytest
from backend.services import session_manager as sm
from backend.analysis.suspicious_analyzer import analyze_suspicious
from backend.analysis import run_full_analysis
from backend.reports.report_builder import build_single_report


def test_ordinary_categorical_values_not_flagged():
    """Requirement 11: Regression test proving that ordinary values such as
    Card, Cash, PayPal, Phone, Laptop, Completed, and Pending are not flagged as suspicious.
    """
    n_rows = 80
    data = {
        "Transaction_ID": [f"TXN_{i:04d}" for i in range(n_rows)],
        "Payment_Method": (["Card"] * 50) + (["Cash"] * 20) + (["PayPal"] * 10),
        "Product": (["Phone"] * 30) + (["Laptop"] * 30) + (["Tablet"] * 20),
        "Transaction_Status": (["Completed"] * 60) + (["Pending"] * 20),
    }
    df = pd.DataFrame(data)

    res = analyze_suspicious(df)

    # Must NOT flag any of these ordinary categories!
    assert res["has_suspicious"] is False
    assert res["total_suspicious_count"] == 0
    assert len(res["suspicious_issues"]) == 0


def test_casing_inconsistency_flags_only_deviant_record():
    """Requirement 2, 3, 4, 5, 6:
    Dataset with 75 'Card' rows and 1 'card' row (total 76 rows):
    - The 75 valid 'Card' records must NOT be flagged as suspicious.
    - ONLY row 75 with 'card' should be detected as a casing inconsistency.
    - Result must specify row, column, original value, detection reason, and severity.
    """
    n_valid = 75
    records = ["Card"] * n_valid + ["card"]
    df = pd.DataFrame({
        "Transaction_ID": [f"T{i}" for i in range(len(records))],
        "Payment_Method": records,
        "Product": ["Laptop"] * len(records),
        "Transaction_Status": ["Completed"] * len(records),
    })

    res = analyze_suspicious(df)

    assert res["has_suspicious"] is True
    assert len(res["suspicious_issues"]) == 1

    issue = res["suspicious_issues"][0]
    assert issue["column"] == "Payment_Method"
    assert issue["type"] == "CASING_INCONSISTENCY"
    assert issue["severity"] == "low"
    assert issue["count"] == 1
    assert issue["indices"] == [75]  # Only the deviant row 75!

    # 75 'Card' rows must NOT be in the indices!
    for i in range(n_valid):
        assert i not in issue["indices"]

    # Verify per-row detail identification (Requirement 6)
    row_details = issue.get("row_details", [])
    assert len(row_details) == 1
    assert row_details[0]["row"] == 75
    assert row_details[0]["column"] == "Payment_Method"
    assert row_details[0]["original_value"] == "card"
    assert "Card" in row_details[0]["reason"]
    assert row_details[0]["severity"] == "low"


def test_genuinely_invalid_values_and_anomalies_detected():
    """Requirement 12: Ensure genuinely invalid values (placeholders, sentinels, corrupt strings)
    are detected with precise row, column, original value, and detection reasons.
    """
    df = pd.DataFrame({
        "Payment_Method": ["Card", "Card", "?", "Cash", "Unknown", "PayPal"],
        "Product": ["Laptop", "Phone", "Phone", "###", "Tablet", "Phone"],
        "Amount": [100.0, 150.0, 120.0, 130.0, 110.0, 99999.0],  # 99999 is outlier / sentinel
    })

    res = analyze_suspicious(df)
    assert res["has_suspicious"] is True

    # Check Payment_Method placeholders ("?", "Unknown")
    pm_issue = next(i for i in res["suspicious_issues"] if i["column"] == "Payment_Method")
    assert pm_issue["type"] == "PLACEHOLDER_VALUES"
    assert pm_issue["count"] == 2
    assert set(pm_issue["indices"]) == {2, 4}
    assert any(d["original_value"] == "?" and d["row"] == 2 for d in pm_issue["row_details"])
    assert any(d["original_value"] == "Unknown" and d["row"] == 4 for d in pm_issue["row_details"])

    # Check Product corrupt symbol value ("###")
    prod_issue = next(i for i in res["suspicious_issues"] if i["column"] == "Product")
    assert prod_issue["indices"] == [3]
    assert prod_issue["row_details"][0]["original_value"] == "###"

    # Check Amount extreme outlier (99999.0)
    amt_issue = next(i for i in res["suspicious_issues"] if i["column"] == "Amount")
    assert amt_issue["indices"] == [5]
    assert amt_issue["row_details"][0]["original_value"] == 99999.0


def test_no_cross_column_contamination():
    """Requirement 5: Do not flag a row as suspicious solely because another column contains an issue.
    Associate every issue strictly with its affected column and value.
    """
    df = pd.DataFrame({
        "Status": ["Completed", "Completed", "Pending", "Completed"],
        "Payment_Method": ["Card", "?", "Cash", "Card"],  # Row 1 is invalid in Payment_Method only
        "Product": ["Phone", "Laptop", "Laptop", "Laptop"],
    })

    full_an = run_full_analysis(df)
    susp_issues = full_an["suspicious"]["suspicious_issues"]

    # Only Payment_Method should have an issue
    assert len(susp_issues) == 1
    assert susp_issues[0]["column"] == "Payment_Method"
    assert susp_issues[0]["indices"] == [1]

    # Status and Product must NOT be flagged
    assert not any(i["column"] == "Status" for i in susp_issues)
    assert not any(i["column"] == "Product" for i in susp_issues)


def test_affected_records_api_contains_cell_flags(client):
    """Requirement 6 & 10: Verify /api/dataset/affected-rows returns cell-level flags
    and specific detection reason for affected records.
    """
    sid = sm.new_session()
    df = pd.DataFrame({
        "Payment_Method": (["Card"] * 20) + ["card"],  # row 20 has casing inconsistency
        "Product": ["Laptop"] * 21,
        "Transaction_Status": ["Completed"] * 21,
    })
    sm.set_original(sid, "single", df, {"filename": "transactions.csv"})

    # Run analysis
    an_res = client.post("/api/analyze", json={"session_id": sid, "dataset": "single"})
    assert an_res.status_code == 200
    analysis = an_res.get_json()["analysis"]

    # In issue center, only row 20 should be affected
    inconsistency_issue = next(i for i in analysis["issue_center"] if i.get("column") == "Payment_Method")
    assert inconsistency_issue["affected_indices"] == [20]
    assert inconsistency_issue["count"] == 1

    # Request affected records for row 20
    aff_res = client.post("/api/dataset/affected-rows", json={
        "session_id": sid,
        "dataset": "single",
        "indices": [20],
    })
    assert aff_res.status_code == 200
    aff_data = aff_res.get_json()

    assert len(aff_data["records"]) == 1
    record = aff_data["records"][0]
    assert record["_row_id"] == 20
    assert record["Payment_Method"] == "card"
    # Cell flags must contain Payment_Method with reason and severity
    assert "Payment_Method" in record["_cell_flags"]
    assert "casing inconsistency" in record["_cell_flags"]["Payment_Method"]["reason"].lower()
    assert record["_cell_flags"]["Payment_Method"]["severity"] == "low"


def test_arbitrary_uploaded_datasets_dynamic_learning():
    """Requirement 7 & 8: Support arbitrary uploaded datasets without hardcoded category names.
    Learn potential categories from data frequencies.
    """
    df = pd.DataFrame({
        "Department": ["Engineering"] * 40 + ["Sales"] * 25 + ["Marketing"] * 20 + ["sales"] * 2,
        "Region": ["EMEA"] * 45 + ["APAC"] * 42,
    })

    res = analyze_suspicious(df)
    assert res["has_suspicious"] is True
    # Department has 2 casing variants of 'Sales' ('sales')
    dept_issue = next(i for i in res["suspicious_issues"] if i["column"] == "Department")
    assert dept_issue["type"] == "CASING_INCONSISTENCY"
    assert dept_issue["count"] == 2
    assert set(dept_issue["indices"]) == {85, 86}

    # Region has zero issues
    assert not any(i["column"] == "Region" for i in res["suspicious_issues"])


def test_cleaning_resolution_and_report_generation(client):
    """Requirement 9 & 10: Verify resolving inconsistency (keep or correct)
    updates issue count and reports accurately.
    """
    sid = sm.new_session()
    df = pd.DataFrame({
        "Payment_Method": (["Card"] * 30) + ["card"],  # Row 30 has 'card'
        "Status": ["Completed"] * 31,
    })
    sm.set_original(sid, "single", df, {"filename": "orders.csv"})

    client.post("/api/analyze", json={"session_id": sid, "dataset": "single"})

    # Standardize casing for row 30 to 'Card'
    resolve_res = client.post("/api/clean/resolve-suspicious", json={
        "session_id": sid,
        "dataset": "single",
        "column": "Payment_Method",
        "row_indices": [30],
        "resolution": "correct",
        "manual_value": "Card",
    })
    assert resolve_res.status_code == 200
    cleaned_an = resolve_res.get_json()["analysis"]

    # All suspicious issues must now be 0!
    assert len(cleaned_an["suspicious"]["suspicious_issues"]) == 0
    assert cleaned_an["suspicious"]["has_suspicious"] is False

    # HTML report generation should succeed with 0 issues
    report_res = client.post("/api/report/html", json={
        "session_id": sid,
        "mode": "single",
        "report_type": "analysis",
    })
    assert report_res.status_code == 200
    html_content = report_res.get_data(as_text=True)
    assert "Data Quality Report" in html_content
