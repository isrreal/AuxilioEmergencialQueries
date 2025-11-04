    import streamlit as st
    import requests
    import time
    import pandas as pd
    from typing import Dict, Any, List, Tuple

    # ==============================
    # ⚙️ Configuração
    # ==============================
    API_BASE_URL: str = "http://api:8000/api/v1/consultas"
    st.set_page_config(page_title="Benchmark Índices - Auxílio Emergencial", layout="wide")

    st.title("📊 Benchmark de Consultas — Auxílio Emergencial")
    st.markdown("""
    Use as abas abaixo para executar comparativos de desempenho (queries com vs. sem índices)
    em diferentes cenários de consulta no banco de dados do Auxílio Emergencial.

    **Processo de Benchmark em cada aba:**
    1.  **Apaga** o índice específico (via API).
    2.  **Mede** o tempo do `SELECT` (Sem Índice).
    3.  **Cria** o índice específico (via API).
    4.  **Mede** o tempo do `SELECT` (Com Índice).
    """)


    # ==============================
    # ⚙️ Funções utilitárias
    # ==============================

    def medir_tempo_get(endpoint: str, params: dict) -> Tuple[float | None, int, Any]:
        """Executa uma requisição GET e mede o tempo de resposta."""
        inicio = time.time()
        try:
            resp = requests.get(f"{API_BASE_URL}/{endpoint}", params=params, timeout=600)
            duracao = time.time() - inicio
            
            if resp.status_code == 200:
                return duracao, resp.status_code, resp.json()
            else:
                detail = f"Erro {resp.status_code}: {resp.json().get('detail', 'Erro desconhecido')}"
                return None, resp.status_code, detail
                
        except requests.exceptions.Timeout:
            return None, 504, "Timeout (600s). A consulta sem índice é provavelmente muito lenta."
        except requests.exceptions.RequestException as e:
            return None, 500, f"Erro de conexão: {str(e)}"
        except Exception as e:
            return None, 500, str(e)

    def chamar_setup_post(endpoint: str) -> Tuple[float | None, Any]:
        """Chama uma rota POST de setup e mede o tempo."""
        inicio = time.time()
        try:
            resp = requests.post(f"{API_BASE_URL}/{endpoint}", timeout=900)
            duracao = time.time() - inicio
            
            if resp.status_code == 200:
                return duracao, resp.json()
            else:
                return None, resp.json()
                
        except requests.exceptions.Timeout:
            return None, {"detail": "Timeout (900s) ao criar/apagar índice."}
        except requests.exceptions.RequestException as e:
            return None, {"detail": f"Erro de conexão: {str(e)}"}
        except Exception as e:
            return None, {"detail": str(e)}

    def exibir_resultados(df: pd.DataFrame, tempo_create: float, label_tempo="Tempo (s)"):
        """Exibe resultados em tabela, gráfico e cálculo de ganho."""
        st.subheader("⏱️ Resultados de desempenho")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric(label="Tempo de Criação do Índice", value=f"{tempo_create:.3f} s")
            if label_tempo in df.columns and len(df[label_tempo]) == 2:
                tempo_sem = df[label_tempo].iloc[0]
                tempo_com = df[label_tempo].iloc[1]
                
                if tempo_sem is not None and tempo_com is not None and tempo_sem > 0:
                    ganho = (tempo_sem - tempo_com) / tempo_sem * 100
                    if ganho > 0:
                        st.success(f"🏆 **Ganho de desempenho:** {ganho:.2f}% mais rápido.")
                    elif ganho < 0:
                        st.warning(f"🚨 **Perda de desempenho:** {abs(ganho):.2f}% mais lento com índice.")
                    else:
                        st.info("ℹ️ **Sem diferença de desempenho.**")
                elif tempo_sem is None:
                    st.error("Falha na medição 'Sem Índice' (provavelmente Timeout). Ganho não calculado.")
                elif tempo_com is None:
                    st.error("Falha na medição 'Com Índice'. Ganho não calculado.")
                else:
                    st.info("Não foi possível calcular o ganho (Tempo 'Sem Índice' foi 0).")
        
        with col2:
            st.dataframe(df, use_container_width=True)

        if label_tempo in df.columns:
            df_plot = df.copy()
            df_plot[label_tempo] = pd.to_numeric(df_plot[label_tempo], errors='coerce')
            st.bar_chart(df_plot.set_index("Cenário")[label_tempo])


    # ==============================
    # 🚀 FUNÇÃO DE BENCHMARK
    # ==============================
    def run_benchmark(
        api_setup_key: str,
        api_exec_endpoint: str,
        exec_params: Dict[str, Any],
        session_state_key: str,
        result_columns: List[str],
        data_extractor_fn: callable
    ):
        """Função genérica para executar o fluxo de benchmark de 4 etapas."""
        
        with st.spinner("Executando benchmark... (Isso pode levar vários minutos)"):
            try:
                st.write(f"1/4: Apagando índices ({api_setup_key})...")
                _, data_drop = chamar_setup_post(f"setup/{api_setup_key}/apagar-indices")
                if _ is None:
                    raise Exception(f"Falha ao APAGAR índices: {data_drop}")

                st.write("2/4: Executando consulta SEM índice...")
                tempo_sem, status_sem, data_sem = medir_tempo_get(api_exec_endpoint, exec_params)
                
                if tempo_sem is None:
    
                    raise Exception(f"Falha na consulta SEM índice (Status {status_sem}): {data_sem}")
                
                st.write(f"3/4: Criando índices ({api_setup_key})... (Pode demorar)")
                tempo_create, data_create = chamar_setup_post(f"setup/{api_setup_key}/criar-indices")
                if tempo_create is None:
                    raise Exception(f"Falha ao CRIAR índices: {data_create}")

                st.write("4/4: Executando consulta COM índice...")
                tempo_com, status_com, data_com = medir_tempo_get(api_exec_endpoint, exec_params)
                if tempo_com is None:
                    st.warning(f"Falha na consulta COM índice (Status {status_com}): {data_com}")

                df_data = {
                    "Cenário": ["Sem Índice", "Com Índice"],
                    "Tempo (s)": [tempo_sem, tempo_com],
                    "Status": [status_sem, status_com],
                }
                
                dados_sem_idx = data_extractor_fn(data_sem)
                dados_com_idx = data_extractor_fn(data_com)
                
                if isinstance(result_columns, list) and isinstance(dados_sem_idx, (list, tuple)):
                    for i, col_name in enumerate(result_columns):
                        df_data[col_name] = [dados_sem_idx[i], dados_com_idx[i]]
                else:
                    col_name = result_columns[0] if isinstance(result_columns, list) else result_columns
                    df_data[col_name] = [dados_sem_idx, dados_com_idx]

                df = pd.DataFrame(df_data)
                
                st.session_state[session_state_key] = (df, tempo_create, data_com if tempo_com is not None else None)
                st.success("Benchmark concluído!")

            except Exception as e:
                st.error(f"Erro fatal no benchmark: {e}")
                st.session_state[session_state_key] = None

    # ==============================
    # 🚀 FUNÇÃO CRIADORA DE ABAS
    # ==============================

    def criar_aba_benchmark(tab: st.tabs, config: Dict[str, Any]):
        """Cria uma aba de benchmark inteira a partir de um dicionário de configuração."""
        with tab:
            st.header(config["header"])
            st.markdown(config["markdown"])
            
            exec_params = config["input_fn"]()
            
            session_key = config["session_state_key"]
            
            if st.button(f"Comparar {config['header']}", key=config["button_key"]):
                run_benchmark(
                    api_setup_key=config["api_setup_key"],
                    api_exec_endpoint=config["api_exec_endpoint"],
                    exec_params=exec_params,
                    session_state_key=session_key,
                    result_columns=config["result_columns"],
                    data_extractor_fn=config["data_extractor_fn"]
                )
            
            if session_key in st.session_state and st.session_state[session_key]:
                df, tempo_create, data_com = st.session_state[session_key]
                exibir_resultados(df, tempo_create)
                
                if config.get("show_data_sample", False) and isinstance(data_com, list) and len(data_com) > 0:
                    st.subheader("Amostra dos dados (Com Índice)")
                    st.dataframe(pd.DataFrame(data_com[:20]), use_container_width=True)


    # ==============================
    # 📊 CONFIGURAÇÃO DAS ABAS (NOVO)
    # ==============================

    def inputs_gasto_uf() -> Dict[str, Any]:
        uf = st.text_input("Digite a UF (ex: CE)", "CE", key="uf_gasto").upper()
        return {"uf": uf}

    def inputs_contagem_municipio() -> Dict[str, Any]:
        col1, col2 = st.columns(2)
        uf = col1.text_input("UF", "CE", key="uf_contagem").upper()
        municipio = col2.text_input("Parte do Município (ex: Aquiraz)", "AQUIRAZ", key="municipio_contagem").upper()
        return {"uf": uf, "municipio": municipio}

    def inputs_busca_nome() -> Dict[str, Any]:
        col1, col2 = st.columns(2)
        nome = col1.text_input("Nome ou parte do nome (ex: MARIA)", "MARIA", key="nome_busca").upper()
        limit = col2.slider("Limite de registros", 10, 500, 50, key="limit_nome")
        return {"nome": nome, "limit": limit}

    def inputs_busca_parcela() -> Dict[str, Any]:
        col1, col2, col3 = st.columns(3)
        uf = col1.text_input("UF", "SP", key="uf_multi").upper()
        min_parcela = col2.number_input("N° da Parcela Maior que", min_value=0, value=1, key="min_parcela")
        limit = col3.slider("Limite de registros", 10, 500, 50, key="limit_multi_parcela")
        return {"uf": uf, "min_parcela": min_parcela, "limit": limit}

    def inputs_beneficiarios_responsaveis() -> Dict[str, Any]:
        col1, col2 = st.columns(2)
        uf = col1.text_input("UF", "SP", key="uf_resp").upper()
        limit = col2.slider("Limite de registros", 10, 500, 50, key="limit_resp")
        return {"uf": uf, "limit": limit}

    BENCHMARK_CONFIG = [
        {
            "header": "💰 Gasto por UF",
            "markdown": "Testa a performance de `JOIN` + `SUM` com filtro em `uf`.",
            "api_setup_key": "gasto-uf",
            "api_exec_endpoint": "executar/total-gasto-por-uf",
            "session_state_key": "gasto_results",
            "button_key": "btn_gasto",
            "input_fn": inputs_gasto_uf,
            "result_columns": ["Total (R$)"],
            "data_extractor_fn": lambda data: data.get("total", 0) if isinstance(data, dict) else 0
        },
        {
            "header": "🏙️ Contagem Município",
            "markdown": "Testa a eficiência de buscas com `ILIKE '%termo%'` usando índices `GIN/TRGM`.",
            "api_setup_key": "contagem-municipio",
            "api_exec_endpoint": "executar/quantidade-beneficiarios-municipio",
            "session_state_key": "contagem_results",
            "button_key": "btn_contagem",
            "input_fn": inputs_contagem_municipio,
            "result_columns": ["Quantidade"],
            "data_extractor_fn": lambda data: data.get("quantidade", 0) if isinstance(data, dict) else 0
        },
        {
            "header": "🔠 Busca por Nome",
            "markdown": "Testa a eficiência de buscas com `ILIKE 'termo%'` usando índices `B-Tree`.",
            "api_setup_key": "por-nome",
            "api_exec_endpoint": "executar/beneficiarios-por-nome",
            "session_state_key": "nome_results",
            "button_key": "btn_nome",
            "input_fn": inputs_busca_nome,
            "result_columns": ["Registros"],
            "data_extractor_fn": lambda data: len(data) if isinstance(data, list) else 0,
            "show_data_sample": True
        },
        {
            "header": "🎁 Busca por N° Parcela",
            "markdown": "Busca beneficiários com parcelas *maiores que* o valor informado. Testa `JOIN`s.",
            "api_setup_key": "multiplas-parcelas",
            "api_exec_endpoint": "executar/beneficiarios-multiplas-parcelas",
            "session_state_key": "parcela_results",
            "button_key": "btn_parcela",
            "input_fn": inputs_busca_parcela,
            "result_columns": ["Registros"],
            "data_extractor_fn": lambda data: len(data) if isinstance(data, list) else 0,
            "show_data_sample": True
        },
        {
            "header": "👥 Beneficiários Responsáveis",
            "markdown": "Encontra beneficiários que também são responsáveis. Testa `JOIN` triplo.",
            "api_setup_key": "beneficiarios-responsaveis",
            "api_exec_endpoint": "executar/beneficiarios-responsaveis",
            "session_state_key": "resp_results",
            "button_key": "btn_resp",
            "input_fn": inputs_beneficiarios_responsaveis,
            "result_columns": ["Registros"],
            "data_extractor_fn": lambda data: len(data) if isinstance(data, list) else 0,
            "show_data_sample": True
        }
    ]

    # ==============================
    # 📊 RENDERIZAÇÃO DAS ABAS 
    # ==============================

    tab_titles = [config["header"] for config in BENCHMARK_CONFIG] + ["🆔 Utilitário: Busca por NIS"]
    tabs = st.tabs(tab_titles)

    for i, config in enumerate(BENCHMARK_CONFIG):
        criar_aba_benchmark(tabs[i], config)

    # ==============================
    # 🆔 Aba 6: Utilitário 
    # ==============================
    with tabs[5]:
        st.header("🆔 Utilitário: Busca por Chave Primária (NIS)")
        st.markdown("""
        Esta é uma busca simples por Chave Primária (PK). **Isso não é um benchmark.**
        A API não expõe rotas para apagar o índice da PK (o que é correto).
        Isto apenas demonstra a velocidade de uma busca `SELECT ... WHERE pk = ...`
        """)
        
        nis_busca = st.text_input("NIS do Beneficiário (ex: 16110218880)", "16110218880", key="nis_busca")

        if st.button("Buscar por NIS", key="btn_nis"):
            endpoint_url = f"executar/buscar-beneficiario/{nis_busca}"
            
            with st.spinner(f"Buscando NIS {nis_busca}..."):
                tempo, status_code, data = medir_tempo_get(endpoint_url, {})
                
                if tempo is not None and status_code == 200:
                    st.success(f"Beneficiário encontrado em {tempo:.6f} segundos.")
                    st.json(data)
                    st.session_state['nis_result'] = data
                else:
                    st.error(f"Erro ao buscar (Status {status_code}): {data}")
                    st.session_state['nis_result'] = None

        elif 'nis_result' in st.session_state and st.session_state['nis_result']:
            st.subheader("Último resultado buscado:")
            st.json(st.session_state['nis_result'])


    st.markdown("---")
    st.caption("Desenvolvido para o Projeto de Auxilio Emergencial ⚙️")