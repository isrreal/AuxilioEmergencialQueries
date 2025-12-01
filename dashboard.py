import streamlit as st
import requests
import time
import pandas as pd
import json
from typing import Generator, Any, Dict, List, Literal, TypedDict, Callable

# Configuração
API_BASE = "http://api:8000/api/v1"
st.set_page_config(page_title="Monitor de Consultas", layout="wide")

# ===================================================================
# AUTENTICAÇÃO (Mantida igual)
# ===================================================================

def login(username: str, password: str) -> str | None:
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
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}

st.sidebar.title("🔐 Autenticação")

if "token" not in st.session_state:
    st.session_state.token = None

if not st.session_state.token:
    username = st.sidebar.text_input("Usuário")
    password = st.sidebar.text_input("Senha", type = "password")
    
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
# FUNÇÕES DE API BÁSICAS (POST removido pois não é mais usado no fluxo principal)
# ===================================================================

def api_get(endpoint: str, params: dict = None) -> tuple[float | None, int, Any]:
    try:
        start = time.time()
        resp = requests.get(
            f"{API_BASE}/consultas/{endpoint}",
            params = params,
            headers = get_headers(),
            timeout = 600
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
    if params is None: params = {}
    params["formato"] = "ndjson"
    
    try:
        with requests.get(
            f"{API_BASE}/consultas/{endpoint}",
            params = params,
            headers = get_headers(),
            timeout = 600,
            stream = True 
        ) as resp:
            resp.raise_for_status() 
            buffer = b""
            for chunk in resp.iter_content(chunk_size = 8192):
                if not chunk: continue
                buffer += chunk
                lines = buffer.split(b'\n')
                buffer = lines[-1] 
                for line in lines[:-1]:
                    line_stripped = line.strip()
                    if line_stripped:
                        try:
                            yield json.loads(line_stripped.decode('utf-8'))
                        except json.JSONDecodeError:
                            pass
            if buffer.strip():
                try:
                    yield json.loads(buffer.strip().decode('utf-8'))
                except json.JSONDecodeError:
                    pass
    except requests.exceptions.RequestException as e:
        st.error(f"Erro na API (Stream {endpoint}): {e}")
    except Exception as e:
        st.error(f"Erro inesperado no stream: {e}")

# ===================================================================
# LÓGICA DE CONSULTA (REFATORADA)
# ===================================================================

def _run_query(endpoint: str, params: dict, usar_stream: bool) -> tuple[float | None, Any, List[Any]]:
    start_time = time.time()
    query_params = params.copy() if params else {}

    if usar_stream:
        registros = []
        amostra = []
        try:
            for item in api_stream_gen(endpoint, query_params):
                if len(amostra) < 50:
                    amostra.append(item)
                registros.append(item)
            tempo_total = time.time() - start_time
            return tempo_total, registros, amostra
        except Exception as e:
            st.error(f"Erro durante o streaming da query: {e}")
            return None, [], []
    else:
        if "limit" in query_params:
            query_params["stream"] = False 
        tempo_api, code, data = api_get(endpoint, query_params)
        if tempo_api is not None:
            amostra = []
            if isinstance(data, list):
                amostra = data[:50]
            elif isinstance(data, dict):
                amostra = [data]
            return tempo_api, data, amostra
        else:
            return None, data, []

def executar_consulta( # Renomeado de executar_benchmark
    exec_endpoint: str, 
    params: dict, 
    extractor_fn: Callable, 
    usar_stream: bool = False
):
    """Executa apenas a consulta e mede o tempo."""
    
    if not st.session_state.get("token"):
        st.error("❌ Faça login primeiro")
        return None
    
    with st.spinner("Executando consulta..."):
        # AQUI FOI REMOVIDA A LÓGICA DE APAGAR/CRIAR ÍNDICES
        
        tempo, data, amostra = _run_query(exec_endpoint, params, usar_stream)
        
        if tempo is None:
            st.error(f"Falha na execução: {data}")
            return None
        
        valor = extractor_fn(data)
        
        st.success("✅ Consulta concluída!")
        
        return {
            "tempo": tempo,
            "valor": valor,
            "data": amostra
        }

def exibir_resultados(resultado, col_name="Resultado"):
    """Exibe os resultados de forma simplificada (sem comparação)."""
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("⏱️ Tempo de Execução", f"{resultado['tempo']:.4f} s")
    
    with col2:
        st.metric(f"📊 {col_name}", f"{resultado['valor']}")
    
    # Amostra de dados
    amostra = resultado.get('data', [])
    if isinstance(amostra, list) and len(amostra) > 0:
        st.markdown("### 📄 Amostra dos Dados")
        st.dataframe(pd.DataFrame(amostra), use_container_width = True)

# ===================================================================
# CONFIGURAÇÃO DA INTERFACE
# ===================================================================

InputType = Literal["text", "number", "slider"]

class BenchmarkInput(TypedDict):
    label: str; key: str; default: Any; type: InputType; kwargs: Dict[str, Any]

class BenchmarkConfig(TypedDict):
    id: str; title: str; header: str; markdown: str
    api_endpoint: str; usar_stream: bool; extractor_fn: Callable
    layout_cols: int; inputs: List[BenchmarkInput]; col_name: str

# Setup Key removido daqui
BENCHMARKS_CONFIG: List[BenchmarkConfig] = [
    {
        "id": "gasto_uf",
        "title": "💰 Gasto por UF",
        "header": "💰 Gasto por UF",
        "markdown": "Consulta `SUM` agregada por estado.",
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
        "markdown": "Consulta contagem com filtro de texto.",
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
        "markdown": "Busca textual por nome parcial.",
        "api_endpoint": "beneficiarios-por-nome",
        "usar_stream": False,
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
        "markdown": "Filtro numérico simples.",
        "api_endpoint": "beneficiarios-multiplas-parcelas",
        "usar_stream": False,
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
        "markdown": "Join complexo via Streaming.",
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
# CONSTRUÇÃO DAS ABAS
# ===================================================================

st.title("🔎 Explorador de Consultas — Auxílio Emergencial")
st.markdown("Execute consultas diretamente na API.")

if not st.session_state.get("token"):
    st.warning("⚠️ Faça login pela barra lateral para executar as consultas")
    st.stop()

tab_titles = [b['title'] for b in BENCHMARKS_CONFIG]
tab_titles.append("🆔 Busca por NIS")
tabs = st.tabs(tab_titles)

for tab, benchmark in zip(tabs[:-1], BENCHMARKS_CONFIG):
    with tab:
        st.header(benchmark['header'])
        st.markdown(benchmark['markdown'])
        
        params = {}
        input_key_prefix = f"{benchmark['id']}_"
        cols = st.columns(benchmark['layout_cols'])
        
        for i, inp in enumerate(benchmark['inputs']):
            col = cols[i % benchmark['layout_cols']]
            input_key = f"{input_key_prefix}{inp['key']}"
            
            if inp['type'] == 'text':
                val = col.text_input(inp['label'], inp['default'], key=input_key, **inp['kwargs'])
                params[inp['key']] = str(val).upper()
            elif inp['type'] == 'number':
                val = col.number_input(inp['label'], value=inp['default'], key=input_key, **inp['kwargs'])
                params[inp['key']] = int(val)
            elif inp['type'] == 'slider':
                val = col.slider(inp['label'], value=inp['default'], key=input_key, **inp['kwargs'])
                params[inp['key']] = int(val)

        button_key = f"btn_{benchmark['id']}"
        session_state_key = f"r_{benchmark['id']}"

        if st.button("Executar Consulta", key=button_key): # Texto do botão alterado
            # Chamada simplificada sem setup_key
            resultado = executar_consulta(
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

# Aba Final (Busca por NIS - sem alterações de lógica)
with tabs[-1]:
    st.header("🆔 Busca por NIS")
    nis = st.text_input("NIS", "16110218880", key="nis6")
    if st.button("Buscar", key="btn6"):
        tempo, status, data = api_get(f"beneficiario/{nis}") 
        if tempo and status == 200:
            st.success(f"Encontrado em {tempo:.6f}s")
            st.json(data)
        else:
            st.error(f"Erro {status}: {data}")

st.markdown("---")
st.caption("Auxílio Emergencial - Query Runner ⚙️")