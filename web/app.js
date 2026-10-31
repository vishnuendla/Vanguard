const TOKEN_KEY = "vanguard-demo-token";
const state = {
  token: "",
  actor: "vanguard-analyst",
  incidents: [],
  selectedId: null,
  status: "all",
};
const $ = (id) => document.getElementById(id);
const esc = (value) =>
  String(value).replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
const SEVERITIES = new Set(["critical", "high", "moderate", "low"]);

function severityClass(value) {
  return SEVERITIES.has(value) ? value : "low";
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

function renderClock() {
  const now = new Date();
  const date = new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  })
    .format(now)
    .toUpperCase();
  const time = new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
  }).format(now);
  const hour = now.getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  $("desk-date").textContent = `${date} · ${time}`;
  $("greeting").textContent = `${greeting}, team.`;
}

function renderMetrics(items) {
  const open = items.filter((item) => item.status === "new");
  const material = items.filter((item) => ["critical", "high"].includes(item.severity));
  const exposure = material.reduce((sum, item) => sum + item.open_order_exposure_usd, 0);
  const categories = new Set(items.map((item) => item.vendor_category));
  const confidence = items.length
    ? Math.round(items.reduce((sum, item) => sum + item.confidence, 0) / items.length)
    : 0;

  $("open-count").textContent = String(open.length).padStart(2, "0");
  $("exposure").textContent = formatUsd(exposure);
  $("vendor-count").textContent = String(new Set(items.map((item) => item.vendor_id)).size).padStart(
    2,
    "0",
  );
  $("confidence").textContent = `${confidence}%`;
  $("vendor-note").innerHTML = `Across <b>${categories.size}</b> supply ${
    categories.size === 1 ? "category" : "categories"
  }`;
  $("nav-count").textContent = String(open.length);
  $("all-count").textContent = String(items.length);
  $("new-count").textContent = String(open.length);
  $("reviewed-count").textContent = String(
    items.filter((item) => item.status === "reviewed").length,
  );
}

function renderList() {
  const items =
    state.status === "all"
      ? state.incidents
      : state.incidents.filter((item) => item.status === state.status);
  const empty = items.length
    ? ""
    : `<div class="loading">No signals in this view.</div>`;
  $("incident-list").innerHTML =
    items
      .map(
        (item) => `<article class="incident-card ${
          item.id === state.selectedId ? "selected" : ""
        }" data-id="${esc(item.id)}" role="button" tabindex="0" aria-pressed="${
          item.id === state.selectedId
        }"><div class="card-top"><span class="severity ${severityClass(
          item.severity,
        )}">${esc(item.severity)}</span><span class="status-pill">${esc(
          item.status.toUpperCase(),
        )}</span><span class="card-time">${formatTime(
          item.last_updated,
        )}</span></div><div class="card-title">${esc(item.vendor_name)} <span style="color:#667682;font-weight:400">/</span> ${esc(
          item.event_type,
        )}</div><div class="card-summary">${esc(
          item.summary,
        )}</div><div class="card-bottom"><span>◈ ${item.evidence.length} source${
          item.evidence.length === 1 ? "" : "s"
        }</span><span>${item.confidence}% confidence</span><span class="risk">RISK ${
          item.risk_score
        }</span></div></article>`,
      )
      .join("") || empty;

  document.querySelectorAll(".incident-card").forEach((card) => {
    card.addEventListener("click", () => selectIncident(card.dataset.id));
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectIncident(card.dataset.id);
      }
    });
  });
}

function evidenceLink(item) {
  const url = safeUrl(item.source_url);
  const label = `${esc(item.title)} ↗`;
  if (url === "#") return `<span class="evidence-title">${label}</span>`;
  return `<a class="evidence-title" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${label}</a>`;
}

