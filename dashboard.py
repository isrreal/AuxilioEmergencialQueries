import streamlit as st
import requests
import pandas as pd
import locale

st.set_page_config(
    page_title="Dashboard Auxílio Emergencial",
    page_icon="🇧🇷",
    layout="wide"
)

API_BASE_URL = "http://localhost:8000/api/v1" 

@st.cache_data
def get_total_gasto_por_uf(uf: str):
    """Chama a API FastAPI para buscar o total gasto por UF."""
    endpoint = f"{API_BASE_URL}/estatisticas/total-gasto-por-uf"
    try:
        response = requests.get(endpoint, params={"uf": uf})
        
        response.raise_for_status() 
        
        return response.json()
    
    except requests.exceptions.ConnectionError:
        st.error(f"Erro: Não foi possível conectar à API em {API_BASE_URL}. A API está rodando?")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"Erro na API ({e.response.status_code}): {e.response.json().get('detail', 'Erro desconhecido')}")
        return None

st.title("Dashboard de Análise do Auxílio Emergencial")
st.markdown("Consumindo dados em tempo real da API FastAPI do projeto.")

st.header("Consulta: Montante Gasto por UF")

uf_input = st.text_input(
    label="Digite a UF (ex: CE, SP, BA):",
    max_chars=2
).upper()

if st.button("Consultar Montante"):
    if not uf_input:
        st.warning("Por favor, digite uma UF.")
    else:
        with st.spinner(f"Buscando dados para {uf_input}..."):
            
            data = get_total_gasto_por_uf(uf_input)
            
            if data:
                total = data.get("total", 0)
                
                locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
                total_formatado = locale.currency(total, grouping=True)
                
                st.metric(
                    label=f"Total Gasto em {uf_input}",
                    value=total_formatado
                )