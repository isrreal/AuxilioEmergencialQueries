import argparse
import asyncio
from dataclasses import dataclass
from math import ceil
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from tqdm import tqdm

from app.core.database import engine

DEFAULT_CSV_PATH = Path("dataset/auxilio_emergencial.csv")
DEFAULT_CHUNK_SIZE = 100_000
UNDEFINED_RESPONSAVEL_NIS = "-2"

COLUMN_TYPES = {
    "nis_responsavel": "str",
    "cpf_responsavel": "str",
    "responsavel": "str",
    "nis_beneficiario": "str",
    "cpf_beneficiario": "str",
    "beneficiario": "str",
    "uf": "str",
    "municipio": "str",
    "ano_mes": "str",
    "enquadramento": "str",
    "observacao": "str",
}


@dataclass(frozen=True)
class IngestionConfig:
    csv_path: Path
    chunk_size: int
    max_rows: int | None


def positive_int(value: str) -> int:
    """Converte um argumento de CLI em inteiro estritamente positivo."""
    parsed_value = int(value)
    if parsed_value <= 0:
        raise argparse.ArgumentTypeError("o valor deve ser maior que zero")
    return parsed_value


def parse_args(argv: Sequence[str] | None = None) -> IngestionConfig:
    """Lê e valida os parâmetros operacionais da ingestão."""
    parser = argparse.ArgumentParser(
        description="Importa o dataset de Auxílio Emergencial para o PostgreSQL."
    )
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help=f"caminho do CSV (padrão: {DEFAULT_CSV_PATH})",
    )
    parser.add_argument(
        "--chunk-size",
        type=positive_int,
        default=DEFAULT_CHUNK_SIZE,
        help=f"linhas processadas por chunk (padrão: {DEFAULT_CHUNK_SIZE})",
    )

    row_scope = parser.add_mutually_exclusive_group(required=True)
    row_scope.add_argument(
        "--max-rows",
        type=positive_int,
        help="limita a quantidade de linhas para testes e cargas parciais",
    )
    row_scope.add_argument(
        "--all-rows",
        action="store_true",
        help="confirma explicitamente o processamento de todo o arquivo",
    )

    args = parser.parse_args(argv)
    if not args.csv_path.is_file():
        parser.error(f"arquivo CSV não encontrado: {args.csv_path}")

    return IngestionConfig(
        csv_path=args.csv_path,
        chunk_size=args.chunk_size,
        max_rows=None if args.all_rows else args.max_rows,
    )


async def copy_from_dataframe(table_name: str, df: pd.DataFrame) -> None:
    """
    Realiza inserção em massa (bulk insert) de um DataFrame em uma tabela PostgreSQL via asyncpg COPY.
    """
    print(f"Inserindo dados na tabela '{table_name}' via asyncpg COPY...")

    async with engine.begin() as db:
        # Obtém a conexão bruta do PostgreSQL
        raw_conn = await db.get_raw_connection()
        asyncpg_conn = raw_conn.driver_connection

        # -------------------------------
        # Preparando os registros para COPY
        # -------------------------------
        # NOTA SOBRE MEMÓRIA:
        # 1. [tuple(x) for x in df.to_numpy()]
        #    -> Cria uma cópia completa do DataFrame em memória
        # 2. (tuple(x) for x in df.to_numpy())
        #    -> Cria um generator para tuplas, mas ainda duplica o array NumPy
        # 3. df.itertuples(index = False, name = None)
        #    -> Mais eficiente para bases grandes: gera tuplas linha a linha sem criar cópias desnecessárias
        #    -> Retorna tuplas imutáveis prontas para asyncpg COPY

        records = df.itertuples(index = False, name = None)

        # Lista de colunas para a inserção
        columns = list(df.columns)

        # -------------------------------
        # Inserção em massa usando asyncpg COPY
        # -------------------------------
        await asyncpg_conn.copy_records_to_table(
            table_name,
            records = records,
            columns = columns
        )

        print(f"Inserção concluída com sucesso ({len(df)} linhas)")


