import asyncio
import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Literal, cast

import verifiers.v1 as vf

from bird_sql_trail.tools import BirdSqlTrailToolset, ToolConfig

SYSTEM_PROMPT = """Translate the user's question into one correct, read-only SQLite query.
The complete database schema is provided. Use database.query to inspect or test data
when useful. Return only the final SQL query, without Markdown or explanation."""
_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_SQL_TOKEN = re.compile(
    r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|[A-Za-z_][\w$]*|\d+(?:\.\d+)?|<>|!=|<=|>=|[-+*/%=<>().,;]"
)


class BirdSqlTrailData(vf.TaskData):
    question_id: int
    db_id: str
    db_path: str
    gold_sql: str
    schema_items: list[str]


class BirdSqlTrailTaskConfig(vf.TaskConfig):
    tools: ToolConfig = ToolConfig()


class BirdSqlTrailTask(vf.Task[BirdSqlTrailData, vf.State, BirdSqlTrailTaskConfig]):
    @classmethod
    def toolsets(cls, config: BirdSqlTrailTaskConfig) -> list[vf.Toolset]:
        return [BirdSqlTrailToolset(config.tools)]

    @property
    def key(self) -> str:
        return f"bird:{self.data.question_id}"

    async def _scores(self, trace: vf.Trace) -> dict[str, float]:
        if scores := trace.info.get("sql_trail_scores"):
            return scores

        predicted = _extract_sql(trace.last_reply or "")
        correct, error = await asyncio.to_thread(
            _execution_match, self.data.db_path, self.data.gold_sql, predicted
        )
        query_calls = _query_calls(trace)
        budget = cast(BirdSqlTrailTaskConfig, self.config).tools.max_queries
        scores = {
            "execution_correctness": float(correct),
            "query_efficiency": float(correct)
            * max(0.0, (budget - query_calls) / budget),
            "schema_grounding": _jaccard(
                _schema_links(predicted, self.data.schema_items),
                _schema_links(self.data.gold_sql, self.data.schema_items),
            ),
            "sql_bigram_similarity": _jaccard(
                _bigrams(predicted), _bigrams(self.data.gold_sql)
            ),
            "syntax_validity": float(error is None),
        }
        trace.info.update(predicted_sql=predicted, sql_trail_scores=scores)
        if error:
            trace.info["sql_error"] = error
        return scores

    @vf.reward(weight=5.0)
    async def execution_correctness(self, trace: vf.Trace) -> float:
        return (await self._scores(trace))["execution_correctness"]

    @vf.reward(weight=2.0)
    async def query_efficiency(self, trace: vf.Trace) -> float:
        return (await self._scores(trace))["query_efficiency"]

    @vf.reward(weight=1.0)
    async def schema_grounding(self, trace: vf.Trace) -> float:
        return (await self._scores(trace))["schema_grounding"]

    @vf.reward(weight=1.0)
    async def sql_bigram_similarity(self, trace: vf.Trace) -> float:
        return (await self._scores(trace))["sql_bigram_similarity"]

    @vf.reward(weight=1.0)
    async def syntax_validity(self, trace: vf.Trace) -> float:
        return (await self._scores(trace))["syntax_validity"]

    @vf.metric
    async def query_calls(self, trace: vf.Trace) -> float:
        return float(_query_calls(trace))

    @vf.metric
    async def repeated_query_calls(self, trace: vf.Trace) -> float:
        queries = _queries(trace)
        return float(len(queries) - len(set(queries)))

    async def validate(self, runtime: vf.Runtime) -> bool:
        correct, _ = await asyncio.to_thread(
            _execution_match,
            self.data.db_path,
            self.data.gold_sql,
            self.data.gold_sql,
        )
        return correct


class BirdSqlTrailConfig(vf.TasksetConfig):
    split: Literal["dev"] = "dev"
    data_dir: Path = Path("data/bird/dev_20251106")
    task: BirdSqlTrailTaskConfig = BirdSqlTrailTaskConfig()


class BirdSqlTrailTaskset(vf.Taskset[BirdSqlTrailTask, BirdSqlTrailConfig]):  # ty: ignore[invalid-type-arguments]
    def load(self) -> list[BirdSqlTrailTask]:
        root = self.config.data_dir.resolve()
        rows_path = root / f"{self.config.split}.json"
        databases = root / f"{self.config.split}_databases"
        if not rows_path.is_file() or not databases.is_dir():
            raise FileNotFoundError(
                f"Data not found at {root}; run scripts/download_bird.sh"
            )

        schemas: dict[str, tuple[str, list[str]]] = {}
        tasks = []
        for idx, row in enumerate(json.loads(rows_path.read_text())):
            db_id = row["db_id"]
            db_path = databases / db_id / f"{db_id}.sqlite"
            if not db_path.is_file():
                raise FileNotFoundError(db_path)
            if db_id not in schemas:
                schemas[db_id] = _schema(db_path)
            schema, schema_items = schemas[db_id]
            question_id = row["question_id"]
            tasks.append(
                BirdSqlTrailTask(
                    BirdSqlTrailData(
                        idx=idx,
                        id=str(question_id),
                        name=f"dev-{question_id}",
                        system_prompt=SYSTEM_PROMPT,
                        prompt=f"Database schema:\n{schema}\n\nQuestion: {row['question']}",
                        question_id=question_id,
                        db_id=db_id,
                        db_path=str(db_path),
                        gold_sql=row["SQL"],
                        schema_items=schema_items,
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


def _schema(db_path: Path) -> tuple[str, list[str]]:
    with sqlite3.connect(
        db_path.resolve().as_uri() + "?mode=ro", uri=True
    ) as connection:
        tables = connection.execute(
            "SELECT name, sql FROM sqlite_schema "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' AND sql IS NOT NULL "
            "ORDER BY name"
        ).fetchall()
        statements = "\n\n".join(sql.rstrip().rstrip(";") + ";" for _, sql in tables)
        items = [name for name, _ in tables]
        for table, _ in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            items.extend(
                row[1] for row in connection.execute(f"PRAGMA table_info({quoted})")
            )
    return statements, sorted(set(items), key=str.casefold)


def _query_calls(trace: vf.Trace) -> int:
    return sum(len(message.tool_calls or []) for message in trace.assistant_messages)


def _queries(trace: vf.Trace) -> list[str]:
    queries = []
    for message in trace.assistant_messages:
        for call in message.tool_calls or []:
            try:
                queries.append(
                    json.loads(call.arguments).get("sql", "").strip().casefold()
                )
            except (json.JSONDecodeError, AttributeError):
                queries.append(call.arguments.strip().casefold())
    return queries


def _schema_links(sql: str, schema_items: list[str]) -> set[str]:
    # ponytail: lexical matching is intentionally approximate; use an SQL parser if
    # schema-reward quality becomes a measured bottleneck.
    return {
        item.casefold()
        for item in schema_items
        if re.search(rf"(?<!\w){re.escape(item)}(?!\w)", sql, re.IGNORECASE)
    }


def _bigrams(sql: str) -> set[tuple[str, str]]:
    tokens = [token.casefold() for token in _SQL_TOKEN.findall(sql)]
    return set(zip(tokens, tokens[1:]))


def _jaccard(left: set, right: set) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0
