/* app.js — Main application router, sidebar, topbar, and state manager */
import * as api from "./api.js";

// ===== GLOBAL STATE =====
export const state = {
  sessionId: null,
  mode: null, // "single" | "compare"
  activeDataset: "single",
  currentPage: "home",
  datasetStates: { single: "empty", ref: "empty", cur: "empty" },
  datasetMeta: { single: null, ref: null, cur: null },
};

// ===== SVG ICONS =====
const ICONS = {
  home: `<svg viewBox="0 0 24 24"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg>`,
  upload: `<svg viewBox="0 0 24 24"><path d="M9 16h6v-6h4l-7-7-7 7h4zm-4 2h14v2H5z"/></svg>`,
  overview: `<svg viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V5h14v14zM7 10h2v7H7zm4-3h2v10h-2zm4 6h2v4h-2z"/></svg>`,
  issues: `<svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>`,
  viz: `<svg viewBox="0 0 24 24"><path d="M3.5 18.49l6-6.01 4 4L22 6.92l-1.41-1.41-7.09 7.09-4-4L2 15.01z"/></svg>`,
  cleaning: `<svg viewBox="0 0 24 24"><path d="M15 16h4v2h-4zm0-8h7v2h-7zm0 4h5v2h-5zM3 18c0 1.1.9 2 2 2h6c1.1 0 2-.9 2-2V8H3v10zM14 5h-3l-1-1H6L5 5H2v2h12z"/></svg>`,
  history: `<svg viewBox="0 0 24 24"><path d="M13 3c-4.97 0-9 4.03-9 9H1l3.89 3.89.07.14L9 12H6c0-3.87 3.13-7 7-7s7 3.13 7 7-3.13 7-7 7c-1.93 0-3.68-.79-4.94-2.06l-1.42 1.42C8.27 19.99 10.51 21 13 21c4.97 0 9-4.03 9-9s-4.03-9-9-9zm-1 5v5l4.28 2.54.72-1.21-3.5-2.08V8H12z"/></svg>`,
  review: `<svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>`,
  reports: `<svg viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/></svg>`,
  compare: `<svg viewBox="0 0 24 24"><path d="M10 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h5v-2H5V5h5V3zm9 0h-5v2h5v14h-5v2h5c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2z"/></svg>`,
};

// ===== INIT =====
export async function initApp() {
  initThemeSwitcher();
  init3DTilt();
  const res = await api.newSession();
  state.sessionId = res.session_id;
  window._sessionId = res.session_id;
  renderSidebar();
  navigate("home");
}

// ===== 3D SUBTLE TILT INTERACTION =====
export function init3DTilt() {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  document.addEventListener("mousemove", (e) => {
    const card = e.target.closest(".mode-card, .tilt-card");
    if (!card) return;
    const rect = card.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;
    // Maximum rotation very small (~3deg)
    const rotateX = Math.max(-3.5, Math.min(3.5, ((y - centerY) / centerY) * -3));
    const rotateY = Math.max(-3.5, Math.min(3.5, ((x - centerX) / centerX) * 3));
    card.style.transform = `perspective(900px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg) translateY(-2px)`;
  });

  document.addEventListener("mouseout", (e) => {
    const card = e.target.closest(".mode-card, .tilt-card");
    if (!card) return;
    if (!card.contains(e.relatedTarget)) {
      card.style.transform = "";
    }
  });
}

// ===== THEME MANAGEMENT =====
export function initThemeSwitcher() {
  const currentTheme = localStorage.getItem("cleancore_theme") || "light";
  setTheme(currentTheme);

  document.querySelectorAll(".theme-btn").forEach(btn => {
    btn.onclick = () => {
      const theme = btn.dataset.theme;
      setTheme(theme);
    };
  });
}

export function setTheme(theme) {
  if (!["light", "dark", "dim"].includes(theme)) theme = "light";
  localStorage.setItem("cleancore_theme", theme);
  document.documentElement.setAttribute("data-theme", theme);

  document.querySelectorAll(".theme-btn").forEach(btn => {
    const isActive = btn.dataset.theme === theme;
    btn.classList.toggle("active", isActive);
    btn.setAttribute("aria-pressed", isActive ? "true" : "false");
  });

  window.dispatchEvent(new CustomEvent("themechange", { detail: { theme } }));
}

