/* upload.js — Clean, professional upload module for CSV & Excel datasets */
import * as api from "./api.js";
import { state, navigate, showAlert, escHtml, updateTopbar } from "./app.js";
import { renderDataPreview } from "./datatable.js";

// ===== HOME / MODE SELECTION =====
export function renderHome(container) {
  container.innerHTML = `
    <div style="max-width:720px; margin:2.5rem auto; text-align:center">
      <!-- Hero Icon -->
      <div style="width:64px; height:64px; margin:0 auto 1.25rem; background:var(--info-bg); border:1px solid var(--info-border); border-radius:18px; display:flex; align-items:center; justify-content:center; color:var(--accent); box-shadow:var(--e2)">
        <svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
        </svg>
      </div>

      <h1 style="font-size:2rem; font-weight:900; color:var(--ink); margin-bottom:0.5rem; letter-spacing:-0.025em">
        Automated Data Quality &amp; Anomaly Profiler
      </h1>
      <p style="color:var(--ink-faint); font-size:0.9375rem; line-height:1.5; margin-bottom:1.5rem">
        Analyze, understand, clean, and compare your datasets with statistical confidence.
      </p>

      <!-- Feature Pills -->
      <div class="feature-pills">
        <span class="feature-pill">
          <svg viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/></svg>
          Missing Values Detection
        </span>
        <span class="feature-pill">
          <svg viewBox="0 0 24 24"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>
          Duplicate Elimination
        </span>
        <span class="feature-pill">
          <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
          Anomaly &amp; Outlier Profiling
        </span>
        <span class="feature-pill">
          <svg viewBox="0 0 24 24"><path d="M10 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h5v-2H5V5h5V3zm9 0h-5v2h5v14h-5v2h5c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2z"/></svg>
          Version Comparison
        </span>
      </div>

      <!-- Subtle Decorative Anomaly Detection & Quality Constellation Visual (Issue UI-5) -->
      <div class="home-viz-card" aria-hidden="true">
        <div class="home-viz-header">
          <span class="home-viz-badge">
            <span class="home-viz-ping"></span>
            Statistical Distribution &amp; Anomaly Profiler
          </span>
          <span class="home-viz-tag">Real-Time Engine</span>
        </div>
        <svg class="home-viz-canvas" viewBox="0 0 680 170" fill="none" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <linearGradient id="scanGradient" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stop-color="#3b5bfd" stop-opacity="0"/>
              <stop offset="50%" stop-color="#8b5cf6" stop-opacity="0.22"/>
              <stop offset="100%" stop-color="#3b5bfd" stop-opacity="0"/>
            </linearGradient>
            <linearGradient id="curveGrad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stop-color="#3b5bfd" stop-opacity="0.4"/>
              <stop offset="50%" stop-color="#8b5cf6" stop-opacity="0.85"/>
              <stop offset="100%" stop-color="#3b5bfd" stop-opacity="0.4"/>
            </linearGradient>
            <linearGradient id="fillGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#6366f1" stop-opacity="0.14"/>
              <stop offset="100%" stop-color="#6366f1" stop-opacity="0"/>
            </linearGradient>
          </defs>

          <!-- Subtle Background Grid -->
          <line x1="40" y1="35" x2="640" y2="35" stroke="currentColor" stroke-opacity="0.08" stroke-dasharray="3 3"/>
          <line x1="40" y1="80" x2="640" y2="80" stroke="currentColor" stroke-opacity="0.08" stroke-dasharray="3 3"/>
          <line x1="40" y1="125" x2="640" y2="125" stroke="currentColor" stroke-opacity="0.08" stroke-dasharray="3 3"/>

          <!-- Statistical Density Curve (Gaussian Anomaly Bell Distribution) -->
          <path d="M 40 140 C 160 140, 230 135, 290 85 C 330 50, 350 40, 370 40 C 390 40, 410 50, 450 85 C 510 135, 560 140, 640 140" fill="none" stroke="url(#curveGrad)" stroke-width="2.5" stroke-linecap="round"/>
          <path d="M 40 140 C 160 140, 230 135, 290 85 C 330 50, 350 40, 370 40 C 390 40, 410 50, 450 85 C 510 135, 560 140, 640 140 L 640 155 L 40 155 Z" fill="url(#fillGrad)"/>

          <!-- 3xIQR Fence Threshold Limit Line -->
          <line x1="520" y1="20" x2="520" y2="150" stroke="#f59e0b" stroke-width="1.2" stroke-dasharray="4 4" stroke-opacity="0.8"/>
          <text x="525" y="32" fill="#f59e0b" font-size="9" font-weight="700" letter-spacing="0.05em">3×IQR FENCE</text>

          <!-- Connected Data Points Mesh -->
          <g class="viz-nodes">
            <circle cx="130" cy="138" r="3.5" fill="#3b5bfd" opacity="0.6"/>
            <circle cx="200" cy="132" r="4" fill="#3b5bfd" opacity="0.7"/>
            <circle cx="260" cy="115" r="4" fill="#6366f1" opacity="0.8"/>
            <circle cx="315" cy="74" r="4.5" fill="#8b5cf6" opacity="0.85"/>
            <circle cx="370" cy="40" r="5" fill="#a855f7" opacity="0.95"/>
            <circle cx="425" cy="74" r="4.5" fill="#8b5cf6" opacity="0.85"/>
            <circle cx="480" cy="115" r="4" fill="#6366f1" opacity="0.8"/>
            <line x1="260" y1="115" x2="315" y2="74" stroke="#8b5cf6" stroke-opacity="0.3" stroke-width="1"/>
            <line x1="315" y1="74" x2="370" y2="40" stroke="#8b5cf6" stroke-opacity="0.4" stroke-width="1"/>
            <line x1="370" y1="40" x2="425" y2="74" stroke="#8b5cf6" stroke-opacity="0.4" stroke-width="1"/>
            <line x1="425" y1="74" x2="480" y2="115" stroke="#8b5cf6" stroke-opacity="0.3" stroke-width="1"/>

            <!-- Anomaly Beacon Node (Beyond Fence with Subtle Pulse) -->
            <g class="viz-anomaly-beacon">
              <circle cx="585" cy="46" r="14" fill="#ef4444" fill-opacity="0.12" class="viz-ping-ring"/>
              <circle cx="585" cy="46" r="5" fill="#ef4444" stroke="#ffffff" stroke-width="1.5"/>
              <text x="540" y="66" fill="#ef4444" font-size="9" font-weight="800">ANOMALY BEACON</text>
              <line x1="520" y1="46" x2="580" y2="46" stroke="#ef4444" stroke-width="1" stroke-dasharray="2 2" stroke-opacity="0.7"/>
            </g>
          </g>

          <!-- Laser Scan Line -->
          <rect class="viz-scanner" x="0" y="15" width="110" height="135" fill="url(#scanGradient)" opacity="0.8"/>
        </svg>
      </div>

      <div class="mode-select-grid">
        <div class="mode-card tilt-card" id="mode-single">
          <div class="mode-icon-wrap">
            <svg style="width:28px; height:28px; fill:currentColor" viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V5h14v14zM7 10h2v7H7zm4-3h2v10h-2zm4 6h2v4h-2z"/></svg>
          </div>
          <div class="mode-title">Single Dataset</div>
          <div class="mode-desc">Analyze and clean a single dataset to detect missing values, duplicates, and statistical anomalies.</div>
          <button class="btn btn-primary btn-lg" style="margin-top:1.5rem; width:100%">Select Single Dataset →</button>
        </div>

        <div class="mode-card tilt-card" id="mode-compare">
          <div class="mode-icon-wrap">
            <svg style="width:28px; height:28px; fill:currentColor" viewBox="0 0 24 24"><path d="M10 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h5v-2H5V5h5V3zm9 0h-5v2h5v14h-5v2h5c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2z"/></svg>
          </div>
          <div class="mode-title">Compare Datasets</div>
          <div class="mode-desc">Analyze, clean, and compare a Reference dataset with a Current dataset to detect version changes and schema drift.</div>
          <button class="btn btn-primary btn-lg" style="margin-top:1.5rem; width:100%">Compare Datasets →</button>
        </div>
      </div>
    </div>
  `;

  container.querySelector("#mode-single").onclick = () => selectMode("single");
  container.querySelector("#mode-compare").onclick = () => selectMode("compare");
}

