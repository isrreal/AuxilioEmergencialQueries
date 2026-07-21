import json
from pathlib import Path

import pandas as pd
import pytest

from analysis.ingestion_baseline import (
    aggregate_runs,
    load_experiment,
    measured_runs,
    validate_manifest,
)


def test_validate_manifest_rejects_incomplete_protocol() -> None:
    with pytest.raises(ValueError, match="não foi concluído"):
        validate_manifest({"schema_version": 1, "status": "failed"})


def test_aggregate_runs_excludes_warmups() -> None:
    runs = pd.DataFrame(
        [
            {"source_rows": 100, "kind": "warmup", "wall_clock_seconds": 100.0},
            {"source_rows": 100, "kind": "run", "wall_clock_seconds": 2.0},
            {"source_rows": 100, "kind": "run", "wall_clock_seconds": 4.0},
        ]
    )
    for column in (
        "source_rows_per_second",
        "peak_memory_mb",
        "setup_write_seconds",
        "read_seconds",
        "transform_seconds",
        "write_seconds",
    ):
        runs[column] = runs["wall_clock_seconds"]

    summary = aggregate_runs(runs)

    assert summary.loc[0, "repetitions"] == 2
    assert summary.loc[0, "wall_clock_seconds_median"] == 3.0


def test_measured_runs_requires_at_least_one_measurement() -> None:
    with pytest.raises(ValueError, match="nenhuma execução"):
        measured_runs(pd.DataFrame([{"kind": "warmup"}]))


def test_load_experiment_rejects_report_outside_experiment(tmp_path: Path) -> None:
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
                        "report": "../outside.json",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="fora do diretório"):
        load_experiment(manifest_path)
