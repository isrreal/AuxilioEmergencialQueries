import ipywidgets
import psycopg2
import pandas 
from sqlalchemy import create_engine


# Tema: Dados informativos sobre o auxílio emergencial liberado por conta da pandemia da COVID-19.
# Dataset original disponível em: https://brasil.io/dataset/govbr/auxilio_emergencial/.
# Primeiro é necessário instanciar uma nova base de dados com base no código postgreSQL arquivo em insercao.txt


conexao = psycopg2.connect(
    database = 'auxilio_emergencial',
    user = 'postgres',
    password = 'suasenha',
    host = 'localhost',
    port = '5432'
)

engine = create_engine("postgresql+psycopg2://postgres:suasenha@localhost:5432/auxilio_emergencial")


botao_consultar1 = ipywidgets.Button(description = "Consultar")
botao_consultar2 = ipywidgets.Button(description = "Consultar")
botao_consultar3 = ipywidgets.Button(description = "Consultar")
botao_consultar4 = ipywidgets.Button(description = "Consultar")

quantidade_de_parcelas = ipywidgets.ToggleButtons(
                            options = ['1', '2', '3', '4'],
                            description = "Quantidade de parcelas:",
                            disabled = False
                        )
uf = ipywidgets.Text(
                    placeholder = 'CE',
                    description = 'Unidade Federal',
                    disabled = False
                )


nome = ipywidgets.Text(
        placeholder = 'Digite algum nome',
        description = 'Pesquisar beneficiários: ',
        disabled = False
    )

unidade_federal = ipywidgets.Text(
                    placeholder = 'CE',
                    description = 'Unidade Federal',
                    disabled = False
                )

mes = ipywidgets.Dropdown(
        options = ['Abril', 'Maio', 'Junho', 'Julho', 'Agosto'],
        description = 'Mês',
        disabled = False
    )


# Busca por quantidade de parcelas recebidas

def quantidade_de_parcelas_em_uf(_):
    consulta = f""" SELECT beneficiario.nome_beneficiario,
                        beneficiario.cpf_beneficiario,
                        beneficiario.municipio
                    FROM beneficiario
                    NATURAL JOIN auxilio
                    WHERE parcela > {quantidade_de_parcelas.value} AND beneficiario.UF = '{uf.value}'; 
                """
    dataframe = pandas.read_sql_query(consulta, engine)
    display(dataframe)
    
botao_consultar1.on_click(quantidade_de_parcelas_em_uf)

display(quantidade_de_parcelas, uf)
display(botao_consultar1)

# Beneficiários com a substring de nome requerida 

def retorna_beneficiarios(_):
    consulta = f"""SELECT beneficiario.nome_beneficiario as nome,
                        beneficiario.cpf_beneficiario as CPF,
                        beneficiario.nis_beneficiario as NIS
                    FROM beneficiario 
                    NATURAL JOIN auxilio 
                    WHERE beneficiario.nome_beneficiario LIKE '{nome.value}%%'; 
                """
    dataframe = pandas.read_sql_query(consulta, engine)
    display(dataframe)

botao_consultar2.on_click(retorna_beneficiarios)

display(nome)
display(botao_consultar2)

# Montante gasto por uma Unidade Federal específica

def seleciona_uf(_):
    consulta = f"""SELECT SUM(valor) as valor_gasto_total 
                    FROM auxilio 
                    NATURAL JOIN beneficiario
                    WHERE UF = '{unidade_federal.value}'
                """
    dataframe = pandas.read_sql_query(consulta, engine)
    display(dataframe)

botao_consultar3.on_click(seleciona_uf)

display(unidade_federal)
display(botao_consultar3)

# Montante gasto pelo Estado em data específica

def montante_gasto_em_data_especifica(_):
    periodo = 0
    if mes.value == 'Abril':
        periodo = 202004
    elif mes.value == 'Maio':
        periodo = 202005
    elif mes.value == 'Junho':
        periodo = 202006
    elif mes.value == 'Julho':
        periodo = 202007
    else:
        periodo = 202008
    consulta = f"""SELECT SUM(valor) AS valor_gasto 
                    FROM auxilio
                    NATURAL JOIN beneficiario 
                    WHERE ano_mes = '{periodo}';
                    """
    dataframe = pandas.read_sql_query(consulta, engine)
    display(dataframe)

botao_consultar4.on_click(montante_gasto_em_data_especifica)

display(mes)
display(botao_consultar4)




