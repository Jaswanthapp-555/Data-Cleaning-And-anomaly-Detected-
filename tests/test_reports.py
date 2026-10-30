import pandas as pd
from backend.reports.report_builder import build_single_report, build_comparison_report
from backend.reports.html_renderer import render_html_report


def test_single_report_builder():
    df = pd.DataFrame({"A": [1, 2, 3], "B": ["x", "y", "z"]})
    report_data = build_single_report(
        ds_key="single",
        source_info={"type": "csv", "filename": "test.csv"},
        df_original=df,
        df_final=df,
        analysis_before={},
        analysis_after={},
        change_history=[],
    )
    assert report_data["report_type"] == "single"
    assert report_data["dimensions"]["original"]["rows"] == 3

    html = render_html_report(report_data)
    assert "Automated Data Quality &amp; Anomaly Profiler" in html or "Automated Data Quality" in html
    assert "test.csv" in html


def test_comparison_report_builder():
    ref_df = pd.DataFrame({"A": [1, 2]})
    cur_df = pd.DataFrame({"A": [1, 2, 3]})
    report_data = build_comparison_report(
        ref_source={"type": "csv", "filename": "ref.csv"},
        cur_source={"type": "csv", "filename": "cur.csv"},
        ref_df_orig=ref_df, cur_df_orig=cur_df,
        ref_df_final=ref_df, cur_df_final=cur_df,
        ref_analysis_before={}, ref_analysis_after={},
        cur_analysis_before={}, cur_analysis_after={},
        ref_history=[], cur_history=[],
        comparison_result={"summary": {"columns_added": 0, "columns_removed": 0, "type_changes": 0, "new_records": 1, "deleted_records": 0, "modified_records": 0, "quality_score_change": 0, "row_count_change": 1, "drift_columns": 0, "strategy": "Position"}},
    )
    assert report_data["report_type"] == "comparison"
    html = render_html_report(report_data)
    assert "Comparison Summary" in html


def test_four_separate_report_artifacts(client):
    """Item 1: Test generating 4 separate artifacts in Two Dataset mode:
       (a) Reference report (HTML/PDF)
       (b) Current report (HTML/PDF)
       (c) Comparison report (HTML/PDF)
       (d) Cleaned CSV downloads (Ref/Cur)
    """
    import io
    ref_csv = b"id,val\n1,10\n2,20\n"
    cur_csv = b"id,val\n1,10\n2,25\n3,30\n"

    res = client.post("/api/session/new")
    sid = res.get_json()["session_id"]
    client.post("/api/session/mode", json={"session_id": sid, "mode": "compare"})

    # Upload Ref & Cur
    client.post("/api/upload/file", data={"file": (io.BytesIO(ref_csv), "ref.csv"), "dataset": "ref"},
                content_type="multipart/form-data", headers={"X-Session-Id": sid})
    client.post("/api/upload/file", data={"file": (io.BytesIO(cur_csv), "cur.csv"), "dataset": "cur"},
                content_type="multipart/form-data", headers={"X-Session-Id": sid})

    # Finalize both
    client.post("/api/finalize", json={"session_id": sid, "dataset": "ref"})
    client.post("/api/finalize", json={"session_id": sid, "dataset": "cur"})

    # (a) Reference Dataset Report (HTML & PDF)
    ref_html_res = client.post("/api/report/html", json={"session_id": sid, "mode": "compare", "report_type": "reference"})
    assert ref_html_res.status_code == 200
    assert "Reference Dataset" in ref_html_res.data.decode("utf-8")
    assert "reference_dataset_report.html" in ref_html_res.headers.get("Content-Disposition", "")

    ref_pdf_res = client.post("/api/report/pdf", json={"session_id": sid, "mode": "compare", "report_type": "reference"})
    assert ref_pdf_res.status_code == 200
    assert ref_pdf_res.data.startswith(b"%PDF")
    assert "reference_dataset_report.pdf" in ref_pdf_res.headers.get("Content-Disposition", "")

    # (b) Current Dataset Report (HTML & PDF)
    cur_html_res = client.post("/api/report/html", json={"session_id": sid, "mode": "compare", "report_type": "current"})
    assert cur_html_res.status_code == 200
    assert "Current Dataset" in cur_html_res.data.decode("utf-8")
    assert "current_dataset_report.html" in cur_html_res.headers.get("Content-Disposition", "")

    cur_pdf_res = client.post("/api/report/pdf", json={"session_id": sid, "mode": "compare", "report_type": "current"})
    assert cur_pdf_res.status_code == 200
    assert cur_pdf_res.data.startswith(b"%PDF")
    assert "current_dataset_report.pdf" in cur_pdf_res.headers.get("Content-Disposition", "")

    # (c) Comparison Report (HTML & PDF)
    comp_html_res = client.post("/api/report/html", json={"session_id": sid, "mode": "compare", "report_type": "comparison"})
    assert comp_html_res.status_code == 200
    assert "Comparison Summary" in comp_html_res.data.decode("utf-8")
    assert "Executive Comparison Narrative" in comp_html_res.data.decode("utf-8")
    assert "comparison_report.html" in comp_html_res.headers.get("Content-Disposition", "")

    comp_pdf_res = client.post("/api/report/pdf", json={"session_id": sid, "mode": "compare", "report_type": "comparison"})
    assert comp_pdf_res.status_code == 200
    assert comp_pdf_res.data.startswith(b"%PDF")
    assert "comparison_report.pdf" in comp_pdf_res.headers.get("Content-Disposition", "")

    # (d) Cleaned CSV Downloads
    ref_csv_res = client.get(f"/api/download/dataset?session_id={sid}&dataset=ref")
    assert ref_csv_res.status_code == 200
    assert "cleaned_dataset_ref.csv" in ref_csv_res.headers.get("Content-Disposition", "")

    cur_csv_res = client.get(f"/api/download/dataset?session_id={sid}&dataset=cur")
    assert cur_csv_res.status_code == 200
    assert "cleaned_dataset_cur.csv" in cur_csv_res.headers.get("Content-Disposition", "")


