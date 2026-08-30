import asyncio
import json
from pathlib import Path
from typing import Literal

import verifiers.v1 as vf

from spider_v1.database_tools import DatabaseToolset
from spider_v1.scoring import exact_set_match, execution_match, extract_sql

SYSTEM_PROMPT = "You translate questions into SQLite queries. Return only the SQL query."
AGENTIC_PROMPT = "Inspect the database with the available tools, then answer with only SQL."


class SpiderData(vf.TaskData):
    split: str
    db_id: str
    db_path: str
    tables_path: str
    evaluator_dir: str
    gold_sql: str


class SpiderTaskConfig(vf.TaskConfig):
    condition: Literal["schema", "agentic"] = "schema"
    tools: vf.ToolsetConfig = vf.ToolsetConfig()


class SpiderTask(vf.Task[SpiderData, vf.State, SpiderTaskConfig]):
    @classmethod
    def toolsets(cls, config: SpiderTaskConfig) -> list[vf.Toolset]:
        return [DatabaseToolset(config.tools)] if config.condition == "agentic" else []

    @property
    def key(self) -> str:
        return f"{self.data.split}:{self.data.idx}"

    @vf.metric
    async def exact_set_match(self, trace: vf.Trace) -> float:
        predicted_sql = extract_sql(trace.last_reply or "")
        correct, error = await asyncio.to_thread(
            exact_set_match,
            self.data.evaluator_dir,
            self.data.tables_path,
            self.data.db_id,
            self.data.db_path,
            self.data.gold_sql,
            predicted_sql,
        )
        if error:
            trace.info["exact_set_match_error"] = error
        return float(correct)

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
        execution_correct, _ = await asyncio.to_thread(
            execution_match, self.data.db_path, self.data.gold_sql, self.data.gold_sql
        )
        exact_correct, _ = await asyncio.to_thread(
            exact_set_match,
            self.data.evaluator_dir,
            self.data.tables_path,
            self.data.db_id,
            self.data.db_path,
            self.data.gold_sql,
            self.data.gold_sql,
        )
        return execution_correct and exact_correct


class SpiderConfig(vf.TasksetConfig):
    split: Literal["dev"] = "dev"
    data_dir: Path = Path("data/spider_data")
    evaluator_dir: Path = Path("data/test-suite-sql-eval")
    task: SpiderTaskConfig = SpiderTaskConfig()


class SpiderTaskset(vf.Taskset[SpiderTask, SpiderConfig]):
    def load(self) -> list[SpiderTask]:
        root = self.config.data_dir.resolve()
        rows_path = root / f"{self.config.split}.json"
        tables_path = root / "tables.json"
        evaluator_dir = self.config.evaluator_dir.resolve()
        if not rows_path.is_file() or not tables_path.is_file():
            raise FileNotFoundError(
                f"Spider data not found at {root}; run scripts/download_spider.sh"
            )
        if not (evaluator_dir / "evaluation.py").is_file():
            raise FileNotFoundError(
                f"Spider evaluator not found at {evaluator_dir}; "
                "run scripts/download_spider.sh"
            )

        rows = json.loads(rows_path.read_text())
        schemas = {
            schema["db_id"]: _schema_sql(schema)
            for schema in json.loads(tables_path.read_text())
        }
        tasks = []
        for idx, row in enumerate(rows):
            db_id = row["db_id"]
            db_path = root / "database" / db_id / f"{db_id}.sqlite"
            if not db_path.is_file():
                raise FileNotFoundError(db_path)
            prompt = (
                f"{AGENTIC_PROMPT}\n\nQuestion: {row['question']}"
                if self.config.task.condition == "agentic"
                else (
                    "Database schema:\n\n"
                    f"{schemas[db_id]}\n\n"
                    f"Question: {row['question']}"
                )
            )
            tasks.append(
                SpiderTask(
                    SpiderData(
                        idx=idx,
                        name=f"{self.config.split}-{idx}",
                        prompt=prompt,
                        system_prompt=SYSTEM_PROMPT,
                        split=self.config.split,
                        db_id=db_id,
                        db_path=str(db_path),
                        tables_path=str(tables_path),
                        evaluator_dir=str(evaluator_dir),
                        gold_sql=row["query"],
                    ),
                    self.config.task,
                )
            )
        return tasks


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _schema_sql(schema: dict) -> str:
    tables = schema["table_names_original"]
    columns = schema["column_names_original"]
    types = schema["column_types"]
    primary_keys = set(schema["primary_keys"])
    foreign_keys = {source: target for source, target in schema["foreign_keys"]}
    statements = []

    for table_idx, table in enumerate(tables):
        definitions = []
        for column_idx, (owner_idx, column) in enumerate(columns):
            if owner_idx != table_idx:
                continue
            definition = f"  {_quote(column)} {types[column_idx].upper()}"
            if column_idx in primary_keys:
                definition += " PRIMARY KEY"
            definitions.append(definition)
        for source, target in foreign_keys.items():
            source_table, source_column = columns[source]
            target_table, target_column = columns[target]
            if source_table == table_idx:
                definitions.append(
                    f"  FOREIGN KEY ({_quote(source_column)}) REFERENCES "
                    f"{_quote(tables[target_table])} ({_quote(target_column)})"
                )
        statements.append(
            f"CREATE TABLE {_quote(table)} (\n" + ",\n".join(definitions) + "\n);"
        )
    return "\n\n".join(statements)
