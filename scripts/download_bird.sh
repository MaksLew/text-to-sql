#!/usr/bin/env bash
set -euo pipefail

archive=data/bird-dev.zip
annotations=data/bird-dev-20251106.json
root=data/bird/dev_20251106
archive_url=https://huggingface.co/datasets/HAL-9001/bird-dev/resolve/main/dev.zip
annotations_url=https://huggingface.co/datasets/birdsql/bird_sql_dev_20251106/resolve/main/data/dev_20251106-00000-of-00001.json
archive_sha=cdd6d19faeb45a23970b98d3ef6c40a87987c95459c2cf12076897a60cf5a630
annotations_sha=ffd8018378ddb1a8794753e0a31cfc81862ff7318a5184c22f3dc4ce03a03feb

mkdir -p data
until [[ -f "$archive" ]] && echo "$archive_sha  $archive" | sha256sum --check --status; do
  curl --http1.1 -L --fail --retry 5 --retry-all-errors -C - "$archive_url" -o "$archive"
done
until [[ -f "$annotations" ]] && echo "$annotations_sha  $annotations" | sha256sum --check --status; do
  curl --http1.1 -L --fail --retry 5 --retry-all-errors "$annotations_url" -o "$annotations"
done

rm -rf data/bird
mkdir -p "$root"
unzip -q "$archive" dev_20240627/dev_databases.zip -d data/bird
unzip -q data/bird/dev_20240627/dev_databases.zip -d "$root"
cp "$annotations" "$root/dev.json"
rm -rf data/bird/dev_20240627

echo "BIRD dev data ready at $root"
