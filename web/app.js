const TOKEN_KEY = "vanguard-demo-token";
const ROUTES = {
  overview: "Overview",
  incidents: "Incident queue",
  vendors: "Vendors",
  audit: "Audit trail",
  api: "API reference",
};
const state = {
  token: "",
  actor: "vanguard-analyst",
  incidents: [],
  vendors: [],
  selectedId: null,
  status: "all",
  search: "",
  auditEvents: [],
  auditFilter: "all",
  auditLoaded: false,
  route: "overview",
};
const $ = (id) => document.getElementById(id);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));
const esc = (value) =>
  String(value).replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
const SEVERITIES = new Set(["critical", "high", "moderate", "low"]);
const STATUSES = new Set(["new", "reviewed", "relevant", "dismissed"]);

function severityClass(value) {
  return SEVERITIES.has(value) ? value : "low";
}

function statusClass(value) {
  return STATUSES.has(value) ? value : "new";
}

function safeUrl(value) {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "#";
  } catch {
    return "#";
  }
}

function formatTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "—";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function formatClock() {
  const now = new Date();
  const date = new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(now);
  const time = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit" }).format(now);
  const hour = now.getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  $("desk-date").textContent = `${date} · ${time}`;
  $("greeting").textContent = `${greeting}, team.`;
}

