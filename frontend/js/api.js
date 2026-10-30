/* api.js — Backend API client (CSV & Excel only) */
const API_BASE = "";

export async function apiFetch(path, options = {}) {
  const sid = window._sessionId;
  const defaultHeaders = { "Content-Type": "application/json" };
  if (sid) defaultHeaders["X-Session-Id"] = sid;

  const timeoutMs = options.timeout ?? 20000;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  const opts = {
    headers: defaultHeaders,
    signal: controller.signal,
    cache: "no-store",
    ...options,
  };
  delete opts.timeout;

  if (options.body && typeof options.body !== "string" && !(options.body instanceof FormData)) {
    opts.body = JSON.stringify(options.body);
  }
  if (options.body instanceof FormData) {
    delete opts.headers["Content-Type"];
  }

  try {
    const res = await fetch(API_BASE + path, opts);
    clearTimeout(timer);
    if (!res.ok) {
      let errMsg = `HTTP ${res.status}`;
      try {
        const j = await res.json();
        errMsg = j.error || errMsg;
      } catch {}
      throw new Error(errMsg);
    }
    const ct = res.headers.get("content-type") || "";
    if (ct.includes("application/json")) return res.json();
    if (ct.includes("text/html") || ct.includes("text/csv")) return res.text();
    return res.blob();
  } catch (err) {
    clearTimeout(timer);
    if (err.name === "AbortError") {
      throw new Error(`Request timed out after ${Math.round(timeoutMs / 1000)}s. Please check your connection or try again.`);
    }
    throw err;
  }
}

export async function newSession() {
  return apiFetch("/api/session/new", { method: "POST" });
}

export async function uploadFile(file, dataset = "single") {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("dataset", dataset);
  return apiFetch("/api/upload/file", { method: "POST", body: fd });
}

export async function loadExcelSheet(sheet, dataset = "single") {
  return apiFetch("/api/upload/excel/load", {
    method: "POST",
    body: { session_id: window._sessionId, sheet, dataset },
  });
}

export async function analyze(dataset = "single") {
  return apiFetch("/api/analyze", {
    method: "POST",
    body: { session_id: window._sessionId, dataset },
  });
}

export async function getAnalysis(dataset = "single") {
  return apiFetch(`/api/analysis/result?session_id=${window._sessionId}&dataset=${dataset}&_t=${Date.now()}`);
}

export async function getDatasetPreview(dataset = "single", { page = 0, pageSize = 50, search = "", sortCol = "", sortAsc = true, which = "working" } = {}) {
  const params = new URLSearchParams({
    session_id: window._sessionId, dataset, page, page_size: pageSize,
    search, sort_col: sortCol, sort_asc: sortAsc, which, _t: Date.now(),
  });
  return apiFetch(`/api/dataset/preview?${params}`);
}

export async function getAffectedRows(dataset, indices) {
  return apiFetch("/api/dataset/affected-rows", {
    method: "POST",
    body: { session_id: window._sessionId, dataset, indices },
  });
}

export async function getDatasetState(dataset = "single") {
  return apiFetch(`/api/dataset/state?session_id=${window._sessionId}&dataset=${dataset}&_t=${Date.now()}`);
}

// Cleaning
export async function editCell(dataset, rowIndex, column, newValue) {
  return apiFetch("/api/clean/edit-cell", {
    method: "POST",
    body: { session_id: window._sessionId, dataset, row_index: rowIndex, column, new_value: newValue },
  });
}

export async function deleteRows(dataset, rowIndices) {
  return apiFetch("/api/clean/delete-rows", {
    method: "POST",
    body: { session_id: window._sessionId, dataset, row_indices: rowIndices },
  });
}

export async function deleteColumns(dataset, columns) {
  return apiFetch("/api/clean/delete-columns", {
    method: "POST",
    body: { session_id: window._sessionId, dataset, columns },
  });
}

export async function renameColumn(dataset, oldName, newName) {
  return apiFetch("/api/clean/rename-column", {
    method: "POST",
    body: { session_id: window._sessionId, dataset, old_name: oldName, new_name: newName },
  });
}

export async function previewFillMissing(dataset, column, method, manualValue = null) {
  return apiFetch("/api/clean/preview-fill-missing", {
    method: "POST",
    body: { session_id: window._sessionId, dataset, column, method, manual_value: manualValue },
  });
}

export async function fillMissing(dataset, column, method, manualValue = null) {
  return apiFetch("/api/clean/fill-missing", {
    method: "POST",
    body: { session_id: window._sessionId, dataset, column, method, manual_value: manualValue },
  });
}

export async function removeDuplicates(dataset, keep = "first") {
  return apiFetch("/api/clean/remove-duplicates", {
    method: "POST",
    body: { session_id: window._sessionId, dataset, keep },
  });
}

export async function repairType(dataset, column, targetType) {
  return apiFetch("/api/clean/repair-type", {
    method: "POST",
    body: { session_id: window._sessionId, dataset, column, target_type: targetType },
  });
}

export async function previewTypeConversion(dataset, column, targetType) {
  return apiFetch("/api/clean/preview-type-conversion", {
    method: "POST",
    body: { session_id: window._sessionId, dataset, column, target_type: targetType },
  });
}

export async function getTypeIssueRows(dataset, column, page = 0, pageSize = 25) {
  return apiFetch("/api/clean/type-issue-rows", {
    method: "POST",
    body: { session_id: window._sessionId, dataset, column, page, page_size: pageSize },
  });
}

export async function resolveTypeRows(dataset, column, action, options = {}) {
  return apiFetch("/api/clean/resolve-type-rows", {
    method: "POST",
    body: {
      session_id: window._sessionId,
      dataset,
      column,
      action,
      row_indices: options.row_indices || [],
      target_type: options.target_type || "int64",
      manual_value: options.manual_value || null,
    },
  });
}

