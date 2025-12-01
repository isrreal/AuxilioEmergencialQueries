import streamlit as st
import requests
import time
import pandas as pd
import json
from typing import Generator, Any, Dict, List, Literal, TypedDict, Callable

# ===================================================================
# CONFIGURAÇÃO GERAL
# ===================================================================
API_BASE = "http://api:8000/api/v1"
st.set_page_config(page_title="Benchmark de Índices", layout="wide", page_icon="⚡")

# Estilo CSS customizado para métricas
st.markdown("""
<style>
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
    }
</style>
""", unsafe_allow_html=True)

# ===================================================================
# AUTENTICAÇÃO
# ===================================================================

def login(username: str, password: str) -> str | None:
    try:
        resp = requests.post(
            f"{API_BASE}/login",
            data = {"username": username, "password": password},
            timeout = 10
        )
        if resp.status_code == 200:
            return resp.json().get("access_token")
    except Exception as e:
        st.sidebar.error(f"Erro de conexão: {e}")
    return None

def get_headers() -> dict:
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}

# Sidebar de Login
st.sidebar.title("🔐 Acesso")
if "token" not in st.session_state:
    st.session_state.token = None

if not st.session_state.token:
    u = st.sidebar.text_input("Usuário")
    p = st.sidebar.text_input("Senha", type = "password")
    if st.sidebar.button("Entrar"):
        t = login(u, p)
        if t:
            st.session_state.token = t
            st.rerun()
        else:
            st.sidebar.error("Falha no login")
else:
    st.sidebar.success("Conectado")
    if st.sidebar.button("Sair"):
        st.session_state.token = None
        st.rerun()

# ===================================================================
# FUNÇÕES DE API (GET e STREAM)
# ===================================================================

def api_get(endpoint: str, params: dict = None) -> tuple[float | None, int, Any]:
    """Executa GET padrão e mede o tempo."""
    try:
        start = time.time()
        resp = requests.get(
            f"{API_BASE}/consultas/{endpoint}",
            params = params,
            headers = get_headers(),
            timeout = 600
        )
        # Força erro se status != 200
        if resp.status_code != 200:
            return None, resp.status_code, resp.text
            
        tempo = time.time() - start
        return tempo, resp.status_code, resp.json()
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None, 500, str(e)

def api_stream_gen(endpoint: str, params: dict = None) -> Generator[Dict[str, Any], None, None]:
    """Gerador que consome NDJSON via streaming."""
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
            if resp.status_code != 200:
                st.error(f"Erro API ({resp.status_code}): {resp.text}")
                return

            buffer = b""
            for chunk in resp.iter_content(chunk_size=8192):
                if not chunk: continue
                buffer += chunk
                lines = buffer.split(b'\n')
                buffer = lines[-1] 
                for line in lines[:-1]:
                    if line.strip():
                        try:
                            yield json.loads(line.strip().decode('utf-8'))
                        except: pass
            if buffer.strip():
                try: yield json.loads(buffer.strip().decode('utf-8'))
                except: pass
    except Exception as e:
        st.error(f"Erro no stream: {e}")

# ===================================================================
# ENGINE DE BENCHMARK
# ===================================================================

def _run_single_query(endpoint: str, params: dict, usar_stream: bool):
    """Executa uma única chamada (com ou sem índice) e retorna métricas."""
    start_global = time.time()
    
    # Define se usa stream=True/False na query string (para paginação)
    # A exceção são rotas que SEMPRE são stream (como beneficiarios-responsaveis)
    q_params = params.copy()
    if "limit" in q_params and not usar_stream:
        q_params["stream"] = False

    registros = []
    amostra = []
    
    try:
        if usar_stream:
            # Consome o gerador inteiro para medir o tempo total de processamento
            for item in api_stream_gen(endpoint, q_params):
                if len(amostra) < 10: amostra.append(item)
                # Não guardamos tudo em memória para não travar o streamlit em testes grandes
                # apenas contamos se necessário, ou guardamos em chunks
                pass 
            tempo_total = time.time() - start_global
            # Se for stream, não temos o 'dado' completo carregado, apenas amostra
            return tempo_total, amostra
        else:
            # Requisição normal (bloqueante)
            t, code, data = api_get(endpoint, q_params)
            if t is None: return None, data # data aqui é a msg de erro
            
            if isinstance(data, list):
                amostra = data[:10]
            elif isinstance(data, dict):
                amostra = [data]
            return t, amostra

    except Exception as e:
        return None, str(e)