function formatUsd(value) {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${Math.round(value / 1_000)}k`;
  return `$${value}`;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      Authorization: `Bearer ${state.token}`,
      "X-User-Id": state.actor,
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = Array.isArray(body.detail)
      ? body.detail.map((item) => item.msg).join("; ")
      : body.detail;
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return response.json();
}

async function loadAuditEvents({ force = false } = {}) {
  const container = $("audit-list");
  if (!force && state.auditLoaded) {
    renderAudit();
    return;
  }
  container.innerHTML = '<div class="loading">Loading review history…</div>';
  try {
    state.auditEvents = await api("/api/audit?limit=100");
    state.auditLoaded = true;
    renderAudit();
  } catch (error) {
    state.auditLoaded = false;
    container.innerHTML = `<div class="error-state">Could not load the audit trail. ${esc(error.message)}</div>`;
  }
}

async function loadAll() {
  const response = await Promise.all([api("/api/incidents"), api("/api/vendors")]);
  state.incidents = response[0];
  state.vendors = response[1];
  if (!state.incidents.some((incident) => incident.id === state.selectedId)) {
    state.selectedId = state.incidents[0]?.id ?? null;
  }
  renderCounts();
  renderOverviewList();
  renderQueue();
  renderVendors();
  renderAuditFilter();
  renderDetail();
}

function displayError(error) {
  const message = `${esc(error.message)}. Use Refresh to retry.`;
  $("incident-list").innerHTML = `<div class="error-state">${message}</div>`;
  $("queue-body").innerHTML = "";
  $("queue-empty").hidden = false;
  $("queue-empty").innerHTML = `<span class="empty-mark" aria-hidden="true">⌕</span><h3>Could not load the queue</h3><p>${message}</p>`;
  $("vendor-grid").innerHTML = `<div class="error-state">${message}</div>`;
}

async function refreshData({ announce = false, message = "Signals refreshed." } = {}) {
  const button = $("refresh");
  if (button) button.disabled = true;
  try {
    await loadAll();
    state.auditLoaded = false;
    if (state.route === "audit") {
      await loadAuditEvents({ force: true });
    }
    if (announce) toast(message);
  } catch (error) {
    displayError(error);
    toast(error.message);
  } finally {
    if (button) button.disabled = false;
  }
}

function renderCounts() {
  const counts = state.incidents.reduce(
    (totals, incident) => {
      totals.all += 1;
      totals[incident.status] = (totals[incident.status] || 0) + 1;
      return totals;
    },
    { all: 0, new: 0, reviewed: 0, relevant: 0, dismissed: 0 },
  );
  $$("[data-count]").forEach((element) => {
    element.textContent = String(counts[element.dataset.count] ?? 0);
  });

  const material = state.incidents.filter((incident) => ["critical", "high"].includes(incident.severity));
  const exposure = material.reduce((sum, incident) => sum + incident.open_order_exposure_usd, 0);
  const confidence = state.incidents.length
    ? Math.round(state.incidents.reduce((sum, incident) => sum + incident.confidence, 0) / state.incidents.length)
    : 0;
  const categories = new Set(state.incidents.map((incident) => incident.vendor_category));

  $("metric-new").textContent = String(counts.all ? counts.new : 0).padStart(2, "0");
  $("metric-exposure").textContent = formatUsd(exposure);
  $("metric-vendors").textContent = String(new Set(state.incidents.map((incident) => incident.vendor_id)).size).padStart(2, "0");
  $("metric-confidence").textContent = `${confidence}%`;
  $("metric-categories").innerHTML = `Across <b>${categories.size}</b> supply ${categories.size === 1 ? "category" : "categories"}`;
  $("sidebar-signals").textContent = String(
    state.incidents.reduce((sum, incident) => sum + incident.evidence.length, 0),
  );
  $("sidebar-vendors").textContent = String(state.vendors.length);
}

function renderFilterState() {
  $$("[data-status]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.status === state.status);
  });
}

function incidentMatchesSearch(incident, query) {
  if (!query) return true;
  const haystack = [
    incident.vendor_name,
    incident.vendor_category,
    incident.event_type,
    incident.title,
    incident.summary,
    ...incident.affected_locations,
  ]
    .join(" ")
    .toLowerCase();
  return haystack.includes(query.toLowerCase());
}

function renderOverviewList() {
  const items =
    state.status === "all"
      ? state.incidents
      : state.incidents.filter((incident) => incident.status === state.status);
  if (!items.length) {
    $("incident-list").innerHTML =
      '<div class="empty-state"><span class="empty-mark" aria-hidden="true">⌖</span><h3>No signals in this view</h3><p>Try another status filter.</p></div>';
    return;
  }
  $("incident-list").innerHTML = items
    .map(
      (incident) => `<article class="incident-card ${
        incident.id === state.selectedId ? "is-selected" : ""
      }" data-select-id="${esc(incident.id)}" role="button" tabindex="0" aria-pressed="${
        incident.id === state.selectedId
      }">
        <div class="incident-top">
          <span class="badge severity-${severityClass(incident.severity)}">${esc(incident.severity)}</span>
          <span class="status-badge status-${statusClass(incident.status)}">${esc(incident.status)}</span>
          <time datetime="${esc(incident.last_updated)}">${formatTime(incident.last_updated)}</time>
        </div>
        <h3 class="incident-title">${esc(incident.vendor_name)}</h3>
        <p class="incident-event">${esc(incident.event_type)}</p>
        <p class="incident-summary">${esc(incident.summary)}</p>
        <div class="incident-meta">
          <span>◈ ${incident.evidence.length} source${incident.evidence.length === 1 ? "" : "s"}</span>
          <span>◎ ${incident.open_orders} open orders</span>
          <span class="risk">Risk ${incident.risk_score}</span>
        </div>
      </article>`,
    )
    .join("");
}

function headline(incident) {
  const prefix = `${incident.vendor_name}: `;
  return incident.title.startsWith(prefix) ? incident.title.slice(prefix.length) : incident.title;
}

function evidenceLink(evidence) {
  const url = safeUrl(evidence.source_url);
  const label = `${esc(evidence.title)} ↗`;
  if (url === "#") {
    return `<span class="evidence-title">${label}</span>`;
  }
  return `<a class="evidence-title" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${label}</a>`;
}

function auditEntryHtml(event) {
  return `<p><strong>${esc(event.actor)}</strong> moved ${esc(event.old_status)} → ${esc(event.new_status)} · ${esc(event.rationale)}</p>`;
}

function renderDetail() {
  const incident = state.incidents.find((item) => item.id === state.selectedId);
  if (!incident) {
    $("detail-panel").innerHTML =
      '<div class="empty-state"><span class="empty-mark" aria-hidden="true">⌖</span><h3>Select a signal</h3><p>Review cited evidence, assess possible impact, then record your decision.</p></div>';
    return;
  }

  $("detail-panel").innerHTML = `<div class="detail-head">
      <div class="detail-top">
        <span class="badge severity-${severityClass(incident.severity)}">${esc(incident.severity)} risk</span>
        <span class="status-badge status-${statusClass(incident.status)}">${esc(incident.status)}</span>
        <span class="risk">Risk ${incident.risk_score}</span>
        <time datetime="${esc(incident.last_updated)}">Updated ${formatTime(incident.last_updated)}</time>
      </div>
      <h2 class="detail-title">${esc(incident.vendor_name)} — ${esc(headline(incident))}</h2>
      <p class="detail-subtitle">${esc(incident.event_type)} · ${esc(incident.vendor_category)} · ${incident.confidence}% confidence</p>
      <p class="detail-summary">${esc(incident.summary)}</p>
      <div class="detail-meta">
        <span>⌖ ${incident.affected_locations.map(esc).join(" · ")}</span>
        <span>◎ ${incident.open_orders} open orders</span>
        <span>◈ ${incident.evidence.length} source records</span>
      </div>
    </div>
    <div class="detail-body">
      <div class="info-section">
        <p class="subheading">Source evidence</p>
        ${incident.evidence
          .map(
            (evidence) => `<article class="evidence-card">
              ${evidenceLink(evidence)}
              <div class="evidence-meta">
                <span>${esc(evidence.source)}</span>
                <span>·</span>
                <span>${formatTime(evidence.published_at)}</span>
                <span>·</span>
                <span>${esc(evidence.signal_type)}</span>
              </div>
              <p>${esc(evidence.summary)}</p>
            </article>`,
          )
          .join("")}
      </div>
      <div class="split-info">
        <div class="info-section">
          <p class="subheading">Reported facts</p>
          ${incident.facts.map((fact) => `<p>• ${esc(fact)}</p>`).join("")}
        </div>
        <div class="info-section">
          <p class="subheading">Potential impact · inference</p>
          ${incident.inferred_impacts.map((item) => `<p>• ${esc(item)}</p>`).join("")}
        </div>
      </div>
      <div class="info-section">
        <p class="subheading">Verify before acting</p>
        <ul class="check-list">
          ${incident.verification_needed.map((item) => `<li>${esc(item)}</li>`).join("")}
        </ul>
      </div>
      <label class="rationale-field">
        <span class="subheading">Decision note · required</span>
        <textarea id="decision-note" maxlength="500" placeholder="Explain the decision and what to verify next."></textarea>
      </label>
      <div class="action-row">
        <button class="primary" type="button" data-status-target="relevant">✓ Mark relevant</button>
        <button type="button" data-status-target="reviewed">◷ Mark reviewed</button>
        <button class="danger" type="button" data-status-target="dismissed">✕ Dismiss</button>
      </div>
      <div class="info-section" id="incident-audit">
        <p class="subheading">Review activity</p>
        <div class="notice">Loading review history…</div>
      </div>
    </div>`;

  $$("[data-status-target]").forEach((button) => {
    button.addEventListener("click", () => updateStatus(incident.id, button.dataset.statusTarget, button));
  });
  loadIncidentAudit(incident.id);
}

async function loadIncidentAudit(incidentId) {
  try {
    const events = await api(`/api/audit?incident_id=${encodeURIComponent(incidentId)}&limit=10`);
    if (state.selectedId !== incidentId) return;
    const container = $("incident-audit");
    if (!container) return;
    container.innerHTML = `<p class="subheading">Review activity</p>${events.length ? events
      .slice(0, 3)
      .map((event) => auditEntryHtml(event)) : '<div class="notice">No recorded decisions yet.</div>'}`;
  } catch {
    const container = $("incident-audit");
    if (!container) return;
    container.innerHTML =
      '<p class="subheading">Review activity</p><div class="notice danger">Could not load review history.</div>';
  }
}

async function updateStatus(incidentId, status, button) {
  const field = $("decision-note");
  const rationale = field?.value.trim() ?? "";
  if (rationale.length < 3) {
    field?.focus();
    toast("Add a short review note first.");
    return;
  }
  button.disabled = true;
  try {
    await api(`/api/incidents/${encodeURIComponent(incidentId)}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status, rationale }),
    });
    toast(`Signal marked ${status}. Review recorded.`);
    state.auditLoaded = false;
    await refreshData();
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
  }
}

