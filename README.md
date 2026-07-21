# Emergency Aid: data ingestion and performance experiments

Portfolio project for studying the ingestion, transformation, storage, and querying of a
large public dataset in PostgreSQL. The goal is to build reproducible, technically
defensible experiments and publish both their results and their limitations.

This repository does not assume that any tool, index, or chunk size is universally better.
Every performance decision should be supported by a hypothesis, controlled variables,
repeated runs, and structured results.

## Current status

| Area | Status |
|---|---|
| Alembic-managed PostgreSQL schema | Implemented |
| Chunked ingestion with Pandas and `asyncpg COPY` | Implemented |
| Automated runner with an isolated database per run | Implemented |
| Baselines for 100 thousand and 1 million rows | Published |
| Per-stage chunk memory instrumentation | Implemented |
| Baseline analysis notebook | Implemented |
| Retained-memory growth experiment | Next step |
| PostgreSQL staging-based deduplication | Planned |
| Chunk-size comparison | Planned |
| Pandas, Polars, and possible PySpark comparison | Planned |
| Controlled index benchmarks with `EXPLAIN ANALYZE` | Planned |

The API and dashboard are functional interfaces for exploring queries, but they are not yet
the final scientific SQL benchmark protocol. HTTP elapsed time combines database execution,
serialization, and network transfer costs.

## Published baseline results

The first protocol used 100-thousand-row chunks, one warm-up run, and three measured runs.
The values below are medians from the machine where the experiment was executed; they are
not performance guarantees for other environments.

| Source rows | Wall-clock time | Throughput | Peak RSS |
|---:|---:|---:|---:|
| 100,000 | 4.80 s | 20,832 rows/s | 214.25 MiB |
| 1,000,000 | 49.65 s | 20,139 rows/s | 387.91 MiB |

The aggregated data is available in
[`results/ingestion-baseline-summary.csv`](results/ingestion-baseline-summary.csv), and the
methodology is documented in
[`notebooks/01_ingestion_baseline.ipynb`](notebooks/01_ingestion_baseline.ipynb).

Growth in peak RSS alone does not prove memory retention. The pipeline now collects current
RSS before and after each stage, together with the cardinality of its deduplication state.
The repeated experiment using these new checkpoints has not been published yet.

## Architecture

```text
Local CSV
   │
   ▼
Pandas: chunked reading and normalization
   │
   ▼
asyncpg: PostgreSQL binary COPY
   │
   ▼
PostgreSQL 15
   │
   ├── FastAPI ── Streamlit
   │
   └── JSON reports ── analysis modules ── JupyterLab
```

Docker Compose services:

- `db`: PostgreSQL 15 with persistent storage;
- `api`: FastAPI and the ingestion CLI;
- `app_runner`: Streamlit dashboard;
- `notebook`: optional JupyterLab service enabled through a profile.

Main technologies: Python 3.11, Pandas, FastAPI, SQLAlchemy, asyncpg, PostgreSQL, Alembic,
Docker Compose, Pytest, Ruff, and JupyterLab.

## Data model

The source CSV is normalized into three tables:

```text
responsavel
    1
    │
    N
beneficiario
    1
    │
    N
auxilio
```

- `responsavel`: one row per responsible party NIS identifier;
- `beneficiario`: one row per beneficiary NIS identifier;
- `auxilio`: payment-installment history associated with each beneficiary.

The baseline schema contains primary and foreign keys. Experimental secondary indexes are
not part of the initial migration: a future benchmark runner will create and remove them
explicitly.

## Relevant project structure

```text
.
├── alembic/                       # schema migrations
├── analysis/
│   ├── ingestion_baseline.py      # baseline validation and aggregation
│   └── ingestion_memory.py        # memory-checkpoint tabulation
├── app/
│   ├── api/                       # FastAPI endpoints
│   ├── core/
│   │   ├── configs.py             # environment-driven configuration
│   │   ├── database.py            # asynchronous engine and sessions
│   │   └── insert.py              # ingestion pipeline
│   └── models/                    # SQLAlchemy models
├── notebooks/
│   └── 01_ingestion_baseline.ipynb
├── results/                       # versioned aggregate results
├── scripts/
│   └── run_ingestion_baseline.py  # reproducible experiment runner
├── tests/
├── dashboard.py
├── docker-compose.yml
└── Dockerfile
```

Local datasets and raw reports under `artifacts/` are not versioned. Public results must be
aggregated and must not expose CPF, NIS, or local filesystem paths.

## Prerequisites

- Docker with the Docker Compose plugin;
- Python 3 on the host to run the experiment orchestrator;
- a `dataset/auxilio_emergencial.csv` file;
- enough memory and storage for the selected input size.

The dataset is not distributed with this repository. The complete source contains hundreds
of millions of rows; always begin with `--max-rows`.

## Configuration

```bash
git clone https://github.com/isrreal/AuxilioEmergencialQueries.git
cd AuxilioEmergencialQueries
cp .env.example .env
```

Edit `.env` and replace the example password. The available variables are documented in
`.env.example`; Docker Compose constructs the application's internal database URL, so it
does not need to be written manually.

Start PostgreSQL and apply the migrations:

```bash
docker compose up -d db
docker compose run --rm api alembic upgrade head
```

`alembic upgrade head` creates the `pg_trgm` extension and the three tables. Do not use
`alembic stamp head` as a substitute: `stamp` only changes the recorded revision and does
not execute structural changes.

## Run a controlled ingestion

Initial 100-thousand-row test:

