/* visualization.js — Interactive Plotly chart builder & Dataset Overview (5 Auto Charts) */
import * as api from "./api.js";
import { showAlert, showModal, escHtml, renderNoDatasetState, getPlotlyThemeLayout } from "./app.js";

// In-memory gallery storage per session
const savedGallery = [];

export async function renderViz(container, dataset) {
  try {
    const st = await api.getDatasetState(dataset);
    if (!st || st.state === "empty") {
      renderNoDatasetState(container, "Visualization", dataset);
      return;
    }
  } catch {
    renderNoDatasetState(container, "Visualization", dataset);
    return;
  }

  container.innerHTML = `
    <!-- Sub-navigation Header -->
    <div class="viz-header-wrap" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:1rem; margin-bottom:1.5rem">
      <div class="sub-nav-tabs" role="tablist">
        <button class="sub-nav-tab active" id="tab-viz-overview" role="tab" aria-selected="true">
          <span class="sub-nav-icon">📊</span>
          <span>Dataset Overview (5 Auto Charts)</span>
        </button>
        <button class="sub-nav-tab" id="tab-viz-builder" role="tab" aria-selected="false">
          <span class="sub-nav-icon">🛠️</span>
          <span>Custom Chart Builder</span>
        </button>
      </div>
      <div id="viz-header-controls" style="display:flex; align-items:center; gap:0.5rem"></div>
    </div>

    <!-- Sub-view Render Container -->
    <div id="viz-subview-content"></div>
  `;

  const overviewTab = container.querySelector("#tab-viz-overview");
  const builderTab = container.querySelector("#tab-viz-builder");
  const subContent = container.querySelector("#viz-subview-content");
  const headerControls = container.querySelector("#viz-header-controls");

  let currentView = "overview";

  const showOverview = async (which = "working") => {
    currentView = "overview";
    overviewTab.classList.add("active");
    overviewTab.setAttribute("aria-selected", "true");
    builderTab.classList.remove("active");
    builderTab.setAttribute("aria-selected", "false");
    headerControls.innerHTML = "";
    await renderDatasetOverview(subContent, dataset, which, headerControls);
  };

  const showBuilder = async () => {
    currentView = "builder";
    builderTab.classList.add("active");
    builderTab.setAttribute("aria-selected", "true");
    overviewTab.classList.remove("active");
    overviewTab.setAttribute("aria-selected", "false");
    headerControls.innerHTML = `
      <button class="btn btn-secondary btn-sm" id="btn-jump-gallery-header">
        🖼️ Saved Gallery (${savedGallery.length})
      </button>
    `;
    const btnJump = headerControls.querySelector("#btn-jump-gallery-header");
    if (btnJump) {
      btnJump.onclick = () => {
        const g = subContent.querySelector("#gallery-card");
        if (g) g.scrollIntoView({ behavior: "smooth" });
      };
    }

    subContent.innerHTML = `<div class="loading-overlay" style="min-height:200px"><div class="spinner spinner-lg"></div><div class="loading-text">Loading custom chart builder...</div></div>`;
    try {
      const avail = await api.getAvailableCharts(dataset);
      renderVizBuilder(subContent, dataset, avail);
    } catch (e) {
      subContent.innerHTML = `<div class="alert alert-error">✗ ${escHtml(e.message)}</div>`;
    }
  };

  overviewTab.onclick = () => showOverview();
  builderTab.onclick = () => showBuilder();

  // Initial load: Dataset Overview
  await showOverview();
}