function selectIncident(id, { navigate = false } = {}) {
  state.selectedId = id;
  renderOverviewList();
  renderDetail();
  if (navigate && state.route !== "overview") {
    location.hash = "overview";
  }
}

function renderQueue() {
  const query = state.search.trim();
  const items = state.incidents.filter((incident) => {
    const statusMatch = state.status === "all" || incident.status === state.status;
    return statusMatch && incidentMatchesSearch(incident, query);
  });
  $("queue-empty").hidden = true;
  $("queue-empty").innerHTML = "";
  if (!items.length) {
    $("queue-body").innerHTML = "";
    $("queue-empty").innerHTML =
      '<span class="empty-mark" aria-hidden="true">⌕</span><h3>No matching incidents</h3><p>Try another status or clear the search field.</p>';
    $("queue-empty").hidden = false;
    return;
  }
  $("queue-body").innerHTML = items
    .map(
      (incident) => `<tr>
        <td><strong>${esc(incident.vendor_name)}</strong><span class="cell-sub">${esc(incident.event_type)}</span></td>
        <td><span class="badge severity-${severityClass(incident.severity)}">${esc(incident.severity)}</span></td>
        <td><span class="status-badge status-${statusClass(incident.status)}">${esc(incident.status)}</span></td>
        <td>${incident.evidence.length}</td>
        <td class="numeric">${incident.risk_score}</td>
        <td><button class="link-button" type="button" data-open-id="${esc(incident.id)}">Review</button></td>
      </tr>`,
    )
    .join("");
}

