import streamlit as st
import requests
import pandas as pd
import locale
from typing import Optional, List, Dict, Any

st.set_page_config(
    page_title="Dashboard Auxílio Emergencial",
    page_icon="🇧🇷",
    layout="wide"
)

API_BASE_URL = "http://api:8000/api/v1"

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
        return locale.currency(value, grouping=True)
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


# ========== FUNÇÕES DA API - ROTAS BÁSICAS ==========

@st.cache_data
def get_total_gasto_por_uf(uf: str) -> Optional[Dict[str, float]]:
    """Chama a API FastAPI para buscar o total gasto por UF."""
    endpoint = f"{API_BASE_URL}/consultas/total-gasto-por-uf"
    try:
        response = requests.get(endpoint, params={"uf": uf})
        response.raise_for_status() 
        return response.json()  
    except requests.exceptions.RequestException as e:
        show_api_error(e)
        return None

@st.cache_data
def get_total_gasto_por_mes(ano_mes: str) -> Optional[Dict[str, float]]:
    """Chama a API para buscar o total gasto por mês."""
    endpoint = f"{API_BASE_URL}/consultas/total-gasto-por-mes"
    try:
        response = requests.get(endpoint, params={"ano_mes": ano_mes})
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        show_api_error(e)
        return None

@st.cache_data
def search_beneficiarios(nome: Optional[str], uf: Optional[str], municipio: Optional[str]) -> List[Dict[str, Any]]:
    """Chama a API para buscar beneficiários por nome, UF e/ou município."""
    endpoint = f"{API_BASE_URL}/beneficiarios/"
    params = {} 
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
def search_responsaveis(nome: str) -> List[Dict[str, Any]]:
    """Chama a API para buscar responsáveis por nome."""
    endpoint = f"{API_BASE_URL}/responsaveis"
    params = {"nome": nome}
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

