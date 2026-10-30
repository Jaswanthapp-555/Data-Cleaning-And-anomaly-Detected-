/* cleaning.js — Cleaning Studio and Change History */
import * as api from "./api.js";
import { navigate, showAlert, showModal, closeModal, escHtml, renderNoDatasetState, updateTopbar } from "./app.js";

let currentPage = 0;
let currentSearch = "";
let currentSortCol = "";
let currentSortAsc = true;
let selectedRows = new Set();
let selectedCols = new Set();

function resetCleaningState() {
  currentPage = 0;
  currentSearch = "";
  currentSortCol = "";
  currentSortAsc = true;
  selectedRows = new Set();
  selectedCols = new Set();
}

export async function renderCleaning(container, dataset, opts = {}) {
  resetCleaningState();

  // Single Source of Truth check
  let st;
  try {
    st = await api.getDatasetState(dataset);
    if (!st || st.state === "empty") {
      renderNoDatasetState(container, "Cleaning Studio", dataset);
      return;
    }
  } catch (err) {
    container.innerHTML = `
      <div class="card">
        <div class="empty-state" style="padding:3rem 1.5rem">
          <div style="font-size:2.5rem; margin-bottom:0.75rem">⚠️</div>
          <div class="empty-title" style="color:var(--danger)">Failed to initialize Cleaning Studio</div>
          <div class="empty-sub" style="margin-bottom:1.25rem; color:var(--ink-faint)">${escHtml(err.message)}</div>
          <button class="btn btn-primary" id="btn-retry-cleaning-init">🔄 Retry</button>
        </div>
      </div>
    `;
    const btn = container.querySelector("#btn-retry-cleaning-init");
    if (btn) btn.onclick = () => renderCleaning(container, dataset, opts);
    return;
  }

  container.innerHTML = `
    <div id="clean-alerts"></div>

    <div class="card">
      <div class="card-title" style="justify-content:space-between">
        <span>🧹 Cleaning Studio — ${escHtml(dataset.toUpperCase())} Dataset</span>
        <button class="btn btn-ghost btn-sm" id="act-goto-history">📋 View Change History →</button>
      </div>
      <p style="color:var(--ink-faint); font-size:0.8125rem; margin-bottom:1.25rem">
        Perform interactive, user-controlled cleaning actions. All actions operate on a working copy; the original dataset remains immutable.
      </p>

      <!-- Missing Values Overview Panel (Issue 10) -->
      <div id="missing-overview-container"></div>

      <!-- Action Toolbar (Issue 10: Grouped Layout) -->
      <div class="toolbar-grouped">
        <!-- Row / Column Actions -->
        <div class="toolbar-group">
          <div class="toolbar-group-label">Row / Column</div>
          <div class="toolbar-group-items">
            <button class="btn btn-secondary btn-sm" id="act-edit-cell">✏️ Edit Cell</button>
            <button class="btn btn-danger btn-sm" id="act-del-rows">🗑️ Delete Selected Row(s)</button>
            <button class="btn btn-danger btn-sm" id="act-del-cols">🗑️ Delete Selected Column(s)</button>
            <button class="btn btn-secondary btn-sm" id="act-rename-col">🏷️ Rename Column</button>
          </div>
        </div>

        <!-- Missing & Duplicate Data -->
        <div class="toolbar-group">
          <div class="toolbar-group-label">Missing &amp; Dups</div>
          <div class="toolbar-group-items">
            <button class="btn btn-primary btn-sm" id="act-fill-missing">💉 Fill Missing Values</button>
            <button class="btn btn-danger btn-sm" id="act-del-col-missing-rows">🗑️ Delete Rows by Column</button>
            <button class="btn btn-danger btn-sm" id="act-del-missing-rows">🗑️ Delete All Rows with Missing</button>
            <button class="btn btn-secondary btn-sm" id="act-rem-dups">👯 Remove Exact Duplicates</button>
          </div>
        </div>

        <!-- Type & Reset -->
        <div class="toolbar-group">
          <div class="toolbar-group-label">Types &amp; Reset</div>
          <div class="toolbar-group-items">
            <button class="btn btn-secondary btn-sm" id="act-repair-type">🔧 Repair Data Type</button>
            <button class="btn btn-secondary btn-sm" id="act-resolve-outlier">🎯 Resolve Outlier</button>
            <button class="btn btn-secondary btn-sm" id="act-resolve-suspicious">⚠️ Resolve Suspicious Values</button>
            <button class="btn btn-ghost btn-sm btn-ghost-danger" id="act-reset" style="margin-left:auto">🔄 Reset to Original</button>
          </div>
        </div>
      </div>

      <!-- Data Table Search/Toolbar -->
      <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:0.75rem; flex-wrap:wrap; gap:0.5rem">
        <div style="display:flex; align-items:center; gap:0.5rem">
          <input type="text" class="form-input" id="clean-search" placeholder="Search rows..." value="${escHtml(currentSearch)}" style="width:220px; padding:0.4rem 0.75rem">
          <button class="btn btn-secondary btn-sm" id="btn-search">Search</button>
          ${currentSearch ? `<button class="btn btn-ghost btn-sm" id="btn-clear-search">Clear</button>` : ''}
        </div>
        <span style="font-size:0.75rem; font-weight:600; color:var(--ink-faint)" id="selection-count">0 row(s), 0 col(s) selected</span>
      </div>

      <!-- Table Container -->
      <div id="cleaning-table-container" style="position:relative; min-height:200px">
        <div class="loading-overlay" style="min-height:180px">
          <div class="spinner spinner-lg"></div>
          <div class="loading-text">Loading dataset rows...</div>
        </div>
      </div>

      <!-- Pagination -->
      <div class="pagination" id="cleaning-pagination"></div>
    </div>
  `;

  const btnGotoHistory = container.querySelector("#act-goto-history");
  if (btnGotoHistory) {
    btnGotoHistory.onclick = () => navigate("history", { dataset });
  }

  wireCleaningActions(container, dataset);

  try {
    await Promise.all([
      loadMissingOverview(container, dataset),
      loadCleaningTable(container, dataset),
    ]);
  } catch (err) {
    console.error("Error loading Cleaning Studio data:", err);
  }

  // Open target modal if navigated with hint/column
  if (opts && opts.hint) {
    if (opts.hint === "repair_type") {
      showRepairTypeModal(dataset, container, opts.column, opts.target);
    } else if (opts.hint === "resolve_suspicious" || opts.hint === "suspicious") {
      showSuspiciousModal(dataset, container, opts.column);
    } else if (opts.hint === "resolve_outlier" || opts.hint === "outliers" || opts.hint === "inspect_outliers") {
      showOutlierModal(dataset, container, opts.column);
    } else if (opts.hint === "fill_missing" || opts.hint === "missing") {
      showFillMissingModal(dataset, opts.column, container);
    } else if (opts.hint === "delete_column_missing") {
      showDeleteColumnMissingModal(dataset, container, opts.column);
    } else if (opts.hint === "duplicates") {
      const btnDups = container.querySelector("#act-rem-dups");
      if (btnDups) btnDups.click();
    }
  } else if (opts && opts.column) {
    showFillMissingModal(dataset, opts.column, container);
  }
}

async function loadMissingOverview(container, dataset) {
  const panel = container.querySelector("#missing-overview-container");
  if (!panel) return;

  panel.innerHTML = `
    <div style="padding:0.75rem 1rem; background:var(--surface-2); border:1px solid var(--line); border-radius:10px; margin-bottom:1.25rem; display:flex; align-items:center; gap:0.75rem">
      <div class="spinner" style="width:16px; height:16px; border-width:2px"></div>
      <span style="font-size:0.8125rem; color:var(--ink-faint)">Loading missing values overview...</span>
    </div>
  `;

  try {
    const res = await api.getAnalysis(dataset);
    const missing = (res && res.analysis && res.analysis.missing) || {};
    const affectedCols = missing.affected_columns || [];

    if (!affectedCols.length) {
      panel.innerHTML = `
        <div style="padding:0.75rem 1rem; background:var(--success-bg); border:1px solid var(--success-border); border-radius:10px; margin-bottom:1.25rem; display:flex; align-items:center; justify-content:space-between">
          <span style="color:var(--success); font-size:0.8125rem; font-weight:600">✓ No missing values detected in working dataset.</span>
          <span class="badge badge-success">0 Missing</span>
        </div>
      `;
      return;
    }

    panel.innerHTML = `
      <div class="missing-overview-panel">
        <div class="missing-overview-header">
          <div class="missing-overview-title">
            <span>⚠️ Missing Values Overview</span>
            <span style="font-size:0.75rem; font-weight:600; color:var(--warning)">(${missing.total_missing ?? 0} cells, ${missing.missing_pct_overall ?? 0}% overall)</span>
          </div>
          <button class="btn btn-danger btn-sm" id="btn-quick-del-missing-rows">
            Delete All Missing Rows
          </button>
        </div>
        <div class="missing-pill-list">
          ${affectedCols.map(col => `
            <div class="missing-pill" data-col="${escHtml(col.column)}">
              <strong>${escHtml(col.column)}</strong>
              <span class="badge badge-warning" style="font-size:0.65rem">${col.missing_count ?? col.count} missing (${col.missing_pct ?? col.pct}%)</span>
              <span style="color:var(--accent); font-size:0.7rem">Fill →</span>
            </div>
          `).join("")}
        </div>
      </div>
    `;

    panel.querySelectorAll(".missing-pill").forEach(p => {
      p.onclick = () => showFillMissingModal(dataset, p.dataset.col, container);
    });

    const btnQuickDel = panel.querySelector("#btn-quick-del-missing-rows");
    if (btnQuickDel) {
      btnQuickDel.onclick = () => triggerDeleteMissingRows(dataset, container);
    }
  } catch (e) {
    panel.innerHTML = `
      <div style="padding:0.75rem 1rem; background:var(--danger-bg); border:1px solid var(--danger-border); border-radius:10px; margin-bottom:1.25rem; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:0.5rem">
        <span style="color:var(--danger); font-size:0.8125rem">⚠️ Failed to load missing values summary: ${escHtml(e.message)}</span>
        <button class="btn btn-secondary btn-sm" id="btn-retry-missing">🔄 Retry</button>
      </div>
    `;
    const btnRetry = panel.querySelector("#btn-retry-missing");
    if (btnRetry) {
      btnRetry.onclick = () => loadMissingOverview(container, dataset);
    }
  }
}

async function loadCleaningTable(container, dataset) {
  const tableWrap = container.querySelector("#cleaning-table-container");
  if (!tableWrap) return;

  // Show loading spinner within container
  tableWrap.innerHTML = `
    <div class="loading-overlay" style="min-height:180px">
      <div class="spinner spinner-lg"></div>
      <div class="loading-text">Loading dataset rows...</div>
    </div>
  `;

  try {
    const data = await api.getDatasetPreview(dataset, {
      page: currentPage,
      pageSize: 25,
      search: currentSearch,
      sortCol: currentSortCol,
      sortAsc: currentSortAsc,
    });
    renderTable(tableWrap, data, dataset, container);
    renderPagination(container.querySelector("#cleaning-pagination"), data, dataset, container);
  } catch (e) {
    tableWrap.innerHTML = `
      <div class="empty-state" style="padding:2.5rem 1rem">
        <div style="font-size:2rem; margin-bottom:0.5rem">⚠️</div>
        <div class="empty-title" style="color:var(--danger)">Failed to load dataset rows</div>
        <div class="empty-sub" style="margin-bottom:1rem; color:var(--ink-faint)">${escHtml(e.message)}</div>
        <button class="btn btn-secondary btn-sm" id="btn-retry-table">🔄 Retry Loading Data</button>
      </div>
    `;
    const pg = container.querySelector("#cleaning-pagination");
    if (pg) pg.innerHTML = "";
    const btnRetry = tableWrap.querySelector("#btn-retry-table");
    if (btnRetry) {
      btnRetry.onclick = () => loadCleaningTable(container, dataset);
    }
  }
}

function renderTable(wrap, data, dataset, container) {
  if (!data || !data.records || !data.records.length) {
    wrap.innerHTML = `<div class="empty-state"><div class="empty-title">No data rows found</div></div>`;
    return;
  }

  const cols = data.columns || [];
  const pageStart = (data.page || 0) * (data.page_size || 25);

  let html = `
    <div class="data-table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th style="width:36px"><input type="checkbox" id="chk-all-rows"></th>
            <th style="width:50px">#</th>
            ${cols.map(c => `
              <th data-col="${escHtml(c)}">
                <input type="checkbox" class="chk-col" data-col="${escHtml(c)}" ${selectedCols.has(c) ? 'checked' : ''}>
                <span class="col-name" style="cursor:pointer">${escHtml(c)}</span>
                <span class="th-sort">${currentSortCol === c ? (currentSortAsc ? '▲' : '▼') : '↕'}</span>
              </th>
            `).join("")}
          </tr>
        </thead>
        <tbody>
  `;

  data.records.forEach((row, idx) => {
    const rowIdx = row._row_id !== undefined ? row._row_id : (pageStart + idx);
    const isRowSelected = selectedRows.has(rowIdx);
    html += `
      <tr data-row="${rowIdx}" class="${isRowSelected ? 'selected' : ''}">
        <td><input type="checkbox" class="chk-row" data-row="${rowIdx}" ${isRowSelected ? 'checked' : ''}></td>
        <td style="color:#94a3b8; font-size:0.75rem">${rowIdx}</td>
        ${cols.map(c => {
          const val = row[c];
          const isNull = val === null || val === undefined;
          return `<td data-row="${rowIdx}" data-col="${escHtml(c)}" class="editable-cell ${isNull ? 'null-cell' : ''}" title="Double click to edit cell">${isNull ? 'null' : escHtml(val)}</td>`;
        }).join("")}
      </tr>
    `;
  });

  html += `</tbody></table></div>`;
  wrap.innerHTML = html;

  // Wire checkbox events
  wrap.querySelectorAll(".chk-row").forEach(chk => {
    chk.onchange = (e) => {
      const r = parseInt(chk.dataset.row);
      if (e.target.checked) selectedRows.add(r); else selectedRows.delete(r);
      chk.closest("tr").classList.toggle("selected", e.target.checked);
      updateSelectionCount(container);
    };
  });

  const chkAll = wrap.querySelector("#chk-all-rows");
  if (chkAll) {
    chkAll.onchange = (e) => {
      wrap.querySelectorAll(".chk-row").forEach(chk => {
        chk.checked = e.target.checked;
        const r = parseInt(chk.dataset.row);
        if (e.target.checked) selectedRows.add(r); else selectedRows.delete(r);
        chk.closest("tr").classList.toggle("selected", e.target.checked);
      });
      updateSelectionCount(container);
    };
  }

  wrap.querySelectorAll(".chk-col").forEach(chk => {
    chk.onchange = (e) => {
      const c = chk.dataset.col;
      if (e.target.checked) selectedCols.add(c); else selectedCols.delete(c);
      updateSelectionCount(container);
    };
  });

  // Double-click cell to edit
  wrap.querySelectorAll(".editable-cell").forEach(td => {
    td.ondblclick = () => {
      const rowIdx = parseInt(td.dataset.row);
      const col = td.dataset.col;
      const currentVal = td.classList.contains("null-cell") ? "" : td.textContent;
      showCellEditModal(dataset, rowIdx, col, currentVal, container);
    };
  });

  // Sort click
  wrap.querySelectorAll(".col-name").forEach(span => {
    span.onclick = async () => {
      const col = span.parentElement.dataset.col;
      if (currentSortCol === col) {
        currentSortAsc = !currentSortAsc;
      } else {
        currentSortCol = col;
        currentSortAsc = true;
      }
      await loadCleaningTable(container, dataset);
    };
  });
}

