"""Cleaning engine — applies user-requested operations to the working DataFrame safely."""
import pandas as pd
import numpy as np
from backend.analysis.missing_analyzer import compute_imputation_value
from backend.analysis.type_analyzer import preview_type_conversion
from backend.utils.df_utils import is_numeric_col, can_be_numeric, clean_numeric_series, get_missing_mask, round_half_up


def edit_cell(df: pd.DataFrame, row_index: int, column: str, new_value) -> tuple[pd.DataFrame, dict]:
    """Edit a single cell. Returns (updated_df, history_entry)."""
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found.")
    if row_index not in df.index:
        raise ValueError(f"Row index {row_index} not found.")
    original = df.at[row_index, column]
    df = df.copy()

    # If column is numeric, try casting new_value to float/int
    if pd.api.types.is_numeric_dtype(df[column]):
        try:
            if new_value is None or str(new_value).strip() == "":
                cast_val = np.nan
            else:
                cast_val = float(new_value) if "." in str(new_value) else int(new_value)
            df.at[row_index, column] = cast_val
        except Exception:
            df.at[row_index, column] = str(new_value)
    else:
        df.at[row_index, column] = str(new_value) if new_value is not None else pd.NA

    return df, {
        "action": "Manual Edit",
        "method": "User-specified",
        "description": f"Manually edited cell [{row_index}, '{column}']",
        "column": column,
        "row_index": row_index,
        "original_value": original,
        "new_value": new_value,
    }

def resolve_outlier(df: pd.DataFrame, row_index: int, column: str, resolution: str, impute_method: str = None, manual_value = None) -> tuple[pd.DataFrame, list]:
    """Resolve an outlier, returning updated df and a list of history entries (1 or 2)."""
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found.")
    if row_index not in df.index:
        raise ValueError(f"Row index {row_index} not found.")
    
    original = df.at[row_index, column]
    df = df.copy()
    entries = []
    
    if resolution in ("keep", "leave_unchanged"):
        entries.append({
            "action": "LEAVE_UNCHANGED",
            "method": "Outlier kept",
            "description": f"Verified and kept outlier value '{original}' unchanged in [{row_index}, '{column}']",
            "column": column,
            "row_index": row_index,
            "original_value": original,
            "new_value": original,
        })
        return df, entries
        
    elif resolution == "correct":
        df, entry = edit_cell(df, row_index, column, manual_value)
        entries.append(entry)
        return df, entries
        
    elif resolution == "delete_row":
        df = df.drop(index=[row_index])
        entries.append({
            "action": "DELETE_ROWS",
            "method": "Outlier removal",
            "description": f"Deleted row {row_index} due to outlier value '{original}' in column '{column}'",
            "column": column,
            "row_index": [row_index],
            "original_value": original,
        })
        return df, entries

    elif resolution in ("delete", "replace", "impute"):
        # Step 1: Remove the outlier
        df.at[row_index, column] = np.nan
        entries.append({
            "action": "Outlier removed",
            "method": "User-specified",
            "description": f"Removed outlier value '{original}' from cell [{row_index}, '{column}']",
            "column": column,
            "row_index": row_index,
            "original_value": original,
            "new_value": "Missing",
        })
        
        # Step 2: If replace or impute, impute the gap using existing logic for that single cell
        if resolution in ("replace", "impute"):
            method = impute_method or "median_excl_outliers"
            if method in ("mean", "median", "mean_excl_outliers", "median_excl_outliers"):
                if not can_be_numeric(df[column]):
                    raise ValueError(f"Method '{method}' is only applicable to numerical columns.")
                # We compute imputation on the current column state (outlier is now NaN)
                series = clean_numeric_series(df[column])
                fill_val, desc = compute_imputation_value(series, method)
                if fill_val is None:
                    raise ValueError(f"Could not compute imputation value: {desc}")
                    
                df[column] = clean_numeric_series(df[column])
                df.at[row_index, column] = fill_val
                entries.append({
                    "action": "FILL_MISSING",
                    "description": f"Filled gap in [{row_index}, '{column}'] using {method}: {desc}",
                    "column": column,
                    "row_index": row_index,
                    "original_value": "Missing",
                    "new_value": str(fill_val),
                    "method": method,
                })
            elif method == "mode":
                fill_val, desc = compute_imputation_value(df[column], "mode")
                if fill_val is None:
                    raise ValueError(f"Could not compute imputation value: {desc}")
                df.at[row_index, column] = fill_val
                entries.append({
                    "action": "FILL_MISSING",
                    "description": f"Filled gap in [{row_index}, '{column}'] using mode: {desc}",
                    "column": column,
                    "row_index": row_index,
                    "original_value": "Missing",
                    "new_value": str(fill_val),
                    "method": "mode",
                })
        return df, entries

    raise ValueError(f"Unknown outlier resolution '{resolution}'")


