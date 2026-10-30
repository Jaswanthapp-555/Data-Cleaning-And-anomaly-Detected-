/* datatable.js — Shared paginated dataset preview component used by all pages */
import * as api from "./api.js";
import { escHtml } from "./app.js";

/**
 * Render a smart dataset preview with a fast initial view and a full paginated viewer.
 * @param {HTMLElement} container  — element to render into
 * @param {string}      dataset    — "single" | "ref" | "cur"
 * @param {object}      opts
 * @param {number}      opts.defaultRows  — fast-preview row count (default 10)
 * @param {string}      opts.which        — "working" | "original" | "finalized"
 */
export async function renderDataPreview(container, dataset, opts = {}) {
  const defaultRows = opts.defaultRows || 10;
  const which = opts.which || "working";

  container.innerHTML = `<div class="loading-overlay" style="min-height:120px"><div class="spinner"></div></div>`;

  try {
    const data = await api.getDatasetPreview(dataset, { page: 0, pageSize: defaultRows, which });
    container.innerHTML = `
      <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:0.5rem">
        <span style="font-size:0.8125rem; color:var(--ink-faint); font-weight:600">
          Preview — First ${data.records ? data.records.length : 0} rows
          <span style="color:var(--ink-faint); font-weight:400">(of ${data.total || 0} total)</span>
        </span>
        <button class="btn btn-ghost btn-sm" id="dt-view-full">
          View Full Dataset →
        </button>
      </div>
      <div id="dt-preview-table">${_renderTable(data)}</div>
      <div id="dt-full-view" class="hidden"></div>
    `;

    container.querySelector("#dt-view-full").onclick = () => _openFullView(container, dataset, which);
  } catch (e) {
    container.innerHTML = `<div class="alert alert-error">✗ ${escHtml(e.message)}</div>`;
  }
}

async function _openFullView(container, dataset, which) {
  const fullDiv = container.querySelector("#dt-full-view");
  const previewDiv = container.querySelector("#dt-preview-table");
  const btn = container.querySelector("#dt-view-full");

  if (!fullDiv.classList.contains("hidden")) {
    // Toggle back to preview
    fullDiv.classList.add("hidden");
    previewDiv.style.display = "";
    btn.textContent = "View Full Dataset →";
    return;
  }

  btn.textContent = "← Back to Preview";
  previewDiv.style.display = "none";
  fullDiv.classList.remove("hidden");
  await _renderFullTable(fullDiv, dataset, which, 0, 25);
}

async function _renderFullTable(container, dataset, which, page, pageSize) {
  container.innerHTML = `<div class="loading-overlay" style="min-height:150px"><div class="spinner spinner-lg"></div></div>`;

  try {
    const data = await api.getDatasetPreview(dataset, { page, pageSize, which });
    const totalPages = data.total_pages || 1;

    container.innerHTML = `
      <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:0.75rem; flex-wrap:wrap; gap:0.5rem">
        <div style="display:flex; align-items:center; gap:0.5rem">
          <span style="font-size:0.75rem; font-weight:700; color:var(--ink-soft)">Rows per page:</span>
          <select class="form-select" id="dt-page-size" style="width:auto; padding:0.3rem 0.6rem; font-size:0.75rem">
            <option value="25" ${pageSize===25?'selected':''}>25</option>
            <option value="50" ${pageSize===50?'selected':''}>50</option>
            <option value="100" ${pageSize===100?'selected':''}>100</option>
          </select>
        </div>
        <div style="display:flex; align-items:center; gap:0.5rem">
          <button class="btn btn-secondary btn-sm" id="dt-prev" ${page===0?'disabled':''}>← Prev</button>
          <span style="font-size:0.8125rem; color:var(--ink-faint)">
            Page <strong>${page+1}</strong> of ${totalPages} &nbsp;·&nbsp; ${data.total || 0} rows
          </span>
          <button class="btn btn-secondary btn-sm" id="dt-next" ${page>=totalPages-1?'disabled':''}>Next →</button>
        </div>
      </div>
      ${_renderTable(data)}
    `;

    container.querySelector("#dt-prev").onclick = () => _renderFullTable(container, dataset, which, Math.max(0, page-1), pageSize);
    container.querySelector("#dt-next").onclick = () => _renderFullTable(container, dataset, which, Math.min(totalPages-1, page+1), pageSize);
    container.querySelector("#dt-page-size").onchange = (e) => _renderFullTable(container, dataset, which, 0, parseInt(e.target.value));
  } catch (e) {
    container.innerHTML = `<div class="alert alert-error">✗ ${escHtml(e.message)}</div>`;
  }
}

function _renderTable(data) {
  if (!data || !data.records || !data.records.length) {
    return `<p style="color:var(--ink-faint); font-size:0.8125rem; padding:1rem 0">No rows available.</p>`;
  }
  const cols = data.columns || [];
  let html = `<div class="data-table-wrap" style="max-height:360px"><table class="data-table"><thead><tr>
    <th style="width:48px; color:var(--ink-faint)">#</th>
    ${cols.map(c => `<th>${escHtml(c)}</th>`).join("")}
  </tr></thead><tbody>`;
  const pageStart = (data.page || 0) * (data.page_size || 10);
  data.records.forEach((row, i) => {
    html += `<tr><td style="color:var(--ink-faint); font-size:0.7rem">${pageStart + i}</td>`;
    cols.forEach(c => {
      const val = row[c];
      html += val === null || val === undefined
        ? `<td><span class="null-cell">null</span></td>`
        : `<td>${escHtml(val)}</td>`;
    });
    html += `</tr>`;
  });
  html += `</tbody></table></div>`;
  return html;
}
