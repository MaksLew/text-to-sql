import re
import sqlite3
import time
from collections import Counter
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
        [
            j
            for j in range(columns)
            if {row[i] for row in gold} == {row[j] for row in predicted}
        ]
        for i in range(columns)
    ]
    for permutation in product(*candidates):
        if len(set(permutation)) != columns:
            continue
        permuted = [tuple(row[j] for j in permutation) for row in predicted]
        if gold == permuted if ordered else Counter(gold) == Counter(permuted):
            return True
    return False


def execution_match(
    db_path: str, gold_sql: str, predicted_sql: str
) -> tuple[bool, str | None]:
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