function renderVendors() {
  const byVendor = new Map(state.incidents.map((incident) => [incident.vendor_id, incident]));
  $("vendor-grid").innerHTML = state.vendors
    .map((vendor) => {
      const incident = byVendor.get(vendor.id);
      return `<article class="vendor-card">
        <div class="vendor-top">
          <div>
            <h3>${esc(vendor.name)}</h3>
            <p class="cell-sub">${esc(vendor.category)}</p>
          </div>
          <span class="criticality-badge criticality-${esc(vendor.criticality)}">${esc(vendor.criticality)}</span>
        </div>
        <p class="cell-sub">⌖ ${vendor.locations.map(esc).join(" · ")}</p>
        <div class="vendor-stats">
          <div class="vendor-stat">Open orders<strong>${vendor.open_orders}</strong></div>
          <div class="vendor-stat">Open-order exposure<strong>${formatUsd(vendor.estimated_exposure_usd)}</strong></div>
        </div>
        <div>
          <p class="subheading">Approved alternatives</p>
          <div class="chip-row" style="margin-top:8px">${
            vendor.approved_alternatives.length
              ? vendor.approved_alternatives.map((item) => `<span class="chip">${esc(item)}</span>`).join("")
              : '<span class="chip">None on file</span>'
          }</div>
        </div>
        <div>
          <p class="subheading">Active signal</p>
          ${
            incident
              ? `<div class="chip-row" style="margin-top:8px"><span class="status-badge status-${statusClass(incident.status)}">${esc(incident.status)}</span><span class="chip">Risk ${incident.risk_score}</span><span class="chip">${esc(incident.event_type)}</span></div><button class="button button-secondary" style="margin-top:12px" type="button" data-open-id="${esc(incident.id)}">Review incident</button>`
              : '<div class="chip-row" style="margin-top:8px"><span class="chip">No active signal</span></div>'
          }
        </div>
      </article>`;
    })
    .join("");
}

function renderAuditFilter() {
  const select = $("audit-filter");
  const current = select.value || state.auditFilter;
  const options = '<option value="all">All incidents</option>' + state.incidents
    .map((incident) => `<option value="${esc(incident.id)}">${esc(incident.vendor_name)}</option>`)
    .join("");
  select.innerHTML = options;
  select.value = select.value && Array.from(select.options).some((option) => option.value === current)
    ? current
    : "all";
  state.auditFilter = select.value;
}

function renderAudit() {
  const container = $("audit-list");
  const events =
    state.auditFilter === "all"
      ? state.auditEvents
      : state.auditEvents.filter((event) => event.incident_id === state.auditFilter);
  if (!events.length) {
    container.innerHTML =
      '<div class="empty-state"><span class="empty-mark" aria-hidden="true">◷</span><h3>No recorded decisions yet</h3><p>Decisions appear here after an analyst updates an incident.</p></div>';
    return;
  }
  container.innerHTML = events
    .map((event) => {
      const incident = state.incidents.find((item) => item.id === event.incident_id);
      return `<article class="audit-page-entry">
        <div class="audit-page-meta">
          <span class="status-badge status-${statusClass(event.old_status)}">${esc(event.old_status)}</span>
          <span aria-hidden="true">→</span>
          <span class="status-badge status-${statusClass(event.new_status)}">${esc(event.new_status)}</span>
          <time datetime="${esc(event.created_at)}">${formatTime(event.created_at)}</time>
        </div>
        <h3>${esc(incident ? incident.vendor_name : event.incident_id)}</h3>
        ${auditEntryHtml(event)}
      </article>`;
    })
    .join("");
}