function renderDetail(incident) {
  if (!incident) {
    $("detail-panel").innerHTML =
      '<div class="detail-empty"><div class="empty-icon">⌖</div><h3>Select a signal</h3><p>Review cited evidence, assess potential impact, then record your decision.</p></div>';
    return;
  }

  const prefix = `${incident.vendor_name}: `;
  const headline = incident.title.startsWith(prefix)
    ? incident.title.slice(prefix.length)
    : incident.title;
  const actions = [
    { status: "relevant", label: "✓ Mark relevant", className: "" },
    { status: "reviewed", label: "◷ Reviewed", className: "secondary" },
    { status: "dismissed", label: "✕ Dismiss", className: "danger" },
  ];

  $("detail-panel").innerHTML = `<div class="detail-head"><div class="card-top"><span class="severity ${severityClass(
    incident.severity,
  )}">${esc(incident.severity)} risk</span><span class="status-pill">${esc(
    incident.status.toUpperCase(),
  )}</span><span class="card-time">RISK SCORE ${
    incident.risk_score
  }</span></div><div class="detail-title">${esc(incident.vendor_name)} — ${esc(
    headline,
  )}</div><div class="detail-summary">${esc(
    incident.summary,
  )}</div><div class="detail-meta"><span>⌖ ${incident.affected_locations
    .map(esc)
    .join(" · ")}</span><span>▦ ${esc(
    incident.vendor_category,
  )}</span><span>◎ ${incident.open_orders} open orders</span><span>◷ Updated ${formatTime(
    incident.last_updated,
  )}</span><span>${incident.confidence}% confidence</span></div></div><div class="detail-body"><div class="subheading">SOURCE EVIDENCE · ${
    incident.evidence.length
  } RECORDS</div>${incident.evidence
    .map(
      (item) => `<article class="evidence">${evidenceLink(
        item,
      )}<div class="evidence-source"><span>${esc(
        item.source,
      )}</span><span>·</span><span>${formatTime(
        item.published_at,
      )}</span><span>·</span><span>${esc(
        item.signal_type,
      )}</span></div><p>${esc(item.summary)}</p></article>`,
    )
    .join(
      "",
    )}<div class="split-info"><div class="info-box"><div class="subheading">REPORTED FACTS</div>${incident.facts
    .map((item) => `<p>• ${esc(item)}</p>`)
    .join(
      "",
    )}</div><div class="info-box"><div class="subheading">POTENTIAL IMPACT · INFERENCE</div>${incident.inferred_impacts
    .map((item) => `<p>• ${esc(item)}</p>`)
    .join(
      "",
    )}</div></div><div class="info-box"><div class="subheading">VERIFY BEFORE ACTING</div><ul class="check-list">${incident.verification_needed
    .map((item) => `<li>${esc(item)}</li>`)
    .join(
      "",
    )}</ul></div><div class="rationale-wrap"><input id="rationale" maxlength="500" aria-label="Review note" placeholder="Add a short review note (required)" /></div><div class="action-row">${actions
    .map(
      (action) =>
        `<button type="button" class="${action.className}" data-next="${action.status}">${action.label}</button>`,
    )
    .join(
      "",
    )}</div><div id="audit-box"></div></div>`;

  document.querySelectorAll(".action-row button").forEach((button) => {
    button.addEventListener("click", () => updateStatus(incident.id, button.dataset.next, button));
  });
  loadAudit(incident.id);
}

async function selectIncident(id) {
  state.selectedId = id;
  renderList();
  try {
    renderDetail(await api(`/api/incidents/${encodeURIComponent(id)}`));
  } catch (error) {
    toast(error.message);
  }
}

async function loadAudit(id) {
  try {
    const events = await api(`/api/audit?incident_id=${encodeURIComponent(id)}&limit=10`);
    $("audit-box").innerHTML = events.length
      ? `<div class="subheading" style="margin-top:14px">RECENT REVIEW ACTIVITY</div>${events
          .slice(0, 3)
          .map(
            (event) =>
              `<div class="audit-line"><b>${esc(event.actor)}</b> changed ${esc(
                event.old_status,
              )} → ${esc(event.new_status)} · ${esc(event.rationale)} <span style="color:#667682">${formatTime(
                event.created_at,
              )}</span></div>`,
          )
          .join("")}`
      : '<div class="audit-line">No review activity recorded yet.</div>';
  } catch {
    $("audit-box").innerHTML =
      '<div class="audit-line">Review activity is temporarily unavailable.</div>';
  }
}

async function updateStatus(id, status, button) {
  const rationale = $("rationale")?.value.trim() || "";
  if (rationale.length < 3) {
    toast("Add a short review note first.");
    $("rationale")?.focus();
    return;
  }
  button.disabled = true;
  try {
    await api(`/api/incidents/${encodeURIComponent(id)}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status, rationale }),
    });
    toast(`Signal marked ${status}. Review recorded.`);
    await load();
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
  }
}

let toastTimer;
function toast(message) {
  const element = $("toast");
  element.textContent = message;
  element.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => element.classList.remove("show"), 2700);
}

async function load() {
  $("incident-list").innerHTML = '<div class="loading">Refreshing source signals…</div>';
  try {
    state.incidents = await api("/api/incidents");
    renderMetrics(state.incidents);
    renderList();
    const selected =
      state.incidents.find((item) => item.id === state.selectedId) || state.incidents[0];
    if (selected) {
      await selectIncident(selected.id);
    } else {
      renderDetail(null);
    }
  } catch (error) {
    $("incident-list").innerHTML = `<div class="error">${esc(
      error.message,
    )}. Refresh the page to retry.</div>`;
  }
}

async function start() {
  renderClock();
  setInterval(renderClock, 60_000);
  state.token = sessionStorage.getItem(TOKEN_KEY) || "";
  localStorage.removeItem(TOKEN_KEY);
  try {
    const config = await fetch("/api/config").then((response) => response.json());
    if (!state.token && config.demo_token) {
      state.token = config.demo_token;
      sessionStorage.setItem(TOKEN_KEY, state.token);
    }
  } catch {
    // A deployment token prompt below keeps the dashboard usable without /api/config.
  }
  if (!state.token) {
    const entered = window.prompt("Enter your Vanguard API bearer token:") || "";
    state.token = entered.trim();
    if (state.token) sessionStorage.setItem(TOKEN_KEY, state.token);
  }
  await load();
}

document.querySelectorAll(".filter").forEach((button) => {
  button.addEventListener("click", () => {
    state.status = button.dataset.status;
    document.querySelectorAll(".filter").forEach((item) => {
      item.classList.toggle("active", item === button);
    });
    renderList();
  });
});
$("refresh").addEventListener("click", load);
start();