export function getPlotlyThemeLayout() {
  const theme = document.documentElement.getAttribute("data-theme") || "light";
  const isDark = theme === "dark";
  const isDim = theme === "dim";

  const fontColor = isDark ? "#f1f5f9" : isDim ? "#e2e8f0" : "#1e293b";
  const gridColor = isDark ? "rgba(255,255,255,0.08)" : isDim ? "rgba(255,255,255,0.09)" : "rgba(0,0,0,0.07)";
  const tickColor = isDark ? "#94a3b8" : isDim ? "#94a3b8" : "#64748b";

  return {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: {
      family: "Inter, system-ui, sans-serif",
      size: 12,
      color: fontColor,
    },
    xaxis: {
      gridcolor: gridColor,
      tickcolor: gridColor,
      tickfont: { color: tickColor },
      titlefont: { color: fontColor },
    },
    yaxis: {
      gridcolor: gridColor,
      tickcolor: gridColor,
      tickfont: { color: tickColor },
      titlefont: { color: fontColor },
    },
    legend: {
      bgcolor: "rgba(0,0,0,0)",
      font: { color: fontColor },
    },
  };
}

// ===== NAVIGATION =====
export function navigate(page, opts = {}) {
  state.currentPage = page;
  if (opts.dataset) state.activeDataset = opts.dataset;
  renderSidebar();
  updateTopbar(opts.dataset || state.activeDataset);
  renderPage(page, opts);
}

function renderPage(page, opts) {
  const main = document.getElementById("page-content");
  main.innerHTML = "";
  switch (page) {
    case "home": import("./upload.js").then(m => m.renderHome(main, opts)); break;
    case "upload-single": import("./upload.js").then(m => m.renderUpload(main, "single")); break;
    case "upload-ref": import("./upload.js").then(m => m.renderUpload(main, "ref")); break;
    case "upload-cur": import("./upload.js").then(m => m.renderUpload(main, "cur")); break;
    case "overview": import("./analysis.js").then(m => m.renderOverview(main, opts.dataset || state.activeDataset)); break;
    case "issues": import("./issues.js").then(m => m.renderIssues(main, opts.dataset || state.activeDataset)); break;
    case "viz": import("./visualization.js").then(m => m.renderViz(main, opts.dataset || state.activeDataset)); break;
    case "cleaning":
      import("./cleaning.js")
        .then(m => m.renderCleaning(main, opts.dataset || state.activeDataset, opts))
        .catch(err => {
          console.error("Failed to load Cleaning Studio:", err);
          main.innerHTML = `
            <div class="card">
              <div class="empty-state" style="padding:3rem 1.5rem">
                <div style="font-size:2.5rem; margin-bottom:0.75rem">⚠️</div>
                <div class="empty-title" style="color:#ef4444">Failed to load Cleaning Studio</div>
                <div class="empty-sub" style="margin-bottom:1.25rem; color:#64748b">${escHtml(err.message)}</div>
                <button class="btn btn-primary" id="btn-retry-page-load">🔄 Retry</button>
              </div>
            </div>
          `;
          const btn = main.querySelector("#btn-retry-page-load");
          if (btn) btn.onclick = () => renderPage("cleaning", opts);
        });
      break;
    case "history": import("./cleaning.js").then(m => m.renderHistory(main, opts.dataset || state.activeDataset)); break;
    case "review": import("./review.js").then(m => m.renderReview(main, opts.dataset || state.activeDataset)); break;
    case "comparison": import("./comparison.js").then(m => m.renderComparison(main)); break;
    case "reports": import("./reports.js").then(m => m.renderReports(main, opts)); break;
    default: main.innerHTML = '<div class="empty-state"><div class="empty-title">Page not found</div></div>';
  }

  const titles = {
    home: "Home",
    "upload-single": "Upload Dataset",
    "upload-ref": "Upload Reference Dataset",
    "upload-cur": "Upload Current Dataset",
    overview: "Dataset Overview",
    issues: "Data Quality Issue Center",
    viz: "Visualization",
    cleaning: "Cleaning Studio",
    history: "Change History",
    review: "Review & Finalize",
    comparison: "Dataset Comparison Dashboard",
    reports: "Reports & Downloads",
  };
  document.getElementById("topbar-title").textContent = titles[page] || "Automated Data Quality & Anomaly Profiler";
}

