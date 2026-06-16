# app_ui.py
import streamlit as st
import requests
import time
import pandas as pd
from typing import Dict, Any, List

# Configuration de la page Streamlit
st.set_page_config(
    page_title="Scientific Comparative Matrix Extractor",
    page_icon="📊",
    layout="wide"
)

# Configuration de l'URL de l'API FastAPI
API_BASE_URL = "http://localhost:8000/api/v1"

st.title("📊 Scientific Comparative Matrix Extractor")
st.write(
    "Upload a scientific paper or proceeding compilation to automatically extract "
    "and structure comparative tables or clinical metrics based on your chosen domain."
)

# ---------------------------------------------------------------------------
# 1. Fonctions de Transformation (Domaine par Défaut - Tableaux Comparatifs)
# ---------------------------------------------------------------------------
def flatten_comparison_row(row_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flattens the nested 'domain_specific_properties' dictionary into 
    first-class columns for standard comparative representation.
    """
    flat_row = {
        "Paper Title": row_dict.get("paper_title"),
        "Authors": ", ".join(row_dict.get("authors", [])) if row_dict.get("authors") else "Unknown",
        "Publication Date": f"{row_dict.get('publication_month') or ''} {row_dict.get('publication_year') or ''}".strip() or "N/A",
        "Venue": row_dict.get("venue") or "N/A",
        "Research Field": row_dict.get("research_field") or "N/A",
        "Research Method": row_dict.get("research_method") or "N/A",
        "DOI": row_dict.get("doi") or "N/A",
        "URL": row_dict.get("url") or "N/A",
    }
    
    if row_dict.get("proceeding_title"):
        flat_row["Proceeding Title"] = row_dict.get("proceeding_title")
        
    # Extraction des propriétés dynamiques (Phi)
    dynamic_props = row_dict.get("domain_specific_properties", {})
    for key, val in dynamic_props.items():
        clean_key = key.replace("_", " ").title()
        flat_row[clean_key] = val
        
    return flat_row


def convert_table_to_dataframe(table_dict: Dict[str, Any]) -> pd.DataFrame:
    """
    Converts a structured comparison table into a flat Pandas DataFrame.
    """
    raw_rows = table_dict.get("rows", [])
    flat_rows = [flatten_comparison_row(row) for row in raw_rows]
    return pd.DataFrame(flat_rows)


# ---------------------------------------------------------------------------
# 2. Fonction de Rendu (Domaine Spécialisé - Infectious Disease)
# ---------------------------------------------------------------------------
def flatten_infectious_disease_row(row_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flattens a specialized Infectious Disease row into first-class columns 
    for side-by-side tabular comparison in Streamlit and CSV.
    """
    flat_row = {
        "Paper Title/Study": row_dict.get("paper_title"),
        "Authors": ", ".join(row_dict.get("authors", [])) if row_dict.get("authors") else "Unknown",
        "Disease Name": row_dict.get("disease_name") or "N/A",
        "Pathogen": row_dict.get("pathogen") or "N/A",
        "Diet Type": row_dict.get("type_of_diet") or "N/A",
        "Food Component": row_dict.get("food_component") or "N/A",
        "Medical Treatment": row_dict.get("medical_treatment") or "N/A",
        "Duration": row_dict.get("duration_of_intervention") or "N/A",
        "Biomarkers": ", ".join(row_dict.get("biomarkers", [])) if row_dict.get("biomarkers") else "N/A",
        "Symptoms": ", ".join(row_dict.get("has_symptom", [])) if row_dict.get("has_symptom") else "N/A",
        "Study Population": row_dict.get("study_population") or "N/A",
        "Geographical Area": row_dict.get("geographical_area") or "N/A",
        "Outcome / Finding": row_dict.get("has_outcome") or "N/A",
        "Follow-up Period": row_dict.get("follow_up_period") or "N/A",
        "Method": row_dict.get("method") or "N/A",
    }
    
    # Extraction du sous-groupe contribution s'il est présent
    contrib = row_dict.get("contribution")
    if contrib:
        flat_row["Contribution: Problem"] = contrib.get("research_problem")
        flat_row["Contribution: Result"] = contrib.get("result")
    else:
        # Les baselines n'ont pas de bloc "contribution" propre au papier uploade
        flat_row["Contribution: Problem"] = "N/A (Prior Study)"
        flat_row["Contribution: Result"] = "N/A (Prior Study)"
        
    return flat_row



def render_infectious_disease_data(data_payload: Dict[str, Any]):
    """
    Renders the complete Infectious Disease comparative table (proposed vs. prior studies)
    as a clean horizontal DataFrame, with CSV download capability.
    """
    research_problem = data_payload.get("research_problem", "Infectious Disease Study")
    st.subheader(f"📊 Comparative Matrix: *{research_problem}*")
    
    # 1. Extraction et aplatissement de toutes les lignes (Étude principale + Baselines)
    raw_rows = data_payload.get("rows", [])
    
    if not raw_rows:
        st.warning("No comparative rows were extracted. Ensure the document contains baseline comparisons.")
        return
        
    flat_rows = [flatten_infectious_disease_row(row) for row in raw_rows]
    
    # 2. Conversion en DataFrame Pandas
    df_display = pd.DataFrame(flat_rows)
    
    # 3. Rendu visuel horizontal interactif
    st.dataframe(df_display, use_container_width=True)
    
    # 4. Exportation CSV unifiée
    csv_data = df_display.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Comparative Matrix as CSV",
        data=csv_data,
        file_name=f"infectious_disease_comparison_{research_problem.lower().replace(' ', '_')}.csv",
        mime="text/csv"
    )

