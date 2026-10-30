"""Dynamic quality scoring (0–100) based on data quality factors."""
import pandas as pd
from backend.utils.df_utils import is_numeric_col


def compute_quality_score(df: pd.DataFrame, analysis: dict) -> dict:
    """Return quality score and breakdown from analysis dict."""
    if df is None or len(df) == 0:
        return {"score": 0, "breakdown": {}, "label": "No Data", "factors": []}

    base = 100.0
    factors = []

    # 1. Missing values penalty (up to 30 pts)
    missing_info = analysis.get("missing", {})
    missing_pct = missing_info.get("missing_pct_overall", 0)
    missing_penalty = min(30, missing_pct * 0.6)
    factors.append({
        "name": "Missing Values",
        "penalty": round(missing_penalty, 2),
        "value": f"{missing_pct:.1f}% of cells missing",
        "weight": 30,
        "explanation": "Missing data reduces dataset completeness and can bias analysis.",
    })

    # 2. Duplicate rows penalty (up to 20 pts)
    dup_info = analysis.get("duplicates", {})
    dup_pct = dup_info.get("duplicate_pct", 0)
    dup_penalty = min(20, dup_pct * 0.4)
    factors.append({
        "name": "Duplicate Rows",
        "penalty": round(dup_penalty, 2),
        "value": f"{dup_pct:.1f}% of rows are exact duplicates",
        "weight": 20,
        "explanation": "Duplicate records inflate counts and distort statistical analysis.",
    })

    # 3. Data-type issues penalty (up to 20 pts)
    type_info = analysis.get("types", {})
    type_cols = type_info.get("columns_with_issues", 0)
    total_cols = max(len(df.columns), 1)
    type_pct = type_cols / total_cols * 100
    type_penalty = min(20, type_pct * 0.4)
    factors.append({
        "name": "Data-Type Issues",
        "penalty": round(type_penalty, 2),
        "value": f"{type_cols}/{total_cols} columns with type inconsistencies",
        "weight": 20,
        "explanation": "Incorrect data types prevent proper analysis and aggregation.",
    })

    # 4. Suspicious values penalty (up to 15 pts)
    susp_info = analysis.get("suspicious", {})
    # Avoid double-penalizing cells already penalized under Data-Type issues
    type_cells = set()
    for t_issue in analysis.get("types", {}).get("type_issues", []):
        t_col = t_issue.get("column")
        for idx in t_issue.get("affected_indices", []):
            type_cells.add((idx, t_col))

    susp_cells = set()
    for s_issue in susp_info.get("suspicious_issues", []):
        s_col = s_issue.get("column")
        for idx in s_issue.get("indices", []):
            if (idx, s_col) not in type_cells:
                susp_cells.add((idx, s_col))

    susp_count = len(susp_cells) if susp_info.get("suspicious_issues") else susp_info.get("total_suspicious_count", 0)
    total_cells = df.size
    susp_pct = susp_count / total_cells * 100 if total_cells > 0 else 0
    susp_penalty = min(15, susp_pct * 3)
    factors.append({
        "name": "Suspicious Values",
        "penalty": round(susp_penalty, 2),
        "value": f"{susp_count} suspicious value(s) detected",
        "weight": 15,
        "explanation": "Suspicious values (placeholders, extreme outliers) may indicate data quality problems.",
    })

    # Note about outliers
    outlier_info = analysis.get("outliers", {})
    outlier_cols = outlier_info.get("columns_with_outliers", 0)
    total_num_cols = max(sum(1 for c in df.columns if is_numeric_col(df[c])), 1)
    # informational_pct: proportion of numeric cols with outliers (0-100), used for bar width
    informational_pct = round(outlier_cols / total_num_cols * 100, 1)
    factors.append({
        "name": "Potential Outliers",
        "penalty": 0,
        "value": f"{outlier_cols} column(s) have potential outliers",
        "weight": 0,
        "explanation": "Outliers are not automatically penalized — they may be valid extreme values. Inspect manually.",
        "informational": True,
        "outlier_cols_count": outlier_cols,
        "informational_pct": informational_pct,
    })

    total_penalty = sum(f["penalty"] for f in factors if not f.get("informational"))
    score = max(0.0, min(100.0, base - total_penalty))

    return {
        "score": round(score, 1),
        "label": _score_label(score),
        "breakdown": {
            "missing_penalty": factors[0]["penalty"],
            "duplicate_penalty": factors[1]["penalty"],
            "type_penalty": factors[2]["penalty"],
            "suspicious_penalty": factors[3]["penalty"],
        },
        "factors": factors,
    }


def _score_label(score: float) -> str:
    if score >= 90:
        return "Excellent"
    if score >= 75:
        return "Good"
    if score >= 60:
        return "Fair"
    if score >= 40:
        return "Poor"
    return "Critical"
