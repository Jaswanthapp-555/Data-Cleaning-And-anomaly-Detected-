"""Master analysis orchestrator — runs all sub-analyzers and assembles full analysis result."""
import pandas as pd
from backend.analysis.schema_analyzer import analyze_schema
from backend.analysis.missing_analyzer import analyze_missing
from backend.analysis.duplicate_analyzer import analyze_duplicates
from backend.analysis.outlier_analyzer import analyze_outliers
from backend.analysis.type_analyzer import analyze_types
from backend.analysis.suspicious_analyzer import analyze_suspicious
from backend.analysis.stats_analyzer import analyze_stats
from backend.analysis.quality_scorer import compute_quality_score
from backend.analysis.recommender import generate_recommendations


def run_full_analysis(df: pd.DataFrame, kept_cells: set = None) -> dict:
    """Run all analysis modules on a DataFrame and return complete results."""
    if df is None or len(df) == 0:
        return {"error": "Dataset is empty or could not be loaded."}

    try:
        schema = analyze_schema(df)
    except Exception as e:
        import traceback; traceback.print_exc()
        schema = {"row_count": len(df), "col_count": len(df.columns), "column_names": list(df.columns), "columns": [], "schema_issues": [], "has_duplicate_headers": False, "empty_rows": 0}

    try:
        missing = analyze_missing(df)
    except Exception as e:
        import traceback; traceback.print_exc()
        missing = {"total_cells": df.size, "total_missing": 0, "missing_pct_overall": 0, "affected_columns": [], "has_missing": False, "columns_with_missing": 0}

    try:
        duplicates = analyze_duplicates(df)
    except Exception as e:
        import traceback; traceback.print_exc()
        duplicates = {"total_duplicates": 0, "duplicate_groups": [], "has_duplicates": False, "duplicate_pct": 0.0}

    try:
        outliers = analyze_outliers(df, kept_cells=kept_cells)
    except Exception as e:
        import traceback; traceback.print_exc()
        outliers = {"columns_with_outliers": 0, "outlier_details": [], "has_outliers": False, "note": "Potential anomalies are reported here. An outlier is NOT automatically an error."}

    try:
        types = analyze_types(df, kept_cells=kept_cells)
    except Exception as e:
        import traceback; traceback.print_exc()
        types = {"type_issues": [], "has_type_issues": False, "columns_with_issues": 0, "column_details": []}

    try:
        suspicious = analyze_suspicious(df, kept_cells=kept_cells)
    except Exception as e:
        import traceback; traceback.print_exc()
        suspicious = {"suspicious_issues": [], "has_suspicious": False, "total_suspicious_count": 0}

    try:
        stats = analyze_stats(df)
    except Exception as e:
        import traceback; traceback.print_exc()
        stats = {"numerical": [], "categorical": [], "has_numerical": False, "has_categorical": False}

    analysis = {
        "schema": schema,
        "missing": missing,
        "duplicates": duplicates,
        "outliers": outliers,
        "types": types,
        "suspicious": suspicious,
        "stats": stats,
    }

    try:
        quality_score = compute_quality_score(df, analysis)
    except Exception as e:
        import traceback; traceback.print_exc()
        quality_score = {"score": 50.0, "label": "Fair", "breakdown": {}, "factors": []}
    analysis["quality_score"] = quality_score

    try:
        recommendations = generate_recommendations(df, analysis)
    except Exception as e:
        import traceback; traceback.print_exc()
        recommendations = []
    analysis["recommendations"] = recommendations

    # Build issue center list
    try:
        analysis["issue_center"] = _build_issue_center(analysis)
    except Exception as e:
        import traceback; traceback.print_exc()
        analysis["issue_center"] = []

    return analysis


def _build_issue_center(analysis: dict) -> list:
    """Assemble all issues into a unified, categorized list."""
    issues = []

    # Missing values
    for col in analysis["missing"].get("affected_columns", []):
        count = col.get("missing_count", 0)
        aff_idx = col.get("affected_row_indices", [])
        if count <= 0 or len(aff_idx) == 0:
            continue
        issues.append({
            "category": "Missing Values",
            "severity": col["severity"],
            "column": col["column"],
            "count": count,
            "pct": col.get("missing_pct"),
            "description": f"{count} missing values ({col.get('missing_pct')}%) in column '{col['column']}'",
            "affected_indices": aff_idx,
            "action_hint": "fill_missing",
        })

    # Duplicates
    if analysis["duplicates"].get("has_duplicates"):
        dup_count = analysis["duplicates"].get("total_duplicates", 0)
        dup_indices = [i for g in analysis["duplicates"].get("duplicate_groups", []) for i in g.get("indices", [])]
        if dup_count > 0 and len(dup_indices) > 0:
            issues.append({
                "category": "Duplicate Rows",
                "severity": "high" if analysis["duplicates"].get("duplicate_pct", 0) > 20 else "medium",
                "column": None,
                "count": dup_count,
                "pct": analysis["duplicates"].get("duplicate_pct"),
                "description": f"{dup_count} exact duplicate rows detected",
                "affected_indices": dup_indices,
                "action_hint": "remove_duplicates",
            })

    # Type issues
    for issue in analysis["types"].get("type_issues", []):
        aff_idx = issue.get("affected_indices", [])
        if len(aff_idx) == 0:
            continue
        issues.append({
            "category": "Data-Type Issues",
            "severity": issue.get("severity", "medium"),
            "column": issue.get("column", ""),
            "count": len(aff_idx),
            "pct": None,
            "description": issue.get("description", ""),
            "affected_indices": aff_idx,
            "action_hint": "repair_type",
            "recommended_type": issue.get("proposed_type") or issue.get("recommended_type", ""),
        })

    # Suspicious values & Category Inconsistencies
    for issue in analysis["suspicious"].get("suspicious_issues", []):
        aff_idx = issue.get("indices", [])
        count = issue.get("count", len(aff_idx))
        if count <= 0 or len(aff_idx) == 0:
            continue
        cat_type = issue.get("category_type")
        is_inconsistency = cat_type == "inconsistency" or issue.get("type") in ("CASING_INCONSISTENCY", "WHITESPACE_INCONSISTENCY", "CATEGORY_INCONSISTENCY")
        category_label = "Category Inconsistencies" if is_inconsistency else "Suspicious Values"
        issues.append({
            "category": category_label,
            "severity": issue.get("severity", "medium"),
            "column": issue.get("column", ""),
            "count": count,
            "pct": None,
            "description": issue.get("description", ""),
            "affected_indices": aff_idx,
            "action_hint": "resolve_suspicious",
            "type": issue.get("type"),
            "category_type": cat_type or ("inconsistency" if is_inconsistency else "invalid"),
            "why": issue.get("why"),
            "recommendation": issue.get("recommendation"),
            "row_details": issue.get("row_details", []),
        })

    # Outliers (informational)
    for col_info in analysis["outliers"].get("outlier_details", []):
        out_count = col_info.get("combined_count", 0)
        out_indices = col_info.get("combined_indices", [])
        if out_count <= 0 or len(out_indices) == 0:
            continue
        issues.append({
            "category": "Potential Outliers",
            "severity": "info",
            "column": col_info["column"],
            "count": out_count,
            "pct": col_info.get("affected_pct"),
            "description": f"{out_count} potential outlier(s) in column '{col_info['column']}'",
            "affected_indices": out_indices[:50],
            "action_hint": "inspect_outliers",
        })

    # Schema issues removed from single-dataset analysis per specifications

    # Sort by severity
    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    issues.sort(key=lambda x: sev_order.get(x["severity"], 5))
    return issues