```bash
mkdir -p artifacts
docker compose run --rm api python -m app.core.insert \
  --chunk-size 100000 \
  --max-rows 100000 \
  > artifacts/ingestion-smoke.json
```

Progress messages are written to `stderr`, while the JSON report is written to `stdout`.
The `--report-path` option can also write the JSON directly to a file accessible inside the
execution environment.

To use another file mounted under `dataset/`:

```bash
docker compose run --rm api python -m app.core.insert \
  --csv-path /data/another_file.csv \
  --chunk-size 100000 \
  --max-rows 100000
```

The CLI requires exactly one explicit scope option:

- `--max-rows N` for a partial load;
- `--all-rows` to process the complete file.

### Current ingestion limitations

- the ingestion is not idempotent and must run against an empty database;
- the deduplication sets grow with the accumulated number of distinct identifiers;
- each target table is written in an independent transaction;
- a failure may leave a partially committed load;
- Pandas reading and transformations are synchronous despite the asynchronous driver;
- the RSS checkpoints depend on Linux `procfs`;
- the reported process memory covers Python, not PostgreSQL.

These limitations are preserved in the baseline so future refactorings can be compared under
the same protocol.

## Run the automated protocol

The runner uses an isolated Compose project, recreates only that project's database before
each run, applies migrations, validates each report, and maintains an incremental manifest:

```bash
python3 scripts/run_ingestion_baseline.py \
  --sizes 100000 1000000 \
  --chunk-size 100000 \
  --warmups 1 \
  --repetitions 3 \
  --confirm-reset
```

`--confirm-reset` is required because the isolated volume is removed repeatedly. The regular
Compose database is not changed. Existing results require `--overwrite`; use `--skip-build`
only when the `csgbd-app:local` image is already current.

```text
artifacts/ingestion/
├── manifest.json
├── rows-100000/
│   ├── warmup-01.json
│   ├── run-01.json
│   ├── run-02.json
│   └── run-03.json
└── rows-1000000/
    └── ...
```

If a run fails or is interrupted, the manifest preserves completed runs and records either
`failed` or `interrupted`. Only a fully completed protocol receives `completed`.

## Memory instrumentation

Every chunk records the following checkpoints:

```text
before_read
after_read
after_transform
after_write
after_cleanup
```

Each checkpoint contains:

- `current_rss_mb`, derived from `VmRSS`;
- `peak_rss_mb`, derived from `VmHWM`.

The report also includes the deep memory footprint of each DataFrame and the number of
identifiers stored in the deduplication sets. The analysis module converts these structures
into one tabular row per chunk:

```python
from pathlib import Path

from analysis.ingestion_memory import load_memory_experiment

chunks, metadata = load_memory_experiment(
    Path("artifacts/ingestion/manifest.json")
)
```

High RSS after `del` does not automatically imply a leak: the allocator may retain unused
memory for reuse. The analysis must relate checkpoints, set cardinality, and repeated runs
before inferring algorithmic retention.

## JupyterLab

```bash
docker compose --profile notebook up notebook
```

Open `http://127.0.0.1:8889`. The port is bound only to the local interface, and the service
does not require a token. Adjust `LOCAL_UID` and `LOCAL_GID` in `.env` if notebook files are
created with incorrect host permissions.

Reports under `artifacts/` are mounted read-only; aggregate results can be written to
`results/`.

## Exploratory API and dashboard

After applying migrations and ingesting data:

```bash
docker compose up -d api app_runner
```

- API: `http://localhost:8000`;
- OpenAPI: `http://localhost:8000/docs`;
- dashboard: `http://localhost:8501`;
- health check: `GET /health`.

Queries currently available under `/api/v1/consultas`:

```http
GET /total-gasto-por-uf
GET /beneficiarios-por-municipio
GET /beneficiarios-responsaveis
GET /beneficiarios-multiplas-parcelas
GET /beneficiarios-por-nome
GET /listar-beneficiarios
GET /beneficiario/{nis}
```

Some routes support JSON or NDJSON and can disable index, index-only, and bitmap scans for
exploratory comparisons. This does not replace a controlled SQL benchmark with explicitly
managed indexes, `EXPLAIN (ANALYZE, BUFFERS)`, and documented cache state.

## Code quality

Rebuild the image before testing when new files have been added:

```bash
docker compose build api
docker compose run --rm --no-deps api python -m pytest -q
```

Run the linter:

```bash
docker compose run --rm --no-deps api python -m ruff check .
```

Install local hooks with:

```bash
pre-commit install
```

## Planned experiments

1. Measure post-cleanup RSS and deduplication-set cardinality at multiple scales.
2. Replace global Python deduplication with PostgreSQL staging and consolidation.
3. Compare chunk sizes under an explicit memory constraint.
4. Compare `COPY` with batched `INSERT`, isolating the database write stage.
5. Compare Pandas and Polars with equivalent transformations and outputs.
6. Build index benchmarks that report plans, buffers, creation cost, and storage overhead.

A synchronous Psycopg 3 ingestion implementation will also be evaluated. The goal is not to
assume that synchronous code is faster, but to determine whether it reduces complexity
without a material regression. The API may remain asynchronous because its concurrent
request workload differs from a sequential ingestion CLI.

## Privacy and reproducibility

- do not commit the raw dataset;
- do not publish CPF, NIS, or identifiable samples;
- do not publish credentials or `.env` files;
- keep raw reports under `artifacts/`;
- publish only reproducible aggregates under `results/`;
- record hardware, parameters, and repetition counts when publishing results.

## Contact

Author: [isrreal](https://github.com/isrreal)
