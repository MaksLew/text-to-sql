# Running evaluations with Docker

The evaluator image contains Python 3.12, the locked `uv` environment, both benchmark packages, and the evaluation CLI. Datasets, model weights, secrets, and outputs stay outside the image.

## Prepare the evaluator

```bash
cp -n .env.example .env
mkdir -p data models outputs
docker build -f Dockerfile.evaluator -t evaluator .
```

Add the required API keys to `.env`. `PRIME_API_KEY` is only needed when uploading a run with `--push`; checked-in configs keep `push = false`.

Download the benchmark data on the host with `./scripts/setup.sh all`, or through the evaluator image:

```bash
docker run --rm \
  -v "$PWD/data:/app/data:z" \
  evaluator ./scripts/setup.sh all
```

## API model

No inference container is needed:

```bash
docker run --rm \
  --env-file .env \
  -v "$PWD/data:/app/data:z" \
  -v "$PWD/outputs:/app/outputs:z" \
  evaluator vf-eval @ configs/bird-gpt-5.6-luna.toml --no-push
```

Replace the config path for Spider or another API model.

## llama.cpp

Put the GGUF named by `MODEL_FILE` in `models/`, then start the server:

```bash
docker compose -f compose.llama-cpp.yaml up -d llama-cpp
curl http://localhost:8080/health
```

Run an evaluation in the evaluator container:

```bash
docker compose -f compose.llama-cpp.yaml run --rm evaluator \
  vf-eval @ configs/bird-qwen3.5-4b.toml --no-push
```

The evaluator shares the llama.cpp network namespace, so the existing `localhost:8080` config works unchanged.

## vLLM

This stack requires an NVIDIA GPU and NVIDIA Container Toolkit. It expects an existing Hugging Face cache at `/workspace/hf`; override the host location with `HF_HOME` when needed.

```bash
HF_HOME=/workspace/hf docker compose -f compose.vllm.yaml up -d vllm
curl http://localhost:8000/v1/models

docker compose -f compose.vllm.yaml run --rm evaluator \
  vf-eval @ configs/bird-qwen3.5-4b-vllm.toml --no-push
```

The host cache is mounted into vLLM at `/workspace/hf`. `VLLM_USE_FLASHINFER_SAMPLER=0` is set by the Compose file.

## Uploading results

Set `PRIME_API_KEY` in `.env` and explicitly override the checked-in `push = false` setting:

```bash
docker compose -f compose.llama-cpp.yaml run --rm evaluator \
  vf-eval @ configs/bird-qwen3.5-4b.toml --push
```

## Stop a backend

```bash
docker compose -f compose.llama-cpp.yaml down
docker compose -f compose.vllm.yaml down
```
