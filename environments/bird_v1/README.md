# bird-v1

Agentic BIRD dev environment: 1,534 SQLite text-to-SQL tasks with evidence, database inspection tools, and official execution-accuracy scoring.

```bash
scripts/setup.sh bird
uv run validate bird-v1 --runtime.type subprocess
uv run eval @ configs/bird-agentic-openai.toml
```

The downloaded BIRD data is CC BY-NC 4.0 and is ignored by git.
