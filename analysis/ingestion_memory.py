"""Validação e tabulação dos checkpoints de memória da ingestão."""

from pathlib import Path

import pandas as pd

from analysis.ingestion_baseline import (
    read_json,
    validate_manifest,
    validate_report,
)

MEMORY_CHECKPOINTS = (
    "before_read",
    "after_read",
    "after_transform",
    "after_write",
    "after_cleanup",
)
DATAFRAME_NAMES = ("source_chunk", "responsavel", "beneficiario", "auxilio")
DEDUPLICATION_ENTITIES = ("responsavel_identifiers", "beneficiario_identifiers")


def _non_negative_number(value: object, field: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        raise ValueError(f"métrica de memória inválida: {field}")
    return float(value)


def validate_memory_chunk(chunk: dict) -> None:
    """Exige todos os checkpoints necessários para comparar chunks."""
    memory = chunk.get("memory_mb")
    if not isinstance(memory, dict):
        raise ValueError("chunk sem instrumentação de memória")

    for checkpoint in MEMORY_CHECKPOINTS:
        snapshot = memory.get(checkpoint)
        if not isinstance(snapshot, dict):
            raise ValueError(f"checkpoint de memória ausente: {checkpoint}")
        current = _non_negative_number(
            snapshot.get("current_rss_mb"), f"{checkpoint}.current_rss_mb"
        )
        peak = _non_negative_number(snapshot.get("peak_rss_mb"), f"{checkpoint}.peak_rss_mb")
        if current > peak:
            raise ValueError(f"RSS atual maior que o pico em {checkpoint}")

    dataframes = memory.get("dataframes_after_transform")
    if not isinstance(dataframes, dict):
        raise ValueError("memória profunda dos DataFrames ausente")
    for name in DATAFRAME_NAMES:
        _non_negative_number(dataframes.get(name), f"dataframes_after_transform.{name}")

    deduplication = chunk.get("deduplication_state")
    if not isinstance(deduplication, dict):
        raise ValueError("estado da deduplicação ausente")
    for entity in DEDUPLICATION_ENTITIES:
        value = deduplication.get(entity)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"cardinalidade de deduplicação inválida: {entity}")


def load_memory_experiment(manifest_path: Path) -> tuple[pd.DataFrame, dict]:
    """Carrega relatórios instrumentados em uma linha por chunk."""
    manifest_path = manifest_path.resolve()
    manifest = read_json(manifest_path)
    validate_manifest(manifest)
    chunk_size = manifest["configuration"]["chunk_size"]
    rows: list[dict] = []

    for entry in manifest["runs"]:
        report_path = (manifest_path.parent / entry["report"]).resolve()
        try:
            report_path.relative_to(manifest_path.parent)
        except ValueError as exc:
            raise ValueError("relatório fora do diretório do experimento") from exc

        report = read_json(report_path)
        validate_report(report, entry, chunk_size)
        processed_rows = 0
        previous_deduplication = {entity: 0 for entity in DEDUPLICATION_ENTITIES}

        for chunk in report["chunks"]:
            validate_memory_chunk(chunk)
            processed_rows += chunk["source_rows"]
            memory = chunk["memory_mb"]
            dataframes = memory["dataframes_after_transform"]
            deduplication = chunk["deduplication_state"]
            current_rss = {
                checkpoint: float(memory[checkpoint]["current_rss_mb"])
                for checkpoint in MEMORY_CHECKPOINTS
            }
            active_peak = max(
                current_rss[checkpoint]
                for checkpoint in ("after_read", "after_transform", "after_write")
            )

            for entity in DEDUPLICATION_ENTITIES:
                if deduplication[entity] < previous_deduplication[entity]:
                    raise ValueError(f"cardinalidade de deduplicação diminuiu: {entity}")
                previous_deduplication[entity] = deduplication[entity]

            rows.append(
                {
                    "source_rows": entry["size"],
                    "kind": entry["kind"],
                    "run": entry["number"],
                    "chunk": chunk["index"],
                    "processed_rows": processed_rows,
                    **{
                        f"current_rss_{checkpoint}_mb": current_rss[checkpoint]
                        for checkpoint in MEMORY_CHECKPOINTS
                    },
                    "active_chunk_rss_high_mb": active_peak,
                    "rss_change_after_cleanup_mb": (
                        current_rss["after_cleanup"] - current_rss["before_read"]
                    ),
                    "rss_drop_from_active_high_mb": (
                        active_peak - current_rss["after_cleanup"]
                    ),
                    **{
                        f"dataframe_{name}_mb": float(dataframes[name])
                        for name in DATAFRAME_NAMES
                    },
                    **deduplication,
                }
            )

    metadata = {
        "schema_version": manifest["schema_version"],
        "chunk_size": chunk_size,
        "warmups": manifest["configuration"]["warmups"],
        "repetitions": manifest["configuration"]["repetitions"],
        "sizes": manifest["configuration"]["sizes"],
    }
    return pd.DataFrame(rows), metadata
