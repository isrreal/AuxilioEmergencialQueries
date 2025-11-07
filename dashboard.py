import streamlit as st
import requests
import time
import pandas as pd
import plotly.graph_objects as go
import json
from typing import Generator, Any, Dict, List, Literal, TypedDict, Callable

# Configuração
API_BASE = "http://api:8000/api/v1"
st.set_page_config(page_title="Benchmark Índices", layout="wide")

# ===================================================================
# AUTENTICAÇÃO
# ===================================================================

def login(username: str, password: str) -> str | None:
    """Realiza login e retorna o token."""
    try:
        resp = requests.post(
            f"{API_BASE}/login",
            data={"username": username, "password": password},
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json().get("access_token")
    except requests.exceptions.RequestException as e:
        st.sidebar.error(f"Erro de conexão: {e}")
    except Exception as e:
        st.sidebar.error(f"Erro inesperado: {e}")
    return None

def get_headers() -> dict:
    """Retorna headers com token de autenticação."""
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}

# Sidebar de Login
st.sidebar.title("🔐 Autenticação")

if "token" not in st.session_state:
    st.session_state.token = None

if not st.session_state.token:
    username = st.sidebar.text_input("Usuário")
    password = st.sidebar.text_input("Senha", type="password")
    
    if st.sidebar.button("Entrar"):
        token = login(username, password)
        if token:
            st.session_state.token = token
            st.rerun()
        else:
            st.sidebar.error("❌ Login falhou")
else:
    st.sidebar.success("✅ Autenticado")
    if st.sidebar.button("Sair"):
        st.session_state.token = None
        st.rerun()

# ===================================================================
# FUNÇÕES DE API (COM PREFIXO /consultas/)
# ===================================================================

def api_post(endpoint: str) -> tuple[float | None, int, Any]:
    """Faz requisição POST e retorna (tempo, status, dados)."""
    try:
        start = time.time()
        resp = requests.post(
            f"{API_BASE}/{endpoint}",
            headers = get_headers(),
            timeout = 900 
        )
        resp.raise_for_status() 
        return time.time() - start, resp.status_code, resp.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Erro na API (POST {endpoint}): {e}")
        return None, e.response.status_code if hasattr(e, 'response') else 500, None
    except Exception as e:
        st.error(f"Erro inesperado: {e}")
        return None, 500, None

def api_get(endpoint: str, params: dict = None) -> tuple[float | None, int, Any]:
    """Faz requisição GET e retorna (tempo, status, dados)."""
    try:
        start = time.time()
        resp = requests.get(
            f"{API_BASE}/consultas/{endpoint}",
            params=params,
            headers=get_headers(),
            timeout=600
        )
        resp.raise_for_status() 
        tempo = time.time() - start
        return tempo, resp.status_code, resp.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Erro na API (GET {endpoint}): {e}")
        return None, e.response.status_code if hasattr(e, 'response') else 500, None
    except json.JSONDecodeError as e:
        st.error(f"Erro ao decodificar JSON: {e}")
        return None, 500, None
    except Exception as e:
        st.error(f"Erro inesperado: {e}")
        return None, 500, None

def api_stream_gen(endpoint: str, params: dict = None) -> Generator[Dict[str, Any], None, None]:
    """Faz requisição com streaming e "produz" (yield) cada item NDJSON."""
    if params is None:
        params = {}
    params["formato"] = "ndjson" # NDJSON é mais robusto para streaming
    
    try:
        with requests.get(
            f"{API_BASE}/consultas/{endpoint}",
            params=params,
            headers=get_headers(),
            timeout=600,
            stream=True 
        ) as resp:
            resp.raise_for_status() 
            
            buffer = b""
            for chunk in resp.iter_content(chunk_size = 8192):
                if not chunk:
                    continue
                    
                buffer += chunk
                lines = buffer.split(b'\n')
                buffer = lines[-1] 
                
                for line in lines[:-1]:
                    line_stripped = line.strip()
                    if line_stripped:
                        try:
                            yield json.loads(line_stripped.decode('utf-8'))
                        except json.JSONDecodeError:
                            st.warning(f"Ignorando linha mal formatada: {line_stripped[:50]}...")
            
            if buffer.strip():
                try:
                    yield json.loads(buffer.strip().decode('utf-8'))
                except json.JSONDecodeError:
                    st.warning(f"Ignorando linha final mal formatada: {buffer[:50]}...")
                    
    except requests.exceptions.RequestException as e:
        st.error(f"Erro na API (Stream {endpoint}): {e}")
    except Exception as e:
        st.error(f"Erro inesperado no stream: {e}")

