"""Dynamic recommendations engine based on actual analysis results."""
import pandas as pd


def generate_recommendations(df: pd.DataFrame, analysis: dict) -> list:
    recs = []

    missing = analysis.get("missing", {})
    duplicates = analysis.get("duplicates", {})
    types = analysis.get("types", {})
    outliers = analysis.get("outliers", {})
    suspicious = analysis.get("suspicious", {})
    score_info = analysis.get("quality_score", {})

    # Missing values
    if missing.get("has_missing"):
        for col_info in missing.get("affected_columns", []):
            col = col_info["column"]
            pct = col_info["missing_pct"]
            is_num = col_info["is_numeric"]
            method = "Median imputation" if is_num else "Mode imputation"
            recs.append({
                "priority": _priority(pct),
                "category": "Missing Values",
                "title": f"Handle missing values in '{col}'",
                "what": f"{pct}% of values in '{col}' are missing ({col_info['missing_count']} records).",
                "why": "Missing values can bias statistical analysis and reduce model reliability.",
                "recommendation": f"{method} is recommended for this column type." if pct < 50 else
                    f"Column '{col}' is more than 50% missing. Consider deleting the column or using a specialized imputation strategy.",
                "action_hint": "fill_missing" if pct < 50 else "delete_column",
                "column": col,
            })

    # Duplicate rows
    if duplicates.get("has_duplicates"):
        dup_count = duplicates.get("total_duplicates", 0)
        dup_pct = duplicates.get("duplicate_pct", 0)
        recs.append({
            "priority": _priority(dup_pct),
            "category": "Duplicate Rows",
            "title": "Remove exact duplicate rows",
            "what": f"{dup_count} rows ({dup_pct:.1f}%) are exact duplicates of another row.",
            "why": "Exact duplicates inflate record counts and distort aggregations.",
            "recommendation": "Review the duplicate groups and remove unwanted duplicates. Preview before removal.",
            "action_hint": "remove_duplicates",
        })

    # Type issues
    for issue in types.get("type_issues", []):
        col = issue.get("column", "")
        recs.append({
            "priority": issue.get("severity", "medium"),
            "category": "Data-Type Issues",
            "title": f"Fix data type in '{col}'",
            "what": issue.get("description", ""),
            "why": "Incorrect data types prevent aggregation, sorting, and accurate analysis.",
            "recommendation": f"Convert '{col}' to {issue.get('proposed_type', 'appropriate type')}. Preview the conversion before applying.",
            "action_hint": "repair_type",
            "column": col,
        })

    # Suspicious values
    for issue in suspicious.get("suspicious_issues", []):
        col = issue.get("column", "")
        recs.append({
            "priority": issue.get("severity", "medium"),
            "category": "Suspicious Values",
            "title": f"Inspect suspicious values in '{col}'",
            "what": issue.get("description", ""),
            "why": issue.get("why", "Suspicious values may indicate data quality problems."),
            "recommendation": issue.get("recommendation", "Inspect and decide: keep, correct, or delete."),
            "action_hint": "edit_cell",
            "column": col,
        })

    # Outliers (informational)
    if outliers.get("has_outliers"):
        for col_info in outliers.get("outlier_details", []):
            col = col_info["column"]
            recs.append({
                "priority": "info",
                "category": "Potential Outliers",
                "title": f"Review potential outliers in '{col}'",
                "what": f"{col_info['combined_count']} potential outlier(s) detected in '{col}'.",
                "why": "Outliers are not necessarily errors — they may be valid extreme observations. Review before acting.",
                "recommendation": "Inspect each outlier value. If it appears to be an error, correct or delete it. Otherwise, keep it.",
                "action_hint": "inspect_outliers",
                "column": col,
            })

    # Sort by priority
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    recs.sort(key=lambda r: priority_order.get(r["priority"], 5))

    return recs


def _priority(pct: float) -> str:
    if pct >= 50:
        return "critical"
    if pct >= 20:
        return "high"
    if pct >= 5:
        return "medium"
    return "low"
