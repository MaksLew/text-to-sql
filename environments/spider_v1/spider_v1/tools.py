import sqlite3
import time
from pathlib import Path

import verifiers.v1 as vf


class Toolset(vf.Toolset[vf.ToolsetConfig]):
    TOOL_PREFIX = "database"

    async def setup_task(self, task) -> None:
        self.db_path = task.db_path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            Path(self.db_path).resolve().as_uri() + "?mode=ro", uri=True
        )
        connection.text_factory = lambda value: value.decode(errors="ignore")
        connection.execute("PRAGMA query_only = ON")
        deadline = time.monotonic() + 5
        connection.set_progress_handler(
            lambda: int(time.monotonic() > deadline), 10_000
        )
        return connection

    @vf.tool
    def list_tables(self) -> list[str]:
        """List the database's tables."""
        with self.connect() as connection:
            return [
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_schema "
                    "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
            ]

    @vf.tool
    def describe_table(self, table: str) -> str:
        """Return the CREATE TABLE statement for a table."""
        with self.connect() as connection:
            row = connection.execute(
                "SELECT sql FROM sqlite_schema WHERE type = 'table' AND name = ?",
                (table,),
            ).fetchone()
        return row[0] if row else f"error: unknown table {table!r}"

    @vf.tool
    def query(self, sql: str) -> dict:
        """Execute a read-only SQLite SELECT and return at most 100 rows."""
        if not sql.lstrip().lower().startswith(("select", "with")):
            return {"error": "only SELECT and WITH queries are allowed"}
        try:
            with self.connect() as connection:
                cursor = connection.execute(sql)
                rows = cursor.fetchmany(101)
                return {
                    "columns": [column[0] for column in cursor.description or []],
                    "rows": rows[:100],
                    "truncated": len(rows) > 100,
                }
        except sqlite3.Error as error:
            return {"error": str(error)}


if __name__ == "__main__":
    Toolset.run()
