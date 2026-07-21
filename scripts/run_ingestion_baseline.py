"""Executa benchmarks reproduzíveis da ingestão em um Compose isolado."""

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence, TextIO
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_PROJECT_NAME = "csgbd-ingestion-baseline"
DEFAULT_DATASET_PATH = Path("dataset/auxilio_emergencial.csv")
DEFAULT_OUTPUT_DIR = Path("artifacts/ingestion")
DEFAULT_POSTGRES_HOST_PORT = 55430


@dataclass(frozen=True)
class BenchmarkConfig:
    sizes: tuple[int, ...]
    chunk_size: int
    warmups: int
    repetitions: int
    dataset_path: Path
    container_csv_path: Path
    output_dir: Path
    postgres_host_port: int
    overwrite: bool
    skip_build: bool


@dataclass(frozen=True)
class PlannedRun:
    size: int
    kind: str
    number: int
    destination: Path


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("o valor deve ser maior que zero")
    return parsed


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("o valor não pode ser negativo")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Executa a ingestão repetidamente em um banco isolado e salva os relatórios JSON."
        )
    )
    parser.add_argument("--sizes", nargs="+", type=positive_int, required=True)
    parser.add_argument("--chunk-size", type=positive_int, default=100_000)
    parser.add_argument("--warmups", type=non_negative_int, default=1)
    parser.add_argument("--repetitions", type=positive_int, default=3)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--postgres-host-port",
        type=positive_int,
        default=DEFAULT_POSTGRES_HOST_PORT,
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument(
        "--confirm-reset",
        action="store_true",
        help=(
            "confirma a remoção repetida do volume exclusivo "
            f"do projeto Compose '{COMPOSE_PROJECT_NAME}'"
        ),
    )
    return parser


def resolve_config(args: argparse.Namespace, parser: argparse.ArgumentParser) -> BenchmarkConfig:
    if not args.confirm_reset:
        parser.error("--confirm-reset é obrigatório porque o benchmark remove seu banco isolado")

    dataset_path = (PROJECT_ROOT / args.dataset_path).resolve()
    dataset_root = (PROJECT_ROOT / "dataset").resolve()
    try:
        relative_dataset_path = dataset_path.relative_to(dataset_root)
    except ValueError:
        parser.error("--dataset-path deve apontar para um arquivo dentro de dataset/")
    if not dataset_path.is_file():
        parser.error(f"dataset não encontrado: {dataset_path}")

    output_dir = (PROJECT_ROOT / args.output_dir).resolve()
    sizes = tuple(dict.fromkeys(args.sizes))
    return BenchmarkConfig(
        sizes=sizes,
        chunk_size=args.chunk_size,
        warmups=args.warmups,
        repetitions=args.repetitions,
        dataset_path=dataset_path,
        container_csv_path=Path("/data") / relative_dataset_path,
        output_dir=output_dir,
        postgres_host_port=args.postgres_host_port,
        overwrite=args.overwrite,
        skip_build=args.skip_build,
    )


def plan_runs(config: BenchmarkConfig) -> list[PlannedRun]:
    runs: list[PlannedRun] = []
    for size in config.sizes:
        size_dir = config.output_dir / f"rows-{size}"
        for number in range(1, config.warmups + 1):
            runs.append(PlannedRun(size, "warmup", number, size_dir / f"warmup-{number:02d}.json"))
        for number in range(1, config.repetitions + 1):
            runs.append(PlannedRun(size, "run", number, size_dir / f"run-{number:02d}.json"))
    return runs


def ensure_destinations_available(runs: Sequence[PlannedRun], overwrite: bool) -> None:
    existing = [run.destination for run in runs if run.destination.exists()]
    if existing and not overwrite:
        formatted = "\n".join(f"- {path}" for path in existing)
        raise FileExistsError(
            "os seguintes resultados já existem; use --overwrite para substituí-los:\n"
            f"{formatted}"
        )


def compose_command(*arguments: str) -> list[str]:
    return ["docker", "compose", "--project-name", COMPOSE_PROJECT_NAME, *arguments]


def run_command(
    command: Sequence[str],
    *,
    environment: dict[str, str],
    stdout: TextIO | None = None,
) -> None:
    print(f"$ {' '.join(command)}", file=sys.stderr)
    subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        stdout=stdout,
        check=True,
    )


def validate_report(report: dict, planned_run: PlannedRun, config: BenchmarkConfig) -> None:
    if report.get("schema_version") != 1 or report.get("status") != "completed":
        raise ValueError("relatório incompleto ou com schema_version incompatível")

    report_config = report.get("configuration", {})
    if report_config.get("max_rows") != planned_run.size:
        raise ValueError("o relatório não corresponde ao volume solicitado")
    if report_config.get("chunk_size") != config.chunk_size:
        raise ValueError("o relatório não corresponde ao chunk_size solicitado")

    totals = report.get("totals", {})
    if totals.get("source_rows") != planned_run.size:
        raise ValueError("a ingestão não processou a quantidade solicitada de linhas")