/* ================================================================
   DATASET OVERVIEW (5 AUTO-GENERATED FIXED CHARTS)
   Zero configuration required — summarizes whole dataset at a glance
   Charts:
   1. Missing Values by Column
   2. Data Type Distribution
   3. Correlation Heatmap
   4. Key Categorical Breakdown
   5. Numeric Distribution Overview
================================================================ */
async function renderDatasetOverview(container, dataset, which = "working", headerControls = null) {
  container.innerHTML = `
    <div class="loading-overlay" style="min-height:300px">
      <div class="spinner spinner-lg"></div>
      <div class="loading-text">Generating 5-point dataset visual profile...</div>
    </div>
  `;

  try {
    const data = await api.getDatasetOverview(dataset, which);
    if (data.error) {
      container.innerHTML = `<div class="alert alert-error">✗ ${escHtml(data.error)}</div>`;
      return;
    }

    const summary = data.summary || {};
    const charts = data.charts || {};
    const stateLabel = data.state_label || which;

    // Header Controls: state selector dropdown + refresh
    if (headerControls) {
      headerControls.innerHTML = `
        <div style="display:flex; align-items:center; gap:0.5rem">
          <label style="font-size:0.75rem; font-weight:700; color:var(--ink-faint)">State:</label>
          <select class="form-select form-select-sm" id="ov-which-select" style="min-width:160px; padding:0.35rem 0.65rem; font-size:0.75rem">
            <option value="working" ${which === "working" ? "selected" : ""}>Working Copy</option>
            <option value="original" ${which === "original" ? "selected" : ""}>Original Uploaded</option>
            <option value="finalized" ${which === "finalized" ? "selected" : ""}>Finalized Dataset</option>
          </select>
          <button class="btn btn-secondary btn-sm" id="btn-refresh-overview" title="Re-generate Overview">🔄 Refresh</button>
        </div>
      `;

      const sel = headerControls.querySelector("#ov-which-select");
      if (sel) {
        sel.onchange = () => renderDatasetOverview(container, dataset, sel.value, headerControls);
      }
      const refBtn = headerControls.querySelector("#btn-refresh-overview");
      if (refBtn) {
        refBtn.onclick = () => renderDatasetOverview(container, dataset, sel ? sel.value : which, headerControls);
      }
    }

    // Top Summary Banner
    let html = `
      <div class="card" style="padding:1.25rem 1.5rem; margin-bottom:1.5rem; background:linear-gradient(135deg, var(--surface) 0%, var(--surface-2) 100%)">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:1rem">
          <div>
            <div style="display:flex; align-items:center; gap:0.6rem; margin-bottom:0.25rem">
              <span style="font-size:1.125rem; font-weight:800; color:var(--ink)">Dataset Visual Intelligence Profile</span>
              <span class="badge ${which === 'finalized' ? 'badge-success' : 'badge-info'}">${escHtml(stateLabel)}</span>
            </div>
            <div style="font-size:0.8125rem; color:var(--ink-faint)">
              Automated 5-chart exploratory overview of <strong>${escHtml(dataset.toUpperCase())}</strong> dataset. No manual parameters required.
            </div>
          </div>
          <div style="display:flex; gap:1.25rem; align-items:center">
            <div style="text-align:right">
              <div style="font-size:0.7rem; font-weight:700; color:var(--ink-faint); text-transform:uppercase">Dimensions</div>
              <div style="font-size:1.125rem; font-weight:800; color:var(--ink)">${summary.rows || 0} rows × ${summary.cols || 0} cols</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 5 Fixed Charts Grid -->
      <div class="grid-2" style="margin-bottom:1.5rem">
        <!-- 1. Missing Values by Column -->
        <div class="card viz-overview-card" id="card-ov-missing">
          <div class="card-title" style="justify-content:space-between">
            <div style="display:flex; align-items:center; gap:0.5rem">
              <span class="viz-icon-pill" style="background:rgba(245,158,11,0.15); color:#d97706">1</span>
              <span>Missing Values by Column</span>
            </div>
            ${charts.missing_values?.status === "chart" ? `<button class="btn btn-secondary btn-sm btn-dl-png" data-target="plot-ov-missing">📷 PNG</button>` : ""}
          </div>
          <div id="plot-ov-missing" class="viz-overview-plot-wrap">
            ${renderChartOrEmptyState(charts.missing_values, "No missing values in this dataset — every column is complete.")}
          </div>
        </div>

        <!-- 2. Data Type Distribution -->
        <div class="card viz-overview-card" id="card-ov-dtypes">
          <div class="card-title" style="justify-content:space-between">
            <div style="display:flex; align-items:center; gap:0.5rem">
              <span class="viz-icon-pill" style="background:rgba(139,92,246,0.15); color:#7c3aed">2</span>
              <span>Data Type Distribution</span>
            </div>
            ${charts.dtype_distribution?.status === "chart" ? `<button class="btn btn-secondary btn-sm btn-dl-png" data-target="plot-ov-dtypes">📷 PNG</button>` : ""}
          </div>
          <div id="plot-ov-dtypes" class="viz-overview-plot-wrap">
            ${renderChartOrEmptyState(charts.dtype_distribution, "All columns categorized by data type.")}
          </div>
        </div>
      </div>

      <!-- 3. Correlation Heatmap (Full Width) -->
      <div class="card viz-overview-card" id="card-ov-corr" style="margin-bottom:1.5rem">
        <div class="card-title" style="justify-content:space-between">
          <div style="display:flex; align-items:center; gap:0.5rem">
            <span class="viz-icon-pill" style="background:rgba(59,91,253,0.15); color:var(--accent)">3</span>
            <span>Correlation Heatmap (All Numeric Variables)</span>
          </div>
          ${charts.correlation_heatmap?.status === "chart" ? `<button class="btn btn-secondary btn-sm btn-dl-png" data-target="plot-ov-corr">📷 PNG</button>` : ""}
        </div>
        <div id="plot-ov-corr" class="viz-overview-plot-wrap" style="min-height:360px">
          ${renderChartOrEmptyState(charts.correlation_heatmap, "Requires at least 2 numerical columns with non-zero variance.")}
        </div>
      </div>

      <!-- 4 & 5. Primary Feature Distributions -->
      <div class="grid-2" style="margin-bottom:1.5rem">
        <!-- 4. Representative Numeric Distribution -->
        <div class="card viz-overview-card" id="card-ov-num">
          <div class="card-title" style="justify-content:space-between">
            <div style="display:flex; align-items:center; gap:0.5rem">
              <span class="viz-icon-pill" style="background:rgba(59,130,246,0.15); color:#2563eb">4</span>
              <span>Primary Numeric Distribution ${charts.numeric_distribution?.column ? `(${escHtml(charts.numeric_distribution.column)})` : ""}</span>
            </div>
            ${charts.numeric_distribution?.status === "chart" ? `<button class="btn btn-secondary btn-sm btn-dl-png" data-target="plot-ov-num">📷 PNG</button>` : ""}
          </div>
          <div id="plot-ov-num" class="viz-overview-plot-wrap">
            ${renderChartOrEmptyState(charts.numeric_distribution, "No numerical columns with variance available.")}
          </div>
        </div>

        <!-- 5. Representative Categorical Breakdown -->
        <div class="card viz-overview-card" id="card-ov-cat">
          <div class="card-title" style="justify-content:space-between">
            <div style="display:flex; align-items:center; gap:0.5rem">
              <span class="viz-icon-pill" style="background:rgba(139,92,246,0.15); color:#7c3aed">5</span>
              <span>Primary Categorical Breakdown ${charts.categorical_breakdown?.column ? `(${escHtml(charts.categorical_breakdown.column)})` : ""}</span>
            </div>
            ${charts.categorical_breakdown?.status === "chart" ? `<button class="btn btn-secondary btn-sm btn-dl-png" data-target="plot-ov-cat">📷 PNG</button>` : ""}
          </div>
          <div id="plot-ov-cat" class="viz-overview-plot-wrap">
            ${renderChartOrEmptyState(charts.categorical_breakdown, "No categorical columns found in this dataset.")}
          </div>
        </div>
      </div>
    `;

    container.innerHTML = html;

    // Render Plotly graphs for active charts with theme-aware styling
    renderOverviewPlot(container, "plot-ov-missing", charts.missing_values);
    renderOverviewPlot(container, "plot-ov-dtypes", charts.dtype_distribution);
    renderOverviewPlot(container, "plot-ov-corr", charts.correlation_heatmap);
    renderOverviewPlot(container, "plot-ov-num", charts.numeric_distribution);
    renderOverviewPlot(container, "plot-ov-cat", charts.categorical_breakdown);

    // PNG download triggers
    container.querySelectorAll(".btn-dl-png").forEach(btn => {
      btn.onclick = () => {
        const targetId = btn.dataset.target;
        const targetEl = container.querySelector(`#${targetId}`);
        if (targetEl) {
          Plotly.downloadImage(targetEl, {
            format: "png",
            width: 1000,
            height: 600,
            filename: `${targetId}_${dataset}_${Date.now()}`,
          });
        }
      };
    });

  } catch (err) {
    container.innerHTML = `<div class="alert alert-error">✗ Failed to generate Dataset Overview: ${escHtml(err.message)}</div>`;
  }
}

