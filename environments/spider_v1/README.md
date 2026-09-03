# spider-v1

A native `verifiers.v1` taskset for the 1,034-question Spider 1.0 development split.

The model receives the question and can inspect the database through three read-only tools: list tables, show a table's `CREATE TABLE` statement, and run a `SELECT` or `WITH` query. Query results are limited to 100 rows.

The model must return one SQLite query. If the reply contains a SQL code block, the first block is extracted; otherwise the entire reply is treated as SQL.

## Setup and validation

From the repository root:

```bash
scripts/setup.sh spider
uv run validate spider-v1 --runtime.type subprocess
```

The setup script downloads the Spider dev data and a pinned copy of Spider's evaluator. Both are stored under `data/`.

## Evaluation

The API config gives the model the question and database tools:

```bash
uv run --env-file .env eval @ configs/spider-openai.toml --dry-run
uv run --env-file .env eval @ configs/spider-openai.toml -n 3 --no-push
uv run --env-file .env eval @ configs/spider-openai.toml --no-push
```

Override its model with `--model <model>`. For a local llama.cpp server, use the equivalent `configs/spider-qwen3.5-4b-llama-cpp.toml` config.

## Scoring

- `execution_accuracy` is the reward. It executes the predicted and gold queries on the original database and compares their results. Duplicate rows matter; row order matters when the gold query contains `ORDER BY`; equivalent output-column permutations are accepted.
- `exact_set_match` is a structural metric based on Spider's evaluator. It does not contribute to the reward.

This taskset does not calculate Spider Test Suite Accuracy. Results are therefore not directly comparable with the current Spider leaderboard protocol.

## Configuration

- `env.taskset.split`: only `dev` is supported.
- `env.taskset.data_dir`: Spider data directory; defaults to `data/spider_data`.
- `env.taskset.evaluator_dir`: Spider evaluator directory; defaults to `data/test-suite-sql-eval`.
