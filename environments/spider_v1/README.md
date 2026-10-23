# spider-v1

A native `verifiers.v1` taskset for the 1,034-question Spider 1.0 development split.

The model receives the question and can inspect the database through three read-only tools: list tables, show a table's `CREATE TABLE` statement, and run a `SELECT` or `WITH` query. Query results are limited to 100 rows.

The model must return one SQLite query. If the reply contains a SQL code block, the first block is extracted; otherwise the entire reply is treated as SQL.

## Setup and validation

From the repository root:

```bash
./scripts/download_spider.sh
uv run vf-validate spider-v1 --runtime.type subprocess
```

The setup script downloads the Spider dev data under `data/`.

## Evaluation

The API config gives the model the question and database tools:

```bash
uv run --env-file .env vf-eval @ configs/spider-gpt-5.6-luna.toml --dry-run
uv run --env-file .env vf-eval @ configs/spider-gpt-5.6-luna.toml -n 3 --no-push
uv run --env-file .env vf-eval @ configs/spider-gpt-5.6-luna.toml --no-push
```

Override its model with `--model <model>`. For a local llama.cpp server, use the equivalent `configs/spider-qwen3.5-4b.toml` config.

### Docker

```bash
docker build -f Dockerfile.evaluator -t evaluator .
docker compose -f compose.llama-cpp.yaml run --rm evaluator \
  vf-eval @ configs/spider-qwen3.5-4b.toml --no-push
```

Start llama.cpp first. See [`docs/docker.md`](../../docs/docker.md) for setup, API-model runs, mounts, and upload instructions.

## Scoring

`execution_accuracy` is the only task score. It executes the predicted and gold queries on the original database and compares their results. Duplicate rows matter; row order matters when the gold query contains `ORDER BY`; equivalent output-column permutations are accepted.

## Configuration

- `env.taskset.split`: only `dev` is supported.
- `env.taskset.data_dir`: Spider data directory; defaults to `data/spider_data`.