@st.cache_data
def get_beneficiarios_por_valor(valor: float) -> List[Dict[str, Any]]:
    """Chama a API para buscar beneficiários que receberam um valor específico."""
    endpoint = f"{API_BASE_URL}/consultas/beneficiarios-por-valor"
    params = {"valor": valor}
    try:
        response = requests.get(endpoint, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        show_api_error(e)
        return []

@st.cache_data
def get_quantidade_beneficiarios_municipio(uf: str, municipio: str) -> Optional[Dict[str, int]]:
    """Chama a API para buscar quantidade de beneficiários em um município."""
    endpoint = f"{API_BASE_URL}/consultas/quantidade-beneficiarios-municipio"
    params = {"uf": uf, "municipio": municipio}
    try:
        response = requests.get(endpoint, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        show_api_error(e)
        return None

@st.cache_data
def get_beneficiarios_responsaveis(uf: str) -> List[Dict[str, Any]]:
    """Chama a API para buscar beneficiários que são também responsáveis."""
    endpoint = f"{API_BASE_URL}/consultas/beneficiarios-responsaveis"
    params = {"uf": uf}
    try:
        response = requests.get(endpoint, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        show_api_error(e)
        return []

@st.cache_data
def get_beneficiarios_multiplas_parcelas(uf: str, min_parcela: int) -> List[Dict[str, Any]]:
    """Chama a API para buscar beneficiários com múltiplas parcelas."""
    endpoint = f"{API_BASE_URL}/consultas/beneficiarios-multiplas-parcelas"
    params = {"uf": uf, "min_parcela": min_parcela}
    try:
        response = requests.get(endpoint, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        show_api_error(e)
        return []

@st.cache_data
def get_beneficiarios_por_nome(nome: str) -> List[Dict[str, Any]]:
    """Chama a API para buscar beneficiários por nome específico."""
    endpoint = f"{API_BASE_URL}/consultas/beneficiarios-por-nome"
    params = {"nome": nome}
    try:
        response = requests.get(endpoint, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        show_api_error(e)
        return []

st.sidebar.title("Navegação")
page = st.sidebar.radio(
    "Selecione uma página:",
    (
        "Estatísticas", 
        "Busca de Beneficiários", 
        "Busca de Responsáveis",
        "Consultas Avançadas"
    )
)

st.title("🇧🇷 Dashboard de Análise do Auxílio Emergencial")
st.markdown("Consumindo dados em tempo real da API FastAPI do projeto.")

if page == "Estatísticas":
    st.header("📊 Estatísticas de Pagamento")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💰 Total Gasto por UF")
        uf_input = st.text_input(
            label="Digite a UF (ex: CE, SP, BA):",
            max_chars=2,
            key="uf_total_input"
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
                            label=f"Total Gasto em {uf_input}",
                            value=format_currency(total)
                        )
    
    with col2:
        st.subheader("📅 Total Gasto por Mês")
        mes_selecionado = st.selectbox(
            "Selecione o Mês:",
            options=list(MES_MAP.keys()) 
        )
        
        if st.button("Consultar Gasto por Mês"):
            ano_mes_val = MES_MAP[mes_selecionado]
            with st.spinner(f"Buscando dados para {mes_selecionado}..."):
                data = get_total_gasto_por_mes(ano_mes_val)
                if data:
                    total = data.get("total", 0)
                    st.metric(
                        label=f"Total Gasto em {mes_selecionado}",
                        value=format_currency(total)
                    )
    
    st.divider()
    
    st.subheader("🏘️ Quantidade de Beneficiários por Município")
    col3, col4 = st.columns(2)
    
    with col3:
        uf_mun = st.text_input("UF:", max_chars=2, key="uf_municipio").upper()
    with col4:
        municipio_input = st.text_input("Município:", key="municipio_input")
    
    if st.button("Consultar Quantidade"):
        if not uf_mun or not municipio_input:
            st.warning("Por favor, preencha UF e Município.")
        else:
            with st.spinner(f"Buscando dados para {municipio_input}/{uf_mun}..."):
                data = get_quantidade_beneficiarios_municipio(uf_mun, municipio_input)
                if data:
                    quantidade = data.get("quantidade", 0)
                    st.metric(
                        label=f"Beneficiários em {municipio_input}/{uf_mun}",
                        value=f"{quantidade:,}".replace(",", ".")
                    )

elif page == "Busca de Beneficiários":
    st.header("🔍 Consulta de Beneficiários")
    
    tab1, tab2, tab3 = st.tabs([
        "Buscar por Nome/Local", 
        "Buscar por NIS", 
        "Buscar por Nome Específico"
    ])
    
    with tab1:
        st.subheader("Buscar por Nome, UF e/ou Município")
        st.info("💡 Deixe os campos vazios para listar todos os beneficiários")
        nome_b = st.text_input("Nome (parcial):", key="b_nome")
        uf_b = st.text_input("UF (ex: CE):", max_chars=2, key="b_uf").upper()
        municipio_b = st.text_input("Município (parcial):", key="b_mun")
        
        if st.button("Buscar Beneficiários", key="b_btn_nome"):
            with st.spinner("Buscando..."):
                resultados = search_beneficiarios(nome_b or None, uf_b or None, municipio_b or None)
                if resultados:
                    df = pd.DataFrame(resultados)
                    st.success(f"✅ {len(resultados)} beneficiário(s) encontrado(s)")
                    st.dataframe(df, use_container_width=True)
                    
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download CSV",
                        data=csv,
                        file_name="beneficiarios.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("Nenhum beneficiário encontrado com esses filtros.")

    with tab2:
        st.subheader("Buscar por NIS")
        nis_b = st.text_input("Digite o NIS do Beneficiário:", key="b_nis")
        
        if st.button("Buscar por NIS", key="b_btn_nis"):
            if not nis_b:
                st.warning("Por favor, digite um NIS.")
            else:
                with st.spinner("Buscando..."):
                    resultado = get_beneficiario_by_nis(nis_b)
                    
                    if resultado:
                        st.success("✅ Beneficiário encontrado!")
                        df = pd.DataFrame([resultado])
                        st.dataframe(df, use_container_width=True)

    with tab3:
        st.subheader("Buscar por Nome Específico")
        st.info("💡 Busca beneficiários cujo nome começa com o texto informado")
        nome_especifico = st.text_input(
            "Digite o nome (ex: ISRAEL):",
            key="b_nome_esp"
        ).upper()
        
        if st.button("Buscar", key="b_btn_nome_esp"):
            if not nome_especifico:
                st.warning("Por favor, digite um nome.")
            else:
                with st.spinner("Buscando..."):
                    resultados = get_beneficiarios_por_nome(nome_especifico)
                    if resultados:
                        df = pd.DataFrame(resultados)
                        st.success(f"✅ {len(resultados)} beneficiário(s) encontrado(s)")
                        st.dataframe(df, use_container_width=True)
                        
                        csv = df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Download CSV",
                            data=csv,
                            file_name=f"beneficiarios_{nome_especifico}.csv",
                            mime="text/csv",
                            key="download_nome_esp"
                        )
                    else:
                        st.info(f"Nenhum beneficiário encontrado com o nome '{nome_especifico}'.")

elif page == "Busca de Responsáveis":
    st.header("👥 Consulta de Responsáveis")
    
    tab1, tab2 = st.tabs(["Buscar por Nome", "Buscar por NIS"])
    
    with tab1:
        st.subheader("Buscar por Nome")
        st.info("💡 Digite parte do nome para buscar")
        nome_r = st.text_input("Nome (parcial):", key="r_nome")
        
        if st.button("Buscar Responsáveis", key="r_btn_nome"):
            if not nome_r:
                st.warning("Por favor, digite parte do nome.")
            else:
                with st.spinner("Buscando..."):
                    resultados = search_responsaveis(nome_r)
                    if resultados:
                        df = pd.DataFrame(resultados)
                        st.success(f"✅ {len(resultados)} responsável(is) encontrado(s)")
                        st.dataframe(df, use_container_width=True)
                        
                        csv = df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Download CSV",
                            data=csv,
                            file_name="responsaveis.csv",
                            mime="text/csv"
                        )
                    else:
                        st.info("Nenhum responsável encontrado.")
    
    with tab2:
        st.subheader("Buscar por NIS")
        nis_r = st.text_input("Digite o NIS do Responsável:", key="r_nis")
        
        if st.button("Buscar por NIS", key="r_btn_nis"):
            if not nis_r:
                st.warning("Por favor, digite um NIS.")
            else:
                with st.spinner("Buscando..."):
                    resultado = get_responsavel_by_nis(nis_r)
                    
                    if resultado:
                        st.success("✅ Responsável encontrado!")
                        df = pd.DataFrame([resultado])
                        st.dataframe(df, use_container_width=True)

elif page == "Consultas Avançadas":
    st.header("🔬 Consultas Avançadas")
    
    tab1, tab2, tab3 = st.tabs([
        "Beneficiários por Valor",
        "Beneficiários com Múltiplas Parcelas",
        "Beneficiários-Responsáveis"
    ])
    
    with tab1:
        st.subheader("💵 Beneficiários que Receberam Valor Específico")
        st.info("📋 Consulta baseada em: Beneficiários que receberam 600 reais")
        
        valor_input = st.number_input(
            "Digite o valor do auxílio:",
            min_value=0.0,
            value=600.0,
            step=100.0,
            key="valor_input"
        )
        
        if st.button("Buscar por Valor", key="btn_valor"):
            with st.spinner(f"Buscando beneficiários que receberam R$ {valor_input:.2f}..."):
                resultados = get_beneficiarios_por_valor(valor_input)
                if resultados:
                    df = pd.DataFrame(resultados)
                    st.success(f"✅ {len(resultados)} beneficiário(s) encontrado(s)")
                    st.dataframe(df, use_container_width=True)
                    
                    total_gasto = len(resultados) * valor_input
                    st.metric(
                        label="Total Gasto Estimado",
                        value=format_currency(total_gasto)
                    )
                    
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download CSV",
                        data=csv,
                        file_name=f"beneficiarios_valor_{valor_input}.csv",
                        mime="text/csv",
                        key="download_valor"
                    )
                else:
                    st.info(f"Nenhum beneficiário encontrado com valor R$ {valor_input:.2f}")
    
    with tab2:
        st.subheader("📦 Beneficiários com Múltiplas Parcelas")
        st.info("📋 Consulta baseada em: Beneficiários que receberam mais de uma parcela")
        
        col1, col2 = st.columns(2)
        with col1:
            uf_parcelas = st.text_input("UF (ex: CE):", max_chars=2, key="uf_parcelas").upper()
        with col2:
            min_parcela = st.selectbox(
                "Parcelas maiores que:",
                options=[0, 1, 2, 3, 4],
                index=1,
                key="min_parcela"
            )
        
        if st.button("Buscar", key="btn_parcelas"):
            if not uf_parcelas:
                st.warning("Por favor, digite uma UF.")
            else:
                with st.spinner("Buscando..."):
                    resultados = get_beneficiarios_multiplas_parcelas(uf_parcelas, min_parcela)
                    if resultados:
                        df = pd.DataFrame(resultados)
                        st.success(f"✅ {len(resultados)} beneficiário(s) encontrado(s)")
                        st.dataframe(df, use_container_width=True)
                        
                        csv = df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Download CSV",
                            data=csv,
                            file_name=f"beneficiarios_{uf_parcelas}_parcelas.csv",
                            mime="text/csv",
                            key="download_parcelas"
                        )
                    else:
                        st.info(f"Nenhum beneficiário encontrado em {uf_parcelas} com mais de {min_parcela} parcela(s).")
    
    with tab3:
        st.subheader("👤👥 Beneficiários que São Responsáveis Concomitantes")
        st.info("📋 Consulta: Pessoas que aparecem tanto como beneficiários quanto como responsáveis")
        
        uf_resp = st.text_input("UF (ex: CE):", max_chars=2, key="uf_resp").upper()
        
        if st.button("Buscar", key="btn_resp"):
            if not uf_resp:
                st.warning("Por favor, digite uma UF.")
            else:
                with st.spinner("Buscando..."):
                    resultados = get_beneficiarios_responsaveis(uf_resp)
                    if resultados:
                        df = pd.DataFrame(resultados)
                        st.success(f"✅ {len(resultados)} registro(s) encontrado(s)")
                        st.dataframe(df, use_container_width=True)
                        
                        csv = df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Download CSV",
                            data=csv,
                            file_name=f"beneficiarios_responsaveis_{uf_resp}.csv",
                            mime="text/csv",
                            key="download_resp"
                        )
                    else:
                        st.info(f"Nenhum beneficiário-responsável encontrado em {uf_resp}.")

# ========== FOOTER ==========
st.divider()
st.markdown(
    """
    <div style='text-align: center; color: gray; font-size: 12px;'>
        Dashboard desenvolvido com Streamlit | Dados via API FastAPI<br>
        💡 <strong>Dica:</strong> Use os botões de download para exportar os dados em CSV
    </div>
    """,
    unsafe_allow_html=True
)