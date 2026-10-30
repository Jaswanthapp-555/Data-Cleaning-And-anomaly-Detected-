"""Cleaning operation routes."""
from flask import Blueprint, request, jsonify
import pandas as pd
import numpy as np
from backend.services import session_manager as sm
from backend.cleaning import cleaning_engine as ce
from backend.analysis import run_full_analysis
from backend.analysis.missing_analyzer import compute_imputation_value
from backend.analysis.type_analyzer import preview_type_conversion
from backend.utils.df_utils import is_numeric_col, can_be_numeric, clean_numeric_series, get_missing_mask

bp = Blueprint("cleaning", __name__, url_prefix="/api/clean")


def _require(data, *keys):
    for k in keys:
        if k not in data:
            return jsonify({"error": f"Missing required field: {k}"}), 400
    return None


def _update_and_reanalyze(sid, dk, new_df, entry):
    sm.set_working_df(sid, dk, new_df)
    if isinstance(entry, list):
        for e in entry:
            sm.add_history(sid, dk, e)
    elif entry:
        sm.add_history(sid, dk, entry)
    kept_cells = sm.get_kept_cells(sid, dk)
    fresh_analysis = run_full_analysis(new_df, kept_cells=kept_cells)
    sm.set_analysis(sid, dk, fresh_analysis)
    return sm.get_analysis(sid, dk)


@bp.route("/edit-cell", methods=["POST"])
def edit_cell():
    data = request.json or {}
    err = _require(data, "session_id", "dataset", "row_index", "column", "new_value")
    if err: return err
    sid, dk = data["session_id"], data["dataset"]
    df = sm.get_working_df(sid, dk)
    if df is None: return jsonify({"error": "Dataset not found."}), 404
    try:
        new_df, entry = ce.edit_cell(df, int(data["row_index"]), data["column"], data["new_value"])
        analysis = _update_and_reanalyze(sid, dk, new_df, entry)
        return jsonify({"success": True, "entry": entry, "analysis": analysis})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/delete-rows", methods=["POST"])
def delete_rows():
    data = request.json or {}
    err = _require(data, "session_id", "dataset", "row_indices")
    if err: return err
    sid, dk = data["session_id"], data["dataset"]
    df = sm.get_working_df(sid, dk)
    if df is None: return jsonify({"error": "Dataset not found."}), 404
    try:
        indices = [int(i) for i in data["row_indices"]]
        new_df, entry = ce.delete_rows(df, indices)
        sm.adjust_resolved_indices(sid, dk, indices)
        analysis = _update_and_reanalyze(sid, dk, new_df, entry)
        return jsonify({"success": True, "entry": entry, "new_row_count": len(new_df), "analysis": analysis})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/delete-columns", methods=["POST"])
def delete_columns():
    data = request.json or {}
    err = _require(data, "session_id", "dataset", "columns")
    if err: return err
    sid, dk = data["session_id"], data["dataset"]
    df = sm.get_working_df(sid, dk)
    if df is None: return jsonify({"error": "Dataset not found."}), 404
    try:
        new_df, entry = ce.delete_columns(df, data["columns"])
        analysis = _update_and_reanalyze(sid, dk, new_df, entry)
        return jsonify({"success": True, "entry": entry, "remaining_columns": list(new_df.columns), "analysis": analysis})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/rename-column", methods=["POST"])
def rename_column():
    data = request.json or {}
    err = _require(data, "session_id", "dataset", "old_name", "new_name")
    if err: return err
    sid, dk = data["session_id"], data["dataset"]
    df = sm.get_working_df(sid, dk)
    if df is None: return jsonify({"error": "Dataset not found."}), 404
    try:
        new_df, entry = ce.rename_column(df, data["old_name"], data["new_name"])
        analysis = _update_and_reanalyze(sid, dk, new_df, entry)
        return jsonify({"success": True, "entry": entry, "analysis": analysis})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/preview-fill-missing", methods=["POST"])