# ---------------------------------------------------------------------------
# 3. Composants d'Interface (UI)
# ---------------------------------------------------------------------------
uploaded_file = st.file_uploader("Choose a scientific PDF file...", type=["pdf"])

if uploaded_file is not None:
    st.info(f"File '{uploaded_file.name}' loaded successfully.")
    
    # Configuration des sélecteurs sur deux colonnes
    col1, col2 = st.columns(2)
    
    with col1:
        doc_type_option = st.selectbox(
            "Document Scale Type",
            options=["Auto-detect", "Single Research Paper", "Conference Proceeding"],
            help="Select 'Auto-detect' to let the model classify the document structure. Select manually to bypass classification and save API tokens."
        )
    with col2:
        domain_option = st.selectbox(
            "Scientific Domain Template",
            options=["General Academic (Default)", "Infectious Disease"],
            help="Select 'Infectious Disease' to target pathogens, diets, clinical interventions, and biomarkers."
        )
        
    # Mappages d'interfaces vers valeurs d'API
    doc_type_mapping = {
        "Auto-detect": "auto", 
        "Single Research Paper": "single", 
        "Conference Proceeding": "proceeding"
    }
    domain_mapping = {
        "General Academic (Default)": "default", 
        "Infectious Disease": "infectious-disease"
    }
    
    api_doc_type = doc_type_mapping[doc_type_option]
    api_domain = domain_mapping[domain_option]
    
    if st.button("🚀 Start Extraction Task", use_container_width=True):
        # 1. Envoi du document à la route d'ingestion de l'API
        with st.spinner("Uploading and registering document in pipeline..."):
            try:
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                data = {
                    "document_type": api_doc_type,
                    "domain": api_domain
                }
                response = requests.post(f"{API_BASE_URL}/ingest", files=files, data=data)
                
                if response.status_code == 202:
                    task_id = response.json()["task_id"]
                    st.success(f"Ingestion successful. Task registered with ID: `{task_id}` (Domain: `{api_domain}`)")
                else:
                    st.error(f"Ingestion failed with code {response.status_code}: {response.text}")
                    st.stop()
            except Exception as e:
                st.error(f"Could not connect to FastAPI server at {API_BASE_URL}. Error: {str(e)}")
                st.stop()
                
        # 2. Suivi asynchrone de l'avancement de la tâche
        status_bar = st.progress(0)
        status_text = st.empty()
        
        task_completed = False
        final_result = None
        
        while not task_completed:
            try:
                status_response = requests.get(f"{API_BASE_URL}/tasks/{task_id}")
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    status = status_data["status"]
                    
                    if status == "SUCCESS":
                        status_bar.progress(100)
                        status_text.success("Processing Completed!")
                        final_result = status_data["result"]
                        task_completed = True
                    elif status == "FAILURE":
                        status_bar.progress(100)
                        status_text.error(f"Task execution failed: {status_data.get('error')}")
                        task_completed = True
                        st.stop()
                    else:
                        progress_msg = status_data.get("progress_info", {}).get("progress_status", "Executing agents...")
                        status_text.info(f"Status: **{status}** — {progress_msg}")
                        status_bar.progress(50)
                else:
                    status_text.error(f"Failed to query task status. Code: {status_response.status_code}")
                    
            except Exception as e:
                st.warning(f"Network glitch during status polling: {str(e)}")
                
            time.sleep(3)  # Intervalle de requête de 3 secondes
            
        # 3. Rendu sémantique dynamique selon le domaine retourné par l'API
        if final_result:
            domain_used = final_result.get("domain", "default")
            data_payload = final_result.get("data", {})
            
            st.markdown("---")
            
            if domain_used == "infectious-disease":
                # Rendu spécifique par fiche clinique descriptive pour Infectious Disease
                render_infectious_disease_data(data_payload)
                
            else:
                # Rendu par tableaux comparatifs classiques avec baselines
                st.subheader("📋 Extracted Comparative Matrices")
                tables = data_payload.get("tables", [])
                
                if not tables:
                    st.warning("No comparative tables were generated. Please verify the paper content.")
                    st.stop()
                    
                for idx, table in enumerate(tables):
                    research_problem = table.get("research_problem", "General Comparison")
                    st.markdown(f"### Table {idx + 1}: *{research_problem}*")
                    
                    # Conversion dynamique en DataFrame Pandas
                    df = convert_table_to_dataframe(table)
                    st.dataframe(df, use_container_width=True)
                    
                    # Export CSV du tableau comparatif
                    csv_data = df.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        label=f"📥 Download Table {idx + 1} as CSV",
                        data=csv_data,
                        file_name=f"comparison_{research_problem.lower().replace(' ', '_')}.csv",
                        mime="text/csv",
                        key=f"dl_btn_{idx}"
                    )