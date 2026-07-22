/* ==========================================================================
   ORKG Comparison Extractor — front-end controller.
   Talks to the FastAPI backend under /api/v1. No framework, no build step.
   ========================================================================== */
"use strict";

const API = "/api/v1";
const STEP_ORDER = ["classifier", "segmenter", "detector", "extractor", "synthesizer"];

/* ---------- tiny helpers ---------- */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

async function api(path, opts = {}) {
  const res = await fetch(`${API}${path}`, opts);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
}

function toast(message, type = "info", ms = 4000) {
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = message;
  $("#toasts").appendChild(el);
  setTimeout(() => { el.style.opacity = "0"; setTimeout(() => el.remove(), 200); }, ms);
}

/* ---------- theme ---------- */
(function initTheme() {
  const stored = localStorage.getItem("theme");
  const dark = stored ? stored === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.classList.toggle("dark", dark);
  syncThemeIcon(dark);
})();
function syncThemeIcon(dark) {
  $("#icon-sun").classList.toggle("hidden", !dark);
  $("#icon-moon").classList.toggle("hidden", dark);
}
$("#theme-toggle").addEventListener("click", () => {
  const dark = !document.documentElement.classList.contains("dark");
  document.documentElement.classList.toggle("dark", dark);
  localStorage.setItem("theme", dark ? "dark" : "light");
  syncThemeIcon(dark);
});

/* ---------- sidebar / tabs ---------- */
const TAB_TITLES = {
  extraction: "New Extraction",
  hitl: "Validation Queue",
  templates: "Template Registry",
  entities: "Paper Entities",
  history: "History Archive",
};
function openSidebar(open) {
  $("#sidebar").classList.toggle("-translate-x-full", !open);
  $("#sidebar-scrim").classList.toggle("hidden", !open);
}
$("#menu-btn").addEventListener("click", () => openSidebar(true));
$("#sidebar-scrim").addEventListener("click", () => openSidebar(false));

function activateTab(tab) {
  $$("#nav .nav-link").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  $$("[data-pane]").forEach((p) => p.classList.toggle("hidden", p.dataset.pane !== tab));
  $("#page-title").textContent = TAB_TITLES[tab] || "";
  openSidebar(false);
  if (tab === "templates") renderTemplates();
  if (tab === "history") renderHistory();
  if (tab === "hitl") renderQueue();
  if (tab === "entities") renderEntities();
}
$$("#nav .nav-link").forEach((btn) =>
  btn.addEventListener("click", () => activateTab(btn.dataset.tab))
);

/* ---------- template selector + inspector ---------- */
const domainSelect = $("#domain-type");

async function loadTemplateOptions() {
  try {
    const data = await api("/templates");
    domainSelect.innerHTML = '<option value="default">General Academic (AI proposes schema)</option>';
    (data.templates || []).forEach((t) => {
      const opt = document.createElement("option");
      opt.value = t.id;
      opt.textContent = t.name;
      domainSelect.appendChild(opt);
    });
  } catch (e) {
    console.error("templates load failed", e);
  }
}

