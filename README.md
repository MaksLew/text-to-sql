# Text-to-SQL evaluation

This repository evaluates text-to-SQL models with [Verifiers](https://github.com/PrimeIntellect-ai/verifiers). Models inspect SQLite databases through read-only tools and return a query whose result is compared with the benchmark's gold query.

## Environments

- [Spider 1.0](environments/spider_v1/README.md)
- [BIRD](environments/bird_v1/README.md)

Each environment README documents its dataset, tools, configuration and scoring behavior.

## Setup

You need Python 3.11–3.13 and [uv](https://docs.astral.sh/uv/getting-started/installation/). The download scripts also use standard command-line tools such as `curl`, `unzip`, and `tar`.

```bash
./scripts/setup.sh all
```

See the environment READMEs for benchmark-specific setup and validation commands. Dataset use remains subject to the upstream benchmark terms.

### Pinned Verifiers workaround

This project pins Verifiers at commit `c51c094a4018471b7fdc873eb5cb55bbd5e956e1`. That revision can repeatedly reinstall uv while preparing a subprocess runtime, eventually causing setup to time out. `scripts/setup.sh` patches the local `.venv` after `uv sync` to avoid the reinstall.

If you run `uv sync` yourself, apply the patch again:

```bash
uv run python scripts/apply_verifiers_uv_patch.py
```

The patch only changes the ignored virtual environment. It can be removed when the pinned Verifiers revision includes the upstream fix.

## Run an API model

Add your API key to the `.env` created during setup, then use one of the configs documented by the chosen environment:

```bash
# Parse and resolve the config without calling the model
uv run --env-file .env eval @ configs/<config>.toml --dry-run

# Run three examples
uv run --env-file .env eval @ configs/<config>.toml -n 3 --no-push

# Run the full split
uv run --env-file .env eval @ configs/<config>.toml --no-push
```

The checked-in API configs use OpenAI's API. To use another OpenAI-compatible endpoint, copy a config and change `model`, `client.base_url`, and `client.api_key_var`. You can also override the model with `--model <model>`.

## Run a local model with llama.cpp

The local configs expect an OpenAI-compatible llama.cpp server at `http://localhost:8080/v1`. Put a compatible GGUF file in `models/`; the default filename is set in `.env` as `Qwen3.5-4B-M-TS-Q4_K_M.gguf`.

```bash
mkdir -p models
# Copy or download the GGUF to models/$MODEL_FILE first.

docker compose -f compose.llama-cpp.yaml up -d
curl http://localhost:8080/health
```

The Compose service enables model reasoning, serves one request at a time, and defaults to 8 CPU threads and a 16,384-token context. Override those settings when starting the server:

```bash
THREADS=12 CONTEXT_SIZE=16384 MODEL_FILE=other.gguf \
  docker compose -f compose.llama-cpp.yaml up -d
```

Use the local config listed in the chosen environment's README.

## Results

Evaluation runs are initially written as flat directories under `outputs/`. Clean the directory by categorizing completed eval runs by environment and model and removing validation runs:

```bash
scripts/clean_outputs.py --dry-run
scripts/clean_outputs.py
```

This produces `outputs/<environment>/<model>/<run-id>/`. Other directories are left untouched. Each run includes the resolved config, traces, and logs. The prediction and any SQLite error are stored in each trace's `info` field.

Summarize a run:

```bash
scripts/summarize_run.py outputs/<environment>/<model>/<run-id>
scripts/summarize_run.py outputs/<environment>/<model>/<run-id> --failures
```

Inspect one trace:

```bash
scripts/show_trace.py outputs/<environment>/<model>/<run-id>/traces.jsonl       # first trace
scripts/show_trace.py outputs/<environment>/<model>/<run-id>/traces.jsonl 4     # fifth trace
```
