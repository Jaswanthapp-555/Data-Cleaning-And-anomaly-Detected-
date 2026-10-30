"""Report data model builder — single authoritative source for HTML and PDF reports."""
import io
import base64
import logging
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from backend.utils.df_utils import is_numeric_col, is_identifier_col, clean_numeric_series

logger = logging.getLogger(__name__)


def build_single_report(ds_key: str, source_info: dict, df_original, df_final,
                         analysis_before: dict, analysis_after: dict,
                         change_history: list, dataset_label: str = "Dataset") -> dict:
    """Build a complete report data model for a single dataset."""
    from backend.utils.df_utils import df_to_records
    final_records = df_to_records(df_final, max_rows=100) if df_final is not None else {}

    quality_before = (analysis_before or {}).get("quality_score", {})
    quality_after = (analysis_after or {}).get("quality_score", {})
    raw_issues = (analysis_after or {}).get("issue_center", [])
    issues = [
        i for i in raw_issues
        if i.get("category") not in ("Schema Problems", "Schema Issues")
        and (i.get("count", 0) > 0 or len(i.get("affected_indices", [])) > 0)
    ]
    stats = (analysis_after or {}).get("stats", {})

    visualizations = _generate_report_visualizations(df_final, analysis_before, analysis_after)
    final_summary = _generate_final_summary(df_original, df_final, quality_before, quality_after, issues)

    return {
        "report_type": "single",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "app_name": "CleanCore — Automated Data Quality & Anomaly Profiler",
        "dataset_label": dataset_label,
        "source_info": source_info,
        "dimensions": {
            "original": {
                "rows": len(df_original) if df_original is not None else 0,
                "cols": len(df_original.columns) if df_original is not None else 0,
            },
            "final": {
                "rows": len(df_final) if df_final is not None else 0,
                "cols": len(df_final.columns) if df_final is not None else 0,
            },
        },
        "analysis_before": analysis_before or {},
        "analysis_after": analysis_after or {},
        "quality_before": quality_before,
        "quality_after": quality_after,
        "change_history": change_history or [],
        "final_sample": final_records,
        "stats": stats,
        "issues": issues,
        "visualizations": visualizations,
        "final_summary": final_summary,
    }


def build_analysis_only_report(ref_source: dict, cur_source: dict,
                                ref_df, cur_df,
                                ref_analysis: dict, cur_analysis: dict,
                                ref_history: list, cur_history: list) -> dict:
    """Build a side-by-side individual analysis report for both datasets (NO comparison content)."""
    from backend.utils.df_utils import df_to_records
    def _clean_issues(raw):
        return [
            i for i in (raw or [])
            if i.get("category") not in ("Schema Problems", "Schema Issues")
            and (i.get("count", 0) > 0 or len(i.get("affected_indices", [])) > 0)
        ]

    return {
        "report_type": "analysis_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "app_name": "CleanCore — Automated Data Quality & Anomaly Profiler",
        "reference": {
            "source_info": ref_source,
            "dimensions": {"rows": len(ref_df) if ref_df is not None else 0,
                           "cols": len(ref_df.columns) if ref_df is not None else 0},
            "analysis": ref_analysis or {},
            "quality_score": (ref_analysis or {}).get("quality_score", {}),
            "stats": (ref_analysis or {}).get("stats", {}),
            "change_history": ref_history or [],
            "issues": _clean_issues((ref_analysis or {}).get("issue_center", [])),
            "sample": df_to_records(ref_df, max_rows=50) if ref_df is not None else {},
        },
        "current": {
            "source_info": cur_source,
            "dimensions": {"rows": len(cur_df) if cur_df is not None else 0,
                           "cols": len(cur_df.columns) if cur_df is not None else 0},
            "analysis": cur_analysis or {},
            "quality_score": (cur_analysis or {}).get("quality_score", {}),
            "stats": (cur_analysis or {}).get("stats", {}),
            "change_history": cur_history or [],
            "issues": _clean_issues((cur_analysis or {}).get("issue_center", [])),
            "sample": df_to_records(cur_df, max_rows=50) if cur_df is not None else {},
        },
    }


