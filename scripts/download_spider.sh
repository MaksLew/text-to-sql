#!/usr/bin/env bash
set -euo pipefail

archive=data/spider_data.zip
root=data/spider_data
id=1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J
sha=00636695dabed6b5f4b8328a16b13e069a2f16591d5efcce57660669c85b121b
evaluator_archive=data/test-suite-sql-eval.tar.gz
evaluator_root=data/test-suite-sql-eval
evaluator_rev=e97acc546ecbee8fa27fa8dbf025ef61493a876c
evaluator_sha=d0813c5ca00120c7b94c316656d207afc877abfe522e57d1d84c592b912c42c2

mkdir -p data
if [[ ! -f "$archive" ]]; then
  uvx --from gdown gdown "https://drive.google.com/uc?id=$id" -O "$archive"
fi
echo "$sha  $archive" | sha256sum --check

rm -rf "$root"
unzip -q "$archive" spider_data/dev.json spider_data/tables.json -d data
while read -r db_id; do
  unzip -q "$archive" "spider_data/database/$db_id/*" -d data
done < <(uv run python - <<'PY'
import json
from pathlib import Path
rows = json.loads(Path("data/spider_data/dev.json").read_text())
print(*sorted({row["db_id"] for row in rows}), sep="\n")
PY
)

if [[ ! -f "$evaluator_archive" ]]; then
  curl -L --fail --silent --show-error \
    "https://github.com/taoyds/test-suite-sql-eval/archive/$evaluator_rev.tar.gz" \
    -o "$evaluator_archive"
fi
echo "$evaluator_sha  $evaluator_archive" | sha256sum --check
rm -rf "$evaluator_root"
mkdir -p "$evaluator_root"
tar -xzf "$evaluator_archive" --strip-components=1 -C "$evaluator_root"
# SQL is already one logical line; avoid NLTK's external punkt data dependency.
sed -i 's/word_tokenize(string)/word_tokenize(string, preserve_line=True)/' \
  "$evaluator_root/process_sql.py"

echo "Spider dev data ready at $root"
echo "Spider evaluator ready at $evaluator_root"
