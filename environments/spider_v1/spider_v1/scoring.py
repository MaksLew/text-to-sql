import importlib
import re
import sqlite3
import sys
import time
from collections import Counter
from functools import cache
from itertools import product
from pathlib import Path

_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_ORDER_BY = re.compile(r"\border\s+by\b", re.IGNORECASE)


def extract_sql(reply: str) -> str:
    """Accept raw SQL or the first fenced SQL block."""
    match = _FENCE.search(reply)
    return (match.group(1) if match else reply).strip().removesuffix(";").strip()


def _execute(db_path: str, query: str, timeout: float = 5.0) -> list[tuple]:
    deadline = time.monotonic() + timeout
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=1) as connection:
        connection.text_factory = lambda value: value.decode(errors="ignore")
        connection.execute("PRAGMA query_only = ON")
        connection.set_progress_handler(
            lambda: int(time.monotonic() > deadline), 10_000
        )
        return connection.execute(query).fetchall()


def _results_equal(gold: list[tuple], predicted: list[tuple], ordered: bool) -> bool:
    """Spider-style bag equality, allowing an equivalent column permutation."""
    if not gold or not predicted:
        return gold == predicted
    if len(gold) != len(predicted) or len(gold[0]) != len(predicted[0]):
        return False

    columns = len(gold[0])
    candidates = [
        [j for j in range(columns) if {row[i] for row in gold} == {row[j] for row in predicted}]
        for i in range(columns)
    ]
    for permutation in product(*candidates):
        if len(set(permutation)) != columns:
            continue
        permuted = [tuple(row[j] for j in permutation) for row in predicted]
        if gold == permuted if ordered else Counter(gold) == Counter(permuted):
            return True
    return False


@cache
def _load_spider_evaluator(evaluator_dir: str):
    root = Path(evaluator_dir).resolve()
    if not (root / "evaluation.py").is_file():
        raise FileNotFoundError(
            f"Spider evaluator not found at {root}; run scripts/download_spider.sh"
        )

    # The official evaluator uses absolute imports, so reject conflicting modules
    # rather than silently loading code from another evaluator directory.
    for name in ("evaluation", "process_sql", "exec_eval", "parse"):
        module = sys.modules.get(name)
        expected = (root / f"{name}.py").resolve()
        loaded = getattr(module, "__file__", None) if module else None
        if module and (not loaded or Path(loaded).resolve() != expected):
            source = Path(loaded).resolve() if loaded else "an unknown location"
            raise RuntimeError(
                f"cannot load Spider evaluator from {root}: {name!r} is already "
                f"loaded from {source}"
            )

    sys.path.insert(0, str(root))
    try:
        return importlib.import_module("evaluation")
    finally:
        sys.path.remove(str(root))


@cache
def _foreign_key_maps(evaluator_dir: str, tables_path: str) -> dict:
    return _load_spider_evaluator(evaluator_dir).build_foreign_key_map_from_json(
        tables_path
    )


def exact_set_match(
    evaluator_dir: str,
    tables_path: str,
    db_id: str,
    db_path: str,
    gold_sql: str,
    predicted_sql: str,
) -> tuple[bool, str | None]:
    """Spider's structural exact-set-match metric (values and DISTINCT ignored)."""
    if not predicted_sql:
        return False, "empty prediction"
    evaluator = _load_spider_evaluator(evaluator_dir)
    try:
        schema = evaluator.Schema(evaluator.get_schema(db_path))
        gold = evaluator.get_sql(schema, gold_sql)
        predicted = evaluator.get_sql(schema, predicted_sql)
        key_map = _foreign_key_maps(evaluator_dir, tables_path)[db_id]
        gold_columns = evaluator.build_valid_col_units(
            gold["from"]["table_units"], schema
        )
        predicted_columns = evaluator.build_valid_col_units(
            predicted["from"]["table_units"], schema
        )
        gold = evaluator.rebuild_sql_col(
            gold_columns, evaluator.rebuild_sql_val(gold), key_map
        )
        predicted = evaluator.rebuild_sql_col(
            predicted_columns, evaluator.rebuild_sql_val(predicted), key_map
        )
        return bool(evaluator.Evaluator().eval_exact_match(predicted, gold)), None
    except Exception as error:
        return False, str(error)


def execution_match(db_path: str, gold_sql: str, predicted_sql: str) -> tuple[bool, str | None]:
    if not predicted_sql:
        return False, "empty prediction"
    try:
        gold = _execute(db_path, gold_sql)
    except sqlite3.Error as error:
        raise RuntimeError(f"gold SQL failed for {db_path}: {error}") from error
    try:
        predicted = _execute(db_path, predicted_sql)
    except sqlite3.Error as error:
        return False, str(error)
    return _results_equal(gold, predicted, bool(_ORDER_BY.search(gold_sql))), None
