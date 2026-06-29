const API_BASE_URL = "/api/v1"; // CORS-free since files are served natively from FastAPI

const dropzone = document.getElementById("pdf-dropzone");
const fileInput = document.getElementById("file-input");
const fileNameDisplay = document.getElementById("selected-file-name");
const btnStart = document.getElementById("btn-start");
const docTypeSelect = document.getElementById("doc-type");
const domainTypeSelect = document.getElementById("domain-type");

const statusCard = document.getElementById("status-card");
const progressBar = document.getElementById("progress-bar");
const statusMessage = document.getElementById("status-message");
const taskIdDisplay = document.getElementById("display-task-id");

const resultsCard = document.getElementById("results-card");
const tableTitle = document.getElementById("table-title");
const tableHeaders = document.getElementById("table-headers");
const tableBody = document.getElementById("table-body");
const btnDownloadCsv = document.getElementById("btn-download-csv");

let selectedFile = null;
let extractedCsvData = ""; // Stocke les données CSV formatées pour le téléchargement

// Gestion des événements d'upload de fichiers (Drag & Drop)
dropzone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", (e) => handleFileSelect(e.target.files[0]));

dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.style.borderColor = "var(--primary-color)";
});

dropzone.addEventListener("dragleave", () => {
    dropzone.style.borderColor = "var(--border-color)";
});

dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.style.borderColor = "var(--border-color)";
    handleFileSelect(e.dataTransfer.files[0]);
});

function handleFileSelect(file) {
    if (file && file.type === "application/pdf") {
        selectedFile = file;
        fileNameDisplay.textContent = `Selected: ${file.name}`;
        btnStart.disabled = false;
    } else {
        alert("Please upload a valid PDF document.");
    }
}

// Lancement du traitement
btnStart.addEventListener("click", async () => {
    if (!selectedFile) return;

    btnStart.disabled = true;
    statusCard.classList.remove("hidden");
    resultsCard.classList.add("hidden");
    progressBar.style.width = "10%";
    statusMessage.textContent = "Uploading document...";

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("document_type", docTypeSelect.value);
    formData.append("domain", domainTypeSelect.value);

    try {
        const response = await fetch(`${API_BASE_URL}/ingest`, {
            method: "POST",
            body: formData
        });
        
        if (response.ok) {
            const data = await response.json();
            const taskId = data.task_id;
            taskIdDisplay.textContent = taskId;
            pollTaskStatus(taskId, domainTypeSelect.value);
        } else {
            throw new Error("Ingestion failure.");
        }
    } catch (error) {
        statusMessage.textContent = `Error: ${error.message}`;
        btnStart.disabled = false;
    }
});

// Suivi de l'avancement (Polling)
function pollTaskStatus(taskId, domain) {
    progressBar.style.width = "40%";
    statusMessage.textContent = "Processing agents executing tasks...";

    const interval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/tasks/${taskId}`);
            if (response.ok) {
                const data = await response.json();
                
                if (data.status === "SUCCESS") {
                    clearInterval(interval);
                    progressBar.style.width = "100%";
                    statusMessage.textContent = "Extraction Completed!";
                    renderResults(data.result, domain);
                    btnStart.disabled = false;
                } else if (data.status === "FAILURE") {
                    clearInterval(interval);
                    statusMessage.textContent = `Failed: ${data.error}`;
                    btnStart.disabled = false;
                } else if (data.progress_info) {
                    statusMessage.textContent = data.progress_info.progress_status;
                }
            }
        } catch (error) {
            console.error("Polling error:", error);
        }
    }, 3000);
}

// Formate une ligne d'extraction en dictionnaire à plat
function flattenRow(row, domain) {
    if (domain === "infectious-disease") {
        return {
            "Paper Title": row.paper_title,
            "Disease Name": row.disease_name || "N/A",
            "Pathogen": row.pathogen || "N/A",
            "Diet Type": row.type_of_diet || "N/A",
            "Food Component": row.food_component || "N/A",
            "Medical Treatment": row.medical_treatment || "N/A",
            "Duration": row.duration_of_intervention || "N/A",
            "Biomarkers": (row.biomarkers || []).join(", ") || "N/A",
            "Outcome": row.has_outcome || "N/A"
        };
    } else if (domain === "nutritional-metabolic") {
        return {
            "Paper Title": row.paper_title,
            "Disease Name": row.disease_name || "N/A",
            "Diet Type": row.type_of_diet || "N/A",
            "Food Component": row.food_component || "N/A",
            "Causes": row.causes || "N/A",
            "Biomarkers": (row.biomarkers || []).join(", ") || "N/A",
            "Outcome": row.has_outcome || "N/A"
        };
    } else {
        // Domaine par défaut
        const flat = {
            "Paper Title": row.paper_title,
            "Research Problem": row.research_problem || "N/A"
        };
        Object.entries(row.domain_specific_properties || {}).forEach(([k, v]) => {
            flat[k.charAt(0).toUpperCase() + k.slice(1)] = v;
        });
        return flat;
    }
}

// Rendu et affichage des résultats
function renderResults(result, domain) {
    resultsCard.classList.remove("hidden");
    tableHeaders.innerHTML = "";
    tableBody.innerHTML = "";

    const payload = result.data;
    let rowsToRender = [];

    if (domain === "default") {
        const table = payload.tables[0] || { research_problem: "Comparison", rows: [] };
        tableTitle.textContent = `📋 Comparative Matrix: ${table.research_problem}`;
        rowsToRender = table.rows.map(r => flattenRow(r, domain));
    } else {
        tableTitle.textContent = `📋 Comparative Matrix: ${payload.research_problem}`;
        rowsToRender = payload.rows.map(r => flattenRow(r, domain));
    }

    if (rowsToRender.length === 0) return;

    // Définition des entêtes à partir des clés du premier dictionnaire plat
    const headers = Object.keys(rowsToRender[0]);
    headers.forEach(h => {
        const th = document.createElement("th");
        th.textContent = h;
        tableHeaders.appendChild(th);
    });

    // Insertion des lignes du tableau
    rowsToRender.forEach(row => {
        const tr = document.createElement("tr");
        headers.forEach(h => {
            const td = document.createElement("td");
            td.textContent = row[h];
            tr.appendChild(td);
        });
        tableBody.appendChild(tr);
    });

    // Génération de la chaîne brute du CSV
    const csvRows = [headers.join(",")];
    rowsToRender.forEach(row => {
        const values = headers.map(h => {
            const val = String(row[h]).replace(/"/g, '""');
            return `"${val}"`;
        });
        csvRows.push(values.join(","));
    });
    extractedCsvData = csvRows.join("\n");
}

// Export CSV
btnDownloadCsv.addEventListener("click", () => {
    if (!extractedCsvData) return;
    const blob = new Blob([extractedCsvData], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `comparative_matrix_export_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
});