def prepare_dataframes(chunk: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Separa e limpa o DataFrame em 3 DataFrames prontos para o banco.
    Assume que 'dtype' foi usado no pd.read_csv para colunas de string/ID.
    """
    
    df_responsavel = chunk[[
        'nis_responsavel',
        'cpf_responsavel',
        'responsavel'
    ]].copy()
    df_responsavel.rename(columns = {'responsavel': 'nome_responsavel'}, inplace = True)
    df_responsavel = df_responsavel[
        df_responsavel["nis_responsavel"] != UNDEFINED_RESPONSAVEL_NIS
    ]
    df_responsavel = df_responsavel.drop_duplicates(subset = ['nis_responsavel'])
        
    
    df_beneficiario = chunk[[
        'nis_beneficiario',
        'cpf_beneficiario',
        'beneficiario',
        'uf',
        'codigo_ibge_municipio',
        'municipio',
        'nis_responsavel'
    ]].copy()
    df_beneficiario.rename(columns = {'beneficiario': 'nome_beneficiario'}, inplace = True)
    df_beneficiario = df_beneficiario[df_beneficiario['nis_beneficiario'].notna()]
    df_beneficiario = df_beneficiario.drop_duplicates(subset = ['nis_beneficiario'])
    
    df_beneficiario['codigo_ibge_municipio'] = df_beneficiario['codigo_ibge_municipio'].astype(int)

    df_auxilio = chunk[[
        'ano_mes',
        'enquadramento',
        'parcela',
        'observacao',
        'valor',
        'nis_beneficiario'
    ]].copy()

    df_auxilio = df_auxilio[df_auxilio['nis_beneficiario'].notna()]
    
    df_auxilio['parcela'] = df_auxilio['parcela'].astype(int)
    df_auxilio['valor'] = df_auxilio['valor'].astype(float)
    
    df_responsavel = df_responsavel.replace({pd.NA: None, np.nan: None})
    df_beneficiario = df_beneficiario.replace({pd.NA: None, np.nan: None})
    df_auxilio = df_auxilio.replace({pd.NA: None, np.nan: None})

    return df_responsavel, df_beneficiario, df_auxilio

async def main(config: IngestionConfig) -> None:
    max_rows_description = config.max_rows if config.max_rows is not None else "todas"
    print(
        "Configuração da ingestão: "
        f"csv={config.csv_path}, chunk_size={config.chunk_size}, "
        f"max_rows={max_rows_description}"
    )

    print("\nInserindo responsável indefinido...")
    df_indefinido: pd.DataFrame = pd.DataFrame([{
        'nis_responsavel': UNDEFINED_RESPONSAVEL_NIS,
        'cpf_responsavel': ' ',
        'nome_responsavel': 'responsavel indefinido'
    }])

    await copy_from_dataframe("responsavel", df_indefinido)

    print("Lendo CSV...")

    nis_responsaveis_inseridos: set[str] = set()
    nis_beneficiarios_inseridos: set[str] = set()
    
    total_responsavel = 1 
    total_beneficiario = 0
    total_auxilio = 0
    
    n_chunks = ceil(config.max_rows / config.chunk_size) if config.max_rows else None

    csv_iterator = pd.read_csv(
        config.csv_path,
        chunksize=config.chunk_size,
        nrows=config.max_rows,
        dtype=COLUMN_TYPES,
    )
    # processando todo o dataset através de chunks (porções volumosas do conjunto de dados).
    for chunk in tqdm(csv_iterator, total=n_chunks, desc="Processando chunks"):
        
        df_responsavel, df_beneficiario, df_auxilio = prepare_dataframes(chunk)
        
        # mantém somente os responsáveis cujo valor de NIS não foram inseridos.
        df_responsavel = df_responsavel[
            ~df_responsavel['nis_responsavel'].isin(nis_responsaveis_inseridos)
        ]

        # Adiciona ao set todos os novos NIS processados neste chunk.
        # Como sets não permitem valores duplicados, isso impede reprocessamento futuro.        

        nis_responsaveis_inseridos.update(df_responsavel['nis_responsavel'])
        # mantém somente os beneficiários cujo valor de NIS ainda não foram inseridos.
        df_beneficiario = df_beneficiario[
            ~df_beneficiario['nis_beneficiario'].isin(nis_beneficiarios_inseridos)
        ]
        nis_beneficiarios_inseridos.update(df_beneficiario['nis_beneficiario'])
        
        if len(df_responsavel) > 0:
            await copy_from_dataframe("responsavel", df_responsavel)
            total_responsavel += len(df_responsavel)
        
        if len(df_beneficiario) > 0:
            await copy_from_dataframe("beneficiario", df_beneficiario)
            total_beneficiario += len(df_beneficiario)
        
        if len(df_auxilio) > 0:
            await copy_from_dataframe("auxilio", df_auxilio)
            total_auxilio += len(df_auxilio)

        # Imprime mensagens sem atrapalhar a barra de progresso.
        tqdm.write(
            f"Acumulado - Responsavel: {total_responsavel}, "
            f"Beneficiario: {total_beneficiario}, Auxilio: {total_auxilio}"
        )
    
    print(f"\nImportação completa!\nTotais - Responsavel: {total_responsavel}, Beneficiario: {total_beneficiario}, Auxilio: {total_auxilio}")

if __name__ == "__main__":
    asyncio.run(main(parse_args()))
