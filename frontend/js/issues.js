/* issues.js — Data Quality Issue Center */
import * as api from "./api.js";
import { navigate, severityBadge, showModal, escHtml, renderNoDatasetState } from "./app.js";

export async function renderIssues(container, dataset) {
  try {
    const st = await api.getDatasetState(dataset);
    if (!st || st.state === "empty") {
      renderNoDatasetState(container, "Issue Center", dataset);
      return;
    }
  } catch {
    renderNoDatasetState(container, "Issue Center", dataset);
    return;
  }

  container.innerHTML = `<div class="loading-overlay" style="min-height:200px"><div class="spinner spinner-lg"></div><div class="loading-text">Loading issues...</div></div>`;
  try {
    const res = await api.getAnalysis(dataset);
    renderIssueCenter(container, res.analysis, dataset);
  } catch (e) {
    container.innerHTML = `<div class="alert alert-error">✗ ${escHtml(e.message)}</div>`;
  }
}

function renderIssueCenter(container, a, dataset) {
  const rawIssues = (a.issue_center || []).filter(i => {
    // A card must disappear when its count reaches 0. Never show a count that opens to an empty list.
    const count = i.count ?? 0;
    if (count <= 0) return false;
    if (Array.isArray(i.affected_indices) && i.affected_indices.length === 0 && (i.category === "Data-Type Issues" || i.category === "Missing Values" || i.category === "Duplicate Rows" || i.category === "Suspicious Values" || i.category === "Category Inconsistencies" || i.category === "Potential Outliers")) {
      return false;
    }
    // Remove Schema Problems from single-dataset analysis
    if (i.category === "Schema Problems" || i.category === "Schema Issues") {
      return false;
    }
    return true;
  });
  const recs = a.recommendations || [];

  // Map recommendations into issues strictly by category and column (Item 5 fix: prevent category cross-pollution)
  const enrichedIssues = rawIssues.map(issue => {
    const match = recs.find(r => 
      (issue.column && r.column === issue.column && (r.category === issue.category || r.action_hint === issue.action_hint)) ||
      (!issue.column && r.category === issue.category)
    );
    return {
      ...issue,
      recommendation: match ? match.recommendation : (issue.recommendation || null),
      recWhy: match ? match.why : (issue.why || null),
    };
  });

  const getCatCount = (filterName) => {
    if (filterName === "all") return enrichedIssues.length;
    return enrichedIssues.filter(i => {
      if (filterName === "Suspicious Values") {
        return i.category === "Suspicious Values" || (i.category_type === "invalid" && !i.category.includes("Inconsisten"));
      }
      if (filterName === "Category Inconsistencies") {
        return i.category === "Category Inconsistencies" || i.category_type === "inconsistency";
      }
      return i.category === filterName;
    }).length;
  };

  container.innerHTML = `
    <div id="issue-alerts"></div>

    <div class="card">
      <div class="card-title">⚠️ Data Quality Issue Center</div>
      <p style="color:var(--ink-faint); font-size:0.8125rem; margin-bottom:1rem">
        Detected quality problems, potential anomalies, and data-type inconsistencies categorized by severity and type.
      </p>

      <div style="display:flex; gap:0.5rem; margin-bottom:1.25rem; flex-wrap:wrap">
        <button class="btn btn-primary btn-sm filter-btn" data-filter="all">All Issues (${getCatCount("all")})</button>
        <button class="btn btn-secondary btn-sm filter-btn" data-filter="Missing Values">Missing Values (${getCatCount("Missing Values")})</button>
        <button class="btn btn-secondary btn-sm filter-btn" data-filter="Duplicate Rows">Duplicate Rows (${getCatCount("Duplicate Rows")})</button>
        <button class="btn btn-secondary btn-sm filter-btn" data-filter="Data-Type Issues">Data-Type Issues (${getCatCount("Data-Type Issues")})</button>
        <button class="btn btn-secondary btn-sm filter-btn" data-filter="Suspicious Values">Suspicious Values (${getCatCount("Suspicious Values")})</button>
        <button class="btn btn-secondary btn-sm filter-btn" data-filter="Category Inconsistencies">Category Inconsistencies (${getCatCount("Category Inconsistencies")})</button>
        <button class="btn btn-secondary btn-sm filter-btn" data-filter="Potential Outliers">Potential Outliers (${getCatCount("Potential Outliers")})</button>
      </div>

      <div id="issue-list-container">
        ${renderIssueList(enrichedIssues)}
      </div>
    </div>
  `;

  // Filter tabs wiring
  container.querySelectorAll(".filter-btn").forEach(btn => {
    btn.onclick = () => {
      container.querySelectorAll(".filter-btn").forEach(b => {
        b.classList.remove("btn-primary");
        b.classList.add("btn-secondary");
      });
      btn.classList.remove("btn-secondary");
      btn.classList.add("btn-primary");
      const f = btn.dataset.filter;
      const filtered = f === "all" ? enrichedIssues : enrichedIssues.filter(i => {
        if (f === "Suspicious Values") {
          return i.category === "Suspicious Values" || (i.category_type === "invalid" && !i.category.includes("Inconsisten"));
        }
        if (f === "Category Inconsistencies") {
          return i.category === "Category Inconsistencies" || i.category_type === "inconsistency";
        }
        return i.category === f;
      });
      container.querySelector("#issue-list-container").innerHTML = renderIssueList(filtered);
      wireIssueButtons(container, dataset, filtered);
    };
  });

  wireIssueButtons(container, dataset, enrichedIssues);
}

