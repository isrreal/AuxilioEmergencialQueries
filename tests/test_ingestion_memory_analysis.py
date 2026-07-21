import json
from pathlib import Path

import pytest

from analysis.ingestion_memory import load_memory_experiment, validate_memory_chunk


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
