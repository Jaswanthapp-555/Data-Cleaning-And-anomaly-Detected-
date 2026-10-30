/* comparison.js — Two Dataset Comparison Dashboard */
import * as api from "./api.js";
import { navigate, severityBadge, fmtNum, escHtml, showAlert } from "./app.js";

export async function renderComparison(container) {
  container.innerHTML = `<div class="loading-overlay" style="min-height:200px"><div class="spinner spinner-lg"></div><div class="loading-text">Analyzing dataset comparison...</div></div>`;

  try {
    // Check if both are finalized first
    const [refSt, curSt] = await Promise.all([
      api.getDatasetState("ref"),
      api.getDatasetState("cur"),
    ]);

    if (!refSt || refSt.state === "empty" || !curSt || curSt.state === "empty") {
      container.innerHTML = `
        <div class="card" style="max-width:650px; margin:2rem auto; text-align:center; padding:2rem 1.5rem">
          <div style="font-size:3rem; margin-bottom:0.75rem">⚖️</div>
          <div class="card-title" style="justify-content:center; margin-bottom:0.5rem">Two Dataset Comparison</div>
          <p style="color:var(--ink-faint); font-size:0.875rem; margin-bottom:1.5rem">
            Both <strong>Reference</strong> and <strong>Current</strong> datasets must be uploaded to run the comparison engine.
          </p>
          <div style="display:flex; justify-content:center; gap:0.75rem">
            <button class="btn btn-primary" id="btn-goto-ref">Upload Reference →</button>
            <button class="btn btn-purple" id="btn-goto-cur">Upload Current →</button>
          </div>
        </div>
      `;
      const btnRef = container.querySelector("#btn-goto-ref");
      const btnCur = container.querySelector("#btn-goto-cur");
      if (btnRef) btnRef.onclick = () => navigate("upload-ref");
      if (btnCur) btnCur.onclick = () => navigate("upload-cur");
      return;
    }

    const bothFinalized = refSt.state === "finalized" && curSt.state === "finalized";

    if (bothFinalized) {
      let res;
      try { res = await api.getComparison(); }
      catch { res = await api.runComparison(); }
      renderComparisonDashboard(container, res.comparison, false);
    } else {
      // Run preview comparison on working datasets
      const res = await api.runPreviewComparison();
      renderComparisonDashboard(container, res.comparison, true);
    }
  } catch (e) {
    container.innerHTML = `
      <div class="card">
        <div class="card-title">⚖️ Comparison Error</div>
        <div class="alert alert-error">✗ ${escHtml(e.message)}</div>
      </div>
    `;
  }
}

