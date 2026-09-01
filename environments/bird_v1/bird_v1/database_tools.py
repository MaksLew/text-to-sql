import sqlite3
import time
from pathlib import Path

import verifiers.v1 as vf


class DatabaseToolset(vf.Toolset[vf.ToolsetConfig]):
    TOOL_PREFIX = "database"

    async def setup_task(self, task) -> None:
        self.db_path = task.db_path

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
        """Return a table's CREATE statement and up to three sample rows."""
        with self.connect() as connection:
            row = connection.execute(
                "SELECT sql FROM sqlite_schema WHERE type = 'table' AND name = ?",
                (table,),
            ).fetchone()
            if not row:
                return f"error: unknown table {table!r}"
            quoted = '"' + table.replace('"', '""') + '"'
            samples = connection.execute(f"SELECT * FROM {quoted} LIMIT 3").fetchall()
            return f"{row[0]}\nSample rows: {samples}"

    @vf.tool
    def query(self, sql: str) -> dict:
        """Execute a read-only SQLite query and return at most 100 rows."""
        if not sql.lstrip().lower().startswith(("select", "with", "explain")):
            return {"error": "only SELECT, WITH, and EXPLAIN queries are allowed"}
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
    DatabaseToolset.run()
