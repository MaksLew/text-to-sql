#!/usr/bin/env python3
import argparse
import json
from collections import defaultdict
from pathlib import Path


def summarize(path: Path) -> dict:
    traces_path = path / "traces.jsonl" if path.is_dir() else path
    episodes = [json.loads(line) for line in traces_path.read_text().splitlines() if line.strip()]
    traces = [trace for episode in episodes for trace in episode.get("traces", [episode])]

    rewards: dict[str, list[float]] = defaultdict(list)
    metrics: dict[str, list[float]] = defaultdict(list)
    usage: dict[str, int] = defaultdict(int)
    failed: dict[str, list[str]] = defaultdict(list)

    for trace in traces:
        for name, value in trace.get("rewards", {}).items():
            rewards[name].append(float(value.get("score", 0) if isinstance(value, dict) else value))
        for name, value in trace.get("metrics", {}).items():
            metrics[name].append(float(value))
        for call in trace.get("calls", []):
            for name, value in call.get("usage", {}).items():
                usage[name] += value or 0
        if trace.get("rewards", {}).get("execution_accuracy", {}).get("score") == 0:
            data = trace.get("task", {}).get("data", {})
            failed[data.get("db_id", "unknown")].append(data.get("name", "unknown"))

    return {
        "traces": len(traces),
        "rewards": rewards,
        "metrics": metrics,
        "episode_errors": sum(bool(episode.get("errors")) for episode in episodes),
        "trace_errors": sum(bool(trace.get("errors")) for trace in traces),
        "sql_errors": sum("sql_error" in trace.get("info", {}) for trace in traces),
        "metric_errors": sum("exact_set_match_error" in trace.get("info", {}) for trace in traces),
        "usage": usage,
        "tool_calls": sum(
            node.get("message", {}).get("role") == "tool"
            for trace in traces
            for node in trace.get("nodes", [])
        ),
        "failed": failed,
    }


def print_scores(title: str, scores: dict[str, list[float]]) -> None:
    print(f"{title}:")
    for name, values in sorted(scores.items()):
        total = sum(values)
        average = total / len(values) if values else 0
        count = f"{total:g}/{len(values)}" if all(value in (0, 1) for value in values) else f"mean {average:.4f}"
        print(f"  {name}: {count} ({average:.1%})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize a Verifiers evaluation run")
    parser.add_argument("run", type=Path, help="run directory or traces.jsonl path")
    args = parser.parse_args()

    result = summarize(args.run)
    print(f"Traces: {result['traces']}")
    print_scores("Rewards", result["rewards"])
    print_scores("Metrics", result["metrics"])
    print(
        "Errors: "
        f"{result['episode_errors']} episode, {result['trace_errors']} trace, "
        f"{result['sql_errors']} SQL, {result['metric_errors']} metric parser"
    )
    usage = result["usage"]
    print(
        "Usage: "
        f"{usage.get('prompt_tokens', 0):,} input, {usage.get('completion_tokens', 0):,} output, "
        f"{usage.get('cached_input_tokens', 0):,} cached, {usage.get('reasoning_tokens', 0):,} reasoning"
    )
    print(f"Tool calls: {result['tool_calls']}")
    if result["failed"]:
        print("Failed execution accuracy:")
        for db_id, names in sorted(result["failed"].items()):
            print(f"  {db_id}: {', '.join(names)}")


if __name__ == "__main__":
    main()
