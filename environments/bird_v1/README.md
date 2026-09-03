# bird-v1

A native `verifiers.v1` taskset for the 1,534-question BIRD development split.

Each task gives the model a question and the benchmark's evidence field supplying necessary domain knowledge. The model can:

- list tables;
- inspect a table's `CREATE TABLE` statement and up to three sample rows;
- run a read-only `SELECT`, `WITH`, or `EXPLAIN` query.

Query results are limited to 100 rows. The model must finish with one SQLite query.

## Dataset version

The download script uses BIRD's `dev_20251106` annotations from the official [`birdsql/bird_sql_dev_20251106`](https://huggingface.co/datasets/birdsql/bird_sql_dev_20251106) release.

Downloaded files are stored under `data/bird/`. Their use remains subject to BIRD's upstream terms.

## Setup and validation

From the repository root:

```bash
scripts/setup.sh bird
uv run validate bird-v1 --runtime.type subprocess
```

## Evaluation

```bash
uv run --env-file .env eval @ configs/bird-agentic-openai.toml -n 3 --no-push
```

For local llama.cpp evaluation, use `configs/bird-agentic-qwen3.5-4b-llama-cpp.toml`.

## Scoring

`execution_accuracy` is the only reward. It executes the predicted and gold queries once on the supplied SQLite database and compares their result rows as Python sets. Row order and duplicate counts are ignored.

The scorer is implemented in this package rather than imported from BIRD's evaluation code.

## Configuration

- `env.taskset.split`: only `dev` is supported.
- `env.taskset.data_dir`: extracted BIRD data directory; defaults to `data/bird/dev_20251106`.
