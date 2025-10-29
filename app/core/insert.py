import asyncio
import pandas as pd
from app.core.database import engine
from app.core.configs import settings
from typing import Set, Tuple

async def create_tables() -> None:
    import app.models.__all_models

    print("Criando as tabelas do banco de dados...")

    async with engine.begin() as conn:
        await conn.run_sync(settings.DBBaseModel.metadata.drop_all)
        await conn.run_sync(settings.DBBaseModel.metadata.create_all)

    print("Tabelas criadas com sucesso")


async def copy_from_dataframe(table_name: str, df: pd.DataFrame) -> None:
    """
    Realiza inserção em massa (bulk insert) de um DataFrame em uma tabela PostgreSQL via asyncpg COPY.
    """
    print(f"Inserindo dados na tabela '{table_name}' via asyncpg COPY...")

    async with engine.begin() as conn:
        raw_conn = await conn.get_raw_connection()
        asyncpg_conn = raw_conn.driver_connection

        records = [tuple(x) for x in df.to_numpy()]
        columns = list(df.columns)

        await asyncpg_conn.copy_records_to_table(
            table_name,
            records=records,
            columns=columns
        )

        print(f"Inserção concluída com sucesso ({len(df)} linhas)")


def prepare_dataframes(chunk: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Separa o DataFrame original em 3 DataFrames correspondentes às tabelas:
    - Responsavel
    - Beneficiario
    - Auxilio
    """
    
    df_responsavel = chunk[[
        'nis_responsavel',
        'cpf_responsavel',
        'responsavel'
    ]].copy()
    
    df_responsavel.rename(columns={'responsavel': 'nome_responsavel'}, inplace = True)
    df_responsavel = df_responsavel[df_responsavel['nis_responsavel'] != '-2']
    df_responsavel = df_responsavel.drop_duplicates(subset=['nis_responsavel'])
    
    df_responsavel['nis_responsavel'] = df_responsavel['nis_responsavel'].astype(float).astype(int).astype(str)
    df_responsavel['cpf_responsavel'] = df_responsavel['cpf_responsavel'].astype(str)
    df_responsavel['nome_responsavel'] = df_responsavel['nome_responsavel'].astype(str)
    
    
    df_beneficiario = chunk[[
        'nis_beneficiario',
        'cpf_beneficiario',
        'beneficiario',
        'uf',
        'codigo_ibge_municipio',
        'municipio',
        'nis_responsavel'
    ]].copy()
    
    df_beneficiario.rename(columns={'beneficiario': 'nome_beneficiario'}, inplace=True)
    df_beneficiario = df_beneficiario[df_beneficiario['nis_beneficiario'].notna()]
    df_beneficiario = df_beneficiario.drop_duplicates(subset = ['nis_beneficiario'])
    
    df_beneficiario['nis_beneficiario'] = df_beneficiario['nis_beneficiario'].astype(float).astype(int).astype(str)
    df_beneficiario['cpf_beneficiario'] = df_beneficiario['cpf_beneficiario'].astype(str)
    df_beneficiario['nome_beneficiario'] = df_beneficiario['nome_beneficiario'].astype(str)
    df_beneficiario['uf'] = df_beneficiario['uf'].astype(str)
    df_beneficiario['codigo_ibge_municipio'] = df_beneficiario['codigo_ibge_municipio'].astype(int)
    df_beneficiario['municipio'] = df_beneficiario['municipio'].astype(str)
    df_beneficiario['nis_responsavel'] = df_beneficiario['nis_responsavel'].astype(float).astype(int).astype(str)
    
    
    df_auxilio = chunk[[
        'ano_mes',
        'enquadramento',
        'parcela',
        'observacao',
        'valor',
        'nis_beneficiario'
    ]].copy()
    
    df_auxilio = df_auxilio[df_auxilio['nis_beneficiario'].notna()]
    
    df_auxilio['ano_mes'] = df_auxilio['ano_mes'].astype(str)
    df_auxilio['enquadramento'] = df_auxilio['enquadramento'].astype(str)
    df_auxilio['parcela'] = df_auxilio['parcela'].astype(int)
    df_auxilio['observacao'] = df_auxilio['observacao'].astype(str)
    df_auxilio['valor'] = df_auxilio['valor'].astype(float)
    df_auxilio['nis_beneficiario'] = df_auxilio['nis_beneficiario'].astype(float).astype(int).astype(str)
    
    return df_responsavel, df_beneficiario, df_auxilio


async def main():
    await create_tables()

    print("Lendo CSV...")
    csv_path = "dataset/auxilio_emergencial.csv"

    chunk_size = 100_000
    
    nis_responsaveis_inseridos: Set = set()
    nis_beneficiarios_inseridos: Set = set()
    
    for i, chunk in enumerate(pd.read_csv(csv_path, chunksize = chunk_size)):
        print(f"\nProcessando chunk {i + 1}...")
        
        df_responsavel, df_beneficiario, df_auxilio = prepare_dataframes(chunk)
        
        df_responsavel = df_responsavel[
            ~df_responsavel['nis_responsavel'].isin(nis_responsaveis_inseridos)
        ]
        nis_responsaveis_inseridos.update(df_responsavel['nis_responsavel'])
        
        df_beneficiario = df_beneficiario[
            ~df_beneficiario['nis_beneficiario'].isin(nis_beneficiarios_inseridos)
        ]
        nis_beneficiarios_inseridos.update(df_beneficiario['nis_beneficiario'])
        
        if len(df_responsavel) > 0:
            await copy_from_dataframe("responsavel", df_responsavel)
        
        if len(df_beneficiario) > 0:
            await copy_from_dataframe("beneficiario", df_beneficiario)
        
        if len(df_auxilio) > 0:
            await copy_from_dataframe("auxilio", df_auxilio)
    
    print("\nInserindo responsável indefinido...")
    df_indefinido = pd.DataFrame([{
        'nis_responsavel': '-2',
        'cpf_responsavel': ' ',
        'nome_responsavel': 'responsavel indefinido'
    }])
    await copy_from_dataframe("responsavel", df_indefinido)
    
    print("\nImportação completa!")


if __name__ == "__main__":
    asyncio.run(main())