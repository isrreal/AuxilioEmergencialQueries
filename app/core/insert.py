import argparse
import asyncio
import json
import platform
import resource
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from math import ceil
from pathlib import Path
from time import perf_counter
from typing import Sequence

import numpy as np
import pandas as pd
from tqdm import tqdm

from app.core.database import engine

DEFAULT_CSV_PATH = Path("/data/auxilio_emergencial.csv")
DEFAULT_CHUNK_SIZE = 100_000
DEFAULT_REPORT_PATH = Path("-")
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
    report_path: Path


@dataclass(frozen=True)
class TransformationCounts:
    responsavel_candidates: int
    responsavel_discarded: int
    beneficiario_candidates: int
    beneficiario_discarded: int
    auxilio_candidates: int
    auxilio_discarded: int


@dataclass(frozen=True)
class PreparedChunk:
    responsaveis: pd.DataFrame
    beneficiarios: pd.DataFrame
    auxilios: pd.DataFrame
    counts: TransformationCounts


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
    parser.add_argument(
        "--report-path",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="arquivo JSON de saída; use '-' para escrever em stdout (padrão: '-')",
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
        report_path=args.report_path,
    )


async def copy_from_dataframe(table_name: str, df: pd.DataFrame) -> None:
    """
    Realiza inserção em massa (bulk insert) de um DataFrame em uma tabela PostgreSQL via asyncpg COPY.
    """
    print(f"Inserindo dados na tabela '{table_name}' via asyncpg COPY...", file=sys.stderr)

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

        print(f"Inserção concluída com sucesso ({len(df)} linhas)", file=sys.stderr)


def prepare_dataframes(chunk: pd.DataFrame) -> PreparedChunk:
    """
    Separa e limpa o DataFrame em 3 DataFrames prontos para o banco.
    Assume que 'dtype' foi usado no pd.read_csv para colunas de string/ID.
    """
    
    source_rows = len(chunk)

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

    return PreparedChunk(
        responsaveis=df_responsavel,
        beneficiarios=df_beneficiario,
        auxilios=df_auxilio,
        counts=TransformationCounts(
            responsavel_candidates=len(df_responsavel),
            responsavel_discarded=source_rows - len(df_responsavel),
            beneficiario_candidates=len(df_beneficiario),
            beneficiario_discarded=source_rows - len(df_beneficiario),
            auxilio_candidates=len(df_auxilio),
            auxilio_discarded=source_rows - len(df_auxilio),
        ),
    )