# ===================================================================
# LÓGICA DE BENCHMARK 
# ===================================================================

def _run_query(endpoint: str, params: dict, usar_stream: bool) -> tuple[float | None, Any, List[Any]]:
    """
    Helper: Roda uma única consulta (stream ou get) e retorna 
    (tempo_total, dados_completos, amostra_dados).
    """
    start_time = time.time()
    
    # Copia params para evitar mutação
    query_params = params.copy() if params else {}

    if usar_stream:
        registros = []
        amostra = []
        try:
            # Rota de streaming (ex: beneficiarios-responsaveis)
            for item in api_stream_gen(endpoint, query_params):
                if len(amostra) < 50:
                    amostra.append(item)
                registros.append(item) # Pode consumir muita memória se for grande
            
            tempo_total = time.time() - start_time
            return tempo_total, registros, amostra
        
        except Exception as e:
            st.error(f"Erro durante o streaming da query: {e}")
            return None, [], []
            
    else:
        # Rota de agregação ou lista (GET normal)
        # Adiciona stream=False para rotas que precisam (ex: por-nome)
        if "limit" in query_params:
            query_params["stream"] = False 
            
        tempo_api, code, data = api_get(endpoint, query_params)
        
        if tempo_api is not None:
            amostra = []
            if isinstance(data, list):
                amostra = data[:50]
            elif isinstance(data, dict):
                amostra = [data] # Agregação
            
            return tempo_api, data, amostra
        else:
            return None, data, []


def executar_benchmark(
    setup_key: str, 
    exec_endpoint: str, 
    params: dict, 
    extractor_fn: Callable, 
    usar_stream: bool = False
):
    """Executa o ciclo completo de benchmark"""
    
    if not st.session_state.get("token"):
        st.error("❌ Faça login primeiro")
        return None

    status = st.empty()
    
    with st.spinner("Executando benchmark..."):
        # 1. Apagar índice
        status.info("1/4: Apagando índices...")
        _, code, msg = api_post(f"setup/{setup_key}/apagar-indices")
        if code != 200:
            st.error(f"Erro ao apagar índices: {msg}")
            return None
        
        # 2. Consulta SEM índice
        status.info("2/4: Consultando SEM índice...")
        tempo_sem, data_sem, _ = _run_query(exec_endpoint, params, usar_stream)
        if tempo_sem is None:
            st.error(f"Erro na consulta sem índice: {data_sem}")
            return None
        
        # 3. Criar índice
        status.info("3/4: Criando índices...")
        tempo_create, code_create, msg_create = api_post(f"setup/{setup_key}/criar-indices")
        if tempo_create is None:
            st.error(f"Erro ao criar índices: {msg_create}")
            return None
        
        # 4. Consulta COM índice
        status.info("4/4: Consultando COM índice...")
        tempo_com, data_com, amostra_com = _run_query(exec_endpoint, params, usar_stream)
        if tempo_com is None:
            st.warning(f"Erro na consulta com índice: {data_com}")
        
        # Calcular resultados
        valor_sem = extractor_fn(data_sem)
        valor_com = extractor_fn(data_com) if tempo_com else None
        
        ganho = ((tempo_sem - tempo_com) / tempo_sem * 100) if tempo_com else None
        
        st.success("✅ Benchmark concluído!")
        
        return {
            "tempo_sem": tempo_sem,
            "tempo_com": tempo_com,
            "tempo_create": tempo_create,
            "valor_sem": valor_sem,
            "valor_com": valor_com,
            "ganho": ganho,
            "data_com": amostra_com # Apenas a amostra para exibir
        }


