import json
from pathlib import Path

import pandas as pd
import pytest

from analysis.ingestion_memory import (
    aggregate_memory_trajectory,
    load_memory_experiment,
    measured_memory_chunks,
    summarize_memory_runs,
    validate_memory_chunk,
)


def make_memory_chunk(*, responsavel_identifiers: int = 10) -> dict:
    checkpoints = {
        "before_read": {"current_rss_mb": 100.0, "peak_rss_mb": 120.0},
        "after_read": {"current_rss_mb": 130.0, "peak_rss_mb": 130.0},
        "after_transform": {"current_rss_mb": 180.0, "peak_rss_mb": 180.0},
        "after_write": {"current_rss_mb": 160.0, "peak_rss_mb": 180.0},
        "after_cleanup": {"current_rss_mb": 110.0, "peak_rss_mb": 180.0},
    }
    return {
        "index": 1,
        "source_rows": 100,
        "memory_mb": {
            **checkpoints,
            "dataframes_after_transform": {
                "source_chunk": 20.0,
                "responsavel": 5.0,
                "beneficiario": 10.0,
                "auxilio": 8.0,
            },
        },
        "deduplication_state": {
            "responsavel_identifiers": responsavel_identifiers,
            "beneficiario_identifiers": 20,
        },
    }


def test_validate_memory_chunk_requires_cleanup_checkpoint() -> None:
    chunk = make_memory_chunk()
    del chunk["memory_mb"]["after_cleanup"]

    with pytest.raises(ValueError, match="after_cleanup"):
        validate_memory_chunk(chunk)


def test_load_memory_experiment_derives_chunk_memory_metrics(tmp_path: Path) -> None:
    report_dir = tmp_path / "rows-100"
    report_dir.mkdir()
    report_path = report_dir / "run-01.json"
    report_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": "completed",
                "configuration": {"max_rows": 100, "chunk_size": 100},
                "totals": {"source_rows": 100},
                "chunks": [make_memory_chunk()],
            }
        ),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": "completed",
                "completed_runs": 1,
                "configuration": {
                    "chunk_size": 100,
                    "warmups": 0,
                    "repetitions": 1,
                    "sizes": [100],
                },
                "runs": [
                    {
                        "size": 100,
                        "kind": "run",
                        "number": 1,
                        "report": "rows-100/run-01.json",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    chunks, metadata = load_memory_experiment(manifest_path)

    assert metadata["chunk_size"] == 100
    assert chunks.loc[0, "processed_rows"] == 100
    assert chunks.loc[0, "active_chunk_rss_high_mb"] == 180.0
    assert chunks.loc[0, "rss_change_after_cleanup_mb"] == 10.0
    assert chunks.loc[0, "rss_drop_from_active_high_mb"] == 70.0


def test_memory_analysis_excludes_warmups_and_summarizes_growth() -> None:
    chunks = pd.DataFrame(
        [
            {
                "source_rows": 200,
                "kind": "warmup",
                "run": 1,
                "processed_rows": 100,
                "current_rss_before_read_mb": 1.0,
            },
            {
                "source_rows": 200,
                "kind": "run",
                "run": 1,
                "processed_rows": 100,
                "current_rss_before_read_mb": 100.0,
                "current_rss_after_read_mb": 120.0,
                "current_rss_after_transform_mb": 140.0,
                "current_rss_after_write_mb": 140.0,
                "current_rss_after_cleanup_mb": 110.0,
                "active_chunk_rss_high_mb": 140.0,
                "responsavel_identifiers": 10,
                "beneficiario_identifiers": 20,
                "dataframe_source_chunk_mb": 20.0,
                "dataframe_responsavel_mb": 5.0,
                "dataframe_beneficiario_mb": 10.0,
                "dataframe_auxilio_mb": 8.0,
            },
            {
                "source_rows": 200,
                "kind": "run",
                "run": 1,
                "processed_rows": 200,
                "current_rss_before_read_mb": 110.0,
                "current_rss_after_read_mb": 130.0,
                "current_rss_after_transform_mb": 150.0,
                "current_rss_after_write_mb": 150.0,
                "current_rss_after_cleanup_mb": 125.0,
                "active_chunk_rss_high_mb": 150.0,
                "responsavel_identifiers": 20,
                "beneficiario_identifiers": 40,
                "dataframe_source_chunk_mb": 20.0,
                "dataframe_responsavel_mb": 5.0,
                "dataframe_beneficiario_mb": 10.0,
                "dataframe_auxilio_mb": 8.0,
            },
        ]
    )

    measured = measured_memory_chunks(chunks)
    trajectory = aggregate_memory_trajectory(chunks)
    summary = summarize_memory_runs(chunks)

    assert len(measured) == 2
    assert len(trajectory) == 2
    assert summary.loc[0, "cleanup_rss_growth_mb"] == 15.0
    assert summary.loc[0, "total_rss_growth_mb"] == 25.0
    assert summary.loc[0, "cleanup_rss_deduplication_correlation"] == 1.0
