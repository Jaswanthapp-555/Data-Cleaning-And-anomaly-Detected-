"""Report and download routes."""
import io
from flask import Blueprint, request, jsonify, send_file, Response
from backend.services import session_manager as sm
from backend.reports.report_builder import build_single_report, build_comparison_report, build_analysis_only_report
from backend.reports.html_renderer import render_html_report
from backend.reports.pdf_renderer import render_pdf_report
from backend.analysis import run_full_analysis

bp = Blueprint("reports", __name__, url_prefix="/api")


@bp.route("/report/html", methods=["POST"])
def html_report():
    data = request.json or {}
    sid = data.get("session_id")
    mode = data.get("mode", "single")
    report_type = data.get("report_type", "analysis")  # analysis | comparison
    if not sid: return jsonify({"error": "session_id required."}), 400

    try:
        report_data = _build_report_data(sid, mode, report_type)
        html = render_html_report(report_data)
        filename = _report_filename(mode, report_type, "html")
        return Response(html, mimetype="text/html",
                        headers={"Content-Disposition": f"attachment; filename={filename}"})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": _clean_error_message(e)}), 500


@bp.route("/report/pdf", methods=["POST"])
def pdf_report():
    data = request.json or {}
    sid = data.get("session_id")
    mode = data.get("mode", "single")
    report_type = data.get("report_type", "analysis")
    if not sid: return jsonify({"error": "session_id required."}), 400

    try:
        report_data = _build_report_data(sid, mode, report_type)
        html = render_html_report(report_data)
        pdf_bytes = render_pdf_report(html)
        if not pdf_bytes or not pdf_bytes.startswith(b"%PDF"):
            raise ValueError("Failed to generate a valid PDF byte stream.")
        filename = _report_filename(mode, report_type, "pdf")
        resp = send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )
        resp.headers["Content-Type"] = "application/pdf"
        resp.headers["Content-Length"] = str(len(pdf_bytes))
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return resp
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": _clean_error_message(e)}), 500


@bp.route("/download/dataset", methods=["GET"])
def download_dataset():
    sid = request.args.get("session_id")
    dk = request.args.get("dataset", "single")
    if not sid: return jsonify({"error": "session_id required."}), 400

    df = sm.get_finalized_df(sid, dk)
    if df is None:
        df = sm.get_working_df(sid, dk)
    if df is None:
        return jsonify({"error": "Dataset not found."}), 404

    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=cleaned_dataset_{dk}.csv"}
    )


