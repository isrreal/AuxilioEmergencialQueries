import streamlit as st
import requests
import time
import pandas as pd

API_BASE_URL = "http://api:8000/api/v1/consultas"
SETUP_ROUTES_URL = "http://api:8000/api/v1/setup"

LOGIN_URL = "http://api:8000/api/v1/login" 

st.set_page_config(page_title="Benchmark Índices", layout="wide")


# ==============================
# <--- Seção de Login
# ==============================
st.sidebar.title("Login")

if "api_token" not in st.session_state:
    st.session_state["api_token"] = None

username = st.sidebar.text_input("Usuário")
password = st.sidebar.text_input("Senha", type="password")

if st.sidebar.button("Logar"):
    login_data = {"username": username, "password": password}
    try:
        resp = requests.post(LOGIN_URL, data=login_data)
        
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            st.session_state["api_token"] = token 
            st.sidebar.success("Login bem-sucedido!")
            st.experimental_rerun() 
            st.session_state["api_token"] = None
            st.sidebar.error(f"Falha no login (Status {resp.status_code}): {resp.json().get('detail', 'Erro')}")
            
    except requests.exceptions.ConnectionError:
        st.sidebar.error(f"Erro de conexão. A API está online em {LOGIN_URL}?")
    except Exception as e:
        st.sidebar.error(f"Erro ao conectar: {e}")

if st.session_state["api_token"]:
    st.sidebar.success("✅ Autenticado")
    if st.sidebar.button("Logout"):
        st.session_state["api_token"] = None
        st.experimental_rerun()
else:
    st.sidebar.warning("⚠️ Não autenticado. Faça login para executar benchmarks de setup.")


# ==============================
# Funções Utilitárias
# ==============================

def request_api(method, endpoint, params=None, timeout=600):
    """
    Faz requisição à API e retorna (tempo, status, dados).
    Direciona a chamada para a URL base correta (setup ou consultas).
    """
    
    if endpoint.startswith("executar/"):
        url = f"{API_BASE_URL}/{endpoint}"
    elif endpoint.startswith("setup/"):
        clean_endpoint = endpoint.replace("setup/", "", 1)
        url = f"{SETUP_ROUTES_URL}/{clean_endpoint}"
    else:
        url = f"{API_BASE_URL}/{endpoint}"
        
    headers = {}
    if st.session_state.get("api_token"):
        headers["Authorization"] = f"Bearer {st.session_state['api_token']}"

    inicio = time.time()
    
    try:
        if method == "GET":
            resp = requests.get(url, params = params, timeout = timeout, headers = headers)
        else:
            resp = requests.post(url, timeout = timeout, headers = headers)
        
        duracao = time.time() - inicio
        
        if resp.status_code == 200:
            return duracao, resp.status_code, resp.json()
        
        if resp.status_code == 401:
             st.error("Erro 401: Não autorizado. Seu token pode ter expirado. Faça login novamente.")
             st.session_state["api_token"] = None 
             
        detail = resp.json().get('detail', 'Erro desconhecido')
        return None, resp.status_code, detail
    
    except requests.exceptions.Timeout:
        return None, 504, "Timeout (a operação pode estar em andamento)"
    except requests.exceptions.ConnectionError:
        return None, 503, f"Erro de conexão. A API está online em {url}?"
    except Exception as e:
        return None, 500, str(e)


def executar_benchmark(setup_key, exec_endpoint, params, extractor_fn):
    """Executa o ciclo completo de benchmark"""
    
    # <--- Checagem de login
    if not st.session_state.get("api_token"):
        st.error("Você precisa estar logado para executar um benchmark (criar/apagar índices).")
        return None
        
    with st.spinner("Executando benchmark..."):
        # 1. Apagar índice
        st.write(f"1/4: Apagando índices ('{setup_key}')...")
        _, status, msg = request_api("POST", f"setup/{setup_key}/apagar-indices", timeout=900)
        if status != 200:
            st.error(f"Erro ao apagar índices: {status} - {msg}")
            return None
        
        # 2. Consulta SEM índice
        st.write(f"2/4: Consultando SEM índice ('{exec_endpoint}')...")
        tempo_sem, status_sem, data_sem = request_api("GET", exec_endpoint, params)
        if tempo_sem is None:
            st.error(f"Erro na consulta sem índice: {status_sem} - {data_sem}")
            return None
        
        # 3. Criar índice
        st.write(f"3/4: Criando índices ('{setup_key}')...")
        tempo_create, status_create, msg_create = request_api("POST", f"setup/{setup_key}/criar-indices", timeout=900)
        if tempo_create is None:
            st.error(f"Erro ao criar índices: {status_create} - {msg_create}")
            return None
        
        # 4. Consulta COM índice
        st.write(f"4/4: Consultando COM índice ('{exec_endpoint}')...")
        tempo_com, status_com, data_com = request_api("GET", exec_endpoint, params)
        if tempo_com is None:
            st.warning(f"Erro na consulta com índice: {status_com} - {data_com}")
        
        # Calcular resultados
        valor_sem = extractor_fn(data_sem)
        valor_com = extractor_fn(data_com) if tempo_com else None
        
        ganho = ((tempo_sem - tempo_com) / tempo_sem * 100) if tempo_com and tempo_sem > 0 else None
        
        st.success("✅ Benchmark concluído!")
        
        return {
            "tempo_sem": tempo_sem,
            "tempo_com": tempo_com,
            "tempo_create": tempo_create,
            "valor_sem": valor_sem,
            "valor_com": valor_com,
            "ganho": ganho,
            "data_com": data_com
        }


