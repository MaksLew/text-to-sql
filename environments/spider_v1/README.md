# spider-v1

Native `verifiers.v1` taskset for Spider 1.0 schema-to-SQL evaluation.

It loads the public development split from `data/spider_data`, renders canonical Spider schema metadata as `CREATE TABLE` statements, and scores generated SQL by read-only execution against the gold query.

From the repository root:

```bash
uv sync
./scripts/download_spider.sh
uv run eval @ configs/spider-openai.toml -n 3 --no-push
```

Config fields:

- `env.taskset.split`: currently `dev`
- `env.taskset.data-dir`: extracted Spider data directory
- `env.taskset.task.condition`: `schema` or `agentic`; agentic mode omits the schema and exposes read-only database tools

The agentic condition uses the MCP-capable built-in `null` harness; see `configs/spider-agentic-openai.toml`.

The environment reports original-database execution accuracy as its reward and Spider Exact Set Match as a metric. It does not yet calculate official Spider Test Suite Accuracy.