def build_comparison_report(ref_source: dict, cur_source: dict,
                              ref_df_orig, cur_df_orig,
                              ref_df_final, cur_df_final,
                              ref_analysis_before, ref_analysis_after,
                              cur_analysis_before, cur_analysis_after,
                              ref_history: list, cur_history: list,
                              comparison_result: dict) -> dict:
    """Build a complete report data model for a two-dataset comparison."""
    def _clean_issues(raw):
        return [
            i for i in (raw or [])
            if i.get("category") not in ("Schema Problems", "Schema Issues")
            and (i.get("count", 0) > 0 or len(i.get("affected_indices", [])) > 0)
        ]

    return {
        "report_type": "comparison",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "app_name": "CleanCore — Automated Data Quality & Anomaly Profiler",
        "reference": {
            "source_info": ref_source,
            "dimensions_original": {
                "rows": len(ref_df_orig) if ref_df_orig is not None else 0,
                "cols": len(ref_df_orig.columns) if ref_df_orig is not None else 0,
            },
            "dimensions_final": {
                "rows": len(ref_df_final) if ref_df_final is not None else 0,
                "cols": len(ref_df_final.columns) if ref_df_final is not None else 0,
            },
            "quality_before": (ref_analysis_before or {}).get("quality_score", {}),
            "quality_after": (ref_analysis_after or {}).get("quality_score", {}),
            "stats": (ref_analysis_after or {}).get("stats", {}),
            "change_history": ref_history or [],
            "issues_after": _clean_issues((ref_analysis_after or {}).get("issue_center", [])),
        },
        "current": {
            "source_info": cur_source,
            "dimensions_original": {
                "rows": len(cur_df_orig) if cur_df_orig is not None else 0,
                "cols": len(cur_df_orig.columns) if cur_df_orig is not None else 0,
            },
            "dimensions_final": {
                "rows": len(cur_df_final) if cur_df_final is not None else 0,
                "cols": len(cur_df_final.columns) if cur_df_final is not None else 0,
            },
            "quality_before": (cur_analysis_before or {}).get("quality_score", {}),
            "quality_after": (cur_analysis_after or {}).get("quality_score", {}),
            "stats": (cur_analysis_after or {}).get("stats", {}),
            "change_history": cur_history or [],
            "issues_after": _clean_issues((cur_analysis_after or {}).get("issue_center", [])),
        },
        "comparison": comparison_result or {},
    }


