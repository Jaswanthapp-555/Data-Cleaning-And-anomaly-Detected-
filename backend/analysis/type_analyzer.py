"""Data type analysis and inconsistency detection."""
import pandas as pd
import numpy as np
from backend.utils.df_utils import is_numeric_col, is_categorical_col, is_datetime_col, get_missing_mask, round_half_up, clean_numeric_series


def analyze_types(df: pd.DataFrame, kept_cells: set = None) -> dict:
    issues = []
    columns = []
    kept = kept_cells or set()

    for col in df.columns:
        series = df[col]
        dtype = str(series.dtype)
        # Missing cells must be excluded from type detection
        mask = get_missing_mask(series)
        non_null = series[~mask]
        if len(non_null) == 0:
            columns.append({"column": col, "dtype": dtype, "issues": []})
            continue

        col_issues = []

        # Float in mostly integer column (e.g. integer column with a few float values)
        if pd.api.types.is_float_dtype(series) or (pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_integer_dtype(series)):
            floats = pd.to_numeric(non_null, errors="coerce").dropna()
            if len(floats) >= 3:
                has_dec = floats.apply(lambda v: abs(float(v) - round(float(v))) > 1e-9)
                dec_indices = [int(i) for i in floats[has_dec].index.tolist()]
                active_dec_indices = [i for i in dec_indices if (i, col) not in kept]
                whole_count = len(floats) - len(dec_indices)
                if len(active_dec_indices) > 0 and (whole_count / len(floats) >= 0.5):
                    col_issues.append({
                        "type": "FLOAT_IN_INTEGER",
                        "column": col,
                        "description": f"Column '{col}' is mostly whole numbers ({whole_count} values), but contains {len(active_dec_indices)} floating-point decimal value(s).",
                        "convertible_count": whole_count,
                        "non_convertible_count": len(active_dec_indices),
                        "affected_indices": active_dec_indices,
                        "proposed_type": "int64",
                        "severity": "medium",
                    })

        # Numeric stored as object / text
        if not pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_datetime64_any_dtype(series):
            from backend.utils.df_utils import clean_numeric_series
            cleaned_s = clean_numeric_series(non_null)
            num_coerced = pd.to_numeric(cleaned_s, errors="coerce")
            num_success = num_coerced.notna().mean()
            if num_success > 0.7:
                has_missing = bool(get_missing_mask(series).any())
                valid_nums = num_coerced.dropna()
                has_dec = valid_nums.apply(lambda v: abs(float(v) - round(float(v))) > 1e-9)
                decimal_count = int(has_dec.sum())
                
                # Propose float64 if significant decimal values exist; else Int64 if blanks/NaN, else int64
                if decimal_count > 0 and (decimal_count / max(1, len(valid_nums)) > 0.3):
                    proposed_type = "float64"
                else:
                    proposed_type = "Int64" if has_missing else "int64"

                # 1. Unconvertible rows: non-null values that cannot be parsed as numbers
                unconvertible_indices = [int(i) for i in non_null[num_coerced.isna()].index.tolist() if (int(i), col) not in kept]
                
                # 2. Decimal rounding rows if integer target
                rounding_indices = []
                if proposed_type in ("int64", "Int64"):
                    dec_mask = num_coerced.notna() & num_coerced.apply(lambda v: pd.notna(v) and abs(float(v) - round(float(v))) > 1e-9)
                    rounding_indices = [int(i) for i in non_null[dec_mask].index.tolist() if (int(i), col) not in kept]

                # Value-level problem indices: unconvertible first, then rounding
                problem_indices = unconvertible_indices + [i for i in rounding_indices if i not in unconvertible_indices]
                clean_count = int(num_coerced.notna().sum()) - len(rounding_indices)
                unconv_count = len(unconvertible_indices)

                desc_parts = []
                if unconv_count > 0:
                    desc_parts.append(f"{unconv_count} value{'s' if unconv_count != 1 else ''} cannot convert")
                if len(rounding_indices) > 0:
                    desc_parts.append(f"{len(rounding_indices)} decimal value{'s' if len(rounding_indices) != 1 else ''} would round")
                if desc_parts:
                    desc = f"Column '{col}': {'; '.join(desc_parts)}; column stored as text."
                else:
                    desc = f"Column '{col}' is stored as text. All {clean_count} values convert cleanly."

                col_issues.append({
                    "type": "NUMERIC_AS_TEXT",
                    "column": col,
                    "description": desc,
                    "convertible_count": int(num_coerced.notna().sum()),
                    "clean_count": clean_count,
                    "non_convertible_count": unconv_count,
                    "decimal_loss_count": len(rounding_indices),
                    "affected_indices": problem_indices,
                    "unconvertible_indices": unconvertible_indices,
                    "rounding_indices": rounding_indices,
                    "proposed_type": proposed_type,
                    "has_missing": has_missing,
                    "severity": "high" if unconv_count > 0 else "medium",
                })

        # Date stored as object / text
        if not pd.api.types.is_datetime64_any_dtype(series) and not pd.api.types.is_numeric_dtype(series):
            try:
                dt_coerced = pd.to_datetime(non_null, errors="coerce")
                dt_success = dt_coerced.notna().mean()
                if dt_success > 0.8 and not col_issues:
                    unconv_indices = [int(i) for i in non_null[dt_coerced.isna()].index.tolist() if (int(i), col) not in kept]
                    clean_count = int(dt_coerced.notna().sum())
                    unconv_count = len(unconv_indices)
                    if unconv_count > 0:
                        desc = f"Column '{col}': {unconv_count} value{'s' if unconv_count != 1 else ''} cannot convert to date; column stored as text."
                    else:
                        desc = f"Column '{col}' is stored as text. All {clean_count} values convert cleanly to date."
                    col_issues.append({
                        "type": "DATETIME_AS_TEXT",
                        "column": col,
                        "description": desc,
                        "convertible_count": clean_count,
                        "clean_count": clean_count,
                        "non_convertible_count": unconv_count,
                        "affected_indices": unconv_indices,
                        "unconvertible_indices": unconv_indices,
                        "proposed_type": "datetime64",
                        "severity": "high" if unconv_count > 0 else "medium",
                    })
            except Exception:
                pass

        # Mixed numeric and non-numeric in object columns
        if is_categorical_col(series) and not col_issues:
            num_mask = pd.to_numeric(non_null, errors="coerce").notna()
            if 0 < num_mask.mean() < 1:
                mixed_indices = [int(i) for i in non_null[~num_mask].index.tolist() if (int(i), col) not in kept]
                if mixed_indices:
                    col_issues.append({
                        "type": "MIXED_TYPES",
                        "column": col,
                        "description": f"Column '{col}' contains a mix of numeric ({num_mask.sum()} values) and non-numeric ({(~num_mask).sum()} values).",
                        "numeric_count": int(num_mask.sum()),
                        "non_numeric_count": int((~num_mask).sum()),
                        "affected_indices": mixed_indices,
                        "severity": "medium",
                    })

        # Boolean inconsistency
        if is_categorical_col(series) and not col_issues:
            unique_lower = set(str(v).strip().lower() for v in non_null.unique())
            bool_vals = {"true", "false", "yes", "no", "1", "0", "y", "n", "t", "f"}
            if unique_lower.issubset(bool_vals) and len(unique_lower) >= 2:
                aff_indices = [int(i) for i in non_null.index.tolist() if (int(i), col) not in kept]
                if aff_indices:
                    col_issues.append({
                        "type": "BOOLEAN_AS_TEXT",
                        "column": col,
                        "description": f"Column '{col}' appears to contain boolean-like values stored as text.",
                        "unique_values": list(unique_lower),
                        "affected_indices": aff_indices,
                        "proposed_type": "boolean",
                        "severity": "low",
                    })

        columns.append({
            "column": col,
            "dtype": dtype,
            "issues": col_issues,
        })
        issues.extend(col_issues)

    return {
        "type_issues": issues,
        "has_type_issues": len(issues) > 0,
        "columns_with_issues": sum(1 for c in columns if c["issues"]),
        "column_details": columns,
    }


