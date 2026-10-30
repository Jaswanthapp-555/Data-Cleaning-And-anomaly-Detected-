"""Plotly-based chart builder — returns JSON-serializable chart specs."""
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.utils import PlotlyJSONEncoder
import json
from backend.utils.df_utils import is_numeric_col, is_categorical_col, is_datetime_col, is_identifier_col, clean_numeric_series


def build_chart(df: pd.DataFrame, chart_type: str, config: dict) -> dict:
    """Build a chart and return Plotly JSON. config keys depend on chart_type."""
    try:
        if chart_type == "histogram":
            fig = _histogram(df, config)
        elif chart_type == "boxplot":
            fig = _boxplot(df, config)
        elif chart_type == "scatter":
            fig = _scatter(df, config)
        elif chart_type == "bar":
            fig = _bar(df, config)
        elif chart_type == "pie":
            fig = _pie(df, config)
        elif chart_type == "heatmap":
            fig = _heatmap(df, config)
        elif chart_type == "line":
            fig = _line(df, config)
        elif chart_type == "frequency":
            fig = _frequency(df, config)
        elif chart_type == "comparison_histogram":
            fig = _comparison_histogram(config)
        elif chart_type == "comparison_boxplot":
            fig = _comparison_boxplot(config)
        else:
            return {"error": f"Unknown chart type: {chart_type}"}

        fig.update_layout(
            font=dict(family="Inter, system-ui, sans-serif", size=13),
            plot_bgcolor="white",
            paper_bgcolor="white",
            margin=dict(l=60, r=30, t=60, b=60),
            legend=dict(bgcolor="rgba(255,255,255,0.8)", bordercolor="#e0e0e0", borderwidth=1),
        )

        raw_dict = json.loads(json.dumps(fig, cls=PlotlyJSONEncoder))
        return {"chart": decode_plotly_chart(raw_dict)}
    except Exception as e:
        return {"error": f"Chart generation error: {str(e)}"}