def execute_ingestion(
    planned_run: PlannedRun,
    config: BenchmarkConfig,
    environment: dict[str, str],
) -> dict:
    planned_run.destination.parent.mkdir(parents=True, exist_ok=True)
    partial_path = planned_run.destination.with_name(
        f".{planned_run.destination.name}.{uuid4().hex}.partial"
    )
    command = compose_command(
        "run",
        "--rm",
        "api",
        "python",
        "-m",
        "app.core.insert",
        "--csv-path",
        str(config.container_csv_path),
        "--chunk-size",
        str(config.chunk_size),
        "--max-rows",
        str(planned_run.size),
    )

    try:
        with partial_path.open("w", encoding="utf-8") as partial_file:
            run_command(command, environment=environment, stdout=partial_file)
        report = json.loads(partial_path.read_text(encoding="utf-8"))
        validate_report(report, planned_run, config)
        partial_path.replace(planned_run.destination)
        return report
    finally:
        partial_path.unlink(missing_ok=True)


def reset_database(environment: dict[str, str]) -> None:
    run_command(
        compose_command("down", "--volumes", "--remove-orphans"),
        environment=environment,
    )
    run_command(compose_command("up", "--detach", "--wait", "db"), environment=environment)
    run_command(
        compose_command("run", "--rm", "api", "alembic", "upgrade", "head"),
        environment=environment,
    )


def manifest_entry(planned_run: PlannedRun, report: dict, output_dir: Path) -> dict:
    totals = report["totals"]
    return {
        "size": planned_run.size,
        "kind": planned_run.kind,
        "number": planned_run.number,
        "report": str(planned_run.destination.relative_to(output_dir)),
        "wall_clock_seconds": totals["timing_seconds"]["wall_clock"],
        "source_rows_per_second": totals["source_rows_per_second"],
        "peak_memory_mb": totals["peak_memory_mb"],
    }


def write_json_atomic(data: dict, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.partial")
    try:
        temporary.write_text(
            f"{json.dumps(data, ensure_ascii=False, indent=2)}\n",
            encoding="utf-8",
        )
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def build_manifest(
    config: BenchmarkConfig,
    *,
    started_at: datetime,
    status: str,
    runs: list[dict],
    error: BaseException | None = None,
) -> dict:
    return {
        "schema_version": 1,
        "status": status,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(UTC).isoformat() if status != "running" else None,
        "compose_project": COMPOSE_PROJECT_NAME,
        "configuration": {
            "sizes": config.sizes,
            "chunk_size": config.chunk_size,
            "warmups": config.warmups,
            "repetitions": config.repetitions,
            "dataset_path": str(config.dataset_path),
            "postgres_host_port": config.postgres_host_port,
        },
        "completed_runs": len(runs),
        "error": (
            {"type": type(error).__name__, "message": str(error)} if error is not None else None
        ),
        "runs": runs,
    }


def run_benchmark(config: BenchmarkConfig) -> None:
    runs = plan_runs(config)
    ensure_destinations_available(runs, config.overwrite)
    manifest_path = config.output_dir / "manifest.json"
    if manifest_path.exists() and not config.overwrite:
        raise FileExistsError(
            f"o manifesto já existe: {manifest_path}; use --overwrite para substituí-lo"
        )
    environment = os.environ.copy()
    environment["POSTGRES_HOST_PORT"] = str(config.postgres_host_port)
    manifest_runs: list[dict] = []
    started_at = datetime.now(UTC)
    status = "running"
    failure: BaseException | None = None

    print(
        f"Projeto Compose isolado: {COMPOSE_PROJECT_NAME}\n"
        f"Dataset: {config.dataset_path}\n"
        f"Execuções planejadas: {len(runs)}",
        file=sys.stderr,
    )

    write_json_atomic(
        build_manifest(config, started_at=started_at, status=status, runs=manifest_runs),
        manifest_path,
    )
    try:
        if not config.skip_build:
            run_command(compose_command("build", "api"), environment=environment)
        for index, planned_run in enumerate(runs, start=1):
            print(
                f"\n[{index}/{len(runs)}] {planned_run.kind} {planned_run.number} "
                f"com {planned_run.size} linhas",
                file=sys.stderr,
            )
            reset_database(environment)
            report = execute_ingestion(planned_run, config, environment)
            manifest_runs.append(manifest_entry(planned_run, report, config.output_dir))
            write_json_atomic(
                build_manifest(
                    config,
                    started_at=started_at,
                    status=status,
                    runs=manifest_runs,
                ),
                manifest_path,
            )
        status = "completed"
    except KeyboardInterrupt as exc:
        status = "interrupted"
        failure = exc
        raise
    except BaseException as exc:
        status = "failed"
        failure = exc
        raise
    finally:
        runtime_failure = failure
        finalization_error: Exception | None = None
        try:
            run_command(
                compose_command("down", "--volumes", "--remove-orphans"),
                environment=environment,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            finalization_error = exc
            if failure is None:
                status = "failed"
                failure = exc
            print(f"aviso: não foi possível limpar o Compose isolado: {exc}", file=sys.stderr)

        try:
            write_json_atomic(
                build_manifest(
                    config,
                    started_at=started_at,
                    status=status,
                    runs=manifest_runs,
                    error=failure,
                ),
                manifest_path,
            )
        except Exception as exc:
            if finalization_error is None:
                finalization_error = exc
            print(f"aviso: não foi possível finalizar o manifesto: {exc}", file=sys.stderr)

        if runtime_failure is None and finalization_error is not None:
            raise finalization_error


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    config = resolve_config(parser.parse_args(argv), parser)
    try:
        run_benchmark(config)
    except KeyboardInterrupt:
        parser.exit(130, "benchmark interrompido; consulte o manifesto parcial\n")
    except (FileExistsError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"erro: {exc}\n")


if __name__ == "__main__":
    main()
