"""Visualization routes."""
import io
import json
from flask import Blueprint, request, jsonify, send_file
from backend.services import session_manager as sm
from backend.visualization.chart_builder import build_chart, get_available_charts, build_dataset_overview

bp = Blueprint("visualization", __name__, url_prefix="/api/viz")


@bp.route("/available", methods=["GET"])
def available_charts():
    sid = request.args.get("session_id")
    dk = request.args.get("dataset", "single")
    if not sid: return jsonify({"error": "session_id required."}), 400
    df = sm.get_working_df(sid, dk)
    if df is None: return jsonify({"error": "Dataset not found."}), 404
    return jsonify(get_available_charts(df))


@bp.route("/overview", methods=["GET"])
@bp.route("/dataset-overview", methods=["GET"])
def dataset_overview():
    sid = request.args.get("session_id")
    dk = request.args.get("dataset", "single")
    which = request.args.get("which", "working")
    if not sid: return jsonify({"error": "session_id required."}), 400

    if which == "original":
        df = sm.get_original_df(sid, dk)
        state_label = "Original Dataset"
    elif which == "finalized":
        df = sm.get_finalized_df(sid, dk)
        state_label = "Finalized Dataset"
    else:
        df = sm.get_working_df(sid, dk)
        ds = sm.get_session(sid)
        ds_state = ds.get(dk, {}).get("state", "working") if ds else "working"
        state_label = "Current Working Dataset" if ds_state != "finalized" else "Finalized Dataset"

    if df is None: return jsonify({"error": "Dataset not found."}), 404

    overview_data = build_dataset_overview(df)
    overview_data["state_label"] = state_label
    overview_data["which"] = which
    overview_data["dataset"] = dk
    return jsonify(overview_data)


@bp.route("/generate", methods=["POST"])
def generate():
    data = request.json or {}
    sid = data.get("session_id")
    dk = data.get("dataset", "single")
    chart_type = data.get("chart_type")
    config = data.get("config", {})
    which = data.get("which", "working")

    if not sid: return jsonify({"error": "session_id required."}), 400
    if not chart_type: return jsonify({"error": "chart_type required."}), 400

    if which == "original":
        df = sm.get_original_df(sid, dk)
        state_label = "Original Dataset"
    elif which == "finalized":
        df = sm.get_finalized_df(sid, dk)
        state_label = "Finalized Dataset"
    else:
        df = sm.get_working_df(sid, dk)
        ds = sm.get_session(sid)
        ds_state = ds.get(dk, {}).get("state", "working") if ds else "working"
        state_label = "Current Working Dataset" if ds_state != "finalized" else "Finalized Dataset"

    if df is None: return jsonify({"error": "Dataset not found."}), 404

    # For comparison charts, pass ref/cur data
    if chart_type in ("comparison_histogram", "comparison_boxplot"):
        col = config.get("col")
        if not col: return jsonify({"error": "col required for comparison charts."}), 400
        ref_df = sm.get_finalized_df(sid, "ref")
        cur_df = sm.get_finalized_df(sid, "cur")
        if ref_df is None or cur_df is None:
            return jsonify({"error": "Both datasets must be finalized for comparison charts."}), 400
        if col not in ref_df.columns or col not in cur_df.columns:
            return jsonify({"error": f"Column '{col}' not in both datasets."}), 400
        config["ref_data"] = ref_df[col].dropna().tolist()
        config["cur_data"] = cur_df[col].dropna().tolist()
        df = ref_df  # Used for type checking only

    result = build_chart(df, chart_type, config)
    if "error" in result:
        return jsonify(result), 400

    result["state_label"] = state_label
    result["chart_type"] = chart_type
    return jsonify(result)
