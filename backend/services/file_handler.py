"""Safe file reading for CSV and Excel uploads."""
import io
import pandas as pd
import numpy as np
import chardet
from backend.utils.df_utils import get_missing_mask, clean_numeric_series


def read_csv(file_bytes: bytes) -> pd.DataFrame:
    """Read CSV bytes, auto-detecting encoding."""
    detected = chardet.detect(file_bytes)
    encoding = detected.get("encoding") or "utf-8"

    errors = []
    for enc in [encoding, "utf-8", "latin-1", "cp1252"]:
        try:
            df = pd.read_csv(io.BytesIO(file_bytes), encoding=enc)
            df = _post_process(df)
            return df
        except Exception as e:
            errors.append(f"{enc}: {e}")

    raise ValueError(f"Could not parse CSV file. Tried encodings: {'; '.join(errors)}")


def read_excel_sheets(file_bytes: bytes) -> list[str]:
    """Return list of sheet names in an Excel file."""
    try:
        xf = pd.ExcelFile(io.BytesIO(file_bytes), engine="openpyxl")
        return xf.sheet_names
    except Exception as e:
        raise ValueError(f"Could not read Excel file: {e}")


def read_excel_sheet(file_bytes: bytes, sheet_name: str) -> pd.DataFrame:
    """Read a specific sheet from an Excel file."""
    try:
        df = pd.read_excel(
            io.BytesIO(file_bytes),
            sheet_name=sheet_name,
            engine="openpyxl",
        )
        df = _post_process(df)
        return df
    except Exception as e:
        raise ValueError(f"Could not read Excel sheet '{sheet_name}': {e}")


def _post_process(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize raw read DataFrame: fix duplicate column names and standardize missing values."""
    df = df.copy()
    df.index = pd.RangeIndex(len(df))

    cols = list(df.columns)
    seen = {}
    new_cols = []
    for c in cols:
        c_str = str(c).strip()
        if c_str in seen:
            seen[c_str] += 1
            new_cols.append(f"{c_str}_{seen[c_str]}")
        else:
            seen[c_str] = 0
            new_cols.append(c_str)
    df.columns = new_cols

    # Convert all missing representations cleanly
    for col in df.columns:
        mask = get_missing_mask(df[col])
        if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]):
            df[col] = df[col].astype(str).str.strip()
            df.loc[mask, col] = pd.NA
        elif pd.api.types.is_numeric_dtype(df[col]):
            df.loc[mask, col] = np.nan

    df = _infer_types(df)
    return df


def _infer_types(df: pd.DataFrame) -> pd.DataFrame:
    """Best-effort type inference on string-typed columns once at load time."""
    for col in df.columns:
        if not (pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col])):
            continue
        mask = get_missing_mask(df[col])
        non_null = df[col][~mask]
        if len(non_null) == 0:
            continue
        # Try datetime: parse cleanly if 100% of non-null values are valid dates
        try:
            parsed = pd.to_datetime(non_null, errors="coerce")
            if parsed.notna().all():
                df[col] = pd.to_datetime(df[col], errors="coerce")
                continue
        except Exception:
            pass
        # Try currency / numbers (strip currency $ and commas) if 100% parse cleanly as numbers
        num = clean_numeric_series(non_null)
        if num.notna().all():
            df[col] = clean_numeric_series(df[col])
            continue
    return df
