import asyncio
import json
from pathlib import Path
from typing import Literal

import verifiers.v1 as vf

from spider_v1.tools import Toolset
from spider_v1.scoring import execution_match, extract_sql

SYSTEM_PROMPT = "You translate questions into SQLite queries. Return only the SQL query."
AGENTIC_PROMPT = "Inspect the database with the available tools, then answer with only SQL."


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
            prompt = f"{AGENTIC_PROMPT}\n\nQuestion: {row['question']}"
            tasks.append(
                Task(
                    TaskData(
                        idx=idx,
                        name=f"{self.config.split}-{idx}",
                        prompt=prompt,
                        system_prompt=SYSTEM_PROMPT,
                        split=self.config.split,
                        db_id=db_id,
                        db_path=str(db_path),
                        gold_sql=row["query"],
                    ),
                    self.config.task,
                )
            )
        return tasks
