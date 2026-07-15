// app/static/app.js (Version Finale de Production Unifiée)
const API_BASE_URL = "/api/v1";

// ---------------------------------------------------------------------------
// 1. GESTION DES ONGLETS DE LA SIDEBAR
// ---------------------------------------------------------------------------
const tabLinks = document.querySelectorAll(".nav-link");
const tabPanes = document.querySelectorAll(".tab-pane");

tabLinks.forEach(link => {
    link.addEventListener("click", () => {
        tabLinks.forEach(l => l.classList.remove("active"));
        tabPanes.forEach(p => p.classList.remove("active"));
        
        link.classList.add("active");
        const activeTabId = `tab-${link.getAttribute("data-tab")}`;
        const targetPane = document.getElementById(activeTabId);
        if (targetPane) {
            targetPane.classList.add("active");
        }
        
        const tabKey = link.getAttribute("data-tab");
        if (tabKey === "templates") fetchAndRenderTemplates();
        if (tabKey === "history") fetchAndRenderHistory();
        if (tabKey === "hitl") fetchAndRenderValidationQueue();
    });
});

// Éléments du sélecteur
const docTypeSelect = document.getElementById("doc-type");
const domainTypeSelect = document.getElementById("domain-type");

// Éléments du formulaire d'inspection
const btnInspectTemplate = document.getElementById("btn-inspect-template");
const templateModal = document.getElementById("template-modal");
const btnCloseModal = document.getElementById("btn-close-modal");
const modalPropertiesBody = document.getElementById("modal-properties-body");
const modalTemplateTitle = document.getElementById("modal-template-title");

// Éléments du MODAL D'HISTORIQUE [3]
const historyModal = document.getElementById("history-modal");
const btnCloseHistoryModal = document.getElementById("btn-close-history-modal");
const modalHistoryHeaders = document.getElementById("modal-history-headers");
const modalHistoryBody = document.getElementById("modal-history-body");
const modalHistoryTitle = document.getElementById("modal-history-title");
const btnDownloadHistoryCsv = document.getElementById("btn-download-history-csv");

let historyCsvData = "";

// Fermeture de la modale d'historique
btnCloseHistoryModal.addEventListener("click", () => {
    historyModal.classList.add("hidden");
});

// Éléments de recommandation
const recommendationCard = document.getElementById("recommendation-card");
const recommendationText = document.getElementById("recommendation-text");
const recommendationActions = document.getElementById("recommendation-actions");

let parsedMarkdownCache = "";
let cachedProposedProperties = [];

// ---------------------------------------------------------------------------
// 2. PEUPLER DYNAMIQUEMENT LE SÉLECTEUR DE DOMAINES (DEPUIS POSTGRESQL)
// ---------------------------------------------------------------------------
async function populateDomainSelector() {
    try {
        const response = await fetch(`${API_BASE_URL}/templates`);
        if (response.ok) {
            const data = await response.json();
            domainTypeSelect.innerHTML = '<option value="default">General Academic (Default)</option>';
            data.templates.forEach(t => {
                const opt = document.createElement("option");
                opt.value = t.id;
                opt.textContent = t.name;
                domainTypeSelect.appendChild(opt);
            });
        }
    } catch (e) {
        console.error("Failed to load templates registry:", e);
    }
}

