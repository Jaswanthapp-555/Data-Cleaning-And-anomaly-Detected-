"""Upload routes for CSV and Excel files (No Database)."""
import os
import uuid
from flask import Blueprint, request, jsonify, current_app
from backend.services import session_manager as sm
from backend.services.file_handler import (
    read_csv, read_excel_sheets, read_excel_sheet
)
from backend.utils.validators import allowed_file, safe_filename

bp = Blueprint("upload", __name__, url_prefix="/api")


def _get_session_id():
    sid = request.headers.get("X-Session-Id") or request.args.get("session_id") or (request.form.get("session_id") if request.form else None)
    if request.is_json and request.json:
        sid = sid or request.json.get("session_id")
    if not sid or not sm.get_session(sid):
        sid = sm.new_session()
    return sid


@bp.route("/session/new", methods=["POST"])
def new_session():
    sid = sm.new_session()
    return jsonify({"session_id": sid})


@bp.route("/upload/file", methods=["POST"])
def upload_file():
    """Single unified file upload endpoint for CSV and Excel."""
    sid = _get_session_id()
    dataset_key = request.form.get("dataset", "single")

    if "file" not in request.files:
        return jsonify({"error": "No file provided in request."}), 400

    file = request.files["file"]
    if not file or not file.filename:
        return jsonify({"error": "No file selected."}), 400

    filename = safe_filename(file.filename)
    if not allowed_file(filename):
        return jsonify({"error": f"Unsupported file format '{filename}'. Supported formats: CSV, XLSX, XLS."}), 400

    try:
        file_bytes = file.read()
        if len(file_bytes) == 0:
            return jsonify({"error": "The uploaded file is empty (0 bytes)."}), 400

        ext = filename.rsplit(".", 1)[1].lower()
        size_mb = round(len(file_bytes) / (1024 * 1024), 2)

        if ext == "csv":
            df = read_csv(file_bytes)
            if len(df) == 0:
                return jsonify({"error": "The CSV file contains no data rows."}), 400

            source_info = {
                "type": "csv",
                "filename": filename,
                "size_mb": size_mb,
                "rows": len(df),
                "cols": len(df.columns),
            }
            sm.set_original(sid, dataset_key, df, source_info)
            from backend.analysis import run_full_analysis
            analysis_res = run_full_analysis(df)
            sm.set_analysis(sid, dataset_key, analysis_res)
            sm.set_original_analysis(sid, dataset_key, analysis_res)

            return jsonify({
                "session_id": sid,
                "dataset": dataset_key,
                "file_type": "csv",
                "source_info": source_info,
                "columns": list(df.columns),
                "dtypes": {c: str(df[c].dtype) for c in df.columns},
                "analysis": analysis_res,
                "preview": _preview(df),
            })
        else:
            # Excel file — return sheet list
            sheets = read_excel_sheets(file_bytes)
            if not sheets:
                return jsonify({"error": "No worksheets found in this Excel file."}), 400

            # Save excel bytes into session for subsequent sheet loading
            sess = sm.get_session(sid)
            sess[f"_excel_bytes_{dataset_key}"] = file_bytes
            sess[f"_excel_filename_{dataset_key}"] = filename
            sess[f"_excel_sizemb_{dataset_key}"] = size_mb
            sm.set_session(sid, sess)

            return jsonify({
                "session_id": sid,
                "dataset": dataset_key,
                "file_type": "excel",
                "filename": filename,
                "size_mb": size_mb,
                "sheets": sheets,
            })

    except Exception as e:
        current_app.logger.exception("File upload error")
        return jsonify({"error": f"Unable to parse file: {str(e)}"}), 400


@bp.route("/upload/excel/load", methods=["POST"])
def load_excel_sheet():
    """Load a specific sheet from a previously uploaded Excel workbook."""
    data = request.json or {}
    sid = data.get("session_id") or _get_session_id()
    dataset_key = data.get("dataset", "single")
    sheet = data.get("sheet")

    if not sheet:
        return jsonify({"error": "Sheet name is required."}), 400

    sess = sm.get_session(sid)
    bytes_key = f"_excel_bytes_{dataset_key}"
    if not sess or bytes_key not in sess:
        return jsonify({"error": "Excel file data not found in session. Please re-upload the file."}), 400

    try:
        file_bytes = sess[bytes_key]
        filename = sess.get(f"_excel_filename_{dataset_key}", "workbook.xlsx")
        size_mb = sess.get(f"_excel_sizemb_{dataset_key}", 0)

        df = read_excel_sheet(file_bytes, sheet)
        if len(df) == 0:
            return jsonify({"error": f"Worksheet '{sheet}' contains no data rows."}), 400

        source_info = {
            "type": "excel",
            "filename": filename,
            "sheet": sheet,
            "size_mb": size_mb,
            "rows": len(df),
            "cols": len(df.columns),
        }
        sm.set_original(sid, dataset_key, df, source_info)

        from backend.analysis import run_full_analysis
        analysis_res = run_full_analysis(df)
        sm.set_analysis(sid, dataset_key, analysis_res)
        sm.set_original_analysis(sid, dataset_key, analysis_res)

        return jsonify({
            "session_id": sid,
            "dataset": dataset_key,
            "file_type": "excel",
            "source_info": source_info,
            "columns": list(df.columns),
            "dtypes": {c: str(df[c].dtype) for c in df.columns},
            "analysis": analysis_res,
            "preview": _preview(df),
        })
    except Exception as e:
        return jsonify({"error": f"Unable to load sheet '{sheet}': {str(e)}"}), 400


def _preview(df, n=10):
    from backend.utils.df_utils import df_to_records
    return df_to_records(df, max_rows=n)
