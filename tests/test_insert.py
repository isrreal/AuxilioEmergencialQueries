import argparse
import json
import os
from pathlib import Path

import pandas as pd
import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/test",
)

from app.core.insert import (  # noqa: E402
    DEFAULT_REPORT_PATH,
    UNDEFINED_RESPONSAVEL_NIS,
    current_memory_mb,
    dataframe_memory_mb,
    parse_args,
    positive_int,
    prepare_dataframes,
    write_report,
)


def make_chunk() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "nis_responsavel": ["10", "10", UNDEFINED_RESPONSAVEL_NIS],
            "cpf_responsavel": ["100", "100", None],
            "responsavel": ["Responsável", "Responsável", None],
            "nis_beneficiario": ["20", "20", None],
            "cpf_beneficiario": ["200", "200", None],
            "beneficiario": ["Beneficiário", "Beneficiário", None],
            "uf": ["CE", "CE", "CE"],
            "codigo_ibge_municipio": [2304400, 2304400, 2304400],
            "municipio": ["Fortaleza", "Fortaleza", "Fortaleza"],
            "ano_mes": ["202004", "202005", "202006"],
            "enquadramento": ["A", "A", "A"],
            "parcela": [1, 2, 3],
            "observacao": [None, None, None],
            "valor": [600.0, 600.0, 600.0],
        }
    )


def test_positive_int_rejects_zero() -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="maior que zero"):
        positive_int("0")


def test_parse_args_uses_stdout_report_by_default(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    csv_path.touch()

    config = parse_args(["--csv-path", str(csv_path), "--max-rows", "10"])

    assert config.csv_path == csv_path
    assert config.max_rows == 10
    assert config.report_path == DEFAULT_REPORT_PATH


def test_prepare_dataframes_counts_filtered_entity_candidates() -> None:
    prepared = prepare_dataframes(make_chunk())

    assert len(prepared.responsaveis) == 1
    assert len(prepared.beneficiarios) == 1
    assert len(prepared.auxilios) == 2
    assert prepared.counts.responsavel_discarded == 2
    assert prepared.counts.beneficiario_discarded == 2
    assert prepared.counts.auxilio_discarded == 1


def test_write_report_creates_parent_directory(tmp_path: Path) -> None:
    report_path = tmp_path / "nested" / "baseline.json"

    write_report({"schema_version": 1}, report_path)

    assert json.loads(report_path.read_text(encoding="utf-8")) == {"schema_version": 1}


def test_current_memory_mb_reads_vmrss_from_proc_status(tmp_path: Path) -> None:
    status_path = tmp_path / "status"
    status_path.write_text("Name:\tpython\nVmRSS:\t2048 kB\n", encoding="utf-8")

    assert current_memory_mb(status_path) == 2.0


def test_dataframe_memory_mb_uses_deep_object_memory() -> None:
    dataframe = pd.DataFrame({"value": ["a" * 1000]})
    shallow_mb = float(dataframe.memory_usage(index=True, deep=False).sum()) / (1024**2)

    assert dataframe_memory_mb(dataframe) > shallow_mb