def exibir_resultados(resultado, col_name="Resultado"):
    """Exibe os resultados do benchmark"""
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Tempo de Criação do Índice", f"{resultado['tempo_create']:.3f} s")
        
        if resultado['ganho'] is not None:
            if resultado['ganho'] > 0:
                st.success(f"🏆 Ganho: {resultado['ganho']:.2f}% mais rápido")
            else:
                st.warning(f"🚨 Perda: {abs(resultado['ganho']):.2f}% mais lento")
        else:
            st.info("Não foi possível calcular o ganho (um dos tempos é 0 ou nulo).")

    
    with col2:
        df = pd.DataFrame({
            "Cenário": ["Sem Índice", "Com Índice"],
            "Tempo (s)": [resultado['tempo_sem'], resultado['tempo_com']],
            col_name: [resultado['valor_sem'], resultado['valor_com']]
        })
        st.dataframe(df, use_container_width=True)
    
    # Gráfico
    chart_data = df.melt(id_vars=["Cenário"], value_vars=["Tempo (s)"], var_name="Métrica", value_name="Tempo")
    st.bar_chart(chart_data.set_index("Cenário"))


# ==============================
# Interface Principal e Abas
# ==============================

st.title("📊 Benchmark de Consultas — Auxílio Emergencial")

if not st.session_state.get("api_token"):
    st.info("ℹ️ Faça login na barra lateral para habilitar os botões de Benchmark.")

tabs = st.tabs([
    "💰 Gasto por UF",
    "🏙️ Contagem Município", 
    "🔠 Busca por Nome",
    "🎁 Busca por Parcela",
    "👥 Beneficiários Responsáveis",
    "🆔 Busca por NIS"
])

is_logged_in = st.session_state.get("api_token") is not None

# Aba 1: Gasto por UF
with tabs[0]:
    st.header("💰 Gasto por UF")
    st.markdown("Testa `JOIN` + `SUM` com filtro em `uf` (índice B-Tree).")
    
    uf = st.text_input("UF (ex: CE)", "CE", key="uf1").upper()
    
    if st.button("Executar Benchmark", key="btn1", disabled=not is_logged_in):
        resultado = executar_benchmark(
            setup_key="gasto-uf",
            exec_endpoint="executar/total-gasto-por-uf",
            params={"uf": uf},
            extractor_fn=lambda d: d.get("total", 0)
        )
        if resultado:
            st.session_state['r1'] = resultado
    
    if 'r1' in st.session_state:
        exibir_resultados(st.session_state['r1'], "Total (R$)")

# Aba 2: Contagem Município
with tabs[1]:
    st.header("🏙️ Contagem Município")
    st.markdown("Testa `ILIKE 'termo%'` com índices `GIN/TRGM`.")
    
    col1, col2 = st.columns(2)
    uf = col1.text_input("UF", "CE", key="uf2").upper()
    municipio = col2.text_input("Município", "AQUIRAZ", key="mun2").upper()
    
    if st.button("Executar Benchmark", key="btn2", disabled=not is_logged_in):
        resultado = executar_benchmark(
            setup_key="contagem-municipio",
            exec_endpoint="executar/quantidade-beneficiarios-municipio",
            params={"uf": uf, "municipio": municipio},
            extractor_fn=lambda d: d.get("quantidade", 0)
        )
        if resultado:
            st.session_state['r2'] = resultado
    
    if 'r2' in st.session_state:
        exibir_resultados(st.session_state['r2'], "Quantidade")