def decode_plotly_chart(obj):
    """Recursively decode Plotly bdata binary buffers and numpy types into native Python lists/primitives."""
    import base64
    from backend.utils.df_utils import safe_json_val

    if isinstance(obj, dict):
        if "bdata" in obj and "dtype" in obj:
            try:
                raw = base64.b64decode(obj["bdata"])
                arr = np.frombuffer(raw, dtype=obj["dtype"])
                return [safe_json_val(x) for x in arr.tolist()]
            except Exception:
                return []
        return {k: decode_plotly_chart(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decode_plotly_chart(v) for v in obj]
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    elif isinstance(obj, (np.ndarray,)):
        return [safe_json_val(x) for x in obj.tolist()]
    return obj



def _histogram(df, config):
    col = config["x"]
    if col not in df.columns:
        raise ValueError(f"Column '{col}' not found.")
    group = config.get("color")
    title = f"Distribution of {col}"
    
    # Coerce to numeric for plotting
    plot_df = df.copy()
    plot_df[col] = clean_numeric_series(plot_df[col])
    
    if group and group in plot_df.columns:
        fig = px.histogram(plot_df, x=col, color=group, title=title,
                           color_discrete_sequence=px.colors.qualitative.Set2,
                           nbins=config.get("bins", 30))
    else:
        fig = px.histogram(plot_df, x=col, title=title,
                           color_discrete_sequence=["#2563eb"],
                           nbins=config.get("bins", 30))
    fig.update_xaxes(title=col)
    fig.update_yaxes(title="Count")
    return fig


def _boxplot(df, config):
    col = config["y"]
    if col not in df.columns:
        raise ValueError(f"Column '{col}' not found.")
    group = config.get("x")
    title = f"Box Plot of {col}"
    
    plot_df = df.copy()
    plot_df[col] = clean_numeric_series(plot_df[col])
    
    if group and group in plot_df.columns:
        fig = px.box(plot_df, x=group, y=col, title=title,
                     color_discrete_sequence=["#2563eb"])
    else:
        fig = px.box(plot_df, y=col, title=title,
                     color_discrete_sequence=["#2563eb"])
    return fig


def _scatter(df, config):
    x = config["x"]
    y = config["y"]
    color = config.get("color")
    title = f"{y} vs {x}"
    
    plot_df = df.copy()
    plot_df[x] = clean_numeric_series(plot_df[x])
    plot_df[y] = clean_numeric_series(plot_df[y])
    
    kwargs = dict(x=x, y=y, title=title, opacity=0.7,
                  color_discrete_sequence=["#2563eb"])
    if color and color in plot_df.columns:
        kwargs["color"] = color
    fig = px.scatter(plot_df, **kwargs)
    return fig


def _bar(df, config):
    col = config["x"]
    if col not in df.columns:
        raise ValueError(f"Column '{col}' not found.")
    agg_col = config.get("y")
    agg = config.get("agg", "count")
    title = config.get("title", f"Bar Chart — {col}")

    if agg_col and agg_col in df.columns and is_numeric_col(df[agg_col]):
        plot_df = df.copy()
        plot_df[agg_col] = clean_numeric_series(plot_df[agg_col])
        if agg == "mean":
            data = plot_df.groupby(col, observed=False)[agg_col].mean().reset_index()
        elif agg == "sum":
            data = plot_df.groupby(col, observed=False)[agg_col].sum().reset_index()
        else:
            data = plot_df.groupby(col, observed=False)[agg_col].count().reset_index()
        fig = px.bar(data, x=col, y=agg_col, title=title,
                     color_discrete_sequence=["#2563eb"])
    else:
        vc = df[col].value_counts().reset_index()
        vc.columns = [col, "count"]
        fig = px.bar(vc.head(30), x=col, y="count", title=title,
                     color_discrete_sequence=["#2563eb"])
    return fig


def _pie(df, config):
    col = config["x"]
    if col not in df.columns:
        raise ValueError(f"Column '{col}' not found.")
    
    hole = 0.4 if config.get("donut", False) else 0.0
    group_other = config.get("group_other", True)
    
    vc = df[col].value_counts(dropna=False)
    if len(vc) > 15 and group_other:
        top10 = vc.head(10)
        other_sum = vc.iloc[10:].sum()
        names = [str(k) if pd.notna(k) else "null" for k in top10.index.tolist()] + ["Other"]
        values = top10.values.tolist() + [int(other_sum)]
    else:
        top = vc.head(20)
        names = [str(k) if pd.notna(k) else "null" for k in top.index.tolist()]
        values = top.values.tolist()

    fig = px.pie(names=names, values=values,
                 title=f"Distribution of {col} (Pie / Donut)",
                 hole=hole,
                 color_discrete_sequence=px.colors.qualitative.Set2)
    return fig


def _heatmap(df, config):
    num_cols = [c for c in df.columns if is_numeric_col(df[c]) and not is_identifier_col(df[c], c)]
    if len(num_cols) < 2:
        num_cols = [c for c in df.columns if is_numeric_col(df[c])]
    if len(num_cols) < 2:
        raise ValueError("Not enough numerical columns for a correlation heatmap.")
    
    clean_df = pd.DataFrame()
    for c in num_cols:
        clean_df[c] = clean_numeric_series(df[c])
        
    corr = clean_df.corr()
    fig = go.Figure(data=go.Heatmap(
        z=corr.values.tolist(),
        x=corr.columns.tolist(),
        y=corr.index.tolist(),
        colorscale="RdBu",
        zmid=0,
        text=[[f"{v:.2f}" if not np.isnan(v) else "—" for v in row] for row in corr.values],
        texttemplate="%{text}",
    ))
    fig.update_layout(title="Correlation Heatmap")
    return fig


def _line(df, config):
    x = config["x"]
    y = config["y"]
    title = f"{y} Over {x}"
    
    plot_df = df.copy()
    if is_numeric_col(plot_df[y]):
        plot_df[y] = clean_numeric_series(plot_df[y])
    sorted_df = plot_df[[x, y]].dropna().sort_values(x)
    fig = px.line(sorted_df, x=x, y=y, title=title,
                  color_discrete_sequence=["#2563eb"])
    return fig


def _frequency(df, config):
    col = config["x"]
    vc = df[col].value_counts().head(20).reset_index()
    vc.columns = [col, "frequency"]
    fig = px.bar(vc, x=col, y="frequency",
                 title=f"Frequency of {col}",
                 color_discrete_sequence=["#2563eb"])
    return fig


def _comparison_histogram(config):
    """Compare two distributions side by side."""
    ref_data = config.get("ref_data", [])
    cur_data = config.get("cur_data", [])
    col = config.get("col", "Value")
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=ref_data, name="Reference", opacity=0.7,
                               marker_color="#2563eb", nbinsx=30))
    fig.add_trace(go.Histogram(x=cur_data, name="Current", opacity=0.7,
                               marker_color="#16a34a", nbinsx=30))
    fig.update_layout(
        barmode="overlay",
        title=f"Distribution Comparison — {col}",
        xaxis_title=col,
        yaxis_title="Count",
    )
    return fig


