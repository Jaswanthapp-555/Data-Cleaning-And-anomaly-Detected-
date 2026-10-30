"""Descriptive statistics for numerical and categorical columns using centralized missing-value detection."""
import pandas as pd
import numpy as np
from backend.utils.df_utils import is_numeric_col, is_categorical_col, safe_json_val, get_missing_mask


def analyze_stats(df: pd.DataFrame) -> dict:
    numerical = []
    categorical = []

    for col in df.columns:
        try:
            series = df[col]
            if is_numeric_col(series):
                numerical.append(_numeric_stats(series, col))
            elif is_categorical_col(series):
                categorical.append(_categorical_stats(series, col))
            else:
                col_mask = get_missing_mask(series)
                if len(series[~col_mask]) == 0:
                    categorical.append({"column": col, "insufficient_data": True, "message": "Insufficient data for reliable analysis"})
        except Exception:
            numerical.append({"column": col, "insufficient_data": True, "message": "Insufficient data for reliable analysis"})

    return {
        "numerical": numerical,
        "categorical": categorical,
        "has_numerical": len(numerical) > 0,
        "has_categorical": len(categorical) > 0,
    }


def _safe_float(val, n=4):
    if val is None or pd.isna(val):
        return None
    try:
        f = float(val)
        if np.isnan(f) or np.isinf(f):
            return None
        return round(f, n)
    except Exception:
        return None


def _numeric_stats(series: pd.Series, col: str) -> dict:
    col_mask = get_missing_mask(series)
    non_null = series[~col_mask]
    if len(non_null) == 0:
        return {"column": col, "insufficient_data": True, "message": "Insufficient data for reliable analysis"}

    num_vals = pd.to_numeric(non_null, errors="coerce").dropna()
    if len(num_vals) == 0:
        return {"column": col, "insufficient_data": True, "message": "Insufficient data for reliable analysis"}

    q1 = float(num_vals.quantile(0.25))
    q2 = float(num_vals.quantile(0.50))
    q3 = float(num_vals.quantile(0.75))
    iqr = q3 - q1

    skewness = None
    kurt = None
    if len(num_vals) >= 3 and len(num_vals.unique()) > 1:
        try:
            from scipy.stats import skew, kurtosis
            s = float(skew(num_vals.values))
            if not np.isnan(s) and not np.isinf(s):
                skewness = s
        except Exception:
            try:
                s = float(num_vals.skew())
                if not np.isnan(s) and not np.isinf(s):
                    skewness = s
            except Exception:
                pass

    if len(num_vals) >= 4 and len(num_vals.unique()) > 1:
        try:
            from scipy.stats import kurtosis
            k = float(kurtosis(num_vals.values))
            if not np.isnan(k) and not np.isinf(k):
                kurt = k
        except Exception:
            try:
                k = float(num_vals.kurtosis())
                if not np.isnan(k) and not np.isinf(k):
                    kurt = k
            except Exception:
                pass

    mean_val = _safe_float(num_vals.mean())
    std_val = _safe_float(num_vals.std()) if len(num_vals) >= 2 else None
    var_val = _safe_float(num_vals.var()) if len(num_vals) >= 2 else None
    min_val = safe_json_val(num_vals.min())
    max_val = safe_json_val(num_vals.max())
    range_val = _safe_float(num_vals.max() - num_vals.min()) if len(num_vals) >= 2 else 0.0

    return {
        "column": col,
        "count": int(len(num_vals)),
        "missing": int(col_mask.sum()),
        "mean": mean_val,
        "median": _safe_float(num_vals.median()),
        "std": std_val,
        "variance": var_val,
        "min": min_val,
        "max": max_val,
        "range": range_val,
        "q1": _safe_float(q1),
        "q2": _safe_float(q2),
        "q3": _safe_float(q3),
        "iqr": _safe_float(iqr),
        "skewness": _safe_float(skewness),
        "kurtosis": _safe_float(kurt),
        "skewness_interpretation": _skewness_label(skewness),
    }


def _categorical_stats(series: pd.Series, col: str) -> dict:
    col_mask = get_missing_mask(series)
    non_null = series[~col_mask]
    if len(non_null) == 0:
        return {"column": col, "insufficient_data": True, "message": "Insufficient data for reliable analysis"}

    vc = non_null.value_counts()
    total = len(non_null)
    top_values = [
        {"value": str(k), "count": int(v), "pct": round(v / total * 100, 2)}
        for k, v in vc.head(10).items()
    ]

    return {
        "column": col,
        "count": int(len(non_null)),
        "missing": int(col_mask.sum()),
        "unique_count": int(non_null.nunique()),
        "top_values": top_values,
        "most_common": str(vc.index[0]) if len(vc) > 0 else None,
        "most_common_count": int(vc.iloc[0]) if len(vc) > 0 else 0,
    }


def _skewness_label(skew: float) -> str:
    if skew is None or pd.isna(skew) or np.isnan(skew):
        return "Insufficient variation"
    if abs(skew) < 0.5:
        return "Approximately symmetric"
    if skew > 2:
        return "Highly right-skewed (positive)"
    if skew > 0.5:
        return "Moderately right-skewed (positive)"
    if skew < -2:
        return "Highly left-skewed (negative)"
    return "Moderately left-skewed (negative)"