function selectMode(mode) {
  state.mode = mode;
  import("./app.js").then(m => m.renderSidebar());
  if (mode === "single") navigate("upload-single");
  else navigate("upload-ref");
}

// ===== UPLOAD PAGE =====
export async function renderUpload(container, dataset) {
  const label = dataset === "single"
    ? "Upload Dataset"
    : dataset === "ref"
    ? "Upload Reference Dataset (Baseline)"
    : "Upload Current Dataset (Present)";

  container.innerHTML = `
    <div id="upload-alerts"></div>

    <div class="card" style="max-width:720px; margin:0 auto">
      <div class="card-title">${escHtml(label)}</div>
      <p style="color:var(--ink-faint); font-size:0.8125rem; margin-bottom:1.5rem">
        Upload a CSV or Excel file to begin automated data quality analysis and anomaly profiling.
      </p>

      <!-- Clean Single Dropzone -->
      <div class="upload-dropzone" id="file-dropzone">
        <div class="dz-icon">
          <svg style="width:24px; height:24px; fill:currentColor" viewBox="0 0 24 24"><path d="M9 16h6v-6h4l-7-7-7 7h4zm-4 2h14v2H5z"/></svg>
        </div>
        <div class="dz-title">Drag &amp; drop your file here</div>
        <div class="dz-sub">or click to browse from your computer</div>
        <div class="dz-formats">Supported formats: CSV • XLSX • XLS</div>
        <input type="file" id="file-input" accept=".csv,.xlsx,.xls" style="display:none">
      </div>

      <!-- Excel Sheet Selector (Hidden initially) -->
      <div id="excel-sheet-card" class="hidden" style="margin-top:1.25rem; padding:1.25rem; background:var(--surface-2); border:1px solid var(--line); border-radius:8px">
        <div style="font-weight:700; font-size:0.875rem; color:var(--ink); margin-bottom:0.25rem" id="excel-filename-label">Excel Workbook</div>
        <div style="font-size:0.75rem; color:var(--ink-faint); margin-bottom:1rem" id="excel-filesize-label"></div>

        <div class="form-group">
          <label class="form-label">Select Worksheet to Analyze</label>
          <select class="form-select" id="excel-sheet-select"></select>
        </div>
        <button class="btn btn-primary" id="btn-load-excel-sheet">Load Selected Sheet →</button>
      </div>
    </div>

    <!-- Dataset Ready Summary & Preview Card (Only shown after backend confirmation) -->
    <div id="dataset-ready-section" class="hidden" style="max-width:720px; margin:1.25rem auto 0">
      <div class="card">
        <div class="card-title" style="color:var(--success)">✓ Dataset Loaded &amp; Ready</div>

        <div class="file-state-card" style="margin-bottom:1.25rem">
          <div class="file-info">
            <div class="file-badge-icon" id="ready-type-badge">CSV</div>
            <div>
              <div style="font-weight:700; font-size:0.9375rem; color:var(--ink)" id="ready-filename">dataset.csv</div>
              <div style="font-size:0.75rem; color:var(--ink-faint)" id="ready-meta">0 rows × 0 columns</div>
            </div>
          </div>
          <div style="display:flex; gap:0.5rem">
            <button class="btn btn-primary" id="btn-start-analysis">Analyze Dataset →</button>
          </div>
        </div>

        <h4 style="font-size:0.875rem; font-weight:700; color:var(--ink); margin-bottom:0.75rem">Dataset Preview</h4>
        <div id="ready-table-wrap"></div>
      </div>
    </div>
  `;

  wireDropzone(container, dataset);

  // Check backend single source of truth for existing dataset
  try {
    const st = await api.getDatasetState(dataset);
    if (st && st.state !== "empty" && st.source_info) {
      showDatasetReady(container, {
        source_info: st.current_info || st.source_info,
      }, dataset);
    }
  } catch (e) {
    // If no session or empty, dropzone remains clean
  }
}