$("#btn-inspect-template").addEventListener("click", async () => {
  const id = domainSelect.value;
  const body = $("#modal-properties-body");
  $("#modal-template-title").textContent = "Template structure";
  body.innerHTML = "";
  const rows = [];
  if (id === "default") {
    $("#modal-template-title").textContent = "General Academic (default)";
    rows.push(
      ["paper_title", "str", "Title of the scholarly paper."],
      ["authors", "list_str", "Authors of the paper."],
      ["research_problem", "str", "The specific research problem addressed."],
      ["research_method", "str", "The scientific method used."]
    );
  } else {
    try {
      const t = await api(`/templates/${id}`);
      $("#modal-template-title").textContent = t.name;
      (t.properties || []).forEach((p) => rows.push([p.name, p.type, p.description]));
    } catch (e) {
      toast(`Could not load template: ${e.message}`, "error");
      return;
    }
  }
  rows.forEach(([name, type, desc]) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td class="py-2 pr-4 font-medium">${esc(name)}</td>
                    <td class="py-2 pr-4"><code class="text-xs">${esc(type)}</code></td>
                    <td class="py-2 text-slate-500">${esc(desc || "")}</td>`;
    body.appendChild(tr);
  });
  openModal("template-modal");
});

/* ---------- modals ---------- */
function openModal(id) { $(`#${id}`).classList.remove("hidden"); }
function closeModal(id) { $(`#${id}`).classList.add("hidden"); }
$$("[data-close-modal]").forEach((b) =>
  b.addEventListener("click", () => closeModal(b.dataset.closeModal))
);
$$(".modal").forEach((m) =>
  m.addEventListener("click", (e) => { if (e.target === m) m.classList.add("hidden"); })
);

/* ---------- file selection / dropzone ---------- */
const dropzone = $("#dropzone");
const fileInput = $("#file-input");
let selectedFile = null;

dropzone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", (e) => setFile(e.target.files[0]));
["dragover", "dragenter"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.add("dragging"); })
);
["dragleave", "drop"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.remove("dragging"); })
);
dropzone.addEventListener("drop", (e) => setFile(e.dataTransfer.files[0]));

function setFile(file) {
  if (!file) return;
  if (file.type !== "application/pdf") { toast("Please choose a PDF file.", "error"); return; }
  selectedFile = file;
  $("#file-name").textContent = file.name;
  $("#btn-start").disabled = false;
}

/* ---------- pipeline visualization ---------- */
function setPipeline(activeKey, finished = false) {
  const activeIndex = STEP_ORDER.indexOf(activeKey);
  STEP_ORDER.forEach((key, i) => {
    const el = $(`.step[data-step="${key}"]`);
    if (!el) return;
    el.classList.remove("active", "done");
    if (finished || i < activeIndex) el.classList.add("done");
    else if (i === activeIndex) el.classList.add(finished ? "done" : "active");
  });
}
function resetPipeline() {
  STEP_ORDER.forEach((k) => $(`.step[data-step="${k}"]`)?.classList.remove("active", "done"));
}

/* ---------- start extraction ---------- */
$("#btn-start").addEventListener("click", async () => {
  if (!selectedFile) return;
  const docType = $("#doc-type").value;
  const domain = domainSelect.value;

  $("#btn-start").disabled = true;
  hide("#results-card"); hide("#schema-card"); hide("#reco-banner");
  setPipeline(docType === "proceeding" ? "segmenter" : "detector");

  const fd = new FormData();
  fd.append("file", selectedFile);
  fd.append("document_type", docType);
  fd.append("domain", domain);

  try {
    const res = await api("/ingest", { method: "POST", body: fd });
    toast("Paper ingested — processing…", "info");
    pollTask(res.task_id, { docType, domain });
  } catch (e) {
    toast(`Ingestion failed: ${e.message}`, "error");
    $("#btn-start").disabled = false;
    resetPipeline();
  }
});

/* ---------- polling ---------- */
function pollTask(taskId, ctx) {
  const timer = setInterval(async () => {
    let data;
    try { data = await api(`/tasks/${taskId}`); }
    catch (e) { return; } // transient; keep polling

    switch (data.status) {
      case "PENDING_SCHEMA_PROPOSAL":
        setPipeline(ctx.docType === "proceeding" ? "segmenter" : "detector");
        break;
      case "PENDING_SCHEMA_VALIDATION":
        clearInterval(timer);
        setPipeline("detector", false);
        showSchemaCheckpoint(data, taskId, ctx);
        break;
      case "PROCESSING":
      case "PENDING":
      case "STARTED":
        setPipeline("extractor");
        break;
      case "SUCCESS":
        clearInterval(timer);
        setPipeline("synthesizer", true);
        renderResults(data.result, ctx.domain);
        $("#btn-start").disabled = false;
        renderQueue();
        toast("Extraction complete.", "success");
        break;
      case "FAILURE":
        clearInterval(timer);
        toast(`Extraction failed: ${data.error || "unknown error"}`, "error");
        $("#btn-start").disabled = false;
        resetPipeline();
        break;
    }
  }, 2500);
}

