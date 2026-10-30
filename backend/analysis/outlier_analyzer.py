"""Outlier and anomaly detection using IQR and Z-score."""
import pandas as pd
import numpy as np
from backend.utils.df_utils import is_numeric_col, is_identifier_col, clean_numeric_series, safe_json_val, get_missing_mask


def analyze_outliers(df: pd.DataFrame, kept_cells: set = None) -> dict:
    results = []
    kept = kept_cells or set()
    for col in df.columns:
        try:
            series = df[col]
            if not is_numeric_col(series) or is_identifier_col(series, col):
                continue

            num_series = clean_numeric_series(series)
            mask = get_missing_mask(series)
            non_null = num_series[~mask].dropna()
            if len(non_null) < 5:
                continue

            iqr_result = _iqr_outliers(num_series, col)
            zscore_result = _zscore_outliers(num_series, col)

            # Combine
            raw_indices = list(set(iqr_result["indices"] + zscore_result["indices"]))
            # Exclude missing cells and kept cells using stable index labels
            all_indices = [int(i) for i in raw_indices if (int(i), col) not in kept and (i in num_series.index and pd.notna(num_series.loc[i]))]

            if len(all_indices) == 0:
                continue

            results.append({
                "column": col,
                "iqr": iqr_result,
                "zscore": zscore_result,
                "combined_indices": all_indices,
                "combined_count": len(all_indices),
                "affected_pct": round(len(all_indices) / len(series) * 100, 2),
                "total_non_null": int(len(non_null)),
                "outlier_values": _outlier_values(num_series, all_indices),
            })
        except Exception:
            continue

    return {
        "columns_with_outliers": len(results),
        "outlier_details": results,
        "has_outliers": len(results) > 0,
        "note": "Potential anomalies are reported here. An outlier is NOT automatically an error.",
    }


def _iqr_outliers(series: pd.Series, col: str) -> dict:
    non_null = series.dropna()
    if len(non_null) < 4:
        return {"method": "IQR", "lower_fence": 0, "upper_fence": 0, "q1": 0, "q3": 0, "iqr": 0, "count": 0, "indices": []}
    q1 = float(non_null.quantile(0.25))
    q3 = float(non_null.quantile(0.75))
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    mask = (series < lower) | (series > upper)
    indices = [int(i) for i in series[mask].index.tolist()]
    return {
        "method": "IQR",
        "lower_fence": round(lower, 4),
        "upper_fence": round(upper, 4),
        "q1": round(q1, 4),
        "q3": round(q3, 4),
        "iqr": round(iqr, 4),
        "count": len(indices),
        "indices": indices,
    }


def _zscore_outliers(series: pd.Series, col: str) -> dict:
    non_null = series.dropna()
    if len(non_null) < 10:
        return {"method": "Z-score", "count": 0, "indices": [], "note": "Insufficient data."}
    mean = float(non_null.mean())
    std = float(non_null.std())
    if std == 0 or np.isnan(std):
        return {"method": "Z-score", "count": 0, "indices": [], "note": "Zero standard deviation."}
    z = (series - mean) / std
    mask = z.abs() > 3
    indices = [int(i) for i in series[mask].index.tolist()]
    return {
        "method": "Z-score",
        "mean": round(mean, 4),
        "std": round(std, 4),
        "threshold": 3,
        "count": len(indices),
        "indices": indices,
    }


def _outlier_values(series: pd.Series, indices: list) -> list:
    vals = []
    for idx in indices[:20]:  # cap at 20
        try:
            if idx in series.index:
                v = series.loc[idx]
                vals.append({"index": idx, "value": safe_json_val(v)})
        except Exception:
            pass
    return vals


def get_iqr_bounds(series: pd.Series) -> tuple[float, float]:
    """Return (lower, upper) IQR fences."""
    num_series = clean_numeric_series(series)
    non_null = num_series.dropna()
    if len(non_null) < 5:
        return float("-inf"), float("inf")
    q1 = float(non_null.quantile(0.25))
    q3 = float(non_null.quantile(0.75))
    iqr = q3 - q1
    return q1 - 1.5 * iqr, q3 + 1.5 * iqr