def test_affected_rows_in_two_dataset_mode(client):
    """Item 2: Test Show Affected Records in Two Dataset mode (Reference and Current side)."""
    import io
    ref_csv = b"id,val,issue_col\n1,10,bad\n2,20,good\n3,30,bad\n"
    res = client.post("/api/session/new")
    sid = res.get_json()["session_id"]
    client.post("/api/upload/file", data={"file": (io.BytesIO(ref_csv), "ref.csv"), "dataset": "ref"},
                content_type="multipart/form-data", headers={"X-Session-Id": sid})

    # Test affected rows with indices for 'ref'
    aff_res = client.post("/api/dataset/affected-rows", json={"session_id": sid, "dataset": "ref", "indices": [0, 2]})
    assert aff_res.status_code == 200
    data = aff_res.get_json()
    assert "records" in data
    assert len(data["records"]) == 2
    assert data["records"][0]["issue_col"] == "bad"
    assert data["records"][1]["issue_col"] == "bad"

    # Also test with alias "reference"
    aff_alias = client.post("/api/dataset/affected-rows", json={"session_id": sid, "dataset": "reference", "indices": ["0", "2"]})
    assert aff_alias.status_code == 200
    assert len(aff_alias.get_json()["records"]) == 2


def test_download_missing_values_log_excel(client):
    """Item 3: Test Download Missing Values Log endpoint and openpyxl workbook structure."""
    import io
    import openpyxl
    csv_data = b"customer_id,income,city\nCUST_1,50000,NYC\nCUST_2,,LA\nCUST_3,75000,\n"
    res = client.post("/api/session/new")
    sid = res.get_json()["session_id"]
    client.post("/api/upload/file", data={"file": (io.BytesIO(csv_data), "clients.csv"), "dataset": "single"},
                content_type="multipart/form-data", headers={"X-Session-Id": sid})

    # Fill missing on income
    client.post("/api/clean/fill-missing", json={"session_id": sid, "dataset": "single", "column": "income", "method": "mean"})

    # Download missing values log
    log_res = client.get(f"/api/download/missing-log?session_id={sid}&dataset=single")
    assert log_res.status_code == 200
    assert "missing_values_log_single.xlsx" in log_res.headers.get("Content-Disposition", "")
    assert len(log_res.data) > 0

    # Parse with openpyxl to verify headers and contents
    wb = openpyxl.load_workbook(io.BytesIO(log_res.data))
    ws = wb.active
    assert ws.title == "Missing Values Audit Log"
    assert "Missing Values Audit Log" in ws["A1"].value
    # Check headers at row 4
    headers = [ws.cell(row=4, column=c).value for c in range(1, 8)]
    assert "Column Name" in headers
    assert "Row Identifier" in headers
    assert "Original State" in headers
    assert "Resolution Method" in headers
    assert "Final Value" in headers

    # Verify rows 5 and 6 audit the 2 originally missing cells (income and city)
    logged_cols = [ws.cell(row=r, column=1).value for r in range(5, 7)]
    assert "income" in logged_cols
    assert "city" in logged_cols


