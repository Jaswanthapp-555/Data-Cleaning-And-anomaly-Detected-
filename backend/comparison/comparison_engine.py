"""Master comparison engine for two-dataset comparison."""
import pandas as pd
import numpy as np
from backend.comparison.row_matcher import match_rows
from backend.comparison.drift_detector import detect_drift
from backend.utils.df_utils import is_numeric_col, is_categorical_col, safe_json_val, get_missing_mask, clean_numeric_series


def compare_datasets(ref_df: pd.DataFrame, cur_df: pd.DataFrame,
                     ref_analysis: dict, cur_analysis: dict) -> dict:
    """Produce a full comparison report between finalized reference and current datasets."""
    schema = _compare_schema(ref_df, cur_df)
    stats = _compare_stats(ref_df, cur_df)
    row_match = match_rows(ref_df, cur_df)
    drift = detect_drift(ref_df, cur_df)
    quality_comparison = _compare_quality(ref_analysis, cur_analysis)

    return {
        "schema": schema,
        "stats": stats,
        "row_match": row_match,
        "drift": drift,
        "quality": quality_comparison,
        "summary": _build_summary(schema, row_match, quality_comparison, drift),
    }


def _compare_schema(ref_df: pd.DataFrame, cur_df: pd.DataFrame) -> dict:
    ref_cols = set(ref_df.columns)
    cur_cols = set(cur_df.columns)
    added = list(cur_cols - ref_cols)
    removed = list(ref_cols - cur_cols)
    common = list(ref_cols & cur_cols)

    type_changes = []
    for col in common:
        rt = str(ref_df[col].dtype)
        ct = str(cur_df[col].dtype)
        if rt != ct:
            type_changes.append({
                "column": col,
                "reference_type": rt,
                "current_type": ct,
            })

    # Possible renames — look for removed cols similar to added cols
    possible_renames = []
    for rem in removed:
        for add in added:
            similarity = _name_similarity(rem, add)
            if similarity > 0.6:
                possible_renames.append({
                    "reference_column": rem,
                    "current_column": add,
                    "confidence": round(similarity, 2),
                    "note": "Possible column rename — manual verification recommended.",
                })

    return {
        "ref_columns": list(ref_df.columns),
        "cur_columns": list(cur_df.columns),
        "ref_col_count": len(ref_df.columns),
        "cur_col_count": len(cur_df.columns),
        "added_columns": added,
        "removed_columns": removed,
        "common_columns": common,
        "type_changes": type_changes,
        "possible_renames": possible_renames,
        "ref_row_count": len(ref_df),
        "cur_row_count": len(cur_df),
        "row_count_change": len(cur_df) - len(ref_df),
    }


def _try_get_numeric_series(series: pd.Series, col_name: str = "") -> pd.Series | None:
    """Safely obtain a numeric float Series or return None if series is categorical/text or identifier."""
    from backend.utils.df_utils import is_identifier_col
    from backend.analysis.missing_analyzer import detect_identifier_column

    if series is None or len(series) == 0:
        return None

    # Never compute numeric statistics on identifier columns
    if is_identifier_col(series, col_name):
        return None
    id_info = detect_identifier_column(series, col_name)
    if id_info.get("is_identifier"):
        return None

    if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
        return pd.to_numeric(series, errors="coerce")

    col_mask = get_missing_mask(series)
    non_null = series[~col_mask]
    if len(non_null) == 0:
        return None

    cleaned = clean_numeric_series(non_null)
    try:
        valid_numeric = pd.to_numeric(cleaned, errors="coerce").dropna()
        if len(valid_numeric) / len(non_null) > 0.8:
            return pd.to_numeric(clean_numeric_series(series), errors="coerce")
    except Exception:
        pass
    return None