// ---------------------------------------------------------------------------
// 3. INSPECTEUR DE STRUCTURES DE TEMPLATES (MODAL)
// ---------------------------------------------------------------------------
btnInspectTemplate.addEventListener("click", async () => {
    const selectedTemplateId = domainTypeSelect.value;
    templateModal.classList.remove("hidden");
    modalPropertiesBody.innerHTML = "<tr><td colspan='3'>Loading template metadata...</td></tr>";
    
    if (selectedTemplateId === "default") {
        modalTemplateTitle.textContent = "📋 Template Structure: General Academic";
        modalPropertiesBody.innerHTML = `
            <tr><td><strong>paper_title</strong></td><td>str</td><td>Title of the scholarly paper.</td></tr>
            <tr><td><strong>authors</strong></td><td>list_str</td><td>Authors of the paper.</td></tr>
            <tr><td><strong>research_problem</strong></td><td>str</td><td>The specific research problem addressed.</td></tr>
            <tr><td><strong>research_method</strong></td><td>str</td><td>The scientific method used.</td></tr>
        `;
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/templates/${selectedTemplateId}`);
        if (response.ok) {
            const data = await response.json();
            modalTemplateTitle.textContent = `📋 Template Structure: ${data.name}`;
            modalPropertiesBody.innerHTML = "";
            data.properties.forEach(p => {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td><strong>${p.name}</strong></td>
                    <td><span class="badge" style="background-color:#e2e8f0; color:#475569;">${p.type}</span></td>
                    <td>${p.description}</td>
                `;
                modalPropertiesBody.appendChild(tr);
            });
        }
    } catch (e) {
        modalPropertiesBody.innerHTML = `<tr><td colspan='3' style='color:var(--primary-color);'>Error: ${e.message}</td></tr>`;
    }
});

btnCloseModal.addEventListener("click", () => templateModal.classList.add("hidden"));

// ---------------------------------------------------------------------------
// 4. RECOMMANDATION AUTOMATIQUE DE TEMPLATES
// ---------------------------------------------------------------------------
async function triggerAIRecommendation(markdownText, taskId) {
    recommendationCard.classList.remove("hidden");
    recommendationText.innerHTML = "<em>Analyzing abstract and scanning database templates...</em>";
    recommendationActions.innerHTML = "";

    try {
        const response = await fetch(`${API_BASE_URL}/recommend-template`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ raw_markdown: markdownText })
        });

        if (response.ok) {
            const r = await response.json();
            recommendationText.innerHTML = `<strong>Analysis Results:</strong><br>${r.rationale}`;

            if (r.decision === "match") {
                recommendationActions.innerHTML = `
                    <button class="btn btn-success" style="width:auto;" onclick="window.acceptMatchRecommendation('${r.matched_template_id}', '${taskId}')">✅ Use Recommended Template (${r.matched_template_id})</button>
                    <button class="btn btn-secondary" style="width:auto;" onclick="window.revealCustomSchemaForm('${taskId}', '${r.proposed_domain_key}')">❌ No, Create Custom Template</button>
                `;
            } else {
                recommendationActions.innerHTML = `
                    <button class="btn btn-primary" style="width:auto;" onclick="window.revealCustomSchemaForm('${taskId}', '${r.proposed_domain_key}')">🛠️ Create & Validate New Schema (${r.proposed_domain_name})</button>
                `;
                renderSchemaValidationForm(r.proposed_properties, r.proposed_domain_key, taskId);
            }
        }
    } catch (e) {
        recommendationText.textContent = `Could not generate recommendation: ${e.message}`;
    }
}

window.acceptMatchRecommendation = async function(templateId, taskId) {
    recommendationCard.classList.add("hidden");
    updateAgentState("extractor", "active");

    const formData = new FormData();
    formData.append("template_id", templateId);

    try {
        const response = await fetch(`${API_BASE_URL}/tasks/${taskId}/resume-with-existing-template`, {
            method: "POST",
            body: formData
        });

        if (response.ok) {
            const responseData = await response.json();
            pollTaskStatus(responseData.task_id, templateId, docTypeSelect.value);
            fetchAndRenderValidationQueue();
        } else {
            alert("Failed to resume extraction using the recommended template.");
            updateAgentState(null);
            btnStart.disabled = false;
        }
    } catch (e) {
        alert(`Network failure: ${e.message}`);
        updateAgentState(null);
        btnStart.disabled = false;
    }
};

window.acceptNewSchemaRecommendation = function(domainKey, domainName, properties, taskId) {
    recommendationCard.classList.add("hidden");
    domainTypeSelect.value = "default";
    renderSchemaValidationForm(properties, domainKey, taskId);
    
    const submitBtn = document.getElementById("btn-submit-schema");
    submitBtn.textContent = "🚀 Approve & Register Schema in Database";
};