// ===== TOPBAR STATUS UPDATE =====
export async function updateTopbar(dataset = "single") {
  const infoEl = document.getElementById("topbar-info");
  if (!infoEl) return;
  if (!state.sessionId || state.currentPage === "home") {
    infoEl.innerHTML = "";
    return;
  }
  try {
    const st = await api.getDatasetState(dataset);
    if (!st || st.state === "empty") {
      state.datasetStates[dataset] = "empty";
      state.datasetMeta[dataset] = null;
      infoEl.innerHTML = `<span class="badge badge-neutral">No Dataset Loaded</span>`;
      return;
    }
    state.datasetStates[dataset] = st.state;
    // We store current_info in datasetMeta so UI reads the live sizes
    state.datasetMeta[dataset] = st.current_info || st.source_info;
    const info = st.current_info || st.source_info || {};
    const stateBadge = st.state === "finalized"
      ? `<span class="badge badge-success">Finalized</span>`
      : `<span class="badge badge-warning">Working Copy</span>`;

    const dsLabel = state.mode === "compare" ? `<strong>[${dataset.toUpperCase()}]</strong> ` : "";

    infoEl.innerHTML = `
      <div class="topbar-chip">
        ${stateBadge}
        <span>${dsLabel}<strong>${info.rows || 0}</strong> rows × <strong>${info.cols || 0}</strong> cols</span>
        <span style="color:#cbd5e1">·</span>
        <span style="max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap">${escHtml(info.filename || info.sheet || "Dataset")}</span>
      </div>
    `;
  } catch {
    infoEl.innerHTML = "";
  }
}

export async function refreshTopbar(dataset) {
  return updateTopbar(dataset || state.activeDataset || "single");
}

export function renderNoDatasetState(container, pageTitle = "this section", dataset = "single") {
  const uploadPage = dataset === "ref" ? "upload-ref" : dataset === "cur" ? "upload-cur" : "upload-single";
  container.innerHTML = `
    <div class="card" style="max-width:600px; margin:2.5rem auto; text-align:center; padding:2.5rem 1.5rem">
      <div class="empty-state">
        <div style="font-size:3rem; margin-bottom:0.75rem">📥</div>
        <div class="empty-title" style="font-size:1.125rem; font-weight:800; color:#0f172a; margin-bottom:0.5rem">No Dataset Loaded</div>
        <div class="empty-sub" style="color:#64748b; font-size:0.875rem; margin-bottom:1.5rem">
          Please upload a CSV or Excel dataset for <strong>${escHtml(dataset.toUpperCase())}</strong> before accessing ${escHtml(pageTitle)}.
        </div>
        <button class="btn btn-primary btn-lg" id="btn-goto-upload" style="margin:0 auto">Upload Dataset Now →</button>
      </div>
    </div>
  `;
  const btn = container.querySelector("#btn-goto-upload");
  if (btn) btn.onclick = () => navigate(uploadPage);
}

// ===== SIDEBAR RENDER =====
export function renderSidebar() {
  const sb = document.getElementById("sidebar-nav");
  const mode = state.mode;
  let navHTML = "";

  if (!mode) {
    navHTML += navItem("home", ICONS.home, "Home");
    sb.innerHTML = navHTML;
    wireNav();
    return;
  }

  navHTML += navItem("home", ICONS.home, "Home");

  if (mode === "single") {
    navHTML += navItem("upload-single", ICONS.upload, "Upload Dataset");
    navHTML += navItem("overview", ICONS.overview, "Dataset Overview");
    navHTML += navItem("issues", ICONS.issues, "Issue Center");
    navHTML += navItem("viz", ICONS.viz, "Visualization");
    navHTML += navItem("cleaning", ICONS.cleaning, "Cleaning");
    navHTML += navItem("history", ICONS.history, "Change History");
    navHTML += navItem("review", ICONS.review, "Review & Finalize");
    navHTML += navItem("reports", ICONS.reports, "Reports & Downloads");
  } else {
    navHTML += `<div class="sidebar-section-label">Reference Dataset</div>`;
    navHTML += navItem("upload-ref", ICONS.upload, "Upload Reference", { dataset: "ref" });
    navHTML += sideNavBtn("overview-ref", ICONS.overview, "Overview", "overview", "ref");
    navHTML += sideNavBtn("issues-ref", ICONS.issues, "Issue Center", "issues", "ref");
    navHTML += sideNavBtn("viz-ref", ICONS.viz, "Visualization", "viz", "ref");
    navHTML += sideNavBtn("cleaning-ref", ICONS.cleaning, "Cleaning", "cleaning", "ref");
    navHTML += sideNavBtn("review-ref", ICONS.review, "Review & Finalize", "review", "ref");

    navHTML += `<div class="sidebar-section-label">Current Dataset</div>`;
    navHTML += navItem("upload-cur", ICONS.upload, "Upload Current", { dataset: "cur" });
    navHTML += sideNavBtn("overview-cur", ICONS.overview, "Overview", "overview", "cur");
    navHTML += sideNavBtn("issues-cur", ICONS.issues, "Issue Center", "issues", "cur");
    navHTML += sideNavBtn("viz-cur", ICONS.viz, "Visualization", "viz", "cur");
    navHTML += sideNavBtn("cleaning-cur", ICONS.cleaning, "Cleaning", "cleaning", "cur");
    navHTML += sideNavBtn("review-cur", ICONS.review, "Review & Finalize", "review", "cur");

    navHTML += `<div class="sidebar-section-label">Comparison</div>`;
    navHTML += navItem("comparison", ICONS.compare, "Comparison Dashboard");
    navHTML += navItem("reports", ICONS.reports, "Reports & Downloads");
  }

  sb.innerHTML = navHTML;
  wireNav();
  updateModeBadge();
}

