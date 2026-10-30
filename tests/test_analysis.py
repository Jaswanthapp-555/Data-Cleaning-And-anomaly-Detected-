import pandas as pd
from backend.analysis import run_full_analysis
from backend.analysis.missing_analyzer import analyze_missing
from backend.analysis.duplicate_analyzer import analyze_duplicates
from backend.analysis.outlier_analyzer import analyze_outliers


def test_full_analysis(sample_df):
    res = run_full_analysis(sample_df)
    assert "quality_score" in res
    assert "missing" in res
    assert "duplicates" in res
    assert "outliers" in res
    assert "stats" in res
    assert "issue_center" in res
    assert "recommendations" in res


def test_missing_analysis():
    df = pd.DataFrame({"A": [1, None, 3], "B": ["x", "y", None]})
    res = analyze_missing(df)
    assert res["total_missing"] == 2
    assert res["columns_with_missing"] == 2


def test_exact_duplicate_rule():
    # A,20,Chennai vs A,21,Chennai are NOT duplicates
    df = pd.DataFrame([
        {"A": "X", "B": 20, "C": "Chennai"},
        {"A": "X", "B": 21, "C": "Chennai"},
        {"A": "X", "B": 20, "C": "Chennai"},  # Exact duplicate of row 0
    ])
    res = analyze_duplicates(df)
    # Total duplicates should be 2 (rows 0 and 2 form a dup pair)
    assert res["total_duplicates"] == 2
    assert len(res["duplicate_groups"]) == 1
    assert res["duplicate_groups"][0]["indices"] == [0, 2]


def test_outlier_analysis():
    df = pd.DataFrame({"val": [10, 12, 11, 13, 12, 11, 10, 12, 1000]})  # 1000 is IQR outlier
    res = analyze_outliers(df)
    assert res["has_outliers"] is True
    assert res["outlier_details"][0]["column"] == "val"
