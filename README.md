# Spider schema-to-SQL evaluation

A native `verifiers.v1` taskset for zero-shot schema-to-SQL evaluation on the Spider 1.0 development split.

The model receives the question and schema as `CREATE TABLE` statements. It has no database access and must return one SQLite query. The reward executes the prediction read-only and compares its result with the gold query on the original Spider database.

## Setup

```bash
uv sync
./scripts/download_spider.sh
uv run python tests/test_exact_set_match.py
uv run validate spider-v1 --runtime.type subprocess
```

The download script retrieves the official Spider release and keeps only the 20 databases used by the development split. Dataset files are ignored by Git and remain under `data/spider_data/`. Spider is distributed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

### Verifiers UV bootstrap regression

The pinned Verifiers revision unconditionally upgrades UV whenever it prepares a runtime script. With the local `subprocess` runtime this can repeatedly reinstall UV until harness setup times out. If setup stalls or reports `HarnessError: harness setup timed out`, apply the included workaround after `uv sync`:

```bash
uv run python scripts/apply_verifiers_uv_patch.py
```

The patch first reuses an installed UV that supports `uv sync --script`. It modifies the ignored `.venv`, so a clean environment or dependency reinstall may require applying it again. Remove this workaround after updating to a Verifiers revision containing the upstream fix.

## Evaluate an API model

```bash
cp .env.example .env
# Put your real OPENAI_API_KEY in .env

# Check config without making model calls
uv run --env-file .env eval @ configs/spider-openai.toml --dry-run

# Smoke test
uv run --env-file .env eval @ configs/spider-openai.toml -n 3 --no-push

# Full 1,034-example dev split
uv run --env-file .env eval @ configs/spider-openai.toml --no-push
```

Switch OpenAI models without changing the task:

```bash
uv run eval @ configs/spider-openai.toml --model gpt-5.6-luna -n 3 --no-push
```

For another OpenAI-compatible API, override `model`, `client.base-url`, and `client.api-key-var` or copy the small TOML file.

Results are written under `outputs/` with the resolved config, traces, rewards, extracted SQL, and SQL errors. Print only a trace's conversation with:

```bash
scripts/show_trace.py outputs/<run>/traces.jsonl       # first trace
scripts/show_trace.py outputs/<run>/traces.jsonl 4     # fifth trace
```


## Metrics

- `execution_accuracy` (reward): result equivalence on the original Spider database.
- `exact_set_match` (metric): Spider's structural Exact Set Match, using the pinned official evaluator downloaded by `scripts/download_spider.sh`.

Exact Set Match is not raw string equality. The official Spider leaderboard metric is Test Suite Accuracy, which is not yet calculated here.
