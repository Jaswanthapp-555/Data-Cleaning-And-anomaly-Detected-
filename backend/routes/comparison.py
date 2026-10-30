"""Comparison routes."""
from flask import Blueprint, request, jsonify
from backend.services import session_manager as sm
from backend.comparison.comparison_engine import compare_datasets
from backend.analysis import run_full_analysis

bp = Blueprint("comparison", __name__, url_prefix="/api/compare")


@bp.route("/run", methods=["POST"])
def run_comparison():
    data = request.json or {}
    sid = data.get("session_id")
    if not sid: return jsonify({"error": "session_id required."}), 400

    ref_df = sm.get_finalized_df(sid, "ref")
    cur_df = sm.get_finalized_df(sid, "cur")

    if ref_df is None:
        return jsonify({"error": "Reference dataset is not finalized yet."}), 400
    if cur_df is None:
        return jsonify({"error": "Current dataset is not finalized yet."}), 400

    ref_analysis = sm.get_analysis(sid, "ref")
    cur_analysis = sm.get_analysis(sid, "cur")

    # Run fresh analysis on finalized datasets if needed
    if ref_analysis is None:
        ref_analysis = run_full_analysis(ref_df)
        sm.set_analysis(sid, "ref", ref_analysis)
    if cur_analysis is None:
        cur_analysis = run_full_analysis(cur_df)
        sm.set_analysis(sid, "cur", cur_analysis)

    try:
        result = compare_datasets(ref_df, cur_df, ref_analysis, cur_analysis)
        sm.set_comparison(sid, result)
        return jsonify({"comparison": result})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@bp.route("/preview", methods=["POST"])
def preview_comparison():
    """Compare current WORKING datasets (not requiring finalization) for preview mode."""
    data = request.json or {}
    sid = data.get("session_id")
    if not sid: return jsonify({"error": "session_id required."}), 400

    ref_df = sm.get_working_df(sid, "ref")
    cur_df = sm.get_working_df(sid, "cur")

    if ref_df is None:
        return jsonify({"error": "Reference dataset not uploaded yet."}), 400
    if cur_df is None:
        return jsonify({"error": "Current dataset not uploaded yet."}), 400

    ref_analysis = sm.get_analysis(sid, "ref") or run_full_analysis(ref_df)
    cur_analysis = sm.get_analysis(sid, "cur") or run_full_analysis(cur_df)

    try:
        result = compare_datasets(ref_df, cur_df, ref_analysis, cur_analysis)
        return jsonify({"comparison": result, "is_preview": True})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@bp.route("/result", methods=["GET"])
def get_comparison():
    sid = request.args.get("session_id")
    if not sid: return jsonify({"error": "session_id required."}), 400
    result = sm.get_comparison(sid)
    if result is None:
        return jsonify({"error": "No comparison available. Run /api/compare/run first."}), 404
    return jsonify({"comparison": result})
