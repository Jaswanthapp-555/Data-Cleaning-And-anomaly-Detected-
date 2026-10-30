"""KS-test based distribution drift detection."""
import pandas as pd
import numpy as np
from backend.utils.df_utils import is_numeric_col, is_categorical_col, is_datetime_col, is_identifier_col, clean_numeric_series, get_missing_mask
from backend.analysis.missing_analyzer import detect_identifier_column

MIN_SAMPLES = 20


def _try_get_numeric_series(series: pd.Series) -> pd.Series | None:
    if series is None or len(series) == 0:
        return None
    if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    col_mask = get_missing_mask(series)
    non_null = series[~col_mask]
    if len(non_null) == 0:
        return None
    cleaned = clean_numeric_series(non_null)
    if float(cleaned.notna().mean()) > 0.8:
        return clean_numeric_series(series)
    return None


def detect_drift(ref_df: pd.DataFrame, cur_df: pd.DataFrame) -> list:
    """Compare distributions of common columns between two DataFrames."""
    results = []
    common_cols = [c for c in ref_df.columns if c in cur_df.columns]

    for col in common_cols:
        ref_s = ref_df[col]
        cur_s = cur_df[col]

        # 1. Skip identifier-like columns (meaningless for unique IDs)
        is_id = is_identifier_col(ref_s, col) or is_identifier_col(cur_s, col)
        if not is_id:
            ref_id_info = detect_identifier_column(ref_s, col)
            cur_id_info = detect_identifier_column(cur_s, col)
            if ref_id_info.get("is_identifier") or cur_id_info.get("is_identifier"):
                is_id = True

        if is_id:
            results.append({
                "column": col,
                "type": "identifier",
                "ks_available": False,
                "drift_detected": False,
                "note": "Identifier column — distribution drift analysis skipped as values represent individual record IDs.",
                "interpretation": "Unique identifier column; distribution drift is not applicable.",
            })
            continue

        # 2. Date columns — time-based trend analysis
        if is_datetime_col(ref_s) or is_datetime_col(cur_s):
            results.append(_datetime_drift(ref_s, cur_s, col))
            continue

        # 3. Numeric vs Categorical classification
        ref_num = _try_get_numeric_series(ref_s)
        cur_num = _try_get_numeric_series(cur_s)

        if ref_num is not None and cur_num is not None:
            results.append(_numeric_drift(ref_num.dropna(), cur_num.dropna(), col))
        else:
            ref_series = ref_s.dropna().astype(str)
            cur_series = cur_s.dropna().astype(str)
            results.append(_categorical_drift(ref_series, cur_series, col))

    return results


def _datetime_drift(ref_series: pd.Series, cur_series: pd.Series, col: str) -> dict:
    """Time-based trend and temporal coverage comparison for date columns."""
    ref_dt = pd.to_datetime(ref_series, errors="coerce").dropna()
    cur_dt = pd.to_datetime(cur_series, errors="coerce").dropna()

    ref_min = str(ref_dt.min().date()) if len(ref_dt) > 0 else "N/A"
    ref_max = str(ref_dt.max().date()) if len(ref_dt) > 0 else "N/A"
    cur_min = str(cur_dt.min().date()) if len(cur_dt) > 0 else "N/A"
    cur_max = str(cur_dt.max().date()) if len(cur_dt) > 0 else "N/A"

    ref_days = (ref_dt.max() - ref_dt.min()).days if len(ref_dt) > 1 else 0
    cur_days = (cur_dt.max() - cur_dt.min()).days if len(cur_dt) > 1 else 0

    parts = []
    if ref_min != cur_min or ref_max != cur_max:
        parts.append(f"Temporal span shifted: Reference [{ref_min} to {ref_max}] vs Current [{cur_min} to {cur_max}].")
    else:
        parts.append(f"Temporal range stable [{ref_min} to {ref_max}].")

    drift_detected = (ref_min != cur_min) or (ref_max != cur_max) or (abs(cur_days - ref_days) > 7)

    return {
        "column": col,
        "type": "datetime",
        "ks_available": False,
        "ref_count": int(len(ref_dt)),
        "cur_count": int(len(cur_dt)),
        "ref_min_date": ref_min,
        "ref_max_date": ref_max,
        "cur_min_date": cur_min,
        "cur_max_date": cur_max,
        "ref_span_days": ref_days,
        "cur_span_days": cur_days,
        "drift_detected": drift_detected,
        "interpretation": " ".join(parts),
    }