/* Helper to render either the clean checkmark confirmation, notice box, or prepare Plotly container */
function renderChartOrEmptyState(chartData, fallbackMsg = "") {
  if (!chartData) {
    return `
      <div class="overview-empty-state notice">
        <div class="overview-empty-icon info">ℹ️</div>
        <div class="overview-empty-title">Chart Not Available</div>
        <div class="overview-empty-sub">${escHtml(fallbackMsg)}</div>
      </div>
    `;
  }

  // Positive Confirmation State (e.g. 0 missing values)
  if (chartData.status === "clean") {
    return `
      <div class="overview-empty-state positive">
        <div class="overview-empty-icon success">
          <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20 6L9 17l-5-5"/>
          </svg>
        </div>
        <div class="overview-empty-title">All Columns Complete</div>
        <div class="overview-empty-sub">${escHtml(chartData.message || fallbackMsg)}</div>
        <div style="margin-top:0.75rem">
          <span class="badge badge-success" style="font-size:0.75rem; padding:0.35rem 0.8rem">100% Data Completeness</span>
        </div>
      </div>
    `;
  }

  // Explanatory Notice State (e.g. <2 numeric columns)
  if (chartData.status === "notice") {
    return `
      <div class="overview-empty-state notice">
        <div class="overview-empty-icon info">
          <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="16" x2="12" y2="12"></line>
            <line x1="12" y1="8" x2="12.01" y2="8"></line>
          </svg>
        </div>
        <div class="overview-empty-title">${escHtml(chartData.title || "Notice")}</div>
        <div class="overview-empty-sub">${escHtml(chartData.message || fallbackMsg)}</div>
      </div>
    `;
  }

  // Chart placeholder container
  return `<div class="plot-plotly-inner" style="width:100%; height:100%; min-height:300px"></div>`;
}