def _calc_numeric_stats(num_series: pd.Series) -> dict:
    """Safely compute summary statistics on a guaranteed numeric series."""
    if num_series is None:
        return {"count": 0, "mean": None, "median": None, "std": None, "min": None, "max": None, "q1": None, "q3": None}

    # Ensure strictly float64 numeric values only
    s = pd.to_numeric(num_series, errors="coerce").dropna()
    n = len(s)
    if n == 0:
        return {"count": 0, "mean": None, "median": None, "std": None, "min": None, "max": None, "q1": None, "q3": None}

    try:
        mean_val = float(s.mean())
    except Exception:
        mean_val = None

    try:
        med_val = float(s.median())
    except Exception:
        med_val = None

    try:
        std_val = float(s.std()) if n > 1 else None
    except Exception:
        std_val = None

    try:
        min_val = float(s.min())
        max_val = float(s.max())
        q1_val = float(s.quantile(0.25))
        q3_val = float(s.quantile(0.75))
    except Exception:
        min_val = max_val = q1_val = q3_val = None

    return {
        "count": n,
        "mean": safe_json_val(mean_val),
        "median": safe_json_val(med_val),
        "std": safe_json_val(std_val),
        "min": safe_json_val(min_val),
        "max": safe_json_val(max_val),
        "q1": safe_json_val(q1_val),
        "q3": safe_json_val(q3_val),
    }


def _compare_stats(ref_df: pd.DataFrame, cur_df: pd.DataFrame) -> list:
    common_cols = [c for c in ref_df.columns if c in cur_df.columns]
    results = []
    for col in common_cols:
        ref_s = ref_df[col]
        cur_s = cur_df[col]

        # First classify: strictly numeric vs categorical / text
        ref_num = _try_get_numeric_series(ref_s, col)
        cur_num = _try_get_numeric_series(cur_s, col)

        if ref_num is not None and cur_num is not None:
            # Both columns can be analyzed numerically
            results.append({
                "column": col,
                "type": "numerical",
                "reference": _calc_numeric_stats(ref_num),
                "current": _calc_numeric_stats(cur_num),
            })
        else:
            # Text / Categorical comparison — NEVER apply numeric reduction
            ref_non_null = ref_s.dropna().astype(str)
            cur_non_null = cur_s.dropna().astype(str)

            ref_vc = ref_non_null.value_counts()
            cur_vc = cur_non_null.value_counts()
            ref_pct = ref_non_null.value_counts(normalize=True) * 100
            cur_pct = cur_non_null.value_counts(normalize=True) * 100

            ref_cats = set(ref_vc.index.tolist())
            cur_cats = set(cur_vc.index.tolist())
            new_cats = [str(c) for c in (cur_cats - ref_cats)][:25]
            removed_cats = [str(c) for c in (ref_cats - cur_cats)][:25]

            top_n = 5
            ref_top_cats = [{"category": str(k), "count": int(v), "proportion": round(float(ref_pct.get(k, 0)), 2)}
                            for k, v in ref_vc.head(top_n).items()]
            cur_top_cats = [{"category": str(k), "count": int(v), "proportion": round(float(cur_pct.get(k, 0)), 2)}
                            for k, v in cur_vc.head(top_n).items()]

            results.append({
                "column": col,
                "type": "categorical",
                "reference": {
                    "count": int(len(ref_non_null)),
                    "unique": int(len(ref_cats)),
                    "top": str(ref_vc.index[0]) if len(ref_vc) > 0 else None,
                    "frequencies": {str(k): int(v) for k, v in ref_vc.head(top_n).items()},
                    "proportions": {str(k): round(float(v), 2) for k, v in ref_pct.head(top_n).items()},
                    "top_categories": ref_top_cats,
                },
                "current": {
                    "count": int(len(cur_non_null)),
                    "unique": int(len(cur_cats)),
                    "top": str(cur_vc.index[0]) if len(cur_vc) > 0 else None,
                    "frequencies": {str(k): int(v) for k, v in cur_vc.head(top_n).items()},
                    "proportions": {str(k): round(float(v), 2) for k, v in cur_pct.head(top_n).items()},
                    "top_categories": cur_top_cats,
                },
                "new_categories": new_cats,
                "removed_categories": removed_cats,
            })
    return results


