/* analysis.js — Dataset overview / quality analysis page */
import * as api from "./api.js";
import { navigate, severityBadge, fmtNum, escHtml, renderNoDatasetState } from "./app.js";

export async function renderOverview(container, dataset) {
  try {
    const st = await api.getDatasetState(dataset);
    if (!st || st.state === "empty") {
      renderNoDatasetState(container, "Dataset Overview", dataset);
      return;
    }
  } catch {
    renderNoDatasetState(container, "Dataset Overview", dataset);
    return;
  }

  container.innerHTML = `<div class="loading-overlay" style="min-height:200px"><div class="spinner spinner-lg"></div><div class="loading-text">Loading analysis...</div></div>`;
  try {
    let res;
    try { res = await api.getAnalysis(dataset); }
    catch { res = await api.analyze(dataset); }
    renderAnalysis(container, res.analysis, dataset);
  } catch (e) {
    container.innerHTML = `<div class="alert alert-error">✗ ${escHtml(e.message)}</div>`;
  }
}

function renderAnalysis(container, a, dataset) {
  const qs = a.quality_score || {};
  const schema = a.schema || {};
  const missing = a.missing || {};
  const dups = a.duplicates || {};
  const stats = a.stats || {};
  const types = a.types || {};
  const outliers = a.outliers || {};

  container.innerHTML = `
    <div id="ov-alerts"></div>

    <!-- Workflow Progress -->
    <div class="card" style="padding:0.875rem 1.25rem">
      <div class="workflow-steps">
        <div class="workflow-step done">✓ Upload</div><div class="workflow-arrow">→</div>
        <div class="workflow-step active">📊 Analysis</div><div class="workflow-arrow">→</div>
        <div class="workflow-step">⚠️ Issues</div><div class="workflow-arrow">→</div>
        <div class="workflow-step">📈 Visualize</div><div class="workflow-arrow">→</div>
        <div class="workflow-step">🧹 Clean</div><div class="workflow-arrow">→</div>
        <div class="workflow-step">✅ Finalize</div><div class="workflow-arrow">→</div>
        <div class="workflow-step">📄 Report</div>
      </div>
    </div>

    <!-- Health Overview -->
    <div class="card">
      <div class="card-title">🏥 Dataset Health Overview</div>
      <div class="score-ring-wrap">
        <div class="score-ring" style="background:${scoreColor(qs.score).bg}; color:${scoreColor(qs.score).fg}">
          <span>${qs.score ?? "—"}</span>
        </div>
        <div class="score-label-block">
          <div class="score-num" style="color:${scoreColor(qs.score).fg}">${qs.score ?? "—"}<span style="font-size:1rem; color:#94a3b8">/100</span></div>
          <div class="score-grade" style="color:${scoreColor(qs.score).fg}">${qs.label ?? ""}</div>
          <div style="font-size:0.75rem; color:#64748b; margin-top:0.25rem">Overall Data Quality Score</div>
        </div>
      </div>
      <div id="score-factors" style="margin-top:1.25rem">${renderFactors(qs.factors || [])}</div>
    </div>

    <!-- Overview Stats -->
    <div class="grid-4">
      <div class="stat-card"><div class="stat-label">Total Rows</div><div class="stat-value">${schema.row_count ?? "—"}</div></div>
      <div class="stat-card"><div class="stat-label">Total Columns</div><div class="stat-value">${schema.col_count ?? "—"}</div></div>
      <div class="stat-card"><div class="stat-label">Missing Values</div><div class="stat-value" style="color:${missing.total_missing ? '#f97316' : '#22c55e'}">${missing.total_missing ?? 0}</div><div class="stat-sub">${missing.missing_pct_overall ?? 0}% of cells</div></div>
      <div class="stat-card"><div class="stat-label">Duplicate Rows</div><div class="stat-value" style="color:${dups.total_duplicates ? '#f97316' : '#22c55e'}">${dups.total_duplicates ?? 0}</div><div class="stat-sub">${dups.duplicate_pct ?? 0}% of rows</div></div>
    </div>
    <div class="grid-4">
      <div class="stat-card"><div class="stat-label">Type Issues</div><div class="stat-value" style="color:${types.columns_with_issues ? '#f97316' : '#22c55e'}">${types.columns_with_issues ?? 0}</div><div class="stat-sub">columns affected</div></div>
      <div class="stat-card"><div class="stat-label">Outlier Columns</div><div class="stat-value" style="color:#3b82f6">${outliers.columns_with_outliers ?? 0}</div><div class="stat-sub">potential anomalies</div></div>
      <div class="stat-card"><div class="stat-label">Issues Total</div><div class="stat-value">${(a.issue_center || []).filter(i => (i.count ?? 0) > 0 && i.category !== 'Schema Problems' && i.category !== 'Schema Issues').length}</div><div class="stat-sub">detected issues</div></div>
      <div class="stat-card"><div class="stat-label">Empty Rows</div><div class="stat-value">${schema.empty_rows ?? 0}</div></div>
    </div>

    <!-- Column List -->
    <div class="card">
      <div class="card-title">📋 Column Overview</div>
      <div class="data-table-wrap">
        <table class="data-table">
          <thead><tr><th>Column</th><th>Type</th><th>Non-Null</th><th>Missing</th><th>Missing %</th><th>Unique</th><th>Sample Values</th></tr></thead>
          <tbody>
            ${(schema.columns || []).map(col => `
              <tr>
                <td><strong>${escHtml(col.name)}</strong></td>
                <td><span class="badge badge-neutral">${escHtml(col.dtype)}</span></td>
                <td>${col.total - col.missing_count}</td>
                <td>${col.missing_count > 0 ? `<span style="color:#f97316">${col.missing_count}</span>` : "0"}</td>
                <td>${col.missing_pct > 0 ? `<span style="color:#f97316">${col.missing_pct}%</span>` : "0%"}</td>
                <td>${col.unique_count}</td>
                <td style="color:#64748b; font-size:0.75rem">${(col.sample_values || []).slice(0,3).map(escHtml).join(", ")}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Numerical Stats -->
    ${stats.numerical && stats.numerical.length ? `
    <div class="card">
      <div class="card-title">📊 Numerical Statistics</div>
      <div class="data-table-wrap">
        <table class="data-table">
          <thead><tr><th>Column</th><th>Count</th><th>Mean</th><th>Median</th><th>Std</th><th>Min</th><th>Max</th><th>IQR</th><th>Skewness</th></tr></thead>
          <tbody>
            ${stats.numerical.map(s => s.insufficient_data ? `
              <tr>
                <td><strong>${escHtml(s.column)}</strong></td>
                <td colspan="8" style="color:var(--ink-faint); font-style:italic">Insufficient data for reliable analysis</td>
              </tr>
            ` : `
              <tr>
                <td><strong>${escHtml(s.column)}</strong></td>
                <td>${s.count}</td>
                <td>${fmtNum(s.mean)}</td>
                <td>${fmtNum(s.median)}</td>
                <td>${fmtNum(s.std)}</td>
                <td>${fmtNum(s.min)}</td>
                <td>${fmtNum(s.max)}</td>
                <td>${fmtNum(s.iqr)}</td>
                <td title="${escHtml(s.skewness_interpretation)}">${fmtNum(s.skewness, 3)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </div>` : ""}

    <!-- Categorical Stats -->
    ${stats.categorical && stats.categorical.length ? `
    <div class="card">
      <div class="card-title">📊 Categorical Statistics</div>
      <div class="data-table-wrap">
        <table class="data-table">
          <thead><tr><th>Column</th><th>Count</th><th>Missing</th><th>Unique</th><th>Most Common</th><th>Top Frequency</th></tr></thead>
          <tbody>
            ${stats.categorical.map(c => c.insufficient_data ? `
              <tr>
                <td><strong>${escHtml(c.column)}</strong></td>
                <td colspan="5" style="color:var(--ink-faint); font-style:italic">Insufficient data for reliable analysis</td>
              </tr>
            ` : `
              <tr>
                <td><strong>${escHtml(c.column)}</strong></td>
                <td>${c.count}</td>
                <td>${c.missing}</td>
                <td>${c.unique_count}</td>
                <td>${escHtml(c.most_common ?? "—")}</td>
                <td>${c.most_common_count}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </div>` : ""}

    <!-- Quick Actions -->
    <div class="card">
      <div class="card-title">⚡ Next Steps</div>
      <div style="display:flex; flex-wrap:wrap; gap:0.75rem">
        <button class="btn btn-warning" id="btn-go-issues">⚠️ View Issue Center</button>
        <button class="btn btn-purple" id="btn-go-viz">📈 Visualize Data</button>
        <button class="btn btn-primary" id="btn-go-clean">🧹 Cleaning Studio</button>
        <button class="btn btn-ghost" id="btn-reanalyze">🔄 Re-Analyze</button>
      </div>
    </div>
  `;

  container.querySelector("#btn-go-issues").onclick = () => navigate("issues", { dataset });
  container.querySelector("#btn-go-viz").onclick = () => navigate("viz", { dataset });
  container.querySelector("#btn-go-clean").onclick = () => navigate("cleaning", { dataset });
  container.querySelector("#btn-reanalyze").onclick = async () => {
    container.querySelector("#ov-alerts").innerHTML = `<div class="alert alert-info">🔄 Re-analyzing...</div>`;
    try {
      const r = await api.analyze(dataset);
      renderAnalysis(container, r.analysis, dataset);
    } catch (e) {
      container.querySelector("#ov-alerts").innerHTML = `<div class="alert alert-error">✗ ${e.message}</div>`;
    }
  };
}

function renderFactors(factors) {
  if (!factors.length) return "";
  return factors.map(f => {
    let barWidth = 0;
    let barBg = '#22c55e';
    let isZero = false;
    let penaltyText = "0";
    let penaltyColor = "#166534";

    if (f.informational) {
      const outlierCount = f.outlier_cols_count || 0;
      const pct = f.informational_pct || (outlierCount > 0 ? 35 : 0);
      if (outlierCount > 0 || pct > 0) {
        barWidth = Math.min(100, Math.max(12, pct));
        barBg = 'linear-gradient(90deg, #fbbf24, #d97706)';
        penaltyText = "ℹ";
        penaltyColor = "#d97706";
      } else {
        barWidth = 0;
        isZero = true;
        penaltyText = "✓";
        penaltyColor = "#166534";
      }
    } else {
      if (f.penalty > 0) {
        barWidth = Math.min(100, (f.penalty / (f.weight || 1)) * 100);
        barBg = 'linear-gradient(90deg, #f87171, #ef4444)';
        penaltyText = `-${f.penalty}`;
        penaltyColor = "#ef4444";
      } else {
        barWidth = 0;
        isZero = true;
        penaltyText = "0";
        penaltyColor = "#166534";
      }
    }

    return `
      <div class="factor-row">
        <div class="factor-name">${escHtml(f.name)}</div>
        <div class="factor-bar-wrap">
          <div class="factor-bar ${isZero ? 'zero' : ''}" style="width:${barWidth}%; background:${barBg}"></div>
        </div>
        <div class="factor-penalty" style="color:${penaltyColor}; font-weight:800">${penaltyText}</div>
        <div class="factor-info">${escHtml(f.value)}</div>
      </div>
    `;
  }).join("");
}

function scoreColor(score) {
  if (score === null || score === undefined) return { bg: "#f1f5f9", fg: "#64748b" };
  if (score >= 90) return { bg: "#dcfce7", fg: "#15803d" };
  if (score >= 75) return { bg: "#dbeafe", fg: "#1d4ed8" };
  if (score >= 60) return { bg: "#fef3c7", fg: "#d97706" }; // Amber/Orange for Fair scores like 72
  if (score >= 40) return { bg: "#ffedd5", fg: "#c2410c" };
  return { bg: "#fee2e2", fg: "#b91c1c" };
}
