#!/usr/bin/env bash
set -euo pipefail

archive=data/spider_data.zip
root=data/spider_data
id=1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J
sha=00636695dabed6b5f4b8328a16b13e069a2f16591d5efcce57660669c85b121b
mkdir -p data
if [[ ! -f "$archive" ]]; then
  uvx --from gdown gdown "https://drive.google.com/uc?id=$id" -O "$archive"
fi
echo "$sha  $archive" | sha256sum --check

rm -rf "$root"
unzip -q "$archive" spider_data/dev.json -d data
while read -r db_id; do
  unzip -q "$archive" "spider_data/database/$db_id/*" -d data
done < <(uv run python - <<'PY'
import json
from pathlib import Path
rows = json.loads(Path("data/spider_data/dev.json").read_text())
print(*sorted({row["db_id"] for row in rows}), sep="\n")
PY
)

echo "Spider dev data ready at $root"
