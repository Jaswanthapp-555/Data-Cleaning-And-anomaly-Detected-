"""DataFrame utility helpers and centralized missing value detection."""
import pandas as pd
import numpy as np
import re
from typing import Any, Union

NULL_STRINGS = {"", "nan", "null", "none", "<na>", "n/a", "na"}


def _series_missing_mask(series: pd.Series) -> pd.Series:
    """Compute boolean missing mask for a single Series.
    Recognizes pd.isna(val), None, np.nan, pd.NA, empty strings '', whitespace-only strings,
    and standard null representations ('nan', 'null', 'none', '<na>', 'n/a', 'na').
    """
    mask = series.isna().copy()
    if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
        return mask
    s_str = series.fillna("").astype(str).str.strip().str.lower()
    return mask | s_str.isin(NULL_STRINGS)


def get_missing_mask(data: Union[pd.Series, pd.DataFrame]) -> Union[pd.Series, pd.DataFrame]:
    """Centralized missing-value detection for a Series or DataFrame."""
    if isinstance(data, pd.DataFrame):
        mask = pd.DataFrame(False, index=data.index, columns=data.columns)
        for col in data.columns:
            mask[col] = _series_missing_mask(data[col])
        return mask
    else:
        return _series_missing_mask(data)


def clean_numeric_series(series: pd.Series) -> pd.Series:
    """Strip currency symbols ($) and commas from string series and return numeric float Series."""
    if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    col_mask = get_missing_mask(series)
    cleaned_str = series.fillna("").astype(str).str.replace(r"[$,]", "", regex=True).str.strip()
    num = pd.to_numeric(cleaned_str, errors="coerce")
    num[col_mask] = np.nan
    return num


def can_be_numeric(series: pd.Series) -> bool:
    """Check if a series is numeric or can be safely parsed as numeric (e.g. stripping currency symbols)."""
    if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
        return True
    col_mask = get_missing_mask(series)
    non_null = series[~col_mask]
    if len(non_null) == 0:
        return False
    num = clean_numeric_series(non_null)
    return float(num.notna().mean()) > 0.8


def is_numeric_col(series: pd.Series) -> bool:
    return can_be_numeric(series)


def is_categorical_col(series: pd.Series) -> bool:
    if is_numeric_col(series):
        return False
    return (
        pd.api.types.is_object_dtype(series)
        or pd.api.types.is_string_dtype(series)
        or isinstance(series.dtype, pd.CategoricalDtype)
    )


def is_datetime_col(series: pd.Series) -> bool:
    return pd.api.types.is_datetime64_any_dtype(series)


import decimal


def round_half_up(val):
    """Round float to nearest integer using round-half-up (e.g. 2.5 -> 3, -2.5 -> -3)."""
    if val is None or pd.isna(val):
        return None
    try:
        f = float(val)
        d = decimal.Decimal(str(f))
        return int(d.quantize(decimal.Decimal('1'), rounding=decimal.ROUND_HALF_UP))
    except Exception:
        try:
            f = float(val)
            return int(np.floor(f + 0.5) if f >= 0 else np.ceil(f - 0.5))
        except Exception:
            return None


def df_to_records(df: pd.DataFrame, max_rows: int = 500, page: int = 0) -> dict:
    """Serialize a DataFrame slice to JSON-safe records with stable row IDs."""
    total = len(df)
    start = page * max_rows
    end = start + max_rows
    slice_df = df.iloc[start:end]
    mask_df = get_missing_mask(slice_df)

    records = []
    for idx, row in slice_df.iterrows():
        rec = {"_row_id": int(idx)}
        for col in slice_df.columns:
            val = row[col]
            is_miss = mask_df.at[idx, col] if col in mask_df.columns else pd.isna(val)
            if is_miss:
                rec[col] = None
            elif isinstance(val, (np.integer,)):
                rec[col] = int(val)
            elif isinstance(val, (np.floating,)):
                rec[col] = float(val)
            elif isinstance(val, (pd.Timestamp,)):
                rec[col] = val.isoformat()
            else:
                rec[col] = str(val)
        records.append(rec)
    return {
        "records": records,
        "row_indices": [int(i) for i in slice_df.index],
        "total": total,
        "page": page,
        "page_size": max_rows,
        "total_pages": max(1, (total + max_rows - 1) // max_rows),
        "columns": list(df.columns),
        "dtypes": {c: str(df[c].dtype) for c in df.columns},
    }


def safe_numeric(series: pd.Series) -> pd.Series:
    """Attempt to coerce a series to numeric, returning NaN for failures."""
    return clean_numeric_series(series)


def safe_json_val(val: Any) -> Any:
    """Convert numpy/pandas types to Python native for JSON serialisation."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return float(val)
    if isinstance(val, (pd.Timestamp,)):
        return val.isoformat()
    if isinstance(val, (np.bool_,)):
        return bool(val)
    return val


def is_identifier_col(series: pd.Series, col_name: str = "") -> bool:
    """Check if a column is an identifier (e.g. ID, code, UUID, index-like)."""
    c_lower = col_name.lower().strip()
    id_suffixes = ("_id", "id", "_code", "uuid", "ssn", "isbn", "transaction_id", "user_id", "customer_id")
    if any(c_lower == s or c_lower.endswith(s) for s in id_suffixes):
        return True
    return False


def get_semantic_type(series: pd.Series, col_name: str = "") -> str:
    """Determine the semantic data type for a column."""
    if is_identifier_col(series, col_name):
        return "Identifier"

    if pd.api.types.is_bool_dtype(series):
        return "Boolean"

    if is_datetime_col(series):
        return "DateTime"

    col_mask = get_missing_mask(series)
    non_null = series[~col_mask]
    if len(non_null) == 0:
        return "Unknown"

    # Check numeric
    if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
        if pd.api.types.is_integer_dtype(series):
            return "Integer"
        # Check if float values are all whole numbers
        try:
            num = pd.to_numeric(non_null, errors="coerce").dropna()
            if len(num) > 0 and (num % 1 == 0).all():
                return "Integer"
        except Exception:
            pass
        return "Float"

    # Check if object/string can be converted to numeric
    if can_be_numeric(series):
        num = clean_numeric_series(non_null).dropna()
        if len(num) > 0 and (num % 1 == 0).all():
            return "Integer"
        return "Float"

    # Check datetime parsing
    try:
        dt = pd.to_datetime(non_null.head(30), errors="coerce")
        if float(dt.notna().mean()) > 0.8:
            return "DateTime"
    except Exception:
        pass

    # Categorical vs Text
    if non_null.nunique() < min(30, len(non_null) * 0.5):
        return "Categorical"

    return "String/Text"


def detect_datetime_columns(df: pd.DataFrame) -> list[str]:
    """Return columns that are datetime or can be parsed as datetime."""
    dt_cols = []
    for col in df.columns:
        if is_datetime_col(df[col]):
            dt_cols.append(col)
            continue
        if is_categorical_col(df[col]):
            mask = get_missing_mask(df[col])
            non_null = df[col][~mask].head(20)
            try:
                parsed = pd.to_datetime(non_null, errors="coerce")
                if parsed.notna().mean() > 0.8:
                    dt_cols.append(col)
            except Exception:
                pass
    return dt_cols