def preview_fill_missing():
    data = request.json or {}
    err = _require(data, "session_id", "dataset", "column", "method")
    if err: return err
    sid, dk = data["session_id"], data["dataset"]
    column, method = data["column"], data["method"]
    df = sm.get_working_df(sid, dk)
    if df is None: return jsonify({"error": "Dataset not found."}), 404
    if column not in df.columns: return jsonify({"error": f"Column '{column}' not found."}), 404

    mask = get_missing_mask(df[column])
    missing_indices = [int(i) for i in df[mask].index.tolist()]
    if not missing_indices:
        return jsonify({"error": f"No missing values found in column '{column}'."}), 400

    is_num = can_be_numeric(df[column])

    if method in ("mean", "median", "mean_excl_outliers", "median_excl_outliers"):
        if not is_num:
            return jsonify({"error": f"Method '{method}' is only applicable to numerical columns."}), 400
        num_series = clean_numeric_series(df[column])
        fill_val, desc = compute_imputation_value(num_series, method)
    elif method == "mode":
        if is_num:
            return jsonify({"error": f"Method 'mode' is only applicable to categorical/text columns. Column '{column}' is numeric."}), 400
        fill_val, desc = compute_imputation_value(df[column], "mode")
    elif method == "manual":
        manual_val = data.get("manual_value")
        if manual_val is None or str(manual_val).strip() == "":
            return jsonify({"error": "Manual value cannot be empty."}), 400
        if is_num:
            try:
                v_str = str(manual_val).strip().replace("$", "").replace(",", "")
                fill_val = float(v_str) if "." in v_str else int(v_str)
            except ValueError:
                return jsonify({"error": f"Invalid manual numeric value '{manual_val}'."}), 400
            desc = f"Manual numeric value: {fill_val}"
        else:
            fill_val = str(manual_val)
            desc = f"Manual text value: '{fill_val}'"
    elif method == "delete_row":
        fill_val = "DELETE ROW"
        desc = "Delete affected rows"
    elif method == "leave_unchanged":
        fill_val = "LEAVE UNCHANGED"
        desc = "No changes applied"
    else:
        return jsonify({"error": f"Unknown imputation method '{method}'."}), 400

    sample_affected = [
        {"row": r, "original": "Missing", "new": str(fill_val)}
        for r in missing_indices[:15]
    ]

    return jsonify({
        "column": column,
        "dtype": "Numerical (float64)" if is_num else str(df[column].dtype),
        "missing_count": len(missing_indices),
        "total_rows": len(df),
        "missing_pct": round(len(missing_indices) / len(df) * 100, 2),
        "method": method,
        "description": desc,
        "replacement_value": fill_val,
        "affected_rows_count": len(missing_indices),
        "sample_affected": sample_affected,
    })


@bp.route("/fill-missing", methods=["POST"])
def fill_missing():
    data = request.json or {}
    err = _require(data, "session_id", "dataset", "column", "method")
    if err: return err
    sid, dk = data["session_id"], data["dataset"]
    df = sm.get_working_df(sid, dk)
    if df is None: return jsonify({"error": "Dataset not found."}), 404
    try:
        new_df, entry = ce.fill_missing(df, data["column"], data["method"],
                                         manual_value=data.get("manual_value"))
        analysis = _update_and_reanalyze(sid, dk, new_df, entry)
        return jsonify({"success": True, "entry": entry, "analysis": analysis})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/remove-duplicates", methods=["POST"])
def remove_duplicates():
    data = request.json or {}
    err = _require(data, "session_id", "dataset")
    if err: return err
    sid, dk = data["session_id"], data["dataset"]
    df = sm.get_working_df(sid, dk)
    if df is None: return jsonify({"error": "Dataset not found."}), 404
    try:
        new_df, entry = ce.remove_duplicates(df, keep=data.get("keep", "first"))
        analysis = _update_and_reanalyze(sid, dk, new_df, entry)
        return jsonify({"success": True, "entry": entry, "new_row_count": len(new_df), "analysis": analysis})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/repair-type", methods=["POST"])
