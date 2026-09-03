# Text-to-SQL evaluation

This repository evaluates text-to-SQL models with [Verifiers](https://github.com/PrimeIntellect-ai/verifiers). It currently supports:

- **Spider 1.0 dev** (1,034 questions): let the model inspect the database with tools.
- **BIRD dev, 2025-11-06 cleaned release** (1,534 questions): give the model the question and evidence, then let it inspect the database with tools.

In both environments, the model must return one SQLite query. The main reward runs that query against the benchmark database and compares its result with the gold query.

## Setup

You need Python 3.11–3.13 and [uv](https://docs.astral.sh/uv/getting-started/installation/). The download scripts also use standard command-line tools such as `curl`, `unzip`, and `tar`.

```bash
./scripts/setup.sh           # install dependencies and download Spider
./scripts/setup.sh bird      # install dependencies and download BIRD
./scripts/setup.sh all       # download both
```

Dataset use remains subject to the upstream [Spider](https://yale-lily.github.io/spider) and [BIRD](https://bird-bench.github.io/) terms.

Check an environment before running a model:

```bash
uv run validate spider-v1 --runtime.type subprocess
uv run validate bird-v1 --runtime.type subprocess
```

### Pinned Verifiers workaround

This project pins Verifiers at commit `c51c094a4018471b7fdc873eb5cb55bbd5e956e1`. That revision can repeatedly reinstall uv while preparing a subprocess runtime, eventually causing setup to time out. `scripts/setup.sh` patches the local `.venv` after `uv sync` to avoid the reinstall.

If you run `uv sync` yourself, apply the patch again:

```bash
uv run python scripts/apply_verifiers_uv_patch.py
```

The patch only changes the ignored virtual environment. It can be removed when the pinned Verifiers revision includes the upstream fix.

## Run an API model

Add your API key to the `.env` created during setup, then choose a config:

| Config | Benchmark | What the model receives |
| --- | --- | --- |
| `configs/spider-openai.toml` | Spider | question and database tools |
| `configs/bird-agentic-openai.toml` | BIRD | question, evidence, and database tools |

```bash
# Parse and resolve the config without calling the model
uv run --env-file .env eval @ configs/spider-openai.toml --dry-run

# Run three examples
uv run --env-file .env eval @ configs/spider-openai.toml -n 3 --no-push

# Run the full split
uv run --env-file .env eval @ configs/spider-openai.toml --no-push
```

The checked-in API configs use OpenAI's API. To use another OpenAI-compatible endpoint, copy a config and change `model`, `client.base_url`, and `client.api_key_var`.

You can also override the model from the command line:

```bash
uv run --env-file .env eval @ configs/spider-openai.toml \
  --model gpt-5.6-luna -n 3 --no-push
```

## Run Qwen3.5-4B with llama.cpp

The local configs expect an OpenAI-compatible llama.cpp server at `http://localhost:8080/v1`. Put a compatible GGUF file in `models/`; the default filename is set in `.env` as `Qwen3.5-4B-M-TS-Q4_K_M.gguf`.

```bash
mkdir -p models
# Copy or download the GGUF to models/$MODEL_FILE first.

docker compose -f compose.llama-cpp.yaml up -d
curl http://localhost:8080/health

uv run --env-file .env eval @ configs/spider-qwen3.5-4b-llama-cpp.toml --dry-run
uv run --env-file .env eval @ configs/spider-qwen3.5-4b-llama-cpp.toml -n 3 --no-push
```

Available local configs:

- `configs/spider-qwen3.5-4b-llama-cpp.toml`
- `configs/bird-agentic-qwen3.5-4b-llama-cpp.toml`

The Compose service disables model reasoning, serves one request at a time, and defaults to 8 CPU threads and an 8,192-token context. Override those settings when starting the server:

```bash
THREADS=12 CONTEXT_SIZE=16384 MODEL_FILE=other.gguf \
  docker compose -f compose.llama-cpp.yaml up -d
```

## Results

Evaluation runs are written under `outputs/`. Each run includes the resolved config, traces, and logs. The prediction and any SQLite error are stored in each trace's `info` field.

Summarize a run:

```bash
scripts/summarize_run.py outputs/<run>
scripts/summarize_run.py outputs/<run> --failures
```

Inspect one trace:

```bash
scripts/show_trace.py outputs/<run>/traces.jsonl       # first trace
scripts/show_trace.py outputs/<run>/traces.jsonl 4     # fifth trace
```

## Scoring

### Spider

- `execution_accuracy` is the reward. It compares the predicted and gold results on the original database.
- `exact_set_match` is an additional structural metric based on Spider's evaluator. It is not raw SQL string equality.

This repository does **not** calculate Spider Test Suite Accuracy, so its numbers should not be presented as official Spider leaderboard results.

### BIRD

- `execution_accuracy` is the reward. It compares the predicted and gold result rows as sets on the original database.
