import streamlit as st
import requests
import pandas as pd
import locale
from typing import Optional, List, Dict, Any

st.set_page_config(
    page_title = "Dashboard Auxílio Emergencial",
    page_icon = "🇧🇷",
    layout = "wide"
)

API_BASE_URL = "http://api:8000/api/v1/auxilio"

MES_MAP = {
    'Abril/2020': '202004',
    'Maio/2020': '202005',
    'Junho/2020': '202006',
    'Julho/2020': '202007',
    'Agosto/2020': '202008',
}

def format_currency(value: float) -> str:
    """
    Formata um valor float como moeda (BRL).
    Inclui um fallback para o caso do locale 'pt_BR' não estar
    instalado no contêiner Docker.
    """
    try:
        locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
        return locale.currency(value, grouping = True)
    except locale.Error:
        return f"R$ {value:,.2f}"

def show_api_error(e: requests.exceptions.RequestException):
    """Exibe uma mensagem de erro padronizada da API."""
    if isinstance(e, requests.exceptions.ConnectionError):
        st.error(f"Erro de Conexão: Não foi possível conectar à API em {API_BASE_URL}. O serviço 'api' está rodando?")
    elif e.response is not None:
        detail = e.response.json().get('detail', 'Erro desconhecido')
        st.error(f"Erro na API ({e.response.status_code}): {detail}")
    else:
        st.error(f"Erro de request: {e}")


@st.cache_data
def get_total_gasto_por_uf(uf: str) -> Optional[Dict[str, float]]:
    """Chama a API FastAPI para buscar o total gasto por UF."""
    endpoint = f"{API_BASE_URL}/estatisticas/total-gasto-por-uf"
    try:
        response = requests.get(endpoint, params = {"uf": uf})
        response.raise_for_status() 
        return response.json()  
    except requests.exceptions.RequestException as e:
        show_api_error(e)
        return None

@st.cache_data
def get_total_gasto_por_mes(ano_mes: str) -> Optional[Dict[str, float]]:
    """Chama a API para buscar o total gasto por mês."""
    endpoint = f"{API_BASE_URL}/estatisticas/total-gasto-por-mes"
    try:
        response = requests.get(endpoint, params = {"ano_mes": ano_mes})
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        show_api_error(e)
        return None

@st.cache_data
def search_beneficiarios(nome: Optional[str], uf: Optional[str], municipio: Optional[str]) -> List[Dict[str, Any]]:
    """Chama a API para buscar beneficiários por nome, UF e/ou município."""
    endpoint = f"{API_BASE_URL}/beneficiarios"
    params = {"skip": 0, "limit": 100} 
    if nome:
        params["nome"] = nome
    if uf:
        params["uf"] = uf
    if municipio:
        params["municipio"] = municipio
        
    try:
        response = requests.get(endpoint, params=params)
        response.raise_for_status()
        return response.json() 
    except requests.exceptions.RequestException as e:
        show_api_error(e)
        return []

@st.cache_data
def get_beneficiario_by_nis(nis: str) -> Optional[Dict[str, Any]]:
    """Chama a API para buscar um beneficiário por NIS."""
    endpoint = f"{API_BASE_URL}/beneficiarios/{nis}"
    try:
        response = requests.get(endpoint)
        response.raise_for_status()
        return response.json()  
    except requests.exceptions.RequestException as e:
        show_api_error(e)
        return None

