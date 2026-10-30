"""Suspicious and invalid value detection."""
import re
import pandas as pd
import numpy as np
from backend.utils.df_utils import (
    is_numeric_col,
    is_identifier_col,
    clean_numeric_series,
    get_missing_mask,
    can_be_numeric,
)

# Standard sentinel placeholder tokens (case-insensitive, trimmed)
PLACEHOLDERS = {
    "nil", "unknown", "?", "??", "???", "-", "--", "---",
    "tbd", "tba", "xxx", "xxxx", "dummy", "test", "testing",
    "undefined", "[object object]", "<null>", "<na>", "none/none",
    "void", "n/a", "na",
}

# Numeric sentinel values often used in legacy systems or error logs
NUMERIC_SENTINELS = {-999, -9999, -99999, 99999, 999999, 9999999}


def analyze_suspicious(df: pd.DataFrame, kept_cells: set = None) -> dict:
    issues = []
    kept = kept_cells or set()
    for col in df.columns:
        series = df[col]
        mask = get_missing_mask(series)
        non_null = series[~mask]
        if len(non_null) == 0:
            continue

        if is_numeric_col(series) and not is_identifier_col(series, col):
            issues.extend(_numeric_suspicious(series, col, kept))
        else:
            issues.extend(_text_suspicious(series, col, kept))

    return {
        "suspicious_issues": issues,
        "has_suspicious": len(issues) > 0,
        "total_suspicious_count": sum(i.get("count", len(i.get("indices", []))) for i in issues),
    }


def _numeric_suspicious(series: pd.Series, col: str, kept: set = None) -> list:
    issues = []
    num_series = clean_numeric_series(series)
    mask = get_missing_mask(series)
    non_null = num_series[~mask].dropna()
    if len(non_null) < 3:
        return []

    kept_set = kept or set()

    # Extreme outliers (beyond 3×IQR)
    q1 = float(non_null.quantile(0.25))
    q3 = float(non_null.quantile(0.75))
    iqr = q3 - q1
    extreme_lower = q1 - 3 * iqr
    extreme_upper = q3 + 3 * iqr

    # Values beyond 3x IQR
    extreme_mask = (num_series < extreme_lower) | (num_series > extreme_upper)
    extreme_indices = [
        int(i) for i in num_series[extreme_mask & num_series.notna() & ~mask].index.tolist()
        if (int(i), col) not in kept_set
    ]

    # Also check known numeric sentinels outside [q1 - 1.5*iqr, q3 + 1.5*iqr]
    normal_lower = q1 - 1.5 * iqr
    normal_upper = q3 + 1.5 * iqr
    sentinel_mask = num_series.isin(NUMERIC_SENTINELS) & ((num_series < normal_lower) | (num_series > normal_upper))
    sentinel_indices = [
        int(i) for i in num_series[sentinel_mask & num_series.notna() & ~mask].index.tolist()
        if (int(i), col) not in kept_set and int(i) not in extreme_indices
    ]

    all_numeric_flagged = extreme_indices + sentinel_indices

    if len(all_numeric_flagged) > 0:
        row_details = []
        for idx in all_numeric_flagged:
            val = float(num_series.loc[idx])
            is_sentinel = val in NUMERIC_SENTINELS
            reason = (
                f"Suspicious numeric sentinel value ({val:.0f})"
                if is_sentinel
                else f"Extreme numeric outlier ({val:.2f}) beyond 3×IQR fence [{extreme_lower:.2f}, {extreme_upper:.2f}]"
            )
            row_details.append({
                "row": idx,
                "column": col,
                "original_value": val,
                "reason": reason,
                "severity": "high",
                "category_type": "outlier" if not is_sentinel else "invalid",
            })

        active_vals = num_series.loc[all_numeric_flagged]
        issues.append({
            "type": "EXTREME_OUTLIER",
            "category_type": "outlier",
            "column": col,
            "count": len(all_numeric_flagged),
            "indices": all_numeric_flagged,
            "values": [float(v) for v in active_vals.head(10).tolist()],
            "description": f"Column '{col}' has {len(all_numeric_flagged)} value(s) beyond 3×IQR fence ({extreme_lower:.2f}, {extreme_upper:.2f}).",
            "severity": "high",
            "why": "Values beyond 3× the IQR fence are statistically unusual and may indicate data entry errors or anomalous observations.",
            "recommendation": "Inspect flagged values and choose an action: Delete row(s) (recommended), Correct with verified value, or Keep if valid observation.",
            "row_details": row_details,
        })

    return issues


