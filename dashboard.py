import streamlit as st
import requests
import time
import pandas as pd
import json

# ===================================================================
# CONFIGURAÇÃO GERAL
# ===================================================================
API_BASE = "http://api:8000/api/v1" 
st.set_page_config(page_title="Benchmark Full Stream", layout="wide", page_icon="⚡")

st.markdown("""
<style>
    div[data-testid="stMetricValue"] { font-size: 1.8rem; }
</style>
""", unsafe_allow_html=True)

# ===================================================================
# FUNÇÕES DE CONSUMO (OTIMIZADAS PARA BIG DATA)
# ===================================================================

def api_stream_consumption(endpoint: str, params: dict) -> tuple[float | None, dict]:
    """
    Consome o stream NDJSON inteiramente, mas NÃO guarda tudo em RAM.
    Apenas conta as linhas e mede o tempo.
    """
    params["formato"] = "ndjson"
    params["stream"] = "true" # Força stream explicitamente
    
    amostra = []
    total_linhas = 0
    start = time.time()
    
    try:
        with requests.get(
            f"{API_BASE}/consultas/{endpoint}",
            params=params,
            stream=True,
            timeout=600 # Timeout generoso para queries pesadas
        ) as resp:
            if resp.status_code != 200: return None, resp.text
            
            # Itera linha a linha sem carregar o arquivo todo
            for line in resp.iter_lines():
                if line:
                    total_linhas += 1
                    if len(amostra) < 3: # Guarda só 3 registros de exemplo
                        try: amostra.append(json.loads(line))
                        except: pass
            
        tempo = time.time() - start
        
        # Retorna estatísticas em vez dos dados brutos
        resultado = {
            "total_processado": total_linhas,
            "amostra_visual": amostra
        }
        return tempo, resultado
        
    except Exception as e:
        return None, str(e)

# ===================================================================
# ENGINE DE BENCHMARK (MODO STREAM ONLY)
# ===================================================================

def executar_benchmark_stream(
    endpoint: str, 
    base_params: dict,
    desc_a: str,
    desc_b: str
):
    my_bar = st.progress(0, text="Iniciando Benchmark via Stream...")
    
    try:
        # --- CENÁRIO A: SEM ÍNDICE (STREAM) ---
        my_bar.progress(10, text=f"🐌 {desc_a} (Forçando Seq Scan no Stream)...")
        params_a = base_params.copy()
        params_a["usar_indice"] = False
        
        t_a, data_a = api_stream_consumption(endpoint, params_a)
        
        if t_a is None:
            st.error(f"Erro em {desc_a}: {data_a}"); my_bar.empty(); return None

        # --- CENÁRIO B: COM ÍNDICE (STREAM) ---
        my_bar.progress(50, text=f"🚀 {desc_b} (Usando Índices no Stream)...")
        params_b = base_params.copy()
        params_b["usar_indice"] = True
        
        t_b, data_b = api_stream_consumption(endpoint, params_b)
        
        if t_b is None:
            st.error(f"Erro em {desc_b}: {data_b}"); my_bar.empty(); return None

        my_bar.progress(100, text="Finalizado!")
        time.sleep(0.5)
        my_bar.empty()

        # Cálculos
        speedup = t_a / t_b if t_b > 0 else 0
        ganho_pct = ((t_a - t_b) / t_a * 100) if t_a > 0 else 0

        return {
            "labels": (desc_a, desc_b),
            "tempos": (t_a, t_b),
            "speedup": speedup,
            "ganho_pct": ganho_pct,
            "qtd_linhas": data_b['total_processado'],
            "amostra": data_b['amostra_visual']
        }

    except Exception as e:
        st.error(f"Erro fatal: {e}"); return None

# ===================================================================
# VISUALIZAÇÃO
# ===================================================================

