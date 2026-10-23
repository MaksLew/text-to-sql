import sqlite3
import time
from pathlib import Path

from pydantic import Field
import verifiers.v1 as vf


class ToolConfig(vf.ToolsetConfig):
    max_queries: int = Field(default=10, gt=0)


class BirdSqlTrailToolset(vf.Toolset[ToolConfig]):
    TOOL_PREFIX = "database"

    async def setup_task(self, task) -> None:
        self.db_path = task.db_path
        self.query_count = 0

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            Path(self.db_path).resolve().as_uri() + "?mode=ro", uri=True
        )
        connection.text_factory = lambda value: value.decode(errors="ignore")
        connection.execute("PRAGMA query_only = ON")
        deadline = time.monotonic() + 30
        connection.set_progress_handler(
            lambda: int(time.monotonic() > deadline), 10_000
        )
        return connection

    @vf.tool
    def query(self, sql: str) -> dict:
        """Execute a read-only SQLite query and return at most 50 rows."""
        self.query_count += 1
        if self.query_count > self.config.max_queries:
            return {"error": "query budget exhausted; return your final SQL answer"}
        if not sql.lstrip().lower().startswith(("select", "with", "explain")):
            return {"error": "only SELECT, WITH, and EXPLAIN queries are allowed"}
        try:
            with self.connect() as connection:
                cursor = connection.execute(sql)
                rows = cursor.fetchmany(51)
                return {
                    "columns": [column[0] for column in cursor.description or []],
                    "rows": rows[:50],
                    "truncated": len(rows) > 50,
                }
        except sqlite3.Error as error:
            return {"error": str(error)}


if __name__ == "__main__":
    BirdSqlTrailToolset.run()
