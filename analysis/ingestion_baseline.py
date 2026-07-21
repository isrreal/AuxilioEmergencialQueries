"""Carregamento, validação e agregação do baseline de ingestão."""

import json
from pathlib import Path

import pandas as pd

SUPPORTED_SCHEMA_VERSION = 1
STAGE_COLUMNS = ("setup_write", "read", "transform", "write")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_manifest(manifest: dict) -> None:
    if manifest.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        raise ValueError("manifesto com schema_version incompatível")
    if manifest.get("status") != "completed":
        raise ValueError("o protocolo de benchmark não foi concluído")
    if manifest.get("completed_runs") != len(manifest.get("runs", [])):
        raise ValueError("a contagem de runs do manifesto é inconsistente")


def validate_report(report: dict, manifest_entry: dict, chunk_size: int) -> None:
    if report.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        raise ValueError("relatório com schema_version incompatível")
    if report.get("status") != "completed":
        raise ValueError("relatório de ingestão incompleto")

    configuration = report.get("configuration", {})
    if configuration.get("max_rows") != manifest_entry["size"]:
        raise ValueError("volume do relatório diverge do manifesto")
    if configuration.get("chunk_size") != chunk_size:
        raise ValueError("chunk_size do relatório diverge do manifesto")
    if report.get("totals", {}).get("source_rows") != manifest_entry["size"]:
        raise ValueError("o relatório não processou todas as linhas solicitadas")


def load_experiment(manifest_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Carrega runs e chunks validados sem expor o caminho local do dataset."""
    manifest_path = manifest_path.resolve()
    manifest = read_json(manifest_path)
    validate_manifest(manifest)
    chunk_size = manifest["configuration"]["chunk_size"]
    run_rows: list[dict] = []
    chunk_rows: list[dict] = []

    for entry in manifest["runs"]:
        report_path = (manifest_path.parent / entry["report"]).resolve()
        try:
            report_path.relative_to(manifest_path.parent)
        except ValueError as exc:
            raise ValueError("relatório fora do diretório do experimento") from exc

        report = read_json(report_path)
        validate_report(report, entry, chunk_size)
        totals = report["totals"]
        timing = totals["timing_seconds"]
        run_rows.append(
            {
                "source_rows": entry["size"],
                "kind": entry["kind"],
                "run": entry["number"],
                "setup_write_seconds": timing["setup_write"],
                "read_seconds": timing["read"],
                "transform_seconds": timing["transform"],
                "write_seconds": timing["write"],
                "wall_clock_seconds": timing["wall_clock"],
                "source_rows_per_second": totals["source_rows_per_second"],
                "peak_memory_mb": totals["peak_memory_mb"],
                "responsavel_inserted": totals["inserted"]["responsavel"],
                "beneficiario_inserted": totals["inserted"]["beneficiario"],
                "auxilio_inserted": totals["inserted"]["auxilio"],
            }
        )

        for chunk in report["chunks"]:
            processed_rows = min(chunk["index"] * chunk_size, entry["size"])
            chunk_rows.append(
                {
                    "source_rows": entry["size"],
                    "kind": entry["kind"],
                    "run": entry["number"],
                    "chunk": chunk["index"],
                    "processed_rows": processed_rows,
                    "read_seconds": chunk["timing_seconds"]["read"],
                    "transform_seconds": chunk["timing_seconds"]["transform"],
                    "write_seconds": chunk["timing_seconds"]["write"],
                    "total_seconds": chunk["timing_seconds"]["total"],
                    "source_rows_per_second": chunk["source_rows_per_second"],
                    "peak_memory_mb": chunk["peak_memory_mb"],
                }
            )

    public_metadata = {
        "schema_version": manifest["schema_version"],
        "chunk_size": chunk_size,
        "warmups": manifest["configuration"]["warmups"],
        "repetitions": manifest["configuration"]["repetitions"],
        "sizes": manifest["configuration"]["sizes"],
    }
    return pd.DataFrame(run_rows), pd.DataFrame(chunk_rows), public_metadata


def measured_runs(runs: pd.DataFrame) -> pd.DataFrame:
    measured = runs.loc[runs["kind"] == "run"].copy()
    if measured.empty:
        raise ValueError("nenhuma execução medida foi encontrada")
    return measured


def aggregate_runs(runs: pd.DataFrame) -> pd.DataFrame:
    """Agrega somente runs medidos; aquecimentos nunca entram nas estatísticas."""
    measured = measured_runs(runs)
    metrics = [
        "wall_clock_seconds",
        "source_rows_per_second",
        "peak_memory_mb",
        "setup_write_seconds",
        "read_seconds",
        "transform_seconds",
        "write_seconds",
    ]
    rows: list[dict] = []
    for source_rows, group in measured.groupby("source_rows", sort=True):
        row: dict = {
            "source_rows": int(source_rows),
            "repetitions": len(group),
        }
        for metric in metrics:
            values = group[metric]
            mean = values.mean()
            row[f"{metric}_median"] = values.median()
            row[f"{metric}_mean"] = mean
            row[f"{metric}_std"] = values.std(ddof=1)
            row[f"{metric}_cv_percent"] = (
                values.std(ddof=1) / mean * 100 if mean else float("nan")
            )
        rows.append(row)
    return pd.DataFrame(rows)


def stage_medians(runs: pd.DataFrame) -> pd.DataFrame:
    measured = measured_runs(runs)
    columns = [f"{stage}_seconds" for stage in STAGE_COLUMNS]
    return measured.groupby("source_rows", sort=True)[columns].median()


def write_public_summary(summary: pd.DataFrame, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(destination, index=False, float_format="%.6f")
