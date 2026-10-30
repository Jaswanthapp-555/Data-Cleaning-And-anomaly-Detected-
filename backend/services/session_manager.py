"""In-memory session manager for dataset state."""
import uuid
import copy
import threading
import pandas as pd
from datetime import datetime, timezone
from typing import Optional

_lock = threading.Lock()
_sessions: dict[str, dict] = {}


def new_session() -> str:
    sid = str(uuid.uuid4())
    with _lock:
        _sessions[sid] = _empty_session()
    return sid


def _empty_dataset_state():
    return {
        "original_df": None,
        "working_df": None,
        "finalized_df": None,
        "source_info": {},
        "analysis": None,
        "original_analysis": None,
        "change_history": [],
        "kept_cells": set(),
        "resolved_outliers": [],
        "resolved_suspicious": [],
        "state": "empty",  # empty | uploaded | analyzed | finalized
    }


def _empty_session():
    return {
        "mode": None,  # single | compare
        "single": _empty_dataset_state(),
        "ref": _empty_dataset_state(),
        "cur": _empty_dataset_state(),
        "comparison_result": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def get_session(sid: str) -> Optional[dict]:
    with _lock:
        return _sessions.get(sid)


def set_session(sid: str, data: dict):
    with _lock:
        _sessions[sid] = data


def normalize_key(key: str) -> str:
    if not key:
        return "single"
    k = str(key).lower().strip()
    if k in ("ref", "reference"):
        return "ref"
    if k in ("cur", "current"):
        return "cur"
    return k


def get_ds(sid: str, dataset_key: str) -> Optional[dict]:
    """Get dataset state (single/ref/cur)."""
    dataset_key = normalize_key(dataset_key)
    sess = get_session(sid)
    if not sess:
        return None
    return sess.get(dataset_key)


def set_ds(sid: str, dataset_key: str, ds: dict):
    dataset_key = normalize_key(dataset_key)
    with _lock:
        if sid in _sessions:
            _sessions[sid][dataset_key] = ds


def set_original(sid: str, dataset_key: str, df: pd.DataFrame, source_info: dict):
    dataset_key = normalize_key(dataset_key)
    with _lock:
        sess = _sessions.get(sid)
        if not sess:
            return
        sess[dataset_key]["original_df"] = df.copy()
        sess[dataset_key]["working_df"] = df.copy()
        sess[dataset_key]["finalized_df"] = None
        sess[dataset_key]["source_info"] = source_info
        sess[dataset_key]["analysis"] = None
        sess[dataset_key]["original_analysis"] = None
        sess[dataset_key]["change_history"] = []
        sess[dataset_key]["kept_cells"] = set()
        sess[dataset_key]["resolved_outliers"] = []
        sess[dataset_key]["resolved_suspicious"] = []
        sess[dataset_key]["state"] = "uploaded"


def get_working_df(sid: str, dataset_key: str) -> Optional[pd.DataFrame]:
    dataset_key = normalize_key(dataset_key)
    with _lock:
        sess = _sessions.get(sid)
        if not sess:
            return None
        w_df = sess[dataset_key].get("working_df")
        if w_df is None:
            w_df = sess[dataset_key].get("finalized_df")
        return w_df


def set_working_df(sid: str, dataset_key: str, df: pd.DataFrame):
    dataset_key = normalize_key(dataset_key)
    with _lock:
        sess = _sessions.get(sid)
        if not sess:
            return
        sess[dataset_key]["working_df"] = df.copy()
        sess[dataset_key]["analysis"] = None  # Invalidate cached analysis


def get_original_df(sid: str, dataset_key: str) -> Optional[pd.DataFrame]:
    dataset_key = normalize_key(dataset_key)
    with _lock:
        sess = _sessions.get(sid)
        if not sess:
            return None
        return sess[dataset_key].get("original_df")


def add_history(sid: str, dataset_key: str, entry: dict):
    dataset_key = normalize_key(dataset_key)
    with _lock:
        sess = _sessions.get(sid)
        if not sess:
            return
        entry["timestamp"] = datetime.now(timezone.utc).isoformat()
        entry["sequence"] = len(sess[dataset_key]["change_history"]) + 1
        sess[dataset_key]["change_history"].append(entry)


def get_history(sid: str, dataset_key: str) -> list:
    dataset_key = normalize_key(dataset_key)
    with _lock:
        sess = _sessions.get(sid)
        if not sess:
            return []
        return sess[dataset_key].get("change_history", [])


def add_kept_cell(sid: str, dataset_key: str, row_index: int, column: str):
    """Record a cell user chose to Keep / Leave Unchanged in the shared cross-category registry."""
    dataset_key = normalize_key(dataset_key)
    with _lock:
        sess = _sessions.get(sid)
        if not sess:
            return
        if "kept_cells" not in sess[dataset_key]:
            sess[dataset_key]["kept_cells"] = set()
        sess[dataset_key]["kept_cells"].add((int(row_index), str(column)))


def get_kept_cells(sid: str, dataset_key: str) -> set:
    """Get the set of kept (row_index, column) tuples."""
    dataset_key = normalize_key(dataset_key)
    with _lock:
        sess = _sessions.get(sid)
        if not sess:
            return set()
        return set(sess[dataset_key].get("kept_cells", set()))


def clear_kept_cells(sid: str, dataset_key: str):
    dataset_key = normalize_key(dataset_key)
    with _lock:
        sess = _sessions.get(sid)
        if not sess:
            return
        sess[dataset_key]["kept_cells"] = set()


def add_resolved_outlier(sid: str, dataset_key: str, column: str, row_index: int, value=None):
    dataset_key = normalize_key(dataset_key)
    with _lock:
        sess = _sessions.get(sid)
        if not sess:
            return
        if "resolved_outliers" not in sess[dataset_key]:
            sess[dataset_key]["resolved_outliers"] = []
        sess[dataset_key]["resolved_outliers"].append({
            "column": column, "row_index": row_index, "value": value
        })
        if "kept_cells" not in sess[dataset_key]:
            sess[dataset_key]["kept_cells"] = set()
        sess[dataset_key]["kept_cells"].add((int(row_index), str(column)))


def add_resolved_suspicious(sid: str, dataset_key: str, column: str, row_index: int, value=None):
    dataset_key = normalize_key(dataset_key)
    with _lock:
        sess = _sessions.get(sid)
        if not sess:
            return
        if "resolved_suspicious" not in sess[dataset_key]:
            sess[dataset_key]["resolved_suspicious"] = []
        sess[dataset_key]["resolved_suspicious"].append({
            "column": column, "row_index": row_index, "value": value
        })
        if "kept_cells" not in sess[dataset_key]:
            sess[dataset_key]["kept_cells"] = set()
        sess[dataset_key]["kept_cells"].add((int(row_index), str(column)))


def adjust_resolved_indices(sid: str, dataset_key: str, deleted_indices: list):
    """Adjust row indices of previously resolved issues when rows are deleted."""
    dataset_key = normalize_key(dataset_key)
    with _lock:
        sess = _sessions.get(sid)
        if not sess:
            return
        del_set = set(deleted_indices)
        for key in ("resolved_outliers", "resolved_suspicious"):
            current = sess[dataset_key].get(key, [])
            updated = []
            for item in current:
                r = item.get("row_index")
                if r is None or r in del_set:
                    continue
                shift = sum(1 for d in deleted_indices if d < r)
                item_copy = dict(item)
                item_copy["row_index"] = r - shift
                updated.append(item_copy)
            sess[dataset_key][key] = updated


def filter_resolved_issues(analysis: dict, resolved_outliers: list, resolved_suspicious: list) -> dict:
    """Filter out resolved outliers and suspicious values so resolved columns drop out of dropdowns."""
    if not analysis:
        return analysis

    filtered = copy.deepcopy(analysis)

    # 1. Filter outliers
    if "outliers" in filtered and "outlier_details" in filtered["outliers"]:
        resolved_out_map = {}
        for r in resolved_outliers:
            col = r.get("column")
            if col:
                resolved_out_map.setdefault(col, set()).add(r.get("row_index"))

        new_outlier_details = []
        for item in filtered["outliers"]["outlier_details"]:
            col = item.get("column")
            resolved_rows = resolved_out_map.get(col, set())

            remaining_indices = [idx for idx in item.get("combined_indices", []) if idx not in resolved_rows]
            remaining_values = [v for v in item.get("outlier_values", []) if (v.get("row") if v.get("row") is not None else v.get("index")) not in resolved_rows]

            # If there are still unresolved outliers in this column, keep it with updated counts
            if len(remaining_indices) > 0:
                item["combined_indices"] = remaining_indices
                item["combined_count"] = len(remaining_indices)
                item["outlier_values"] = remaining_values
                new_outlier_details.append(item)
            # If all were resolved, the column drops out entirely!

        filtered["outliers"]["outlier_details"] = new_outlier_details
        filtered["outliers"]["columns_with_outliers"] = len(new_outlier_details)
        filtered["outliers"]["has_outliers"] = len(new_outlier_details) > 0

    # 2. Filter suspicious
    if "suspicious" in filtered and "suspicious_issues" in filtered["suspicious"]:
        resolved_susp_map = {}
        for r in resolved_suspicious:
            col = r.get("column")
            if col:
                resolved_susp_map.setdefault(col, set()).add(r.get("row_index"))

        new_susp_issues = []
        for iss in filtered["suspicious"]["suspicious_issues"]:
            col = iss.get("column")
            resolved_rows = resolved_susp_map.get(col, set())

            if "indices" in iss and iss["indices"]:
                remaining_indices = [idx for idx in iss["indices"] if idx not in resolved_rows]
                resolved_in_issue = len([idx for idx in iss["indices"] if idx in resolved_rows])
                new_count = max(0, iss.get("count", len(iss["indices"])) - resolved_in_issue)
                if len(remaining_indices) > 0 and new_count > 0:
                    iss["indices"] = remaining_indices
                    iss["count"] = new_count
                    if "row_details" in iss:
                        iss["row_details"] = [d for d in iss["row_details"] if d.get("row") not in resolved_rows]
                    new_susp_issues.append(iss)
            else:
                if col not in resolved_susp_map:
                    new_susp_issues.append(iss)

        filtered["suspicious"]["suspicious_issues"] = new_susp_issues
        filtered["suspicious"]["has_suspicious"] = len(new_susp_issues) > 0
        filtered["suspicious"]["total_suspicious_count"] = sum(i.get("count", 1) for i in new_susp_issues)

    # 3. Filter issue_center
    if "issue_center" in filtered:
        active_outlier_cols = {d["column"] for d in filtered.get("outliers", {}).get("outlier_details", [])}
        active_susp_cols = {i.get("column") for i in filtered.get("suspicious", {}).get("suspicious_issues", [])}

        filtered_issue_center = []
        for issue in filtered["issue_center"]:
            cat = issue.get("category", "")
            col = issue.get("column", "")
            if "Outlier" in cat and col and col not in active_outlier_cols:
                continue
            if ("Suspicious" in cat or "Invalid" in cat or "Inconsisten" in cat) and col and col not in active_susp_cols:
                continue
            # Keep remaining affected indices in sync
            if ("Suspicious" in cat or "Invalid" in cat or "Inconsisten" in cat) and col in resolved_susp_map:
                resolved_rows = resolved_susp_map.get(col, set())
                rem_idx = [idx for idx in issue.get("affected_indices", []) if idx not in resolved_rows]
                issue["affected_indices"] = rem_idx
                issue["count"] = len(rem_idx)
                if "row_details" in issue:
                    issue["row_details"] = [d for d in issue["row_details"] if d.get("row") not in resolved_rows]
            # A card must disappear when its count reaches 0. Never show a count that opens to an empty list.
            if issue.get("count", 0) <= 0:
                continue
            if isinstance(issue.get("affected_indices"), list) and len(issue.get("affected_indices")) == 0 and issue.get("category") in ("Data-Type Issues", "Missing Values", "Duplicate Rows", "Suspicious Values", "Category Inconsistencies", "Potential Outliers"):
                continue
            if issue.get("category") in ("Schema Problems", "Schema Issues"):
                continue
            filtered_issue_center.append(issue)
        filtered["issue_center"] = filtered_issue_center

    return filtered


def set_analysis(sid: str, dataset_key: str, result: dict):
    dataset_key = normalize_key(dataset_key)
    with _lock:
        sess = _sessions.get(sid)
        if not sess:
            return
        sess[dataset_key]["analysis"] = result
        sess[dataset_key]["state"] = "analyzed"


def get_analysis(sid: str, dataset_key: str) -> Optional[dict]:
    dataset_key = normalize_key(dataset_key)
    with _lock:
        sess = _sessions.get(sid)
        if not sess:
            return None
        raw = sess[dataset_key].get("analysis")
        if not raw:
            return None
        res_out = sess[dataset_key].get("resolved_outliers", [])
        res_susp = sess[dataset_key].get("resolved_suspicious", [])
        return filter_resolved_issues(raw, res_out, res_susp)


def set_original_analysis(sid: str, dataset_key: str, result: dict):
    dataset_key = normalize_key(dataset_key)
    with _lock:
        sess = _sessions.get(sid)
        if not sess:
            return
        sess[dataset_key]["original_analysis"] = copy.deepcopy(result)


def get_original_analysis(sid: str, dataset_key: str) -> Optional[dict]:
    dataset_key = normalize_key(dataset_key)
    with _lock:
        sess = _sessions.get(sid)
        if not sess:
            return None
        return sess[dataset_key].get("original_analysis")


def finalize_dataset(sid: str, dataset_key: str):
    dataset_key = normalize_key(dataset_key)
    with _lock:
        sess = _sessions.get(sid)
        if not sess:
            return
        working = sess[dataset_key]["working_df"]
        if working is not None:
            sess[dataset_key]["finalized_df"] = working.copy()
            sess[dataset_key]["state"] = "finalized"


def get_finalized_df(sid: str, dataset_key: str) -> Optional[pd.DataFrame]:
    dataset_key = normalize_key(dataset_key)
    with _lock:
        sess = _sessions.get(sid)
        if not sess:
            return None
        return sess[dataset_key].get("finalized_df")


def reset_working(sid: str, dataset_key: str):
    dataset_key = normalize_key(dataset_key)
    with _lock:
        sess = _sessions.get(sid)
        if not sess:
            return
        orig = sess[dataset_key]["original_df"]
        if orig is not None:
            sess[dataset_key]["working_df"] = orig.copy()
            sess[dataset_key]["analysis"] = None
            sess[dataset_key]["kept_cells"] = set()
            sess[dataset_key]["resolved_outliers"] = []
            sess[dataset_key]["resolved_suspicious"] = []
            sess[dataset_key]["state"] = "uploaded"
            sess[dataset_key]["change_history"].append({
                "action": "RESET",
                "description": "Working dataset reset to original uploaded state.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sequence": len(sess[dataset_key]["change_history"]) + 1,
            })


def set_comparison(sid: str, result: dict):
    with _lock:
        sess = _sessions.get(sid)
        if not sess:
            return
        sess["comparison_result"] = result


def get_comparison(sid: str) -> Optional[dict]:
    with _lock:
        sess = _sessions.get(sid)
        if not sess:
            return None
        return sess.get("comparison_result")


def delete_session(sid: str):
    with _lock:
        _sessions.pop(sid, None)
