#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

benchmark=${1:-spider}
if [[ "$benchmark" != spider && "$benchmark" != bird && "$benchmark" != all ]]; then
  echo "Usage: $0 [spider|bird|all]" >&2
  exit 2
fi

if ! command -v uv >/dev/null; then
  echo "uv is required: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

uv sync
uv run python scripts/apply_verifiers_uv_patch.py
[[ -e .env ]] || cp .env.example .env

[[ "$benchmark" == bird ]] || scripts/download_spider.sh
[[ "$benchmark" == spider ]] || scripts/download_bird.sh

echo "Setup complete."