def delete_rows(df: pd.DataFrame, row_indices: list) -> tuple[pd.DataFrame, dict]:
    """Delete specific rows by index."""
    existing = [i for i in row_indices if i in df.index]
    if not existing:
        raise ValueError("None of the specified row indices exist.")
    df = df.drop(index=existing)
    return df, {
        "action": "DELETE_ROWS",
        "description": f"Deleted {len(existing)} row(s): {existing[:10]}{'...' if len(existing) > 10 else ''}",
        "row_index": existing,
        "count": len(existing),
    }


def delete_columns(df: pd.DataFrame, columns: list) -> tuple[pd.DataFrame, dict]:
    """Delete specific columns."""
    existing = [c for c in columns if c in df.columns]
    if not existing:
        raise ValueError("None of the specified columns exist.")
    df = df.drop(columns=existing)
    return df, {
        "action": "DELETE_COLUMNS",
        "description": f"Deleted column(s): {existing}",
        "column": existing,
    }


def rename_column(df: pd.DataFrame, old_name: str, new_name: str) -> tuple[pd.DataFrame, dict]:
    """Rename a single column."""
    if old_name not in df.columns:
        raise ValueError(f"Column '{old_name}' not found.")
    if new_name in df.columns and new_name != old_name:
        raise ValueError(f"Column '{new_name}' already exists.")
    df = df.rename(columns={old_name: new_name})
    return df, {
        "action": "RENAME_COLUMN",
        "description": f"Renamed column '{old_name}' → '{new_name}'",
        "column": old_name,
        "new_value": new_name,
    }


def fill_missing(df: pd.DataFrame, column: str, method: str, manual_value=None) -> tuple[pd.DataFrame, dict]:
    """Fill missing values in a column using the specified method."""
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found.")

    mask = get_missing_mask(df[column])
    missing_indices = df[mask].index.tolist()
    if not missing_indices:
        raise ValueError(f"No missing values found in column '{column}'.")

    df = df.copy()

    if method == "delete_row":
        return delete_rows(df, missing_indices)
    elif method == "leave_unchanged":
        return df, {"action": "LEAVE_UNCHANGED", "description": f"Missing values in '{column}' left unchanged.", "column": column}

    is_num = can_be_numeric(df[column])

    if method in ("mean", "median", "mean_excl_outliers", "median_excl_outliers"):
        if not is_num:
            raise ValueError(f"Method '{method}' is only applicable to numerical columns. Column '{column}' is categorical.")
        # Coerce column to float64 numeric first to prevent StringDtype assignment errors
        df[column] = clean_numeric_series(df[column])
        fill_val, desc = compute_imputation_value(df[column], method)
        if fill_val is None:
            raise ValueError(f"Could not compute imputation value: {desc}")
        df.loc[mask, column] = fill_val

    elif method == "mode":
        if is_num:
            raise ValueError(f"Method 'mode' is only applicable to categorical/text columns. Column '{column}' is numeric.")
        fill_val, desc = compute_imputation_value(df[column], "mode")
        if fill_val is None:
            raise ValueError(f"Could not compute mode: {desc}")
        df.loc[mask, column] = fill_val

    elif method == "manual":
        if manual_value is None or str(manual_value).strip() == "":
            raise ValueError("Manual imputation value cannot be empty.")
        if is_num or pd.api.types.is_numeric_dtype(df[column]):
            try:
                val_str = str(manual_value).strip().replace("$", "").replace(",", "")
                fill_val = float(val_str) if "." in val_str else int(val_str)
                df[column] = clean_numeric_series(df[column])
            except ValueError:
                raise ValueError(f"Invalid manual value '{manual_value}' for numeric column '{column}'. Expected a valid number.")
            desc = f"Manual numeric value: {fill_val}"
            df.loc[mask, column] = fill_val
        else:
            fill_val = str(manual_value)
            desc = f"Manual string value: '{fill_val}'"
            df.loc[mask, column] = fill_val
    else:
        raise ValueError(f"Unknown imputation method '{method}'.")

    return df, {
        "action": "FILL_MISSING",
        "description": f"Filled {len(missing_indices)} missing value(s) in '{column}' using {method}: {desc}",
        "column": column,
        "original_value": "Missing",
        "new_value": str(fill_val),
        "method": method,
        "affected_rows": len(missing_indices),
    }