def preview_type_conversion(df: pd.DataFrame, col: str, target_type: str) -> dict:
    """Preview what a type conversion would look like across the 6 scoped conversions."""
    if col not in df.columns:
        return {"error": f"Column '{col}' not found."}
    series = df[col]

    # Normalize target_type
    target_clean = str(target_type).strip().lower()
    target_norm_map = {
        "float": "float64", "float64": "float64", "numeric": "float64",
        "int": "int64", "int64": "int64", "integer": "int64",
        "str": "str", "string": "str", "text": "str",
        "datetime": "datetime64", "datetime64": "datetime64", "date": "datetime64"
    }
    normalized_target = target_norm_map.get(target_clean, target_type)

    # Determine column category
    if pd.api.types.is_integer_dtype(series):
        current_category = "int"
    elif pd.api.types.is_float_dtype(series):
        current_category = "float"
    elif pd.api.types.is_datetime64_any_dtype(series):
        current_category = "date"
    elif pd.api.types.is_numeric_dtype(series):
        current_category = "float"
    else:
        current_category = "text"

    conversion_code = f"{current_category}_to_{normalized_target}"
    decimal_loss_count = 0
    decimal_loss_examples = []
    is_safe = True

    try:
        if normalized_target == "float64":
            if current_category == "int":
                conversion_code = "int_to_float"
                coerced = pd.to_numeric(series, errors="coerce")
                failed = series[coerced.isna() & series.notna()]
                converted = coerced.astype(float)
                is_safe = (len(failed) == 0)
            elif current_category == "text":
                conversion_code = "text_to_float"
                from backend.utils.df_utils import clean_numeric_series
                cleaned_s = clean_numeric_series(series)
                coerced = pd.to_numeric(cleaned_s, errors="coerce")
                failed = series[coerced.isna() & series.notna()]
                converted = coerced.astype(float)
                is_safe = (len(failed) == 0)
            else:
                conversion_code = "num_to_float"
                coerced = pd.to_numeric(series, errors="coerce")
                failed = series[coerced.isna() & series.notna()]
                converted = coerced.astype(float)
                is_safe = (len(failed) == 0)

        elif normalized_target == "int64":
            if current_category == "float":
                conversion_code = "float_to_int"
                floats = pd.to_numeric(series, errors="coerce")
                has_dec = floats.dropna().apply(lambda v: abs(float(v) - round(float(v))) > 1e-9)
                decimal_loss_count = int(has_dec.sum())
                decimal_loss_examples = [
                    f"'{floats.loc[idx]}' (row {int(idx) + 1 if isinstance(idx, (int, np.integer)) else idx})"
                    for idx in floats.dropna()[has_dec].head(5).index
                ]
                converted = floats.apply(round_half_up).astype("Int64")
                failed = series[converted.isna() & series.notna()]
                is_safe = (len(failed) == 0 and decimal_loss_count == 0)
            elif current_category == "text":
                conversion_code = "text_to_int"
                from backend.utils.df_utils import clean_numeric_series
                cleaned_s = clean_numeric_series(series)
                coerced = pd.to_numeric(cleaned_s, errors="coerce")
                failed = series[coerced.isna() & series.notna()]
                has_dec = coerced.dropna().apply(lambda v: abs(float(v) - round(float(v))) > 1e-9)
                decimal_loss_count = int(has_dec.sum())
                decimal_loss_examples = [
                    f"'{series.loc[idx]}' (row {int(idx) + 1 if isinstance(idx, (int, np.integer)) else idx})"
                    for idx in coerced.dropna()[has_dec].head(5).index
                ]
                converted = coerced.apply(round_half_up).astype("Int64")
                is_safe = (len(failed) == 0 and decimal_loss_count == 0)
            else:
                conversion_code = "int_to_int"
                coerced = pd.to_numeric(series, errors="coerce")
                failed = series[coerced.isna() & series.notna()]
                converted = series.astype("Int64")
                is_safe = (len(failed) == 0)

        elif normalized_target == "str":
            if current_category in ("int", "float"):
                conversion_code = "num_to_text"
                is_safe = True  # Safe for value preservation, but capability loss warning shown
                def _fmt_clean(v):
                    if pd.isna(v): return None
                    if isinstance(v, (float, np.floating)) and float(v).is_integer():
                        return str(int(v))
                    return str(v)
                converted = series.apply(_fmt_clean)
                failed = pd.Series([], dtype=object)
            elif current_category == "date":
                conversion_code = "date_to_text"
                is_safe = True
                converted = series.dt.strftime("%Y-%m-%d").where(series.notna(), None)
                failed = pd.Series([], dtype=object)
            else:
                conversion_code = "text_to_text"
                is_safe = True
                converted = series.astype(str)
                failed = pd.Series([], dtype=object)

        elif normalized_target == "datetime64":
            conversion_code = f"{current_category}_to_date" if current_category != "text" else "text_to_date"
            coerced = pd.to_datetime(series, errors="coerce")
            failed = series[coerced.isna() & series.notna()]
            converted = coerced
            is_safe = (len(failed) == 0)

        else:
            try:
                converted = series.astype(normalized_target)
                failed = pd.Series([], dtype=object)
            except Exception:
                coerced = pd.to_numeric(series, errors="coerce")
                failed = series[coerced.isna() & series.notna()]
                converted = coerced
            is_safe = (len(failed) == 0)

        failed_examples = [f"'{val}' (row {int(idx) + 1})" for idx, val in failed.head(5).items()]
        failed_details = [{"row": int(idx) + 1, "value": str(val)} for idx, val in failed.head(10).items()]

        # Generate sample pairs (top 6 non-null rows)
        sample_pairs = []
        for idx in series.dropna().head(6).index:
            orig_val = series.loc[idx]
            conv_val = converted.loc[idx] if idx in converted.index else None
            if pd.isna(conv_val):
                sample_pairs.append({
                    "row": int(idx) + 1,
                    "original": str(orig_val),
                    "converted": "null (conversion failed)",
                    "status": "fail"
                })
            else:
                if normalized_target == "float64":
                    try:
                        c_str = f"{float(conv_val):.2f}"
                    except Exception:
                        c_str = str(conv_val)
                elif normalized_target == "datetime64":
                    c_str = str(conv_val)[:10]
                else:
                    c_str = str(conv_val)
                sample_pairs.append({
                    "row": int(idx) + 1,
                    "original": str(orig_val),
                    "converted": c_str,
                    "status": "success"
                })

        non_null_count = int(series.notna().sum())
        convertible_count = max(0, int(non_null_count - len(failed)))
        non_convertible_count = int(len(failed))
        will_be_empty = (non_null_count > 0 and convertible_count == 0)
        if will_be_empty:
            is_safe = False

        return {
            "column": col,
            "current_type": str(series.dtype),
            "current_category": current_category,
            "target_type": normalized_target,
            "conversion_code": conversion_code,
            "total_values": len(series),
            "non_null_count": non_null_count,
            "convertible_count": convertible_count,
            "non_convertible_count": non_convertible_count,
            "will_be_empty": will_be_empty,
            "empty_warning": f"Conversion to {normalized_target} will fail for all {non_null_count} values in '{col}', leaving the column entirely empty." if will_be_empty else None,
            "non_convertible_examples": failed_examples,
            "non_convertible_details": failed_details,
            "decimal_loss_count": decimal_loss_count,
            "decimal_loss_examples": decimal_loss_examples,
            "sample_pairs": sample_pairs,
            "sample_output": [str(v) for v in converted.dropna().head(5).tolist()],
            "is_safe": is_safe,
            "success": True,
        }
    except Exception as e:
        return {"error": str(e), "success": False}