function renderIssueList(issues) {
  if (!issues.length) {
    return `
      <div class="empty-state">
        <div style="font-size:2.5rem; margin-bottom:0.5rem">🎉</div>
        <div class="empty-title">No issues in this category!</div>
        <div class="empty-sub">Your dataset meets quality standards for this category.</div>
      </div>
    `;
  }

  return issues.map((i, idx) => `
    <div class="issue-card ${i.severity}" style="margin-bottom:1rem">
      <div style="display:flex; align-items:center; justify-content:space-between; gap:0.5rem; margin-bottom:0.35rem">
        <div style="display:flex; align-items:center; gap:0.5rem; font-weight:700; color:var(--ink); font-size:0.875rem">
          ${severityBadge(i.severity)}
          <span>${escHtml(i.category)} ${i.column ? `— Column '${escHtml(i.column)}'` : ''}</span>
        </div>
        <div style="font-size:0.75rem; color:var(--ink-faint)">
          Affected: <strong>${i.count}</strong> ${i.pct !== null && i.pct !== undefined ? `(${i.pct}%)` : ''}
        </div>
      </div>

      <div style="font-size:0.8125rem; color:var(--ink-soft); line-height:1.45; margin-bottom:0.5rem">
        ${escHtml(i.description)}
      </div>

      ${i.recommendation ? `
        <div style="margin-bottom:0.75rem; padding:0.6rem 0.85rem; background:var(--info-bg); border-radius:8px; border-left:3px solid var(--info); font-size:0.8125rem">
          <div style="font-weight:700; color:var(--info); margin-bottom:0.15rem">💡 Recommendation:</div>
          <div style="color:var(--ink-soft); line-height:1.4">${escHtml(i.recommendation)}</div>
        </div>
      ` : ''}

      <div style="display:flex; gap:0.5rem; align-items:center; flex-wrap:wrap">
        ${i.affected_indices && i.affected_indices.length ? `
          <button class="btn btn-secondary btn-sm ${i.category === 'Data-Type Issues' ? 'btn-inspect-type' : 'btn-inspect'}" data-idx="${idx}" data-col="${escHtml(i.column || '')}">
            Show Affected Records (${i.affected_indices.length})
          </button>
        ` : (i.category === 'Data-Type Issues' && i.column ? `
          <button class="btn btn-secondary btn-sm btn-inspect-type" data-idx="${idx}" data-col="${escHtml(i.column || '')}">
            Show Affected Records
          </button>
        ` : '')}
        ${(i.category === "Category Inconsistencies" || i.category_type === "inconsistency") ? `
          <button class="btn btn-primary btn-sm btn-action" data-hint="resolve_suspicious" data-col="${escHtml(i.column || '')}">
            Standardize / Resolve →
          </button>
        ` : i.category === "Suspicious Values" ? `
          <button class="btn btn-danger btn-sm btn-quick-del-susp" data-idx="${idx}" title="Delete rows containing suspicious values">
            🗑️ Delete Affected Row(s) (Default)
          </button>
          <button class="btn btn-primary btn-sm btn-action" data-hint="resolve_suspicious" data-col="${escHtml(i.column || '')}">
            Resolve in Modal →
          </button>
        ` : i.category === "Data-Type Issues" ? `
          <button class="btn btn-primary btn-sm btn-action" data-hint="repair_type" data-col="${escHtml(i.column || '')}" data-target="${escHtml(i.recommended_type || '')}">
            Apply Action →
          </button>
        ` : `
          <button class="btn btn-primary btn-sm btn-action" data-hint="${i.action_hint || ''}" data-col="${escHtml(i.column || '')}">
            Apply Action →
          </button>
        `}
      </div>
    </div>
  `).join("");
}