def peak_memory_mb() -> float:
    """Retorna o pico de RSS do processo em MiB em sistemas Linux."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def current_memory_mb(status_path: Path = Path("/proc/self/status")) -> float:
    """Retorna o RSS atual do processo em MiB a partir do procfs do Linux."""
    with status_path.open(encoding="utf-8") as status_file:
        for line in status_file:
            if line.startswith("VmRSS:"):
                rss_kib = int(line.split()[1])
                return rss_kib / 1024

    raise RuntimeError(f"VmRSS não encontrado em {status_path}")


def memory_snapshot(status_path: Path = Path("/proc/self/status")) -> dict[str, float]:
    """Captura RSS atual e pico de RSS usando a mesma fonte do procfs."""
    values: dict[str, float] = {}
    proc_fields = {"VmRSS:": "current_rss_mb", "VmHWM:": "peak_rss_mb"}
    with status_path.open(encoding="utf-8") as status_file:
        for line in status_file:
            fields = line.split()
            if fields and fields[0] in proc_fields:
                values[proc_fields[fields[0]]] = int(fields[1]) / 1024

    missing = set(proc_fields.values()) - values.keys()
    if missing:
        formatted = ", ".join(sorted(missing))
        raise RuntimeError(f"campos de memória ausentes em {status_path}: {formatted}")
    return values


def dataframe_memory_mb(dataframe: pd.DataFrame) -> float:
    """Calcula a memória profunda ocupada por um DataFrame em MiB."""
    return float(dataframe.memory_usage(index=True, deep=True).sum()) / (1024**2)


def write_report(report: dict, destination: Path) -> None:
    """Serializa o relatório em stdout ou em um arquivo JSON."""
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if destination == Path("-"):
        print(serialized)
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(f"{serialized}\n", encoding="utf-8")

async def main(config: IngestionConfig) -> None:
    started_at = datetime.now(UTC)
    total_started = perf_counter()
    ingestion_start_memory = memory_snapshot()
    max_rows_description = config.max_rows if config.max_rows is not None else "todas"
    print(
        "Configuração da ingestão: "
        f"csv={config.csv_path}, chunk_size={config.chunk_size}, "
        f"max_rows={max_rows_description}",
        file=sys.stderr,
    )

    print("\nInserindo responsável indefinido...", file=sys.stderr)
    df_indefinido: pd.DataFrame = pd.DataFrame([{
        'nis_responsavel': UNDEFINED_RESPONSAVEL_NIS,
        'cpf_responsavel': ' ',
        'nome_responsavel': 'responsavel indefinido'
    }])

    setup_write_started = perf_counter()
    await copy_from_dataframe("responsavel", df_indefinido)
    setup_write_seconds = perf_counter() - setup_write_started
    after_setup_memory = memory_snapshot()
    del df_indefinido

    print("Lendo CSV...", file=sys.stderr)

    nis_responsaveis_inseridos: set[str] = set()
    nis_beneficiarios_inseridos: set[str] = set()
    
    total_responsavel = 1 
    total_beneficiario = 0
    total_auxilio = 0
    total_source_rows = 0
    total_read_seconds = 0.0
    total_transform_seconds = 0.0
    total_write_seconds = 0.0
    total_discarded = {
        "responsavel": 0,
        "beneficiario": 0,
        "auxilio": 0,
        "responsavel_cross_chunk_duplicate": 0,
        "beneficiario_cross_chunk_duplicate": 0,
    }
    chunks: list[dict] = []
    
    n_chunks = ceil(config.max_rows / config.chunk_size) if config.max_rows else None

    csv_iterator = pd.read_csv(
        config.csv_path,
        chunksize=config.chunk_size,
        nrows=config.max_rows,
        dtype=COLUMN_TYPES,
    )
    progress = tqdm(total=n_chunks, desc="Processando chunks", file=sys.stderr)
    chunk_index = 0
    while True:
        before_read_memory = memory_snapshot()
        read_started = perf_counter()
        try:
            chunk = next(csv_iterator)
        except StopIteration:
            break
        read_seconds = perf_counter() - read_started
        after_read_memory = memory_snapshot()
        chunk_index += 1
        total_source_rows += len(chunk)

        transform_started = perf_counter()
        prepared = prepare_dataframes(chunk)
        df_responsavel = prepared.responsaveis
        df_beneficiario = prepared.beneficiarios
        df_auxilio = prepared.auxilios
        responsavel_before_global_dedup = len(df_responsavel)
        beneficiario_before_global_dedup = len(df_beneficiario)
        
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

        responsavel_cross_chunk_duplicates = (
            responsavel_before_global_dedup - len(df_responsavel)
        )
        beneficiario_cross_chunk_duplicates = (
            beneficiario_before_global_dedup - len(df_beneficiario)
        )
        transform_seconds = perf_counter() - transform_started
        after_transform_memory = memory_snapshot()
        dataframe_memory = {
            "source_chunk": dataframe_memory_mb(chunk),
            "responsavel": dataframe_memory_mb(df_responsavel),
            "beneficiario": dataframe_memory_mb(df_beneficiario),
            "auxilio": dataframe_memory_mb(df_auxilio),
        }

        write_started = perf_counter()
        if len(df_responsavel) > 0:
            await copy_from_dataframe("responsavel", df_responsavel)
            total_responsavel += len(df_responsavel)
        
        if len(df_beneficiario) > 0:
            await copy_from_dataframe("beneficiario", df_beneficiario)
            total_beneficiario += len(df_beneficiario)
        
        if len(df_auxilio) > 0:
            await copy_from_dataframe("auxilio", df_auxilio)
            total_auxilio += len(df_auxilio)
        write_seconds = perf_counter() - write_started
        after_write_memory = memory_snapshot()

        total_read_seconds += read_seconds
        total_transform_seconds += transform_seconds
        total_write_seconds += write_seconds
        total_discarded["responsavel"] += prepared.counts.responsavel_discarded
        total_discarded["beneficiario"] += prepared.counts.beneficiario_discarded
        total_discarded["auxilio"] += prepared.counts.auxilio_discarded
        total_discarded["responsavel_cross_chunk_duplicate"] += (
            responsavel_cross_chunk_duplicates
        )
        total_discarded["beneficiario_cross_chunk_duplicate"] += (
            beneficiario_cross_chunk_duplicates
        )

        chunk_elapsed = read_seconds + transform_seconds + write_seconds
        chunk_report = {
            "index": chunk_index,
            "source_rows": len(chunk),
            "candidates_after_chunk_cleaning": {
                "responsavel": prepared.counts.responsavel_candidates,
                "beneficiario": prepared.counts.beneficiario_candidates,
                "auxilio": prepared.counts.auxilio_candidates,
            },
            "inserted": {
                "responsavel": len(df_responsavel),
                "beneficiario": len(df_beneficiario),
                "auxilio": len(df_auxilio),
            },
            "discarded": {
                "responsavel": prepared.counts.responsavel_discarded,
                "beneficiario": prepared.counts.beneficiario_discarded,
                "auxilio": prepared.counts.auxilio_discarded,
                "responsavel_cross_chunk_duplicate": responsavel_cross_chunk_duplicates,
                "beneficiario_cross_chunk_duplicate": beneficiario_cross_chunk_duplicates,
            },
            "timing_seconds": {
                "read": read_seconds,
                "transform": transform_seconds,
                "write": write_seconds,
                "total": chunk_elapsed,
            },
            "source_rows_per_second": (
                len(chunk) / chunk_elapsed if chunk_elapsed > 0 else None
            ),
            "peak_memory_mb": peak_memory_mb(),
            "memory_mb": {
                "before_read": before_read_memory,
                "after_read": after_read_memory,
                "after_transform": after_transform_memory,
                "after_write": after_write_memory,
                "dataframes_after_transform": dataframe_memory,
            },
            "deduplication_state": {
                "responsavel_identifiers": len(nis_responsaveis_inseridos),
                "beneficiario_identifiers": len(nis_beneficiarios_inseridos),
            },
        }

        del chunk
        del prepared
        del df_responsavel
        del df_beneficiario
        del df_auxilio
        chunk_report["memory_mb"]["after_cleanup"] = memory_snapshot()
        chunks.append(chunk_report)

        # Imprime mensagens sem atrapalhar a barra de progresso.
        tqdm.write(
            f"Acumulado - Responsavel: {total_responsavel}, "
            f"Beneficiario: {total_beneficiario}, Auxilio: {total_auxilio}",
            file=sys.stderr,
        )
        progress.update(1)

    progress.close()
    total_seconds = perf_counter() - total_started
    report = {
        "schema_version": 1,
        "status": "completed",
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "source": {
            "path": str(config.csv_path.resolve()),
            "size_bytes": config.csv_path.stat().st_size,
        },
        "configuration": {
            "chunk_size": config.chunk_size,
            "max_rows": config.max_rows,
        },
        "known_limitations": [
            "deduplication sets grow with every distinct identifier",
            "each table write uses an independent transaction",
            "the ingestion is not idempotent",
        ],
        "environment": {
            "python_version": platform.python_version(),
            "pandas_version": pd.__version__,
            "platform": platform.platform(),
        },
        "totals": {
            "chunks": chunk_index,
            "source_rows": total_source_rows,
            "inserted": {
                "responsavel": total_responsavel,
                "beneficiario": total_beneficiario,
                "auxilio": total_auxilio,
            },
            "synthetic_rows_inserted": {"responsavel": 1},
            "discarded": total_discarded,
            "timing_seconds": {
                "setup_write": setup_write_seconds,
                "read": total_read_seconds,
                "transform": total_transform_seconds,
                "write": total_write_seconds,
                "measured_stages": (
                    setup_write_seconds
                    + total_read_seconds
                    + total_transform_seconds
                    + total_write_seconds
                ),
                "wall_clock": total_seconds,
            },
            "source_rows_per_second": (
                total_source_rows / total_seconds if total_seconds > 0 else None
            ),
            "peak_memory_mb": peak_memory_mb(),
            "memory_mb": {
                "ingestion_start": ingestion_start_memory,
                "after_setup": after_setup_memory,
                "ingestion_end": memory_snapshot(),
            },
        },
        "chunks": chunks,
    }
    write_report(report, config.report_path)
    print(
        f"\nImportação completa em {total_seconds:.2f}s "
        f"({report['totals']['source_rows_per_second']:.2f} linhas/s).",
        file=sys.stderr,
    )

if __name__ == "__main__":
    asyncio.run(main(parse_args()))