/* ---------- HITL schema checkpoint ---------- */
function showSchemaCheckpoint(data, validationTaskId, ctx) {
  const domain = data.domain || ctx.domain;
  buildSchemaForm(data.proposed_properties || [], domain, validationTaskId, ctx);
  show("#schema-card");
  $("#schema-card").scrollIntoView({ behavior: "smooth", block: "start" });
  maybeSuggestExistingTemplate(data.raw_markdown, validationTaskId, ctx);
}

async function maybeSuggestExistingTemplate(rawMarkdown, validationTaskId, ctx) {
  if (!rawMarkdown) return;
  try {
    const r = await api("/recommend-template", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ raw_markdown: rawMarkdown }),
    });
    if (r.decision === "match" && r.matched_template_id) {
      $("#reco-text").innerHTML =
        `<strong>Tip:</strong> this looks like your existing template ` +
        `<code>${esc(r.matched_template_id)}</code>. ${esc(r.rationale || "")}`;
      const actions = $("#reco-actions");
      actions.innerHTML = "";
      const useBtn = document.createElement("button");
      useBtn.className = "btn-primary";
      useBtn.textContent = `Use “${r.matched_template_id}” instead`;
      useBtn.addEventListener("click", () => resumeWithExisting(validationTaskId, r.matched_template_id, ctx));
      actions.appendChild(useBtn);
      show("#reco-banner");
    }
  } catch (_) { /* recommendation is optional */ }
}

async function resumeWithExisting(validationTaskId, templateId, ctx) {
  hide("#reco-banner"); hide("#schema-card");
  setPipeline("extractor");
  try {
    const fd = new FormData();
    fd.append("template_id", templateId);
    const res = await api(`/tasks/${validationTaskId}/resume-with-existing-template`, { method: "POST", body: fd });
    pollTask(res.task_id, { ...ctx, domain: templateId });
    renderQueue();
  } catch (e) {
    toast(`Could not resume: ${e.message}`, "error");
  }
}

function buildSchemaForm(properties, domain, validationTaskId, ctx) {
  const friendly = (domain || "custom")
    .split("-").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
  $("#domain-display-name").value = friendly;

  const list = $("#properties-list");
  list.innerHTML = "";
  (properties.length ? properties : [{ name: "", type: "str", description: "" }])
    .forEach((p) => addPropertyRow(p.name, p.type || "str", p.description));

  // rebind submit/decline cleanly
  const submit = $("#btn-submit-schema");
  submit.replaceWith(submit.cloneNode(true));
  $("#btn-submit-schema").addEventListener("click", () => submitSchema(domain, validationTaskId, friendly, ctx));

  const decline = $("#btn-decline-schema");
  decline.replaceWith(decline.cloneNode(true));
  $("#btn-decline-schema").addEventListener("click", () => declineTask(validationTaskId));
}

function addPropertyRow(name = "", type = "str", description = "") {
  const row = document.createElement("div");
  row.className = "property-row grid grid-cols-[1.2fr_0.8fr_2fr_auto] gap-3 items-center";
  const types = ["str", "int", "list_str", "bool"];
  row.innerHTML = `
    <input class="input prop-name" value="${esc(name)}" placeholder="clinical_outcome" />
    <select class="input prop-type">
      ${types.map((t) => `<option value="${t}" ${t === type ? "selected" : ""}>${t}</option>`).join("")}
    </select>
    <input class="input prop-desc" value="${esc(description)}" placeholder="What the agent should extract" />
    <button class="btn-ghost prop-del" title="Remove">✕</button>`;
  row.querySelector(".prop-del").addEventListener("click", () => row.remove());
  $("#properties-list").appendChild(row);
}
$("#btn-add-property").addEventListener("click", () => addPropertyRow());