def _compare_quality(ref_analysis: dict, cur_analysis: dict) -> dict:
    ref_score = ref_analysis.get("quality_score", {}).get("score", 0) if ref_analysis else 0
    cur_score = cur_analysis.get("quality_score", {}).get("score", 0) if cur_analysis else 0
    ref_missing = ref_analysis.get("missing", {}).get("missing_pct_overall", 0) if ref_analysis else 0
    cur_missing = cur_analysis.get("missing", {}).get("missing_pct_overall", 0) if cur_analysis else 0
    ref_dups = ref_analysis.get("duplicates", {}).get("total_duplicates", 0) if ref_analysis else 0
    cur_dups = cur_analysis.get("duplicates", {}).get("total_duplicates", 0) if cur_analysis else 0

    return {
        "reference_score": ref_score,
        "current_score": cur_score,
        "score_change": round(cur_score - ref_score, 1),
        "reference_missing_pct": ref_missing,
        "current_missing_pct": cur_missing,
        "missing_change": round(cur_missing - ref_missing, 2),
        "reference_duplicates": ref_dups,
        "current_duplicates": cur_dups,
        "duplicate_change": cur_dups - ref_dups,
    }


def _build_summary(schema: dict, row_match: dict, quality: dict, drift: list) -> dict:
    drift_detected = sum(1 for d in drift if d.get("drift_detected", False))

    added_names = ", ".join(f"'{c}'" for c in schema["added_columns"][:5])
    if len(schema["added_columns"]) > 5:
        added_names += f" (+{len(schema['added_columns']) - 5} more)"

    removed_names = ", ".join(f"'{c}'" for c in schema["removed_columns"][:5])
    if len(schema["removed_columns"]) > 5:
        removed_names += f" (+{len(schema['removed_columns']) - 5} more)"

    score_chg = quality["score_change"]
    score_verb = f"+{score_chg} points" if score_chg > 0 else (f"{score_chg} points" if score_chg < 0 else "unchanged")

    # Plain-language narrative paragraph (Item 6b & 6e)
    narrative = (
        f"Reference dataset: {schema['ref_col_count']} columns, {schema['ref_row_count']} rows, "
        f"Quality Score {quality['reference_score']}/100. "
        f"Current dataset: {schema['cur_col_count']} columns, {schema['cur_row_count']} rows, "
        f"Quality Score {quality['current_score']}/100. "
        f"Between versions: {len(schema['added_columns'])} column(s) added"
        + (f" ({added_names})" if schema["added_columns"] else "")
        + f", {len(schema['removed_columns'])} column(s) removed"
        + (f" ({removed_names})" if schema["removed_columns"] else "")
        + f", and {len(schema['type_changes'])} data type shift(s). "
        f"{row_match['deleted_count']} record(s) deleted, {row_match['new_count']} new record(s) added, "
        f"and {row_match['modified_count']} record(s) had at least one modified value. "
        f"Overall quality score changed by {score_verb}. "
        f"{row_match['strategy']}."
    )

    return {
        "columns_added": len(schema["added_columns"]),
        "columns_removed": len(schema["removed_columns"]),
        "type_changes": len(schema["type_changes"]),
        "row_count_change": schema["row_count_change"],
        "new_records": row_match["new_count"],
        "deleted_records": row_match["deleted_count"],
        "modified_records": row_match["modified_count"],
        "unchanged_records": row_match["unchanged_count"],
        "quality_score_change": quality["score_change"],
        "drift_columns": drift_detected,
        "strategy": row_match["strategy"],
        "matching_strategy": row_match["strategy"],
        "matching_strategy_note": row_match["strategy"],
        "narrative": narrative,
    }


def _name_similarity(a: str, b: str) -> float:
    """Simple character overlap similarity."""
    a_lower = a.lower().replace("_", "").replace(" ", "")
    b_lower = b.lower().replace("_", "").replace(" ", "")
    if not a_lower or not b_lower:
        return 0.0
    overlap = len(set(a_lower) & set(b_lower))
    return overlap / max(len(set(a_lower)), len(set(b_lower)))

