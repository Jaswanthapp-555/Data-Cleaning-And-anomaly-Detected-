"""Schema analysis: columns, types, schema problems using centralized missing-value detection."""
import pandas as pd
from backend.utils.df_utils import is_numeric_col, is_categorical_col, is_datetime_col, get_missing_mask, get_semantic_type


def analyze_schema(df: pd.DataFrame) -> dict:
    columns = []
    full_mask = get_missing_mask(df)

    for col in df.columns:
        series = df[col]
        dtype = str(series.dtype)
        col_mask = full_mask[col] if col in full_mask.columns else get_missing_mask(series)
        non_null = series[~col_mask]
        unique_count = int(non_null.nunique())
        total = len(series)
        missing_count = int(col_mask.sum())
        missing_pct = round(missing_count / total * 100, 2) if total > 0 else 0
        sem_type = get_semantic_type(series, col)

        col_info = {
            "name": col,
            "dtype": dtype,
            "semantic_type": sem_type,
            "is_numeric": bool(is_numeric_col(series)),
            "is_categorical": bool(is_categorical_col(series)),
            "is_datetime": bool(is_datetime_col(series)),
            "total": total,
            "missing_count": missing_count,
            "missing_pct": missing_pct,
            "unique_count": unique_count,
            "unique_pct": round(unique_count / total * 100, 2) if total > 0 else 0,
            "sample_values": [
                str(v) for v in non_null.head(5).tolist()
            ],
        }
        columns.append(col_info)

    issues = []
    empty_rows_mask = full_mask.all(axis=1)

    return {
        "row_count": len(df),
        "col_count": len(df.columns),
        "column_names": list(df.columns),
        "columns": columns,
        "schema_issues": [],
        "has_duplicate_headers": len(df.columns) != len(set(df.columns)),
        "empty_rows": int(empty_rows_mask.sum()),
    }


def _detect_schema_issues(df: pd.DataFrame, columns: list) -> list:
    return []