async function submitSchema(domain, validationTaskId, friendly, ctx) {
  const props = $$(".property-row").map((r) => ({
    name: $(".prop-name", r).value.trim(),
    type: $(".prop-type", r).value,
    description: $(".prop-desc", r).value.trim(),
  })).filter((p) => p.name);

  if (!props.length) { toast("Add at least one column.", "error"); return; }

  const btn = $("#btn-submit-schema");
  btn.disabled = true; btn.textContent = "Saving & extracting…";
  try {
    const res = await api(`/tasks/${validationTaskId}/validate-schema`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        domain_display_name: $("#domain-display-name").value.trim() || friendly,
        properties: props,
      }),
    });
    hide("#schema-card"); hide("#reco-banner");
    setPipeline("extractor");
    renderQueue();
    pollTask(res.task_id, ctx);
  } catch (e) {
    toast(`Could not save schema: ${e.message}`, "error");
  } finally {
    btn.disabled = false; btn.textContent = "Approve & extract";
  }
}

async function declineTask(validationTaskId) {
  if (!confirm("Decline and delete this validation task? Its temporary segments will be removed.")) return;
  try {
    await api(`/tasks/${validationTaskId}/decline`, { method: "POST" });
    hide("#schema-card"); hide("#reco-banner");
    resetPipeline();
    $("#btn-start").disabled = false;
    renderQueue();
    toast("Validation task declined.", "info");
  } catch (e) {
    toast(`Could not decline: ${e.message}`, "error");
  }
}

/* ---------- results rendering ---------- */
function flattenRow(row) {
  const base = {
    "Paper / Study": row.paper_title,
    "Authors": (row.authors || []).join(", ") || "—",
    "Published": `${row.publication_month || ""} ${row.publication_year || ""}`.trim() || "—",
    "Venue": row.venue || "—",
    "Field": row.research_field || "—",
    "Method": row.research_method || "—",
    "DOI": row.doi || "—",
    "URL": row.url || "—",
  };
  const props = row.domain_specific_properties || {};
  Object.entries(props).forEach(([k, v]) => {
    const header = k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    base[header] = Array.isArray(v) ? v.join(", ") : (v ?? "—");
  });
  return base;
}

function buildTable(rows, markProposed = true) {
  const flat = rows.map(flattenRow);
  const headers = Object.keys(flat[0]);           // data columns (also used for CSV)
  const anyEvidence = rows.some((r) => (r.evidence || []).length);

  const shell = document.createElement("div");
  shell.className = "table-shell overflow-x-auto";
  const table = document.createElement("table");
  table.className = "data-table";

  const thead = document.createElement("thead");
  thead.innerHTML = `<tr>${headers.map((h) => `<th>${esc(h)}</th>`).join("")}${anyEvidence ? "<th>Source</th>" : ""}</tr>`;
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  const colSpan = headers.length + (anyEvidence ? 1 : 0);

  flat.forEach((r, i) => {
    const tr = document.createElement("tr");
    if (markProposed && rows[i].is_proposed_method) tr.className = "proposed";
    tr.innerHTML = headers.map((h) => `<td>${esc(String(r[h]))}</td>`).join("");

    const evidence = rows[i].evidence || [];
    if (anyEvidence) {
      const td = document.createElement("td");
      if (evidence.length) {
        const btn = document.createElement("button");
        btn.className = "btn-ghost text-xs";
        btn.textContent = `🔍 ${evidence.length}`;
        btn.title = "Show source quotes";
        td.appendChild(btn);
        tr.appendChild(td);

        const detail = document.createElement("tr");
        detail.className = "hidden";
        const dtd = document.createElement("td");
        dtd.colSpan = colSpan;
        dtd.className = "bg-slate-50 dark:bg-slate-800/40";
        dtd.innerHTML =
          `<div class="space-y-1 py-1 text-xs text-slate-600 dark:text-slate-300">` +
          evidence.map((e) =>
            `<div><span class="font-semibold">${esc(e.field)}</span>: <span class="italic">“${esc(e.quote)}”</span></div>`
          ).join("") + `</div>`;
        detail.appendChild(dtd);

        btn.addEventListener("click", () => detail.classList.toggle("hidden"));
        tbody.appendChild(tr);
        tbody.appendChild(detail);
        return;
      }
      tr.appendChild(td); // empty source cell
    }
    tbody.appendChild(tr);
  });

  table.appendChild(tbody);
  shell.appendChild(table);
  return { shell, headers, flat };
}

