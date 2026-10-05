import asyncio
import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Literal

import verifiers.v1 as vf

from bird_v1.tools import Toolset

SYSTEM_PROMPT = (
    "You translate questions into SQLite queries. Return only the SQL query."
)
PROMPT = "Inspect the database with the available tools, then answer with only SQL."
_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


class TaskData(vf.TaskData):
    split: str
    db_id: str
    db_path: str
    gold_sql: str
    difficulty: str


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
        predicted_sql = _extract_sql(trace.last_reply or "")
        trace.info["predicted_sql"] = predicted_sql
        correct, error = await asyncio.to_thread(
            _execution_match, self.data.db_path, self.data.gold_sql, predicted_sql
        )
        if error:
            trace.info["sql_error"] = error
        return float(correct)

    async def validate(self, runtime: vf.Runtime) -> bool:
        await asyncio.to_thread(_execute, self.data.db_path, self.data.gold_sql)
        return True


class TasksetConfig(vf.TasksetConfig):
    split: Literal["dev"] = "dev"
    data_dir: Path = Path("data/bird/dev_20251106")
    task: TaskConfig = TaskConfig()


class Taskset(vf.Taskset[Task, TasksetConfig]):  # ty: ignore[invalid-type-arguments]
    def load(self) -> list[Task]:
        root = self.config.data_dir.resolve()
        rows_path = root / f"{self.config.split}.json"
        databases = root / f"{self.config.split}_databases"
        if not rows_path.is_file() or not databases.is_dir():
            raise FileNotFoundError(
                f"Data not found at {root}; run scripts/download_bird.sh"
            )

        tasks = []
        for idx, row in enumerate(json.loads(rows_path.read_text())):
            db_id = row["db_id"]
            db_path = databases / db_id / f"{db_id}.sqlite"
            if not db_path.is_file():
                raise FileNotFoundError(db_path)
            evidence = row.get("evidence") or "None provided."
            tasks.append(
                Task(
                    TaskData(
                        idx=idx,
                        name=f"{self.config.split}-{idx}",
                        prompt=(
                            f"{PROMPT}\n\nEvidence: {evidence}\n\n"
                            f"Question: {row['question']}"
                        ),
                        system_prompt=SYSTEM_PROMPT,
                        split=self.config.split,
                        db_id=db_id,
                        db_path=str(db_path),
                        gold_sql=row["SQL"],
                        difficulty=row["difficulty"],
                    ),
                    self.config.task,
                )
            )
        return tasks


def _extract_sql(reply: str) -> str:
    match = _FENCE.search(reply)
    return (match.group(1) if match else reply).strip().removesuffix(";").strip()


def _execute(db_path: str, sql: str) -> list[tuple]:
    if not sql:
        raise sqlite3.OperationalError("empty prediction")
    deadline = time.monotonic() + 30
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.text_factory = lambda value: value.decode(errors="ignore")
        connection.execute("PRAGMA query_only = ON")
        connection.set_progress_handler(
            lambda: int(time.monotonic() > deadline), 10_000
        )
        return connection.execute(sql).fetchall()


def _execution_match(
    db_path: str, gold_sql: str, predicted_sql: str
) -> tuple[bool, str | None]:
    """Official BIRD execution accuracy: set equality of result rows."""
    try:
        gold = _execute(db_path, gold_sql)
    except sqlite3.Error as error:
        raise RuntimeError(f"gold SQL failed for {db_path}: {error}") from error
    try:
        predicted = _execute(db_path, predicted_sql)
    except sqlite3.Error as error:
        return False, str(error)
    return set(gold) == set(predicted), None