function ensurePlotlyDataDecoded(chart) {
  if (!chart || !chart.data) return chart;
  chart.data.forEach(trace => {
    ["x", "y", "z", "values", "labels"].forEach(k => {
      const val = trace[k];
      if (val && typeof val === "object" && !Array.isArray(val) && val.bdata) {
        try {
          const binaryStr = atob(val.bdata);
          const len = binaryStr.length;
          const bytes = new Uint8Array(len);
          for (let i = 0; i < len; i++) {
            bytes[i] = binaryStr.charCodeAt(i);
          }
          if (val.dtype === "f8" || val.dtype === "<f8") {
            trace[k] = Array.from(new Float64Array(bytes.buffer));
          } else if (val.dtype === "f4" || val.dtype === "<f4") {
            trace[k] = Array.from(new Float32Array(bytes.buffer));
          } else if (val.dtype === "i8" || val.dtype === "<i8") {
            trace[k] = Array.from(new BigInt64Array(bytes.buffer)).map(n => Number(n));
          } else if (val.dtype === "i4" || val.dtype === "<i4") {
            trace[k] = Array.from(new Int32Array(bytes.buffer));
          }
        } catch (e) {
          console.warn("Failed to decode bdata:", e);
        }
      }
    });
  });
  return chart;
}

function renderOverviewPlot(container, elementId, chartData) {
  if (!chartData || chartData.status !== "chart" || !chartData.chart) return;
  const wrap = container.querySelector(`#${elementId}`);
  if (!wrap) return;

  const inner = wrap.querySelector(".plot-plotly-inner") || wrap;
  const themeLayout = getPlotlyThemeLayout();

  ensurePlotlyDataDecoded(chartData.chart);

  const layout = {
    ...chartData.chart.layout,
    ...themeLayout,
    autosize: true,
    margin: { l: 45, r: 25, t: 40, b: 45 },
  };

  Plotly.newPlot(inner, chartData.chart.data, layout, {
    responsive: true,
    displayModeBar: false,
  });

  // Listen for themechange to dynamically update Plotly colors
  const themeHandler = () => {
    const updatedTheme = getPlotlyThemeLayout();
    try {
      Plotly.relayout(inner, updatedTheme);
    } catch { }
  };
  window.addEventListener("themechange", themeHandler);
}