// ---------------------------------------------------------------------------
// 5. INGESTION ET EXÉCUTION
// ---------------------------------------------------------------------------
const dropzone = document.getElementById("pdf-dropzone");
const fileInput = document.getElementById("file-input");
const fileNameDisplay = document.getElementById("selected-file-name");
const btnStart = document.getElementById("btn-start");

const resultsCard = document.getElementById("results-card");
const tableTitle = document.getElementById("table-title");
const tableHeaders = document.getElementById("table-headers");
const tableBody = document.getElementById("table-body");
const btnDownloadCsv = document.getElementById("btn-download-csv");

let selectedFile = null;
let extractedCsvData = "";

dropzone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", (e) => handleFileSelect(e.target.files[0]));

function handleFileSelect(file) {
    if (file && file.type === "application/pdf") {
        selectedFile = file;
        fileNameDisplay.textContent = `Selected File: ${file.name}`;
        btnStart.disabled = false;
    }
}

const flowNodes = {
    classifier: document.getElementById("node-classifier"),
    segmenter: document.getElementById("node-segmenter"),
    detector: document.getElementById("node-detector"),
    extractor: document.getElementById("node-extractor"),
    synthesizer: document.getElementById("node-synthesizer")
};

function updateAgentState(activeNodeKey, state = "active") {
    const keys = Object.keys(flowNodes);
    const activeIndex = keys.indexOf(activeNodeKey);

    keys.forEach((key, index) => {
        const nodeElement = flowNodes[key];
        if (!nodeElement) return;

        nodeElement.classList.remove("active", "completed");

        if (state === "active") {
            if (index < activeIndex) {
                nodeElement.classList.add("completed");
            } else if (index === activeIndex) {
                nodeElement.classList.add("active");
            }
        } else if (state === "completed") {
            if (index <= activeIndex) {
                nodeElement.classList.add("completed");
            }
        }
    });
}

domainTypeSelect.addEventListener("change", () => {
    if (domainTypeSelect.value !== "default") {
        recommendationCard.classList.add("hidden");
    }
});

btnStart.addEventListener("click", async () => {
    if (!selectedFile) return;

    btnStart.disabled = true;
    resultsCard.classList.add("hidden");
    document.getElementById("schema-card").classList.add("hidden");
    
    const selectedType = docTypeSelect.value;
    if (selectedType === "single") {
        updateAgentState("detector", "active");
    } else {
        updateAgentState("segmenter", "active");
    }

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("document_type", selectedType);
    formData.append("domain", domainTypeSelect.value);

    try {
        const response = await fetch(`${API_BASE_URL}/ingest`, {
            method: "POST",
            body: formData
        });
        
        if (response.ok) {
            const data = await response.json();
            pollTaskStatus(data.task_id, domainTypeSelect.value, selectedType);
        } else {
            const errText = await response.text();
            throw new Error(errText);
        }
    } catch (e) {
        alert(`Ingestion error: ${e.message}`);
        btnStart.disabled = false;
        updateAgentState(null);
    }
});