def repair_type():
    data = request.json or {}
    err = _require(data, "session_id", "dataset", "column", "target_type")
    if err: return err
    sid, dk = data["session_id"], data["dataset"]
    df = sm.get_working_df(sid, dk)
    if df is None: return jsonify({"error": "Dataset not found."}), 404
    try:
        new_df, entry = ce.repair_type(df, data["column"], data["target_type"])
        analysis = _update_and_reanalyze(sid, dk, new_df, entry)
        return jsonify({"success": True, "entry": entry, "analysis": analysis})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/preview-type-conversion", methods=["POST"])
def preview_type():
    data = request.json or {}
    err = _require(data, "session_id", "dataset", "column", "target_type")
    if err: return err
    sid, dk = data["session_id"], data["dataset"]
    df = sm.get_working_df(sid, dk)
    if df is None: return jsonify({"error": "Dataset not found."}), 404
    result = preview_type_conversion(df, data["column"], data["target_type"])
    return jsonify(result)


@bp.route("/reset", methods=["POST"])
def reset_working():
    data = request.json or {}
    err = _require(data, "session_id", "dataset")
    if err: return err
    sid, dk = data["session_id"], data["dataset"]
    sm.reset_working(sid, dk)
    orig = sm.get_original_df(sid, dk)
    if orig is not None:
        kept_cells = sm.get_kept_cells(sid, dk)
        fresh_analysis = run_full_analysis(orig, kept_cells=kept_cells)
        sm.set_analysis(sid, dk, fresh_analysis)
    return jsonify({"success": True, "message": "Working dataset reset to original.", "analysis": sm.get_analysis(sid, dk)})


@bp.route("/finalize", methods=["POST"])
def finalize():
    data = request.json or {}
    err = _require(data, "session_id", "dataset")
    if err: return err
    sid, dk = data["session_id"], data["dataset"]
    df = sm.get_working_df(sid, dk)
    if df is None: return jsonify({"error": "Dataset not found."}), 404
    sm.finalize_dataset(sid, dk)
    kept_cells = sm.get_kept_cells(sid, dk)
    fresh_analysis = run_full_analysis(df, kept_cells=kept_cells)
    sm.set_analysis(sid, dk, fresh_analysis)
    return jsonify({"success": True, "message": "Dataset finalized.", "rows": len(df), "cols": len(df.columns), "analysis": sm.get_analysis(sid, dk)})


