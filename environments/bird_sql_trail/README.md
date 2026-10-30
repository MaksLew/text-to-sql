# bird-sql-trail

SQL-Trail-inspired `verifiers.v1` taskset for the BIRD development split.

Each task gives the model the natural-language question and complete SQLite schema, with BIRD evidence included as task data in the system prompt. Difficulty labels are not loaded. The model can run read-only SQL through a single `database.query` tool, which returns column names and at most 50 rows, then must return one final SQL query.

## Setup and validation

Use the same BIRD data as `bird-v1`:

```bash
./scripts/download_bird.sh
uv run vf-validate bird-sql-trail --runtime.type subprocess
```

## Evaluation

The checked-in API config runs GPT-5.6 Luna with the schema-and-evidence prompt and database query tool:

```bash
uv run --env-file .env vf-eval @ configs/bird-sql-trail-gpt-5.6-luna.toml --dry-run
uv run --env-file .env vf-eval @ configs/bird-sql-trail-gpt-5.6-luna.toml -n 3 --no-push
uv run --env-file .env vf-eval @ configs/bird-sql-trail-gpt-5.6-luna.toml -n 200
```

Choose the number of tasks at launch with `-n`. Omitting `-n` runs the full split.

## Reward

The total reward ranges from 0 to 10:

- execution correctness × 5;
- correctness-gated query efficiency × 2;
- schema-link Jaccard similarity × 1;
- SQL-token bigram Jaccard similarity × 1;
- executable syntax × 1.

Query efficiency is `execution_correctness * max(0, (budget - query_calls) / budget)`. Execution correctness uses the existing BIRD set-equality evaluator.