def executar_benchmark_comparativo(
    endpoint: str, 
    base_params: dict, 
    extractor_fn: Callable, 
    usar_stream: bool
):
    """
    Roda o teste A/B:
    1. Sem Índice (usar_indice=False)
    2. Com Índice (usar_indice=True)
    """
    if not st.session_state.token:
        st.error("Faça login.")
        return None

    results = {}
    
    # Barra de progresso visual
    progress_text = "Iniciando benchmark..."
    my_bar = st.progress(0, text=progress_text)

    try:
        # --- ETAPA 1: SEM ÍNDICE ---
        my_bar.progress(10, text = "🐌 Rodando SEM índice (Forçando Full Scan)...")
        params_sem = base_params.copy()
        params_sem["usar_indice"] = False
        
        t_sem, data_sem = _run_single_query(endpoint, params_sem, usar_stream)
        
        if t_sem is None:
            st.error(f"Falha no teste sem índice: {data_sem}")
            my_bar.empty()
            return None

        # --- ETAPA 2: COM ÍNDICE ---
        my_bar.progress(60, text = "🚀 Rodando COM índice (B-Tree/GIN)...")
        params_com = base_params.copy()
        params_com["usar_indice"] = True
        
        t_com, data_com = _run_single_query(endpoint, params_com, usar_stream)
        
        if t_com is None:
            st.error(f"Falha no teste com índice: {data_com}")
            my_bar.empty()
            return None

        my_bar.progress(100, text = "Finalizado!")
        time.sleep(0.5)
        my_bar.empty()

        # Cálculos
        speedup = t_sem / t_com if t_com > 0 else 0
        ganho_pct = ((t_sem - t_com) / t_sem * 100) if t_sem > 0 else 0

        return {
            "tempo_sem": t_sem,
            "tempo_com": t_com,
            "speedup": speedup,
            "ganho_pct": ganho_pct,
            "amostra": data_com, # Mostra dados da versão rápida
            "resultado_valor": extractor_fn(data_com[0]) if data_com and len(data_com) > 0 and isinstance(data_com[0], dict) else len(data_com)
        }

    except Exception as e:
        st.error(f"Erro fatal no benchmark: {e}")
        return None

# ===================================================================
# EXIBIÇÃO DE RESULTADOS
# ===================================================================

def exibir_dashboard(res: dict, col_name_resultado: str):
    st.divider()
    
    # 1. KPIs Principais
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("🐌 Tempo (Sem Índice)", f"{res['tempo_sem']:.3f} s")
    with c2:
        delta_color = "normal" if res['tempo_com'] < res['tempo_sem'] else "inverse"
        st.metric("🚀 Tempo (Com Índice)", f"{res['tempo_com']:.3f} s", delta = f"{res['ganho_pct']:.1f}% mais rápido", delta_color = delta_color)
    with c3:
        st.metric("⚡ Speedup (x Vezes)", f"{res['speedup']:.1f}x")
    with c4:
        st.metric(f"📊 {col_name_resultado}", f"{res['resultado_valor']}")

    # 2. Gráfico Comparativo
    c_chart, c_data = st.columns([1, 1])
    
    with c_chart:
        st.subheader("Comparação de Desempenho")
        df_chart = pd.DataFrame({
            "Cenário": ["Sem Índice", "Com Índice"],
            "Tempo (s)": [res['tempo_sem'], res['tempo_com']],
            "Cor": ["#FF4B4B", "#00CC96"] # Vermelho vs Verde
        })
        
        # Usando Altair nativo do Streamlit via bar_chart (simples) ou Vega-Lite
        st.bar_chart(df_chart, x="Cenário", y="Tempo (s)", color="Cenário")

    with c_data:
        st.subheader("Amostra dos Dados")
        if res.get('amostra'):
            st.dataframe(res['amostra'], height = 300, use_container_width = True)
        else:
            st.info("Nenhum dado retornado para amostra.")

# ===================================================================
# DEFINIÇÃO DOS TESTES (CONFIGURAÇÃO)
# ===================================================================