@bp.route("/resolve-outlier", methods=["POST"])
def resolve_outlier():
    data = request.json or {}
    sid = data.get("session_id")
    dk = data.get("dataset", "single")
    col_name = data.get("column")
    resolution = data.get("resolution")

    if not sid or not col_name or not resolution:
        return jsonify({"error": "session_id, column, and resolution are required."}), 400

    row_indices = data.get("row_indices")
    if row_indices is None:
        raw_idx = data.get("row_index")
        if raw_idx is None:
            return jsonify({"error": "row_index or row_indices is required."}), 400
        row_indices = raw_idx if isinstance(raw_idx, list) else [raw_idx]

    try:
        row_indices = [int(i) for i in row_indices]
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid row index in list."}), 400

    df = sm.get_working_df(sid, dk)
    if df is None: return jsonify({"error": "Dataset not found."}), 404

    try:
        new_df = df.copy()
        all_entries = []
        impute_method = data.get("impute_method")
        manual_value = data.get("manual_value")

        if resolution == "delete_row":
            deleted_rows = []
            for r in sorted(row_indices, reverse=True):
                if r in new_df.index:
                    orig_val = new_df.at[r, col_name]
                    all_entries.append({
                        "action": "DELETE_ROWS",
                        "method": "Outlier removal",
                        "description": f"Deleted row {r} due to outlier value '{orig_val}' in column '{col_name}'",
                        "column": col_name,
                        "row_index": [r],
                        "original_value": orig_val,
                    })
                    deleted_rows.append(r)
            if deleted_rows:
                new_df = new_df.drop(index=deleted_rows)
                sm.adjust_resolved_indices(sid, dk, sorted(deleted_rows))

        elif resolution in ("keep", "leave_unchanged"):
            for r in row_indices:
                if r in new_df.index:
                    orig_val = new_df.at[r, col_name]
                    all_entries.append({
                        "action": "LEAVE_UNCHANGED",
                        "method": "Outlier kept",
                        "description": f"Verified and kept outlier value '{orig_val}' unchanged in [{r}, '{col_name}']",
                        "column": col_name,
                        "row_index": r,
                        "original_value": orig_val,
                        "new_value": orig_val,
                    })
                    sm.add_resolved_outlier(sid, dk, col_name, r, orig_val)

        elif resolution == "correct":
            for r in row_indices:
                if r in new_df.index:
                    sub_df, entry = ce.edit_cell(new_df, r, col_name, manual_value)
                    new_df = sub_df
                    entry["description"] = f"Corrected outlier in [{r}, '{col_name}'] to '{manual_value}'"
                    all_entries.append(entry)
                    sm.add_resolved_outlier(sid, dk, col_name, r, entry.get("original_value"))

        elif resolution in ("replace", "impute"):
            from backend.utils.df_utils import clean_numeric_series, can_be_numeric
            from backend.analysis.missing_analyzer import compute_imputation_value
            method = impute_method or "median_excl_outliers"
            series = clean_numeric_series(new_df[col_name]).copy()
            for r in row_indices:
                if r in series.index:
                    series.at[r] = np.nan
            fill_val, desc = compute_imputation_value(series, method)
            if fill_val is None:
                raise ValueError(f"Could not compute imputation value: {desc}")
            new_df[col_name] = clean_numeric_series(new_df[col_name])

            for r in row_indices:
                if r in new_df.index:
                    orig_val = df.at[r, col_name] if r in df.index else None
                    new_df.at[r, col_name] = fill_val
                    all_entries.append({
                        "action": "FILL_MISSING",
                        "description": f"Replaced outlier in [{r}, '{col_name}'] with {fill_val} using {method}: {desc}",
                        "column": col_name,
                        "row_index": r,
                        "original_value": str(orig_val),
                        "new_value": str(fill_val),
                        "method": method,
                    })
                    sm.add_resolved_outlier(sid, dk, col_name, r, orig_val)
        else:
            return jsonify({"error": f"Unknown resolution '{resolution}'."}), 400

        if all_entries:
            filtered_analysis = _update_and_reanalyze(sid, dk, new_df, all_entries)
        else:
            filtered_analysis = sm.get_analysis(sid, dk)

        return jsonify({"success": True, "entries": all_entries, "analysis": filtered_analysis})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 400

@bp.route("/history", methods=["GET"])
def get_history():
    sid = request.args.get("session_id")
    dk = request.args.get("dataset", "single")
    if not sid: return jsonify({"error": "session_id required."}), 400
    history = sm.get_history(sid, dk)
    return jsonify({"history": history, "count": len(history)})


@bp.route("/delete-missing-rows", methods=["POST"])
def delete_missing_rows():
    """Delete all rows that contain at least one missing value."""
    data = request.json or {}
    err = _require(data, "session_id", "dataset")
    if err: return err
    sid, dk = data["session_id"], data["dataset"]
    df = sm.get_working_df(sid, dk)
    if df is None: return jsonify({"error": "Dataset not found."}), 404
    try:
        from backend.utils.df_utils import get_missing_mask
        # Find any row with at least one missing value
        any_missing = get_missing_mask(df).any(axis=1)
        missing_indices = [int(i) for i in df[any_missing].index.tolist()]
        if not missing_indices:
            return jsonify({"error": "No rows with missing values found."}), 400
        new_df, entry = ce.delete_rows(df, missing_indices)
        sm.adjust_resolved_indices(sid, dk, missing_indices)
        entry["action"] = "DELETE_MISSING_ROWS"
        entry["description"] = f"Deleted {len(missing_indices)} row(s) that had at least one missing value."
        analysis = _update_and_reanalyze(sid, dk, new_df, entry)
        return jsonify({"success": True, "entry": entry, "deleted_count": len(missing_indices), "new_row_count": len(new_df), "analysis": analysis})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/delete-column-missing-rows", methods=["POST"])