/* ================================================================
   MANUAL CHART BUILDER ("Build Your Own")
================================================================ */
function renderVizBuilder(container, dataset, avail) {
  const numCols = avail.numerical_columns || [];
  const catCols = avail.categorical_columns || [];
  const dtCols = avail.datetime_columns || [];
  const allCols = avail.all_columns || [...numCols, ...catCols, ...dtCols];
  const cardinality = avail.cardinality || {};

  container.innerHTML = `
    <div id="viz-alerts"></div>

    <!-- Main Chart Studio Card -->
    <div class="card">
      <div class="card-title" style="justify-content:space-between">
        <div style="display:flex; align-items:center; gap:0.5rem">
          <span style="font-size:1.1rem">📈</span>
          <span>Manual Visualization Builder — ${escHtml(dataset.toUpperCase())} Dataset</span>
        </div>
        <button class="btn btn-secondary btn-sm" id="btn-jump-gallery">
          🖼️ Saved Gallery (${savedGallery.length})
        </button>
      </div>
      <p style="color:var(--ink-faint); font-size:0.8125rem; margin-bottom:1.25rem">
        Design interactive, publication-ready data visualizations with automatic type validation and aggregation.
      </p>

      <!-- Control Panel -->
      <div class="grid-3" style="margin-bottom:1rem">
        <div class="form-group">
          <label class="form-label">Chart Type</label>
          <select class="form-select" id="viz-chart-type">
            <option value="histogram">Histogram (Numerical Distribution)</option>
            <option value="boxplot">Box Plot (Outlier &amp; Quartiles)</option>
            <option value="scatter">Scatter Plot (Two Numerical Variables)</option>
            <option value="bar">Bar Chart (Categorical Aggregation)</option>
            <option value="pie">Pie / Donut Chart (Proportions)</option>
            <option value="heatmap">Correlation Heatmap (Numerical Matrix)</option>
            <option value="line">Line / Trend Chart (Time-Series)</option>
            <option value="frequency">Frequency Distribution (Top Categories)</option>
          </select>
        </div>

        <div class="form-group">
          <label class="form-label">Dataset State</label>
          <select class="form-select" id="viz-which">
            <option value="working" selected>Current Working Dataset</option>
            <option value="original">Original Uploaded Dataset</option>
            <option value="finalized">Finalized Dataset</option>
          </select>
        </div>

        <div class="form-group">
          <label class="form-label">Chart Title (Optional)</label>
          <input class="form-input" id="viz-title-custom" placeholder="Auto-generated if empty">
        </div>
      </div>

      <!-- Dynamic Chart Parameters -->
      <div class="grid-3" id="viz-dynamic-inputs" style="background:var(--surface-2); padding:1rem; border-radius:10px; border:1px solid var(--line); margin-bottom:1.25rem">
        <!-- Injected dynamically based on selected chart type -->
      </div>

      <!-- High Cardinality / Type Warning Banner -->
      <div id="viz-validation-warning" class="hidden" style="margin-bottom:1rem; padding:0.75rem 1rem; background:var(--warning-bg); border:1px solid var(--warning-border); border-radius:8px">
        <div style="font-weight:700; color:var(--warning); font-size:0.8125rem" id="viz-warn-title">⚠️ Notice</div>
        <div style="font-size:0.75rem; color:var(--ink-soft); margin-top:0.2rem" id="viz-warn-desc"></div>
      </div>

      <!-- Action Buttons -->
      <div style="display:flex; gap:0.5rem; align-items:center; flex-wrap:wrap">
        <button class="btn btn-primary" id="btn-gen-chart">Generate Visualization</button>
        <button class="btn btn-purple hidden" id="btn-save-chart">💾 Save to Gallery</button>
        <button class="btn btn-ghost btn-sm hidden" id="btn-new-chart">➕ Visualize Another</button>
      </div>
    </div>

    <!-- Active Chart Render Area -->
    <div class="card" id="chart-card">
      <div class="card-title" style="justify-content:space-between">
        <span id="chart-title-label">Interactive Visualization</span>
        <div style="display:flex; gap:0.5rem; align-items:center">
          <span class="badge badge-info" id="chart-state-badge">State: Working</span>
          <button class="btn btn-primary btn-sm hidden" id="btn-download-png">📷 Export PNG</button>
        </div>
      </div>
      <div id="plotly-container" style="width:100%; min-height:460px; position:relative">
        <div class="empty-state">
          <div style="font-size:3rem; margin-bottom:0.5rem">📊</div>
          <div class="empty-title">Select parameters and click "Generate Visualization"</div>
          <div class="empty-sub">Plots will be rendered here with full zoom, pan, hover, and export controls.</div>
        </div>
      </div>
    </div>

    <!-- Saved Visualizations Gallery -->
    <div class="card" id="gallery-card">
      <div class="card-title" style="justify-content:space-between">
        <span>🖼️ Saved Visualizations Gallery</span>
        <span class="badge badge-neutral" id="gallery-count-badge">${savedGallery.length} saved</span>
      </div>
      <div id="gallery-container">
        ${renderGalleryCards()}
      </div>
    </div>
  `;

  let currentActiveChartData = null;

  const chartTypeSel = container.querySelector("#viz-chart-type");
  const inputsContainer = container.querySelector("#viz-dynamic-inputs");
  const warnBox = container.querySelector("#viz-validation-warning");
  const warnTitle = container.querySelector("#viz-warn-title");
  const warnDesc = container.querySelector("#viz-warn-desc");

  const updateInputs = () => {
    const type = chartTypeSel.value;
    let html = "";
    warnBox.classList.add("hidden");

    if (type === "histogram") {
      html += optSelect("X-Axis (Numerical Variable)", "viz-x", numCols.length ? numCols : allCols);
      html += optSelect("Color / Group By (Optional)", "viz-color", ["None", ...catCols]);
      html += optSelect("Bins Count", "viz-bins", ["20", "30", "50", "100"]);
    } else if (type === "boxplot") {
      html += optSelect("Numerical Metric (Y-Axis)", "viz-y", numCols.length ? numCols : allCols);
      html += optSelect("Group By Category (X-Axis, Optional)", "viz-x", ["None", ...catCols]);
    } else if (type === "scatter") {
      html += optSelect("X-Axis (Numerical)", "viz-x", numCols.length ? numCols : allCols);
      html += optSelect("Y-Axis (Numerical)", "viz-y", numCols.length > 1 ? numCols.slice(1).concat(numCols[0]) : allCols);
      html += optSelect("Color / Hue (Optional)", "viz-color", ["None", ...catCols]);
    } else if (type === "bar") {
      html += optSelect("Category (X-Axis)", "viz-x", catCols.length ? catCols : allCols);
      html += optSelect("Metric (Y-Axis, Optional)", "viz-y", ["None (Row Count)", ...numCols]);
      html += optSelect("Aggregation", "viz-agg", ["count", "sum", "mean", "min", "max"]);
    } else if (type === "pie") {
      html += optSelect("Category Column", "viz-x", catCols.length ? catCols : allCols);
      html += optSelect("Style", "viz-donut", ["Pie Chart", "Donut Chart (Hole)"]);
      html += optSelect("High-Cardinality Handling", "viz-group-other", ["Group Top 10 + Other (Recommended)", "Show All Categories"]);
    } else if (type === "line") {
      html += optSelect("Time / Sequence (X-Axis)", "viz-x", dtCols.length ? dtCols : allCols);
      html += optSelect("Metric (Y-Axis)", "viz-y", numCols.length ? numCols : allCols);
    } else if (type === "frequency") {
      html += optSelect("Categorical Column", "viz-x", catCols.length ? catCols : allCols);
    } else if (type === "heatmap") {
      html += `<div style="grid-column: span 3; color:var(--ink-faint); font-size:0.8125rem">Calculates Pearson correlation matrix for all ${numCols.length} numerical columns.</div>`;
    }

    inputsContainer.innerHTML = html;

    if (type === "pie") {
      const xSel = container.querySelector("#viz-x");
      if (xSel) {
        xSel.onchange = () => {
          const col = xSel.value;
          const count = cardinality[col] || 0;
          if (count > 15) {
            warnBox.classList.remove("hidden");
            warnTitle.textContent = `⚠️ High Cardinality (${count} unique values)`;
            warnDesc.textContent = `Column '${col}' has ${count} distinct values. Pie charts with >15 slices are hard to read. 'Group Top 10 + Other' has been automatically enabled.`;
          } else {
            warnBox.classList.add("hidden");
          }
        };
        xSel.onchange();
      }
    }
  };

  chartTypeSel.onchange = updateInputs;
  updateInputs();

  // Generate chart button
  container.querySelector("#btn-gen-chart").onclick = async () => {
    const type = chartTypeSel.value;
    const which = container.querySelector("#viz-which").value;
    const customTitle = container.querySelector("#viz-title-custom").value.trim();
    const config = {};

    const xEl = container.querySelector("#viz-x");
    const yEl = container.querySelector("#viz-y");
    const colEl = container.querySelector("#viz-color");
    const aggEl = container.querySelector("#viz-agg");
    const binsEl = container.querySelector("#viz-bins");
    const donutEl = container.querySelector("#viz-donut");
    const groupOtherEl = container.querySelector("#viz-group-other");

    if (xEl && xEl.value !== "None") config.x = xEl.value;
    if (yEl && yEl.value !== "None (Row Count)" && yEl.value !== "None") config.y = yEl.value;
    if (colEl && colEl.value !== "None") config.color = colEl.value;
    if (aggEl) config.agg = aggEl.value;
    if (binsEl) config.bins = parseInt(binsEl.value);
    if (donutEl) config.donut = donutEl.value.includes("Donut");
    if (groupOtherEl) config.group_other = groupOtherEl.value.includes("Top 10");
    if (customTitle) config.title = customTitle;

    const plotlyWrap = container.querySelector("#plotly-container");
    plotlyWrap.innerHTML = `<div class="loading-overlay"><div class="spinner spinner-lg"></div><div class="loading-text">Rendering visualization...</div></div>`;

    try {
      const res = await api.generateChart(dataset, type, config, which);
      plotlyWrap.innerHTML = "";

      if (res.chart) {
        ensurePlotlyDataDecoded(res.chart);
        const themeLayout = getPlotlyThemeLayout();
        const layout = {
          ...res.chart.layout,
          ...themeLayout,
        };
        if (customTitle && layout) {
          layout.title = customTitle;
        }

        Plotly.newPlot(plotlyWrap, res.chart.data, layout, { responsive: true, displayModeBar: true });
        container.querySelector("#chart-state-badge").textContent = `State: ${res.state_label || which}`;
        container.querySelector("#chart-title-label").textContent = customTitle || res.chart.layout?.title?.text || `${type.toUpperCase()} Chart`;

        currentActiveChartData = {
          dataset,
          chartType: type,
          config,
          which,
          chart: res.chart,
          title: customTitle || res.chart.layout?.title?.text || `${type.toUpperCase()} - ${config.x || ''}`,
          createdAt: new Date().toLocaleTimeString(),
        };

        // Show save, reset, and PNG buttons
        container.querySelector("#btn-save-chart").classList.remove("hidden");
        container.querySelector("#btn-new-chart").classList.remove("hidden");
        container.querySelector("#btn-download-png").classList.remove("hidden");
      }
    } catch (e) {
      plotlyWrap.innerHTML = `<div class="alert alert-error">✗ Chart generation failed: ${escHtml(e.message)}</div>`;
    }
  };

  // Save to Gallery button
  container.querySelector("#btn-save-chart").onclick = () => {
    if (!currentActiveChartData) return;
    const id = "viz_" + Date.now();
    savedGallery.push({ ...currentActiveChartData, id });
    showAlert("✓ Visualization saved to gallery!", "success");
    container.querySelector("#gallery-container").innerHTML = renderGalleryCards();
    container.querySelector("#gallery-count-badge").textContent = `${savedGallery.length} saved`;
    wireGalleryButtons(container);
  };

  // New chart reset button
  container.querySelector("#btn-new-chart").onclick = () => {
    container.querySelector("#viz-title-custom").value = "";
    updateInputs();
    showAlert("Builder reset. Select new parameters above.", "info");
  };

  // Export active chart as PNG
  container.querySelector("#btn-download-png").onclick = () => {
    const plotlyWrap = container.querySelector("#plotly-container");
    Plotly.downloadImage(plotlyWrap, {
      format: "png",
      width: 1000,
      height: 600,
      filename: `chart_${Date.now()}`,
    });
  };

  // Jump to gallery button
  container.querySelector("#btn-jump-gallery").onclick = () => {
    const gEl = container.querySelector("#gallery-card");
    if (gEl) gEl.scrollIntoView({ behavior: "smooth" });
  };

  wireGalleryButtons(container);
}