function pollTaskStatus(taskId, domain, docType = "single") {
    const interval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/tasks/${taskId}`);
            if (response.ok) {
                const data = await response.json();
                
                if (data.status === "PENDING_SCHEMA_PROPOSAL") {
                    if (docType === "proceeding") {
                        updateAgentState("segmenter", "active");
                    } else {
                        updateAgentState("detector", "active");
                    }
                }
                else if (data.status === "PENDING_SCHEMA_VALIDATION") {
                    clearInterval(interval);
                    updateAgentState("detector", "completed");
                    
                    const targetDomain = data.domain || domain;
                    cachedProposedProperties = data.proposed_properties;
                    renderSchemaValidationForm(data.proposed_properties, targetDomain, taskId);
                }
                else if (data.status === "PROCESSING") {
                    updateAgentState("extractor", "active");
                }
                else if (data.status === "SUCCESS") {
                    clearInterval(interval);
                    updateAgentState("synthesizer", "completed");
                    renderResults(data.result, domain);
                    btnStart.disabled = false;
                    fetchAndRenderValidationQueue();
                }
                else if (data.status === "FAILURE") {
                    clearInterval(interval);
                    alert(`Extraction failed: ${data.error}`);
                    btnStart.disabled = false;
                    updateAgentState(null);
                }
            }
        } catch (error) {
            console.error("Polling transaction failed:", error);
        }
    }, 3000);
}

// ---------------------------------------------------------------------------
// 5. RENDU SÉPARÉ PAR ACCORDÉON POUR LES PROCEEDINGS ET HORIZONTAL POUR LES PAPIERS SIMPLES
// ---------------------------------------------------------------------------
function flattenRow(row, domain) {
    const base = {
        "Paper Title/Study": row.paper_title,
        "Authors": (row.authors || []).join(", ") || "Unknown",
        "Publication Date": `${row.publication_month || ''} ${row.publication_year || ''}`.trim() || "N/A",
        "Venue": row.venue || "N/A",
        "Research Field": row.research_field || "N/A",
        "Methodology": row.research_method || "N/A",
        "DOI": row.doi || "N/A",
        "URL": row.url || "N/A"
    };

    const properties = row.domain_specific_properties || {};
    Object.entries(properties).forEach(([key, val]) => {
        const cleanHeader = key.replace("_", " ").split(" ").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
        base[cleanHeader] = Array.isArray(val) ? val.join(", ") : (val || "N/A");
    });

    return base;
}

function renderResults(result, domain) {
    resultsCard.classList.remove("hidden");
    
    const resultsContainer = document.getElementById("results-card");
    const resultsHeader = resultsContainer.querySelector(".results-header");
    resultsContainer.innerHTML = "";
    resultsContainer.appendChild(resultsHeader);

    const payload = result.consolidated_result || result;
    const tables = payload.tables || [];

    if (tables.length === 0) {
        tableTitle.textContent = "📋 Comparative Matrix (Empty)";
        return;
    }

    const isProceeding = payload.document_type === "proceeding";

    if (isProceeding) {
        tableTitle.textContent = "📋 Proceeding Chunk Comparative Matrices";
        btnDownloadCsv.classList.add("hidden");
        
        tables.forEach((table, index) => {
            const chunkCard = document.createElement("div");
            chunkCard.className = "proceeding-chunk-card";
            
            chunkCard.innerHTML = `
                <div class="chunk-header">
                    <span>Paper Segment ${index + 1}: ${table.research_problem}</span>
                    <span class="chevron">▼</span>
                </div>
                <div class="chunk-content hidden">
                    <div class="table-wrapper">
                        <table class="data-table">
                            <thead><tr class="chunk-headers"></tr></thead>
                            <tbody class="chunk-body"></tbody>
                        </table>
                    </div>
                    <button class="btn btn-success btn-download-chunk-csv" style="margin-top:1rem; width:auto;">📥 Download Segment CSV</button>
                </div>
            `;
            
            const header = chunkCard.querySelector(".chunk-header");
            const content = chunkCard.querySelector(".chunk-content");
            const chevron = chunkCard.querySelector(".chevron");
            header.addEventListener("click", () => {
                const isHidden = content.classList.contains("hidden");
                if (isHidden) {
                    content.classList.remove("hidden");
                    chevron.textContent = "▲";
                } else {
                    content.classList.add("hidden");
                    chevron.textContent = "▼";
                }
            });

            const rowsToRender = table.rows.map(row => flattenRow(row, domain));
            const headers = Object.keys(rowsToRender[0]);
            
            const headerRow = chunkCard.querySelector(".chunk-headers");
            headers.forEach(h => {
                const th = document.createElement("th");
                th.textContent = h;
                headerRow.appendChild(th);
            });
            
            const bodyRow = chunkCard.querySelector(".chunk-body");
            rowsToRender.forEach(row => {
                const tr = document.createElement("tr");
                headers.forEach(h => {
                    const td = document.createElement("td");
                    td.textContent = row[h];
                    tr.appendChild(td);
                });
                bodyRow.appendChild(tr);
            });

            const btnDownloadChunk = chunkCard.querySelector(".btn-download-chunk-csv");
            btnDownloadChunk.addEventListener("click", () => {
                const csvRows = [headers.join(",")];
                rowsToRender.forEach(row => {
                    const values = headers.map(h => `"${String(row[h]).replace(/"/g, '""')}"`);
                    csvRows.push(values.join(","));
                });
                const blob = new Blob([csvRows.join("\n")], { type: "text/csv;charset=utf-8;" });
                const url = URL.createObjectURL(blob);
                const link = document.createElement("a");
                link.setAttribute("href", url);
                link.setAttribute("download", `segment_${index+1}_${table.research_problem.substring(0,20).replace(/\s/g, '_')}.csv`);
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            });

            resultsContainer.appendChild(chunkCard);
        });
    } else {
        btnDownloadCsv.classList.remove("hidden");
        const table = tables[0];
        tableTitle.textContent = `📋 Comparative Matrix: ${table.research_problem}`;
        
        const wrapper = document.createElement("div");
        wrapper.className = "table-wrapper";
        wrapper.innerHTML = `
            <table class="data-table" id="results-table">
                <thead><tr id="table-headers"></tr></thead>
                <tbody id="table-body"></tbody>
            </table>
        `;
        resultsContainer.appendChild(wrapper);
        
        const rowsToRender = table.rows.map(row => flattenRow(row, domain));
        const headers = Object.keys(rowsToRender[0]);
        
        const headerContainer = document.getElementById("table-headers");
        headers.forEach(h => {
            const th = document.createElement("th");
            th.textContent = h;
            headerContainer.appendChild(th);
        });
        
        const bodyContainer = document.getElementById("table-body");
        rowsToRender.forEach(row => {
            const tr = document.createElement("tr");
            headers.forEach(h => {
                const td = document.createElement("td");
                td.textContent = row[h];
                tr.appendChild(td);
            });
            bodyContainer.appendChild(tr);
        });

        const csvRows = [headers.join(",")];
        rowsToRender.forEach(row => {
            const values = headers.map(h => `"${String(row[h]).replace(/"/g, '""')}"`);
            csvRows.push(values.join(","));
        });
        extractedCsvData = csvRows.join("\n");
    }
}

