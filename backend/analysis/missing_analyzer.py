"""Missing value analysis using centralized missing-value detection."""
import re
import pandas as pd
import numpy as np
from backend.utils.df_utils import is_numeric_col, is_categorical_col, get_missing_mask


# Substrings that hint at an identifier-like column (case-insensitive)
_ID_SUBSTRINGS = ["id", "_id", "uuid", "code", "key", "number", "no", "name"]
_ID_PATTERN = re.compile(
    r"(?:^|[_\-\s])(?:" + "|".join(re.escape(s) for s in _ID_SUBSTRINGS) + r")(?:[_\-\s]|$)",
    re.IGNORECASE,
)


def detect_identifier_column(series: pd.Series, col_name: str) -> dict:
    """Dynamically detect whether a column is identifier-like.

    Returns a dict with:
      - is_identifier: bool
      - confidence: 'strong' | 'weak' | None
      - label: human-readable label
      - reason: why it was flagged
    """
    signals = 0
    reasons = []

    # Signal 1: high uniqueness ratio (>95% unique among non-null)
    non_null = series.dropna()
    if len(non_null) > 0:
        uniqueness = non_null.nunique() / len(non_null)
        if uniqueness >= 0.95:
            signals += 1
            reasons.append(f"High uniqueness ratio ({uniqueness:.1%})")

    col_lower = str(col_name).lower().strip()
    has_name_signal = bool(_ID_PATTERN.search(col_lower) or col_lower in _ID_SUBSTRINGS)
    if has_name_signal:
        signals += 1
        reasons.append("Column name contains identifier-like substring")

    # High uniqueness alone is common in numeric float/price/timestamp columns and must NEVER flag an identifier
    if signals >= 2 and has_name_signal:
        return {
            "is_identifier": True,
            "confidence": "strong",
            "label": "Identifier-like column",
            "reason": "; ".join(reasons),
        }
    elif has_name_signal and (series.dtype == "object" or pd.api.types.is_integer_dtype(series)):
        # Column name strongly suggests ID (e.g. customer_id, order_code) even if not 100% unique
        return {
            "is_identifier": True,
            "confidence": "weak",
            "label": "Possible identifier column — manual verification recommended",
            "reason": "; ".join(reasons),
        }

    return {"is_identifier": False, "confidence": None, "label": None, "reason": None}


def analyze_missing(df: pd.DataFrame) -> dict:
    """Analyze missing values in the given DataFrame using centralized get_missing_mask."""
    if df is None or len(df) == 0:
        return {"total_cells": 0, "total_missing": 0, "missing_pct_overall": 0, "affected_columns": [], "has_missing": False, "columns_with_missing": 0}

    total_cells = df.size
    full_mask = get_missing_mask(df)
    total_missing = int(full_mask.sum().sum())
    missing_pct_overall = round(total_missing / total_cells * 100, 2) if total_cells > 0 else 0

    affected_columns = []
    for col in df.columns:
        series = df[col]
        col_mask = full_mask[col] if col in full_mask.columns else get_missing_mask(series)
        miss = int(col_mask.sum())
        if miss == 0:
            continue
        total = len(series)
        pct = round(miss / total * 100, 2)
        affected_rows = [int(i) for i in df[col_mask].index.tolist()[:50]]  # cap at 50

        id_info = detect_identifier_column(series, col)

        col_info = {
            "column": col,
            "dtype": str(series.dtype),
            "missing_count": miss,
            "missing_pct": pct,
            "total": total,
            "affected_row_indices": affected_rows,
            "is_numeric": bool(is_numeric_col(series)),
            "is_categorical": bool(is_categorical_col(series)),
            "severity": _severity(pct),
            "available_methods": _available_methods(series, id_info),
            "is_identifier": id_info["is_identifier"],
            "identifier_confidence": id_info["confidence"],
            "identifier_label": id_info["label"],
            "identifier_reason": id_info["reason"],
        }
        affected_columns.append(col_info)

    affected_columns.sort(key=lambda x: x["missing_pct"], reverse=True)

    return {
        "total_cells": total_cells,
        "total_missing": total_missing,
        "missing_pct_overall": missing_pct_overall,
        "affected_columns": affected_columns,
        "has_missing": total_missing > 0,
        "columns_with_missing": len(affected_columns),
    }


def _severity(pct: float) -> str:
    if pct >= 50:
        return "critical"
    if pct >= 20:
        return "high"
    if pct >= 5:
        return "medium"
    return "low"


def _available_methods(series: pd.Series, id_info: dict) -> list:
    """Return available imputation methods. For identifier columns, statistical
    methods are still listed but marked as not recommended, and delete_row is default."""
    if id_info.get("is_identifier"):
        methods = ["delete_row", "leave_unchanged", "manual"]
        if is_numeric_col(series):
            # Statistical methods are available but discouraged
            methods.extend([
                "mean (not recommended for identifier-like columns)",
                "median (not recommended for identifier-like columns)",
                "mean_excl_outliers (not recommended for identifier-like columns)",
                "median_excl_outliers (not recommended for identifier-like columns)",
            ])
        elif is_categorical_col(series):
            methods.append("mode (not recommended for identifier-like columns)")
        return methods
    # Normal columns
    methods = ["leave_unchanged", "delete_row", "manual"]
    if is_numeric_col(series):
        methods = ["mean", "median", "mean_excl_outliers", "median_excl_outliers"] + methods
    elif is_categorical_col(series):
        methods = ["mode"] + methods
    return methods


def compute_imputation_value(series: pd.Series, method: str) -> tuple:
    """Return (value, description) for the imputation method."""
    col_mask = get_missing_mask(series)
    non_null = series[~col_mask]
    if len(non_null) == 0:
        return None, "No non-null values to compute from."

    if method == "mean":
        val = float(pd.to_numeric(non_null, errors="coerce").mean())
        return val, f"Mean of non-null values: {val:.4f}"

    if method == "median":
        val = float(pd.to_numeric(non_null, errors="coerce").median())
        return val, f"Median of non-null values: {val:.4f}"

    if method in ("mean_excl_outliers", "median_excl_outliers"):
        num_vals = pd.to_numeric(non_null, errors="coerce").dropna()
        if len(num_vals) == 0:
            return None, "No numeric values to compute from."
        q1 = num_vals.quantile(0.25)
        q3 = num_vals.quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        filtered = num_vals[(num_vals >= lower) & (num_vals <= upper)]
        if len(filtered) == 0:
            filtered = num_vals
        if method == "mean_excl_outliers":
            val = float(filtered.mean())
            return val, f"Mean excluding outliers (IQR method): {val:.4f}"
        else:
            val = float(filtered.median())
            return val, f"Median excluding outliers (IQR method): {val:.4f}"

    if method == "mode":
        mode_vals = non_null.mode()
        if len(mode_vals) == 0:
            return None, "No mode found."
        val = str(mode_vals.iloc[0])
        return val, f"Mode of non-null values: {val}"

    return None, "Unknown method."