export async function resetWorking(dataset) {
  return apiFetch("/api/clean/reset", {
    method: "POST",
    body: { session_id: window._sessionId, dataset },
  });
}

export async function finalizeDataset(dataset) {
  return apiFetch("/api/clean/finalize", {
    method: "POST",
    body: { session_id: window._sessionId, dataset },
  });
}

export async function getHistory(dataset = "single") {
  return apiFetch(`/api/clean/history?session_id=${window._sessionId}&dataset=${dataset}`);
}

export async function resolveOutlier(dataset, rowIndex, column, resolution, imputeMethod = null, manualValue = null) {
  const rowIndices = Array.isArray(rowIndex) ? rowIndex : [rowIndex];
  return apiFetch("/api/clean/resolve-outlier", {
    method: "POST",
    body: {
      session_id: window._sessionId, dataset,
      row_index: rowIndices.length === 1 ? rowIndices[0] : rowIndices,
      row_indices: rowIndices,
      column, resolution,
      impute_method: imputeMethod, manual_value: manualValue,
    },
  });
}

// Visualization
export async function getAvailableCharts(dataset = "single") {
  return apiFetch(`/api/viz/available?session_id=${window._sessionId}&dataset=${dataset}`);
}

export async function getDatasetOverview(dataset = "single", which = "working") {
  return apiFetch(`/api/viz/overview?session_id=${window._sessionId}&dataset=${dataset}&which=${encodeURIComponent(which)}`);
}

export async function generateChart(dataset, chartType, config, which = "working") {
  return apiFetch("/api/viz/generate", {
    method: "POST",
    body: { session_id: window._sessionId, dataset, chart_type: chartType, config, which },
  });
}

// Comparison
export async function runComparison() {
  return apiFetch("/api/compare/run", {
    method: "POST",
    body: { session_id: window._sessionId },
  });
}

export async function runPreviewComparison() {
  return apiFetch("/api/compare/preview", {
    method: "POST",
    body: { session_id: window._sessionId },
  });
}

export async function getComparison() {
  return apiFetch(`/api/compare/result?session_id=${window._sessionId}`);
}

export async function deleteMissingRows(dataset) {
  return apiFetch("/api/clean/delete-missing-rows", {
    method: "POST",
    body: { session_id: window._sessionId, dataset },
  });
}

export async function deleteColumnMissingRows(dataset, column) {
  return apiFetch("/api/clean/delete-column-missing-rows", {
    method: "POST",
    body: { session_id: window._sessionId, dataset, column },
  });
}

export async function resolveSuspicious(dataset, rowIndex, column, resolution, imputeMethod = null, manualValue = null) {
  const rowIndices = Array.isArray(rowIndex) ? rowIndex : [rowIndex];
  return apiFetch("/api/clean/resolve-suspicious", {
    method: "POST",
    body: {
      session_id: window._sessionId, dataset,
      row_index: rowIndices.length === 1 ? rowIndices[0] : rowIndices,
      row_indices: rowIndices,
      column, resolution,
      impute_method: imputeMethod, manual_value: manualValue,
    },
  });
}

// Reports & Downloads
export async function downloadHTMLReport(mode = "single", reportType = "analysis") {
  const res = await fetch(`${API_BASE}/api/report/html`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Session-Id": window._sessionId },
    body: JSON.stringify({ session_id: window._sessionId, mode, report_type: reportType }),
  });
  if (!res.ok) {
    let errMsg = `HTTP ${res.status}`;
    try {
      const j = await res.json();
      errMsg = j.error || errMsg;
    } catch {}
    throw new Error(errMsg);
  }
  const text = await res.text();
  const blob = new Blob([text], { type: "text/html" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  if (reportType === "comparison") {
    a.download = "comparison_report.html";
  } else if (reportType === "reference") {
    a.download = "reference_dataset_report.html";
  } else if (reportType === "current") {
    a.download = "current_dataset_report.html";
  } else {
    a.download = "data_quality_report.html";
  }
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 100);
}

export async function downloadPDFReport(mode = "single", reportType = "analysis") {
  const res = await fetch(`${API_BASE}/api/report/pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Session-Id": window._sessionId },
    body: JSON.stringify({ session_id: window._sessionId, mode, report_type: reportType }),
  });
  if (!res.ok) {
    let errMsg = `HTTP ${res.status}`;
    try {
      const j = await res.json();
      errMsg = j.error || errMsg;
    } catch {}
    throw new Error(errMsg);
  }
  const ct = res.headers.get("content-type") || "";
  if (!ct.includes("application/pdf")) {
    throw new Error("Invalid response format: expected application/pdf");
  }
  const blob = await res.blob();
  if (blob.size === 0) {
    throw new Error("Received empty PDF file from server.");
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  if (reportType === "comparison") {
    a.download = "comparison_report.pdf";
  } else if (reportType === "reference") {
    a.download = "reference_dataset_report.pdf";
  } else if (reportType === "current") {
    a.download = "current_dataset_report.pdf";
  } else {
    a.download = "data_quality_report.pdf";
  }
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 100);
}

export async function downloadDataset(dataset = "single") {
  const url = `${API_BASE}/api/download/dataset?session_id=${window._sessionId}&dataset=${dataset}`;
  const a = document.createElement("a");
  a.href = url;
  a.download = `cleaned_${dataset}.csv`;
  a.click();
}

export async function downloadMissingLog(dataset = "single") {
  const url = `${API_BASE}/api/download/missing-log?session_id=${window._sessionId}&dataset=${dataset}`;
  const a = document.createElement("a");
  a.href = url;
  a.download = `missing_values_log_${dataset}.xlsx`;
  a.click();
}
