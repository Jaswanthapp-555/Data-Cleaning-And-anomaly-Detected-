"""Row matching for dataset comparison."""
import pandas as pd
import numpy as np


def match_rows(ref_df: pd.DataFrame, cur_df: pd.DataFrame) -> dict:
    """Match rows between reference and current datasets.
    Returns info about strategy used and matched/unmatched rows."""
    id_col = _find_id_column(ref_df, cur_df)

    if id_col:
        strategy = f"Records matched using detected unique identifier column: '{id_col}'"
        return _match_by_id(ref_df, cur_df, id_col, strategy)
    else:
        strategy = "No unique identifier found. Records matched by position (row index). Note: positional matching may produce false changes if rows were reordered or rows were inserted/deleted."
        return _match_by_position(ref_df, cur_df, strategy)


def detect_identifier_column(data, col_name: str = ""):
    """Find the best identifier column in a DataFrame or detect if a Series is an identifier."""
    from backend.analysis.missing_analyzer import detect_identifier_column as check_id
    from backend.utils.df_utils import is_identifier_col
    if data is None:
        return None if col_name == "" else {}
    if isinstance(data, pd.DataFrame):
        for col in data.columns:
            s = data[col]
            id_info = check_id(s, col)
            if id_info.get("is_identifier"):
                return col
            non_null = s.dropna()
            if len(non_null) > 0 and (non_null.nunique() / len(non_null)) >= 0.9 and is_identifier_col(s, col):
                return col
        return None
    return check_id(data, col_name)


def _find_id_column(ref_df: pd.DataFrame, cur_df: pd.DataFrame) -> str | None:
    """Find the best identifier column present in both DataFrames using uniqueness ratio and name signals."""
    from backend.analysis.missing_analyzer import detect_identifier_column as check_id
    from backend.utils.df_utils import is_identifier_col

    common_cols = [c for c in ref_df.columns if c in cur_df.columns]
    if not common_cols:
        return None

    candidates = []
    for col in common_cols:
        ref_s = ref_df[col]
        cur_s = cur_df[col]

        ref_id_info = check_id(ref_s, col)
        cur_id_info = check_id(cur_s, col)

        ref_non_null = ref_s.dropna()
        cur_non_null = cur_s.dropna()

        ref_u = (ref_non_null.nunique() / len(ref_non_null)) if len(ref_non_null) > 0 else 0.0
        cur_u = (cur_non_null.nunique() / len(cur_non_null)) if len(cur_non_null) > 0 else 0.0

        is_id_name = is_identifier_col(ref_s, col) or ref_id_info.get("is_identifier", False) or cur_id_info.get("is_identifier", False)
        strong_confidence = ref_id_info.get("confidence") == "strong" or cur_id_info.get("confidence") == "strong"

        score = 0
        # High priority: name signal + high uniqueness (>90%)
        if is_id_name and ref_u >= 0.90 and cur_u >= 0.90:
            score = 150 + (ref_u + cur_u) * 20
        elif strong_confidence:
            score = 140 + (ref_u + cur_u) * 10
        elif ref_u == 1.0 and cur_u == 1.0:
            score = 120 + (30 if is_id_name else 0)
        elif is_id_name and ref_u >= 0.80 and cur_u >= 0.80:
            score = 100 + (ref_u + cur_u) * 10
        elif ref_u >= 0.98 and cur_u >= 0.98:
            # Very high uniqueness even without explicit name signal (e.g. custom code)
            score = 80

        if score >= 80:
            candidates.append((score, col))

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    return None


def _match_by_id(ref_df: pd.DataFrame, cur_df: pd.DataFrame, id_col: str, strategy: str) -> dict:
    ref_ids = [str(x) for x in ref_df[id_col].dropna().tolist()]
    cur_ids = [str(x) for x in cur_df[id_col].dropna().tolist()]

    ref_set = set(ref_ids)
    cur_set = set(cur_ids)

    new_ids = cur_set - ref_set
    deleted_ids = ref_set - cur_set
    common_ids = [cid for cid in ref_ids if cid in cur_set]  # preserve order

    # Deduplicate on id_col for safe .loc index lookup
    ref_dedup = ref_df.drop_duplicates(subset=[id_col], keep="first")
    cur_dedup = cur_df.drop_duplicates(subset=[id_col], keep="first")
    ref_indexed = ref_dedup.set_index(ref_dedup[id_col].astype(str))
    cur_indexed = cur_dedup.set_index(cur_dedup[id_col].astype(str))

    modified = []
    unchanged = []
    col_change_counts = {}

    for rid in common_ids[:5000]:  # cap processing
        ref_row = ref_indexed.loc[rid]
        cur_row = cur_indexed.loc[rid]
        changes = _compare_rows(ref_row, cur_row, rid, skip_col=id_col)
        if changes:
            modified.append({"id": rid, "changes": changes})
            for ch in changes:
                col_name = ch["column"]
                col_change_counts[col_name] = col_change_counts.get(col_name, 0) + 1
        else:
            unchanged.append(rid)

    frequent_changes = _compute_frequent_changes(col_change_counts, len(modified))

    return {
        "strategy": strategy,
        "id_column": id_col,
        "new_record_ids": list(new_ids)[:100],
        "deleted_record_ids": list(deleted_ids)[:100],
        "modified_records": modified[:100],
        "unchanged_count": len(unchanged),
        "new_count": len(new_ids),
        "deleted_count": len(deleted_ids),
        "modified_count": len(modified),
        "new_record_count": len(new_ids),
        "deleted_record_count": len(deleted_ids),
        "modified_record_count": len(modified),
        "frequently_changed_columns": frequent_changes,
    }