# Aba 3: Busca por Nome
with tabs[2]:
    st.header("🔠 Busca por Nome")
    st.markdown("Testa `ILIKE 'termo%'` com índices `GIN/TRGM` em `nome_beneficiario`.")
    
    col1, col2 = st.columns(2)
    nome = col1.text_input("Nome", "MARIA", key="nome3").upper()
    limit = col2.slider("Limite", 10, 500, 50, key="lim3")
    
    if st.button("Executar Benchmark", key="btn3", disabled=not is_logged_in):
        resultado = executar_benchmark(
            setup_key="por-nome",
            exec_endpoint="executar/beneficiarios-por-nome",
            params={"nome": nome, "limit": limit},
            extractor_fn=lambda d: len(d) if isinstance(d, list) else 0
        )
        if resultado:
            st.session_state['r3'] = resultado
    
    if 'r3' in st.session_state:
        exibir_resultados(st.session_state['r3'], "Registros")
        if isinstance(st.session_state['r3']['data_com'], list):
            st.subheader("Amostra dos dados")
            st.dataframe(pd.DataFrame(st.session_state['r3']['data_com'][:20]))

# Aba 4: Busca por Parcela
with tabs[3]:
    st.header("🎁 Busca por N° Parcela")
    st.markdown("Busca beneficiários com `parcela > X`. Testa índice B-Tree em `(nis, parcela)`.")
    
    col1, col2, col3 = st.columns(3)
    uf = col1.text_input("UF", "SP", key="uf4").upper()
    min_parcela = col2.number_input("Parcela >", 0, value=1, key="par4")
    limit = col3.slider("Limite", 10, 500, 50, key="lim4")
    
    if st.button("Executar Benchmark", key="btn4", disabled=not is_logged_in):
        resultado = executar_benchmark(
            setup_key="multiplas-parcelas",
            exec_endpoint="executar/beneficiarios-multiplas-parcelas",
            params={"uf": uf, "min_parcela": min_parcela, "limit": limit},
            extractor_fn=lambda d: len(d) if isinstance(d, list) else 0
        )
        if resultado:
            st.session_state['r4'] = resultado
    
    if 'r4' in st.session_state:
        exibir_resultados(st.session_state['r4'], "Registros")
        if isinstance(st.session_state['r4']['data_com'], list):
            st.subheader("Amostra dos dados")
            st.dataframe(pd.DataFrame(st.session_state['r4']['data_com'][:20]))

# Aba 5: Beneficiários Responsáveis
with tabs[4]:
    st.header("👥 Beneficiários Responsáveis")
    st.markdown("Encontra beneficiários que também são responsáveis. Testa `JOIN` triplo e índices B-Tree.")
    
    col1, col2 = st.columns(2)
    uf = col1.text_input("UF", "SP", key="uf5").upper()
    limit = col2.slider("Limite", 10, 500, 50, key="lim5")
    
    if st.button("Executar Benchmark", key="btn5", disabled=not is_logged_in):
        resultado = executar_benchmark(
            setup_key="beneficiarios-responsaveis",
            exec_endpoint="executar/beneficiarios-responsaveis",
            params={"uf": uf, "limit": limit},
            extractor_fn=lambda d: len(d) if isinstance(d, list) else 0
        )
        if resultado:
            st.session_state['r5'] = resultado
    
    if 'r5' in st.session_state:
        exibir_resultados(st.session_state['r5'], "Registros")
        if isinstance(st.session_state['r5']['data_com'], list):
            st.subheader("Amostra dos dados")
            st.dataframe(pd.DataFrame(st.session_state['r5']['data_com'][:20]))

# Aba 6: Busca por NIS (utilitário)
with tabs[5]:
    st.header("🆔 Busca por NIS")
    st.markdown("Busca simples por chave primária (não é benchmark, sempre usa índice PK).")
    
    nis = st.text_input("NIS", "16110218880", key="nis6")
    
    if st.button("Buscar", key="btn6"):
        endpoint = f"executar/buscar-beneficiario/{nis}"
        tempo, status, data = request_api("GET", endpoint, timeout=30)
        
        if tempo and status == 200:
            st.success(f"Encontrado em {tempo:.6f}s")
            st.json(data)
        else:
            st.error(f"Erro {status}: {data}")

st.markdown("---")
st.caption("Desenvolvido para o Projeto de Auxílio Emergencial ⚙️")