BENCHMARKS_CONFIG = [
    {
        "id": "gasto_uf",
        "title": "💰 Agregação (SUM + JOIN)",
        "desc": "Soma total de gastos por UF. O índice em `uf` e `nis` evita varrer toda a tabela de beneficiários e auxílios.",
        "endpoint": "total-gasto-por-uf",
        "stream": False,
        "inputs": [{"label": "UF", "key": "uf", "val": "CE", "type": "text"}],
        "extractor": lambda d: f"R$ {d.get('total', 0):,.2f}",
        "col_name": "Total Gasto"
    },
    {
        "id": "count_mun",
        "title": "🏙️ Busca Textual (ILIKE %term%)",
        "desc": "Conta beneficiários filtrando município. O índice GIN/Trigram otimiza buscas com `%` no início.",
        "endpoint": "beneficiarios-por-municipio",
        "stream": False,
        "inputs": [
            {"label": "UF", "key": "uf", "val": "CE", "type": "text"},
            {"label": "Município (Parte)", "key": "municipio", "val": "FORTALEZA", "type": "text"}
        ],
        "extractor": lambda d: f"{d.get('quantidade', 0)}",
        "col_name": "Qtd. Encontrada"
    },
    {
        "id": "busca_nome",
        "title": "🔠 Busca por Nome",
        "desc": "Busca textual parcial no nome. Com índice, o banco salta direto para os registros relevantes.",
        "endpoint": "beneficiarios-por-nome",
        "stream": False,
        "inputs": [
            {"label": "Nome (Parte)", "key": "nome", "val": "MARIA DAS DORES", "type": "text"},
            {"label": "Limite", "key": "limit", "val": 100, "type": "number"}
        ],
        "extractor": lambda d: "N/A", # Será calculado pelo tamanho da lista
        "col_name": "Registros Retornados"
    },
    {
        "id": "filtro_num",
        "title": "🔢 Filtro Numérico (Parcela)",
        "desc": "Filtra auxílios com número de parcela alto. Índice B-Tree em `parcela`.",
        "endpoint": "beneficiarios-multiplas-parcelas",
        "stream": False,
        "inputs": [
            {"label": "UF", "key": "uf", "val": "SP", "type": "text"},
            {"label": "Parcela >", "key": "min_parcela", "val": 5, "type": "number"},
            {"label": "Limite", "key": "limit", "val": 100, "type": "number"}
        ],
        "extractor": lambda d: "N/A",
        "col_name": "Registros"
    },
    {
        "id": "join_complexo",
        "title": "🕸️ Join Complexo (Streaming)",
        "desc": "Cruza Beneficiários com Auxílios e Responsáveis. Otimização massiva em Joins.",
        "endpoint": "beneficiarios-responsaveis",
        "stream": True, # Força stream mode
        "inputs": [{"label": "UF", "key": "uf", "val": "AC", "type": "text"}],
        "extractor": lambda d: "N/A",
        "col_name": "Registros Processados"
    }
]

# ===================================================================
# UI PRINCIPAL
# ===================================================================

st.title("🚀 Benchmark de Performance de Banco de Dados")
st.markdown("Comparativo em tempo real: **Com Índices** vs **Sem Índices (Full Scan)**.")

if not st.session_state.token:
    st.warning("⚠️ Realize login na barra lateral para acessar os testes.")
    st.stop()

tabs = st.tabs([b['title'] for b in BENCHMARKS_CONFIG])

for tab, cfg in zip(tabs, BENCHMARKS_CONFIG):
    with tab:
        st.markdown(f"**Cenário:** {cfg['desc']}")
        
        # Layout de inputs
        cols = st.columns(len(cfg['inputs']) + 1)
        params = {}
        
        # Gerar Inputs Dinamicamente
        for i, inp in enumerate(cfg['inputs']):
            key_widget = f"{cfg['id']}_{inp['key']}"
            if inp['type'] == 'text':
                val = cols[i].text_input(inp['label'], inp['val'], key = key_widget)
                params[inp['key']] = str(val).upper()
            elif inp['type'] == 'number':
                val = cols[i].number_input(inp['label'], value = inp['val'], key = key_widget)
                params[inp['key']] = int(val)

        # Botão de Ação
        with cols[-1]:
            st.markdown("<br>", unsafe_allow_html = True) # Espaçamento
            if st.button("🔥 Rodar Benchmark", key = f"btn_{cfg['id']}", use_container_width = True):
                
                # Executa
                resultado = executar_benchmark_comparativo(
                    endpoint = cfg['endpoint'],
                    base_params = params,
                    extractor_fn = cfg['extractor'],
                    usar_stream = cfg['stream']
                )
                
                # Salva no estado para persistir ao recarregar
                if resultado:
                    st.session_state[f"res_{cfg['id']}"] = resultado

        # Exibe Resultados se existirem
        if f"res_{cfg['id']}" in st.session_state:
            exibir_dashboard(
                st.session_state[f"res_{cfg['id']}"], 
                cfg['col_name']
            )

st.divider()
st.caption("Sistema de Demonstração de Otimização SQL - PostgreSQL 15 + FastAPI")