def remove_duplicates(df: pd.DataFrame, keep: str = "first") -> tuple[pd.DataFrame, dict]:
    """Remove exact duplicate rows, keeping first occurrence."""
    before = len(df)
    df = df.drop_duplicates(keep=keep)
    after = len(df)
    removed = before - after
    return df, {
        "action": "REMOVE_DUPLICATES",
        "description": f"Removed {removed} exact duplicate row(s). Kept {'first' if keep == 'first' else keep} occurrence.",
        "count": removed,
    }


def repair_type(df: pd.DataFrame, column: str, target_type: str) -> tuple[pd.DataFrame, dict]:
    """Convert a column to the specified target type."""
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found.")
    original_dtype = str(df[column].dtype)
    df = df.copy()

    target_clean = str(target_type).strip().lower()
    target_norm_map = {
        "float": "float64", "float64": "float64", "numeric": "float64",
        "int": "int64", "int64": "int64", "integer": "int64",
        "str": "str", "string": "str", "text": "str",
        "datetime": "datetime64", "datetime64": "datetime64", "date": "datetime64"
    }
    target = target_norm_map.get(target_clean, target_type)

    non_null_before = int(df[column].notna().sum())

    try:
        if target in ("float64", "numeric"):
            df[column] = pd.to_numeric(clean_numeric_series(df[column]), errors="coerce").astype(float)
        elif target == "int64":
            num_clean = clean_numeric_series(df[column])
            coerced = pd.to_numeric(num_clean, errors="coerce")
            df[column] = coerced.apply(lambda v: round_half_up(v) if pd.notna(v) else v).astype("Int64")
        elif target == "datetime64":
            df[column] = pd.to_datetime(df[column], errors="coerce")
        elif target == "str":
            if pd.api.types.is_datetime64_any_dtype(df[column]):
                df[column] = df[column].dt.strftime("%Y-%m-%d").where(df[column].notna(), None)
            elif pd.api.types.is_numeric_dtype(df[column]):
                def _fmt_clean_str(v):
                    if pd.isna(v): return None
                    if isinstance(v, (float, np.floating)) and float(v).is_integer():
                        return str(int(v))
                    return str(v)
                df[column] = df[column].apply(_fmt_clean_str)
            else:
                df[column] = df[column].astype(str).replace({"nan": None, "None": None, "<NA>": None})
        else:
            df[column] = df[column].astype(target, errors="ignore")
    except Exception as e:
        raise ValueError(f"Could not convert '{column}' to {target_type}: {e}")

    non_null_after = int(df[column].notna().sum())
    if non_null_before > 0 and non_null_after == 0:
        raise ValueError(f"Type conversion to {target_type} failed for all values in '{column}'. Conversion would leave the column entirely empty.")

    failed_count = max(0, non_null_before - non_null_after)
    desc = f"Converted '{column}' from {original_dtype} to {target}."
    if failed_count > 0:
        desc = f"Converted '{column}' from {original_dtype} to {target} ({failed_count} unparseable value(s) converted to null)."

    return df, {
        "action": "REPAIR_TYPE",
        "description": desc,
        "column": column,
        "original_value": original_dtype,
        "new_value": target,
        "method": "type_conversion",
        "failed_count": failed_count,
    }