def _comparison_boxplot(config):
    ref_data = config.get("ref_data", [])
    cur_data = config.get("cur_data", [])
    col = config.get("col", "Value")
    fig = go.Figure()
    fig.add_trace(go.Box(y=ref_data, name="Reference", marker_color="#2563eb"))
    fig.add_trace(go.Box(y=cur_data, name="Current", marker_color="#16a34a"))
    fig.update_layout(
        title=f"Box Plot Comparison — {col}",
        yaxis_title=col,
    )
    return fig


def get_available_charts(df: pd.DataFrame) -> dict:
    """Return which chart types are available for this DataFrame."""
    num_cols = [c for c in df.columns if is_numeric_col(df[c]) and not is_identifier_col(df[c], c)]
    # Fallback if all numeric are identifier names
    if not num_cols:
        num_cols = [c for c in df.columns if is_numeric_col(df[c])]
        
    cat_cols = [c for c in df.columns if is_categorical_col(df[c]) or is_identifier_col(df[c], c)]
    dt_cols = [c for c in df.columns if is_datetime_col(df[c])]

    charts = []
    if num_cols:
        charts.append({"type": "histogram", "label": "Histogram", "requires": "1 numerical column"})
        charts.append({"type": "boxplot", "label": "Box Plot", "requires": "1 numerical column"})
    if len(num_cols) >= 2:
        charts.append({"type": "scatter", "label": "Scatter Plot", "requires": "2 numerical columns"})
        charts.append({"type": "heatmap", "label": "Correlation Heatmap", "requires": "≥2 numerical columns"})
    if cat_cols:
        charts.append({"type": "bar", "label": "Bar Chart", "requires": "1 categorical column"})
        charts.append({"type": "frequency", "label": "Frequency Chart", "requires": "1 categorical column"})
    if cat_cols and len(cat_cols[0]) > 0:
        top_unique = df[cat_cols[0]].nunique() if cat_cols else 0
        if top_unique <= 20:
            charts.append({"type": "pie", "label": "Pie / Donut Chart", "requires": "categorical column with ≤20 unique values"})
    if dt_cols and num_cols:
        charts.append({"type": "line", "label": "Line / Time-Series Chart", "requires": "1 datetime + 1 numerical column"})
    if num_cols and cat_cols:
        charts.append({"type": "bar", "label": "Grouped Bar Chart", "requires": "1 categorical + 1 numerical column"})

    cardinality = {str(c): int(df[c].nunique()) for c in df.columns}

    return {
        "available_charts": charts,
        "numerical_columns": num_cols,
        "categorical_columns": cat_cols,
        "datetime_columns": dt_cols,
        "cardinality": cardinality,
        "all_columns": list(df.columns),
    }


