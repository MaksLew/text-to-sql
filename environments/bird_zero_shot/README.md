# BIRD-zero-shot

A native `verifiers.v1` taskset for the 1,534-question BIRD development split.

Each task gives the model a question, the benchmark's evidence field supplying necessary domain knowledge, and the database schema as `CREATE TABLE` statements in the user prompt. The system prompt instructs the model to return only one correct, read-only SQLite query.

No tools, sample rows, or examples are provided. The model has one turn to generate the query using the `null` harness.

## Dataset version

The download script uses BIRD's `dev_20251106` annotations from the official [`birdsql/bird_sql_dev_20251106`](https://huggingface.co/datasets/birdsql/bird_sql_dev_20251106) release.

Downloaded files are stored under `data/bird/`. Their use remains subject to BIRD's upstream terms.

## Setup and validation

From the repository root:

```bash
./scripts/download_bird.sh
uv run --package bird-zero-shot vf-validate bird-zero-shot --runtime.type subprocess
```

## Evaluation

The API config gives the model the question, evidence, and database schema:

```bash
uv run --package bird-zero-shot --env-file .env vf-eval @ configs/bird-zero-shot-gpt-5.6-luna.toml --dry-run
uv run --package bird-zero-shot --env-file .env vf-eval @ configs/bird-zero-shot-gpt-5.6-luna.toml -n 3 --no-push
uv run --package bird-zero-shot --env-file .env vf-eval @ configs/bird-zero-shot-gpt-5.6-luna.toml --no-push
```

Override its model with `--model <model>`.

### Docker (recommended)

Build the evaluator once, then run the API-model evaluation with `OPENAI_API_KEY` in `.env`:

```bash
docker build -f Dockerfile.evaluator -t evaluator .

mkdir -p outputs
docker run --rm --env-file .env \
  -v "$PWD/data:/app/data:z" \
  -v "$PWD/outputs:/app/outputs:z" \
  evaluator uv run --frozen --package bird-zero-shot \
  vf-eval @ configs/bird-zero-shot-gpt-5.6-luna.toml --no-push
```

See [`docs/docker.md`](../../docs/docker.md) for setup, API-model runs, mounts, and upload instructions.

## Scoring

`execution_accuracy` is the only task score. It executes the predicted and gold queries once on the supplied SQLite database and compares their result rows as Python sets. Row order and duplicate counts are ignored.

## Configuration

- `env.taskset.split`: only `dev` is supported.
- `env.taskset.data_dir`: extracted BIRD data directory; defaults to `data/bird/dev_20251106`.