@bp.route("/download/missing-log", methods=["GET"])
def download_missing_log():
    sid = request.args.get("session_id")
    dk = request.args.get("dataset", "single")
    if not sid: return jsonify({"error": "session_id required."}), 400

    orig_df = sm.get_original_df(sid, dk)
    if orig_df is None:
        return jsonify({"error": "Original dataset not found."}), 404

    final_df = sm.get_finalized_df(sid, dk)
    if final_df is None:
        final_df = sm.get_working_df(sid, dk)
    if final_df is None:
        final_df = orig_df

    history = sm.get_history(sid, dk)
    from backend.reports.missing_log import export_missing_values_log_bytes
    
    excel_bytes = export_missing_values_log_bytes(orig_df, final_df, history, dataset_name=dk)
    filename = f"missing_values_log_{dk}.xlsx"
    return Response(
        excel_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


def _report_filename(mode, report_type, ext):
    if report_type in ("comparison", "compare"):
        return f"comparison_report.{ext}"
    elif report_type in ("reference", "ref"):
        return f"reference_dataset_report.{ext}"
    elif report_type in ("current", "cur"):
        return f"current_dataset_report.{ext}"
    elif mode in ("compare", "comparison") and report_type == "analysis":
        return f"analysis_report.{ext}"
    return f"data_quality_report.{ext}"


def _clean_error_message(e: Exception) -> str:
    msg = str(e)
    if "truth value of a DataFrame" in msg or "ambiguous" in msg:
        return "Failed to process dataset state. Please ensure the dataset is properly loaded."
    if "traceback" in msg.lower() or "syntaxerror" in msg.lower():
        return "An internal error occurred while generating the report. Please try again."
    if isinstance(e, ValueError):
        return msg
    return "Failed to generate report. Please verify your dataset and try again."


def _build_report_data(sid, mode, report_type="analysis"):
    sess = sm.get_session(sid)
    if not sess:
        raise ValueError("Session not found.")

    # (a) Standalone Reference Dataset Report (same structure as Single Dataset report)
    if report_type in ("reference", "ref"):
        ref_orig = sm.get_original_df(sid, "ref")
        ref_final = sm.get_finalized_df(sid, "ref")
        if ref_final is None:
            ref_final = sm.get_working_df(sid, "ref")
        if ref_orig is None and ref_final is None:
            raise ValueError("Reference dataset has not been uploaded.")
        analysis_before = _get_analysis_before(sid, "ref", ref_orig)
        analysis_after = _get_analysis_after(sid, "ref", ref_final)
        return build_single_report(
            ds_key="ref",
            source_info=sess.get("ref", {}).get("source_info", {}),
            df_original=ref_orig,
            df_final=ref_final,
            analysis_before=analysis_before,
            analysis_after=analysis_after,
            change_history=sm.get_history(sid, "ref"),
            dataset_label="Reference Dataset",
        )

    # (b) Standalone Current Dataset Report (same structure as Single Dataset report)
    if report_type in ("current", "cur"):
        cur_orig = sm.get_original_df(sid, "cur")
        cur_final = sm.get_finalized_df(sid, "cur")
        if cur_final is None:
            cur_final = sm.get_working_df(sid, "cur")
        if cur_orig is None and cur_final is None:
            raise ValueError("Current dataset has not been uploaded.")
        analysis_before = _get_analysis_before(sid, "cur", cur_orig)
        analysis_after = _get_analysis_after(sid, "cur", cur_final)
        return build_single_report(
            ds_key="cur",
            source_info=sess.get("cur", {}).get("source_info", {}),
            df_original=cur_orig,
            df_final=cur_final,
            analysis_before=analysis_before,
            analysis_after=analysis_after,
            change_history=sm.get_history(sid, "cur"),
            dataset_label="Current Dataset",
        )

    # (c) Comparison Report (only comparison findings between finalized Ref & Cur)
    if mode in ("compare", "comparison") or report_type in ("comparison", "compare"):
        ref_orig = sm.get_original_df(sid, "ref")
        cur_orig = sm.get_original_df(sid, "cur")
        ref_final = sm.get_finalized_df(sid, "ref")
        cur_final = sm.get_finalized_df(sid, "cur")

        # For comparison report, finalized is preferred; fallback to working
        if ref_final is None:
            ref_final = sm.get_working_df(sid, "ref")
        if cur_final is None:
            cur_final = sm.get_working_df(sid, "cur")

        if ref_final is None or cur_final is None:
            raise ValueError("Both Reference and Current datasets must be uploaded before generating a comparison report.")

        ref_analysis_before = _get_analysis_before(sid, "ref", ref_orig)
        ref_analysis_after = _get_analysis_after(sid, "ref", ref_final)
        cur_analysis_before = _get_analysis_before(sid, "cur", cur_orig)
        cur_analysis_after = _get_analysis_after(sid, "cur", cur_final)

        comparison = sm.get_comparison(sid)
        if comparison is None:
            from backend.comparison.comparison_engine import compare_datasets
            comparison = compare_datasets(ref_final, cur_final, ref_analysis_after, cur_analysis_after)
            sm.set_comparison(sid, comparison)

        return build_comparison_report(
            ref_source=sess.get("ref", {}).get("source_info", {}),
            cur_source=sess.get("cur", {}).get("source_info", {}),
            ref_df_orig=ref_orig, cur_df_orig=cur_orig,
            ref_df_final=ref_final, cur_df_final=cur_final,
            ref_analysis_before=ref_analysis_before,
            ref_analysis_after=ref_analysis_after,
            cur_analysis_before=cur_analysis_before,
            cur_analysis_after=cur_analysis_after,
            ref_history=sm.get_history(sid, "ref"),
            cur_history=sm.get_history(sid, "cur"),
            comparison_result=comparison,
        )

    # Single dataset mode report
    orig_df = sm.get_original_df(sid, "single")
    final_df = sm.get_finalized_df(sid, "single")
    if final_df is None:
        final_df = sm.get_working_df(sid, "single")
    if final_df is None:
        raise ValueError("No dataset available.")

    analysis_before = _get_analysis_before(sid, "single", orig_df)
    analysis_after = _get_analysis_after(sid, "single", final_df)

    return build_single_report(
        ds_key="single",
        source_info=sess.get("single", {}).get("source_info", {}),
        df_original=orig_df,
        df_final=final_df,
        analysis_before=analysis_before,
        analysis_after=analysis_after,
        change_history=sm.get_history(sid, "single"),
    )


def _get_analysis_before(sid, dk, orig_df):
    a = sm.get_original_analysis(sid, dk)
    if a is None and orig_df is not None:
        a = run_full_analysis(orig_df)
        sm.set_original_analysis(sid, dk, a)
    return a


def _get_analysis_after(sid, dk, final_df):
    working_df = sm.get_working_df(sid, dk)
    if final_df is not None and working_df is not None and len(final_df) == len(working_df) and list(final_df.columns) == list(working_df.columns):
        a = sm.get_analysis(sid, dk)
        if a is not None:
            return a
    if final_df is not None:
        return run_full_analysis(final_df)
    return None