function toCSV(headers, flat) {
  const lines = [headers.join(",")];
  flat.forEach((r) => lines.push(headers.map((h) => `"${String(r[h]).replace(/"/g, '""')}"`).join(",")));
  return lines.join("\n");
}
function downloadCSV(csv, filename) {
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8;" }));
  const a = document.createElement("a");
  a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}

function renderResults(result, domain) {
  const payload = result?.consolidated_result || result || {};
  const tables = payload.tables || [];
  const body = $("#results-body");
  body.innerHTML = "";
  show("#results-card");
  const dl = $("#btn-download-csv");
  dl.classList.add("hidden");

  if (!tables.length) {
    $("#results-title").textContent = "No rows extracted";
    body.innerHTML = `<p class="text-sm text-slate-500">The pipeline finished but produced no comparison rows.</p>`;
    return;
  }

  if (payload.document_type === "proceeding") {
    $("#results-title").textContent = `Proceeding · ${tables.length} paper table(s)`;
    tables.forEach((t, i) => {
      const { shell, headers, flat } = buildTable(t.rows);
      const card = document.createElement("div");
      card.className = "table-shell mb-3 overflow-hidden";
      const head = document.createElement("div");
      head.className = "accordion-head";
      head.innerHTML = `<span>Paper ${i + 1}: ${esc(t.research_problem || "Untitled")}</span><span class="chev">▾</span>`;
      const content = document.createElement("div");
      content.className = "hidden p-3";
      content.appendChild(shell);
      const dlBtn = document.createElement("button");
      dlBtn.className = "btn-success mt-3";
      dlBtn.textContent = "Download segment CSV";
      dlBtn.addEventListener("click", () => downloadCSV(toCSV(headers, flat), `segment_${i + 1}.csv`));
      content.appendChild(dlBtn);
      head.addEventListener("click", () => {
        content.classList.toggle("hidden");
        head.querySelector(".chev").textContent = content.classList.contains("hidden") ? "▾" : "▴";
      });
      card.appendChild(head); card.appendChild(content);
      body.appendChild(card);
    });
  } else {
    const t = tables[0];
    $("#results-title").textContent = t.research_problem || "Comparison table";
    const { shell, headers, flat } = buildTable(t.rows);
    body.appendChild(shell);
    dl.classList.remove("hidden");
    dl.replaceWith(dl.cloneNode(true));
    $("#btn-download-csv").classList.remove("hidden");
    $("#btn-download-csv").addEventListener("click", () => downloadCSV(toCSV(headers, flat), "comparison_table.csv"));
  }
}

/* ---------- validation queue ---------- */
async function renderQueue() {
  const container = $("#hitl-queue");
  const badge = $("#hitl-badge");
  try {
    const data = await api("/validation-tasks");
    const tasks = data.tasks || [];
    badge.textContent = tasks.length;
    badge.classList.toggle("hidden", tasks.length === 0);
    container.innerHTML = "";
    if (!tasks.length) {
      container.innerHTML = `<div class="card text-center text-sm text-slate-500">Queue is empty — all schemas verified.</div>`;
      return;
    }
    tasks.forEach((t) => {
      const card = document.createElement("div");
      card.className = "card flex flex-wrap items-center justify-between gap-3";
      card.innerHTML = `
        <div>
          <p class="text-sm font-semibold text-slate-900 dark:text-white">Domain: <code>${esc(t.domain || "—")}</code></p>
          <p class="text-xs text-slate-400">${new Date(t.created_at).toLocaleString()}</p>
        </div>`;
      const actions = document.createElement("div");
      actions.className = "flex gap-2";
      const solve = document.createElement("button");
      solve.className = "btn-primary"; solve.textContent = "Solve schema";
      solve.addEventListener("click", () => solveQueued(t.task_id, t.domain));
      const refuse = document.createElement("button");
      refuse.className = "btn-danger"; refuse.textContent = "Refuse";
      refuse.addEventListener("click", () => declineTask(t.task_id).then(renderQueue));
      actions.append(solve, refuse);
      card.appendChild(actions);
      container.appendChild(card);
    });
  } catch (e) {
    container.innerHTML = `<div class="card text-sm text-rose-500">Could not load queue: ${esc(e.message)}</div>`;
  }
}

