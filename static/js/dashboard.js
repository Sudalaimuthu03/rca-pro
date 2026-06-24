(function () {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str ?? "";
    return div.innerHTML;
  }

  function formatDate(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" }) + " · " +
           d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  }

  function severityBadge(sev) {
    const s = (sev || "MEDIUM").toLowerCase();
    return `<span class="badge badge-${s}">${s}</span>`;
  }

  function statusBadge(status) {
    const s = (status || "OPEN").toLowerCase();
    return `<span class="badge badge-${s}">${s.replace("_", " ")}</span>`;
  }

  async function api(path, opts = {}) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      ...opts,
    });
    if (res.status === 401) {
      window.location.href = "/login";
      throw new Error("Unauthorized");
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.error || "Request failed");
    }
    return data;
  }

  function toast(message, type = "success") {
    const stack = $("#toastStack");
    const el = document.createElement("div");
    el.className = `toast ${type}`;
    el.textContent = message;
    stack.appendChild(el);
    setTimeout(() => {
      el.style.transition = "opacity 0.3s ease";
      el.style.opacity = "0";
      setTimeout(() => el.remove(), 300);
    }, 3200);
  }

  // ── view routing ────────────────────────────────────────────────────────
  const views = $$(".view");
  const navItems = $$(".nav-item");

  function showView(name) {
    views.forEach(v => v.classList.toggle("active", v.dataset.view === name));
    navItems.forEach(n => n.classList.toggle("active", n.dataset.view === name));
    if (name === "dashboard") loadDashboard();
    if (name === "incidents") loadIncidents();
    window.scrollTo({ top: 0, behavior: "smooth" });
    closeSidebar();
  }

  navItems.forEach(item => {
    item.addEventListener("click", (e) => {
      e.preventDefault();
      showView(item.dataset.view);
    });
  });

  $$("[data-view-link]").forEach(link => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      showView(link.dataset.viewLink);
    });
  });

  // ── mobile sidebar ──────────────────────────────────────────────────────
  const sidebar = $("#sidebar");
  const backdrop = $("#sidebarBackdrop");

  function openSidebar() { sidebar.classList.add("show"); backdrop.classList.add("show"); }
  function closeSidebar() { sidebar.classList.remove("show"); backdrop.classList.remove("show"); }

  $("#menuToggle")?.addEventListener("click", openSidebar);
  backdrop?.addEventListener("click", closeSidebar);

  // ── user / logout ───────────────────────────────────────────────────────
  async function loadUser() {
    try {
      const data = await api("/api/auth/me");
      $("#userName").textContent = data.user.name;
      $("#userAvatar").textContent = data.user.name.charAt(0).toUpperCase();
    } catch (e) { /* redirected to login already if 401 */ }
  }

  $("#logoutBtn")?.addEventListener("click", async () => {
    try {
      await api("/api/auth/logout", { method: "POST" });
      window.location.href = "/login";
    } catch (e) {
      toast("Could not log out — try again", "error");
    }
  });

  // ── dashboard ───────────────────────────────────────────────────────────
  let trendChart, categoryChart;

  const STAT_DEFS = [
    { key: "open",        label: "Open",        color: "var(--status-open)" },
    { key: "in_progress", label: "In progress", color: "var(--status-progress)" },
    { key: "resolved",    label: "Resolved",    color: "var(--status-resolved)" },
    { key: "critical",    label: "Critical",    color: "var(--critical)" },
    { key: "total",       label: "Total",       color: "var(--brand-bright)" },
  ];

  async function loadDashboard() {
    const grid = $("#statGrid");
    grid.innerHTML = STAT_DEFS.map(() => `<div class="stat-card"><div class="skeleton" style="height:14px;width:60%;margin-bottom:10px;"></div><div class="skeleton" style="height:26px;width:40%;"></div></div>`).join("");

    let data;
    try {
      data = await api("/api/analytics/dashboard");
    } catch (e) {
      toast("Could not load dashboard", "error");
      return;
    }

    grid.innerHTML = STAT_DEFS.map(def => `
      <div class="stat-card">
        <div class="label"><span class="stat-dot" style="background:${def.color}"></span>${def.label}</div>
        <div class="value">${data.summary[def.key] ?? 0}</div>
      </div>
    `).join("");

    renderTrendChart(data.daily_trend || []);
    renderCategoryChart(data.root_cause_distribution || []);
    renderRecentList(data.recent_incidents || []);
  }

  function renderTrendChart(trend) {
    const ctx = $("#trendChart");
    const labels = trend.map(t => new Date(t.day).toLocaleDateString(undefined, { month: "short", day: "numeric" }));
    const values = trend.map(t => t.incidents);
    if (trendChart) trendChart.destroy();
    trendChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: labels.length ? labels : ["No data"],
        datasets: [{
            data: values.length ? values : [0],
            borderColor: "#9C8FFF",
            backgroundColor: "rgba(124,111,240,0.15)",
            fill: true,
            tension: 0.4,
            borderWidth: 3,
    
            pointRadius: values.length === 1 ? 6 : 3,
            pointHoverRadius: 8,
            pointBackgroundColor: "#9C8FFF",
            pointBorderColor: "#FFFFFF",
            pointBorderWidth: 2,
        }],
      },
      options: chartOptions(),
    });
  }

  function renderCategoryChart(dist) {
    const ctx = $("#categoryChart");
    const labels = dist.map(d => (d.category || "OTHER").replace(/_/g, " "));
    const values = dist.map(d => d.count);
    const colors = ["#7C6FF0", "#4DABF7", "#FF9F43", "#FF4D5E", "#6FCF97", "#9C8FFF", "#5A6678"];
    if (categoryChart) categoryChart.destroy();
    categoryChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels.length ? labels : ["No data"],
        datasets: [{
          data: values.length ? values : [0],
          backgroundColor: labels.map((_, i) => colors[i % colors.length]),
          borderRadius: 6,
        }],
      },
      options: { ...chartOptions(), indexAxis: "y" },
    });
  }

  function chartOptions() {
    return {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#93A0B4", font: { size: 11 } }, grid: { color: "#1A2230" } },
        y: { ticks: { color: "#93A0B4", font: { size: 11 } }, grid: { color: "#1A2230" }, beginAtZero: true },
      },
    };
  }

  function renderRecentList(items) {
    const container = $("#recentList");
    if (!items.length) {
      container.innerHTML = `<div class="empty-state"><span class="empty-icon">◈</span><p>No incidents yet — create your first one.</p></div>`;
      return;
    }
    container.innerHTML = items.map(incidentRow).join("");
    bindIncidentRows(container);
  }

  // ── new incident form (create only — no auto-analyze) ──────────────────
  const newForm = $("#newIncidentForm");
  const titleInput = $("#incTitle");
  const logInput = $("#incLog");

  function validateNewIncident() {
    let valid = true;
    if (!titleInput.value.trim()) {
      titleInput.classList.add("invalid");
      $("#incTitleError").textContent = "Title is required";
      $("#incTitleError").classList.add("show");
      valid = false;
    } else {
      titleInput.classList.remove("invalid");
      $("#incTitleError").classList.remove("show");
    }
    if (!logInput.value.trim() || logInput.value.trim().length < 10) {
      logInput.classList.add("invalid");
      $("#incLogError").textContent = "Paste the error log (at least 10 characters)";
      $("#incLogError").classList.add("show");
      valid = false;
    } else {
      logInput.classList.remove("invalid");
      $("#incLogError").classList.remove("show");
    }
    return valid;
  }

  [titleInput, logInput].forEach(el => el?.addEventListener("input", () => {
    el.classList.remove("invalid");
    (el === titleInput ? $("#incTitleError") : $("#incLogError")).classList.remove("show");
  }));

  // Option B: submit only CREATES the incident (status = OPEN).
  // Analysis is triggered separately from the drawer via "Analyze with AI".
  newForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!validateNewIncident()) return;

    const saveBtn = $("#saveBtn");
    const saveLabel = $("#saveLabel");
    saveBtn.disabled = true;
    saveLabel.innerHTML = `<span class="spinner"></span> Saving…`;

    try {
      const created = await api("/api/incidents", {
        method: "POST",
        body: JSON.stringify({
          title: titleInput.value.trim(),
          error_log: logInput.value.trim(),
          severity: $("#incSeverity").value,
        }),
      });

      resetNewIncidentForm();
      toast(`Incident saved — open it in Incidents to analyze.`, "success");

      // Refresh dashboard so open_count increments immediately
      loadDashboard();

    } catch (err) {
      saveBtn.disabled = false;
      saveLabel.textContent = "Save Incident";
      toast(err.message || "Could not save — please try again", "error");
    }
  });

  function resetNewIncidentForm() {
    newForm.reset();
    $("#newIncidentPanel").hidden = false;
    $("#analysisResult").hidden = true;
    $("#analysisResult").innerHTML = "";
    $("#saveBtn").disabled = false;
    $("#saveLabel").textContent = "Save Incident";
  }

  // ── analyze flow (triggered from drawer) ────────────────────────────────
  async function runAnalysis(incidentId, drawerBodyEl) {
    // Show analyzing state inside the drawer
    drawerBodyEl.innerHTML = `
      <div class="panel analyzing-panel" style="margin-top:16px;">
        <svg class="trace-loader" viewBox="0 0 600 120" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <linearGradient id="loaderGradient2" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%"   stop-color="#7C6FF0" stop-opacity="0"/>
              <stop offset="50%"  stop-color="#9C8FFF" stop-opacity="1"/>
              <stop offset="100%" stop-color="#7C6FF0" stop-opacity="0"/>
            </linearGradient>
          </defs>
          <path d="M -50 60 L 90 60 L 120 20 L 160 100 L 200 60 L 260 60 L 290 10 L 330 60 L 650 60" />
        </svg>
        <p class="analyzing-text">Tracing root cause<span class="dots"><span>.</span><span>.</span><span>.</span></span></p>
      </div>
    `;

    try {
      const result = await api(`/api/incidents/${incidentId}/analyze`, { method: "POST" });
      // Re-open the drawer so the full analysis renders fresh
      closeDrawer();
      await openDrawer(incidentId);
      toast("Analysis complete", "success");
      loadDashboard();
    } catch (err) {
      toast(err.message || "Analysis failed — please try again", "error");
      // Re-open drawer to restore original state
      closeDrawer();
      await openDrawer(incidentId);
    }
  }

  // ── render analysis result (used inside drawer) ──────────────────────────
  function renderAnalysisHtml(a) {
    const causes = (a.root_causes || []).map(rc => `
      <div class="rc-card">
        <div class="rc-head">
          <h4>${escapeHtml(rc.cause)}</h4>
          ${severityBadge(rc.severity)}
        </div>
        <div class="rc-service">${escapeHtml(rc.service || "")}</div>
        <div class="confidence-bar">
          <div class="confidence-track"><div class="confidence-fill" style="width:${rc.confidence}%"></div></div>
          <div class="confidence-label">${rc.confidence}%</div>
        </div>
        <div class="rc-fix">${escapeHtml(rc.fix)}</div>
      </div>
    `).join("");

    const whys = a.five_whys || {};
    const whysHtml = Object.keys(whys).sort().map((k, i) => `
      <div class="why-row">
        <span class="why-num">${i + 1}</span>
        <span class="why-text">${escapeHtml(whys[k])}</span>
      </div>
    `).join("");

    const servicesHtml = (a.affected_services || [])
      .map(s => `<span class="tag">${escapeHtml(s)}</span>`).join("");

    const historyHtml = a.recurrence_count > 0 ? `
      <div class="history-card">
        <span>↻</span>
        <span><strong>${a.recurrence_count} similar incident${a.recurrence_count > 1 ? "s" : ""}</strong> found in this category.
        ${a.historical_solution ? escapeHtml(a.historical_solution) : ""}</span>
      </div>` : "";

    return `
      <div class="result-summary"><p>${escapeHtml(a.summary)}</p></div>
      ${historyHtml}
      ${causes}
      <div class="whys-card">
        <h3>Five whys</h3>
        ${whysHtml}
      </div>
      <div class="panel" style="margin-top:12px;">
        <div class="panel-head"><h3>Affected services</h3></div>
        <div class="tags-row">${servicesHtml || '<span class="tag">None identified</span>'}</div>
      </div>
    `;
  }

  // ── incidents list ──────────────────────────────────────────────────────
  function incidentRow(inc) {
    return `
      <div class="incident-row" data-id="${inc.id}">
        <span class="title">${escapeHtml(inc.title)}</span>
        ${severityBadge(inc.severity)}
        ${statusBadge(inc.status)}
        <span class="meta">${formatDate(inc.created_at)}</span>
      </div>
    `;
  }

  function bindIncidentRows(container) {
    $$(".incident-row", container).forEach(row => {
      row.addEventListener("click", () => openDrawer(row.dataset.id));
    });
  }

  async function loadIncidents() {
    const container = $("#incidentsList");
    const empty = $("#incidentsEmpty");
    container.innerHTML = Array.from({ length: 4 }).map(() =>
      `<div class="incident-row"><div class="skeleton" style="height:16px;width:100%;"></div></div>`
    ).join("");

    const status = $("#filterStatus").value;
    const severity = $("#filterSeverity").value;
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (severity) params.set("severity", severity);

    let data;
    try {
      data = await api(`/api/incidents?${params.toString()}`);
    } catch (e) {
      toast("Could not load incidents", "error");
      return;
    }

    if (!data.incidents.length) {
      container.innerHTML = "";
      empty.hidden = false;
      return;
    }
    empty.hidden = true;
    container.innerHTML = data.incidents.map(incidentRow).join("");
    bindIncidentRows(container);
  }

  $("#filterStatus")?.addEventListener("change", loadIncidents);
  $("#filterSeverity")?.addEventListener("change", loadIncidents);

  // ── drawer ──────────────────────────────────────────────────────────────
  const drawer = $("#drawer");
  const drawerBackdrop = $("#drawerBackdrop");

  function closeDrawer() {
    drawer.classList.remove("show");
    drawerBackdrop.classList.remove("show");
  }
  $("#drawerClose")?.addEventListener("click", closeDrawer);
  drawerBackdrop?.addEventListener("click", closeDrawer);

  async function openDrawer(id) {
    drawer.classList.add("show");
    drawerBackdrop.classList.add("show");
    $("#drawerBody").innerHTML = `<div class="skeleton" style="height:80px;"></div>`;

    let data;
    try {
      data = await api(`/api/incidents/${id}`);
    } catch (e) {
      $("#drawerBody").innerHTML = `<p>Could not load incident.</p>`;
      return;
    }

    const inc = data.incident;
    const a = inc.analysis;
    $("#drawerTitle").textContent = inc.title;

    // Analysis section — show results if analyzed, or prompt to analyze if OPEN
    let analysisHtml;
    if (a) {
      analysisHtml = renderAnalysisHtml(a);
    } else {
      // Option B: OPEN incidents show an Analyze button instead of "No analysis"
      analysisHtml = `
        <div class="no-analysis-prompt">
          <p style="color:var(--text-faint);font-size:13.5px;margin-bottom:12px;">
            This incident has not been analyzed yet.
          </p>
          <button class="btn-primary" id="drawerAnalyze">
            <span id="drawerAnalyzeLabel">Analyze with AI</span>
          </button>
        </div>
      `;
    }

    // Action buttons — resolve only if not already resolved/closed
    const canResolve = inc.status !== "RESOLVED" && inc.status !== "CLOSED";

    $("#drawerBody").innerHTML = `
      <div style="display:flex;gap:8px;flex-wrap:wrap;">
        ${severityBadge(inc.severity)} ${statusBadge(inc.status)}
      </div>
      <div class="rc-fix" style="max-height:160px;overflow:auto;">${escapeHtml(inc.error_log)}</div>
      ${analysisHtml}
      <div class="result-actions">
        ${canResolve ? `<button class="btn-secondary" id="drawerResolve">Mark as resolved</button>` : ""}
        <button class="btn-secondary" id="drawerDelete" style="color:var(--critical);">Delete incident</button>
      </div>
    `;

    // Analyze button (only present for unanalyzed incidents)
    $("#drawerAnalyze")?.addEventListener("click", async () => {
      const btn = $("#drawerAnalyze");
      const label = $("#drawerAnalyzeLabel");
      btn.disabled = true;
      label.innerHTML = `<span class="spinner"></span> Starting…`;
      await runAnalysis(id, $("#drawerBody"));
      loadIncidents();
    });

    // Resolve button
    $("#drawerResolve")?.addEventListener("click", async () => {
      try {
        await api(`/api/incidents/${id}/resolve`, { method: "PUT" });
        toast("Marked as resolved", "success");
        closeDrawer();
        loadIncidents();
        loadDashboard();
      } catch (e) { toast(e.message, "error"); }
    });

    // Delete button
    $("#drawerDelete")?.addEventListener("click", async () => {
      if (!confirm("Delete this incident? This cannot be undone.")) return;
      try {
        await api(`/api/incidents/${id}`, { method: "DELETE" });
        toast("Incident deleted", "success");
        closeDrawer();
        loadIncidents();
        loadDashboard();
      } catch (e) { toast(e.message, "error"); }
    });
  }

  // ── init ────────────────────────────────────────────────────────────────
  loadUser();
  loadDashboard();
})();
