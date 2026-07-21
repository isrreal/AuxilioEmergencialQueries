import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.run_ingestion_baseline import (
    BenchmarkConfig,
    PlannedRun,
    build_manifest,
    ensure_destinations_available,
    plan_runs,
    run_benchmark,
    validate_report,
    write_json_atomic,
)


def make_config(tmp_path: Path) -> BenchmarkConfig:
    return BenchmarkConfig(
        sizes=(100_000, 1_000_000),
        chunk_size=100_000,
        warmups=1,
        repetitions=2,
        dataset_path=tmp_path / "dataset.csv",
        container_csv_path=Path("/data/dataset.csv"),
        output_dir=tmp_path / "artifacts",
        postgres_host_port=55_430,
        overwrite=False,
        skip_build=True,
    )


def test_plan_runs_creates_warmups_and_measured_runs(tmp_path: Path) -> None:
    runs = plan_runs(make_config(tmp_path))

    assert [(run.size, run.kind, run.number) for run in runs] == [
        (100_000, "warmup", 1),
        (100_000, "run", 1),
        (100_000, "run", 2),
        (1_000_000, "warmup", 1),
        (1_000_000, "run", 1),
        (1_000_000, "run", 2),
    ]


def test_existing_result_requires_explicit_overwrite(tmp_path: Path) -> None:
    run = plan_runs(make_config(tmp_path))[0]
    run.destination.parent.mkdir(parents=True)
    run.destination.touch()

    with pytest.raises(FileExistsError, match="--overwrite"):
        ensure_destinations_available([run], overwrite=False)


def test_validate_report_rejects_wrong_source_row_count(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    run = PlannedRun(100_000, "run", 1, tmp_path / "run.json")
    report = {
        "schema_version": 1,
        "status": "completed",
        "configuration": {"max_rows": 100_000, "chunk_size": 100_000},
        "totals": {"source_rows": 99_999},
    }

    with pytest.raises(ValueError, match="quantidade solicitada"):
        validate_report(report, run, config)


def test_write_json_atomic_produces_valid_json(tmp_path: Path) -> None:
    destination = tmp_path / "manifest.json"

    write_json_atomic({"schema_version": 1}, destination)

    assert json.loads(destination.read_text(encoding="utf-8")) == {"schema_version": 1}
    assert not list(tmp_path.glob("*.partial"))


def test_build_manifest_records_partial_progress(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    manifest = build_manifest(
        config,
        started_at=datetime.now(UTC),
        status="running",
        runs=[{"report": "rows-100000/run-01.json"}],
    )

    assert manifest["status"] == "running"
    assert manifest["completed_runs"] == 1
    assert manifest["finished_at"] is None


def test_run_benchmark_persists_failure_manifest(tmp_path: Path, monkeypatch) -> None:
    config = make_config(tmp_path)

    def fail_command(*args, **kwargs) -> None:
        raise subprocess.CalledProcessError(1, ["docker", "compose"])

    monkeypatch.setattr("scripts.run_ingestion_baseline.run_command", fail_command)

    with pytest.raises(subprocess.CalledProcessError):
        run_benchmark(config)

    manifest = json.loads((config.output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert manifest["completed_runs"] == 0
    assert manifest["error"]["type"] == "CalledProcessError"
