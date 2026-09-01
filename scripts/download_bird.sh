#!/usr/bin/env bash
set -euo pipefail

archive=data/bird-dev.zip
root=data/bird/dev_20240627
url=https://huggingface.co/datasets/HAL-9001/bird-dev/resolve/main/dev.zip
sha=cdd6d19faeb45a23970b98d3ef6c40a87987c95459c2cf12076897a60cf5a630

mkdir -p data
until [[ -f "$archive" ]] && echo "$sha  $archive" | sha256sum --check --status; do
  curl --http1.1 -L --fail --retry 5 --retry-all-errors -C - "$url" -o "$archive"
done

rm -rf data/bird
mkdir -p data/bird
unzip -q "$archive" -d data/bird
unzip -q "$root/dev_databases.zip" -d "$root"

echo "BIRD dev data ready at $root"