def _text_suspicious(series: pd.Series, col: str, kept: set = None) -> list:
    issues = []
    mask = get_missing_mask(series)
    non_null = series[~mask].astype(str)
    if len(non_null) == 0:
        return []

    kept_set = kept or set()

    # 1. Placeholder-like values (excluding standard null strings already detected as missing)
    s_trimmed_lower = non_null.str.strip().str.lower()
    ph_mask = s_trimmed_lower.isin(PLACEHOLDERS)
    ph_indices = [int(i) for i in non_null[ph_mask].index.tolist() if (int(i), col) not in kept_set]
    if len(ph_indices) > 0:
        ph_vals = non_null.loc[ph_indices]
        row_details = []
        for idx in ph_indices:
            orig = str(non_null.loc[idx])
            row_details.append({
                "row": idx,
                "column": col,
                "original_value": orig,
                "reason": f"Placeholder token '{orig}' masks genuine categorical value",
                "severity": "medium",
                "category_type": "invalid",
            })
        issues.append({
            "type": "PLACEHOLDER_VALUES",
            "category_type": "invalid",
            "column": col,
            "count": len(ph_indices),
            "indices": ph_indices,
            "values": list(ph_vals.head(10).tolist()),
            "description": f"Column '{col}' has {len(ph_indices)} potential placeholder value(s) (e.g., {list(ph_vals.unique()[:5])}).",
            "severity": "medium",
            "why": "Placeholder strings mask true values and distort category distribution and analysis.",
            "recommendation": "Inspect flagged values and decide: Delete row(s) (recommended), Correct with verified value, or Keep if valid observation.",
            "row_details": row_details,
        })

    # 2. Corrupt / numeric sentinel values in predominantly text/categorical columns
    valid_non_ph = non_null[~ph_mask]
    if len(valid_non_ph) > 0:
        # Check if column is predominantly alphabetic/descriptive text (>60% contain letters)
        has_alpha_ratio = valid_non_ph.str.contains(r"[a-zA-Z]", regex=True).mean()
        if has_alpha_ratio >= 0.6:
            # Check for numeric sentinels or corrupt symbol strings
            corrupt_indices = []
            row_details_corrupt = []
            for idx, val in valid_non_ph.items():
                if (int(idx), col) in kept_set:
                    continue
                v_str = str(val).strip()
                # Check for sentinel integer in text column
                try:
                    num_val = int(v_str)
                    if num_val in NUMERIC_SENTINELS:
                        corrupt_indices.append(int(idx))
                        row_details_corrupt.append({
                            "row": int(idx),
                            "column": col,
                            "original_value": v_str,
                            "reason": f"Numeric sentinel value '{v_str}' in text category column",
                            "severity": "high",
                            "category_type": "invalid",
                        })
                        continue
                except (ValueError, TypeError):
                    pass

                # Check for corrupt non-alphanumeric punctuation junk (e.g. "###", "!!!", "***")
                if len(v_str) >= 2 and re.match(r"^[^a-zA-Z0-9\s]+$", v_str) and v_str not in {"-", "--", "/", "&", "+"}:
                    corrupt_indices.append(int(idx))
                    row_details_corrupt.append({
                        "row": int(idx),
                        "column": col,
                        "original_value": v_str,
                        "reason": f"Corrupt or symbol-only value '{v_str}' in category column",
                        "severity": "high",
                        "category_type": "invalid",
                    })

            if corrupt_indices:
                corrupt_vals = non_null.loc[corrupt_indices]
                issues.append({
                    "type": "CORRUPT_OR_INVALID_VALUE",
                    "category_type": "invalid",
                    "column": col,
                    "count": len(corrupt_indices),
                    "indices": corrupt_indices,
                    "values": list(corrupt_vals.head(10).tolist()),
                    "description": f"Column '{col}' has {len(corrupt_indices)} corrupt or invalid sentinel value(s).",
                    "severity": "high",
                    "why": "Corrupt symbols or numeric error codes in category columns corrupt aggregations and reporting.",
                    "recommendation": "Inspect and decide: Delete row(s), Correct with verified value, or Keep.",
                    "row_details": row_details_corrupt,
                })

    # 3. Categorical consistency analysis (casing and whitespace variants)
    # Only analyze if column behaves like categorical (low-to-moderate distinct count)
    clean_categorical_vals = non_null[~ph_mask]
    n_unique = clean_categorical_vals.nunique()
    total_len = len(clean_categorical_vals)

    is_categorical_col = (
        (total_len <= 50 and n_unique <= 30)
        or (total_len > 50 and n_unique <= 60)
        or (total_len > 20 and n_unique / total_len <= 0.6)
    )

    if is_categorical_col and n_unique > 1:
        # Group unique distinct values by lowercased, stripped representation
        val_counts = clean_categorical_vals.value_counts()
        cluster_map = {}
        for raw_val in clean_categorical_vals.unique():
            norm_key = str(raw_val).strip().lower()
            cluster_map.setdefault(norm_key, []).append(str(raw_val))

        casing_indices = []
        casing_details = []
        casing_variants_reported = []

        whitespace_indices = []
        whitespace_details = []

        for norm_key, variants in cluster_map.items():
            if len(variants) > 1:
                # Determine the canonical dominant form:
                # 1) Highest occurrence frequency in dataset
                # 2) Trimmed over untrimmed
                # 3) Conventional capitalization (Title/Upper > lower)
                canonical = max(
                    variants,
                    key=lambda v: (
                        val_counts.get(v, 0),
                        len(v) == len(v.strip()),
                        1 if v and v[0].isupper() else 0,
                    )
                )
                canonical_count = val_counts.get(canonical, 0)

                for var in variants:
                    # Check for whitespace variant
                    if var != var.strip():
                        var_indices_ws = [
                            int(i) for i in clean_categorical_vals[clean_categorical_vals == var].index.tolist()
                            if (int(i), col) not in kept_set
                        ]
                        for r_idx in var_indices_ws:
                            whitespace_indices.append(r_idx)
                            whitespace_details.append({
                                "row": r_idx,
                                "column": col,
                                "original_value": var,
                                "reason": f"Whitespace inconsistency: value contains leading/trailing spaces (canonical: '{canonical}')",
                                "severity": "low",
                                "category_type": "inconsistency",
                            })

                    # Check for casing variant deviating from canonical
                    if var.strip() != canonical.strip() and var.strip().lower() == canonical.strip().lower():
                        deviant_indices = [
                            int(i) for i in clean_categorical_vals[clean_categorical_vals == var].index.tolist()
                            if (int(i), col) not in kept_set
                        ]
                        for r_idx in deviant_indices:
                            casing_indices.append(r_idx)
                            casing_details.append({
                                "row": r_idx,
                                "column": col,
                                "original_value": var,
                                "reason": f"Potential casing inconsistency: '{var}' deviating from dominant canonical category '{canonical}' ({canonical_count} occurrences)",
                                "severity": "low",
                                "category_type": "inconsistency",
                            })
                        casing_variants_reported.append(f"'{var}' (vs canonical '{canonical}')")

        if casing_indices:
            issues.append({
                "type": "CASING_INCONSISTENCY",
                "category_type": "inconsistency",
                "column": col,
                "count": len(casing_indices),
                "variants": casing_variants_reported[:10],
                "indices": casing_indices,
                "description": f"Column '{col}' has {len(casing_indices)} potential category casing inconsistency value(s): {', '.join(casing_variants_reported[:3])}.",
                "severity": "low",
                "why": "Inconsistent capitalization creates separate categories in filters, groupings, and reports. Dominant categories were recognized.",
                "recommendation": "Standardize casing to match dominant categories across this column, or Keep if intentionally distinct.",
                "row_details": casing_details,
            })

        if whitespace_indices:
            issues.append({
                "type": "WHITESPACE_INCONSISTENCY",
                "category_type": "inconsistency",
                "column": col,
                "count": len(whitespace_indices),
                "indices": whitespace_indices,
                "description": f"Column '{col}' has {len(whitespace_indices)} value(s) with leading or trailing whitespace.",
                "severity": "low",
                "why": "Surrounding whitespace causes invisible mismatches during joins, lookups, and aggregations.",
                "recommendation": "Trim whitespace to match standard categories.",
                "row_details": whitespace_details,
            })

    # 4. Very long strings (only flag truly runaway or dumped text strings)
    lengths = non_null.str.len()
    max_len = lengths.max()
    mean_len = lengths.mean()
    std_len = lengths.std()
    if max_len > 100 and std_len > 15 and mean_len > 15:
        threshold = max(100.0, mean_len + 4 * std_len)
        long_mask = lengths > threshold
        long_indices = [int(i) for i in non_null[long_mask].index.tolist() if (int(i), col) not in kept_set]
        if len(long_indices) > 0:
            long_vals = non_null.loc[long_indices]
            row_details_long = [
                {
                    "row": idx,
                    "column": col,
                    "original_value": str(non_null.loc[idx]),
                    "reason": f"Unusually long text string ({len(str(non_null.loc[idx]))} chars, threshold >{threshold:.0f})",
                    "severity": "low",
                    "category_type": "anomaly",
                }
                for idx in long_indices
            ]
            issues.append({
                "type": "UNUSUALLY_LONG_TEXT",
                "category_type": "anomaly",
                "column": col,
                "count": len(long_indices),
                "indices": long_indices,
                "values": [str(v)[:50] + "..." if len(str(v)) > 50 else str(v) for v in long_vals.head(5).tolist()],
                "description": f"Column '{col}' has {len(long_indices)} value(s) with unusually long text (>{threshold:.0f} chars).",
                "severity": "low",
                "why": "Unusually long text may indicate data entry errors, accidental concatenation, or log dumps.",
                "recommendation": "Inspect flagged values and decide: Delete row(s), Correct, or Keep if valid description.",
                "row_details": row_details_long,
            })

    return issues