function navItem(page, iconSvg, label, opts = {}) {
  const ds = opts.dataset ? `data-dataset="${opts.dataset}"` : "";
  const isActive = state.currentPage === page && (!opts.dataset || state.activeDataset === opts.dataset);
  return `<div class="nav-item ${isActive ? 'active' : ''}" data-page="${page}" ${ds}><span class="nav-icon">${iconSvg}</span>${label}</div>`;
}

function sideNavBtn(id, iconSvg, label, page, dataset) {
  const isActive = state.currentPage === page && state.activeDataset === dataset;
  return `<div class="nav-item ${isActive ? 'active' : ''}" data-page="${page}" data-dataset="${dataset}"><span class="nav-icon">${iconSvg}</span>${label}</div>`;
}

function wireNav() {
  document.querySelectorAll(".nav-item[data-page]").forEach(el => {
    el.onclick = () => navigate(el.dataset.page, { dataset: el.dataset.dataset });
  });
}

function updateModeBadge() {
  const badge = document.getElementById("mode-badge");
  if (!badge) return;
  if (!state.mode) { badge.innerHTML = ""; return; }
  badge.innerHTML = `<strong>${state.mode === "single" ? "Single Dataset" : "Two Dataset Comparison"}</strong>`;
}

// ===== UTILS =====
export function showAlert(msg, type = "info", container = null) {
  const html = `<div class="alert alert-${type}"><span>${escHtml(msg)}</span></div>`;
  if (container) {
    const el = document.createElement("div");
    el.innerHTML = html;
    container.prepend(el.firstChild);
    return;
  }
  const toast = document.getElementById("toast-container");
  if (toast) {
    const el = document.createElement("div");
    el.innerHTML = html;
    const node = el.firstChild;
    toast.appendChild(node);
    setTimeout(() => node.remove(), 4000);
  }
}

export function showModal({
  title,
  body,
  onConfirm,
  confirmText = "Confirm",
  confirmClass = "btn-primary",
  showConfirm = true,
  showCancel = true,
  cancelText = "Cancel",
  autoClose = true,
  onCancel = null,
}) {
  const backdrop = document.getElementById("modal-backdrop");
  document.getElementById("modal-title").textContent = title;
  document.getElementById("modal-body").innerHTML = body;
  const confirmBtn = document.getElementById("modal-confirm");
  const cancelBtn = document.getElementById("modal-cancel");
  confirmBtn.textContent = confirmText;
  confirmBtn.className = `btn ${confirmClass}`;
  confirmBtn.style.display = showConfirm ? "" : "none";
  cancelBtn.textContent = cancelText;
  cancelBtn.className = "btn btn-secondary";
  cancelBtn.style.display = showCancel ? "" : "none";
  confirmBtn.onclick = async () => {
    if (autoClose) backdrop.classList.add("hidden");
    if (onConfirm) await onConfirm();
  };
  const handleClose = () => {
    backdrop.classList.add("hidden");
    if (onCancel) onCancel();
  };
  cancelBtn.onclick = handleClose;
  document.getElementById("modal-close").onclick = handleClose;
  backdrop.classList.remove("hidden");
}

export function closeModal() {
  const backdrop = document.getElementById("modal-backdrop");
  if (backdrop) backdrop.classList.add("hidden");
}

export function severityBadge(sev) {
  const map = { critical: "badge-critical", high: "badge-high", medium: "badge-medium", low: "badge-low", info: "badge-info" };
  return `<span class="badge ${map[sev] || "badge-neutral"}">${sev}</span>`;
}

export function fmtNum(v, decimals = 2) {
  if (v === null || v === undefined || (typeof v === "number" && isNaN(v))) return "—";
  return typeof v === "number" ? v.toFixed(decimals) : v;
}

export function escHtml(str) {
  if (str === null || str === undefined) return "—";
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