async function solveQueued(taskId, domain) {
  try {
    const data = await api(`/tasks/${taskId}`);
    activateTab("extraction");
    buildSchemaForm(data.proposed_properties || [], data.domain || domain, taskId, { docType: "single", domain: data.domain || domain });
    show("#schema-card");
    $("#schema-card").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    toast(`Could not open task: ${e.message}`, "error");
  }
}

/* ---------- template registry ---------- */
async function renderTemplates() {
  const grid = $("#templates-grid");
  grid.innerHTML = `<p class="text-sm text-slate-400">Loading…</p>`;
  try {
    const data = await api("/templates");
    const templates = data.templates || [];
    grid.innerHTML = "";
    if (!templates.length) {
      grid.innerHTML = `<div class="card text-sm text-slate-500">No templates yet. Ingest a paper with “General Academic” to create one.</div>`;
      return;
    }
    templates.forEach((t) => {
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = `
        <h3 class="text-sm font-semibold text-slate-900 dark:text-white">${esc(t.name)}</h3>
        <p class="mb-3 text-xs text-slate-400">ID: <code>${esc(t.id)}</code></p>
        <ul class="space-y-1 text-xs text-slate-500">
          ${(t.properties || []).map((p) => `<li><span class="font-medium text-slate-700 dark:text-slate-300">${esc(p.name)}</span> · ${esc(p.description || "")}</li>`).join("")}
        </ul>`;
      grid.appendChild(card);
    });
  } catch (e) {
    grid.innerHTML = `<div class="card text-sm text-rose-500">Could not load templates: ${esc(e.message)}</div>`;
  }
}

/* ---------- paper entities (cross-paper resolution) ---------- */
async function renderEntities() {
  const grid = $("#entities-grid");
  grid.innerHTML = `<p class="text-sm text-slate-400">Loading…</p>`;
  try {
    const data = await api("/entities");
    const entities = data.entities || [];
    grid.innerHTML = "";
    if (!entities.length) {
      grid.innerHTML = `<div class="card text-sm text-slate-500">No papers yet. Run an extraction — papers and their baselines will be de-duplicated here.</div>`;
      return;
    }
    entities.forEach((e) => {
      const card = document.createElement("div");
      card.className = "card cursor-pointer transition hover:border-teal-400";
      const multi = e.mention_count > 1;
      card.innerHTML = `
        <div class="mb-2 flex items-start justify-between gap-2">
          <h3 class="text-sm font-semibold text-slate-900 dark:text-white">${esc(e.canonical_title)}</h3>
          <span class="shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${multi ? "bg-teal-100 text-teal-700 dark:bg-teal-900/50 dark:text-teal-300" : "bg-slate-100 text-slate-500 dark:bg-slate-800"}">
            ${e.mention_count}×
          </span>
        </div>
        <p class="text-xs text-slate-500">${esc((e.authors || []).join(", ") || "Authors unknown")}</p>
        ${e.doi ? `<p class="mt-1 text-xs text-slate-400">DOI: <code>${esc(e.doi)}</code></p>` : ""}
        ${multi ? `<p class="mt-2 text-xs font-medium text-teal-600">Cited across ${e.mention_count} tables →</p>` : `<p class="mt-2 text-xs text-slate-400">Appears once →</p>`}`;
      card.addEventListener("click", () => openEntity(e.id));
      grid.appendChild(card);
    });
  } catch (err) {
    grid.innerHTML = `<div class="card text-sm text-rose-500">Could not load entities: ${esc(err.message)}</div>`;
  }
}