def delete_column_missing_rows():
    """Delete every row where the specified column has a missing value."""
    data = request.json or {}
    err = _require(data, "session_id", "dataset", "column")
    if err: return err
    sid, dk = data["session_id"], data["dataset"]
    column = data["column"]
    df = sm.get_working_df(sid, dk)
    if df is None: return jsonify({"error": "Dataset not found."}), 404
    try:
        new_df, entry = ce.delete_column_missing_rows(df, column)
        sm.adjust_resolved_indices(sid, dk, entry.get("affected_rows", []))
        analysis = _update_and_reanalyze(sid, dk, new_df, entry)
        return jsonify({"success": True, "entry": entry, "deleted_count": entry.get("count", 0), "new_row_count": len(new_df), "analysis": analysis})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/resolve-suspicious", methods=["POST"])
def resolve_suspicious():
    data = request.json or {}
    sid = data.get("session_id")
    dk = data.get("dataset", "single")
    col_name = data.get("column")
    resolution = data.get("resolution")

    if not sid or not col_name or not resolution:
        return jsonify({"error": "session_id, column, and resolution are required."}), 400

    row_indices = data.get("row_indices")
    if row_indices is None:
        raw_idx = data.get("row_index")
        if raw_idx is None:
            return jsonify({"error": "row_index or row_indices is required."}), 400
        row_indices = raw_idx if isinstance(raw_idx, list) else [raw_idx]

    try:
        row_indices = [int(i) for i in row_indices]
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid row index in list."}), 400

    df = sm.get_working_df(sid, dk)
    if df is None: return jsonify({"error": "Dataset not found."}), 404

    try:
        new_df = df.copy()
        all_entries = []
        impute_method = data.get("impute_method")
        manual_value = data.get("manual_value")

        if resolution == "delete_row":
            deleted_rows = []
            for r in sorted(row_indices, reverse=True):
                if r in new_df.index:
                    orig_val = new_df.at[r, col_name]
                    all_entries.append({
                        "action": "DELETE_ROWS",
                        "method": "Suspicious value removal",
                        "description": f"Deleted row {r} due to suspicious value '{orig_val}' in column '{col_name}'",
                        "column": col_name,
                        "row_index": [r],
                        "original_value": orig_val,
                    })
                    deleted_rows.append(r)
            if deleted_rows:
                new_df = new_df.drop(index=deleted_rows)
                sm.adjust_resolved_indices(sid, dk, sorted(deleted_rows))
            for r in row_indices:
                sm.add_resolved_suspicious(sid, dk, col_name, r, None)

        elif resolution in ("keep", "leave_unchanged"):
            for r in row_indices:
                if r in new_df.index:
                    orig_val = new_df.at[r, col_name]
                    all_entries.append({
                        "action": "LEAVE_UNCHANGED",
                        "method": "User decision: Keep",
                        "description": f"Verified and kept suspicious value '{orig_val}' in [{r}, '{col_name}']",
                        "column": col_name,
                        "row_index": r,
                        "original_value": orig_val,
                        "new_value": orig_val,
                    })
                    sm.add_resolved_suspicious(sid, dk, col_name, r, orig_val)

        elif resolution in ("correct", "manual"):
            for r in row_indices:
                if r in new_df.index:
                    sub_df, entry = ce.edit_cell(new_df, r, col_name, manual_value)
                    new_df = sub_df
                    entry["action"] = "CORRECT_VALUE"
                    entry["description"] = f"Corrected suspicious value in [{r}, '{col_name}']: '{entry.get('original_value')}' → '{manual_value}'"
                    all_entries.append(entry)
                    sm.add_resolved_suspicious(sid, dk, col_name, r, entry.get("original_value"))

        elif resolution in ("replace", "impute"):
            from backend.utils.df_utils import clean_numeric_series, can_be_numeric
            from backend.analysis.missing_analyzer import compute_imputation_value
            is_num = can_be_numeric(new_df[col_name])
            method = impute_method or ("median_excl_outliers" if is_num else "mode")
            if is_num:
                series = clean_numeric_series(new_df[col_name]).copy()
                for r in row_indices:
                    if r in series.index:
                        series.at[r] = np.nan
                fill_val, desc = compute_imputation_value(series, method)
                if fill_val is None:
                    raise ValueError(f"Could not compute imputation value: {desc}")
                new_df[col_name] = clean_numeric_series(new_df[col_name])
            else:
                series = new_df[col_name].copy()
                for r in row_indices:
                    if r in series.index:
                        series.at[r] = np.nan
                fill_val, desc = compute_imputation_value(series, "mode")
                if fill_val is None:
                    raise ValueError(f"Could not compute mode: {desc}")

            for r in row_indices:
                if r in new_df.index:
                    orig_val = df.at[r, col_name] if r in df.index else None
                    new_df.at[r, col_name] = fill_val
                    all_entries.append({
                        "action": "REPLACE_SUSPICIOUS",
                        "description": f"Replaced suspicious value '{orig_val}' in [{r}, '{col_name}'] using {method}: {fill_val}",
                        "column": col_name,
                        "row_index": r,
                        "original_value": orig_val,
                        "new_value": str(fill_val),
                        "method": method,
                    })
                    sm.add_resolved_suspicious(sid, dk, col_name, r, orig_val)
        else:
            return jsonify({"error": f"Unknown suspicious resolution '{resolution}'."}), 400

        if all_entries:
            fresh_analysis = _update_and_reanalyze(sid, dk, new_df, all_entries)
        else:
            fresh_analysis = sm.get_analysis(sid, dk)

        return jsonify({"success": True, "entries": all_entries, "analysis": fresh_analysis})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 400