def _numeric_drift(ref_series: pd.Series, cur_series: pd.Series, col: str) -> dict:
    # Strictly coerce to float64 numeric arrays to ensure no string dtype reductions
    ref_series = pd.to_numeric(ref_series, errors="coerce").dropna()
    cur_series = pd.to_numeric(cur_series, errors="coerce").dropna()

    result = {
        "column": col,
        "type": "numerical",
        "ref_count": int(len(ref_series)),
        "cur_count": int(len(cur_series)),
    }

    if len(ref_series) < MIN_SAMPLES or len(cur_series) < MIN_SAMPLES:
        result["ks_available"] = False
        result["note"] = f"Insufficient data for KS test (need ≥{MIN_SAMPLES} samples per dataset)."
        result["drift_detected"] = False
        result["ref_mean"] = round(float(ref_series.mean()), 4) if len(ref_series) > 0 else 0.0
        result["cur_mean"] = round(float(cur_series.mean()), 4) if len(cur_series) > 0 else 0.0
        return result

    try:
        from scipy.stats import ks_2samp
        ks_stat, p_value = ks_2samp(ref_series.values, cur_series.values)
        significant = p_value < 0.05
        result.update({
            "ks_available": True,
            "ks_statistic": round(float(ks_stat), 4),
            "p_value": round(float(p_value), 4),
            "significance_threshold": 0.05,
            "drift_detected": bool(significant),
            "interpretation": (
                f"Possible distribution shift detected (KS statistic={ks_stat:.4f}, p={p_value:.4f}). "
                "This indicates a statistically significant difference in distributions."
            ) if significant else (
                f"No statistically significant distribution shift detected (KS statistic={ks_stat:.4f}, p={p_value:.4f})."
            ),
            "caution": "Statistical significance does not automatically imply practical importance. Review the actual values.",
        })
    except Exception as e:
        result["ks_available"] = False
        result["error"] = str(e)
        result["drift_detected"] = False

    # Safely compute summary stats
    try:
        result["ref_mean"] = round(float(ref_series.mean()), 4) if len(ref_series) > 0 else 0.0
        result["cur_mean"] = round(float(cur_series.mean()), 4) if len(cur_series) > 0 else 0.0
        result["ref_std"] = round(float(ref_series.std()), 4) if len(ref_series) > 1 else 0.0
        result["cur_std"] = round(float(cur_series.std()), 4) if len(cur_series) > 1 else 0.0
        result["mean_change_pct"] = round((result["cur_mean"] - result["ref_mean"]) / abs(result["ref_mean"]) * 100, 2) if result["ref_mean"] != 0 else None
    except Exception:
        result["ref_mean"] = None
        result["cur_mean"] = None
        result["ref_std"] = None
        result["cur_std"] = None
        result["mean_change_pct"] = None

    return result


def _categorical_drift(ref_series: pd.Series, cur_series: pd.Series, col: str) -> dict:
    ref_counts = ref_series.value_counts(normalize=True)
    cur_counts = cur_series.value_counts(normalize=True)

    ref_cats = set(ref_series.unique())
    cur_cats = set(cur_series.unique())
    new_cats = list(cur_cats - ref_cats)
    removed_cats = list(ref_cats - cur_cats)

    freq_changes = []
    for cat in ref_cats & cur_cats:
        ref_pct = round(float(ref_counts.get(cat, 0)) * 100, 2)
        cur_pct = round(float(cur_counts.get(cat, 0)) * 100, 2)
        if abs(ref_pct - cur_pct) > 5:
            freq_changes.append({
                "category": str(cat),
                "reference_pct": ref_pct,
                "current_pct": cur_pct,
                "change_pct": round(cur_pct - ref_pct, 2),
            })

    return {
        "column": col,
        "type": "categorical",
        "ref_count": int(len(ref_series)),
        "cur_count": int(len(cur_series)),
        "ref_unique": int(ref_series.nunique()),
        "cur_unique": int(cur_series.nunique()),
        "new_categories": new_cats[:20],
        "removed_categories": removed_cats[:20],
        "frequency_changes": freq_changes[:20],
        "drift_detected": bool(new_cats or removed_cats or freq_changes),
        "ks_available": False,
        "interpretation": _categorical_interpretation(new_cats, removed_cats, freq_changes),
    }


def _categorical_interpretation(new_cats, removed_cats, freq_changes) -> str:
    parts = []
    if new_cats:
        parts.append(f"{len(new_cats)} new category/categories appeared.")
    if removed_cats:
        parts.append(f"{len(removed_cats)} category/categories were removed.")
    if freq_changes:
        parts.append(f"{len(freq_changes)} category/categories changed proportion by >5%.")
    return " ".join(parts) if parts else "No notable categorical distribution changes detected."