async function openEntity(id) {
  try {
    const e = await api(`/entities/${id}`);
    $("#modal-entity-title").textContent = e.canonical_title;
    $("#modal-entity-meta").innerHTML =
      `${esc((e.authors || []).join(", ") || "Authors unknown")}` +
      (e.doi ? ` · DOI <code>${esc(e.doi)}</code>` : "") +
      ` · referenced <span class="font-semibold text-teal-600">${e.mention_count}×</span>`;
    const box = $("#modal-entity-mentions");
    box.innerHTML = "";
    (e.mentions || []).forEach((m) => {
      const row = document.createElement("button");
      row.className = "table-shell flex w-full items-center justify-between gap-3 p-3 text-left hover:border-teal-400";
      row.innerHTML = `
        <div>
          <p class="text-sm font-medium text-slate-800 dark:text-slate-200">${esc(m.research_problem)}</p>
          <p class="text-xs text-slate-400">as “${esc(m.paper_title)}” · ${esc(m.domain)}</p>
        </div>
        <span class="shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${m.is_proposed_method ? "bg-teal-100 text-teal-700 dark:bg-teal-900/50 dark:text-teal-300" : "bg-slate-100 text-slate-500 dark:bg-slate-800"}">
          ${m.is_proposed_method ? "proposed" : "baseline"}
        </span>`;
      row.addEventListener("click", () => { closeModal("entity-modal"); openHistory(m.table_id); });
      box.appendChild(row);
    });
    openModal("entity-modal");
  } catch (err) {
    toast(`Could not open entity: ${err.message}`, "error");
  }
}

/* ---------- history ---------- */
async function renderHistory() {
  const body = $("#history-body");
  body.innerHTML = `<tr><td class="px-4 py-4 text-sm text-slate-400" colspan="5">Loading…</td></tr>`;
  try {
    const data = await api("/comparisons");
    const items = data.comparisons || [];
    body.innerHTML = "";
    if (!items.length) {
      body.innerHTML = `<tr><td class="px-4 py-4 text-sm text-slate-500" colspan="5">No extractions yet.</td></tr>`;
      return;
    }
    items.forEach((c) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="px-4 py-3 text-slate-500">${new Date(c.created_at).toLocaleString()}</td>
        <td class="px-4 py-3 font-medium text-slate-800 dark:text-slate-200">${esc(c.research_problem)}</td>
        <td class="px-4 py-3"><span class="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">${esc(c.domain)}</span></td>
        <td class="px-4 py-3 text-slate-500">${c.rows_count}</td>`;
      const td = document.createElement("td");
      td.className = "px-4 py-3";
      const view = document.createElement("button");
      view.className = "btn-ghost text-xs"; view.textContent = "View";
      view.addEventListener("click", () => openHistory(c.id));
      td.appendChild(view);
      tr.appendChild(td);
      body.appendChild(tr);
    });
  } catch (e) {
    body.innerHTML = `<tr><td class="px-4 py-4 text-sm text-rose-500" colspan="5">Could not load history: ${esc(e.message)}</td></tr>`;
  }
}

async function openHistory(tableId) {
  try {
    const data = await api(`/comparisons/${tableId}`);
    const payload = data.consolidated_result || data;
    const t = (payload.tables || [])[0];
    if (!t) { toast("Empty table.", "error"); return; }
    $("#modal-history-title").textContent = t.research_problem || "Comparison table";
    const { shell, headers, flat } = buildTable(t.rows);
    const container = $("#modal-history-container");
    container.innerHTML = "";
    container.appendChild(shell);
    const dl = $("#btn-download-history-csv");
    dl.replaceWith(dl.cloneNode(true));
    $("#btn-download-history-csv").addEventListener("click", () => downloadCSV(toCSV(headers, flat), "comparison_table.csv"));
    openModal("history-modal");
  } catch (e) {
    toast(`Could not open table: ${e.message}`, "error");
  }
}

/* ---------- small utilities ---------- */
function show(sel) { $(sel).classList.remove("hidden"); }
function hide(sel) { $(sel).classList.add("hidden"); }
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/* ---------- boot ---------- */
window.addEventListener("DOMContentLoaded", () => {
  loadTemplateOptions();
  renderQueue();
});
