import streamlit as st
import requests
import time
import pandas as pd

API_BASE_URL = "http://api:8000/api/v1/consultas"

st.set_page_config(page_title="Benchmark Índices", layout="wide")
st.title("📊 Benchmark de Consultas — Auxílio Emergencial")

# ==============================
# Funções Utilitárias
# ==============================

def request_api(method, endpoint, params=None, timeout=600):
    """Faz requisição e retorna (tempo, status, dados)"""
    url = f"{API_BASE_URL}/{endpoint}"
    inicio = time.time()
    
    try:
        if method == "GET":
            resp = requests.get(url, params=params, timeout=timeout)
        else:
            resp = requests.post(url, timeout=timeout)
        
        duracao = time.time() - inicio
        
        if resp.status_code == 200:
            return duracao, resp.status_code, resp.json()
        return None, resp.status_code, resp.json().get('detail', 'Erro')
    
    except requests.exceptions.Timeout:
        return None, 504, "Timeout"
    except Exception as e:
        return None, 500, str(e)


def executar_benchmark(setup_key, exec_endpoint, params, extractor_fn):
    """Executa o ciclo completo de benchmark"""
    
    with st.spinner("Executando benchmark..."):
        # 1. Apagar índice
        st.write("1/4: Apagando índices...")
        _, status, msg = request_api("POST", f"setup/{setup_key}/apagar-indices", timeout=900)
        if status != 200:
            st.error(f"Erro ao apagar índices: {msg}")
            return None
        
        # 2. Consulta SEM índice
        st.write("2/4: Consultando SEM índice...")
        tempo_sem, status_sem, data_sem = request_api("GET", exec_endpoint, params)
        if tempo_sem is None:
            st.error(f"Erro na consulta sem índice: {data_sem}")
            return None
        
        # 3. Criar índice
        st.write("3/4: Criando índices...")
        tempo_create, status_create, msg_create = request_api("POST", f"setup/{setup_key}/criar-indices", timeout=900)
        if tempo_create is None:
            st.error(f"Erro ao criar índices: {msg_create}")
            return None
        
        # 4. Consulta COM índice
        st.write("4/4: Consultando COM índice...")
        tempo_com, status_com, data_com = request_api("GET", exec_endpoint, params)
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
            "data_com": data_com
        }


def exibir_resultados(resultado, col_name="Resultado"):
    """Exibe os resultados do benchmark"""
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Tempo de Criação do Índice", f"{resultado['tempo_create']:.3f} s")
        
        if resultado['ganho']:
            if resultado['ganho'] > 0:
                st.success(f"🏆 Ganho: {resultado['ganho']:.2f}% mais rápido")
            else:
                st.warning(f"🚨 Perda: {abs(resultado['ganho']):.2f}% mais lento")
    
    with col2:
        df = pd.DataFrame({
            "Cenário": ["Sem Índice", "Com Índice"],
            "Tempo (s)": [resultado['tempo_sem'], resultado['tempo_com']],
            col_name: [resultado['valor_sem'], resultado['valor_com']]
        })
        st.dataframe(df, use_container_width=True)
    
    # Gráfico
    st.bar_chart(df.set_index("Cenário")["Tempo (s)"])


# ==============================
# Abas de Benchmark
# ==============================

tabs = st.tabs([
    "💰 Gasto por UF",
    "🏙️ Contagem Município", 
    "🔠 Busca por Nome",
    "🎁 Busca por Parcela",
    "👥 Beneficiários Responsáveis",
    "🆔 Busca por NIS"
])

# Aba 1: Gasto por UF
with tabs[0]:
    st.header("💰 Gasto por UF")
    st.markdown("Testa `JOIN` + `SUM` com filtro em `uf`")
    
    uf = st.text_input("UF (ex: CE)", "CE", key="uf1").upper()
    
    if st.button("Executar Benchmark", key="btn1"):
        resultado = executar_benchmark(
            "gasto-uf",
            "executar/total-gasto-por-uf",
            {"uf": uf},
            lambda d: d.get("total", 0)
        )
        if resultado:
            st.session_state['r1'] = resultado
    
    if 'r1' in st.session_state:
        exibir_resultados(st.session_state['r1'], "Total (R$)")

# Aba 2: Contagem Município
with tabs[1]:
    st.header("🏙️ Contagem Município")
    st.markdown("Testa `ILIKE 'termo%'` com índices `GIN/TRGM`")
    
    col1, col2 = st.columns(2)
    uf = col1.text_input("UF", "CE", key="uf2").upper()
    municipio = col2.text_input("Município", "AQUIRAZ", key="mun2").upper()
    
    if st.button("Executar Benchmark", key="btn2"):
        resultado = executar_benchmark(
            "contagem-municipio",
            "executar/quantidade-beneficiarios-municipio",
            {"uf": uf, "municipio": municipio},
            lambda d: d.get("quantidade", 0)
        )
        if resultado:
            st.session_state['r2'] = resultado
    
    if 'r2' in st.session_state:
        exibir_resultados(st.session_state['r2'], "Quantidade")

# Aba 3: Busca por Nome
with tabs[2]:
    st.header("🔠 Busca por Nome")
    st.markdown("Testa `ILIKE 'termo%'` com índices `B-Tree`")
    
    col1, col2 = st.columns(2)
    nome = col1.text_input("Nome", "MARIA", key="nome3").upper()
    limit = col2.slider("Limite", 10, 500, 50, key="lim3")
    
    if st.button("Executar Benchmark", key="btn3"):
        resultado = executar_benchmark(
            "por-nome",
            "executar/beneficiarios-por-nome",
            {"nome": nome, "limit": limit},
            lambda d: len(d) if isinstance(d, list) else 0
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
    st.markdown("Busca beneficiários com parcelas maiores que o valor")
    
    col1, col2, col3 = st.columns(3)
    uf = col1.text_input("UF", "SP", key="uf4").upper()
    min_parcela = col2.number_input("Parcela >", 0, value=1, key="par4")
    limit = col3.slider("Limite", 10, 500, 50, key="lim4")
    
    if st.button("Executar Benchmark", key="btn4"):
        resultado = executar_benchmark(
            "multiplas-parcelas",
            "executar/beneficiarios-multiplas-parcelas",
            {"uf": uf, "min_parcela": min_parcela, "limit": limit},
            lambda d: len(d) if isinstance(d, list) else 0
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
    st.markdown("Encontra beneficiários que também são responsáveis")
    
    col1, col2 = st.columns(2)
    uf = col1.text_input("UF", "SP", key="uf5").upper()
    limit = col2.slider("Limite", 10, 500, 50, key="lim5")
    
    if st.button("Executar Benchmark", key="btn5"):
        resultado = executar_benchmark(
            "beneficiarios-responsaveis",
            "executar/beneficiarios-responsaveis",
            {"uf": uf, "limit": limit},
            lambda d: len(d) if isinstance(d, list) else 0
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
    st.markdown("Busca simples por chave primária (não é benchmark)")
    
    nis = st.text_input("NIS", "16110218880", key="nis6")
    
    if st.button("Buscar", key="btn6"):
        tempo, status, data = request_api("GET", f"executar/buscar-beneficiario/{nis}", timeout=30)
        
        if tempo and status == 200:
            st.success(f"Encontrado em {tempo:.6f}s")
            st.json(data)
        else:
            st.error(f"Erro {status}: {data}")

st.markdown("---")
st.caption("Desenvolvido para o Projeto de Auxílio Emergencial ⚙️")