function renderPagination(wrap, data, dataset, container) {
  if (!wrap || !data) return;
  const totalPages = data.total_pages || 1;
  wrap.innerHTML = `
    <button class="btn btn-secondary btn-sm" id="pg-prev" ${currentPage === 0 ? 'disabled' : ''}>← Prev</button>
    <span class="page-info">Page <strong>${currentPage + 1}</strong> of ${totalPages} (${data.total || 0} rows)</span>
    <button class="btn btn-secondary btn-sm" id="pg-next" ${currentPage >= totalPages - 1 ? 'disabled' : ''}>Next →</button>
  `;
  wrap.querySelector("#pg-prev").onclick = async () => {
    if (currentPage > 0) { currentPage--; await loadCleaningTable(container, dataset); }
  };
  wrap.querySelector("#pg-next").onclick = async () => {
    if (currentPage < totalPages - 1) { currentPage++; await loadCleaningTable(container, dataset); }
  };
}

function updateSelectionCount(container) {
  const el = container.querySelector("#selection-count");
  if (el) el.textContent = `${selectedRows.size} row(s), ${selectedCols.size} col(s) selected`;
}

// ===== CLEANING ACTIONS WIRING =====
function wireCleaningActions(container, dataset) {
  const searchInput = container.querySelector("#clean-search");
  const searchBtn = container.querySelector("#btn-search");
  const clearBtn = container.querySelector("#btn-clear-search");

  const triggerSearch = async () => {
    currentSearch = searchInput.value.trim();
    currentPage = 0;
    await loadCleaningTable(container, dataset);
  };
  if (searchBtn) searchBtn.onclick = triggerSearch;
  if (searchInput) searchInput.onkeypress = (e) => { if (e.key === "Enter") triggerSearch(); };
  if (clearBtn) clearBtn.onclick = async () => {
    searchInput.value = "";
    currentSearch = "";
    currentPage = 0;
    await loadCleaningTable(container, dataset);
  };

  // Edit cell
  container.querySelector("#act-edit-cell").onclick = () => {
    showModal({
      title: "Edit Cell Value",
      body: `
        <div class="form-group"><label class="form-label">Row Index</label><input class="form-input" id="m-row" type="number" placeholder="0"></div>
        <div class="form-group"><label class="form-label">Column Name</label><input class="form-input" id="m-col" placeholder="Column name"></div>
        <div class="form-group"><label class="form-label">New Value</label><input class="form-input" id="m-val" placeholder="New value"></div>
      `,
      confirmText: "Save Edit",
      onConfirm: async () => {
        const r = parseInt(document.getElementById("m-row").value);
        const c = document.getElementById("m-col").value.trim();
        const v = document.getElementById("m-val").value;
        try {
          const res = await api.editCell(dataset, r, c, v);
          await updateTopbar(dataset);
          showAlert(`✓ Edited cell [${r}, '${c}']: '${res.entry?.original_value ?? '—'}' → '${v}'`, "success");
          await loadMissingOverview(container, dataset);
          await loadCleaningTable(container, dataset);
        } catch (e) { showAlert(e.message, "error"); }
      }
    });
  };

  // Delete selected rows
  container.querySelector("#act-del-rows").onclick = () => {
    const indices = Array.from(selectedRows);
    if (!indices.length) { showAlert("Please select at least one row using the checkboxes.", "warning"); return; }
    showModal({
      title: `Delete ${indices.length} Row(s)?`,
      body: `<p>Are you sure you want to delete row index(es): <strong>${indices.slice(0, 10).join(", ")}${indices.length > 10 ? '...' : ''}</strong>?</p><p style="color:#ef4444; font-size:0.75rem; margin-top:0.5rem">This operation affects the working copy only.</p>`,
      confirmText: "Delete Rows",
      confirmClass: "btn-danger",
      onConfirm: async () => {
        try {
          await api.deleteRows(dataset, indices);
          selectedRows.clear();
          updateSelectionCount(container);
          await updateTopbar(dataset);
          showAlert(`✓ Deleted ${indices.length} row(s).`, "success");
          await loadMissingOverview(container, dataset);
          await loadCleaningTable(container, dataset);
        } catch (e) { showAlert(e.message, "error"); }
      }
    });
  };

  // Delete columns
  container.querySelector("#act-del-cols").onclick = () => {
    const cols = Array.from(selectedCols);
    if (!cols.length) { showAlert("Please select at least one column header checkbox.", "warning"); return; }
    showModal({
      title: `Delete Column(s)?`,
      body: `<p>Delete column(s): <strong>${cols.join(", ")}</strong>?</p>`,
      confirmText: "Delete Columns",
      confirmClass: "btn-danger",
      onConfirm: async () => {
        try {
          await api.deleteColumns(dataset, cols);
          selectedCols.clear();
          updateSelectionCount(container);
          await updateTopbar(dataset);
          showAlert(`✓ Deleted column(s).`, "success");
          await loadMissingOverview(container, dataset);
          await loadCleaningTable(container, dataset);
        } catch (e) { showAlert(e.message, "error"); }
      }
    });
  };

  // Rename column
  container.querySelector("#act-rename-col").onclick = () => {
    showModal({
      title: "Rename Column",
      body: `
        <div class="form-group"><label class="form-label">Current Column Name</label><input class="form-input" id="m-old-col" placeholder="Old name"></div>
        <div class="form-group"><label class="form-label">New Column Name</label><input class="form-input" id="m-new-col" placeholder="New name"></div>
      `,
      confirmText: "Rename",
      onConfirm: async () => {
        const oldName = document.getElementById("m-old-col").value.trim();
        const newName = document.getElementById("m-new-col").value.trim();
        try {
          await api.renameColumn(dataset, oldName, newName);
          await updateTopbar(dataset);
          showAlert(`✓ Renamed '${oldName}' to '${newName}'`, "success");
          await loadMissingOverview(container, dataset);
          await loadCleaningTable(container, dataset);
        } catch (e) { showAlert(e.message, "error"); }
      }
    });
  };

  // Fill missing values button
  container.querySelector("#act-fill-missing").onclick = () => {
    showFillMissingModal(dataset, null, container);
  };

  // Delete rows by column (Issue 20)
  const btnDelColMissing = container.querySelector("#act-del-col-missing-rows");
  if (btnDelColMissing) {
    btnDelColMissing.onclick = () => showDeleteColumnMissingModal(dataset, container);
  }

  // Delete all rows with missing values
  container.querySelector("#act-del-missing-rows").onclick = () => {
    triggerDeleteMissingRows(dataset, container);
  };

  // Remove exact duplicates
  container.querySelector("#act-rem-dups").onclick = () => {
    showModal({
      title: "Remove Exact Duplicates",
      body: `<p>Identify and remove exact complete-row duplicate records. Only rows where <em>every</em> cell is identical will be removed.</p>`,
      confirmText: "Remove Duplicates",
      confirmClass: "btn-warning",
      onConfirm: async () => {
        try {
          const res = await api.removeDuplicates(dataset);
          await updateTopbar(dataset);
          showAlert(`✓ ${res.entry.description}`, "success");
          await loadMissingOverview(container, dataset);
          await loadCleaningTable(container, dataset);
        } catch (e) { showAlert(e.message, "error"); }
      }
    });
  };

  // Repair type (Issue 2)
  container.querySelector("#act-repair-type").onclick = () => {
    showRepairTypeModal(dataset, container);
  };

  // Resolve Outlier (Issue 19)
  container.querySelector("#act-resolve-outlier").onclick = () => {
    showOutlierModal(dataset, container);
  };

  // Resolve Suspicious Values (Issue 18)
  const btnResolveSuspicious = container.querySelector("#act-resolve-suspicious");
  if (btnResolveSuspicious) {
    btnResolveSuspicious.onclick = () => showSuspiciousModal(dataset, container);
  }

  // Reset
  container.querySelector("#act-reset").onclick = () => {
    showModal({
      title: "Reset Working Dataset to Original?",
      body: `<p style="color:var(--danger)">Warning: All un-finalized cleaning operations will be discarded and the working dataset will be restored to its original state.</p>`,
      confirmText: "Reset to Original",
      confirmClass: "btn-danger",
      onConfirm: async () => {
        try {
          await api.resetWorking(dataset);
          selectedRows.clear();
          selectedCols.clear();
          await updateTopbar(dataset);
          showAlert("✓ Working dataset reset to original state.", "info");
          await loadMissingOverview(container, dataset);
          await loadCleaningTable(container, dataset);
        } catch (e) { showAlert(e.message, "error"); }
      }
    });
  };
}

// Bulk delete missing rows helper
function triggerDeleteMissingRows(dataset, container) {
  showModal({
    title: "Delete All Rows Containing Missing Values?",
    body: `
      <p>This will delete every row that contains at least one null/missing value in any column.</p>
      <div style="margin-top:0.75rem; padding:0.6rem; background:var(--danger-bg); border:1px solid var(--danger-border); border-radius:6px; font-size:0.75rem; color:var(--danger)">
        ⚠️ This action cannot be undone for the current working copy without resetting.
      </div>
    `,
    confirmText: "Delete Missing Rows",
    confirmClass: "btn-danger",
    onConfirm: async () => {
      try {
        const res = await api.deleteMissingRows(dataset);
        await updateTopbar(dataset);
        showAlert(`✓ ${res.entry.description} (New row count: ${res.new_row_count})`, "success");
        await loadMissingOverview(container, dataset);
        await loadCleaningTable(container, dataset);
      } catch (e) { showAlert(e.message, "error"); }
    }
  });
}

// Issue 20: Per-column bulk delete for missing values
async function showDeleteColumnMissingModal(dataset, container, defaultCol = null) {
  try {
    const analysisRes = await api.getAnalysis(dataset);
    const analysis = analysisRes.analysis || {};
    const affectedCols = (analysis.missing && analysis.missing.affected_columns) || [];
    const schemaCols = (analysis.schema && analysis.schema.columns) || [];

    // Columns that actually have missing values
    let missingCols = affectedCols.map(c => ({
      column: c.column,
      missing_count: c.missing_count ?? c.count ?? 0,
      missing_pct: c.missing_pct ?? c.pct ?? 0,
    }));

    if (!missingCols.length) {
      missingCols = schemaCols
        .filter(c => (c.missing_count ?? 0) > 0)
        .map(c => ({
          column: c.name,
          missing_count: c.missing_count,
          missing_pct: c.missing_pct ?? 0,
        }));
    }

    if (!missingCols.length) {
      showAlert("🎉 No columns currently contain missing values!", "info");
      return;
    }

    const selectedCol = defaultCol && missingCols.some(c => c.column === defaultCol)
      ? defaultCol
      : missingCols[0].column;

    showModal({
      title: "Delete Rows by Column (Scoped Missing Removal)",
      body: `
        <div class="form-group">
          <label class="form-label">Select Column</label>
          <select class="form-select" id="m-del-col-missing-select">
            ${missingCols.map(c => `
              <option value="${escHtml(c.column)}" ${c.column === selectedCol ? 'selected' : ''}>
                ${escHtml(c.column)} — ${c.missing_count} missing rows (${c.missing_pct}%)
              </option>
            `).join("")}
          </select>
          <div class="form-hint">
            Only rows where <strong>this specific column</strong> is missing will be deleted. Rows with missing values in other columns will remain untouched.
          </div>
        </div>
        <div style="margin-top:0.75rem; padding:0.6rem; background:var(--danger-bg); border:1px solid var(--danger-border); border-radius:6px; font-size:0.75rem; color:var(--danger)">
          ⚠️ Deleting rows reduces the total dataset record count. This action affects the working copy.
        </div>
      `,
      confirmText: "Delete Rows Missing in Selected Column",
      confirmClass: "btn-danger",
      onConfirm: async () => {
        const col = document.getElementById("m-del-col-missing-select").value;
        try {
          const res = await api.deleteColumnMissingRows(dataset, col);
          await updateTopbar(dataset);
          showAlert(`✓ ${res.entry.description} (New row count: ${res.new_row_count})`, "success");
          await loadMissingOverview(container, dataset);
          await loadCleaningTable(container, dataset);
        } catch (e) {
          showAlert(e.message, "error");
        }
      }
    });
  } catch (e) {
    showAlert(e.message, "error");
  }
}