function wireIssueButtons(container, dataset, currentIssues) {
  // Standard inspect for missing, duplicates, suspicious, outliers
  container.querySelectorAll(".btn-inspect").forEach(btn => {
    btn.onclick = async () => {
      const idx = parseInt(btn.dataset.idx);
      const issue = currentIssues[idx];
      if (!issue || !issue.affected_indices || !issue.affected_indices.length) return;

      try {
        const recordsRes = await api.getAffectedRows(dataset, issue.affected_indices);
        showModal({
          title: `Affected Records (${recordsRes.records ? recordsRes.records.length : 0}) — ${issue.category}`,
          body: renderAffectedModalTable(recordsRes, issue),
          showCancel: false,
          confirmText: "Close",
        });
      } catch (e) {
        showAlert(e.message, "error");
      }
    };
  });

  // Dedicated inspect for Data-Type Issues (Item 4)
  container.querySelectorAll(".btn-inspect-type").forEach(btn => {
    btn.onclick = async () => {
      const idx = parseInt(btn.dataset.idx);
      const issue = currentIssues[idx];
      const col = btn.dataset.col || (issue && issue.column);
      if (!col) return;

      await showTypeIssueRecordsModal(dataset, col, issue);
    };
  });

  // Default fast one-click row deletion for suspicious values
  container.querySelectorAll(".btn-quick-del-susp").forEach(btn => {
    btn.onclick = () => {
      const idx = parseInt(btn.dataset.idx);
      const issue = currentIssues[idx];
      if (!issue || !issue.affected_indices || !issue.affected_indices.length) return;
      const count = issue.affected_indices.length;

      showModal({
        title: `Delete ${count} Row(s) with Suspicious Values?`,
        body: `
          <p>Delete all ${count} record(s) flagged for suspicious / invalid values in column <strong>'${escHtml(issue.column || '')}'</strong>?</p>
          <div style="margin-top:0.75rem; padding:0.6rem; background:var(--danger-bg); border:1px solid var(--danger-border); border-radius:6px; font-size:0.75rem; color:var(--danger)">
            ⚠️ Affected row indices: ${issue.affected_indices.slice(0, 15).join(", ")}${count > 15 ? '...' : ''}
          </div>
        `,
        confirmText: "Delete Affected Row(s)",
        confirmClass: "btn-danger",
        onConfirm: async () => {
          try {
            await api.deleteRows(dataset, issue.affected_indices);
            showAlert(`✓ Deleted ${count} row(s) containing suspicious values.`, "success");
            renderIssues(container, dataset);
          } catch (e) {
            showAlert(e.message, "error");
          }
        }
      });
    };
  });

  const goClean = (hint, col, target) => {
    navigate("cleaning", { dataset, hint, column: col, target });
  };

  container.querySelectorAll(".btn-action").forEach(btn => {
    btn.onclick = () => goClean(btn.dataset.hint, btn.dataset.col, btn.dataset.target);
  });
}