def _generate_report_visualizations(df_final: pd.DataFrame, analysis_before: dict, analysis_after: dict) -> dict:
    """Generate key static charts embedded as base64 PNG images for HTML/PDF reports."""
    charts = {}
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # 1. Missing Values by Column Chart
        missing_info = (analysis_after or {}).get("missing", {})
        affected_cols = missing_info.get("affected_columns", [])
        
        fig, ax = plt.subplots(figsize=(6, 2.8), dpi=100)
        if affected_cols:
            col_names = [c["column"] for c in affected_cols[:8]][::-1]
            counts = [c["missing_count"] for c in affected_cols[:8]][::-1]
            bars = ax.barh(col_names, counts, color="#f59e0b", edgecolor="#d97706", height=0.55)
            ax.set_title("Missing Values by Column (Final State)", fontsize=11, fontweight="bold", pad=10)
            ax.set_xlabel("Missing Count", fontsize=9)
            ax.grid(axis="x", linestyle="--", alpha=0.5)
            for bar in bars:
                w = bar.get_width()
                ax.text(w + max(max(counts)*0.02, 0.5), bar.get_y() + bar.get_height()/2, f"{int(w)}",
                        va="center", ha="left", fontsize=8, color="#334155")
        else:
            ax.text(0.5, 0.5, "0 Missing Values\nFinalized dataset is complete",
                    ha="center", va="center", fontsize=12, fontweight="bold", color="#16a34a")
            ax.set_axis_off()
            ax.set_title("Missing Values Status", fontsize=11, fontweight="bold")
        
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        charts["missing_chart"] = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")

        # 2. Quality Score Comparison Chart
        qb = (analysis_before or {}).get("quality_score", {})
        qa = (analysis_after or {}).get("quality_score", {})
        score_before = qb.get("score", 0) if qb else 0
        score_after = qa.get("score", 0) if qa else 0

        fig, ax = plt.subplots(figsize=(6, 2.8), dpi=100)
        labels = ["Before Cleaning", "After Cleaning (Final)"]
        scores = [score_before, score_after]
        colors = ["#94a3b8", "#16a34a" if score_after >= score_before else "#dc2626"]
        bars = ax.bar(labels, scores, color=colors, width=0.45, edgecolor="#475569")
        ax.set_ylim(0, 105)
        ax.set_ylabel("Quality Score (0–100)", fontsize=9)
        ax.set_title("Data Quality Score Progression", fontsize=11, fontweight="bold", pad=10)
        ax.grid(axis="y", linestyle="--", alpha=0.5)
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2, h + 2, f"{h:.1f}/100",
                    ha="center", va="bottom", fontsize=9, fontweight="bold")

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        charts["score_chart"] = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")

        # 3. Key Distribution Chart (first numerical column)
        if df_final is not None:
            num_cols = [c for c in df_final.columns if is_numeric_col(df_final[c]) and not is_identifier_col(df_final[c], c)]
            if not num_cols:
                num_cols = [c for c in df_final.columns if is_numeric_col(df_final[c])]
            if num_cols:
                target_col = num_cols[0]
                s = clean_numeric_series(df_final[target_col]).dropna()
                if len(s) > 1:
                    fig, ax = plt.subplots(figsize=(6, 2.8), dpi=100)
                    ax.hist(s, bins=min(25, max(5, int(len(s)**0.5))), color="#3b82f6", edgecolor="#1d4ed8", alpha=0.85)
                    ax.set_title(f"Distribution of '{target_col}' (Finalized)", fontsize=11, fontweight="bold", pad=10)
                    ax.set_xlabel(target_col, fontsize=9)
                    ax.set_ylabel("Frequency", fontsize=9)
                    ax.grid(axis="y", linestyle="--", alpha=0.5)
                    plt.tight_layout()
                    buf = io.BytesIO()
                    plt.savefig(buf, format="png", bbox_inches="tight")
                    plt.close(fig)
                    charts["distribution_chart"] = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")

    except Exception as e:
        logger.warning(f"Static chart generation warning: {e}")

    return charts


def _generate_final_summary(df_orig, df_final, quality_before, quality_after, issues) -> dict:
    """Generate concise closing takeaway paragraph and summary stats."""
    orig_rows = len(df_orig) if df_orig is not None else 0
    final_rows = len(df_final) if df_final is not None else 0
    rows_diff = orig_rows - final_rows
    
    score_before = quality_before.get("score") if quality_before else None
    score_after = quality_after.get("score") if quality_after else None
    label_after = quality_after.get("label", "N/A") if quality_after else "N/A"

    score_text = ""
    if score_after is not None:
        score_text = f"Quality score: {score_after:.1f}/100 ({label_after})"
        if score_before is not None:
            delta = score_after - score_before
            if delta > 0:
                score_text += f" (+{delta:.1f} improvement)"
            elif delta < 0:
                score_text += f" ({delta:.1f} decline)"
            else:
                score_text += " (unchanged)"
    
    # Issues remaining
    issue_categories = set(i.get("category") for i in (issues or []))
    cat_count = len(issue_categories)
    if cat_count == 0:
        issues_text = "All identified quality issues have been resolved."
    elif cat_count == 1:
        issues_text = f"1 issue category remains unresolved ({list(issue_categories)[0]})."
    else:
        issues_text = f"{cat_count} issue categories remain unresolved."

    retention_pct = (final_rows / orig_rows * 100) if orig_rows > 0 else 100.0
    paragraph = (
        f"{final_rows} of {orig_rows} original rows retained ({retention_pct:.1f}%) after cleaning"
        + (f", removing {rows_diff} invalid or duplicate row(s)" if rows_diff > 0 else "")
        + f". {score_text}. {issues_text}"
    )

    return {
        "text": paragraph,
        "original_rows": orig_rows,
        "final_rows": final_rows,
        "rows_removed": rows_diff,
        "retention_pct": round(retention_pct, 1),
        "score_before": score_before,
        "score_after": score_after,
        "score_label": label_after,
        "unresolved_categories_count": cat_count,
    }
