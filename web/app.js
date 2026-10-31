const state = { token: "", actor: "vanguard-analyst", incidents: [], selectedId: null, status: "all" };
const $ = (id) => document.getElementById(id);
const esc = (value) => String(value).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { Authorization: `Bearer ${state.token}`, "X-User-Id": state.actor, "Content-Type": "application/json", ...(options.headers || {}) } });
  if (!response.ok) throw new Error((await response.json()).detail || `Request failed (${response.status})`);
  return response.json();
}
function severityClass(s) { return ({ critical: "critical", high: "high", moderate: "moderate", low: "low" })[s] || "low"; }
function formatTime(date) { return new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", timeZone: "America/Los_Angeles" }).format(new Date(date)); }
function renderMetrics(items) {
  const open = items.filter((i) => !["dismissed", "relevant"].includes(i.status));
  const highest = items.filter((i) => ["critical", "high"].includes(i.severity));
  const exposure = highest.reduce((sum, i) => sum + (i.vendor_id === "northstar-logistics" ? 420000 : i.vendor_id === "apex-components" ? 185000 : i.vendor_id === "solstice-energy" ? 96000 : 0), 0);
  $("open-count").textContent = open.length.toString().padStart(2, "0");
  $("exposure").textContent = `$${Math.round(exposure / 1000)}k`;
  $("vendor-count").textContent = new Set(items.map((i) => i.vendor_id)).size.toString().padStart(2, "0");
  $("confidence").textContent = `${items.length ? Math.round(items.reduce((s, i) => s + i.confidence, 0) / items.length) : 0}%`;
  $("nav-count").textContent = String(open.length);
  $("all-count").textContent = String(items.length);
  $("new-count").textContent = String(items.filter((i) => i.status === "new").length);
}
function renderList() {
  const items = state.status === "all" ? state.incidents : state.incidents.filter((i) => i.status === state.status);
  $("incident-list").innerHTML = items.length ? items.map((i) => `<article class="incident-card ${i.id === state.selectedId ? "selected" : ""}" data-id="${esc(i.id)}"><div class="card-top"><span class="severity ${severityClass(i.severity)}">${esc(i.severity)}</span><span class="status-pill">${esc(i.status.toUpperCase())}</span><span class="card-time">${formatTime(i.last_updated)}</span></div><div class="card-title">${esc(i.vendor_name)} <span style="color:#667682;font-weight:400">/</span> ${esc(i.event_type)}</div><div class="card-summary">${esc(i.summary)}</div><div class="card-bottom"><span>◈ ${i.evidence.length} source${i.evidence.length === 1 ? "" : "s"}</span><span>${i.confidence}% confidence</span><span class="risk">RISK ${i.risk_score}</span></div></article>`).join("") : '<div class="loading">No signals in this view.</div>';
  document.querySelectorAll(".incident-card").forEach((card) => card.addEventListener("click", () => selectIncident(card.dataset.id)));
}
function renderDetail(incident) {
  if (!incident) { $("detail-panel").innerHTML = '<div class="detail-empty"><div class="empty-icon">⌖</div><h3>Select a signal</h3><p>Review cited evidence, assess potential impact, then record your decision.</p></div>'; return; }
  $("detail-panel").innerHTML = `<div class="detail-head"><div class="card-top"><span class="severity ${severityClass(incident.severity)}">${esc(incident.severity)} risk</span><span class="status-pill">${esc(incident.status.toUpperCase())}</span><span class="card-time">RISK SCORE ${incident.risk_score}</span></div><div class="detail-title">${esc(incident.vendor_name)} — ${esc(incident.title.replace(`${incident.vendor_name}: `, ""))}</div><div class="detail-summary">${esc(incident.summary)}</div><div class="detail-meta"><span>⌖ ${incident.affected_locations.map(esc).join(" · ")}</span><span>◷ Updated ${formatTime(incident.last_updated)}</span><span>◎ ${incident.confidence}% confidence</span></div></div><div class="detail-body"><div class="subheading">SOURCE EVIDENCE · ${incident.evidence.length} RECORDS</div>${incident.evidence.map((e) => `<article class="evidence"><a class="evidence-title" href="${esc(e.source_url)}" target="_blank" rel="noopener noreferrer">${esc(e.title)} ↗</a><div class="evidence-source"><span>${esc(e.source)}</span><span>·</span><span>${formatTime(e.published_at)}</span><span>·</span><span>${esc(e.signal_type)}</span></div><p>${esc(e.summary)}</p></article>`).join("")}<div class="split-info"><div class="info-box"><div class="subheading">REPORTED FACTS</div>${incident.facts.map((x) => `<p>• ${esc(x)}</p>`).join("")}</div><div class="info-box"><div class="subheading">POTENTIAL IMPACT · INFERENCE</div>${incident.inferred_impacts.map((x) => `<p>• ${esc(x)}</p>`).join("")}</div></div><div class="info-box"><div class="subheading">VERIFY BEFORE ACTING</div><ul class="check-list">${incident.verification_needed.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div><div class="rationale-wrap"><input id="rationale" maxlength="500" placeholder="Add a short review note (required)" /></div><div class="action-row"><button data-next="relevant">✓ Mark relevant</button><button class="secondary" data-next="reviewed">◷ Reviewed</button><button class="danger" data-next="dismissed">× Dismiss</button></div><div id="audit-box"></div></div>`;
  document.querySelectorAll(".action-row button").forEach((button) => button.addEventListener("click", () => updateStatus(incident.id, button.dataset.next, button)));
  loadAudit(incident.id);
}
async function selectIncident(id) {
  state.selectedId = id;
  renderList();
  try { renderDetail(await api(`/api/incidents/${encodeURIComponent(id)}`)); } catch (error) { toast(error.message); }
}
async function loadAudit(id) {
  try {
    const events = await api(`/api/audit?incident_id=${encodeURIComponent(id)}`);
    if (!events.length) return;
    $("audit-box").innerHTML = `<div class="subheading" style="margin-top:14px">RECENT REVIEW ACTIVITY</div>${events.slice(0, 3).map((e) => `<div class="audit-line"><b>${esc(e.actor)}</b> changed ${esc(e.old_status)} → ${esc(e.new_status)} · ${esc(e.rationale)} <span style="color:#667682">${formatTime(e.created_at)}</span></div>`).join("")}`;
  } catch (_) { /* Keep the evidence panel usable if audit history is empty. */ }
}
async function updateStatus(id, status, button) {
  const rationale = $("rationale")?.value.trim() || "";
  if (rationale.length < 3) { toast("Add a short review note first."); $("rationale")?.focus(); return; }
  button.disabled = true;
  try {
    await api(`/api/incidents/${encodeURIComponent(id)}/status`, { method: "PATCH", body: JSON.stringify({ status, rationale }) });
    toast(`Signal marked ${status}. Review recorded.`);
    await load();
    await selectIncident(id);
  } catch (error) { toast(error.message); }
  finally { button.disabled = false; }
}
function toast(message) { const el = $("toast"); el.textContent = message; el.classList.add("show"); setTimeout(() => el.classList.remove("show"), 2700); }
async function load() {
  $("incident-list").innerHTML = '<div class="loading">Refreshing source signals…</div>';
  try { state.incidents = await api("/api/incidents"); renderMetrics(state.incidents); renderList(); const selected = state.incidents.find((i) => i.id === state.selectedId) || state.incidents[0]; if (selected) await selectIncident(selected.id); }
  catch (error) { $("incident-list").innerHTML = `<div class="error">${esc(error.message)}. Refresh the page to retry.</div>`; }
}
async function start() {
  try { state.token = localStorage.getItem("vanguard-demo-token") || ""; if (!state.token) { state.token = (await fetch("/api/config").then((r) => r.json())).demo_token; if (!state.token) state.token = window.prompt("Enter your Vanguard API bearer token:") || ""; if (state.token) localStorage.setItem("vanguard-demo-token", state.token); } await load(); }
  catch (error) { $("incident-list").innerHTML = `<div class="error">${esc(error.message)}</div>`; }
}
document.querySelectorAll(".filter").forEach((button) => button.addEventListener("click", () => { state.status = button.dataset.status; document.querySelectorAll(".filter").forEach((b) => b.classList.toggle("active", b === button)); renderList(); }));
$("refresh").addEventListener("click", load);
start();