@st.cache_data
def get_beneficiarios_por_parcela(uf: str, min_parcela: int) -> List[Dict[str, Any]]:
    """Chama a API para a consulta avançada de parcelas por UF."""
    endpoint = f"{API_BASE_URL}/beneficiarios/consulta/por-parcela-e-uf"
    params = {"uf": uf, "min_parcela": min_parcela, "limit": 100}
    try:
        response = requests.get(endpoint, params = params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        show_api_error(e)
        return []

@st.cache_data
def search_responsaveis(nome: str) -> List[Dict[str, Any]]:
    """Chama a API para buscar responsáveis por nome."""
    endpoint = f"{API_BASE_URL}/responsaveis"
    params = {"nome": nome, "limit": 100}
    try:
        response = requests.get(endpoint, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        show_api_error(e)
        return []

@st.cache_data
def get_responsavel_by_nis(nis: str) -> Optional[Dict[str, Any]]:
    """Chama a API para buscar um responsável por NIS."""
    endpoint = f"{API_BASE_URL}/responsaveis/{nis}"
    try:
        response = requests.get(endpoint)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        show_api_error(e)
        return None

st.sidebar.title("Navegação")
page = st.sidebar.radio(
    "Selecione uma página:",
    ("Estatísticas", "Busca de Beneficiários", "Busca de Responsáveis")
)

st.title("🇧🇷 Dashboard de Análise do Auxílio Emergencial")
st.markdown("Consumindo dados em tempo real da API FastAPI do projeto.")

if page == "Estatísticas":
    st.header("Estatísticas de Pagamento")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Total Gasto por UF")
        uf_input = st.text_input(
            label = "Digite a UF (ex: CE, SP, BA):",
            max_chars = 2,
            key = "uf_total_input"
        ).upper()
        
        if st.button("Consultar Gasto por UF"):
            if not uf_input:
                st.warning("Por favor, digite uma UF.")
            else:
                with st.spinner(f"Buscando dados para {uf_input}..."):
                    data = get_total_gasto_por_uf(uf_input)
                    if data:
                        total = data.get("total", 0)
                        st.metric(
                            label = f"Total Gasto em {uf_input}",
                            value = format_currency(total)
                        )
    
    with col2:
        st.subheader("Total Gasto por Mês")
        mes_selecionado = st.selectbox(
            "Selecione o Mês:",
            options = list(MES_MAP.keys()) 
        )
        
        if st.button("Consultar Gasto por Mês"):
            ano_mes_val = MES_MAP[mes_selecionado]
            with st.spinner(f"Buscando dados para {mes_selecionado}..."):
                data = get_total_gasto_por_mes(ano_mes_val)
                if data:
                    total = data.get("total", 0)
                    st.metric(
                        label = f"Total Gasto em {mes_selecionado}",
                        value = format_currency(total)
                    )

elif page == "Busca de Beneficiários":
    st.header("Consulta de Beneficiários")
    
    tab1, tab2, tab3 = st.tabs([
        "Buscar por Nome/Local", 
        "Buscar por NIS", 
        "Consulta Avançada (Parcelas)"
    ])
    
    with tab1:
        st.subheader("Buscar por Nome, UF e/ou Município")
        nome_b = st.text_input("Nome (parcial):", key = "b_nome")
        uf_b = st.text_input("UF (ex: CE):", max_chars = 2, key = "b_uf").upper()
        municipio_b = st.text_input("Município (parcial):", key = "b_mun")
        
        if st.button("Buscar Beneficiários", key = "b_btn_nome"):
            with st.spinner("Buscando..."):
                resultados = search_beneficiarios(nome_b, uf_b, municipio_b)
                if resultados:
                    df = pd.DataFrame(resultados)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("Nenhum beneficiário encontrado com esses filtros.")

    with tab2:
        st.subheader("Buscar por NIS")
        nis_b = st.text_input("Digite o NIS do Beneficiário:", key = "b_nis")
        
        if st.button("Buscar por NIS", key = "b_btn_nis"):
            if not nis_b:
                st.warning("Por favor, digite um NIS.")
            else:
                with st.spinner("Buscando..."):
                    resultado = get_beneficiario_by_nis(nis_b)
                    
                    if resultado:
                        df = pd.DataFrame([resultado])
                        st.dataframe(df, use_container_width = True)
                  


    with tab3:
        st.subheader("Beneficiários por Nº de Parcelas e UF")
        uf_p = st.text_input("UF (ex: CE):", max_chars = 2, key = "p_uf").upper()
        parcela_p = st.selectbox(
            "Número de parcelas recebidas MAIOR que:",
            options = [0, 1, 2, 3, 4], 
            index = 1, 
            key = "p_parcela"
        )
        
        if st.button("Consultar", key = "p_btn"):
            if not uf_p:
                st.warning("Por favor, digite uma UF.")
            else:
                with st.spinner("Buscando..."):
                    resultados = get_beneficiarios_por_parcela(uf_p, int(parcela_p))
                    if resultados:
                        df = pd.DataFrame(resultados)
                        st.dataframe(df, use_container_width = True)

elif page == "Busca de Responsáveis":
    st.header("Consulta de Responsáveis")
    
    tab1, tab2 = st.tabs(["Buscar por Nome", "Buscar por NIS"])
    
    with tab1:
        st.subheader("Buscar por Nome")
        nome_r = st.text_input("Nome (parcial):", key = "r_nome")
        
        if st.button("Buscar Responsáveis", key = "r_btn_nome"):
            if not nome_r:
                st.warning("Por favor, digite parte do nome.")
            else:
                with st.spinner("Buscando..."):
                    resultados = search_responsaveis(nome_r)
                    if resultados:
                        df = pd.DataFrame(resultados)
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info("Nenhum responsável encontrado.")
    
    with tab2:
        st.subheader("Buscar por NIS")
        nis_r = st.text_input("Digite o NIS do Responsável:", key = "r_nis")
        
        if st.button("Buscar por NIS", key = "r_btn_nis"):
            if not nis_r:
                st.warning("Por favor, digite um NIS.")
            else:
                with st.spinner("Buscando..."):
                    resultado = get_responsavel_by_nis(nis_r)
                    
                    if resultado:
                        df = pd.DataFrame([resultado])
                        st.dataframe(df, use_container_width = True)
