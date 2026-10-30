/* review.js — Reviewed / Finalized dataset inspection page */
import * as api from "./api.js";
import { navigate, showAlert, showModal, escHtml, renderNoDatasetState, updateTopbar } from "./app.js";
import { renderDataPreview } from "./datatable.js";

export async function renderReview(container, dataset) {
  try {
    const st = await api.getDatasetState(dataset);
    if (!st || st.state === "empty") {
      renderNoDatasetState(container, "Review & Finalize", dataset);
      return;
    }
  } catch {
    renderNoDatasetState(container, "Review & Finalize", dataset);
    return;
  }

  container.innerHTML = `<div class="loading-overlay" style="min-height:200px"><div class="spinner spinner-lg"></div><div class="loading-text">Loading dataset state...</div></div>`;
  try {
    const stateRes = await api.getDatasetState(dataset);
    renderReviewPage(container, dataset, stateRes);
  } catch (e) {
    container.innerHTML = `<div class="alert alert-error">✗ ${escHtml(e.message)}</div>`;
  }
}

function renderReviewPage(container, dataset, stateRes) {
  const isFinalized = stateRes.state === "finalized";
  const info = stateRes.current_info || stateRes.source_info || {};

  container.innerHTML = `
    <div id="review-alerts"></div>

    <div class="card">
      <div class="card-title">🔍 Reviewed Dataset Inspection — ${dataset.toUpperCase()} Dataset</div>
      <p style="color:var(--ink-faint); font-size:0.8125rem; margin-bottom:1rem">
        Inspect the real working dataset in its current state. Verify all cleaning operations before final approval.
      </p>

      <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:1rem; background:var(--surface-2); padding:0.75rem 1rem; border-radius:8px; border:1px solid var(--line)">
        <div>
          <span style="font-size:0.8125rem; font-weight:600; color:var(--ink)">Current Status: </span>
          <span class="badge ${isFinalized ? 'badge-success' : 'badge-warning'}" style="font-size:0.8125rem">
            ${isFinalized ? '✅ FINALIZED' : '⏳ IN REVIEW (Unfinalized)'}
          </span>
        </div>
        <div style="display:flex; gap:0.5rem; flex-wrap:wrap">
          <button class="btn btn-primary btn-sm" id="btn-make-more-changes">🧹 Make More Changes</button>
          <button class="btn btn-success btn-sm" id="btn-finalize-dataset" ${isFinalized ? 'disabled' : ''}>
            ${isFinalized ? '✓ Finalized' : '🔒 Finalize Dataset'}
          </button>
        </div>
      </div>

      <!-- Dataset Stats Banner -->
      <div class="grid-3" style="margin-bottom:1.25rem">
        <div class="stat-card"><div class="stat-label">Current Rows</div><div class="stat-value">${info.rows || 0}</div></div>
        <div class="stat-card"><div class="stat-label">Current Columns</div><div class="stat-value">${info.cols || 0}</div></div>
        <div class="stat-card"><div class="stat-label">Change History Count</div><div class="stat-value">${stateRes.change_count || 0}</div></div>
      </div>

      <!-- Actual DataFrame Table with Full Pagination -->
      <div id="review-table-container"></div>
    </div>
  `;

  const tableContainer = container.querySelector("#review-table-container");
  if (tableContainer) {
    renderDataPreview(tableContainer, dataset, { defaultRows: 15, which: "working" });
  }

  container.querySelector("#btn-make-more-changes").onclick = () => navigate("cleaning", { dataset });
  container.querySelector("#btn-finalize-dataset").onclick = () => {
    showModal({
      title: `Finalize ${dataset.toUpperCase()} Dataset?`,
      body: `<p>Finalizing locks the current working dataset state for reporting and comparison. You can still make more changes later if needed.</p>`,
      confirmText: "Finalize Now",
      confirmClass: "btn-success",
      onConfirm: async () => {
        try {
          await api.finalizeDataset(dataset);
          await updateTopbar(dataset);
          showAlert(`✓ ${dataset.toUpperCase()} dataset finalized!`, "success");
          renderReview(container, dataset);
        } catch (e) { showAlert(e.message, "error"); }
      }
    });
  };
}