// ---------------------------------------------------------------------------
// 6. FORMULAIRE DE CONCEPTION D'ONTOLOGIES (HITL)
// ---------------------------------------------------------------------------
const schemaCard = document.getElementById("schema-card");
const propertiesList = document.getElementById("properties-list");
const btnAddProperty = document.getElementById("btn-add-property");

btnAddProperty.addEventListener("click", () => addPropertyRow("", "str", ""));

function renderSchemaValidationForm(proposedProperties, domainName, validationTaskId) {
    schemaCard.classList.remove("hidden");
    propertiesList.innerHTML = "";
    
    const friendlyName = domainName
        .split("-")
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");
    document.getElementById("domain-display-name").value = friendlyName;

    proposedProperties.forEach(prop => {
        addPropertyRow(prop.name, prop.type || "str", prop.description);
    });

    const submitBtn = document.getElementById("btn-submit-schema");
    const newSubmitBtn = submitBtn.cloneNode(true);
    submitBtn.parentNode.replaceChild(newSubmitBtn, submitBtn);

    newSubmitBtn.addEventListener("click", async () => {
        const rows = propertiesList.querySelectorAll(".property-row");
        const validatedProperties = [];
        
        rows.forEach(row => {
            const name = row.querySelector(".prop-name").value.trim();
            const type = row.querySelector(".prop-type").value;
            const desc = row.querySelector(".prop-desc").value.trim();
            
            if (name) {
                validatedProperties.push({ name, type, description: desc });
            }
        });

        if (validatedProperties.length === 0) {
            alert("Please define at least one comparative property.");
            return;
        }

        const payload = {
            domain_display_name: document.getElementById("domain-display-name").value.trim() || friendlyName,
            properties: validatedProperties
        };

        newSubmitBtn.disabled = true;
        newSubmitBtn.textContent = "Saving Schema & Starting Data Extraction...";

        try {
            const response = await fetch(`${API_BASE_URL}/tasks/${validationTaskId}/validate-schema`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                const responseData = await response.json();
                schemaCard.classList.add("hidden");
                
                // ACTUALISATION TRANSACTIONNELLE IMMÉDIATE
                fetchAndRenderValidationQueue();
                
                const statusCard = document.getElementById("status-card");
                if (statusCard) statusCard.classList.remove("hidden");
                
                pollTaskStatus(responseData.task_id, domainName, docTypeSelect.value);
            } else {
                const errText = await response.text();
                alert(`Error submitting template: ${errText}`);
                newSubmitBtn.disabled = false;
                newSubmitBtn.textContent = "🚀 Approve Schema & Resume Process";
            }
        } catch (e) {
            alert(`Network failure: ${e.message}`);
            newSubmitBtn.disabled = false;
        }
    });

    // Événement d'annulation du schéma
    const declineBtn = document.getElementById("btn-decline-schema");
    const newDeclineBtn = declineBtn.cloneNode(true);
    declineBtn.parentNode.replaceChild(newDeclineBtn, declineBtn);

    newDeclineBtn.addEventListener("click", () => {
        window.declineHITLTask(validationTaskId);
    });
}

