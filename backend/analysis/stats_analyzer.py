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

    try:
        from scipy.stats import skew, kurtosis
        skewness = float(skew(num_vals.values))
        kurt = float(kurtosis(num_vals.values))
    except Exception:
        skewness = float(num_vals.skew())
        kurt = float(num_vals.kurtosis())

    return {
        "column": col,
        "count": int(len(num_vals)),
        "missing": int(col_mask.sum()),
        "mean": round(float(num_vals.mean()), 4),
        "median": round(float(num_vals.median()), 4),
        "std": round(float(num_vals.std()), 4),
        "variance": round(float(num_vals.var()), 4),
        "min": safe_json_val(num_vals.min()),
        "max": safe_json_val(num_vals.max()),
        "range": round(float(num_vals.max() - num_vals.min()), 4),
        "q1": round(q1, 4),
        "q2": round(q2, 4),
        "q3": round(q3, 4),
        "iqr": round(iqr, 4),
        "skewness": round(skewness, 4),
        "kurtosis": round(kurt, 4),
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
    if abs(skew) < 0.5:
        return "Approximately symmetric"
    if skew > 2:
        return "Highly right-skewed (positive)"
    if skew > 0.5:
        return "Moderately right-skewed (positive)"
    if skew < -2:
        return "Highly left-skewed (negative)"
    return "Moderately left-skewed (negative)"