def exibir_resultados(resultado, col_name="Resultado"):
    """Exibe os resultados do benchmark (versão do dashboard.py)"""
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Tempo de Criação do Índice", f"{resultado['tempo_create']:.3f} s")
        
        if resultado['ganho'] is not None:
            if resultado['ganho'] > 0:
                st.success(f"🏆 Ganho: {resultado['ganho']:.2f}% mais rápido")
            else:
                st.warning(f"🚨 Perda: {abs(resultado['ganho']):.2f}% mais lento")
    
    with col2:
        df_data = {
            "Cenário": ["Sem Índice", "Com Índice"],
            "Tempo (s)": [resultado['tempo_sem'], resultado['tempo_com']],
            col_name: [resultado['valor_sem'], resultado['valor_com']]
        }
        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True)
    
    # Gráfico
    chart_df = df.set_index("Cenário")[["Tempo (s)"]]
    st.bar_chart(chart_df)

    # Amostra de dados (se houver)
    amostra = resultado.get('data_com', [])
    if isinstance(amostra, list) and len(amostra) > 0:
        with st.expander(f"📄 Amostra dos Dados (primeiros {len(amostra)} registros)"):
            st.dataframe(pd.DataFrame(amostra))


# ===================================================================
# --- CONFIGURAÇÃO CENTRALIZADA DA INTERFACE (com 6 abas) ---
# ===================================================================

# Definindo tipos para melhor autocompletar e verificação
InputType = Literal["text", "number", "slider"]

class BenchmarkInput(TypedDict):
    label: str
    key: str
    default: Any
    type: InputType
    kwargs: Dict[str, Any]

class BenchmarkConfig(TypedDict):
    id: str
    title: str
    header: str
    markdown: str
    setup_key: str
    api_endpoint: str
    usar_stream: bool
    extractor_fn: Callable
    layout_cols: int
    inputs: List[BenchmarkInput]
    col_name: str # Nome da coluna de resultados

# Esta lista agora comanda toda a interface
BENCHMARKS_CONFIG: List[BenchmarkConfig] = [
    {
        "id": "gasto_uf",
        "title": "💰 Gasto por UF",
        "header": "💰 Gasto por UF",
        "markdown": "Testa `JOIN` + `SUM` com filtro em `uf`",
        "setup_key": "gasto-uf",
        "api_endpoint": "total-gasto-por-uf",
        "usar_stream": False,
        "extractor_fn": lambda d: d.get("total", 0) if isinstance(d, dict) else 0,
        "layout_cols": 1,
        "inputs": [
            {"label": "UF (ex: CE)", "key": "uf", "default": "CE", "type": "text", "kwargs": {}},
        ],
        "col_name": "Total (R$)"
    },
    {
        "id": "contagem_municipio",
        "title": "🏙️ Contagem Município",
        "header": "🏙️ Contagem Município",
        "markdown": "Testa `ILIKE '%termo%'` com índices `GIN/TRGM`",
        "setup_key": "contagem-municipio",
        "api_endpoint": "beneficiarios-por-municipio",
        "usar_stream": False,
        "extractor_fn": lambda d: d.get("quantidade", 0) if isinstance(d, dict) else 0,
        "layout_cols": 2,
        "inputs": [
            {"label": "UF", "key": "uf", "default": "CE", "type": "text", "kwargs": {}},
            {"label": "Município", "key": "municipio", "default": "AQUIRAZ", "type": "text", "kwargs": {}},
        ],
        "col_name": "Quantidade"
    },
    {
        "id": "busca_nome",
        "title": "🔠 Busca por Nome",
        "header": "🔠 Busca por Nome",
        "markdown": "Testa `ILIKE 'termo%'` com índices `B-Tree`. (Força GET com `stream=False`)",
        "setup_key": "por-nome",
        "api_endpoint": "beneficiarios-por-nome",
        "usar_stream": False, # Usar GET normal com stream=False
        "extractor_fn": lambda d: len(d) if isinstance(d, list) else 0,
        "layout_cols": 2,
        "inputs": [
            {"label": "Nome", "key": "nome", "default": "MARIA", "type": "text", "kwargs": {}},
            {"label": "Limite", "key": "limit", "default": 50, "type": "slider", "kwargs": {"min_value": 10, "max_value": 500}},
        ],
        "col_name": "Registros"
    },
    {
        "id": "busca_parcela",
        "title": "🎁 Busca por Parcela",
        "header": "🎁 Busca por N° Parcela",
        "markdown": "Busca beneficiários com parcelas > valor. (Força GET com `stream=False`)",
        "setup_key": "multiplas-parcelas", 
        "api_endpoint": "beneficiarios-multiplas-parcelas",
        "usar_stream": False, # Usar GET normal com stream=False
        "extractor_fn": lambda d: len(d) if isinstance(d, list) else 0,
        "layout_cols": 3,
        "inputs": [
            {"label": "UF", "key": "uf", "default": "SP", "type": "text", "kwargs": {}},
            {"label": "Parcela >", "key": "min_parcela", "default": 1, "type": "number", "kwargs": {"min_value": 0}},
            {"label": "Limite", "key": "limit", "default": 50, "type": "slider", "kwargs": {"min_value": 10, "max_value": 500}},
        ],
        "col_name": "Registros"
    },
    {
        "id": "benef_responsaveis",
        "title": "👥 Beneficiários Responsáveis",
        "header": "👥 Beneficiários Responsáveis",
        "markdown": "Encontra beneficiários que também são responsáveis (Usa **Streaming**)",
        "setup_key": "beneficiarios-responsaveis",
        "api_endpoint": "beneficiarios-responsaveis",
        "usar_stream": True, 
        "extractor_fn": lambda d: len(d) if isinstance(d, list) else 0,
        "layout_cols": 2,
        "inputs": [
            {"label": "UF", "key": "uf", "default": "SP", "type": "text", "kwargs": {}},
        ],
        "col_name": "Registros"
    },
]