function addPropertyRow(name = "", type = "str", description = "") {
    const row = document.createElement("div");
    row.className = "property-row";
    
    row.innerHTML = `
        <input type="text" class="prop-name" value="${name}" placeholder="e.g., clinical_outcome">
        <select class="prop-type">
            <option value="str" ${type === "str" ? "selected" : ""}>String (text)</option>
            <option value="int" ${type === "int" ? "selected" : ""}>Integer (number)</option>
            <option value="list_str" ${type === "list_str" ? "selected" : ""}>Array (list)</option>
            <option value="bool" ${type === "bool" ? "selected" : ""}>Boolean (yes/no)</option>
        </select>
        <input type="text" class="prop-desc" value="${description}" placeholder="The therapeutic result observed">
        <button class="btn-delete-prop" type="button">❌</button>
    `;

    row.querySelector(".btn-delete-prop").addEventListener("click", () => row.remove());
    propertiesList.appendChild(row);
}

// ---------------------------------------------------------------------------
// 8. LOGIQUE GLOBALE DE REFUS ET DE NETTOYAGE TRANSACTIONNEL DE LA QUEUE
// ---------------------------------------------------------------------------
window.declineHITLTask = async function(taskId) {
    if (confirm("Are you sure you want to decline and delete this validation task? All associated temporary segments will be permanently removed.")) {
        try {
            const response = await fetch(`${API_BASE_URL}/tasks/${taskId}/decline`, {
                method: "POST"
            });
            if (response.ok) {
                alert("Validation task declined and successfully deleted.");
                
                schemaCard.classList.add("hidden");
                resultsCard.classList.add("hidden");
                btnStart.disabled = false;
                updateAgentState(null);
                
                fetchAndRenderValidationQueue();
            } else {
                alert("Failed to decline the validation task.");
            }
        } catch (e) {
            alert(`Network error: ${e.message}`);
        }
    }
};

// ---------------------------------------------------------------------------
// 9. RENDU DES PANNEAUX SECONDAIRES DEPUIS LA BASE DE DONNÉES (POSTGRESQL)
// ---------------------------------------------------------------------------

// A. Rendu du registre d'Ontologies
async function fetchAndRenderTemplates() {
    const container = document.getElementById("templates-grid-container");
    container.innerHTML = "<p style='color:var(--text-muted);'>Querying PostgreSQL Template Registry...</p>";
    try {
        const response = await fetch(`${API_BASE_URL}/templates`);
        if (response.ok) {
            const data = await response.json();
            container.innerHTML = "";
            data.templates.forEach(t => {
                const card = document.createElement("div");
                card.className = "template-card";
                card.innerHTML = `
                    <h3>📋 ${t.name}</h3>
                    <p style="font-size:0.7rem; color:var(--text-muted); margin-bottom:0.75rem;">DB Schema ID: <code>${t.id}</code></p>
                    <ul class="properties-list-mini">
                        ${t.properties.map(p => `<li><strong>${p.name}</strong>: ${p.description} (<em>${p.type}</em>)</li>`).join("")}
                    </ul>
                `;
                container.appendChild(card);
            });
        }
    } catch (e) {
        container.innerHTML = `<p style="color:var(--primary-color);">Database read error: ${e.message}</p>`;
    }
}