def exibir_dashboard(res: dict):
    st.divider()
    l_a, l_b = res['labels']
    t_a, t_b = res['tempos']
    
    # KPIs
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric(f"Tempo {l_a}", f"{t_a:.2f} s")
    with c2: 
        delta_color = "normal" if t_b < t_a else "inverse"
        st.metric(f"Tempo {l_b}", f"{t_b:.2f} s", delta=f"{res['ganho_pct']:.1f}%", delta_color=delta_color)
    with c3: st.metric("Speedup (Vezes)", f"{res['speedup']:.2f}x")
    with c4: st.metric("Linhas Baixadas", f"{res['qtd_linhas']:,}")

    # Gráfico
    st.subheader("⏱️ Comparativo de Tempo Total (Download + Processamento)")
    df = pd.DataFrame({"Cenário": [l_a, l_b], "Segundos": [t_a, t_b]})
    st.bar_chart(df, x="Cenário", y="Segundos", color="Cenário")
    
    with st.expander("🔍 Ver Amostra (Primeiros registros do Stream)"):
        st.json(res['amostra'])

# ===================================================================
# CONFIGURAÇÃO DOS TESTES
# ===================================================================

BENCHMARKS_CONFIG = [
    {
        "id": "list_full",
        "title": "📋 Listar Beneficiários (Big Data)",
        "desc": "Baixa lista massiva filtrada. Compara 'Sem Índice' vs 'Com Índice', ambos via Streaming para não estourar memória.",
        "endpoint": "listar-beneficiarios",
        "inputs": [
            {"label": "UF (Obrigatório)", "key": "uf", "val": "AC", "type": "text"}
        ]
    },
    {
        "id": "name_full",
        "title": "🔍 Busca por Nome (Big Data)",
        "desc": "Busca textual em toda a base. Compara Full Scan vs Índice Trigram, via Streaming.",
        "endpoint": "beneficiarios-por-nome",
        "inputs": [
            {"label": "Nome Contém", "key": "nome", "val": "MARIA", "type": "text"}
        ]
    },
    {
        "id": "agg_uf",
        "title": "💰 Agregação Gasto (Analítico)",
        "desc": "Calcula total gasto (Single Result). O stream aqui é interno no banco, retorno é JSON simples.",
        "endpoint": "total-gasto-por-uf",
        "inputs": [
            {"label": "UF", "key": "uf", "val": "CE", "type": "text"}
        ]
    }
]

# ===================================================================
# UI PRINCIPAL
# ===================================================================

st.title("🚀 Benchmark: Database & Stream")
st.caption("Comparação de performance 'Com Índice' vs 'Sem Índice' usando transporte via Stream para grandes volumes.")

tabs = st.tabs([b['title'] for b in BENCHMARKS_CONFIG])

for tab, cfg in zip(tabs, BENCHMARKS_CONFIG):
    with tab:
        st.info(f"ℹ️ {cfg['desc']}")
        cols = st.columns(len(cfg['inputs']) + 1)
        params = {}
        
        for i, inp in enumerate(cfg['inputs']):
            key_widget = f"{cfg['id']}_{inp['key']}"
            if inp['type'] == 'text':
                val = cols[i].text_input(inp['label'], inp['val'], key=key_widget)
                params[inp['key']] = str(val).upper()
            elif inp['type'] == 'number':
                val = cols[i].number_input(inp['label'], value=inp['val'], key=key_widget)
                params[inp['key']] = int(val)

        with cols[-1]:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔥 Rodar", key=f"btn_{cfg['id']}", use_container_width=True):
                # Decide qual função usar baseada no endpoint (agregação vs listagem)
                if cfg['id'] == "agg_uf":
                     # Agregação retorna JSON pequeno, usa lógica antiga (mas simplificada aqui para manter padrão)
                     # Neste caso adaptamos para usar a mesma funcão de stream_consumption pois ela lida com JSON também
                     pass 
                
                res = executar_benchmark_stream(
                    endpoint=cfg['endpoint'],
                    base_params=params,
                    desc_a="Sem Índice",
                    desc_b="Com Índice"
                )
                if res: st.session_state[f"res_{cfg['id']}"] = res

        if f"res_{cfg['id']}" in st.session_state:
            exibir_dashboard(st.session_state[f"res_{cfg['id']}"])