def get_type_affected_rows(df: pd.DataFrame, col: str, kept_cells: set = None) -> dict:
    """Return specific affected rows for a type-flagged column (Tab 1 of Repair Data Type).
    Directly reflects analyze_types detection results.
    """
    if col not in df.columns:
        return {"error": f"Column '{col}' not found.", "affected_rows": []}

    series = df[col]
    kept = kept_cells or set()
    analysis = analyze_types(df, kept_cells=kept)
    col_issues = [i for i in analysis.get("type_issues", []) if i.get("column") == col]

    col_category = "text"
    if pd.api.types.is_integer_dtype(series):
        col_category = "int"
    elif pd.api.types.is_float_dtype(series):
        col_category = "float"
    elif pd.api.types.is_datetime64_any_dtype(series):
        col_category = "date"

    if not col_issues:
        return {
            "column": col,
            "current_dtype": str(series.dtype),
            "col_category": col_category,
            "proposed_target": "none",
            "total_affected": 0,
            "affected_rows": [],
        }

    issue = col_issues[0]
    issue_type = issue.get("type")
    proposed_target = issue.get("proposed_type", "str")
    has_missing = bool(get_missing_mask(series).any())
    if proposed_target in ("int", "int64", "integer") and has_missing:
        proposed_target = "Int64"

    aff_indices = issue.get("affected_indices", [])

    affected_rows = []

    for idx in aff_indices:
        if idx not in df.index or (int(idx), col) in kept:
            continue
        orig = series.loc[idx]
        orig_str = str(orig)
        can_convert = False
        proposed_value = None
        fail_reason = None

        if issue_type == "FLOAT_IN_INTEGER":
            try:
                num = float(orig)
                rounded = round_half_up(num)
                can_convert = True
                proposed_value = str(rounded)
                if abs(num - rounded) > 1e-9:
                    fail_reason = f"Decimal value '{orig_str}' will be rounded to integer '{proposed_value}'"
            except Exception:
                can_convert = False
                fail_reason = f"Cannot round '{orig_str}' to integer"

        elif issue_type == "DATETIME_AS_TEXT":
            try:
                dt = pd.to_datetime(orig)
                if pd.notna(dt):
                    can_convert = True
                    proposed_value = dt.strftime("%Y-%m-%d %H:%M:%S") if (dt.hour or dt.minute or dt.second) else dt.strftime("%Y-%m-%d")
                else:
                    can_convert = False
                    fail_reason = f"Value '{orig_str}' cannot be parsed as date/time"
            except Exception:
                can_convert = False
                fail_reason = f"Value '{orig_str}' cannot be parsed as date/time"

        elif issue_type == "NUMERIC_AS_TEXT":
            try:
                cleaned = str(orig).replace("$", "").replace(",", "").strip()
                num = float(cleaned)
                if proposed_target in ("int64", "Int64"):
                    p_val = round_half_up(num)
                    proposed_value = str(p_val)
                    if num % 1 != 0:
                        fail_reason = f"Decimal value '{orig_str}' will be rounded to integer '{proposed_value}'"
                else:
                    proposed_value = f"{num:.4f}".rstrip("0").rstrip(".") if num % 1 != 0 else f"{num:.1f}"
                can_convert = True
            except Exception:
                can_convert = False
                fail_reason = f"Value '{orig_str}' cannot be parsed as a number"

        elif issue_type == "BOOLEAN_AS_TEXT":
            s_lower = orig_str.strip().lower()
            if s_lower in ("true", "1", "yes", "y", "t"):
                can_convert = True
                proposed_value = "True"
            elif s_lower in ("false", "0", "no", "n", "f"):
                can_convert = True
                proposed_value = "False"
            else:
                can_convert = False
                fail_reason = f"Value '{orig_str}' is not recognized as boolean"

        elif issue_type == "MIXED_TYPES":
            try:
                cleaned = str(orig).replace("$", "").replace(",", "").strip()
                num = float(cleaned)
                can_convert = True
                proposed_value = f"{num:.4f}".rstrip("0").rstrip(".") if num % 1 != 0 else f"{num:.1f}"
            except Exception:
                can_convert = False
                fail_reason = f"Non-numeric value '{orig_str}' in numeric column"

        else:
            can_convert = True
            proposed_value = orig_str

        # Never list a row whose stored value and converted value are identical
        if can_convert and proposed_value is not None:
            if orig_str.strip() == str(proposed_value).strip():
                continue

        affected_rows.append({
            "row_index": int(idx),
            "current_value": orig_str,
            "current_type": str(series.dtype),
            "proposed_value": proposed_value,
            "proposed_target": proposed_target,
            "can_convert": can_convert,
            "fail_reason": fail_reason,
        })

    # Show value-level problem rows first: unconvertible (can_convert == False) first, then rounding
    affected_rows.sort(key=lambda r: (1 if r["can_convert"] else 0, r["row_index"]))

    unconv_count = len([r for r in affected_rows if not r["can_convert"]])
    decimal_loss_count = len([r for r in affected_rows if r["can_convert"]])
    clean_count = issue.get("clean_count", max(0, len(series.dropna()) - len(affected_rows)))

    if unconv_count > 0:
        summary_text = f"'{col}' is stored as text. {clean_count} value{'s' if clean_count != 1 else ''} convert cleanly; {unconv_count} cannot (listed below)."
    elif decimal_loss_count > 0:
        summary_text = f"'{col}' is mostly whole numbers. {clean_count} value{'s' if clean_count != 1 else ''} convert cleanly; {decimal_loss_count} decimal value{'s' if decimal_loss_count != 1 else ''} will be rounded (listed below)."
    else:
        summary_text = f"'{col}' is stored as text. All {clean_count} value{'s' if clean_count != 1 else ''} convert cleanly (0 problem rows)."

    return {
        "column": col,
        "current_dtype": str(series.dtype),
        "col_category": col_category,
        "proposed_target": proposed_target,
        "total_affected": len(affected_rows),
        "affected_rows": affected_rows,
        "all_problem_indices": [r["row_index"] for r in affected_rows],
        "unconvertible_indices": [r["row_index"] for r in affected_rows if not r["can_convert"]],
        "clean_count": clean_count,
        "unconvertible_count": unconv_count,
        "decimal_loss_count": decimal_loss_count,
        "total_values": len(series),
        "has_missing": has_missing,
        "summary": summary_text,
    }
