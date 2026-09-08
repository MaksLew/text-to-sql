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

The API config gives the model the question, evidence, and database tools:

```bash
uv run --env-file .env eval @ configs/bird-gpt-5.6-luna.toml --dry-run
uv run --env-file .env eval @ configs/bird-gpt-5.6-luna.toml -n 3 --no-push
uv run --env-file .env eval @ configs/bird-gpt-5.6-luna.toml --no-push
```

Override its model with `--model <model>`. For a local llama.cpp server, use `configs/bird-qwen3.5-4b.toml`.

## Scoring

`execution_accuracy` is the only reward. It executes the predicted and gold queries once on the supplied SQLite database and compares their result rows as Python sets. Row order and duplicate counts are ignored.

`structural_exact_match` is a diagnostic metric implemented with SQLGlot. It compares normalized SQLite syntax trees after ignoring literal values, `DISTINCT`, aliases, identifier quoting and casing, select/group and boolean-term order, explicit `INNER`, and foreign-key-equivalent columns. It is not an official BIRD metric.

## Configuration

- `env.taskset.split`: only `dev` is supported.
- `env.taskset.data_dir`: extracted BIRD data directory; defaults to `data/bird/dev_20251106`.