def correct_value(df: pd.DataFrame, row_index: int, column: str, new_value) -> tuple[pd.DataFrame, dict]:
    """Correct a specific outlier/suspicious value."""
    return edit_cell(df, row_index, column, new_value)


def resolve_suspicious_value(df: pd.DataFrame, row_index: int, column: str, resolution: str,
                             manual_value=None, impute_method: str = None) -> tuple[pd.DataFrame, list]:
    """Resolve a suspicious value row-by-row.
    Resolutions:
      - 'delete_row' (default/highlighted action)
      - 'keep' / 'leave_unchanged'
      - 'correct' / 'manual'
      - 'replace' / 'impute' (statistical imputation based on column type)
    """
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found.")
    if row_index not in df.index:
        raise ValueError(f"Row index {row_index} not found.")

    original = df.at[row_index, column]
    df = df.copy()
    entries = []

    if resolution == "delete_row":
        df = df.drop(index=[row_index])
        entries.append({
            "action": "DELETE_ROWS",
            "method": "Suspicious value removal",
            "description": f"Deleted row {row_index} due to suspicious value '{original}' in column '{column}'",
            "column": column,
            "row_index": [row_index],
            "original_value": original,
        })
        return df, entries

    elif resolution in ("keep", "leave_unchanged"):
        entries.append({
            "action": "LEAVE_UNCHANGED",
            "method": "User decision: Keep",
            "description": f"Verified and kept suspicious value '{original}' in [{row_index}, '{column}']",
            "column": column,
            "row_index": row_index,
            "original_value": original,
            "new_value": original,
        })
        return df, entries

    elif resolution in ("correct", "manual"):
        df, entry = edit_cell(df, row_index, column, manual_value)
        entry["action"] = "CORRECT_VALUE"
        entry["description"] = f"Corrected suspicious value in [{row_index}, '{column}']: '{original}' → '{manual_value}'"
        entries.append(entry)
        return df, entries

    elif resolution in ("replace", "impute"):
        df.at[row_index, column] = np.nan
        method = impute_method or ("median_excl_outliers" if can_be_numeric(df[column]) else "mode")
        if method in ("mean", "median", "mean_excl_outliers", "median_excl_outliers"):
            if not can_be_numeric(df[column]):
                raise ValueError(f"Method '{method}' is only applicable to numerical columns.")
            series = clean_numeric_series(df[column])
            fill_val, desc = compute_imputation_value(series, method)
            if fill_val is None:
                raise ValueError(f"Could not compute imputation value: {desc}")
            df[column] = clean_numeric_series(df[column])
            df.at[row_index, column] = fill_val
        elif method == "mode":
            fill_val, desc = compute_imputation_value(df[column], "mode")
            if fill_val is None:
                raise ValueError(f"Could not compute mode: {desc}")
            df.at[row_index, column] = fill_val
        else:
            raise ValueError(f"Unknown imputation method '{method}'.")

        entries.append({
            "action": "REPLACE_SUSPICIOUS",
            "description": f"Replaced suspicious value '{original}' in [{row_index}, '{column}'] using {method}: {fill_val}",
            "column": column,
            "row_index": row_index,
            "original_value": original,
            "new_value": str(fill_val),
            "method": method,
        })
        return df, entries

    raise ValueError(f"Unknown suspicious value resolution '{resolution}'")


def delete_column_missing_rows(df: pd.DataFrame, column: str) -> tuple[pd.DataFrame, dict]:
    """Delete every row where the specified column has a missing value."""
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found.")
    mask = get_missing_mask(df[column])
    missing_indices = [int(i) for i in df[mask].index.tolist()]
    if not missing_indices:
        raise ValueError(f"No missing values found in column '{column}'.")

    df = df.drop(index=missing_indices)
    return df, {
        "action": "DELETE_ROWS_BY_COLUMN",
        "description": f"Deleted {len(missing_indices)} row(s) where column '{column}' was missing.",
        "column": column,
        "count": len(missing_indices),
        "affected_rows": len(missing_indices),
    }
