/* reports.js — Report generation and download hub */
import * as api from "./api.js";
import { state, showAlert, escHtml } from "./app.js";

function getSafeErrorMessage(e) {
  const msg = e && e.message ? String(e.message) : "";
  if (!msg || msg.includes("truth value of a DataFrame") || msg.includes("ambiguous") || msg.includes("Traceback") || msg.includes("500")) {
    return "Failed to generate report. Please ensure your dataset is loaded and try again.";
  }
  return msg;
}

export function renderReports(container, opts = {}) {
  const mode = state.mode || "single";

  if (mode === "single") {
    renderSingleReports(container);
  } else {
    renderCompareReports(container);
  }
}

function renderSingleReports(container) {
  container.innerHTML = `
    <div id="report-alerts"></div>

    <div class="card">
      <div class="card-title">📄 Reports &amp; Downloads Hub</div>
      <p style="color:var(--ink-faint); font-size:0.8125rem; margin-bottom:1.5rem">
        Generate professional Data Quality &amp; Profiling Reports in HTML and PDF formats, export the cleaned dataset, or download the audit log.
      </p>

      <div class="grid-2" style="margin-bottom:1.25rem">
        <!-- HTML Report Card -->
        <div class="stat-card" style="display:flex; flex-direction:column; justify-content:space-between">
          <div>
            <div style="font-size:2rem; margin-bottom:0.5rem">🌐</div>
            <div style="font-size:1rem; font-weight:700; color:var(--ink)">Interactive HTML Report</div>
            <div style="font-size:0.75rem; color:var(--ink-faint); margin:0.35rem 0 1rem; line-height:1.4">
              Standalone, fully responsive HTML report containing all quality metrics, issue breakdown, factor scores, and recommendations.
            </div>
          </div>
          <button class="btn btn-primary" id="btn-dl-html" style="width:100%">Download HTML Report</button>
        </div>

        <!-- PDF Report Card -->
        <div class="stat-card" style="display:flex; flex-direction:column; justify-content:space-between">
          <div>
            <div style="font-size:2rem; margin-bottom:0.5rem">📕</div>
            <div style="font-size:1rem; font-weight:700; color:var(--ink)">Formal PDF Report</div>
            <div style="font-size:0.75rem; color:var(--ink-faint); margin:0.35rem 0 1rem; line-height:1.4">
              Print-ready PDF report with Quality Score on page 1, structured summary tables, and full cleaning history.
            </div>
          </div>
          <button class="btn btn-purple" id="btn-dl-pdf" style="width:100%">Download PDF Report</button>
        </div>
      </div>

      <div class="grid-2">
        <!-- Cleaned Dataset Download -->
        <div class="stat-card" style="display:flex; flex-direction:column; justify-content:space-between">
          <div>
            <div style="font-size:2rem; margin-bottom:0.5rem">💾</div>
            <div style="font-size:1rem; font-weight:700; color:var(--ink)">Cleaned CSV Dataset</div>
            <div style="font-size:0.75rem; color:var(--ink-faint); margin:0.35rem 0 1rem; line-height:1.4">
              Export the latest dataset with all cleaning transformations, type repairs, and missing-value fills applied.
            </div>
          </div>
          <button class="btn btn-success" id="btn-dl-ds" style="width:100%">Download Cleaned CSV</button>
        </div>

        <!-- Missing Values Log Download -->
        <div class="stat-card" style="display:flex; flex-direction:column; justify-content:space-between">
          <div>
            <div style="font-size:2rem; margin-bottom:0.5rem">📥</div>
            <div style="font-size:1rem; font-weight:700; color:var(--ink)">Missing Values Audit Log</div>
            <div style="font-size:0.75rem; color:var(--ink-faint); margin:0.35rem 0 1rem; line-height:1.4">
              Dedicated audit spreadsheet (.xlsx) tracking every originally-missing cell, its resolution method, and final state.
            </div>
          </div>
          <button class="btn btn-amber" id="btn-dl-missing-log" style="width:100%">Download Missing Log (.xlsx)</button>
        </div>
      </div>
    </div>
  `;

  container.querySelector("#btn-dl-html").onclick = async () => {
    try {
      await api.downloadHTMLReport("single", "analysis");
      showAlert("✓ HTML report download started.", "success");
    } catch (e) { showAlert(getSafeErrorMessage(e), "error"); }
  };

  container.querySelector("#btn-dl-pdf").onclick = async () => {
    try {
      await api.downloadPDFReport("single", "analysis");
      showAlert("✓ PDF report download started.", "success");
    } catch (e) { showAlert(getSafeErrorMessage(e), "error"); }
  };

  container.querySelector("#btn-dl-ds").onclick = () => api.downloadDataset("single");

  container.querySelector("#btn-dl-missing-log").onclick = () => {
    try {
      api.downloadMissingLog("single");
      showAlert("✓ Download started: Missing Values Audit Log.", "success");
    } catch (e) { showAlert(getSafeErrorMessage(e), "error"); }
  };
}