function renderGalleryCards() {
  if (!savedGallery.length) {
    return `
      <div class="empty-state">
        <div style="font-size:2rem; margin-bottom:0.5rem">🖼️</div>
        <div class="empty-title">No saved visualizations yet</div>
        <div class="empty-sub">Generate any chart above and click "Save to Gallery" to bookmark it here.</div>
      </div>
    `;
  }

  return `
    <div class="viz-gallery-grid">
      ${savedGallery.map(item => `
        <div class="viz-card" id="card-${item.id}">
          <div class="viz-card-header">
            <div>
              <div class="viz-card-title">${escHtml(item.title)}</div>
              <div style="font-size:0.7rem; color:var(--ink-faint)">${escHtml(item.chartType)} · ${item.createdAt}</div>
            </div>
            <div style="display:flex; gap:0.35rem">
              <button class="btn btn-secondary btn-sm btn-dl-gallery-png" data-id="${item.id}" title="Export PNG">📷 PNG</button>
              <button class="btn btn-ghost btn-sm btn-ghost-danger btn-del-gallery" data-id="${item.id}" title="Remove">✕</button>
            </div>
          </div>
          <div id="plot-${item.id}" style="width:100%; height:280px"></div>
        </div>
      `).join("")}
    </div>
  `;
}

function wireGalleryButtons(container) {
  savedGallery.forEach(item => {
    const el = container.querySelector(`#plot-${item.id}`);
    if (el && item.chart) {
      const themeLayout = getPlotlyThemeLayout();
      const layout = {
        ...item.chart.layout,
        ...themeLayout,
        margin: { l: 40, r: 20, t: 30, b: 40 },
        height: 280,
      };
      Plotly.newPlot(el, item.chart.data, layout, { responsive: true, displayModeBar: false });
    }
  });

  container.querySelectorAll(".btn-dl-gallery-png").forEach(btn => {
    btn.onclick = () => {
      const id = btn.dataset.id;
      const el = container.querySelector(`#plot-${id}`);
      if (el) {
        Plotly.downloadImage(el, { format: "png", width: 1000, height: 600, filename: `saved_chart_${id}` });
      }
    };
  });

  container.querySelectorAll(".btn-del-gallery").forEach(btn => {
    btn.onclick = () => {
      const id = btn.dataset.id;
      const idx = savedGallery.findIndex(i => i.id === id);
      if (idx !== -1) {
        savedGallery.splice(idx, 1);
        container.querySelector("#gallery-container").innerHTML = renderGalleryCards();
        container.querySelector("#gallery-count-badge").textContent = `${savedGallery.length} saved`;
        wireGalleryButtons(container);
        showAlert("Removed chart from gallery.", "info");
      }
    };
  });
}

function optSelect(label, id, options) {
  return `
    <div class="form-group">
      <label class="form-label">${escHtml(label)}</label>
      <select class="form-select" id="${id}">
        ${options.map(o => `<option value="${escHtml(o)}">${escHtml(o)}</option>`).join("")}
      </select>
    </div>
  `;
}
