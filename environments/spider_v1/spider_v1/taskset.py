import asyncio
import json
import re
import sqlite3
import time
from collections import Counter
from itertools import product
from pathlib import Path
from typing import Literal

import verifiers.v1 as vf

from spider_v1.tools import Toolset

PROMPT = (
    "You translate questions into SQLite queries. "
    "Inspect the database with the available tools, then return only the SQL query."
)
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


class TaskData(vf.TaskData):
    split: str
    db_id: str
    db_path: str
    gold_sql: str


class TaskConfig(vf.TaskConfig):
    tools: vf.ToolsetConfig = vf.ToolsetConfig()


class Task(vf.Task[TaskData, vf.State, TaskConfig]):
    @classmethod
    def toolsets(cls, config: TaskConfig) -> list[vf.Toolset]:
        return [Toolset(config.tools)]

    @property
    def key(self) -> str:
        return f"{self.data.split}:{self.data.idx}"

    @vf.reward(weight=1.0)
    async def execution_accuracy(self, trace: vf.Trace) -> float:
        predicted_sql = extract_sql(trace.last_reply or "")
        correct, error = await asyncio.to_thread(
            execution_match, self.data.db_path, self.data.gold_sql, predicted_sql
        )
        trace.info["predicted_sql"] = predicted_sql
        if error:
            trace.info["sql_error"] = error
        return float(correct)

    async def validate(self, runtime: vf.Runtime) -> bool:
        correct, _ = await asyncio.to_thread(
            execution_match, self.data.db_path, self.data.gold_sql, self.data.gold_sql
        )
        return correct


class TasksetConfig(vf.TasksetConfig):
    split: Literal["dev"] = "dev"
    data_dir: Path = Path("data/spider_data")
    task: TaskConfig = TaskConfig()


class Taskset(vf.Taskset[Task, TasksetConfig]):  # ty: ignore[invalid-type-arguments]
    def load(self) -> list[Task]:
        root = self.config.data_dir.resolve()
        rows_path = root / f"{self.config.split}.json"
        if not rows_path.is_file():
            raise FileNotFoundError(
                f"Spider data not found at {root}; run scripts/download_spider.sh"
            )

        rows = json.loads(rows_path.read_text())
        tasks = []
        for idx, row in enumerate(rows):
            db_id = row["db_id"]
            db_path = root / "database" / db_id / f"{db_id}.sqlite"
            if not db_path.is_file():
                raise FileNotFoundError(db_path)
            prompt = f"{PROMPT}\n\nQuestion: {row['question']}"
            tasks.append(
                Task(
                    TaskData(
                        idx=idx,
                        name=f"{self.config.split}-{idx}",
                        prompt=prompt,
                        split=self.config.split,
                        db_id=db_id,
                        db_path=str(db_path),
                        gold_sql=row["query"],
                    ),
                    self.config.task,
                )
            )
        return tasks