@bp.route("/type-issue-rows", methods=["POST"])
def type_issue_rows():
    """Fetch specific affected rows for a column with data type issues."""
    data = request.json or {}
    err = _require(data, "session_id", "dataset", "column")
    if err: return err
    sid, dk = data["session_id"], data["dataset"]
    column = data["column"]
    df = sm.get_working_df(sid, dk)
    if df is None: return jsonify({"error": "Dataset not found."}), 404
    if column not in df.columns: return jsonify({"error": f"Column '{column}' not found."}), 404

    kept_cells = sm.get_kept_cells(sid, dk)
    from backend.analysis.type_analyzer import get_type_affected_rows
    res = get_type_affected_rows(df, column, kept_cells)

    page = int(data.get("page", 0))
    page_size = int(data.get("page_size", 25))
    all_rows = res.get("affected_rows", [])
    total = len(all_rows)
    start = page * page_size
    paged_rows = all_rows[start : start + page_size]

    return jsonify({
        "column": res.get("column"),
        "current_dtype": res.get("current_dtype"),
        "col_category": res.get("col_category"),
        "proposed_target": res.get("proposed_target"),
        "total_affected": total,
        "rows": paged_rows,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "all_problem_indices": res.get("all_problem_indices", []),
        "unconvertible_indices": res.get("unconvertible_indices", []),
        "clean_count": res.get("clean_count", 0),
        "unconvertible_count": res.get("unconvertible_count", 0),
        "decimal_loss_count": res.get("decimal_loss_count", 0),
        "total_values": res.get("total_values", 0),
        "has_missing": res.get("has_missing", False),
        "summary": res.get("summary", ""),
    })