def build_dataset_overview(df: pd.DataFrame) -> dict:
    """Auto-generate exactly 5 fixed charts summarizing the dataset with robust edge case handling."""
    if df is None or len(df) == 0:
        return {
            "summary": {"rows": 0, "cols": 0, "columns": []},
            "charts": {}
        }

    layout_defaults = dict(
        font=dict(family="Inter, system-ui, sans-serif", size=12),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=50, r=20, t=50, b=45),
    )

    charts = {}

    # 1. Missing Values by Column
    from backend.utils.df_utils import get_missing_mask
    mask = get_missing_mask(df)
    missing_counts = mask.sum()
    total_missing = int(missing_counts.sum())

    if total_missing == 0:
        charts["missing_values"] = {
            "title": "Missing Values by Column",
            "status": "clean",
            "message": "No missing values in this dataset — every column is complete.",
        }
    else:
        cols_with_missing = missing_counts[missing_counts > 0].sort_values(ascending=True)
        col_names = [str(c) for c in cols_with_missing.index.tolist()]
        counts = [int(v) for v in cols_with_missing.values.tolist()]
        pcts = [round(c / len(df) * 100, 1) for c in counts]
        hover = [f"{c}: {cnt} missing ({pct}%)" for c, cnt, pct in zip(col_names, counts, pcts)]

        fig1 = go.Figure(go.Bar(
            x=counts,
            y=col_names,
            orientation="h",
            marker=dict(color="#f59e0b", line=dict(color="#d97706", width=1)),
            text=[f"{cnt} ({pct}%)" for cnt, pct in zip(counts, pcts)],
            textposition="auto",
            hovertext=hover,
            hoverinfo="text",
        ))
        fig1.update_layout(
            **layout_defaults,
            title="Missing Values by Column (Count & %)",
            xaxis_title="Missing Records Count",
            yaxis_title="Column",
        )
        charts["missing_values"] = {
            "title": "Missing Values by Column",
            "status": "chart",
            "chart": decode_plotly_chart(json.loads(json.dumps(fig1, cls=PlotlyJSONEncoder))),
        }

    # 2. Data Type Distribution
    type_counts = {"Numerical": 0, "Categorical / Text": 0, "Datetime": 0, "Boolean / Other": 0}
    for col in df.columns:
        s = df[col]
        if is_numeric_col(s):
            type_counts["Numerical"] += 1
        elif is_datetime_col(s):
            type_counts["Datetime"] += 1
        elif is_categorical_col(s):
            type_counts["Categorical / Text"] += 1
        else:
            type_counts["Boolean / Other"] += 1

    active_types = {k: v for k, v in type_counts.items() if v > 0}
    if not active_types:
        charts["dtype_distribution"] = {
            "title": "Data Type Distribution",
            "status": "notice",
            "message": "No columns found to analyze data types.",
        }
    else:
        color_map = {
            "Numerical": "#3b82f6",
            "Categorical / Text": "#8b5cf6",
            "Datetime": "#10b981",
            "Boolean / Other": "#f59e0b",
        }
        fig2 = go.Figure(go.Pie(
            labels=list(active_types.keys()),
            values=list(active_types.values()),
            hole=0.45,
            marker=dict(colors=[color_map.get(k, "#64748b") for k in active_types.keys()]),
            textinfo="label+value+percent",
            hoverinfo="label+value+percent",
        ))
        fig2.update_layout(
            **layout_defaults,
            title="Data Type Distribution (Columns)",
            showlegend=True,
        )
        charts["dtype_distribution"] = {
            "title": "Data Type Distribution",
            "status": "chart",
            "chart": decode_plotly_chart(json.loads(json.dumps(fig2, cls=PlotlyJSONEncoder))),
        }

    # 3. Correlation Heatmap (only when ≥2 numeric columns with non-zero std)
    num_cols = [c for c in df.columns if is_numeric_col(df[c]) and not is_identifier_col(df[c], c)]
    if len(num_cols) < 2:
        num_cols = [c for c in df.columns if is_numeric_col(df[c])]

    if len(num_cols) < 2:
        charts["correlation_heatmap"] = {
            "title": "Correlation Heatmap",
            "status": "notice",
            "message": f"Correlation Heatmap requires at least 2 numerical columns (found {len(num_cols)}).",
        }
    else:
        clean_df = pd.DataFrame()
        for c in num_cols:
            clean_df[c] = clean_numeric_series(df[c])

        valid_cols = [c for c in num_cols if clean_df[c].dropna().std() > 0]
        if len(valid_cols) < 2:
            charts["correlation_heatmap"] = {
                "title": "Correlation Heatmap",
                "status": "notice",
                "message": "Numerical columns have insufficient variance; correlation cannot be computed.",
            }
        else:
            corr = clean_df[valid_cols].corr()
            fig3 = go.Figure(data=go.Heatmap(
                z=[[float(v) if not np.isnan(v) else 0.0 for v in row] for row in corr.values],
                x=corr.columns.tolist(),
                y=corr.index.tolist(),
                colorscale="RdBu",
                zmid=0,
                zmin=-1,
                zmax=1,
                text=[[f"{v:.2f}" if not np.isnan(v) else "—" for v in row] for row in corr.values],
                texttemplate="%{text}",
                colorbar=dict(title="r"),
            ))
            fig3.update_layout(
                **layout_defaults,
                title="Correlation Heatmap (Numerical Variables)",
            )
            charts["correlation_heatmap"] = {
                "title": "Correlation Heatmap",
                "status": "chart",
                "chart": decode_plotly_chart(json.loads(json.dumps(fig3, cls=PlotlyJSONEncoder))),
            }

    # 4. ONE Representative Numeric Distribution Histogram
    num_candidates = [c for c in df.columns if is_numeric_col(df[c]) and not is_identifier_col(df[c], c)]
    if not num_candidates:
        num_candidates = [c for c in df.columns if is_numeric_col(df[c])]

    if not num_candidates:
        charts["numeric_distribution"] = {
            "title": "Numeric Distribution",
            "status": "notice",
            "message": "No numerical columns found in this dataset.",
        }
    else:
        # Select best representative numeric column: highest non-zero variance or largest sample
        best_num = num_candidates[0]
        max_std = -1.0
        for c in num_candidates:
            s_clean = clean_numeric_series(df[c]).dropna()
            if len(s_clean) > 0:
                std_val = float(s_clean.std()) if len(s_clean) > 1 else 0.0
                if std_val > max_std:
                    max_std = std_val
                    best_num = c

        s_vals = [float(v) for v in clean_numeric_series(df[best_num]).dropna().tolist()]
        if len(s_vals) == 0:
            charts["numeric_distribution"] = {
                "title": f"Distribution — {best_num}",
                "status": "notice",
                "message": f"Column '{best_num}' has no non-null numerical values.",
            }
        else:
            fig4 = go.Figure(go.Histogram(
                x=s_vals,
                nbinsx=min(30, max(10, int(len(s_vals)**0.5))),
                marker=dict(color="#3b82f6", line=dict(color="#2563eb", width=1.2)),
            ))
            fig4.update_layout(
                **layout_defaults,
                title=f"Primary Numeric Distribution — '{best_num}'",
                xaxis_title=best_num,
                yaxis_title="Frequency",
            )
            charts["numeric_distribution"] = {
                "column": best_num,
                "title": f"Numeric Distribution ('{best_num}')",
                "status": "chart",
                "chart": decode_plotly_chart(json.loads(json.dumps(fig4, cls=PlotlyJSONEncoder))),
            }

    # 5. ONE Representative Categorical Breakdown Chart
    cat_candidates = [c for c in df.columns if not is_numeric_col(df[c]) and not is_identifier_col(df[c], c) and not is_datetime_col(df[c])]
    if not cat_candidates:
        cat_candidates = [c for c in df.columns if not is_numeric_col(df[c]) and not is_datetime_col(df[c])]

    if not cat_candidates:
        charts["categorical_breakdown"] = {
            "title": "Categorical Breakdown",
            "status": "notice",
            "message": "No categorical columns found in this dataset.",
        }
    else:
        # Select best representative categorical column: cardinality between 2 and 20 if possible
        best_cat = cat_candidates[0]
        for c in cat_candidates:
            n_uniq = df[c].dropna().nunique()
            if 2 <= n_uniq <= 20:
                best_cat = c
                break

        vc = df[best_cat].dropna().astype(str).value_counts()
        if len(vc) == 0:
            charts["categorical_breakdown"] = {
                "title": f"Breakdown — {best_cat}",
                "status": "notice",
                "message": f"Column '{best_cat}' contains no records.",
            }
        else:
            # Top N + Other grouping for high cardinality (> 10)
            if len(vc) > 10:
                top10 = vc.head(10)
                other = int(vc.iloc[10:].sum())
                labels = [str(k) for k in top10.index.tolist()] + ["Other"]
                values = [int(v) for v in top10.values.tolist()] + [other]
            else:
                labels = [str(k) for k in vc.index.tolist()]
                values = [int(v) for v in vc.values.tolist()]

            fig5 = go.Figure(go.Bar(
                x=labels,
                y=values,
                marker=dict(color="#8b5cf6", line=dict(color="#7c3aed", width=1.2)),
                text=values,
                textposition="auto",
            ))
            fig5.update_layout(
                **layout_defaults,
                title=f"Primary Category Breakdown — '{best_cat}'",
                xaxis_title=best_cat,
                yaxis_title="Count",
            )
            charts["categorical_breakdown"] = {
                "column": best_cat,
                "title": f"Category Breakdown ('{best_cat}')",
                "status": "chart",
                "chart": decode_plotly_chart(json.loads(json.dumps(fig5, cls=PlotlyJSONEncoder))),
            }

    return {
        "summary": {
            "rows": len(df),
            "cols": len(df.columns),
            "columns": list(df.columns),
        },
        "charts": charts,
    }