// B. Rendu de l'historique d'extraction
async function fetchAndRenderHistory() {
    const body = document.getElementById("history-table-body");
    body.innerHTML = "<tr><td colspan='5' style='color:var(--text-muted);'>Querying PostgreSQL comparative history...</td></tr>";
    try {
        const response = await fetch(`${API_BASE_URL}/comparisons`);
        if (response.ok) {
            const data = await response.json();
            body.innerHTML = "";
            data.comparisons.forEach(c => {
                const tr = document.createElement("tr");
                const date = new Date(c.created_at).toLocaleString();
                tr.innerHTML = `
                    <td>${date}</td>
                    <td><strong>${c.research_problem}</strong></td>
                    <td><span class="badge" style="background-color:var(--accent-color);">${c.domain}</span></td>
                    <td>${c.rows_count} items</td>
                    <td><button class="btn btn-primary btn-view-history" style="padding:0.25rem 0.75rem; font-size:0.75rem;">👁️ View Table</button></td>
                `;
                
                tr.querySelector(".btn-view-history").addEventListener("click", () => {
                    loadHistoryTable(c.id);
                });
                
                body.appendChild(tr);
            });
        }
    } catch (e) {
        body.innerHTML = `<tr><td colspan='5' style="color:var(--primary-color);">Error reading history: ${e.message}</td></tr>`;
    }
}

// C. Rendu du modal d'historique consolidé [3]
function renderHistoryModalTable(result) {
    modalHistoryHeaders.innerHTML = "";
    modalHistoryBody.innerHTML = "";
    
    const payload = result.consolidated_result || result;
    const tables = payload.tables || [];
    if (tables.length === 0) return;
    
    const table = tables[0];
    modalHistoryTitle.textContent = `📊 Historical Comparison: ${table.research_problem}`;
    
    const rowsToRender = table.rows.map(row => flattenRow(row, payload.domain));
    if (rowsToRender.length === 0) return;
    
    const headers = Object.keys(rowsToRender[0]);
    headers.forEach(h => {
        const th = document.createElement("th");
        th.textContent = h;
        modalHistoryHeaders.appendChild(th);
    });
    
    rowsToRender.forEach(row => {
        const tr = document.createElement("tr");
        headers.forEach(h => {
            const td = document.createElement("td");
            td.textContent = row[h];
            tr.appendChild(td);
        });
        modalHistoryBody.appendChild(tr);
    });
    
    // Génération et capture du CSV de session d'historique [3]
    const csvRows = [headers.join(",")];
    rowsToRender.forEach(row => {
        const values = headers.map(h => `"${String(row[h]).replace(/"/g, '""')}"`);
        csvRows.push(values.join(","));
    });
    historyCsvData = csvRows.join("\n");
}