@bp.route("/resolve-type-rows", methods=["POST"])
def resolve_type_rows():
    """Resolve specific row values or whole column for data-type issues."""
    data = request.json or {}
    err = _require(data, "session_id", "dataset", "column", "action")
    if err: return err
    sid, dk = data["session_id"], data["dataset"]
    column = data["column"]
    action = data["action"]

    df = sm.get_working_df(sid, dk)
    if df is None: return jsonify({"error": "Dataset not found."}), 404
    if column not in df.columns: return jsonify({"error": f"Column '{column}' not found."}), 404

    try:
        new_df = df.copy()
        all_entries = []
        row_indices = data.get("row_indices", [])
        if not isinstance(row_indices, list):
            row_indices = [row_indices]
        row_indices = [int(i) for i in row_indices]

        # 1. Whole column conversion in one action across ALL rows
        if action in ("convert_column", "convert_whole_column", "convert_all_int", "convert_all_float") or (action == "convert" and not row_indices):
            target = data.get("target_type")
            if not target:
                target = "int64" if action == "convert_all_int" else ("float64" if action == "convert_all_float" else "int64")

            from backend.utils.df_utils import get_missing_mask, clean_numeric_series, round_half_up
            has_missing = get_missing_mask(new_df[column]).any()
            if target in ("int", "int64", "integer"):
                target = "Int64" if has_missing else "int64"

            orig_series = new_df[column].copy()

            if target in ("int64", "Int64", "integer"):
                cleaned = clean_numeric_series(new_df[column])
                coerced = pd.to_numeric(cleaned, errors="coerce")
                new_series = coerced.apply(lambda v: round_half_up(v) if pd.notna(v) else pd.NA).astype("Int64")
                new_df[column] = new_series
            elif target in ("float64", "float", "numeric"):
                cleaned = clean_numeric_series(new_df[column])
                new_series = pd.to_numeric(cleaned, errors="coerce").astype(float)
                new_df[column] = new_series
            elif target in ("datetime64", "date"):
                new_series = pd.to_datetime(new_df[column], errors="coerce")
                new_df[column] = new_series
            elif target in ("boolean", "bool"):
                b_s = new_df[column].map(lambda x: True if str(x).lower() in ("true", "1", "yes", "y", "t") else (False if str(x).lower() in ("false", "0", "no", "n", "f") else pd.NA))
                new_df[column] = b_s.astype("boolean")
            else:
                new_df, _ = ce.repair_type(new_df, column, target)

            # Log each changed row in Change History
            for idx in orig_series.index:
                old_val = orig_series.loc[idx]
                new_val = new_df.loc[idx, column]
                if pd.isna(old_val) and pd.isna(new_val):
                    continue
                if str(old_val).strip() != str(new_val).strip():
                    all_entries.append({
                        "action": "CONVERT_ROW_TYPE",
                        "method": f"Column converted to {target}",
                        "description": f"Converted [{idx}, '{column}']: '{old_val}' → '{new_val}'",
                        "column": column,
                        "row_index": int(idx),
                        "original_value": str(old_val) if pd.notna(old_val) else "",
                        "new_value": str(new_val) if pd.notna(new_val) else "",
                    })

            # Also log summary entry
            all_entries.append({
                "action": "REPAIR_TYPE",
                "method": "Type conversion",
                "description": f"Converted whole column '{column}' to {target}.",
                "column": column,
                "original_value": str(orig_series.dtype),
                "new_value": target,
            })

        else:
            if action == "convert":
                from backend.utils.df_utils import round_half_up, get_missing_mask
                target = data.get("target_type", "int64")
                has_missing = get_missing_mask(new_df[column]).any()
                if target in ("int", "int64", "integer") and has_missing:
                    target = "Int64"

                new_df[column] = new_df[column].astype(object)
                for r in row_indices:
                    if r in new_df.index:
                        orig = new_df.at[r, column]
                        if target in ("int64", "Int64"):
                            try:
                                val_num = float(str(orig).replace("$", "").replace(",", "").strip())
                                converted_val = round_half_up(val_num)
                                new_df.at[r, column] = converted_val
                            except Exception:
                                pass
                        elif target == "float64":
                            try:
                                val_num = float(str(orig).replace("$", "").replace(",", "").strip())
                                new_df.at[r, column] = val_num
                            except Exception:
                                pass
                        elif target == "datetime64":
                            try:
                                new_df.at[r, column] = pd.to_datetime(orig)
                            except Exception:
                                pass
                        elif target == "boolean":
                            try:
                                s_lower = str(orig).strip().lower()
                                if s_lower in ("true", "1", "yes", "y", "t"):
                                    new_df.at[r, column] = True
                                elif s_lower in ("false", "0", "no", "n", "f"):
                                    new_df.at[r, column] = False
                            except Exception:
                                pass
                        all_entries.append({
                            "action": "CONVERT_ROW_TYPE",
                            "method": f"Row converted to {target} (round-half-up)",
                            "description": f"Converted [{r}, '{column}']: '{orig}' → '{new_df.at[r, column]}'",
                            "column": column,
                            "row_index": r,
                            "original_value": str(orig) if orig is not None else "",
                            "new_value": str(new_df.at[r, column]),
                        })

                # If all remaining non-null values can cleanly cast to the target type, cast the whole column series
                try:
                    if target == "datetime64":
                        new_df[column] = pd.to_datetime(new_df[column], errors="coerce")
                    elif target in ("int64", "Int64"):
                        num_s = pd.to_numeric(new_df[column], errors="coerce")
                        if (num_s.dropna() % 1 == 0).all():
                            new_df[column] = num_s.astype("Int64")
                    elif target == "float64":
                        new_df[column] = pd.to_numeric(new_df[column], errors="coerce").astype(float)
                    elif target == "boolean":
                        b_s = new_df[column].map(lambda x: True if str(x).lower() in ("true", "1", "yes", "y", "t") else (False if str(x).lower() in ("false", "0", "no", "n", "f") else x))
                        if b_s.dropna().isin([True, False]).all():
                            new_df[column] = b_s.astype("boolean")
                except Exception:
                    pass

            elif action == "edit":
                manual_value = data.get("manual_value")
                for r in row_indices:
                    if r in new_df.index:
                        new_df, entry = ce.edit_cell(new_df, r, column, manual_value)
                        all_entries.append(entry)

            elif action in ("delete_row", "delete_unconvertible"):
                deleted_rows = [r for r in row_indices if r in new_df.index]
                if deleted_rows:
                    for r in deleted_rows:
                        orig = new_df.at[r, column]
                        all_entries.append({
                            "action": "DELETE_ROWS",
                            "method": "Type issue resolution",
                            "description": f"Deleted row {r} with invalid type value '{orig}' in '{column}'",
                            "column": column,
                            "row_index": r,
                            "original_value": str(orig) if orig is not None else "",
                        })
                    new_df = new_df.drop(index=deleted_rows)
                    sm.adjust_resolved_indices(sid, dk, sorted(deleted_rows))

                    target = data.get("target_type")
                    if target:
                        try:
                            if target == "datetime64":
                                new_df[column] = pd.to_datetime(new_df[column], errors="coerce")
                            elif target in ("int64", "Int64"):
                                num_s = pd.to_numeric(new_df[column], errors="coerce")
                                if (num_s.dropna() % 1 == 0).all():
                                    new_df[column] = num_s.astype("Int64")
                            elif target == "float64":
                                new_df[column] = pd.to_numeric(new_df[column], errors="coerce").astype(float)
                            elif target == "boolean":
                                b_s = new_df[column].map(lambda x: True if str(x).lower() in ("true", "1", "yes", "y", "t") else (False if str(x).lower() in ("false", "0", "no", "n", "f") else x))
                                if b_s.dropna().isin([True, False]).all():
                                    new_df[column] = b_s.astype("boolean")
                        except Exception:
                            pass

            elif action in ("keep", "leave_unchanged"):
                for r in row_indices:
                    if r in new_df.index:
                        orig = new_df.at[r, column]
                        sm.add_kept_cell(sid, dk, r, column)
                        all_entries.append({
                            "action": "LEAVE_UNCHANGED",
                            "method": "User decision: Keep",
                            "description": f"Verified and kept value '{orig}' in [{r}, '{column}']",
                            "column": column,
                            "row_index": r,
                            "original_value": str(orig),
                            "new_value": str(orig),
                        })
            else:
                return jsonify({"error": f"Unknown action '{action}'."}), 400

        analysis = _update_and_reanalyze(sid, dk, new_df, all_entries)
        return jsonify({"success": True, "entries": all_entries, "analysis": analysis})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 400