function renderComparisonDashboard(container, c, isPreview) {
  const s = c.summary || {};
  const schema = c.schema || {};
  const q = c.quality || {};
  const drift = c.drift || [];
  const rowMatch = c.row_match || {};

  container.innerHTML = `
    <!-- Mode Banner -->
    ${isPreview ? `
      <div style="padding:1rem 1.25rem; background:var(--warning-bg); border:1px solid var(--warning-border); border-radius:12px; margin-bottom:1.25rem; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:0.75rem">
        <div>
          <div style="font-weight:800; color:var(--ink); font-size:0.9375rem; display:flex; align-items:center; gap:0.4rem">
            <span>🔍 Working Copy Preview Mode</span>
            <span class="badge badge-warning">Unfinalized</span>
          </div>
          <div style="color:var(--ink-soft); font-size:0.75rem; margin-top:0.2rem">
            This comparison reflects the active working datasets. To generate official comparison reports, finalize both datasets in Review &amp; Finalize.
          </div>
        </div>
        <div style="display:flex; gap:0.5rem">
          <button class="btn btn-primary btn-sm" id="btn-goto-ref-review">Review Ref</button>
          <button class="btn btn-purple btn-sm" id="btn-goto-cur-review">Review Cur</button>
        </div>
      </div>
    ` : `
      <div style="padding:0.75rem 1.25rem; background:var(--success-bg); border:1px solid var(--success-border); border-radius:12px; margin-bottom:1.25rem; display:flex; align-items:center; justify-content:space-between">
        <div style="color:var(--ink); font-size:0.8125rem; font-weight:700">
          ✅ Finalized Comparison — Official baseline audit across Reference and Current datasets.
        </div>
        <button class="btn btn-primary btn-sm" id="btn-goto-reports">Generate Reports →</button>
      </div>
    `}

    <!-- Executive Comparison Narrative (Item 6b) -->
    ${s.narrative ? `
      <div class="card" style="background:linear-gradient(135deg, rgba(59,130,246,0.08) 0%, rgba(99,102,241,0.05) 100%); border-left:4px solid var(--primary); margin-bottom:1.25rem; padding:1.25rem 1.5rem">
        <div style="font-weight:800; color:var(--ink); font-size:1rem; margin-bottom:0.4rem; display:flex; align-items:center; gap:0.5rem">
          <span>📝 Executive Comparison Summary</span>
        </div>
        <p style="color:var(--ink-soft); font-size:0.875rem; line-height:1.55; margin:0">
          ${escHtml(s.narrative)}
        </p>
        ${s.matching_strategy_note ? `
          <div style="margin-top:0.6rem; padding-top:0.5rem; border-top:1px dashed var(--line); font-size:0.8rem; color:var(--primary)">
            <strong>Matching Strategy:</strong> ${escHtml(s.matching_strategy_note)}
          </div>
        ` : ''}
      </div>
    ` : ''}

    <!-- Summary Header Cards -->
    <div class="card">
      <div class="card-title">⚖️ Comparison Summary Dashboard</div>
      <div class="grid-4" style="margin-bottom:1rem">
        <div class="stat-card"><div class="stat-label">Reference Rows / Cols</div><div class="stat-value" style="font-size:1.25rem">${schema.ref_row_count} × ${schema.ref_col_count}</div></div>
        <div class="stat-card"><div class="stat-label">Current Rows / Cols</div><div class="stat-value" style="font-size:1.25rem">${schema.cur_row_count} × ${schema.cur_col_count}</div></div>
        <div class="stat-card">
          <div class="stat-label">Quality Score Shift</div>
          <div class="stat-value" style="color:${q.score_change >= 0 ? 'var(--success)' : 'var(--danger)'}">
            ${q.score_change >= 0 ? '+' : ''}${q.score_change}
          </div>
          <div class="stat-sub">${q.reference_score} → ${q.current_score}</div>
        </div>
        <div class="stat-card"><div class="stat-label">Record Net Shift</div><div class="stat-value">${schema.row_count_change >= 0 ? '+' : ''}${schema.row_count_change}</div></div>
      </div>

      <div class="grid-4">
        <div class="stat-card"><div class="stat-label">Columns Added</div><div class="stat-value" style="color:var(--success)">+${s.columns_added}</div></div>
        <div class="stat-card"><div class="stat-label">Columns Removed</div><div class="stat-value" style="color:var(--danger)">-${s.columns_removed}</div></div>
        <div class="stat-card"><div class="stat-label">New Records</div><div class="stat-value" style="color:var(--success)">+${s.new_records}</div></div>
        <div class="stat-card"><div class="stat-label">Deleted Records</div><div class="stat-value" style="color:var(--danger)">-${s.deleted_records}</div></div>
      </div>
      <div class="grid-3" style="margin-top:1rem">
        <div class="stat-card"><div class="stat-label">Modified Records</div><div class="stat-value">${s.modified_records}</div></div>
        <div class="stat-card"><div class="stat-label">Type Changes</div><div class="stat-value">${s.type_changes}</div></div>
        <div class="stat-card"><div class="stat-label">Distribution Drift Cols</div><div class="stat-value" style="color:${s.drift_columns ? 'var(--warning)' : 'var(--success)'}">${s.drift_columns}</div></div>
      </div>
      <p style="color:var(--ink-faint); font-size:0.75rem; margin-top:0.75rem"><strong>Matching Strategy:</strong> ${escHtml(s.strategy)}</p>
    </div>

    <!-- Schema Comparison -->
    <div class="card">
      <div class="card-title">📐 Schema Comparison</div>
      <div class="grid-3">
        <div>
          <h4 style="font-size:0.8125rem; color:var(--success); margin-bottom:0.35rem">Added Columns (${(schema.added_columns || []).length})</h4>
          ${(schema.added_columns || []).map(col => `<span class="tag tag-added">+ ${escHtml(col)}</span>`).join("") || '<span style="color:var(--ink-faint); font-size:0.75rem">None</span>'}
        </div>
        <div>
          <h4 style="font-size:0.8125rem; color:var(--danger); margin-bottom:0.35rem">Removed Columns (${(schema.removed_columns || []).length})</h4>
          ${(schema.removed_columns || []).map(col => `<span class="tag tag-removed">- ${escHtml(col)}</span>`).join("") || '<span style="color:var(--ink-faint); font-size:0.75rem">None</span>'}
        </div>
        <div>
          <h4 style="font-size:0.8125rem; color:var(--warning); margin-bottom:0.35rem">Type Changes (${(schema.type_changes || []).length})</h4>
          ${(schema.type_changes || []).map(tc => `<span class="tag tag-changed">${escHtml(tc.column)}: ${tc.reference_type} → ${tc.current_type}</span>`).join("") || '<span style="color:var(--ink-faint); font-size:0.75rem">None</span>'}
        </div>
      </div>

      ${(schema.possible_renames || []).length ? `
        <div style="margin-top:1rem; padding:0.75rem; background:var(--warning-bg); border-radius:8px; border:1px solid var(--warning-border)">
          <h4 style="font-size:0.8125rem; color:var(--warning); margin-bottom:0.25rem">Possible Column Renames</h4>
          ${schema.possible_renames.map(r => `<p style="font-size:0.75rem; color:var(--ink)">⚠ '${escHtml(r.reference_column)}' → '${escHtml(r.current_column)}' (confidence: ${r.confidence}) — ${escHtml(r.note)}</p>`).join("")}
        </div>
      ` : ""}
    </div>

    <!-- Most Frequently Changed Columns (Item 6c) -->
    ${(rowMatch.frequently_changed_columns || []).length ? `
    <div class="card">
      <div class="card-title">📊 Most Frequently Changed Columns</div>
      <p style="color:var(--ink-faint); font-size:0.8125rem; margin-bottom:1rem">
        Distribution of record modifications across columns, identifying high-volatility features.
      </p>
      <div class="data-table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>Column Name</th>
              <th>Changed Records Count</th>
              <th>% of Modified Records</th>
              <th style="width:35%">Concentration</th>
            </tr>
          </thead>
          <tbody>
            ${rowMatch.frequently_changed_columns.map(fc => `
              <tr>
                <td><strong>${escHtml(fc.column)}</strong></td>
                <td>${fc.change_count}</td>
                <td><strong>${fc.percent_of_modified}%</strong></td>
                <td>
                  <div style="background:var(--surface-2); border-radius:4px; height:8px; width:100%; overflow:hidden">
                    <div style="background:var(--primary); height:100%; width:${Math.min(100, fc.percent_of_modified)}%"></div>
                  </div>
                </td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </div>
    ` : ""}

    <!-- Cell Level Changes Sample (Item 6d) -->
    ${(rowMatch.modified_records || []).length ? `
    <div class="card">
      <div class="card-title">🔍 Cell-Level Modifications (Sample)</div>
      <div class="data-table-wrap" style="max-height:350px">
        <table class="data-table">
          <thead><tr><th>Record ID</th><th>Column</th><th>Reference Value</th><th>Current Value</th></tr></thead>
          <tbody>
            ${(rowMatch.modified_records || []).slice(0, 50).map(rec =>
              (rec.changes || []).map(ch => `
                <tr>
                  <td><code>${rec.id}</code></td>
                  <td><strong>${escHtml(ch.column)}</strong></td>
                  <td style="color:var(--danger)">${ch.reference_value === null ? '<em>null</em>' : escHtml(ch.reference_value)}</td>
                  <td>
                    <span style="color:var(--success); font-weight:600">${ch.current_value === null ? '<em>null</em>' : escHtml(ch.current_value)}</span>
                    ${ch.anomalous ? `
                      <span class="badge badge-danger" style="margin-left:6px; font-size:0.7rem; font-weight:700" title="${escHtml(ch.anomaly_reason || 'Suspicious value')}">
                        ⚠️ ANOMALY: ${escHtml(ch.anomaly_reason || 'Suspicious')}
                      </span>
                    ` : ''}
                  </td>
                </tr>
              `).join("")
            ).join("")}
          </tbody>
        </table>
      </div>
    </div>
    ` : ""}

    <!-- Column Statistics Comparison (Numerical & Categorical) -->
    ${(c.stats || []).length ? `
    <div class="card">
      <div class="card-title">📊 Column Statistics Comparison</div>
      <div class="data-table-wrap" style="max-height:400px; margin-bottom:1rem">
        <table class="data-table">
          <thead>
            <tr>
              <th>Column</th>
              <th>Type</th>
              <th>Reference Metric</th>
              <th>Current Metric</th>
              <th>Shift / Notes</th>
            </tr>
          </thead>
          <tbody>
            ${(c.stats || []).map(st => {
              if (st.type === "numerical") {
                const rm = st.reference?.mean != null ? fmtNum(st.reference.mean) : '—';
                const cm = st.current?.mean != null ? fmtNum(st.current.mean) : '—';
                const rmed = st.reference?.median != null ? fmtNum(st.reference.median) : '—';
                const cmed = st.current?.median != null ? fmtNum(st.current.median) : '—';
                const diff = (st.current?.mean != null && st.reference?.mean != null) ? fmtNum(st.current.mean - st.reference.mean) : null;
                return `
                  <tr>
                    <td><strong>${escHtml(st.column)}</strong></td>
                    <td><span class="badge badge-info">Numerical</span></td>
                    <td>Mean: <strong>${rm}</strong> &nbsp;·&nbsp; Median: ${rmed} (n=${st.reference?.count ?? 0})</td>
                    <td>Mean: <strong>${cm}</strong> &nbsp;·&nbsp; Median: ${cmed} (n=${st.current?.count ?? 0})</td>
                    <td>${diff !== null ? `<span style="font-weight:700; color:${diff >= 0 ? 'var(--success)' : 'var(--danger)'}">${diff >= 0 ? '+' : ''}${diff} mean shift</span>` : '—'}</td>
                  </tr>
                `;
              } else {
                const ru = st.reference?.unique ?? 0;
                const cu = st.current?.unique ?? 0;
                const rtop = st.reference?.top != null ? escHtml(st.reference.top) : '—';
                const ctop = st.current?.top != null ? escHtml(st.current.top) : '—';
                const newCats = (st.new_categories || []).length ? `<span class="tag tag-added">+${st.new_categories.length} new</span>` : '';
                const remCats = (st.removed_categories || []).length ? `<span class="tag tag-removed">-${st.removed_categories.length} removed</span>` : '';
                return `
                  <tr>
                    <td><strong>${escHtml(st.column)}</strong></td>
                    <td><span class="badge badge-neutral">Categorical</span></td>
                    <td>Unique: <strong>${ru}</strong> &nbsp;·&nbsp; Top: <em>${rtop}</em> (n=${st.reference?.count ?? 0})</td>
                    <td>Unique: <strong>${cu}</strong> &nbsp;·&nbsp; Top: <em>${ctop}</em> (n=${st.current?.count ?? 0})</td>
                    <td>${newCats} ${remCats} ${!newCats && !remCats ? '<span style="color:var(--ink-faint); font-size:0.75rem">Stable categories</span>' : ''}</td>
                  </tr>
                `;
              }
            }).join("")}
          </tbody>
        </table>
      </div>
    </div>
    ` : ""}

    <!-- Distribution Drift (KS Test) -->
    <div class="card">
      <div class="card-title">📈 Statistical Distribution Drift (KS Test)</div>
      <div class="data-table-wrap">
        <table class="data-table">
          <thead><tr><th>Column</th><th>Type</th><th>KS Stat</th><th>p-value</th><th>Ref Mean</th><th>Cur Mean</th><th>Drift Result</th></tr></thead>
          <tbody>
            ${drift.map(d => `
              <tr>
                <td><strong>${escHtml(d.column)}</strong></td>
                <td><span class="badge badge-neutral">${d.type}</span></td>
                <td>${d.ks_available ? d.ks_statistic : 'N/A'}</td>
                <td>${d.ks_available ? d.p_value : 'N/A'}</td>
                <td>${fmtNum(d.ref_mean)}</td>
                <td>${fmtNum(d.cur_mean)}</td>
                <td>${d.drift_detected ? '<span class="badge badge-high">Possible Drift</span>' : '<span class="badge badge-low">No Drift</span>'}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
      <p style="color:var(--ink-faint); font-size:0.75rem; margin-top:0.5rem">
        ⚠ Kolmogorov-Smirnov test applied to numerical distributions (n ≥ 20). Statistical significance does not automatically equal business impact.
      </p>
    </div>
  `;

  if (isPreview) {
    const btnRefRev = container.querySelector("#btn-goto-ref-review");
    const btnCurRev = container.querySelector("#btn-goto-cur-review");
    if (btnRefRev) btnRefRev.onclick = () => navigate("review", { dataset: "ref" });
    if (btnCurRev) btnCurRev.onclick = () => navigate("review", { dataset: "cur" });
  } else {
    const btnRep = container.querySelector("#btn-goto-reports");
    if (btnRep) btnRep.onclick = () => navigate("reports");
  }
}