async function showTypeIssueRecordsModal(dataset, column, issue) {
  let curPage = 0;
  const pageSize = 20;

  async function loadModalPage(page = 0) {
    try {
      const res = await api.getTypeIssueRows(dataset, column, page, pageSize);
      const total = res.total_affected || 0;
      const totalPages = res.total_pages || 1;
      const rows = res.rows || [];

      const bodyHtml = `
        <div style="margin-bottom:0.75rem; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem">
          <div style="font-size:0.8125rem; color:var(--ink-soft)">
            Column: <strong>'${escHtml(column)}'</strong> | Current: <code>${escHtml(res.current_dtype || '')}</code> | Proposed: <code>${escHtml(res.proposed_target || '')}</code>
          </div>
          <button class="btn btn-primary btn-sm" id="btn-open-repair-from-modal">🔧 Repair in Modal →</button>
        </div>

        <div class="data-table-wrap" style="max-height:420px; overflow-y:auto">
          <table class="data-table">
            <thead>
              <tr>
                <th style="width:60px">Row #</th>
                <th>Stored Value</th>
                <th>Stored Type</th>
                <th>Proposed Converted Value</th>
                <th>Convertibility Status</th>
              </tr>
            </thead>
            <tbody>
              ${rows.length === 0 ? `<tr><td colspan="5" style="text-align:center; color:var(--ink-faint); padding:1.5rem">No affected rows found.</td></tr>` : rows.map(r => `
                <tr>
                  <td><strong>${r.row_index}</strong></td>
                  <td><code>${escHtml(r.current_value)}</code></td>
                  <td><span class="badge badge-secondary" style="font-size:0.7rem">${escHtml(r.current_type)}</span></td>
                  <td>${r.proposed_value !== null && r.proposed_value !== undefined ? `<strong style="color:var(--accent)">${escHtml(r.proposed_value)}</strong>` : '<span style="color:var(--ink-faint)">—</span>'}</td>
                  <td>
                    ${r.can_convert ? `
                      <span class="badge badge-success" style="font-size:0.7rem">✓ Ready to Convert</span>
                    ` : `
                      <span class="badge badge-danger" style="font-size:0.7rem" title="${escHtml(r.fail_reason || '')}">⚠️ ${escHtml(r.fail_reason || 'Cannot convert')}</span>
                    `}
                  </td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>

        ${totalPages > 1 ? `
          <div style="display:flex; justify-content:space-between; align-items:center; margin-top:0.75rem; font-size:0.8125rem">
            <span>Page ${page + 1} of ${totalPages} (${total} total affected rows)</span>
            <div style="display:flex; gap:0.35rem">
              <button class="btn btn-secondary btn-sm" id="btn-type-prev" ${page <= 0 ? 'disabled' : ''}>← Previous</button>
              <button class="btn btn-secondary btn-sm" id="btn-type-next" ${page >= totalPages - 1 ? 'disabled' : ''}>Next →</button>
            </div>
          </div>
        ` : ''}
      `;

      showModal({
        title: `Affected Records (${total}) — Data-Type Issue: '${column}'`,
        body: bodyHtml,
        showCancel: false,
        confirmText: "Close",
      });

      const backdrop = document.getElementById("modal-backdrop");
      const btnRepair = backdrop?.querySelector("#btn-open-repair-from-modal");
      if (btnRepair) {
        btnRepair.onclick = () => {
          const btnClose = backdrop.querySelector("#modal-close");
          if (btnClose) btnClose.click();
          navigate("cleaning", { dataset, hint: "repair_type", column, target: res.proposed_target });
        };
      }

      const btnPrev = backdrop?.querySelector("#btn-type-prev");
      if (btnPrev) btnPrev.onclick = () => loadModalPage(page - 1);
      const btnNext = backdrop?.querySelector("#btn-type-next");
      if (btnNext) btnNext.onclick = () => loadModalPage(page + 1);

    } catch (e) {
      showAlert(e.message, "error");
    }
  }

  await loadModalPage(0);
}

function renderAffectedModalTable(res, currentIssue = null) {
  if (!res.records || !res.records.length) return "<p style='color:var(--ink-faint)'>No records found.</p>";
  const cols = res.columns || [];
  const curCat = (currentIssue && currentIssue.category) ? currentIssue.category.toLowerCase() : "";
  const curCol = (currentIssue && currentIssue.column) ? currentIssue.column : null;

  // Map row details from currentIssue if available
  const detailsByRow = new Map();
  if (currentIssue && Array.isArray(currentIssue.row_details)) {
    currentIssue.row_details.forEach(d => {
      if (d && d.row !== undefined) detailsByRow.set(d.row, d);
    });
  }

  let html = `
    <div style="margin-bottom:0.75rem; padding:0.65rem 0.85rem; background:var(--surface-2); border-left:4px solid var(--primary); border-radius:4px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem">
      <div>
        <div style="font-weight:700; color:var(--ink); font-size:0.875rem">
          ${currentIssue ? escHtml(currentIssue.category) : 'Affected Records'} ${curCol ? `— Column: '<strong>${escHtml(curCol)}</strong>'` : ''}
        </div>
        <div style="font-size:0.8rem; color:var(--ink-soft); margin-top:2px">
          ${currentIssue && currentIssue.description ? escHtml(currentIssue.description) : 'Records flagged by quality profiler.'}
        </div>
      </div>
      ${curCol ? `<span class="badge badge-warning" style="font-size:0.7rem; font-weight:700">Target Column: ${escHtml(curCol)}</span>` : ''}
    </div>
    <div class="data-table-wrap" style="max-height:420px; overflow-y:auto">
      <table class="data-table">
        <thead>
          <tr>
            <th style="width:75px">Row #</th>
            ${cols.map(c => `
              <th ${c === curCol ? 'style="background:rgba(239, 68, 68, 0.12); border-bottom:2px solid #ef4444; color:#b91c1c"' : ''}>
                ${escHtml(c)}
                ${c === curCol ? '<span class="badge badge-danger" style="font-size:0.6rem; margin-left:3px; vertical-align:middle">FLAGGED VALUE</span>' : ''}
              </th>
            `).join("")}
          </tr>
        </thead>
        <tbody>
  `;

  res.records.forEach((row, i) => {
    const rowId = row._row_id !== undefined ? row._row_id : i;
    const alsoFlagged = Array.isArray(row._also_flagged) ? row._also_flagged : [];
    const otherFlags = alsoFlagged.filter(f => !f.toLowerCase().includes(curCat));
    const cellFlags = row._cell_flags || {};
    const specificDetail = detailsByRow.get(rowId) || (curCol && cellFlags[curCol]);

    html += `
      <tr>
        <td>
          <strong>${rowId}</strong>
          ${otherFlags.length > 0 ? `
            <div style="margin-top:2px">
              <span class="badge badge-warning" style="font-size:0.6rem; padding:0.15rem 0.35rem; display:inline-block" title="Flagged across multiple categories">
                also: ${escHtml(otherFlags.join(", "))}
              </span>
            </div>
          ` : ''}
        </td>
        ${cols.map(c => {
          const val = row[c];
          const valDisplay = val === null ? '<span class="null-cell">null</span>' : escHtml(val);
          if (c === curCol) {
            const reason = (specificDetail && specificDetail.reason) || (currentIssue && currentIssue.description) || "Flagged value";
            return `
              <td style="background: rgba(239, 68, 68, 0.08); border-left: 2px solid #ef4444; border-right: 2px solid #ef4444">
                <div style="font-weight:700; color:var(--ink)">${valDisplay}</div>
                <div style="font-size:0.7rem; color:#b91c1c; margin-top:3px; line-height:1.2; font-weight:600" title="${escHtml(reason)}">
                  ⚠️ ${escHtml(reason)}
                </div>
              </td>
            `;
          }
          return `<td>${valDisplay}</td>`;
        }).join("")}
      </tr>
    `;
  });
  html += "</tbody></table></div>";
  return html;
}