function bindCopyButtons() {
  $$("[data-copy-target]").forEach((button) => {
    button.addEventListener("click", async () => {
      const source = $(button.dataset.copyTarget);
      const text = source?.textContent.replace(/^\s+/, "") ?? "";
      if (!text) return;
      try {
        await navigator.clipboard.writeText(text);
        toast("Copied to clipboard.");
      } catch {
        const helper = document.createElement("textarea");
        helper.value = text;
        document.body.appendChild(helper);
        helper.select();
        document.execCommand("copy");
        helper.remove();
        toast("Copied to clipboard.");
      }
    });
  });
}

let toastTimer;
function toast(message) {
  const element = $("toast");
  element.textContent = message;
  element.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => element.classList.remove("show"), 2700);
}

function renderRoute() {
  const route = location.hash.replace("#", "") || "overview";
  const active = ROUTES[route] ? route : "overview";
  state.route = active;
  $$("[data-page]").forEach((page) => {
    page.hidden = page.dataset.page !== active;
  });
  $$(".nav-link").forEach((link) => {
    const isActive = link.dataset.route === active;
    link.classList.toggle("is-active", isActive);
    if (isActive) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  $("breadcrumb-label").textContent = ROUTES[active];
  if (active === "audit") {
    loadAuditEvents();
  }
  if (active === "overview") {
    renderDetail();
  }
  window.scrollTo(0, 0);
}

function bindEvents() {
  window.addEventListener("hashchange", renderRoute);
  $$("[data-status]").forEach((button) => {
    button.addEventListener("click", () => {
      state.status = button.dataset.status;
      renderFilterState();
      renderOverviewList();
      renderQueue();
    });
  });
  $("queue-search").addEventListener("input", (event) => {
    state.search = event.target.value;
    renderQueue();
  });
  $("audit-filter").addEventListener("change", (event) => {
    state.auditFilter = event.target.value;
    renderAudit();
  });
  $("refresh").addEventListener("click", () => refreshData({ announce: true }));
  document.addEventListener("click", (event) => {
    const card = event.target.closest("[data-select-id]");
    if (card) {
      selectIncident(card.dataset.selectId);
      return;
    }
    const open = event.target.closest("[data-open-id]");
    if (open) {
      selectIncident(open.dataset.openId, { navigate: true });
      return;
    }
    const copy = event.target.closest("[data-copy-target]");
    if (copy) {
      void copyButton(copy);
      return;
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    const card = event.target.closest?.("[data-select-id]");
    if (!card) return;
    event.preventDefault();
    selectIncident(card.dataset.selectId);
  });
}

async function copyButton(button) {
  const source = $(button.dataset.copyTarget);
  const text = source?.textContent.replace(/^\s+/, "") ?? "";
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    toast("Copied to clipboard.");
  } catch {
    const helper = document.createElement("textarea");
    helper.value = text;
    helper.style.position = "fixed";
    helper.style.opacity = "0";
    document.body.appendChild(helper);
    helper.select();
    try {
      document.execCommand("copy");
      toast("Copied to clipboard.");
    } catch {
      toast("Copy failed. Select the text manually.");
    }
    helper.remove();
  }
}

async function start() {
  formatClock();
  setInterval(formatClock, 60_000);
  bindEvents();
  state.token = sessionStorage.getItem(TOKEN_KEY) || "";
  localStorage.removeItem(TOKEN_KEY);
  try {
    const config = await fetch("/api/config").then((response) => response.json());
    if (!state.token && config.demo_token) {
      state.token = config.demo_token;
      sessionStorage.setItem(TOKEN_KEY, state.token);
    }
  } catch {
    // Keep the workspace usable: the prompted token below still authenticates.
  }
  if (!state.token) {
    const entered = window.prompt("Enter your Vanguard API bearer token:") || "";
    state.token = entered.trim();
    if (state.token) sessionStorage.setItem(TOKEN_KEY, state.token);
  }
  if (!state.token) {
    toast("A bearer token is required to load signals.");
  }
  try {
    await loadAll();
  } catch (error) {
    displayError(error);
    if (!state.token) toast("A bearer token is required to load signals.");
  }
  renderFilterState();
  renderRoute();
}

start();