def test_quality_score_at_start_of_report():
    """Verify Quality Score section appears at the start of report, before Statistics."""
    import pandas as pd
    from backend.reports.report_builder import build_single_report, build_comparison_report
    from backend.reports.html_renderer import render_html_report
    from backend.analysis import run_full_analysis

    df = pd.DataFrame({"col_a": [1, 2, 3], "col_b": ["x", "y", "z"]})
    analysis = run_full_analysis(df)
    report_data = build_single_report(
        ds_key="single",
        source_info={"filename": "test.csv", "type": "csv"},
        df_original=df,
        df_final=df,
        analysis_before=analysis,
        analysis_after=analysis,
        change_history=[],
        dataset_label="Single Dataset"
    )
    html = render_html_report(report_data)
    qs_idx = html.find("<h2>Data Quality Score</h2>")
    stats_idx = html.find("<h2>Statistics (Final State)</h2>")
    assert qs_idx != -1, "Data Quality Score section not found"
    assert stats_idx != -1, "Statistics section not found"
    assert qs_idx < stats_idx, "Data Quality Score must appear BEFORE Statistics"


def test_no_dataframe_ambiguity_in_finalized_two_dataset_reports(client):
    """Verify Reference and Current standalone PDF reports succeed when datasets are finalized."""
    import io
    ref_csv = b"id,val\n1,10\n2,20\n"
    cur_csv = b"id,val\n1,10\n2,25\n3,30\n"

    res = client.post("/api/session/new")
    sid = res.get_json()["session_id"]
    client.post("/api/session/mode", json={"session_id": sid, "mode": "compare"})

    client.post("/api/upload/file", data={"file": (io.BytesIO(ref_csv), "ref.csv"), "dataset": "ref", "session_id": sid},
                content_type="multipart/form-data")
    client.post("/api/upload/file", data={"file": (io.BytesIO(cur_csv), "cur.csv"), "dataset": "cur", "session_id": sid},
                content_type="multipart/form-data")

    # Finalize both
    f_ref = client.post("/api/clean/finalize", json={"session_id": sid, "dataset": "ref"})
    assert f_ref.status_code == 200
    f_cur = client.post("/api/clean/finalize", json={"session_id": sid, "dataset": "cur"})
    assert f_cur.status_code == 200

    # Standalone Reference PDF
    ref_pdf = client.post("/api/report/pdf", json={"session_id": sid, "mode": "compare", "report_type": "reference"})
    assert ref_pdf.status_code == 200
    assert ref_pdf.data.startswith(b"%PDF")
    assert b"truth value of a DataFrame" not in ref_pdf.data

    # Standalone Current PDF
    cur_pdf = client.post("/api/report/pdf", json={"session_id": sid, "mode": "compare", "report_type": "current"})
    assert cur_pdf.status_code == 200
    assert cur_pdf.data.startswith(b"%PDF")
    assert b"truth value of a DataFrame" not in cur_pdf.data

    # Comparison PDF
    comp_pdf = client.post("/api/report/pdf", json={"session_id": sid, "mode": "compare", "report_type": "comparison"})
    assert comp_pdf.status_code == 200
    assert comp_pdf.data.startswith(b"%PDF")

    # Download missing logs for ref and cur
    ref_log = client.get(f"/api/download/missing-log?session_id={sid}&dataset=ref")
    assert ref_log.status_code == 200
    assert "missing_values_log_ref.xlsx" in ref_log.headers.get("Content-Disposition", "")

    cur_log = client.get(f"/api/download/missing-log?session_id={sid}&dataset=cur")
    assert cur_log.status_code == 200
    assert "missing_values_log_cur.xlsx" in cur_log.headers.get("Content-Disposition", "")