function wireDropzone(container, dataset) {
  const dropzone = container.querySelector("#file-dropzone");
  const fileInput = container.querySelector("#file-input");
  const alertBox = container.querySelector("#upload-alerts");

  if (!dropzone || !fileInput) return;

  dropzone.onclick = () => fileInput.click();
  dropzone.ondragover = e => { e.preventDefault(); dropzone.classList.add("drag-over"); };
  dropzone.ondragleave = () => dropzone.classList.remove("drag-over");
  dropzone.ondrop = e => {
    e.preventDefault();
    dropzone.classList.remove("drag-over");
    if (e.dataTransfer.files && e.dataTransfer.files.length) {
      processFile(e.dataTransfer.files[0], container, dataset);
    }
  };

  fileInput.onchange = () => {
    if (fileInput.files && fileInput.files.length) {
      processFile(fileInput.files[0], container, dataset);
    }
  };

  const btnLoadExcel = container.querySelector("#btn-load-excel-sheet");
  if (btnLoadExcel) {
    btnLoadExcel.onclick = async () => {
      const sheet = container.querySelector("#excel-sheet-select").value;
      if (!sheet) return;
      alertBox.innerHTML = `<div class="alert alert-info">⏳ Loading sheet '${escHtml(sheet)}'...</div>`;
      try {
        const res = await api.loadExcelSheet(sheet, dataset);
        state.datasetStates[dataset] = "uploaded";
        showDatasetReady(container, res, dataset);
        alertBox.innerHTML = `<div class="alert alert-success">✓ Loaded worksheet '${escHtml(sheet)}' successfully.</div>`;
      } catch (e) {
        alertBox.innerHTML = `<div class="alert alert-error">✗ Unable to load sheet: ${escHtml(e.message)}</div>`;
      }
    };
  }
}

