"""Exact duplicate row detection."""
import pandas as pd


def analyze_duplicates(df: pd.DataFrame) -> dict:
    """Detect exact complete-row duplicates only."""
    if len(df) == 0:
        return {"total_duplicates": 0, "duplicate_groups": [], "has_duplicates": False}

    # Mark all rows that are exact duplicates of another row
    dup_mask = df.duplicated(keep=False)
    dup_count = int(dup_mask.sum())

    groups = []
    if dup_count > 0:
        dup_df = df[dup_mask].copy()
        dup_df["_row_index"] = dup_df.index.tolist()

        # Group by all columns to find groups
        group_cols = list(df.columns)
        try:
            grouped = dup_df.groupby(group_cols, dropna=False)
            for key, grp in grouped:
                if len(grp) < 2:
                    continue
                indices = grp["_row_index"].tolist()
                row_vals = {col: _safe_val(grp.iloc[0][col] if len(grp) > 0 else None) for col in group_cols}
                groups.append({
                    "indices": indices,
                    "count": len(grp),
                    "row_values": row_vals,
                })
        except Exception:
            # Fallback: just report indices
            groups.append({
                "indices": list(dup_df["_row_index"].tolist()),
                "count": dup_count,
                "row_values": {},
            })

    return {
        "total_duplicates": dup_count,
        "duplicate_groups": groups,
        "has_duplicates": dup_count > 0,
        "duplicate_pct": round(dup_count / len(df) * 100, 2) if len(df) > 0 else 0,
    }


def _safe_val(val):
    import numpy as np
    if val is None:
        return None
    if isinstance(val, float) and np.isnan(val):
        return None
    return str(val)
