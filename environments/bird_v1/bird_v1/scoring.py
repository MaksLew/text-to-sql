import sqlite3
from functools import cache

import sqlglot
from sqlglot import exp
from sqlglot.optimizer.canonicalize import canonicalize
from sqlglot.optimizer.normalize import normalize
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope


def structural_exact_match(
    db_path: str, gold_sql: str, predicted_sql: str
) -> tuple[bool, str | None]:
    """Compare normalized SQLite ASTs, ignoring values and DISTINCT."""
    if not predicted_sql:
        return False, "empty prediction"
    try:
        return _normalize(db_path, predicted_sql) == _normalize(db_path, gold_sql), None
    except Exception as error:
        return False, str(error)


def _normalize(db_path: str, sql: str) -> exp.Expression:
    expression = qualify(
        sqlglot.parse_one(sql, read="sqlite"),
        dialect="sqlite",
        schema=_schema(db_path),
        validate_qualify_columns=False,
        quote_identifiers=False,
        identify=False,
        canonicalize_table_aliases=True,
        expand_stars=False,
    )

    foreign_keys = _foreign_keys(db_path)
    for scope in traverse_scope(expression):
        for column in scope.columns:
            source = scope.sources.get(column.table)
            if isinstance(source, exp.Table):
                table, name = foreign_keys.get(
                    (source.name.lower(), column.name.lower()),
                    (source.name.lower(), column.name.lower()),
                )
                column.set("table", exp.to_identifier(table))
                column.set("this", exp.to_identifier(name))

    tables = list(expression.find_all(exp.Table))
    for index, cte in enumerate(expression.find_all(exp.CTE)):
        old_name = cte.alias
        new_name = f"_cte_{index}"
        cte.set("alias", exp.TableAlias(this=exp.to_identifier(new_name)))
        for table in tables:
            if table.name == old_name:
                table.set("this", exp.to_identifier(new_name))

    for table in tables:
        table.set("alias", None)
    for alias in list(expression.find_all(exp.Alias)):
        alias.replace(alias.this)
    for select in expression.find_all(exp.Select):
        select.set("distinct", None)
    for distinct in list(expression.find_all(exp.Distinct)):
        if distinct.parent and not isinstance(distinct.parent, exp.Select):
            replacement = (
                distinct.expressions[0]
                if len(distinct.expressions) == 1
                else exp.Tuple(expressions=distinct.expressions)
            )
            distinct.replace(replacement)
    for literal in list(expression.find_all(exp.Literal)):
        literal.replace(exp.Literal.string("__value__"))
    for identifier in expression.find_all(exp.Identifier):
        identifier.set("this", identifier.this.lower())
        identifier.set("quoted", False)

    expression = normalize(canonicalize(expression, dialect="sqlite"))
    for join in expression.find_all(exp.Join):
        if join.kind.upper() == "INNER":
            join.set("kind", None)
    for connector, combine in ((exp.And, exp.and_), (exp.Or, exp.or_)):
        roots = [
            node
            for node in expression.find_all(connector)
            if not isinstance(node.parent, connector)
        ]
        for root in roots:
            root.replace(
                combine(
                    *sorted(root.flatten(), key=lambda item: item.sql()),
                    copy=False,
                    wrap=False,
                )
            )
    for node in (*expression.find_all(exp.Select), *expression.find_all(exp.Group)):
        node.set("expressions", sorted(node.expressions, key=lambda item: item.sql()))
    return expression


@cache
def _schema(db_path: str) -> dict[str, dict[str, str]]:
    with sqlite3.connect(db_path) as connection:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        return {
            table: {
                row[1]: row[2] or "TEXT"
                for row in connection.execute(f"PRAGMA table_info({_quote(table)})")
            }
            for table in tables
        }


@cache
def _foreign_keys(db_path: str) -> dict[tuple[str, str], tuple[str, str]]:
    parents: dict[tuple[str, str], tuple[str, str]] = {}

    def find(column: tuple[str, str]) -> tuple[str, str]:
        parents.setdefault(column, column)
        while parents[column] != column:
            parents[column] = parents[parents[column]]
            column = parents[column]
        return column

    def union(left: tuple[str, str], right: tuple[str, str]) -> None:
        left, right = find(left), find(right)
        if left != right:
            parents[max(left, right)] = min(left, right)

    with sqlite3.connect(db_path) as connection:
        for table in _schema(db_path):
            for row in connection.execute(f"PRAGMA foreign_key_list({_quote(table)})"):
                target = row[4] or next(
                    column[1]
                    for column in connection.execute(
                        f"PRAGMA table_info({_quote(row[2])})"
                    )
                    if column[5] == 1
                )
                union((table.lower(), row[3].lower()), (row[2].lower(), target.lower()))
    return {column: find(column) for column in parents}


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'
