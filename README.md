# Text-to-SQL evaluation

This repository evaluates text-to-SQL models with [Verifiers](https://github.com/PrimeIntellect-ai/verifiers). Models inspect SQLite databases through read-only tools or receive schemas directly, and return a query whose result is compared with the benchmark's gold query.

## Environments

- [Spider 1.0](environments/spider_v1/README.md)
- [BIRD](environments/bird_v1/README.md)
- [BIRD-zero-shot](environments/bird_zero_shot/README.md) (one turn, schema in prompt, no tools)

Each environment README documents its dataset, tools, configuration and scoring behavior.

## Setup

You need Python 3.11–3.13 and [uv](https://docs.astral.sh/uv/getting-started/installation/). The download scripts also use standard command-line tools such as `curl`, `unzip`, and `sha256sum`.

```bash
cp -n .env.example .env
uv sync --frozen
./scripts/download_bird.sh
./scripts/download_spider.sh
```

Run only the download script for the benchmark you need. See the environment READMEs for validation commands. Dataset use remains subject to the upstream benchmark terms.

For a reproducible evaluator runtime, build the Docker image instead:

```bash
docker build -f Dockerfile.evaluator -t evaluator .
```

The complete container workflow, including dataset mounts, local inference servers, and result uploads, is documented in [docs/docker.md](docs/docker.md).

## Run an API model

Add your API key to the `.env` created during setup, then use one of the configs documented by the chosen environment:

```bash
# Parse and resolve the config without calling the model
uv run --env-file .env vf-eval @ configs/<config>.toml --dry-run

# Run three examples
uv run --env-file .env vf-eval @ configs/<config>.toml -n 3 --no-push

# Run the full split
uv run --env-file .env vf-eval @ configs/<config>.toml --no-push
```

Or run the same evaluation in the container:

```bash
docker run --rm --env-file .env \
  -v "$PWD/data:/app/data:z" -v "$PWD/outputs:/app/outputs:z" \
  evaluator vf-eval @ configs/<config>.toml --no-push
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

Run the evaluator against that service:

```bash
docker compose -f compose.llama-cpp.yaml run --rm evaluator \
  vf-eval @ configs/bird-qwen3.5-4b.toml --no-push
```

Use the corresponding local config listed in the chosen environment's README. For the GPU-backed vLLM workflow, see [docs/docker.md](docs/docker.md#vllm).

## Results

Local runs are written under `outputs/`; locate their episode files with:

```bash
find outputs -name traces.jsonl -print
```

Each `traces.jsonl` line is one episode. Inspect a selected episode with a one-off standard-library script rather than relying on a repository-specific result helper:

```bash
RUN=outputs/<run-directory>
uv run python - "$RUN/traces.jsonl" 0 <<'PY'
import json, pprint, sys

path, index = sys.argv[1], int(sys.argv[2])
with open(path) as lines:
    episode = next(row for i, row in enumerate(lines) if i == index)
pprint.pp(json.loads(episode))
PY
```

For a pushed run, use Prime CLI JSON output and page through all samples when the total exceeds the requested page size:

```bash
prime --plain eval list --output json -n 20
prime --plain eval get "$ID" --output json
prime --plain eval samples "$ID" --output json -n 100 -p 1
```

Use `jq` or a short one-off Python script to project only the rewards, errors, SQL, or calls needed for the question instead of dumping every full trace.