async function processFile(file, container, dataset) {
  const alertBox = container.querySelector("#upload-alerts");
  const filename = file.name || "";
  const ext = filename.split(".").pop().toLowerCase();

  if (!["csv", "xlsx", "xls"].includes(ext)) {
    alertBox.innerHTML = `<div class="alert alert-error">✗ Unsupported file type '${escHtml(filename)}'. Only CSV, XLSX, and XLS files are supported.</div>`;
    return;
  }

  alertBox.innerHTML = `<div class="alert alert-info">⏳ Uploading and reading file <strong>${escHtml(filename)}</strong>...</div>`;

  try {
    const res = await api.uploadFile(file, dataset);
    if (res.session_id) {
      window._sessionId = res.session_id;
      state.sessionId = res.session_id;
    }

    if (res.file_type === "excel") {
      // Excel workbook with sheet list
      container.querySelector("#excel-filename-label").textContent = res.filename;
      container.querySelector("#excel-filesize-label").textContent = `Excel Workbook (${res.size_mb || '<1'} MB)`;
      const sheetSel = container.querySelector("#excel-sheet-select");
      sheetSel.innerHTML = (res.sheets || []).map(s => `<option value="${escHtml(s)}">${escHtml(s)}</option>`).join("");
      container.querySelector("#excel-sheet-card").classList.remove("hidden");
      container.querySelector("#dataset-ready-section").classList.add("hidden");
      alertBox.innerHTML = `<div class="alert alert-success">✓ Excel file uploaded. Select a worksheet to load.</div>`;
    } else {
      // CSV file loaded
      state.datasetStates[dataset] = "uploaded";
      container.querySelector("#excel-sheet-card").classList.add("hidden");
      showDatasetReady(container, res, dataset);
      alertBox.innerHTML = `<div class="alert alert-success">✓ File '${escHtml(filename)}' uploaded and parsed successfully.</div>`;
    }
  } catch (e) {
    alertBox.innerHTML = `<div class="alert alert-error">✗ Unable to load this file. ${escHtml(e.message)}</div>`;
  }
}

function showDatasetReady(container, res, dataset) {
  const readySection = container.querySelector("#dataset-ready-section");
  if (!readySection) return;
  readySection.classList.remove("hidden");

  const info = res.source_info || {};
  container.querySelector("#ready-filename").textContent = info.filename || "dataset.csv";
  container.querySelector("#ready-type-badge").textContent = (info.type || "CSV").toUpperCase();
  container.querySelector("#ready-meta").textContent = `${info.rows || 0} rows × ${info.cols || 0} columns ${info.sheet ? `(Sheet: ${info.sheet})` : ''}`;

  const tableWrap = container.querySelector("#ready-table-wrap");
  if (tableWrap) {
    renderDataPreview(tableWrap, dataset, { defaultRows: 10, which: "working" });
  }

  updateTopbar(dataset);

  container.querySelector("#btn-start-analysis").onclick = async () => {
    navigate("overview", { dataset });
  };
}