function renderCompareReports(container) {
  container.innerHTML = `
    <div id="report-alerts"></div>

    <div class="card">
      <div class="card-title">📄 Reports &amp; Downloads Hub — Two Dataset Mode</div>
      <p style="color:var(--ink-faint); font-size:0.8125rem; margin-bottom:1.5rem">
        Export dedicated artifacts covering standalone dataset audits, cross-dataset comparative reporting, cleaned datasets, and audit logs.
      </p>

      <!-- Artifact (a): Reference Dataset Report (PDF ONLY) -->
      <h3 style="font-size:0.9375rem; font-weight:800; color:var(--ink); margin-bottom:0.75rem">1. Reference Dataset Report (Standalone Profile)</h3>
      <div style="margin-bottom:1.5rem">
        <div class="stat-card" style="display:flex; align-items:center; justify-content:space-between">
          <div style="display:flex; align-items:center; gap:1rem">
            <div style="font-size:2rem">📕</div>
            <div>
              <div style="font-weight:700; font-size:0.9375rem; color:var(--ink)">Reference Dataset Formal PDF Report</div>
              <p style="font-size:0.75rem; color:var(--ink-faint); margin:0.2rem 0 0">
                Print-ready PDF report for the Reference dataset with Data Quality Score on page 1, structured summary tables, and full cleaning history (PDF only).
              </p>
            </div>
          </div>
          <button class="btn btn-purple" id="btn-dl-ref-pdf" style="white-space:nowrap">Download Reference PDF →</button>
        </div>
      </div>

      <!-- Artifact (b): Current Dataset Report (PDF ONLY) -->
      <h3 style="font-size:0.9375rem; font-weight:800; color:var(--ink); margin-bottom:0.75rem">2. Current Dataset Report (Standalone Profile)</h3>
      <div style="margin-bottom:1.5rem">
        <div class="stat-card" style="display:flex; align-items:center; justify-content:space-between">
          <div style="display:flex; align-items:center; gap:1rem">
            <div style="font-size:2rem">📕</div>
            <div>
              <div style="font-weight:700; font-size:0.9375rem; color:var(--ink)">Current Dataset Formal PDF Report</div>
              <p style="font-size:0.75rem; color:var(--ink-faint); margin:0.2rem 0 0">
                Print-ready PDF report for the Current dataset with Data Quality Score on page 1, structured summary tables, and full cleaning history (PDF only).
              </p>
            </div>
          </div>
          <button class="btn btn-purple" id="btn-dl-cur-pdf" style="white-space:nowrap">Download Current PDF →</button>
        </div>
      </div>

      <!-- Artifact (c): Comparison Report (Both HTML and PDF) -->
      <h3 style="font-size:0.9375rem; font-weight:800; color:var(--ink); margin-bottom:0.75rem">3. Comparison Report (Cross-Dataset Audit)</h3>
      <div class="grid-2" style="margin-bottom:1.5rem">
        <div class="stat-card">
          <div style="font-size:1.5rem; margin-bottom:0.35rem">⚖️</div>
          <div style="font-weight:700; font-size:0.9375rem; color:var(--ink)">Comparison Report (HTML)</div>
          <p style="font-size:0.75rem; color:var(--ink-faint); margin:0.35rem 0 0.75rem">
            Interactive comparative report containing ONLY comparison findings: executive narrative, schema/row/cell diffs, and drift.
          </p>
          <button class="btn btn-primary btn-sm" id="btn-dl-comp-html">Download Comparison HTML →</button>
        </div>
        <div class="stat-card">
          <div style="font-size:1.5rem; margin-bottom:0.35rem">📑</div>
          <div style="font-weight:700; font-size:0.9375rem; color:var(--ink)">Comparison Report (PDF)</div>
          <p style="font-size:0.75rem; color:var(--ink-faint); margin:0.35rem 0 0.75rem">
            Formal PDF audit summarizing schema evolution, data shift, most changed columns, and distribution drift.
          </p>
          <button class="btn btn-purple btn-sm" id="btn-dl-comp-pdf">Download Comparison PDF →</button>
        </div>
      </div>

      <!-- Artifact (d): Cleaned CSV Exports -->
      <h3 style="font-size:0.9375rem; font-weight:800; color:var(--ink); margin-bottom:0.75rem">4. Cleaned Datasets (CSV Downloads)</h3>
      <div class="grid-2" style="margin-bottom:1.5rem">
        <div class="stat-card" style="display:flex; align-items:center; justify-content:space-between">
          <div>
            <div style="font-weight:700; color:var(--ink)">Reference Dataset</div>
            <div style="font-size:0.75rem; color:var(--ink-faint)">Cleaned baseline CSV data file</div>
          </div>
          <button class="btn btn-success btn-sm" id="btn-dl-ref-csv">Download Ref CSV</button>
        </div>
        <div class="stat-card" style="display:flex; align-items:center; justify-content:space-between">
          <div>
            <div style="font-weight:700; color:var(--ink)">Current Dataset</div>
            <div style="font-size:0.75rem; color:var(--ink-faint)">Cleaned present CSV data file</div>
          </div>
          <button class="btn btn-success btn-sm" id="btn-dl-cur-csv">Download Cur CSV</button>
        </div>
      </div>

      <!-- Artifact (e): Missing Values Audit Logs -->
      <h3 style="font-size:0.9375rem; font-weight:800; color:var(--ink); margin-bottom:0.75rem">5. Missing Values Audit Logs (.xlsx)</h3>
      <div class="grid-2">
        <div class="stat-card" style="display:flex; align-items:center; justify-content:space-between">
          <div>
            <div style="font-weight:700; color:var(--ink)">Reference Missing Log</div>
            <div style="font-size:0.75rem; color:var(--ink-faint)">Audit spreadsheet of missing values &amp; resolutions in Reference</div>
          </div>
          <button class="btn btn-amber btn-sm" id="btn-dl-ref-missing-log">Download Ref Log (.xlsx)</button>
        </div>
        <div class="stat-card" style="display:flex; align-items:center; justify-content:space-between">
          <div>
            <div style="font-weight:700; color:var(--ink)">Current Missing Log</div>
            <div style="font-size:0.75rem; color:var(--ink-faint)">Audit spreadsheet of missing values &amp; resolutions in Current</div>
          </div>
          <button class="btn btn-amber btn-sm" id="btn-dl-cur-missing-log">Download Cur Log (.xlsx)</button>
        </div>
      </div>
    </div>
  `;

  // Wire buttons: Artifact (a) Reference Dataset Report (PDF ONLY)
  container.querySelector("#btn-dl-ref-pdf").onclick = async () => {
    try {
      await api.downloadPDFReport("compare", "reference");
      showAlert("✓ Reference Dataset PDF report download started.", "success");
    } catch (e) { showAlert(getSafeErrorMessage(e), "error"); }
  };

  // Wire buttons: Artifact (b) Current Dataset Report (PDF ONLY)
  container.querySelector("#btn-dl-cur-pdf").onclick = async () => {
    try {
      await api.downloadPDFReport("compare", "current");
      showAlert("✓ Current Dataset PDF report download started.", "success");
    } catch (e) { showAlert(getSafeErrorMessage(e), "error"); }
  };

  // Wire buttons: Artifact (c) Comparison Report (HTML and PDF)
  container.querySelector("#btn-dl-comp-html").onclick = async () => {
    try {
      await api.downloadHTMLReport("compare", "comparison");
      showAlert("✓ Comparison HTML report download started.", "success");
    } catch (e) { showAlert(getSafeErrorMessage(e), "error"); }
  };

  container.querySelector("#btn-dl-comp-pdf").onclick = async () => {
    try {
      await api.downloadPDFReport("compare", "comparison");
      showAlert("✓ Comparison PDF report download started.", "success");
    } catch (e) { showAlert(getSafeErrorMessage(e), "error"); }
  };

  // Wire buttons: Artifact (d) CSV Downloads
  container.querySelector("#btn-dl-ref-csv").onclick = () => api.downloadDataset("ref");
  container.querySelector("#btn-dl-cur-csv").onclick = () => api.downloadDataset("cur");

  // Wire buttons: Artifact (e) Missing Values Audit Logs
  container.querySelector("#btn-dl-ref-missing-log").onclick = () => {
    try {
      api.downloadMissingLog("ref");
      showAlert("✓ Download started: Reference Missing Values Audit Log.", "success");
    } catch (e) { showAlert(getSafeErrorMessage(e), "error"); }
  };

  container.querySelector("#btn-dl-cur-missing-log").onclick = () => {
    try {
      api.downloadMissingLog("cur");
      showAlert("✓ Download started: Current Missing Values Audit Log.", "success");
    } catch (e) { showAlert(getSafeErrorMessage(e), "error"); }
  };
}