// Liaison de téléchargement CSV du modal d'historique [3]
btnDownloadHistoryCsv.addEventListener("click", () => {
    if (!historyCsvData) return;
    const blob = new Blob([historyCsvData], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `history_export_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
});

window.loadHistoryTable = async function(tableId) {
    try {
        const response = await fetch(`${API_BASE_URL}/comparisons/${tableId}`);
        if (response.ok) {
            const data = await response.json();
            
            // Ouvrir le modal d'historique directement dans l'onglet actif [3]
            historyModal.classList.remove("hidden");
            renderHistoryModalTable(data);
        }
    } catch (e) {
        alert(`Failed to load comparative matrix: ${e.message}`);
    }
}

// D. Rendu de la file d'attente HITL
async function fetchAndRenderValidationQueue() {
    const container = document.getElementById("hitl-queue-container");
    const badge = document.getElementById("hitl-badge");
    try {
        const response = await fetch(`${API_BASE_URL}/validation-tasks`);
        if (response.ok) {
            const data = await response.json();
            badge.textContent = data.tasks.length;
            container.innerHTML = "";
            
            if (data.tasks.length === 0) {
                container.innerHTML = "<p style='color:var(--text-muted); text-align:center; padding: 2rem 0;'>🎉 Validation queue is empty. All schemas are verified.</p>";
                return;
            }
            
            data.tasks.forEach(t => {
                const div = document.createElement("div");
                div.className = "queue-item";
                div.innerHTML = `
                    <div>
                        <h4 style="font-size:0.9rem;">Domain Target: <code>${t.domain}</code></h4>
                        <p style="font-size:0.75rem; color:var(--text-muted);">Registered: ${new Date(t.created_at).toLocaleString()} | DB UUID: ${t.task_id}</p>
                    </div>
                    <div class="queue-actions">
                        <button class="btn btn-primary btn-solve-schema">🛠️ Solve Schema</button>
                        <button class="btn btn-danger btn-decline-schema-item">❌ Refuse</button>
                    </div>
                `;
                
                div.querySelector(".btn-solve-schema").addEventListener("click", () => {
                    loadHITLTask(t.task_id, t.domain);
                });
                
                div.querySelector(".btn-decline-schema-item").addEventListener("click", () => {
                    window.declineHITLTask(t.task_id);
                });
                
                container.appendChild(div);
            });
        }
    } catch (e) {
        container.innerHTML = `<p style="color:var(--primary-color);">Error reading validation queue: ${e.message}</p>`;
    }
}

async function loadHITLTask(taskId, domain) {
    try {
        const response = await fetch(`${API_BASE_URL}/tasks/${taskId}`);
        if (response.ok) {
            const data = await response.json();
            tabLinks[0].click();
            renderSchemaValidationForm(data.proposed_properties, domain, taskId);
        }
    } catch (e) {
        alert(e.message);
    }
}

// Interception de l'upload pour la recommandation sémantique automatique
fileInput.addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (file && file.type === "application/pdf") {
        // CORRECTION : Déclenche l'analyse d'IA UNIQUEMENT si le template est sur "default"
        if (domainTypeSelect.value !== "default") {
            recommendationCard.classList.add("hidden");
            return;
        }

        const formData = new FormData();
        formData.append("file", file);
        formData.append("document_type", "single");
        formData.append("domain", "default");

        try {
            const response = await fetch(`${API_BASE_URL}/ingest`, { method: "POST", body: formData });
            if (response.ok) {
                const data = await response.json();
                
                const pollMarkdown = setInterval(async () => {
                    const statusRes = await fetch(`${API_BASE_URL}/tasks/${data.task_id}`);
                    if (statusRes.ok) {
                        const statusData = await statusRes.json();
                        if (statusData.status === "PENDING_SCHEMA_VALIDATION" || statusData.status === "SUCCESS" || statusData.status === "PENDING_SCHEMA_PROPOSAL") {
                            clearInterval(pollMarkdown);
                            
                            // Sécurité : Si l'utilisateur a changé le sélecteur entre-temps, on annule
                            if (domainTypeSelect.value !== "default") {
                                recommendationCard.classList.add("hidden");
                                return;
                            }

                            const taskRes = await fetch(`${API_BASE_URL}/tasks/${data.task_id}`);
                            const taskData = await taskRes.json();
                            
                            // CORRECTION : Transmettre le véritable ID de tâche (data.task_id) à la recommandation
                            triggerAIRecommendation(taskData.raw_markdown || "Academic Abstract Analysis", data.task_id);
                        }
                    }
                }, 1000);
            }
        } catch (err) {
            console.warn("Failed pre-parsing for recommendation:", err);
        }
    }
});

// 1. Écouteur sur le sélecteur de domaine pour masquer la recommandation si un template est choisi à la main
domainTypeSelect.addEventListener("change", () => {
    if (domainTypeSelect.value !== "default") {
        recommendationCard.classList.add("hidden");
        writeLog("system", `User selected template '${domainTypeSelect.value}' manually. Bypassing AI recommendation.`);
    }
});

window.addEventListener("DOMContentLoaded", () => {
    populateDomainSelector();
    fetchAndRenderValidationQueue();
});