def _match_by_position(ref_df: pd.DataFrame, cur_df: pd.DataFrame, strategy: str) -> dict:
    min_rows = min(len(ref_df), len(cur_df))
    modified = []
    unchanged = []
    col_change_counts = {}

    for i in range(min_rows):
        changes = _compare_rows(ref_df.iloc[i], cur_df.iloc[i], i)
        if changes:
            modified.append({"id": i, "changes": changes})
            for ch in changes:
                col_name = ch["column"]
                col_change_counts[col_name] = col_change_counts.get(col_name, 0) + 1
        else:
            unchanged.append(i)

    new_count = max(0, len(cur_df) - len(ref_df))
    deleted_count = max(0, len(ref_df) - len(cur_df))
    frequent_changes = _compute_frequent_changes(col_change_counts, len(modified))

    return {
        "strategy": strategy,
        "id_column": None,
        "new_record_ids": list(range(len(ref_df), len(ref_df) + new_count))[:100],
        "deleted_record_ids": list(range(len(cur_df), len(cur_df) + deleted_count))[:100],
        "modified_records": modified[:100],
        "unchanged_count": len(unchanged),
        "new_count": new_count,
        "deleted_count": deleted_count,
        "modified_count": len(modified),
        "frequently_changed_columns": frequent_changes,
    }


def _compute_frequent_changes(counts: dict, total_modified: int) -> list:
    """Compute % of modified records affected for each changed column."""
    if total_modified == 0 or not counts:
        return []
    items = []
    for col, count in counts.items():
        pct = round(count / total_modified * 100, 1)
        items.append({
            "column": col,
            "change_count": count,
            "change_pct": pct,
            "percent_of_modified": pct,
        })
    items.sort(key=lambda x: x["change_count"], reverse=True)
    return items


def _detect_cell_anomaly(col_name: str, val) -> str | None:
    """Flag clearly anomalous values in cells: negative numbers where unexpected, out of range, etc."""
    if val is None or val == "" or pd.isna(val):
        return None
    val_str = str(val).strip()
    c_lower = col_name.lower()

    # Check for numeric conversion
    cleaned_val = val_str.replace("$", "").replace(",", "")
    try:
        num = float(cleaned_val)
    except (ValueError, TypeError):
        return None

    # Check negative values in typically positive fields
    positive_fields = ("income", "salary", "price", "cost", "revenue", "age", "rating", "score", "quantity", "count", "amount")
    if any(k in c_lower for k in positive_fields) and num < 0:
        return f"Negative value ({num}) in typically positive column '{col_name}'"

    # Rating / Score range check (typically 0-5 or 0-10 or 0-100)
    if "rating" in c_lower:
        if num < 0 or num > 10:
            return f"Rating value ({num}) outside standard scale"

    # Age check
    if c_lower in ("age", "customer_age", "user_age"):
        if num < 0 or num > 130:
            return f"Unrealistic age value ({num})"

    # Suspicious round placeholder numbers like 999999 or -999
    if num in (-999, -9999, 99999, 999999, 9999999):
        return f"Suspicious placeholder value ({num})"

    return None


def _compare_rows(ref_row: pd.Series, cur_row: pd.Series, row_id, skip_col: str = None) -> list:
    changes = []
    ref_cols = set(ref_row.index)
    cur_cols = set(cur_row.index)
    common = sorted(list(ref_cols & cur_cols))
    for col in common:
        if skip_col and col == skip_col:
            continue
        rv = ref_row[col]
        cv = cur_row[col]
        ref_na = pd.isna(rv) if not isinstance(rv, str) else rv in ("", "nan", "none", "null")
        cur_na = pd.isna(cv) if not isinstance(cv, str) else cv in ("", "nan", "none", "null")
        if ref_na and cur_na:
            continue
        if str(rv) != str(cv):
            anomaly = _detect_cell_anomaly(col, cv) or _detect_cell_anomaly(col, rv)
            changes.append({
                "column": col,
                "reference_value": str(rv) if not ref_na else None,
                "current_value": str(cv) if not cur_na else None,
                "anomaly": anomaly,
                "anomalous": anomaly is not None,
                "anomaly_reason": anomaly,
            })
    return changes