// ============================================================
// Issue 3: REPAIR DATA TYPE MODAL (TWO-TAB FLOW: FIX AFFECTED VALUES & CONVERT ENTIRE COLUMN)
// =========================================================================================
async function showRepairTypeModal(dataset, container, initialCol = null, initialTarget = null) {
  try {
    const analysisRes = await api.getAnalysis(dataset);
    let analysis = analysisRes.analysis || {};
    let typeIssues = (analysis.types && analysis.types.type_issues) || [];
    let colDetails = (analysis.types && analysis.types.column_details) || [];
    let schemaCols = (analysis.schema && analysis.schema.columns) || [];

    // Helper: Build map of all columns
    function buildColMap(schema, details, issues) {
      const map = new Map();
      schema.forEach(c => {
        map.set(c.name, {
          name: c.name,
          dtype: c.dtype || "unknown",
          issues: []
        });
      });
      details.forEach(cd => {
        if (map.has(cd.column)) {
          map.get(cd.column).dtype = cd.dtype;
          map.get(cd.column).issues = cd.issues || [];
        } else {
          map.set(cd.column, { name: cd.column, dtype: cd.dtype, issues: cd.issues || [] });
        }
      });
      issues.forEach(ti => {
        if (ti.column && map.has(ti.column)) {
          const entry = map.get(ti.column);
          if (!entry.issues.some(x => x.type === ti.type)) {
            entry.issues.push(ti);
          }
        }
      });
      return map;
    }

    let colMap = buildColMap(schemaCols, colDetails, typeIssues);
    let allCols = Array.from(colMap.values());
    if (!allCols.length) {
      showAlert("No columns available to convert.", "error");
      return;
    }

    let justResolvedCol = null;

    function getIssueCount(colItem) {
      if (!colItem || !colItem.issues || !colItem.issues.length) return 0;
      let count = 0;
      colItem.issues.forEach(i => {
        if (Array.isArray(i.affected_indices)) {
          count += i.affected_indices.length;
        } else if (typeof i.numeric_count === "number") {
          count += i.numeric_count;
        } else {
          count += 1;
        }
      });
      return count || 1;
    }

    function formatSensibleValue(val) {
      if (val === null || val === undefined) return "—";
      const str = String(val);
      const trimmed = str.trim();
      if (/^-?\d+\.\d+$/.test(trimmed)) {
        const parts = trimmed.split(".");
        if (parts[1] && parts[1].length > 4) {
          const num = parseFloat(trimmed);
          if (!isNaN(num)) {
            return num.toFixed(4).replace(/\.?0+$/, "");
          }
        }
        return trimmed;
      }
      return str;
    }

    let colsWithIssues = allCols.filter(c => c.issues && c.issues.length > 0);
    let cleanCols = allCols.filter(c => !c.issues || c.issues.length === 0);

    // Helper: Categorize column dtype
    function getColCategory(dtype) {
      const d = String(dtype || "").toLowerCase();
      if (d.includes("int")) return "int";
      if (d.includes("float")) return "float";
      if (d.includes("date") || d.includes("time")) return "date";
      return "text";
    }

    // Helper: 6 Scoped Valid Conversions
    function getValidTargets(cat) {
      if (cat === "int") {
        return [
          { value: "float64", label: "Float (Decimal Number) — Int → Float" },
          { value: "str", label: "Text / String — Int → Text" }
        ];
      }
      if (cat === "float") {
        return [
          { value: "int64", label: "Integer (Whole Number) — Float → Int" },
          { value: "str", label: "Text / String — Float → Text" }
        ];
      }
      if (cat === "text") {
        return [
          { value: "int64", label: "Integer (Whole Number) — Text → Int" },
          { value: "float64", label: "Float (Decimal Number) — Text → Float" },
          { value: "datetime64", label: "Date / Datetime — Text → Date" }
        ];
      }
      if (cat === "date") {
        return [
          { value: "str", label: "Text / String — Date → Text" }
        ];
      }
      return [
        { value: "float64", label: "Float (Decimal Number)" },
        { value: "int64", label: "Integer (Whole Number)" },
        { value: "str", label: "Text / String" }
      ];
    }

    // Determine default tab and selected column
    const initialHasIssue = initialCol && colsWithIssues.some(c => c.name === initialCol);
    let activeTab = (initialHasIssue || colsWithIssues.length > 0) ? "tab-fix-values" : "tab-convert-column";
    let defaultFixCol = initialHasIssue ? initialCol : (colsWithIssues.length > 0 ? colsWithIssues[0].name : "");
    let defaultConvertCol = initialCol && colMap.has(initialCol) ? initialCol : (colsWithIssues.length > 0 ? colsWithIssues[0].name : allCols[0].name);

    const modalHtml = `
      <div style="display:flex; flex-direction:column; gap:1rem">
        <!-- Navigation Tabs -->
        <div style="display:flex; gap:0.5rem; border-bottom:1px solid var(--line); padding-bottom:0.6rem">
          <button class="btn ${activeTab === 'tab-fix-values' ? 'btn-primary' : 'btn-secondary'} btn-sm repair-tab-btn" id="btn-tab-fix" data-tab="tab-fix-values">
            🎯 Tab 1: Fix Affected Values ${colsWithIssues.length > 0 ? `(${colsWithIssues.length})` : ''}
          </button>
          <button class="btn ${activeTab === 'tab-convert-column' ? 'btn-primary' : 'btn-secondary'} btn-sm repair-tab-btn" id="btn-tab-convert" data-tab="tab-convert-column">
            🔄 Tab 2: Convert Entire Column
          </button>
        </div>

        <!-- Non-blocking prompt banner -->
        <div id="m-repair-prompt-banner" style="display:none"></div>

        <!-- TAB 1: Fix Affected Values -->
        <div id="view-fix-values" style="display:${activeTab === 'tab-fix-values' ? 'block' : 'none'}">
          ${colsWithIssues.length === 0 ? `
            <div class="empty-state" style="padding:2.5rem 1rem">
              <div style="font-size:2.5rem; margin-bottom:0.5rem">🎉</div>
              <div class="empty-title">All column data types are clean!</div>
              <div class="empty-sub" style="margin-bottom:1rem">No columns currently have unresolved type issues. You can convert any column to another type in Tab 2.</div>
              <button class="btn btn-secondary btn-sm" id="btn-quick-switch-tab2">Switch to Convert Entire Column →</button>
            </div>
          ` : `
            <div style="display:flex; flex-direction:column; gap:1rem">
              <div class="form-group" style="margin-bottom:0">
                <label class="form-label" style="display:flex; justify-content:space-between; align-items:center">
                  <span>Select Flagged Column to Fix</span>
                  <span style="font-size:0.75rem; color:var(--ink-faint)">Only columns with active type issues</span>
                </label>
                <select class="form-select" id="m-fix-col-select">
                  ${colsWithIssues.map(c => {
                    const cnt = getIssueCount(c);
                    return `
                      <option value="${escHtml(c.name)}" ${c.name === defaultFixCol ? 'selected' : ''}>
                        ${escHtml(c.name)} (${cnt} issue${cnt === 1 ? '' : 's'})
                      </option>
                    `;
                  }).join("")}
                </select>
              </div>

              <!-- Container for affected rows table & actions -->
              <div id="m-fix-rows-container" style="min-height:220px">
                <div style="display:flex; align-items:center; justify-content:center; gap:0.5rem; color:var(--ink-faint); padding:2rem 0">
                  <span class="spinner spinner-sm"></span> Loading affected rows...
                </div>
              </div>
            </div>
          `}
        </div>

        <!-- TAB 2: Convert Entire Column -->
        <div id="view-convert-column" style="display:${activeTab === 'tab-convert-column' ? 'block' : 'none'}">
          <div style="display:flex; flex-direction:column; gap:1rem">
            <div class="form-group" style="margin-bottom:0">
              <label class="form-label" style="display:flex; justify-content:space-between; align-items:center">
                <span>Select Column to Convert</span>
                <span id="m-repair-col-meta" style="font-weight:600; font-size:0.75rem; color:var(--ink-faint)"></span>
              </label>
              <select class="form-select" id="m-repair-col-select">
                ${colsWithIssues.length > 0 ? `
                  <optgroup label="⚠️ Columns with Detected Type Issues">
                    ${colsWithIssues.map(c => `
                      <option value="${escHtml(c.name)}" ${c.name === defaultConvertCol ? 'selected' : ''}>
                        ${escHtml(c.name)} (${escHtml(c.dtype)}) — ${c.issues.map(i => i.type || i.description).join(", ")}
                      </option>
                    `).join("")}
                  </optgroup>
                ` : ''}
                <optgroup label="${colsWithIssues.length > 0 ? 'Other Columns (Consistent / Clean)' : 'Dataset Columns'}">
                  ${cleanCols.map(c => `
                    <option value="${escHtml(c.name)}" ${c.name === defaultConvertCol ? 'selected' : ''}>
                      ${escHtml(c.name)} (${escHtml(c.dtype)})
                    </option>
                  `).join("")}
                </optgroup>
              </select>
            </div>

            <div class="form-group" style="margin-bottom:0">
              <label class="form-label" style="display:flex; justify-content:space-between; align-items:center">
                <span>Target Data Type</span>
                <span style="font-size:0.72rem; color:var(--ink-faint)">Filtered to valid scoped conversions</span>
              </label>
              <select class="form-select" id="m-repair-target-select"></select>
            </div>

            <div id="m-repair-preview-card" style="background:var(--surface-2); border:1px solid var(--line); border-radius:12px; padding:1.15rem; min-height:160px">
              <div style="display:flex; align-items:center; justify-content:center; gap:0.5rem; color:var(--ink-faint); padding:2rem 0">
                <span class="spinner spinner-sm"></span> Loading preview...
              </div>
            </div>

            <div style="display:flex; justify-content:flex-end; gap:0.5rem; margin-top:0.5rem">
              <button class="btn btn-secondary btn-sm" id="btn-cancel-tab2">Cancel</button>
              <button class="btn btn-primary btn-sm" id="btn-apply-col-conversion" disabled>Apply Conversion</button>
            </div>
          </div>
        </div>
      </div>
    `;

    showModal({
      title: "🔧 Repair Column Data Type",
      body: modalHtml,
      showConfirm: false,
      showCancel: true,
      cancelText: "Close",
      autoClose: false,
    });

    const backdropEl = document.getElementById("modal-backdrop");
    const modalDialog = backdropEl?.querySelector(".modal");
    if (modalDialog) modalDialog.classList.add("modal-lg");

    // Close / Cancel button wiring
    const cleanupModal = () => {
      justResolvedCol = null;
      const promptBanner = document.getElementById("m-repair-prompt-banner");
      if (promptBanner) {
        promptBanner.style.display = "none";
        promptBanner.innerHTML = "";
      }
      if (modalDialog) modalDialog.classList.remove("modal-lg");
      closeModal();
    };

    const btnCloseModal = document.getElementById("modal-close");
    if (btnCloseModal) btnCloseModal.onclick = cleanupModal;
    const btnCancelModal = document.getElementById("modal-cancel");
    if (btnCancelModal) btnCancelModal.onclick = cleanupModal;

    // Tab switching wiring
    const btnTabFix = document.getElementById("btn-tab-fix");
    const btnTabConvert = document.getElementById("btn-tab-convert");
    const viewFix = document.getElementById("view-fix-values");
    const viewConvert = document.getElementById("view-convert-column");

    function switchTab(tab) {
      activeTab = tab;
      justResolvedCol = null;
      const promptBanner = document.getElementById("m-repair-prompt-banner");
      if (promptBanner) {
        promptBanner.style.display = "none";
        promptBanner.innerHTML = "";
      }
      if (tab === "tab-fix-values") {
        btnTabFix?.classList.remove("btn-secondary");
        btnTabFix?.classList.add("btn-primary");
        btnTabConvert?.classList.remove("btn-primary");
        btnTabConvert?.classList.add("btn-secondary");
        if (viewFix) viewFix.style.display = "block";
        if (viewConvert) viewConvert.style.display = "none";
        loadTab1();
      } else {
        btnTabConvert?.classList.remove("btn-secondary");
        btnTabConvert?.classList.add("btn-primary");
        btnTabFix?.classList.remove("btn-primary");
        btnTabFix?.classList.add("btn-secondary");
        if (viewFix) viewFix.style.display = "none";
        if (viewConvert) viewConvert.style.display = "block";
        updateTargetDropdown();
      }
    }

    if (btnTabFix) btnTabFix.onclick = () => switchTab("tab-fix-values");
    if (btnTabConvert) btnTabConvert.onclick = () => switchTab("tab-convert-column");
    const btnQuickSwitch = document.getElementById("btn-quick-switch-tab2");
    if (btnQuickSwitch) btnQuickSwitch.onclick = () => switchTab("tab-convert-column");
    const btnCancelTab2 = document.getElementById("btn-cancel-tab2");
    if (btnCancelTab2) btnCancelTab2.onclick = cleanupModal;

    // ==========================================
    // TAB 1: FIX AFFECTED VALUES IMPLEMENTATION
    // ==========================================
    let tab1SelectedRows = new Set();
    let tab1Page = 0;
    const tab1PageSize = 20;

    async function loadTab1() {
      const rowsContainer = document.getElementById("m-fix-rows-container");
      if (!rowsContainer) return;

      // Re-fetch fresh analysis so Tab 1 and Issue Center read the EXACT same current detection result
      try {
        const analysisRes = await api.getAnalysis(dataset);
        let analysis = analysisRes.analysis || {};
        let typeIssues = (analysis.types && analysis.types.type_issues) || [];
        let colDetails = (analysis.types && analysis.types.column_details) || [];
        let schemaCols = (analysis.schema && analysis.schema.columns) || [];
        colMap = buildColMap(schemaCols, colDetails, typeIssues);
        allCols = Array.from(colMap.values());
        colsWithIssues = allCols.filter(c => c.issues && c.issues.length > 0);
        cleanCols = allCols.filter(c => !c.issues || c.issues.length === 0);
      } catch (err) {
        console.error("Failed to re-fetch analysis:", err);
      }

      if (btnTabFix) {
        btnTabFix.innerHTML = `🎯 Tab 1: Fix Affected Values ${colsWithIssues.length > 0 ? `(${colsWithIssues.length})` : ''}`;
      }

      const colSel = document.getElementById("m-fix-col-select");
      let col = colSel ? colSel.value : defaultFixCol;

      const promptBanner = document.getElementById("m-repair-prompt-banner");
      const colStillHasIssues = colsWithIssues.some(c => c.name === col);

      if (!colStillHasIssues) {
        if (justResolvedCol && justResolvedCol === col) {
          if (promptBanner) {
            promptBanner.style.display = "block";
            promptBanner.innerHTML = `
              <div class="alert alert-success" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem; margin-bottom:0.75rem">
                <div>
                  <strong>🎉 All type issues in '${escHtml(col)}' are resolved!</strong>
                  <span style="margin-left:0.35rem">
                    <a href="javascript:void(0)" id="link-prompt-switch-tab2" style="color:inherit; text-decoration:underline; font-weight:600">Switch to Tab 2 (Convert Entire Column) →</a>
                  </span>
                </div>
                <button class="btn btn-ghost btn-sm" id="btn-prompt-dismiss" style="padding:0.2rem 0.5rem">Dismiss</button>
              </div>
            `;
            const linkSwitch = promptBanner.querySelector("#link-prompt-switch-tab2");
            if (linkSwitch) {
              linkSwitch.onclick = () => {
                defaultConvertCol = col;
                switchTab("tab-convert-column");
              };
            }
            const btnDismiss = promptBanner.querySelector("#btn-prompt-dismiss");
            if (btnDismiss) {
              btnDismiss.onclick = () => {
                promptBanner.style.display = "none";
                promptBanner.innerHTML = "";
                justResolvedCol = null;
              };
            }
          }
        } else {
          if (promptBanner) {
            promptBanner.style.display = "none";
            promptBanner.innerHTML = "";
          }
        }

        if (colsWithIssues.length > 0) {
          col = colsWithIssues[0].name;
          defaultFixCol = col;
        } else {
          col = "";
          defaultFixCol = "";
        }
      } else {
        justResolvedCol = null;
        if (promptBanner) {
          promptBanner.style.display = "none";
          promptBanner.innerHTML = "";
        }
      }

      if (colSel) {
        colSel.innerHTML = colsWithIssues.map(c => {
          const cnt = getIssueCount(c);
          return `
            <option value="${escHtml(c.name)}" ${c.name === col ? 'selected' : ''}>
              ${escHtml(c.name)} (${cnt > 0 ? `${cnt} issue${cnt === 1 ? '' : 's'}` : 'column stored as text'})
            </option>
          `;
        }).join("");
      }

      if (colsWithIssues.length === 0) {
        rowsContainer.innerHTML = `
          <div class="empty-state" style="padding:2.5rem 1rem">
            <div style="font-size:2.5rem; margin-bottom:0.5rem">🎉</div>
            <div class="empty-title">All column data types are clean!</div>
            <div class="empty-sub" style="margin-bottom:1rem">No columns currently have unresolved type issues. You can convert any column to another type in Tab 2.</div>
            <button class="btn btn-secondary btn-sm" id="btn-quick-switch-tab2">Switch to Convert Entire Column →</button>
          </div>
        `;
        const btnQuick = rowsContainer.querySelector("#btn-quick-switch-tab2");
        if (btnQuick) btnQuick.onclick = () => switchTab("tab-convert-column");
        return;
      }

      tab1SelectedRows.clear();
      rowsContainer.innerHTML = `
        <div style="display:flex; align-items:center; justify-content:center; gap:0.5rem; color:var(--ink-faint); padding:2rem 0">
          <span class="spinner spinner-sm"></span> Loading affected rows for '${escHtml(col)}'...
        </div>
      `;

      try {
        const res = await api.getTypeIssueRows(dataset, col, tab1Page, tab1PageSize);
        renderTab1Content(res, col);
      } catch (e) {
        rowsContainer.innerHTML = `<div class="alert alert-error">✗ Failed to load affected rows: ${escHtml(e.message)}</div>`;
      }
    }

    function renderTab1Content(res, col) {
      const rowsContainer = document.getElementById("m-fix-rows-container");
      if (!rowsContainer) return;

      const total = res.total_affected || 0;
      const totalPages = res.total_pages || 1;
      const rows = res.rows || [];
      const propTarget = res.proposed_target || "Int64";
      const cleanCount = res.clean_count ?? 0;
      const unconvertibleCount = res.unconvertible_count ?? 0;
      const decimalLossCount = res.decimal_loss_count ?? 0;
      const totalValues = res.total_values || (cleanCount + total);
      const allProblemIndices = res.all_problem_indices || [];
      const unconvertibleIndices = res.unconvertible_indices || [];

      // By default, select all problem rows across all pages
      tab1SelectedRows.clear();
      allProblemIndices.forEach(idx => tab1SelectedRows.add(idx));

      rowsContainer.innerHTML = `
        <!-- Summary Box: Column-level summary, clean vs unconvertible counts, proposed type -->
        <div style="background:var(--surface-2); border:1px solid var(--line); border-radius:8px; padding:0.75rem 1rem; margin-bottom:0.85rem">
          <div style="font-size:0.875rem; font-weight:600; color:var(--ink); margin-bottom:0.35rem">
            ${escHtml(res.summary || `'${col}' is stored as text. ${cleanCount} values convert cleanly${unconvertibleCount > 0 ? `; ${unconvertibleCount} cannot (listed below)` : ' (0 problem rows)'}.`)}
          </div>
          <div style="font-size:0.78rem; color:var(--ink-faint); display:flex; gap:1rem; flex-wrap:wrap; align-items:center">
            <span>Column: <strong>'${escHtml(col)}'</strong></span>
            <span>Current: <code>${escHtml(res.current_dtype)}</code></span>
            <span>Proposed Type: <strong style="color:var(--accent)"><code>${escHtml(propTarget)}</code></strong></span>
            <span>Total Rows: <strong>${totalValues}</strong></span>
            <span>Convert Cleanly: <strong style="color:var(--success)">${cleanCount}</strong></span>
            <span>Cannot Convert: <strong style="${unconvertibleCount > 0 ? 'color:var(--danger)' : ''}">${unconvertibleCount}</strong></span>
            ${decimalLossCount > 0 ? `<span>Rounding: <strong style="color:var(--warning)">${decimalLossCount}</strong></span>` : ''}
          </div>
        </div>

        <!-- Action Toolbar: Select All, Selected Count, Delete unconvertible, Convert entire column -->
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.65rem; flex-wrap:wrap; gap:0.5rem">
          <div style="display:flex; align-items:center; gap:0.5rem">
            ${total > 0 ? `
              <label style="display:flex; align-items:center; gap:0.35rem; font-size:0.8125rem; cursor:pointer">
                <input type="checkbox" id="chk-all-fix-rows" ${tab1SelectedRows.size > 0 ? 'checked' : ''} /> Select All
              </label>
              <span style="font-size:0.75rem; color:var(--ink-faint)" id="fix-selected-count">All ${tab1SelectedRows.size} problem rows selected</span>
            ` : `
              <span style="font-size:0.8125rem; color:var(--success); font-weight:600">✓ No value-level problems in this column</span>
            `}
          </div>
          <div style="display:flex; gap:0.5rem; flex-wrap:wrap">
            ${total > 0 ? `
              <button class="btn btn-secondary btn-sm" id="btn-fix-delete" title="Delete rows containing values that cannot convert">
                Delete rows with unconvertible values (${unconvertibleCount || total})
              </button>
            ` : ''}
            <button class="btn btn-primary btn-sm" id="btn-fix-convert-all" title="Convert the whole column across all rows in one action">
              Convert entire column (${cleanCount} values to ${escHtml(propTarget)})
            </button>
          </div>
        </div>

        <!-- Problem Rows Table (Lists ONLY genuine value-level problems) -->
        ${rows.length === 0 ? `
          <div style="background:var(--surface-2); border:1px solid var(--line); border-radius:8px; padding:2rem 1rem; text-align:center; color:var(--ink-soft); margin-bottom:0.75rem">
            <div style="font-size:1.75rem; margin-bottom:0.35rem">✓</div>
            <div style="font-weight:700; font-size:0.95rem; margin-bottom:0.25rem">No Value-Level Problem Rows</div>
            <div style="font-size:0.8125rem; color:var(--ink-faint)">
              All ${cleanCount} values in <strong>'${escHtml(col)}'</strong> convert cleanly to <code>${escHtml(propTarget)}</code>. Click 'Convert entire column' above to apply.
            </div>
          </div>
        ` : `
          <div class="data-table-wrap" style="max-height:300px; overflow-y:auto">
            <table class="data-table">
              <thead>
                <tr>
                  <th style="width:36px"><input type="checkbox" id="chk-head-sync" checked /></th>
                  <th style="width:65px">Row #</th>
                  <th>Stored Value</th>
                  <th>Proposed Converted Value</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                ${rows.map(r => `
                  <tr data-row="${r.row_index}">
                    <td><input type="checkbox" class="chk-fix-row" data-row="${r.row_index}" ${tab1SelectedRows.has(r.row_index) ? 'checked' : ''} /></td>
                    <td><strong>${r.row_index}</strong></td>
                    <td><code>${escHtml(formatSensibleValue(r.current_value))}</code></td>
                    <td>${r.proposed_value !== null && r.proposed_value !== undefined ? `<strong style="color:var(--accent)">${escHtml(formatSensibleValue(r.proposed_value))}</strong>` : '<span style="color:var(--ink-faint)">null (blank)</span>'}</td>
                    <td>
                      ${r.can_convert ? `
                        <span class="badge badge-warning" style="font-size:0.75rem" title="${escHtml(r.fail_reason || '')}">⚠️ Rounding: ${escHtml(r.fail_reason || 'decimal will be rounded')}</span>
                      ` : `
                        <span class="badge badge-danger" style="font-size:0.75rem" title="${escHtml(r.fail_reason || '')}">⚠️ Cannot convert${r.fail_reason ? `: ${escHtml(r.fail_reason)}` : ''}</span>
                      `}
                    </td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        `}

        ${totalPages > 1 ? `
          <div style="display:flex; justify-content:space-between; align-items:center; margin-top:0.65rem; font-size:0.8125rem">
            <span>Page ${tab1Page + 1} of ${totalPages} (${total} total problem rows)</span>
            <div style="display:flex; gap:0.35rem">
              <button class="btn btn-secondary btn-sm" id="btn-tab1-prev" ${tab1Page <= 0 ? 'disabled' : ''}>← Prev</button>
              <button class="btn btn-secondary btn-sm" id="btn-tab1-next" ${tab1Page >= totalPages - 1 ? 'disabled' : ''}>Next →</button>
            </div>
          </div>
        ` : ''}
      `;

      // Wire checkboxes
      const chkAll = rowsContainer.querySelector("#chk-all-fix-rows");
      const chkHeadSync = rowsContainer.querySelector("#chk-head-sync");
      const selCount = rowsContainer.querySelector("#fix-selected-count");
      const btnConvertAll = rowsContainer.querySelector("#btn-fix-convert-all");
      const btnDelete = rowsContainer.querySelector("#btn-fix-delete");

      function updateFixSelection() {
        const size = tab1SelectedRows.size;
        const totalCount = allProblemIndices.length;
        if (selCount) {
          if (size === totalCount) {
            selCount.textContent = `All ${size} problem rows selected`;
          } else {
            selCount.textContent = `${size} of ${totalCount} selected`;
          }
        }
        if (btnDelete) {
          btnDelete.disabled = size === 0 && unconvertibleCount === 0;
          if (size > 0 && size < totalCount) {
            btnDelete.textContent = `Delete ${size} selected rows`;
          } else {
            btnDelete.textContent = `Delete rows with unconvertible values (${unconvertibleCount || totalCount})`;
          }
        }
        const allPageChecked = rows.length > 0 && rows.every(r => tab1SelectedRows.has(r.row_index));
        if (chkAll) chkAll.checked = size === totalCount && totalCount > 0;
        if (chkHeadSync) chkHeadSync.checked = allPageChecked;
      }

      rowsContainer.querySelectorAll(".chk-fix-row").forEach(chk => {
        chk.onchange = (e) => {
          const r = parseInt(chk.dataset.row);
          if (e.target.checked) tab1SelectedRows.add(r); else tab1SelectedRows.delete(r);
          updateFixSelection();
        };
      });

      function handleSelectAll(checked) {
        if (checked) {
          allProblemIndices.forEach(idx => tab1SelectedRows.add(idx));
        } else {
          tab1SelectedRows.clear();
        }
        rowsContainer.querySelectorAll(".chk-fix-row").forEach(c => c.checked = checked);
        updateFixSelection();
      }

      if (chkAll) chkAll.onchange = (e) => handleSelectAll(e.target.checked);
      if (chkHeadSync) chkHeadSync.onchange = (e) => handleSelectAll(e.target.checked);

      // Primary Button: Convert WHOLE column in one action across ALL rows
      if (btnConvertAll) {
        btnConvertAll.onclick = async () => {
          let warningMsg = `Convert entire column '${col}' to ${propTarget}?\n\n`;
          warningMsg += `• ${cleanCount} value(s) will be converted cleanly to ${propTarget}.\n`;
          if (unconvertibleCount > 0) {
            const unconvList = rows.filter(r => !r.can_convert).map(r => `Row ${r.row_index}: '${r.current_value}'`).slice(0, 10);
            warningMsg += `• WARNING: ${unconvertibleCount} value(s) cannot convert and will become blank/null:\n  ${unconvList.join("\n  ")}${unconvertibleCount > 10 ? `\n  ...and ${unconvertibleCount - 10} more` : ''}\n\n`;
          }
          if (decimalLossCount > 0) {
            warningMsg += `• ${decimalLossCount} decimal value(s) will be rounded to integers.\n\n`;
          }
          if (res.has_missing) {
            warningMsg += `• Existing blanks stay blank.\n\n`;
          }
          warningMsg += `Proceed with converting the entire column?`;

          if (unconvertibleCount > 0 || decimalLossCount > 0) {
            if (!confirm(warningMsg)) return;
          }

          btnConvertAll.disabled = true;
          btnConvertAll.textContent = "Converting entire column...";

          try {
            await api.resolveTypeRows(dataset, col, "convert_column", {
              target_type: propTarget,
            });

            justResolvedCol = col;
            await updateTopbar(dataset);
            await loadCleaningTable(container, dataset);
            showAlert(`✓ Converted entire column '${col}' to ${propTarget}.`, "success");
            await loadTab1();
          } catch (err) {
            btnConvertAll.disabled = false;
            btnConvertAll.textContent = `Convert entire column (${cleanCount} values to ${escHtml(propTarget)})`;
            showAlert(err.message, "error");
          }
        };
      }

      // Secondary Button: Delete rows with unconvertible values
      if (btnDelete) {
        btnDelete.onclick = async () => {
          const targetRows = tab1SelectedRows.size > 0
            ? Array.from(tab1SelectedRows)
            : (unconvertibleIndices.length > 0 ? unconvertibleIndices : allProblemIndices);
          if (targetRows.length === 0) return;

          if (!confirm(`Are you sure you want to delete ${targetRows.length} row(s) containing unconvertible values in '${col}'?`)) {
            return;
          }

          btnDelete.disabled = true;
          btnDelete.textContent = "Deleting...";

          try {
            await api.resolveTypeRows(dataset, col, "delete_row", {
              row_indices: targetRows,
              target_type: propTarget,
            });

            justResolvedCol = col;
            await updateTopbar(dataset);
            await loadCleaningTable(container, dataset);
            showAlert(`✓ Deleted ${targetRows.length} row(s) in '${col}'.`, "success");
            await loadTab1();
          } catch (err) {
            btnDelete.disabled = false;
            btnDelete.textContent = "Delete rows with unconvertible values";
            showAlert(err.message, "error");
          }
        };
      }

      // Wire pagination
      const btnPrev = rowsContainer.querySelector("#btn-tab1-prev");
      if (btnPrev) btnPrev.onclick = () => { tab1Page--; loadTab1(); };
      const btnNext = rowsContainer.querySelector("#btn-tab1-next");
      if (btnNext) btnNext.onclick = () => { tab1Page++; loadTab1(); };
    }

    const colSelFix = document.getElementById("m-fix-col-select");
    if (colSelFix) {
      colSelFix.onchange = () => {
        justResolvedCol = null;
        const promptBanner = document.getElementById("m-repair-prompt-banner");
        if (promptBanner) {
          promptBanner.style.display = "none";
          promptBanner.innerHTML = "";
        }
        tab1Page = 0;
        loadTab1();
      };
    }

    // ==========================================
    // TAB 2: CONVERT ENTIRE COLUMN IMPLEMENTATION
    // ==========================================
    const colSelConvert = document.getElementById("m-repair-col-select");
    const targetSel = document.getElementById("m-repair-target-select");
    const metaSpan = document.getElementById("m-repair-col-meta");
    const previewCard = document.getElementById("m-repair-preview-card");
    const btnApplyCol = document.getElementById("btn-apply-col-conversion");

    async function updateTargetDropdown() {
      if (!colSelConvert || !targetSel) return;
      const currentSelectedCol = colSelConvert.value;
      const colEntry = colMap.get(currentSelectedCol) || { dtype: "unknown" };
      const cat = getColCategory(colEntry.dtype);
      if (metaSpan) metaSpan.textContent = `Current Type: ${colEntry.dtype} (${cat.toUpperCase()})`;

      const targets = getValidTargets(cat);
      targetSel.innerHTML = targets.map((t, idx) => `
        <option value="${t.value}" ${initialTarget && t.value === initialTarget ? 'selected' : (idx === 0 ? 'selected' : '')}>
          ${escHtml(t.label)}
        </option>
      `).join("");

      await runPreview();
    }

    async function runPreview() {
      if (!colSelConvert || !targetSel || !previewCard || !btnApplyCol) return;
      const col = colSelConvert.value;
      const target = targetSel.value;
      if (!col || !target) return;

      btnApplyCol.disabled = true;
      btnApplyCol.textContent = "Analyzing...";

      previewCard.innerHTML = `
        <div style="display:flex; align-items:center; justify-content:center; gap:0.5rem; color:var(--ink-faint); padding:1.5rem 0">
          <span class="spinner spinner-sm"></span> Analyzing type conversion...
        </div>
      `;

      try {
        const prev = await api.previewTypeConversion(dataset, col, target);
        if (prev.error) {
          previewCard.innerHTML = `<div class="alert alert-error">✗ ${escHtml(prev.error)}</div>`;
          btnApplyCol.disabled = true;
          return;
        }

        renderPreviewContent(prev);
      } catch (err) {
        previewCard.innerHTML = `<div class="alert alert-error">✗ Failed to preview conversion: ${escHtml(err.message)}</div>`;
        btnApplyCol.disabled = true;
      }
    }

    function renderPreviewContent(p) {
      const col = p.column;
      const target = p.target_type;
      const convCode = p.conversion_code || "";
      const total = p.total_values || 0;
      const convertible = p.convertible_count ?? total;
      const nonConvertible = p.non_convertible_count ?? 0;
      const decLoss = p.decimal_loss_count ?? 0;

      let bannerHtml = "";
      let requiresCheckbox = false;

      if (convCode === "int_to_float") {
        bannerHtml = `
          <div class="alert alert-success" style="margin-bottom:0.85rem">
            <div>
              <strong>✅ Safe Conversion (Int → Float):</strong>
              All integer values will be converted to floating-point numbers with standard decimal precision.
            </div>
          </div>
        `;
      } else if (convCode === "float_to_int") {
        if (decLoss === 0) {
          bannerHtml = `
            <div class="alert alert-success" style="margin-bottom:0.85rem">
              <div>
                <strong>✅ Safe Conversion (Float → Int):</strong>
                Every value in this column is already a whole number with no fractional decimal part.
              </div>
            </div>
          `;
        } else {
          requiresCheckbox = true;
          bannerHtml = `
            <div class="alert alert-warning" style="margin-bottom:0.85rem">
              <div>
                <div style="font-weight:700">⚠️ Precision Loss Warning (Float → Int):</div>
                <div style="margin:0.25rem 0 0.5rem">
                  <strong>${decLoss} of ${total}</strong> values have fractional decimal parts that will be rounded to integers using round-half-up:
                  ${p.decimal_loss_examples && p.decimal_loss_examples.length ? `<span style="font-family:monospace; background:rgba(0,0,0,0.06); padding:0.1rem 0.35rem; border-radius:4px">${p.decimal_loss_examples.join(", ")}</span>` : ""}.
                </div>
                <label style="display:flex; align-items:center; gap:0.5rem; cursor:pointer; font-weight:700; color:var(--ink); margin-top:0.4rem; padding-top:0.4rem; border-top:1px dashed rgba(217,119,6,0.3)">
                  <input type="checkbox" id="m-repair-chk-loss" style="width:16px; height:16px; cursor:pointer" />
                  <span>I confirm and authorize rounding ${decLoss} decimal values to integers.</span>
                </label>
              </div>
            </div>
          `;
        }
      } else if (convCode === "num_to_text") {
        bannerHtml = `
          <div class="alert alert-warning" style="margin-bottom:0.85rem">
            <div>
              <strong>⚠️ Capability Warning (Numeric → Text):</strong>
              Converting to text preserves exact values, but this column will <strong>lose numeric calculation and statistical profiling capabilities</strong>.
            </div>
          </div>
        `;
      } else if (convCode === "text_to_int" || convCode === "text_to_float") {
        if (p.will_be_empty || (total > 0 && convertible === 0 && nonConvertible > 0)) {
          bannerHtml = `
            <div class="alert alert-error" style="margin-bottom:0.85rem">
              <div>
                <div style="font-weight:700">❌ Complete Conversion Failure:</div>
                <div style="margin-top:0.25rem">
                  All <strong>${nonConvertible}</strong> value(s) in this column failed conversion to ${escHtml(target)} and would become null/NaN.
                  This conversion would leave the column entirely empty and cannot be applied.
                  <div style="margin-top:0.35rem; font-family:monospace; font-size:0.75rem; background:rgba(0,0,0,0.06); padding:0.35rem 0.6rem; border-radius:6px">
                    ${(p.non_convertible_examples || []).join(", ")}
                  </div>
                </div>
              </div>
            </div>
          `;
        } else if (nonConvertible > 0) {
          bannerHtml = `
            <div class="alert alert-warning" style="margin-bottom:0.85rem">
              <div>
                <div style="font-weight:700">⚠️ Partial Conversion (${convertible} of ${total} valid):</div>
                <div style="margin-top:0.25rem">
                  <strong>${convertible} of ${total}</strong> values converted successfully.
                  <strong>${nonConvertible} value(s) could not be converted</strong> and will become null/NaN:
                  <div style="margin-top:0.35rem; font-family:monospace; font-size:0.75rem; background:rgba(0,0,0,0.06); padding:0.35rem 0.6rem; border-radius:6px">
                    ${(p.non_convertible_examples || []).join(", ")}
                  </div>
                </div>
              </div>
            </div>
          `;
        } else {
          bannerHtml = `
            <div class="alert alert-success" style="margin-bottom:0.85rem">
              <div>
                <strong>✅ Clean Conversion:</strong>
                All ${convertible} text values parse cleanly into valid numbers.
              </div>
            </div>
          `;
        }
        if (convCode === "text_to_int" && decLoss > 0) {
          requiresCheckbox = true;
          bannerHtml += `
            <div class="alert alert-warning" style="margin-bottom:0.85rem">
              <div>
                <div style="font-weight:700">⚠️ Decimal Rounding Notice:</div>
                <div style="margin:0.25rem 0 0.4rem">
                  ${decLoss} values contain decimal points and will be rounded using round-half-up: ${(p.decimal_loss_examples || []).join(", ")}.
                </div>
                <label style="display:flex; align-items:center; gap:0.5rem; cursor:pointer; font-weight:700; color:var(--ink); margin-top:0.35rem">
                  <input type="checkbox" id="m-repair-chk-loss" style="width:16px; height:16px; cursor:pointer" />
                  <span>I authorize rounding ${decLoss} decimal values to integers.</span>
                </label>
              </div>
            </div>
          `;
        }
      } else if (convCode === "text_to_date" || (convCode && convCode.endsWith("_to_date"))) {
        if (p.will_be_empty || (total > 0 && convertible === 0 && nonConvertible > 0)) {
          bannerHtml = `
            <div class="alert alert-error" style="margin-bottom:0.85rem">
              <div>
                <div style="font-weight:700">❌ Complete Conversion Failure:</div>
                <div style="margin-top:0.25rem">
                  All <strong>${nonConvertible}</strong> value(s) in this column failed date parsing and would become null.
                  This conversion would leave the column entirely empty and cannot be applied.
                  <div style="margin-top:0.35rem; font-family:monospace; font-size:0.75rem; background:rgba(0,0,0,0.06); padding:0.35rem 0.6rem; border-radius:6px">
                    ${(p.non_convertible_examples || []).join(", ")}
                  </div>
                </div>
              </div>
            </div>
          `;
        } else if (nonConvertible > 0) {
          bannerHtml = `
            <div class="alert alert-warning" style="margin-bottom:0.85rem">
              <div>
                <div style="font-weight:700">⚠️ Date Parsing Issues (${convertible} of ${total} recognized):</div>
                <div style="margin-top:0.25rem">
                  <strong>${convertible} of ${total}</strong> values recognized as valid dates.
                  <strong>${nonConvertible} value(s) failed date parsing</strong> and will become null:
                  <div style="margin-top:0.35rem; font-family:monospace; font-size:0.75rem; background:rgba(0,0,0,0.06); padding:0.35rem 0.6rem; border-radius:6px">
                    ${(p.non_convertible_examples || []).join(", ")}
                  </div>
                </div>
              </div>
            </div>
          `;
        } else {
          bannerHtml = `
            <div class="alert alert-success" style="margin-bottom:0.85rem">
              <div>
                <strong>✅ Clean Date Conversion:</strong>
                All ${convertible} values parsed successfully into standard dates.
              </div>
            </div>
          `;
        }
      } else if (convCode === "date_to_text") {
        bannerHtml = `
          <div class="alert alert-success" style="margin-bottom:0.85rem">
            <div>
              <strong>✅ Safe Conversion (Date → Text):</strong>
              All dates will be formatted into standard ISO text representations (YYYY-MM-DD).
            </div>
          </div>
        `;
      }

      const sampleRows = p.sample_pairs || [];
      let tableHtml = "";
      if (sampleRows.length > 0) {
        tableHtml = `
          <div style="margin-top:0.85rem">
            <div style="font-size:0.75rem; font-weight:700; color:var(--ink-soft); text-transform:uppercase; letter-spacing:0.04em; margin-bottom:0.4rem">
              Expected Result Preview (Sample Values)
            </div>
            <div style="border:1px solid var(--line); border-radius:8px; overflow:hidden">
              <table class="data-table" style="font-size:0.78rem">
                <thead>
                  <tr>
                    <th style="width:50px">Row</th>
                    <th>Current Value (${escHtml(p.current_type)})</th>
                    <th>Proposed Result (${escHtml(p.target_type)})</th>
                    <th style="width:85px; text-align:center">Status</th>
                  </tr>
                </thead>
                <tbody>
                  ${sampleRows.map(r => `
                    <tr>
                      <td style="color:var(--ink-faint); font-weight:600">#${r.row}</td>
                      <td><code>${escHtml(r.original)}</code></td>
                      <td><code>${escHtml(r.converted)}</code></td>
                      <td style="text-align:center">
                        <span class="badge ${r.status === 'success' ? 'badge-success' : 'badge-danger'}" style="font-size:0.7rem">
                          ${r.status === 'success' ? '✓ OK' : '✗ Failed'}
                        </span>
                      </td>
                    </tr>
                  `).join("")}
                </tbody>
              </table>
            </div>
          </div>
        `;
      }

      previewCard.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.85rem; padding-bottom:0.65rem; border-bottom:1px solid var(--line)">
          <div style="display:flex; align-items:center; gap:0.5rem">
            <span class="badge badge-info" style="font-size:0.78rem">${escHtml(p.current_type)}</span>
            <span style="color:var(--ink-faint); font-weight:800">➔</span>
            <span class="badge badge-success" style="font-size:0.78rem">${escHtml(p.target_type)}</span>
          </div>
          <div style="font-size:0.75rem; color:var(--ink-soft)">
            Convertible: <strong>${convertible}/${total}</strong>
            ${nonConvertible > 0 ? `· <span style="color:var(--danger)">Failed: ${nonConvertible}</span>` : ""}
          </div>
        </div>

        ${bannerHtml}
        ${tableHtml}
      `;

      btnApplyCol.textContent = `Apply Conversion (${escHtml(col)} → ${escHtml(target)})`;
      if (p.will_be_empty || (total > 0 && convertible === 0 && nonConvertible > 0)) {
        btnApplyCol.disabled = true;
        btnApplyCol.title = "Cannot apply: all values in this column failed conversion.";
      } else if (requiresCheckbox) {
        btnApplyCol.disabled = true;
        const chk = document.getElementById("m-repair-chk-loss");
        if (chk) chk.onchange = () => { btnApplyCol.disabled = !chk.checked; };
      } else {
        btnApplyCol.disabled = false;
      }
    }

    if (btnApplyCol) {
      btnApplyCol.onclick = async () => {
        const col = colSelConvert.value;
        const target = targetSel.value;
        const chkLoss = document.getElementById("m-repair-chk-loss");
        if (chkLoss && !chkLoss.checked) {
          showAlert("⚠️ Please check the confirmation checkbox to authorize rounding before applying.", "warning");
          return;
        }

        btnApplyCol.disabled = true;
        btnApplyCol.textContent = "Converting...";

        try {
          await api.repairType(dataset, col, target);
          closeModal();
          if (modalDialog) modalDialog.classList.remove("modal-lg");
          await updateTopbar(dataset);
          showAlert(`✓ Converted column '${col}' to ${target}`, "success");
          await loadCleaningTable(container, dataset);
        } catch (e) {
          btnApplyCol.disabled = false;
          btnApplyCol.textContent = "Apply Conversion";
          showAlert(e.message, "error");
        }
      };
    }

    if (colSelConvert) colSelConvert.onchange = () => updateTargetDropdown();
    if (targetSel) targetSel.onchange = () => runPreview();

    // Initial render based on active tab
    if (activeTab === "tab-fix-values") {
      await loadTab1();
    } else {
      await updateTargetDropdown();
    }

  } catch (err) {
    showAlert("Failed to open Repair Data Type modal: " + err.message, "error");
  }
}

// Issue 19 & Item 6/7: Dynamic Outlier Resolution Modal with Multi-Row Selection & Real-Time Dropdown State Flow
async function showOutlierModal(dataset, container, defaultCol = null) {
  try {
    const [analysisRes, prevRes] = await Promise.all([
      api.getAnalysis(dataset),
      api.getDatasetPreview(dataset, { page: 0, pageSize: 1 })
    ]);
    let currentAnalysis = analysisRes.analysis || {};
    const schemaCols = (currentAnalysis.schema && currentAnalysis.schema.columns) || [];
    const dtypes = prevRes.dtypes || {};

    const getUnresolvedOutlierCols = (an) => {
      const details = (an.outliers && an.outliers.outlier_details) || [];
      return details.filter(c => (c.combined_count > 0 || (c.combined_indices && c.combined_indices.length > 0)));
    };

    let outlierCols = getUnresolvedOutlierCols(currentAnalysis);

    if (!outlierCols.length) {
      showAlert("🎉 No columns currently contain detected statistical outliers!", "info");
      return;
    }

    let selectedCol = defaultCol && outlierCols.some(c => c.column === defaultCol)
      ? defaultCol
      : outlierCols[0].column;

    showModal({
      title: "Resolve Outliers & Anomalies",
      autoClose: false,
      body: `
        <div id="m-out-body-wrap">
          <div class="form-group">
            <label class="form-label">Column with Outliers</label>
            <select class="form-select" id="m-out-col">
              ${outlierCols.map(c => `
                <option value="${escHtml(c.column)}" ${c.column === selectedCol ? 'selected' : ''}>
                  ${escHtml(c.column)} (${c.combined_count} outlier${c.combined_count > 1 ? 's' : ''})
                </option>
              `).join("")}
            </select>
          </div>

          <div class="form-group">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.35rem">
              <label class="form-label" style="margin-bottom:0">Select Affected Rows</label>
              <label style="display:flex; align-items:center; gap:0.35rem; font-size:0.75rem; font-weight:600; cursor:pointer; color:var(--primary); user-select:none">
                <input type="checkbox" id="m-out-select-all" style="cursor:pointer; accent-color:var(--primary)"> Select All (<span id="m-out-total-count">0</span>)
              </label>
            </div>
            <div id="m-out-rows-container" style="max-height:165px; overflow-y:auto; border:1px solid var(--border); border-radius:6px; padding:0.4rem; background:var(--surface-2); display:flex; flex-direction:column; gap:0.3rem"></div>
            <div class="form-hint" style="display:flex; justify-content:space-between; margin-top:0.35rem">
              <span>Select one or more rows to apply resolution in bulk.</span>
              <span id="m-out-selected-count" style="font-weight:600; color:var(--primary)">0 selected</span>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Resolution Action</label>
            <select class="form-select" id="m-out-res">
              <option value="replace" selected>Replace with Statistical Imputation</option>
              <option value="correct">Correct (Enter Verified Manual Value)</option>
              <option value="delete_row">Delete Entire Row(s) (Remove Record)</option>
              <option value="keep">Keep (Verified Valid Domain Value — Log Decision)</option>
            </select>
          </div>

          <div class="form-group hidden" id="m-out-manual-wrap">
            <label class="form-label">Verified Value</label>
            <input class="form-input" id="m-out-val" placeholder="Enter verified replacement value">
            <div class="form-hint">This value will be written to all selected rows.</div>
          </div>

          <div class="form-group" id="m-out-impute-wrap">
            <label class="form-label">Imputation Method</label>
            <select class="form-select" id="m-out-impute-method"></select>
            <div class="form-hint" id="m-out-method-hint">Replacement values exclude remaining outliers to prevent circular skew.</div>
          </div>
        </div>
      `,
      confirmText: "Apply Resolution",
      onConfirm: async () => {
        const colSel = document.getElementById("m-out-col");
        const resSel = document.getElementById("m-out-res");
        if (!colSel) return;

        const col = colSel.value;
        const res = resSel.value;
        const manualVal = document.getElementById("m-out-val") ? document.getElementById("m-out-val").value : null;
        const imputeMethod = document.getElementById("m-out-impute-method") ? document.getElementById("m-out-impute-method").value : null;

        const checkedBoxes = Array.from(document.querySelectorAll(".m-out-row-cb:checked"));
        const rowIndices = checkedBoxes.map(cb => parseInt(cb.value)).filter(n => !isNaN(n));

        if (!rowIndices.length) {
          showAlert("Please select at least one row to resolve.", "warning");
          return;
        }

        const confirmBtn = document.getElementById("modal-confirm");
        if (confirmBtn) {
          confirmBtn.disabled = true;
          confirmBtn.textContent = "Applying...";
        }

        try {
          const r = await api.resolveOutlier(dataset, rowIndices, col, res, imputeMethod, manualVal);
          await updateTopbar(dataset);
          const desc = (r.entries && r.entries.length)
            ? `${r.entries.length} row(s) resolved for '${col}'`
            : "Outlier resolved.";
          showAlert(`✓ ${desc}`, "success");
          loadMissingOverview(container, dataset);
          loadCleaningTable(container, dataset);

          // Always re-fetch fresh state from server so dropdown filtering is 100% synchronized
          const freshRes = await api.getAnalysis(dataset);
          currentAnalysis = freshRes.analysis || r.analysis || {};
          outlierCols = getUnresolvedOutlierCols(currentAnalysis);

          if (!outlierCols.length) {
            // All outliers in the entire dataset have been resolved!
            const wrap = document.getElementById("m-out-body-wrap");
            if (wrap) {
              wrap.innerHTML = `
                <div style="text-align:center; padding:2rem 1rem">
                  <div style="font-size:3rem; margin-bottom:0.75rem">🎉</div>
                  <div style="font-weight:800; font-size:1.15rem; color:var(--ink); margin-bottom:0.5rem">All Outliers Resolved!</div>
                  <p style="color:var(--ink-faint); font-size:0.875rem; margin-bottom:1.5rem">No remaining unresolved outliers exist in this dataset.</p>
                </div>
              `;
            }
            const cancelBtn = document.getElementById("modal-cancel");
            if (cancelBtn) cancelBtn.style.display = "none";
            if (confirmBtn) {
              confirmBtn.disabled = false;
              confirmBtn.textContent = "Done";
              confirmBtn.className = "btn btn-success";
              confirmBtn.onclick = () => closeModal();
            }
            return;
          }

          // If the currently selected column is now resolved, automatically switch to the next unresolved column
          if (!outlierCols.some(c => c.column === selectedCol)) {
            selectedCol = outlierCols[0].column;
          }

          // Rebuild column dropdown options from CURRENT unresolved state (removes resolved columns)
          colSel.innerHTML = outlierCols.map(c => `
            <option value="${escHtml(c.column)}" ${c.column === selectedCol ? 'selected' : ''}>
              ${escHtml(c.column)} (${c.combined_count} outlier${c.combined_count > 1 ? 's' : ''})
            </option>
          `).join("");

          updateRowsAndMethods();
          updateVisibility();
        } catch (e) {
          showAlert(e.message, "error");
        } finally {
          if (confirmBtn && outlierCols.length > 0) {
            confirmBtn.disabled = false;
            confirmBtn.textContent = "Apply Resolution";
          }
        }
      }
    });

    const updateRowsAndMethods = () => {
      const colSel = document.getElementById("m-out-col");
      const rowsContainer = document.getElementById("m-out-rows-container");
      const selectAllCb = document.getElementById("m-out-select-all");
      const totalCountEl = document.getElementById("m-out-total-count");
      const selectedCountEl = document.getElementById("m-out-selected-count");
      const imputeMethodSel = document.getElementById("m-out-impute-method");
      if (!colSel || !rowsContainer) return;

      selectedCol = colSel.value;
      const colDetail = outlierCols.find(c => c.column === selectedCol) || {};
      const indices = colDetail.combined_indices || [];
      const outlierValues = colDetail.outlier_values || [];

      if (totalCountEl) totalCountEl.textContent = indices.length;

      if (!indices.length) {
        rowsContainer.innerHTML = `<div style="color:var(--ink-faint); font-size:0.8rem; padding:0.6rem; text-align:center">No unresolved outliers in this column</div>`;
        if (selectAllCb) { selectAllCb.checked = false; selectAllCb.disabled = true; }
        if (selectedCountEl) selectedCountEl.textContent = "0 selected";
      } else {
        if (selectAllCb) { selectAllCb.checked = false; selectAllCb.disabled = false; }
        rowsContainer.innerHTML = indices.map((idx, i) => {
          const ov = outlierValues.find(v => (v.row === idx || v.index === idx));
          const valStr = ov && ov.value !== undefined ? `Value: ${ov.value}` : "";
          return `
            <label style="display:flex; align-items:center; justify-content:space-between; padding:0.4rem 0.6rem; border-radius:4px; cursor:pointer; background:var(--surface); border:1px solid var(--border-soft); font-size:0.8rem; user-select:none; transition:background 0.15s">
              <span style="display:flex; align-items:center; gap:0.5rem">
                <input type="checkbox" class="m-out-row-cb" value="${idx}" ${i === 0 ? 'checked' : ''} style="cursor:pointer; accent-color:var(--primary)">
                <strong>Row ${idx}</strong>
              </span>
              <span style="color:var(--ink-faint); font-family:monospace; font-size:0.75rem">${escHtml(valStr)}</span>
            </label>
          `;
        }).join("");

        const updateSelectedCount = () => {
          const cbs = Array.from(rowsContainer.querySelectorAll(".m-out-row-cb"));
          const checked = cbs.filter(cb => cb.checked);
          if (selectedCountEl) selectedCountEl.textContent = `${checked.length} of ${cbs.length} selected`;
          if (selectAllCb) {
            selectAllCb.checked = checked.length === cbs.length && cbs.length > 0;
            selectAllCb.indeterminate = checked.length > 0 && checked.length < cbs.length;
          }
        };

        rowsContainer.querySelectorAll(".m-out-row-cb").forEach(cb => {
          cb.addEventListener("change", updateSelectedCount);
        });

        if (selectAllCb) {
          selectAllCb.onchange = () => {
            rowsContainer.querySelectorAll(".m-out-row-cb").forEach(cb => {
              cb.checked = selectAllCb.checked;
            });
            updateSelectedCount();
          };
        }

        updateSelectedCount();
      }

      const colSchema = schemaCols.find(c => c.name === selectedCol) || {};
      const dtype = dtypes[selectedCol] || colSchema.dtype || "";
      const isNum = Boolean(colSchema.is_numeric || dtype.includes("int") || dtype.includes("float") || dtype.includes("number"));

      if (imputeMethodSel) {
        if (isNum) {
          imputeMethodSel.innerHTML = `
            <option value="median_excl_outliers" selected>Median (Excl. Outliers) — Recommended</option>
            <option value="mean_excl_outliers">Mean (Excl. Outliers)</option>
            <option value="median">Median (All Values)</option>
            <option value="mean">Mean (All Values)</option>
          `;
        } else {
          imputeMethodSel.innerHTML = `
            <option value="mode" selected>Mode (Most Frequent)</option>
          `;
        }
      }
    };

    const updateVisibility = () => {
      const resSel = document.getElementById("m-out-res");
      const manualWrap = document.getElementById("m-out-manual-wrap");
      const imputeWrap = document.getElementById("m-out-impute-wrap");
      if (!resSel) return;
      const val = resSel.value;
      if (manualWrap) manualWrap.classList.toggle("hidden", val !== "correct");
      if (imputeWrap) imputeWrap.classList.toggle("hidden", val !== "replace");
    };

    setTimeout(() => {
      const colSel = document.getElementById("m-out-col");
      const resSel = document.getElementById("m-out-res");
      if (colSel) colSel.onchange = updateRowsAndMethods;
      if (resSel) resSel.onchange = updateVisibility;
      updateRowsAndMethods();
      updateVisibility();
    }, 100);

  } catch (e) {
    showAlert(e.message, "error");
  }
}

// Issue 18 & Item 6/7: Dedicated Suspicious Values Resolution Modal with Multi-Row Selection & Real-Time Dropdown State Flow
async function showSuspiciousModal(dataset, container, defaultCol = null) {
  try {
    const analysisRes = await api.getAnalysis(dataset);
    let currentAnalysis = analysisRes.analysis || {};

    const getUnresolvedSuspCols = (an) => {
      const issues = (an.suspicious && an.suspicious.suspicious_issues) || [];
      const colMap = new Map();
      issues.forEach(iss => {
        const col = iss.column;
        if (!col) return;
        if (!colMap.has(col)) {
          colMap.set(col, { column: col, count: 0, indices: [], issues: [] });
        }
        const entry = colMap.get(col);
        const curCount = iss.count || (iss.indices ? iss.indices.length : 1);
        entry.count += curCount;
        if (iss.indices) {
          iss.indices.forEach(idx => {
            if (!entry.indices.includes(idx)) entry.indices.push(idx);
          });
        }
        entry.issues.push(iss);
      });
      return Array.from(colMap.values()).filter(c => c.count > 0 && c.indices.length > 0);
    };

    let suspCols = getUnresolvedSuspCols(currentAnalysis);

    if (!suspCols.length) {
      showAlert("🎉 No columns currently contain suspicious or invalid values!", "info");
      return;
    }

    let selectedCol = defaultCol && suspCols.some(c => c.column === defaultCol)
      ? defaultCol
      : suspCols[0].column;

    showModal({
      title: "Resolve Suspicious & Invalid Values",
      autoClose: false,
      body: `
        <div id="m-susp-body-wrap">
          <div class="form-group">
            <label class="form-label">Column with Suspicious Values</label>
            <select class="form-select" id="m-susp-col">
              ${suspCols.map(c => `
                <option value="${escHtml(c.column)}" ${c.column === selectedCol ? 'selected' : ''}>
                  ${escHtml(c.column)} (${c.count} suspicious value${c.count > 1 ? 's' : ''})
                </option>
              `).join("")}
            </select>
          </div>

          <div class="form-group">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.35rem">
              <label class="form-label" style="margin-bottom:0">Select Affected Rows</label>
              <label style="display:flex; align-items:center; gap:0.35rem; font-size:0.75rem; font-weight:600; cursor:pointer; color:var(--primary); user-select:none">
                <input type="checkbox" id="m-susp-select-all" style="cursor:pointer; accent-color:var(--primary)"> Select All (<span id="m-susp-total-count">0</span>)
              </label>
            </div>
            <div id="m-susp-rows-container" style="max-height:165px; overflow-y:auto; border:1px solid var(--border); border-radius:6px; padding:0.4rem; background:var(--surface-2); display:flex; flex-direction:column; gap:0.3rem"></div>
            <div class="form-hint" style="display:flex; justify-content:space-between; margin-top:0.35rem">
              <span>Select one or more rows to apply resolution in bulk.</span>
              <span id="m-susp-selected-count" style="font-weight:600; color:var(--primary)">0 selected</span>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Resolution Action</label>
            <select class="form-select" id="m-susp-res" style="border-color:#ef4444; font-weight:600">
              <option value="delete_row" selected>🗑️ Delete Affected Row(s) (Default / Recommended)</option>
              <option value="correct">✏️ Correct (Enter Verified Manual Value)</option>
              <option value="replace">🔄 Replace with Imputed Value</option>
              <option value="keep">✓ Keep (Verified Valid Domain Value — Log Decision)</option>
            </select>
            <div class="form-hint" id="m-susp-action-hint">
              Deleting affected rows removes corrupted or logically invalid records from the dataset.
            </div>
          </div>

          <div class="form-group hidden" id="m-susp-manual-wrap">
            <label class="form-label">Verified Replacement Value</label>
            <input class="form-input" id="m-susp-val" placeholder="Enter corrected value">
          </div>

          <div class="form-group hidden" id="m-susp-impute-wrap">
            <label class="form-label">Imputation Method</label>
            <select class="form-select" id="m-susp-impute-method">
              <option value="median_excl_outliers" selected>Median (Excl. Outliers)</option>
              <option value="mean_excl_outliers">Mean (Excl. Outliers)</option>
              <option value="mode">Mode (Most Frequent)</option>
            </select>
          </div>
        </div>
      `,
      confirmText: "🗑️ Delete Affected Row(s)",
      confirmClass: "btn-danger",
      onConfirm: async () => {
        const colSel = document.getElementById("m-susp-col");
        const resSel = document.getElementById("m-susp-res");
        if (!colSel) return;

        const col = colSel.value;
        const res = resSel.value;
        const manualVal = document.getElementById("m-susp-val") ? document.getElementById("m-susp-val").value : null;
        const imputeMethod = document.getElementById("m-susp-impute-method") ? document.getElementById("m-susp-impute-method").value : null;

        const checkedBoxes = Array.from(document.querySelectorAll(".m-susp-row-cb:checked"));
        const rowIndices = checkedBoxes.map(cb => parseInt(cb.value)).filter(n => !isNaN(n));

        if (!rowIndices.length) {
          showAlert("Please select at least one row to resolve.", "warning");
          return;
        }

        const confirmBtn = document.getElementById("modal-confirm");
        if (confirmBtn) {
          confirmBtn.disabled = true;
          confirmBtn.textContent = "Applying...";
        }

        try {
          const r = await api.resolveSuspicious(dataset, rowIndices, col, res, imputeMethod, manualVal);
          await updateTopbar(dataset);
          const desc = (r.entries && r.entries.length)
            ? `${r.entries.length} suspicious value(s) resolved for '${col}'`
            : "Suspicious value resolved.";
          showAlert(`✓ ${desc}`, "success");
          loadMissingOverview(container, dataset);
          loadCleaningTable(container, dataset);

          // Always re-fetch fresh state from server so dropdown filtering is 100% synchronized
          const freshRes = await api.getAnalysis(dataset);
          currentAnalysis = freshRes.analysis || r.analysis || {};
          suspCols = getUnresolvedSuspCols(currentAnalysis);

          if (!suspCols.length) {
            // All suspicious issues in the entire dataset have been resolved!
            const wrap = document.getElementById("m-susp-body-wrap");
            if (wrap) {
              wrap.innerHTML = `
                <div style="text-align:center; padding:2rem 1rem">
                  <div style="font-size:3rem; margin-bottom:0.75rem">🎉</div>
                  <div style="font-weight:800; font-size:1.15rem; color:var(--ink); margin-bottom:0.5rem">All Suspicious Values Resolved!</div>
                  <p style="color:var(--ink-faint); font-size:0.875rem; margin-bottom:1.5rem">No remaining unresolved suspicious or invalid values exist in this dataset.</p>
                </div>
              `;
            }
            const cancelBtn = document.getElementById("modal-cancel");
            if (cancelBtn) cancelBtn.style.display = "none";
            if (confirmBtn) {
              confirmBtn.disabled = false;
              confirmBtn.textContent = "Done";
              confirmBtn.className = "btn btn-success";
              confirmBtn.onclick = () => closeModal();
            }
            return;
          }

          // If the currently selected column is now fully resolved, select the next unresolved column
          if (!suspCols.some(c => c.column === selectedCol)) {
            selectedCol = suspCols[0].column;
          }

          // Rebuild column dropdown options from CURRENT unresolved state (removes resolved columns)
          colSel.innerHTML = suspCols.map(c => `
            <option value="${escHtml(c.column)}" ${c.column === selectedCol ? 'selected' : ''}>
              ${escHtml(c.column)} (${c.count} suspicious value${c.count > 1 ? 's' : ''})
            </option>
          `).join("");

          updateRows();
          updateResDisplay();
        } catch (e) {
          showAlert(e.message, "error");
        } finally {
          if (confirmBtn && suspCols.length > 0) {
            confirmBtn.disabled = false;
            updateResDisplay();
          }
        }
      }
    });

    const updateRows = () => {
      const colSel = document.getElementById("m-susp-col");
      const rowsContainer = document.getElementById("m-susp-rows-container");
      const selectAllCb = document.getElementById("m-susp-select-all");
      const totalCountEl = document.getElementById("m-susp-total-count");
      const selectedCountEl = document.getElementById("m-susp-selected-count");
      if (!colSel || !rowsContainer) return;
      selectedCol = colSel.value;
      const colEntry = suspCols.find(c => c.column === selectedCol);
      const indices = colEntry ? colEntry.indices : [];

      if (totalCountEl) totalCountEl.textContent = indices.length;

      if (!indices.length) {
        rowsContainer.innerHTML = `<div style="color:var(--ink-faint); font-size:0.8rem; padding:0.6rem; text-align:center">No unresolved suspicious rows in this column</div>`;
        if (selectAllCb) { selectAllCb.checked = false; selectAllCb.disabled = true; }
        if (selectedCountEl) selectedCountEl.textContent = "0 selected";
      } else {
        if (selectAllCb) { selectAllCb.checked = false; selectAllCb.disabled = false; }
        rowsContainer.innerHTML = indices.map((idx, i) => {
          const rowDetail = colEntry.issues.flatMap(iss => iss.row_details || []).find(d => d.row === idx);
          const detailVal = rowDetail && rowDetail.original_value !== undefined ? `"${rowDetail.original_value}"` : "";
          const detailReason = rowDetail && rowDetail.reason ? rowDetail.reason : "Suspicious Issue";
          return `
            <label style="display:flex; align-items:center; justify-content:space-between; padding:0.4rem 0.6rem; border-radius:4px; cursor:pointer; background:var(--surface); border:1px solid var(--border-soft); font-size:0.8rem; user-select:none; transition:background 0.15s">
              <span style="display:flex; align-items:center; gap:0.5rem">
                <input type="checkbox" class="m-susp-row-cb" value="${idx}" ${i === 0 ? "checked" : ""} style="cursor:pointer; accent-color:var(--primary)">
                <strong>Row ${idx}</strong>
                ${detailVal ? `<span class="badge badge-secondary" style="font-size:0.7rem; font-family:monospace">${escHtml(detailVal)}</span>` : ''}
              </span>
              <span style="color:var(--ink-faint); font-size:0.75rem; max-width:55%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap" title="${escHtml(detailReason)}">
                ${escHtml(detailReason)}
              </span>
            </label>
          `;
        }).join("");

        const updateSelectedCount = () => {
          const cbs = Array.from(rowsContainer.querySelectorAll(".m-susp-row-cb"));
          const checked = cbs.filter(cb => cb.checked);
          if (selectedCountEl) selectedCountEl.textContent = `${checked.length} of ${cbs.length} selected`;
          if (selectAllCb) {
            selectAllCb.checked = checked.length === cbs.length && cbs.length > 0;
            selectAllCb.indeterminate = checked.length > 0 && checked.length < cbs.length;
          }
          const btn = document.getElementById("modal-confirm");
          const resSel = document.getElementById("m-susp-res");
          if (btn && resSel && resSel.value === "delete_row") {
            btn.textContent = checked.length > 1 ? `🗑️ Delete ${checked.length} Selected Rows` : "🗑️ Delete Affected Row";
          }
        };

        rowsContainer.querySelectorAll(".m-susp-row-cb").forEach(cb => {
          cb.addEventListener("change", updateSelectedCount);
        });

        if (selectAllCb) {
          selectAllCb.onchange = () => {
            rowsContainer.querySelectorAll(".m-susp-row-cb").forEach(cb => {
              cb.checked = selectAllCb.checked;
            });
            updateSelectedCount();
          };
        }

        updateSelectedCount();
      }
    };

    const updateResDisplay = () => {
      const resSel = document.getElementById("m-susp-res");
      const manualWrap = document.getElementById("m-susp-manual-wrap");
      const imputeWrap = document.getElementById("m-susp-impute-wrap");
      if (!resSel) return;
      const val = resSel.value;
      if (manualWrap) manualWrap.classList.toggle("hidden", val !== "correct");
      if (imputeWrap) imputeWrap.classList.toggle("hidden", val !== "replace");

      const btn = document.getElementById("modal-confirm");
      if (btn && suspCols.length > 0) {
        if (val === "delete_row") {
          btn.className = "btn btn-danger";
          const count = document.querySelectorAll(".m-susp-row-cb:checked").length;
          btn.textContent = count > 1 ? `🗑️ Delete ${count} Selected Rows` : "🗑️ Delete Affected Row";
        } else {
          btn.className = "btn btn-primary";
          btn.textContent = "Apply Resolution";
        }
      }
    };

    setTimeout(() => {
      const colSel = document.getElementById("m-susp-col");
      const resSel = document.getElementById("m-susp-res");
      if (colSel) colSel.onchange = () => {
        updateRows();
        updateResDisplay();
      };
      if (resSel) resSel.onchange = updateResDisplay;
      updateRows();
      updateResDisplay();
    }, 100);

  } catch (e) {
    showAlert(e.message, "error");
  }
}

// Fill Missing Modal with Issues 4, 11, & 21 fixes
async function showFillMissingModal(dataset, defaultCol, container) {
  try {
    const [analysisRes, prevRes] = await Promise.all([
      api.getAnalysis(dataset),
      api.getDatasetPreview(dataset, { page: 0, pageSize: 1 })
    ]);

    const analysis = analysisRes.analysis || {};
    const missing = analysis.missing || {};
    const affectedCols = missing.affected_columns || [];
    const schemaCols = (analysis.schema || {}).columns || [];
    const dtypes = prevRes.dtypes || {};

    // Filter to only columns with missing values (Issue 11a)
    let missingColNames = affectedCols.map(c => c.column);
    if (!missingColNames.length) {
      missingColNames = schemaCols.filter(c => (c.missing_count ?? 0) > 0).map(c => c.name);
    }

    if (!missingColNames.length) {
      showAlert("🎉 No columns currently contain missing values!", "info");
      return;
    }

    const selectedCol = defaultCol && missingColNames.includes(defaultCol) ? defaultCol : missingColNames[0];

    showModal({
      title: "Fill Missing Values — Configure & Preview",
      body: `
        <div class="form-group">
          <label class="form-label">Select Column with Missing Values</label>
          <select class="form-select" id="m-fill-col">
            ${missingColNames.map(c => {
              const aff = affectedCols.find(a => a.column === c);
              const mCount = aff ? (aff.missing_count ?? aff.count ?? 0) : 0;
              const mPct = aff ? (aff.missing_pct ?? aff.pct ?? 0) : 0;
              const countBadge = aff ? ` (${mCount} missing, ${mPct}%)` : '';
              return `<option value="${escHtml(c)}" ${c === selectedCol ? 'selected' : ''}>${escHtml(c)}${countBadge}</option>`;
            }).join("")}
          </select>
        </div>

        <!-- Identifier Column Warning (Issue 4 & Issue 21b) -->
        <div id="m-id-warning" class="hidden" style="margin-bottom:1rem; padding:0.75rem; background:var(--warning-bg); border:1px solid var(--warning-border); border-radius:8px">
          <div style="font-weight:700; color:var(--warning); font-size:0.8125rem" id="m-id-warning-title">⚠️ Identifier-Like Column Detected</div>
          <div style="font-size:0.75rem; color:var(--ink-soft); margin-top:0.25rem" id="m-id-warning-desc">
            This column appears to be a unique identifier / primary key. Statistical imputation (Mean/Median/Mode) will create invalid or duplicate keys. Deleting the row or entering a manual key is recommended.
          </div>
        </div>

        <div class="form-group">
          <label class="form-label">Imputation Method</label>
          <select class="form-select" id="m-fill-method"></select>
          <div class="form-hint" id="m-method-hint">Select appropriate method for this column type.</div>
        </div>

        <div class="form-group hidden" id="m-manual-wrap">
          <label class="form-label">Manual Replacement Value</label>
          <input class="form-input" id="m-fill-val" placeholder="Enter value to replace missing cells">
          <div class="form-hint">This value will replace all missing cells in the selected column.</div>
        </div>
      `,
      confirmText: "Preview Imputation →",
      onConfirm: async () => {
        const col = document.getElementById("m-fill-col").value;
        const method = document.getElementById("m-fill-method").value;
        const manualVal = document.getElementById("m-fill-val") ? document.getElementById("m-fill-val").value : null;

        try {
          const prevData = await api.previewFillMissing(dataset, col, method, manualVal);
          showImputationPreviewModal(dataset, prevData, manualVal, container);
        } catch (e) {
          showAlert(e.message, "error");
        }
      }
    });

    setTimeout(() => {
      const colSel = document.getElementById("m-fill-col");
      const methodSel = document.getElementById("m-fill-method");
      const manualWrap = document.getElementById("m-manual-wrap");
      const idWarning = document.getElementById("m-id-warning");

      const updateMethodsForCol = () => {
        if (!colSel || !methodSel) return;
        const colName = colSel.value;
        const colSchema = schemaCols.find(c => c.name === colName) || {};
        const aff = affectedCols.find(a => a.column === colName) || {};
        const dtype = (dtypes[colName] || colSchema.dtype || aff.dtype || "").toLowerCase();
        const isNum = Boolean(aff.is_numeric || colSchema.is_numeric || dtype.includes("int") || dtype.includes("float") || dtype.includes("number"));
        const isIdentifier = Boolean(colSchema.is_identifier || aff.is_identifier);
        const idConf = colSchema.identifier_confidence || aff.identifier_confidence || "";

        if (idWarning) {
          if (isIdentifier) {
            idWarning.classList.remove("hidden");
            document.getElementById("m-id-warning-title").textContent = idConf === "strong" ? "🛑 Identifier Column Detected" : "⚠️ Possible Identifier Column";
          } else {
            idWarning.classList.add("hidden");
          }
        }

        if (isIdentifier) {
          methodSel.innerHTML = `
            <option value="delete_row" selected>Delete Affected Rows (Recommended for IDs)</option>
            <option value="manual">Manual Value Entry</option>
            <option value="leave_unchanged">Leave Unchanged</option>
          `;
        } else if (isNum) {
          // Issue 21c: Never offer Mode for numeric columns
          methodSel.innerHTML = `
            <option value="median_excl_outliers" selected>Median (Excluding Outliers) — Recommended</option>
            <option value="mean_excl_outliers">Mean (Excluding Outliers)</option>
            <option value="median">Median (All Values)</option>
            <option value="mean">Mean (All Values)</option>
            <option value="manual">Manual Value Entry</option>
            <option value="delete_row">Delete Affected Rows</option>
            <option value="leave_unchanged">Leave Unchanged</option>
          `;
        } else {
          // Categorical / string columns
          methodSel.innerHTML = `
            <option value="mode" selected>Mode (Most Frequent Value)</option>
            <option value="manual">Manual Value Entry</option>
            <option value="delete_row">Delete Affected Rows</option>
            <option value="leave_unchanged">Leave Unchanged</option>
          `;
        }

        if (manualWrap) manualWrap.classList.toggle("hidden", methodSel.value !== "manual");
      };

      if (colSel) colSel.onchange = updateMethodsForCol;
      if (methodSel) methodSel.onchange = () => { if (manualWrap) manualWrap.classList.toggle("hidden", methodSel.value !== "manual"); };
      updateMethodsForCol();
    }, 100);

  } catch (e) {
    showAlert(e.message, "error");
  }
}

function showImputationPreviewModal(dataset, prevData, manualVal, container) {
  const sampleTable = (prevData.sample_affected || []).map(r => `
    <tr>
      <td>${r.row}</td>
      <td style="color:#94a3b8"><em>Missing</em></td>
      <td style="color:#166534; font-weight:700">${escHtml(r.new)}</td>
    </tr>
  `).join("");

  showModal({
    title: `Preview Imputation — Column '${escHtml(prevData.column)}'`,
    body: `
      <div class="grid-2" style="gap:0.75rem; margin-bottom:1rem">
        <div class="stat-card"><div class="stat-label">Data Type</div><div class="stat-value" style="font-size:1rem">${escHtml(prevData.dtype)}</div></div>
        <div class="stat-card"><div class="stat-label">Missing Cells</div><div class="stat-value" style="color:#d97706">${prevData.missing_count} (${prevData.missing_pct}%)</div></div>
      </div>
      <div style="background:#f8fafc; padding:0.75rem 1rem; border-radius:8px; border:1px solid #e2e8f0; margin-bottom:1rem">
        <div style="font-size:0.8125rem; color:#334155"><strong>Method:</strong> ${escHtml(prevData.method)}</div>
        <div style="font-size:0.8125rem; color:#334155"><strong>Description:</strong> ${escHtml(prevData.description)}</div>
        <div style="font-size:0.875rem; color:#166534; font-weight:700; margin-top:0.25rem">Replacement Value: ${escHtml(prevData.replacement_value)}</div>
      </div>

      <h4 style="font-size:0.875rem; font-weight:700; color:#0f172a; margin-bottom:0.35rem">Sample Affected Records</h4>
      <div class="data-table-wrap" style="max-height:200px">
        <table class="data-table">
          <thead><tr><th>Row #</th><th>Original</th><th>New Imputed Value</th></tr></thead>
          <tbody>${sampleTable || '<tr><td colspan="3" style="text-align:center">No sample rows</td></tr>'}</tbody>
        </table>
      </div>
    `,
    confirmText: "Apply Changes Now",
    confirmClass: "btn-success",
    onConfirm: async () => {
      try {
        const res = await api.fillMissing(dataset, prevData.column, prevData.method, manualVal);
        await updateTopbar(dataset);
        showAlert(`✓ ${res.entry.description}`, "success");
        await loadMissingOverview(container, dataset);
        await loadCleaningTable(container, dataset);
      } catch (e) {
        showAlert(e.message, "error");
      }
    }
  });
}

function showCellEditModal(dataset, rowIdx, col, currentVal, container) {
  showModal({
    title: `Edit Cell [Row ${rowIdx}, Column '${col}']`,
    body: `
      <div class="form-group"><label class="form-label">Current Value</label><input class="form-input" value="${escHtml(currentVal)}" disabled></div>
      <div class="form-group"><label class="form-label">New Value</label><input class="form-input" id="m-edit-newval" value="${escHtml(currentVal)}"></div>
    `,
    confirmText: "Save Edit",
    onConfirm: async () => {
      const newVal = document.getElementById("m-edit-newval").value;
      try {
        const res = await api.editCell(dataset, rowIdx, col, newVal);
        await updateTopbar(dataset);
        showAlert(`✓ Cell [${rowIdx}, '${col}'] updated: '${currentVal}' → '${newVal}'`, "success");
        await loadMissingOverview(container, dataset);
        await loadCleaningTable(container, dataset);
      } catch (e) { showAlert(e.message, "error"); }
    }
  });
}

// ===== CHANGE HISTORY PAGE (Issue 12: Styled Cards) =====
export async function renderHistory(container, dataset) {
  try {
    const st = await api.getDatasetState(dataset);
    if (!st || st.state === "empty") {
      renderNoDatasetState(container, "Change History", dataset);
      return;
    }
  } catch {
    renderNoDatasetState(container, "Change History", dataset);
    return;
  }

  container.innerHTML = `<div class="loading-overlay" style="min-height:200px"><div class="spinner spinner-lg"></div><div class="loading-text">Loading history...</div></div>`;
  try {
    const res = await api.getHistory(dataset);
    const history = res.history || [];

    // Reverse chronological order for audit log
    const reversedHistory = [...history].reverse();

    container.innerHTML = `
      <div class="card">
        <div class="card-title" style="justify-content:space-between">
          <span>📋 Complete Change History — ${escHtml(dataset.toUpperCase())} Dataset</span>
          <span class="badge badge-info">${history.length} Action(s) Recorded</span>
        </div>
        <p style="color:#64748b; font-size:0.8125rem; margin-bottom:1.25rem">
          Comprehensive audit log of all modifications applied to the working dataset in chronological order.
        </p>
        ${!reversedHistory.length ? `
          <div class="empty-state">
            <div style="font-size:2.5rem; margin-bottom:0.5rem">📝</div>
            <div class="empty-title">No changes recorded yet</div>
            <div class="empty-sub">Actions taken in the Cleaning Studio will appear here with full audit trails.</div>
          </div>
        ` : `
          <div>
            ${reversedHistory.map(item => {
              const act = (item.action || "").toUpperCase();
              let badgeClass = "history-badge fill";
              let icon = "💉";
              let iconBg = "#dbeafe";

              if (act.includes("DELETE") || act.includes("DROP")) {
                badgeClass = "history-badge delete";
                icon = "🗑️";
                iconBg = "#fee2e2";
              } else if (act.includes("EDIT") || act.includes("MANUAL")) {
                badgeClass = "history-badge edit";
                icon = "✏️";
                iconBg = "#ede9fe";
              } else if (act.includes("TYPE") || act.includes("REPAIR")) {
                badgeClass = "history-badge type";
                icon = "🔧";
                iconBg = "#fef3c7";
              } else if (act.includes("RENAME")) {
                badgeClass = "history-badge rename";
                icon = "🏷️";
                iconBg = "#e0e7ff";
              } else if (act.includes("DUPLICATE")) {
                badgeClass = "history-badge duplicate";
                icon = "👯";
                iconBg = "#ffedd5";
              } else if (act.includes("OUTLIER")) {
                badgeClass = "history-badge outlier";
                icon = "🎯";
                iconBg = "#fce7f3";
              } else if (act.includes("RESET")) {
                badgeClass = "history-badge reset";
                icon = "🔄";
                iconBg = "#f1f5f9";
              }

              return `
                <div class="history-card">
                  <div class="history-icon-wrap" style="background:${iconBg}">${icon}</div>
                  <div class="history-content">
                    <div class="history-top">
                      <div style="display:flex; align-items:center; gap:0.5rem">
                        <span class="${badgeClass}">${escHtml(item.action)}</span>
                        ${item.column ? `<strong style="font-size:0.8125rem; color:#0f172a">'${escHtml(item.column)}'</strong>` : ''}
                      </div>
                      <span class="history-time">#${item.sequence} · ${item.timestamp ? item.timestamp.slice(0, 19).replace('T', ' ') : '—'}</span>
                    </div>
                    <div class="history-desc">${escHtml(item.description)}</div>
                    ${item.original_value !== undefined || item.new_value !== undefined ? `
                      <div class="history-meta">
                        ${item.original_value !== undefined ? `Original: <code style="background:#f1f5f9; padding:0.1rem 0.3rem; border-radius:3px">${escHtml(item.original_value)}</code> → ` : ''}
                        ${item.new_value !== undefined ? `New: <code style="background:#dcfce7; color:#166534; padding:0.1rem 0.3rem; border-radius:3px">${escHtml(item.new_value)}</code>` : ''}
                      </div>
                    ` : ''}
                  </div>
                </div>
              `;
            }).join("")}
          </div>
        `}
      </div>
    `;
  } catch (e) {
    container.innerHTML = `<div class="alert alert-error">✗ ${escHtml(e.message)}</div>`;
  }
}