# ===================================================================
# INTERFACE (Agora gerada dinamicamente)
# ===================================================================

st.title("📊 Benchmark de Consultas — Auxílio Emergencial")
st.markdown("Compare o desempenho de consultas com e sem índices")

if not st.session_state.get("token"):
    st.warning("⚠️ Faça login pela barra lateral para executar os benchmarks")
    st.stop()

# Cria as abas a partir da configuração
tab_titles = [b['title'] for b in BENCHMARKS_CONFIG]
tab_titles.append("🆔 Busca por NIS") # Adiciona a aba estática
tabs = st.tabs(tab_titles)

# Itera sobre a configuração e as abas criadas
for tab, benchmark in zip(tabs[:-1], BENCHMARKS_CONFIG):
    with tab:
        st.header(benchmark['header'])
        st.markdown(benchmark['markdown'])
        
        params = {}
        input_key_prefix = f"{benchmark['id']}_"
        
        # Cria colunas de layout
        cols = st.columns(benchmark['layout_cols'])
        
        # Itera e cria os widgets de input
        for i, inp in enumerate(benchmark['inputs']):
            col = cols[i % benchmark['layout_cols']]
            input_key = f"{input_key_prefix}{inp['key']}"
            input_widget = None
            val = None

            if inp['type'] == 'text':
                val = col.text_input(
                    inp['label'], 
                    inp['default'], 
                    key=input_key, 
                    **inp['kwargs']
                )
                params[inp['key']] = str(val).upper()
                
            elif inp['type'] == 'number':
                val = col.number_input(
                    inp['label'], 
                    value=inp['default'], 
                    key=input_key, 
                    **inp['kwargs']
                )
                params[inp['key']] = int(val)
            
            elif inp['type'] == 'slider':
                val = col.slider(
                    inp['label'], 
                    value=inp['default'], 
                    key=input_key, 
                    **inp['kwargs']
                )
                params[inp['key']] = int(val)

        # Chave de botão e de sessão únicas
        button_key = f"btn_{benchmark['id']}"
        session_state_key = f"r_{benchmark['id']}"

        if st.button("Executar Benchmark", key=button_key):
            resultado = executar_benchmark(
                setup_key=benchmark['setup_key'],
                exec_endpoint=benchmark['api_endpoint'],
                params=params,
                extractor_fn=benchmark['extractor_fn'],
                usar_stream=benchmark['usar_stream']
            )
            if resultado:
                st.session_state[session_state_key] = resultado
        
        if session_state_key in st.session_state:
            exibir_resultados(
                st.session_state[session_state_key], 
                col_name=benchmark['col_name']
            )

# Aba 6: Busca por NIS (utilitário, não-benchmark)
with tabs[-1]:
    st.header("🆔 Busca por NIS")
    st.markdown("Busca simples por chave primária (não é benchmark)")
    
    nis = st.text_input("NIS", "16110218880", key="nis6")
    
    if st.button("Buscar", key="btn6"):
        tempo, status, data = api_get(f"beneficiario/{nis}") 
        
        if tempo and status == 200:
            st.success(f"Encontrado em {tempo:.6f}s")
            st.json(data)
        else:
            st.error(f"Erro {status}: {data}")

st.markdown("---")
st.caption("Desenvolvido para o Projeto de Auxílio Emergencial⚙️")